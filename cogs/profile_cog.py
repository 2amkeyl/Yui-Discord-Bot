from typing import Optional
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

from core.common import ERROR_COLOR, make_embed


async def resolve_guild_member(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
    """Ưu tiên lấy Member từ cache của guild (không tốn HTTP request); chỉ gọi
    fetch_member khi cache miss, để tránh spam rate limit khi nhiều người dùng
    /avatar liên tục."""
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


class ProfileImageView(discord.ui.View):
    """View hiển thị giao diện động: Nút Mở Ảnh + Các nút chuyển đổi Server/Global"""

    def __init__(self, target: discord.User, requester: discord.User, global_url: str, guild_url: Optional[str], is_banner: bool = False, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.target = target
        self.requester = requester
        self.global_url = global_url
        self.guild_url = guild_url
        self.is_banner = is_banner
        self.current_mode = "server" if guild_url else "global"
        self.message: Optional[discord.Message] = None
        self.update_buttons()

    def update_buttons(self):
        """Cập nhật lại các nút bấm dựa trên trạng thái hiện tại"""
        self.clear_items()
        current_url = self.guild_url if self.current_mode == "server" else self.global_url
        label_prefix = "Banner" if self.is_banner else "Ảnh"

        self.add_item(discord.ui.Button(
            label=f"Mở {label_prefix}", 
            style=discord.ButtonStyle.link, 
            url=current_url
        ))

        if self.guild_url and self.global_url:
            btn_server = discord.ui.Button(
                label="Ảnh Server",
                style=discord.ButtonStyle.success if self.current_mode == "server" else discord.ButtonStyle.secondary
            )
            btn_server.callback = self.show_server
            self.add_item(btn_server)

            btn_global = discord.ui.Button(
                label="Ảnh Cá Nhân",
                style=discord.ButtonStyle.success if self.current_mode == "global" else discord.ButtonStyle.secondary
            )
            btn_global.callback = self.show_global
            self.add_item(btn_global)

    def build_embed(self, guild: Optional[discord.Guild]) -> discord.Embed:
        """Tạo embed giao diện mới"""
        current_url = self.guild_url if self.current_mode == "server" else self.global_url
        title_text = f"{self.target.display_name}'s {'Banner' if self.is_banner else 'Avatar'}"

        desc = (
            f"**Tên đăng nhập:** {self.target.name}\n"
            f"**Tên hiển thị:** {self.target.display_name}\n"
            f"**ID:** `{self.target.id}`"
        )

        embed = make_embed(desc, title=title_text, guild=guild)
        
        embed.set_image(url=current_url)

        months = ["", "Một", "Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Tám", "Chín", "Mười", "Mười Một", "Mười Hai"]
        now = datetime.now()
        date_str = f"{now.day} Tháng {months[now.month]} {now.year} {now.strftime('%H:%M')}"
        
        embed.set_footer(text=f"Yêu cầu bởi {self.requester.name} • {date_str}")

        return embed

    async def show_server(self, interaction: discord.Interaction):
        self.current_mode = "server"
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(interaction.guild), view=self)

    async def show_global(self, interaction: discord.Interaction):
        self.current_mode = "global"
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(interaction.guild), view=self)

    async def on_timeout(self):
        for item in self.children:
            # Chỉ vô hiệu hóa các nút chức năng, giữ nút Link
            if item.style != discord.ButtonStyle.link:
                item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ProfileCog(commands.Cog, name="Hồ Sơ"):
    """Xem avatar/banner cá nhân & avatar/banner riêng theo server"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="avatar", description="Xem avatar cá nhân và avatar riêng theo server của một người")
    @app_commands.describe(member="Người muốn xem avatar (mặc định là chính bạn)")
    @app_commands.checks.cooldown(1, 5)
    async def avatar_cmd(self, interaction: discord.Interaction, member: Optional[discord.User] = None):
        target = member or interaction.user
        await interaction.response.defer()

        try:
            user = await self.bot.fetch_user(target.id)
        except discord.NotFound:
            return await interaction.followup.send(embed=make_embed(f"Yui hổng tìm thấy người này đâu!", color=ERROR_COLOR, guild=interaction.guild))

        global_url = user.display_avatar.url
        guild_url = None
        if interaction.guild:
            gm = await resolve_guild_member(interaction.guild, target.id)
            if gm and gm.guild_avatar:
                guild_url = gm.guild_avatar.url

        view = ProfileImageView(
            target=user, 
            requester=interaction.user, 
            global_url=global_url, 
            guild_url=guild_url, 
            is_banner=False
        )
        
        embed = view.build_embed(interaction.guild)
        view.message = await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="banner", description="Xem banner cá nhân và banner riêng theo server của một người")
    @app_commands.describe(member="Người muốn xem banner (mặc định là chính bạn)")
    @app_commands.checks.cooldown(1, 5)
    async def banner_cmd(self, interaction: discord.Interaction, member: Optional[discord.User] = None):
        target = member or interaction.user
        await interaction.response.defer()

        try:
            user = await self.bot.fetch_user(target.id)
        except discord.NotFound:
            return await interaction.followup.send(embed=make_embed(f"Yui hổng tìm thấy người này đâu!", color=ERROR_COLOR, guild=interaction.guild))

        global_url = user.banner.url if user.banner else None
        guild_url = None
        if interaction.guild:
            try:
                gm = await interaction.guild.fetch_member(target.id)
            except discord.NotFound:
                gm = None
            if gm and getattr(gm, "guild_banner", None):
                guild_url = gm.guild_banner.url

        if not global_url and not guild_url:
            return await interaction.followup.send(embed=make_embed(f"{target.mention} chưa đặt banner nào cả! :3", color=ERROR_COLOR, guild=interaction.guild))

        view = ProfileImageView(
            target=user, 
            requester=interaction.user, 
            global_url=global_url, 
            guild_url=guild_url, 
            is_banner=True
        )
        
        embed = view.build_embed(interaction.guild)
        view.message = await interaction.followup.send(embed=embed, view=view)
