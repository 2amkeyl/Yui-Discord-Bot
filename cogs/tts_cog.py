import asyncio
import io
import math
import re
import time
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

from core.common import ERROR_COLOR, make_embed, log
from stores.tts_store import load_user_langs, save_user_langs

TTS_MAX_CHARS = 200          # giới hạn độ dài mỗi lần đọc
TTS_MAX_QUEUE = 5            # số lượt đọc tối đa đang chờ trong 1 server
TTS_IDLE_SECONDS = 60        # rảnh chừng này giây thì Yui tự rời phòng voice
TTS_USER_DELAY_SECONDS = 8.0 # delay giữa 2 lần dùng /say của cùng 1 người
TTS_GAP_SECONDS = 1.0        # khoảng nghỉ giữa 2 câu đọc liên tiếp trong hàng chờ
TTS_DEFAULT_LANG = "vi"

TTS_LANG_CHOICES = [
    Choice(name="Tiếng Việt", value="vi"),
    Choice(name="English", value="en"),
    Choice(name="日本語", value="ja"),
    Choice(name="한국어", value="ko"),
    Choice(name="中文", value="zh-CN"),
]

LANG_NAMES = {c.value: c.name for c in TTS_LANG_CHOICES}

FFMPEG_TTS_OPTS = "-vn"

_URL_RE = re.compile(r"https?://\S+", re.I)
_CUSTOM_EMOJI_RE = re.compile(r"<a?:\w+:\d+>")
_USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
_ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")
_CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
_SPACES_RE = re.compile(r"\s+")


def clean_tts_text(text: str, guild: Optional[discord.Guild]) -> str:
    """Đổi mention thành tên, bỏ link/emoji tuỳ chỉnh để giọng đọc không đọc ra mã lằng nhằng."""
    def _user(m):
        member = guild.get_member(int(m.group(1))) if guild else None
        return member.display_name if member else "một người nào đó"

    def _role(m):
        role = guild.get_role(int(m.group(1))) if guild else None
        return role.name if role else "một vai trò"

    def _channel(m):
        ch = guild.get_channel(int(m.group(1))) if guild else None
        return ch.name if ch else "một kênh"

    text = _USER_MENTION_RE.sub(_user, text)
    text = _ROLE_MENTION_RE.sub(_role, text)
    text = _CHANNEL_MENTION_RE.sub(_channel, text)
    text = _CUSTOM_EMOJI_RE.sub(" ", text)
    text = _URL_RE.sub(" liên kết ", text)
    text = text.replace("@everyone", "mọi người").replace("@here", "mọi người")
    return _SPACES_RE.sub(" ", text).strip()


def synth_tts(text: str, lang: str) -> bytes:
    """Chạy trong thread (gTTS là hàm đồng bộ, gọi mạng tới Google)."""
    from gtts import gTTS
    buf = io.BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


class TTSItem:
    __slots__ = ("audio", "text", "requester_name", "requester_avatar")

    def __init__(self, audio: bytes, text: str, requester: discord.abc.User):
        self.audio = audio
        self.text = text
        self.requester_name = requester.display_name
        self.requester_avatar = requester.display_avatar.url


class GuildTTSState:
    __slots__ = ("queue", "playing", "idle_task", "text_channel_id")

    def __init__(self):
        self.queue: list[TTSItem] = []
        self.playing = False
        self.idle_task: Optional[asyncio.Task] = None
        self.text_channel_id: Optional[int] = None


