"""Cầu nối prefix: gọi mọi slash command bằng `yui<lệnh> [tham số]` (viết liền, vd `yuihug @ai_do`).

Không cần sửa từng cog: bridge đọc danh sách lệnh trong bot.tree, tự parse tham số theo
đúng kiểu của slash command rồi chạy callback với một "interaction giả" (PrefixInteraction)
có đủ các hàm mà code hiện tại đang dùng (response.send_message, followup.send, defer,
original_response, edit_original_response...). Cooldown, check quyền và error handler của
từng lệnh vẫn được chạy như bình thường.
"""
import re
import unicodedata
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.common import ERROR_COLOR, make_embed, log

PREFIX = "yui"
# Viết liền với tên lệnh: `yuihug @ai_do`. Vẫn nhận `yui hug` (có cách) cho đỡ nhầm tay.
PREFIX_RE = re.compile(rf"^{PREFIX}\s*", re.I)

# Tên gọi tắt khi dùng prefix: `yuicf` = `yuicoinflip`
PREFIX_ALIASES = {"cf": "coinflip"}

# Các lệnh dựa vào tin nhắn ẩn (ephemeral) để nhập thông tin riêng tư -> để nguyên, chỉ dùng slash.
SLASH_ONLY = {"quest", "hypesquad", "badge"}

_SEND_KWARGS = {"content", "embed", "embeds", "file", "files", "view", "allowed_mentions",
                "delete_after", "suppress_embeds", "silent", "poll"}
_EDIT_KWARGS = {"content", "embed", "embeds", "attachments", "view", "allowed_mentions", "delete_after"}
_SAFE_MENTIONS = discord.AllowedMentions(users=True, roles=False, everyone=False, replied_user=False)


class UsageError(Exception):
    pass


def split_params(cmd: app_commands.Command) -> tuple[list, list]:
    """Tách tham số của lệnh thành (tail, main).

    tail = các lựa chọn TUỲ CHỌN đứng sau chuỗi cuối cùng (vd `lang` của /say). Ở prefix chúng được
    nhập ở đầu (`yuisay en hello`) vì chuỗi cuối nuốt hết phần còn lại của tin nhắn."""
    params = list(cmd.parameters)
    last_str = max((i for i, p in enumerate(params)
                    if p.type is discord.AppCommandOptionType.string and not p.choices), default=-1)
    tail: list = []
    if last_str >= 0:
        for p in params[last_str + 1:]:
            if not p.required and p.choices:
                tail.append(p)
            else:
                tail = []
                break
    main = [p for p in params if p not in tail]
    return tail, main


# Nhãn hiển thị riêng cho lựa chọn khi gọi bằng prefix (vd `yuicoinflip 100 sap`)
USAGE_LABELS = {("coinflip", "mat"): "ngua|sap"}


def _greedy_param(main: list):
    """Tham số chuỗi cuối cùng (nuốt hết phần còn lại của tin nhắn), nếu có."""
    if main and main[-1].type is discord.AppCommandOptionType.string and not main[-1].choices:
        return main[-1]
    return None


def prefix_usage(cmd: app_commands.Command) -> str:
    """Cách gọi lệnh bằng prefix, vd: `yuigive <member> <amount>`."""
    tail, main = split_params(cmd)
    parts = [f"{PREFIX}{cmd.qualified_name}"]
    greedy = _greedy_param(main)
    # chuỗi cuối là tuỳ chọn -> lựa chọn được phép đứng cuối (vd `yuicoinflip 100 sap`)
    ordered = main + tail if greedy is not None and not greedy.required else tail + main
    for p in ordered:
        label = USAGE_LABELS.get((cmd.name, p.name)) or (
            "|".join(str(c.value) for c in p.choices) if p.choices else p.display_name)
        parts.append(f"<{label}>" if p.required else f"[{label}]")
    return " ".join(parts)


def supports_prefix(cmd: app_commands.Command) -> bool:
    return cmd.name not in SLASH_ONLY


