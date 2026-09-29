import asyncio
import random

import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

from core.common import ERROR_COLOR, make_embed, safe_send
from stores.notify_store import load_disabled_guilds, save_disabled_guilds
from cogs.prefix_bridge import prefix_usage, supports_prefix

LEAVE_MESSAGES = [
    "Bai bai **{name}** nha! Hẹn cậu ở buổi trà chiều sau!",
    "**{name}** về rồi hả... Yui sẽ nhớ cậu lắm đó nha! :3",
    "Tạm biệt **{name}**! Nhớ quay lại chơi với Yui nha!",
    "**{name}** rời phòng rồi, hẹn gặp lại cậu sau nha!",
    "**{name}** đi ngủ hay đi đâu vậy ta... Ngủ ngon nha cậu!",
    "Buổi trà chiều với **{name}** tạm dừng ở đây thôi. Hẹn lần sau nha!",
]
JOIN_MESSAGES = [
    "**{name}** vừa đáp chuyến bay từ **{channel}** tới đây!",
    "**{name}** vừa ghé qua **{channel}**, chào mừng cậu nha :3",
    "**{name}** đã vào **{channel}**, Yui ôm ghi ta ra chào nè!",
    "Ơ, **{name}** ghé chơi hả! Vào **{channel}** ngồi chơi nha :3",
    "**{name}** tới rồi nè, **{channel}** vui hẳn lên luôn!",
    "Yui vừa pha xong trà thì **{name}** ghé **{channel}** đúng lúc ghê!",
]


HELP_HIDDEN = {"addcoin"}  # lệnh admin, không hiện trong /help


def build_help_categories(bot: commands.Bot) -> dict:
    """Duyệt bot.tree.get_commands() và gom theo Cog — thêm/bớt lệnh trong các
    cog sẽ tự động xuất hiện/biến mất khỏi /help, không cần sửa tay ở đây."""
    categories: dict[str, dict] = {}
    for cmd in bot.tree.get_commands():
        if not isinstance(cmd, app_commands.Command):
            continue  # bỏ qua app_commands.Group nếu có, không áp dụng ở đây
        if cmd.name in HELP_HIDDEN:
            continue
        cog = getattr(cmd, "binding", None)
        if cog is not None:
            key = cog.qualified_name
            desc = (cog.description or "Các lệnh trong nhóm này").strip()
        else:
            key = "Khác"
            desc = "Các lệnh khác"
        entry = categories.setdefault(key, {"desc": desc, "commands": []})
        entry["commands"].append(cmd)
    return categories


class HelpSelect(discord.ui.Select):
    def __init__(self, categories: dict):
        self.categories = categories
        options = [
            discord.SelectOption(label=key[:100], description=(data["desc"][:100] or None), value=key)
            for key, data in categories.items()
        ]
        super().__init__(placeholder="Chọn danh mục lệnh muốn xem...", options=options)

    def _category_embed(self, key: str, guild) -> discord.Embed:
        commands_ = self.categories[key]["commands"]
        lines = []
        for cmd in commands_:
            line = f"**/{cmd.qualified_name}**\nMô tả: {cmd.description}"
            if supports_prefix(cmd):
                line += f"\nPrefix: `{prefix_usage(cmd)}`"
            lines.append(line)
        return make_embed("\n\n".join(lines)[:4000], title=f"{key}", guild=guild)

    async def callback(self, interaction: discord.Interaction):
        embed = self._category_embed(self.values[0], interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, categories: dict):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(categories))


class UtilityCog(commands.Cog, name="Tiện Ích"):
    """Trợ giúp, thông báo voice & các cài đặt chung của server"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.disabled_notify_guilds: set = load_disabled_guilds()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or before.channel == after.channel:
            return
        guild = member.guild
        if guild.id in self.disabled_notify_guilds:
            return

        if after.channel is not None and before.channel != after.channel:
            perms = after.channel.permissions_for(guild.me)
            if perms.view_channel and perms.send_messages:
                text = random.choice(JOIN_MESSAGES).format(name=member.display_name, channel=after.channel.name)
                await safe_send(after.channel, text)
        elif before.channel is not None and after.channel is None:
            perms = before.channel.permissions_for(guild.me)
            if perms.view_channel and perms.send_messages:
                text = random.choice(LEAVE_MESSAGES).format(name=member.display_name, channel=before.channel.name)
                await safe_send(before.channel, text)

    @app_commands.command(name="thongbao", description="Bật/tắt thông báo Yui chào khi có người ra vào phòng voice (cần quyền Manage Server)")
    @app_commands.describe(trang_thai="Bật hay tắt thông báo cho cả server")
    @app_commands.choices(trang_thai=[Choice(name="Bật", value="on"), Choice(name="Tắt", value="off")])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_notify(self, interaction: discord.Interaction, trang_thai: Choice[str]):
        guild_id = interaction.guild_id
        if trang_thai.value == "off":
            self.disabled_notify_guilds.add(guild_id)
            msg = "Yui im re, hổng chào ai ra vào phòng voice nữa nha! :3"
        else:
            self.disabled_notify_guilds.discard(guild_id)
            msg = "Yui lại chào hỏi mọi người ra vào phòng voice rồi nha! :3"
        await asyncio.to_thread(save_disabled_guilds, self.disabled_notify_guilds)
        await interaction.response.send_message(embed=make_embed(msg, guild=interaction.guild))

    @toggle_notify.error
    async def toggle_notify_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(embed=make_embed("Cậu cần quyền Manage Server mới đổi được cái này nha!", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        else:
            raise error

    @app_commands.command(name="help", description="Xem danh sách lệnh của Yui theo từng danh mục")
    async def help_cmd(self, interaction: discord.Interaction):
        categories = build_help_categories(self.bot)
        total_cmds = sum(len(data["commands"]) for data in categories.values())
        embed = make_embed(
            "Chọn 1 danh mục ở menu bên dưới để xem các lệnh trong đó nha :3\n"
            "Ngoài slash, cậu còn gọi được bằng prefix `yui` viết liền với tên lệnh, vd `yuicash`, `yuihug @ai_đó`\n"
            f"-# Hiện Yui có tổng cộng **{total_cmds}** lệnh trong **{len(categories)}** danh mục",
            title=f"Danh sách các lệnh của Yui",
            guild=interaction.guild,
        )
        await interaction.response.send_message(embed=embed, view=HelpView(categories))