class TTSCog(commands.Cog, name="Đọc Giọng"):
    """Yui vào phòng voice và đọc to nội dung cậu nhập (TTS)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildTTSState] = {}
        self._last_say: dict[int, float] = {}
        self.user_langs: dict[str, str] = {u: l for u, l in load_user_langs().items() if l in LANG_NAMES}

    def get_state(self, guild_id: int) -> GuildTTSState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildTTSState()
        return self.states[guild_id]

    async def cog_unload(self):
        for state in self.states.values():
            if state.idle_task:
                state.idle_task.cancel()
        for vc in list(self.bot.voice_clients):
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass

    # ── Phát tuần tự trong hàng chờ ───────────────────────────────────────
    def _cancel_idle(self, state: GuildTTSState):
        if state.idle_task:
            state.idle_task.cancel()
            state.idle_task = None

    def _schedule_idle_leave(self, guild: discord.Guild, state: GuildTTSState):
        self._cancel_idle(state)

        async def _leave_later():
            try:
                await asyncio.sleep(TTS_IDLE_SECONDS)
            except asyncio.CancelledError:
                return
            vc = guild.voice_client
            if vc and not vc.is_playing() and not state.queue:
                await vc.disconnect()

        state.idle_task = asyncio.create_task(_leave_later())

    async def _play_next(self, guild: discord.Guild, delay: float = 0.0):
        state = self.get_state(guild.id)
        if delay > 0:
            await asyncio.sleep(delay)  # nghỉ 1 nhịp giữa các câu cho đỡ dính nhau
        vc = guild.voice_client
        if vc is None or not vc.is_connected():
            state.queue.clear()
            state.playing = False
            return
        if not state.queue:
            state.playing = False
            self._schedule_idle_leave(guild, state)
            return

        item = state.queue.pop(0)
        state.playing = True
        self._cancel_idle(state)
        source = discord.FFmpegPCMAudio(io.BytesIO(item.audio), pipe=True, options=FFMPEG_TTS_OPTS)

        def _after(error: Optional[Exception]):
            if error:
                log(f"Lỗi khi phát TTS: {error}", "warn")
            fut = asyncio.run_coroutine_threadsafe(self._play_next(guild, TTS_GAP_SECONDS), self.bot.loop)
            fut.add_done_callback(lambda f: f.exception() and log(f"Lỗi chuyển lượt TTS: {f.exception()}", "warn"))

        try:
            vc.play(source, after=_after)
        except Exception as e:
            log(f"Không phát được TTS: {e}", "warn")
            state.playing = False
            await self._play_next(guild)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Bot bị kick khỏi phòng voice -> dọn hàng chờ
        if self.bot.user and member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            state = self.states.get(member.guild.id)
            if state:
                self._cancel_idle(state)
                state.queue.clear()
                state.playing = False

    # ── Lệnh /say ────────────────────────────────────────────────────────
    @app_commands.command(name="leave", description="Cho Yui rời phòng voice (chỉ người đang ở cùng phòng với Yui)")
    async def leave(self, interaction: discord.Interaction):
        guild = interaction.guild
        vc = guild.voice_client if guild else None
        if guild is None or vc is None or not vc.is_connected():
            return await interaction.response.send_message(embed=make_embed("Yui có ở trong phòng voice nào đâu mà đòi đuổi!", color=ERROR_COLOR, guild=guild), ephemeral=True)

        voice = getattr(interaction.user, "voice", None)
        if voice is None or voice.channel is None or voice.channel.id != vc.channel.id:
            return await interaction.response.send_message(embed=make_embed(f"Cậu phải ở cùng phòng voice **{vc.channel.name}** với Yui thì mới đuổi Yui được nha!", color=ERROR_COLOR, guild=guild), ephemeral=True)

        channel_name = vc.channel.name
        state = self.get_state(guild.id)
        self._cancel_idle(state)
        state.queue.clear()
        state.playing = False
        try:
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await vc.disconnect()
        except Exception as e:
            log(f"Lỗi khi rời phòng voice: {e}", "warn")
            return await interaction.response.send_message(embed=make_embed("Yui rời phòng hổng được, thử lại sau nha!", color=ERROR_COLOR, guild=guild), ephemeral=True)

        await interaction.response.send_message(embed=make_embed(
            f"Yui rời **{channel_name}** rồi, bai bai nha! Cần thì gọi Yui lại bằng `/say` :3",
            title="Yui đi đây~", guild=guild,
        ))

    @app_commands.command(name="language", description="Chọn ngôn ngữ giọng đọc riêng cho cậu khi dùng /say")
    @app_commands.describe(lang="Ngôn ngữ muốn dùng (bỏ trống để xem ngôn ngữ hiện tại)")
    @app_commands.choices(lang=TTS_LANG_CHOICES)
    async def language(self, interaction: discord.Interaction, lang: Optional[Choice[str]] = None):
        uid = str(interaction.user.id)
        if lang is None:
            current = self.user_langs.get(uid, TTS_DEFAULT_LANG)
            desc = f"Ngôn ngữ đọc của cậu hiện là **{LANG_NAMES.get(current, current)}**.\nMuốn đổi thì dùng lại lệnh này và chọn ngôn ngữ nha :3"
            return await interaction.response.send_message(embed=make_embed(desc, title="Ngôn ngữ giọng đọc", guild=interaction.guild))

        self.user_langs[uid] = lang.value
        await asyncio.to_thread(save_user_langs, dict(self.user_langs))
        await interaction.response.send_message(embed=make_embed(
            f"Xong rồi! Từ giờ `/say` của cậu sẽ đọc bằng **{lang.name}** nha :3",
            title="Đã lưu ngôn ngữ", guild=interaction.guild,
        ))

    @app_commands.command(name="say", description="Yui đọc to nội dung cậu nhập trong phòng voice (TTS)")
    @app_commands.describe(
        text=f"Nội dung Yui sẽ đọc (tối đa {TTS_MAX_CHARS} ký tự)",
        lang="Chọn ngôn ngữ cho lần này (mặc định dùng ngôn ngữ đã lưu bằng /language)",
    )
    @app_commands.choices(lang=TTS_LANG_CHOICES)
    async def say(self, interaction: discord.Interaction, text: str, lang: Optional[Choice[str]] = None):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(embed=make_embed("Lệnh này chỉ dùng được trong server thôi nha!", color=ERROR_COLOR), ephemeral=True)

        voice = getattr(interaction.user, "voice", None)
        if voice is None or voice.channel is None:
            return await interaction.response.send_message(embed=make_embed("Cậu phải vào phòng voice trước thì Yui mới đọc cho nghe được chứ!", color=ERROR_COLOR, guild=guild), ephemeral=True)
        channel = voice.channel

        cleaned = clean_tts_text(text, guild)
        if not cleaned:
            return await interaction.response.send_message(embed=make_embed("Hổng có gì để Yui đọc hết á!", color=ERROR_COLOR, guild=guild), ephemeral=True)
        if len(cleaned) > TTS_MAX_CHARS:
            return await interaction.response.send_message(embed=make_embed(f"Dài quá, Yui chỉ đọc tối đa **{TTS_MAX_CHARS}** ký tự thôi nha! (bài của cậu **{len(cleaned)}** ký tự)", color=ERROR_COLOR, guild=guild), ephemeral=True)

        perms = channel.permissions_for(guild.me)
        if not (perms.connect and perms.speak):
            return await interaction.response.send_message(embed=make_embed(f"Yui hổng có quyền vào hoặc nói trong **{channel.name}** rồi!", color=ERROR_COLOR, guild=guild), ephemeral=True)

        state = self.get_state(guild.id)
        vc = guild.voice_client
        if vc and vc.channel != channel and (vc.is_playing() or state.queue):
            return await interaction.response.send_message(embed=make_embed(f"Yui đang đọc cho người khác ở **{vc.channel.name}**, đợi xíu nha!", color=ERROR_COLOR, guild=guild), ephemeral=True)
        if len(state.queue) >= TTS_MAX_QUEUE:
            return await interaction.response.send_message(embed=make_embed("Hàng chờ đọc đầy rồi, đợi Yui đọc xong bớt đã nha!", color=ERROR_COLOR, guild=guild), ephemeral=True)

        # Delay giữa 2 lần /say của cùng 1 người (chỉ tính khi lệnh hợp lệ, gõ sai không bị phạt)
        uid_int = interaction.user.id
        now = time.monotonic()
        wait = TTS_USER_DELAY_SECONDS - (now - self._last_say.get(uid_int, -1e9))
        if wait > 0:
            return await interaction.response.send_message(embed=make_embed(f"Từ từ đã nào, đợi thêm **{math.ceil(wait)} giây** nữa rồi `/say` tiếp nha!", color=ERROR_COLOR, guild=guild), ephemeral=True)
        self._last_say[uid_int] = now

        await interaction.response.defer(ephemeral=True)
        lang_code = lang.value if lang else self.user_langs.get(str(interaction.user.id), TTS_DEFAULT_LANG)

        try:
            audio = await asyncio.to_thread(synth_tts, cleaned, lang_code)
        except Exception as e:
            log(f"Lỗi tạo giọng TTS: {e}", "warn")
            self._last_say.pop(uid_int, None)
            return await interaction.followup.send(embed=make_embed("Yui hổng tạo được giọng đọc lúc này, thử lại sau nha!", color=ERROR_COLOR, guild=guild))

        try:
            if vc is None or not vc.is_connected():
                vc = await channel.connect(timeout=15, self_deaf=True)
            elif vc.channel != channel:
                await vc.move_to(channel)
        except Exception as e:
            log(f"Lỗi vào phòng voice cho TTS: {e}", "warn")
            self._last_say.pop(uid_int, None)
            return await interaction.followup.send(embed=make_embed("Yui hổng vào được phòng voice, thử lại sau nha!", color=ERROR_COLOR, guild=guild))

        state.text_channel_id = interaction.channel_id
        was_busy = vc.is_playing() or vc.is_paused() or state.playing
        state.queue.append(TTSItem(audio, cleaned, interaction.user))

        # Không gửi thông báo "đang đọc / xếp hàng" nữa -> xoá luôn tin nhắn "đang suy nghĩ" của defer
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

        if not was_busy:
            await self._play_next(guild)