def _take(text: str) -> tuple[str, str]:
    """Tách token đầu tiên khỏi phần còn lại (giữ nguyên phần còn lại)."""
    m = re.match(r"\s*(\S+)\s*(.*)", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", "")


def _fold(text: str) -> str:
    """Bỏ dấu tiếng Việt + hạ chữ thường để 'ngua' khớp 'Ngửa'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").casefold()


def _match_choice(param, token: str):
    key = _fold(token)
    for c in param.choices:
        first_word = str(c.name).split()[0] if str(c.name).split() else ""
        if key in {_fold(str(c.value)), _fold(str(c.name)), _fold(first_word)}:
            return c
    return None


# ==============================================================================
# ── INTERACTION GIẢ CHO PREFIX ────────────────────────────────────────────────
# ==============================================================================

class _Response:
    def __init__(self, inter: "PrefixInteraction"):
        self._i = inter
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: Any = None, **kwargs):
        self._done = True
        self._i._message = await self._i._send(content, **kwargs)

    async def defer(self, **kwargs):
        self._done = True
        await self._i._typing()

    async def edit_message(self, **kwargs):
        raise NotImplementedError("edit_message chỉ dùng cho tương tác nút bấm thật")

    async def send_modal(self, modal):
        raise NotImplementedError("send_modal chỉ dùng được với slash / nút bấm")


class _Followup:
    def __init__(self, inter: "PrefixInteraction"):
        self._i = inter

    async def send(self, content: Any = None, **kwargs) -> discord.Message:
        msg = await self._i._send(content, **kwargs)
        if self._i._message is None:
            self._i._message = msg
        return msg


class PrefixInteraction:
    """Đóng vai discord.Interaction cho lệnh gọi bằng prefix (chỉ có phần code trong bot đang dùng)."""

    def __init__(self, bot: commands.Bot, message: discord.Message, command: app_commands.Command):
        self.client = bot
        self._origin = message
        self.command = command
        self.user = message.author
        self.guild = message.guild
        self.guild_id = message.guild.id if message.guild else None
        self.channel = message.channel
        self.channel_id = message.channel.id
        self.created_at = message.created_at
        self.type = discord.InteractionType.application_command
        self.command_failed = False
        self.extras: dict = {}
        self.is_prefix = True
        self._message: Optional[discord.Message] = None
        self.response = _Response(self)
        self.followup = _Followup(self)

    @property
    def permissions(self) -> discord.Permissions:
        return self.channel.permissions_for(self.user)

    @property
    def app_permissions(self) -> discord.Permissions:
        return self.channel.permissions_for(self.guild.me) if self.guild else discord.Permissions.none()

    async def _typing(self):
        try:
            await self.channel._state.http.send_typing(self.channel.id)
        except Exception:
            pass

    async def _send(self, content: Any = None, **kwargs) -> discord.Message:
        # prefix không có tin nhắn ẩn -> ephemeral/wait/thinking... bị bỏ qua
        payload = {k: v for k, v in kwargs.items() if k in _SEND_KWARGS and v is not None}
        payload.setdefault("allowed_mentions", _SAFE_MENTIONS)
        if content is not None:
            payload["content"] = content
        try:
            return await self._origin.reply(mention_author=False, **payload)
        except discord.HTTPException:
            # tin nhắn gốc bị xoá -> gửi thẳng vào kênh
            return await self.channel.send(**payload)

    async def original_response(self) -> discord.Message:
        if self._message is None:
            raise RuntimeError("Chưa có phản hồi nào để lấy lại")
        return self._message

    async def edit_original_response(self, **kwargs) -> discord.Message:
        payload = {k: v for k, v in kwargs.items() if k in _EDIT_KWARGS}
        if self._message is None:
            # chưa có tin nhắn nào (vd: mới defer) -> gửi tin nhắn đầu tiên
            atts = payload.pop("attachments", None)
            if atts:
                payload["files"] = [a for a in atts if isinstance(a, discord.File)]
            payload = {k: v for k, v in payload.items() if v is not None}
            self.response._done = True
            self._message = await self._send(payload.pop("content", None), **payload)
            return self._message
        self._message = await self._message.edit(**payload)
        return self._message

    async def delete_original_response(self) -> None:
        if self._message is not None:
            await self._message.delete()
            self._message = None


# ==============================================================================
# ── COG CẦU NỐI ───────────────────────────────────────────────────────────────
# ==============================================================================

class PrefixBridgeCog(commands.Cog, name="Prefix"):
    """Cho phép gọi lệnh bằng `yui<lệnh>` (viết liền)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── tìm lệnh ─────────────────────────────────────────────────────────
    def find_command(self, rest: str) -> tuple[Optional[app_commands.Command], str]:
        name, args = _take(rest)
        name = name.lower()
        name = PREFIX_ALIASES.get(name, name)
        if not name:
            return None, ""
        cmd = self.bot.tree.get_command(name)
        if cmd is None and args:
            # cho phép "yui noitu stop" / "yui toi-nay xem-gi": ghép 2 từ bằng _ hoặc -
            second, remaining = _take(args)
            for sep in ("_", "-"):
                cmd = self.bot.tree.get_command(f"{name}{sep}{second.lower()}")
                if cmd is not None:
                    return (cmd, remaining) if isinstance(cmd, app_commands.Command) else (None, "")
        if not isinstance(cmd, app_commands.Command):
            return None, ""
        return cmd, args

    # ── parse tham số ────────────────────────────────────────────────────
    async def _resolve_user(self, message: discord.Message, token: str):
        guild = message.guild
        m = re.fullmatch(r"<@!?(\d+)>|(\d{15,20})", token)
        if m:
            uid = int(m.group(1) or m.group(2))
            member = guild.get_member(uid)
            if member is None:
                try:
                    member = await guild.fetch_member(uid)
                except discord.HTTPException:
                    member = None
            if member is not None:
                return member
            try:
                return await self.bot.fetch_user(uid)
            except discord.HTTPException:
                raise UsageError("Yui hổng tìm thấy người này đâu!")
        name = token.lstrip("@").casefold()
        found = discord.utils.find(
            lambda mem: mem.name.casefold() == name or mem.display_name.casefold() == name, guild.members
        )
        if found is None:
            raise UsageError(f"Yui hổng tìm thấy **{token}** trong server này!")
        return found

    def _replied_user(self, message: discord.Message):
        ref = message.reference
        resolved = ref.resolved if ref else None
        if isinstance(resolved, discord.Message):
            return message.guild.get_member(resolved.author.id) or resolved.author
        return None

    async def _convert(self, message: discord.Message, p, token: str):
        t = p.type
        T = discord.AppCommandOptionType
        if t is T.string:
            if p.choices:
                c = _match_choice(p, token)
                if c is None:
                    raise UsageError(f"**{p.display_name}** phải là một trong: " + ", ".join(f"`{c.value}`" for c in p.choices))
                return c
            if p.max_value is not None and len(token) > p.max_value:
                raise UsageError(f"**{p.display_name}** dài quá (tối đa {int(p.max_value)} ký tự)")
            if p.min_value is not None and len(token) < p.min_value:
                raise UsageError(f"**{p.display_name}** ngắn quá (tối thiểu {int(p.min_value)} ký tự)")
            return token
        if t in (T.integer, T.number):
            if p.choices:
                c = _match_choice(p, token)
                if c is None:
                    raise UsageError(f"**{p.display_name}** phải là một trong: " + ", ".join(f"`{c.value}`" for c in p.choices))
                return c
            try:
                cleaned = token.replace(",", "").replace("_", "")
                value = int(cleaned) if t is T.integer else float(cleaned)
            except ValueError:
                raise UsageError(f"**{p.display_name}** phải là một con số")
            if p.min_value is not None and value < p.min_value:
                raise UsageError(f"**{p.display_name}** tối thiểu là {p.min_value:g}")
            if p.max_value is not None and value > p.max_value:
                raise UsageError(f"**{p.display_name}** tối đa là {p.max_value:g}")
            return value
        if t is T.boolean:
            low = _fold(token)
            if low in {"true", "yes", "y", "1", "on", "co", "bat"}:
                return True
            if low in {"false", "no", "n", "0", "off", "khong", "tat"}:
                return False
            raise UsageError(f"**{p.display_name}** phải là có/không")
        if t in (T.user, T.mentionable):
            return await self._resolve_user(message, token)
        if t is T.channel:
            m = re.fullmatch(r"<#(\d+)>|(\d{15,20})", token)
            ch = message.guild.get_channel(int(m.group(1) or m.group(2))) if m else None
            if ch is None:
                raise UsageError(f"**{p.display_name}** phải là một kênh (#kênh)")
            return ch
        if t is T.role:
            m = re.fullmatch(r"<@&(\d+)>|(\d{15,20})", token)
            role = message.guild.get_role(int(m.group(1) or m.group(2))) if m else None
            if role is None:
                raise UsageError(f"**{p.display_name}** phải là một vai trò (@role)")
            return role
        raise UsageError("Lệnh này cần dữ liệu mà prefix không nhập được, cậu dùng slash nha!")

    async def parse_args(self, message: discord.Message, cmd: app_commands.Command, text: str) -> dict:
        rest = text.strip()
        kwargs: dict[str, Any] = {}

        tail, main = split_params(cmd)
        greedy = _greedy_param(main)
        all_optional = all(not p.required for p in main)
        for p in tail:
            # 1) lựa chọn đứng đầu: `yuicoinflip sap 100` (hoặc `yuicoinflip sap` khi các tham số còn lại đều tuỳ chọn)
            token, remaining = _take(rest)
            c = _match_choice(p, token) if token else None
            if c is not None and (remaining or all_optional):
                kwargs[p.name] = c
                rest = remaining
                continue
            # 2) lựa chọn đứng cuối: `yuicoinflip 100 sap` (chỉ khi chuỗi cuối là tuỳ chọn, không ăn nhầm nội dung)
            if greedy is not None and not greedy.required:
                m = re.match(r"^(.*\S)\s+(\S+)\s*$", rest, re.S)
                if m:
                    c = _match_choice(p, m.group(2))
                    if c is not None:
                        kwargs[p.name] = c
                        rest = m.group(1)

        for idx, p in enumerate(main):
            is_greedy = p.type is discord.AppCommandOptionType.string and not p.choices and idx == len(main) - 1
            if is_greedy:
                token, rest = rest, ""
            else:
                token, rest = _take(rest)

            if not token:
                if p.type in (discord.AppCommandOptionType.user, discord.AppCommandOptionType.mentionable):
                    replied = self._replied_user(message)
                    if replied is not None:
                        kwargs[p.name] = replied
                        continue
                if p.required:
                    raise UsageError(f"Thiếu **{p.display_name}**")
                continue
            kwargs[p.name] = await self._convert(message, p, token)
        return kwargs

    # ── chạy lệnh ────────────────────────────────────────────────────────
    async def run_command(self, message: discord.Message, cmd: app_commands.Command, arg_text: str):
        inter = PrefixInteraction(self.bot, message, cmd)
        tree = self.bot.tree

        try:
            if not await tree.interaction_check(inter):  # type: ignore[arg-type]
                return
            kwargs = await self.parse_args(message, cmd, arg_text)
        except UsageError as e:
            embed = make_embed(f"{e}\n\nCách dùng: `{prefix_usage(cmd)}`", color=ERROR_COLOR, guild=message.guild)
            await inter._send(None, embed=embed)
            return

        try:
            try:
                if not await cmd._check_can_run(inter):  # type: ignore[arg-type]
                    raise app_commands.CheckFailure(f"Check của lệnh {cmd.name!r} không qua")
                await cmd.callback(cmd.binding, inter, **kwargs)  # type: ignore[misc]
            except app_commands.AppCommandError:
                raise
            except Exception as e:
                raise app_commands.CommandInvokeError(cmd, e) from e
        except app_commands.AppCommandError as e:
            inter.command_failed = True
            try:
                await cmd._invoke_error_handlers(inter, e)  # type: ignore[arg-type]
                await tree.on_error(inter, e)  # type: ignore[arg-type]
            except Exception as handler_err:
                log(f"Lỗi khi xử lý lỗi của '{PREFIX} {cmd.name}': {handler_err}", "error")

    # ── nghe tin nhắn ────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or not message.content:
            return
        m = PREFIX_RE.match(message.content)
        if not m:
            return
        cmd, arg_text = self.find_command(message.content[m.end():])
        if cmd is None:
            return
        if not supports_prefix(cmd):
            return  # lệnh chỉ dùng slash: để nguyên
        await self.run_command(message, cmd, arg_text)
