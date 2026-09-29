import asyncio
import os

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from core.common import ERROR_COLOR, log, make_embed, set_footer_guild

from cogs.badge_cog import BadgeCog
from cogs.utility_cog import UtilityCog
from cogs.fun_cog import FunCog
from cogs.gacha_cog import GachaCog
from cogs.economy_cog import EconomyCog
from cogs.minigame_cog import MinigameCog
from cogs.profile_cog import ProfileCog
from cogs.tts_cog import TTSCog
from cogs.prefix_bridge import PrefixBridgeCog

load_dotenv()

async def _cooldown_countdown_warning(interaction: discord.Interaction, seconds: int):
    def _text(n: int) -> str:
        return f"{interaction.user.mention} từ từ đã nào, đợi thêm **{n} giây** nữa rồi dùng lại lệnh này nha!"
    try:
        await interaction.response.send_message(_text(seconds))
    except discord.HTTPException: return

    remaining = seconds
    while remaining > 1:
        await asyncio.sleep(1)
        remaining -= 1
        try: await interaction.edit_original_response(content=_text(remaining))
        except discord.HTTPException: return
    await asyncio.sleep(1)
    try: await interaction.delete_original_response()
    except discord.HTTPException: pass

class YuiCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        set_footer_guild(interaction.guild)
        return True
        
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            seconds = max(1, round(error.retry_after))
            asyncio.create_task(_cooldown_countdown_warning(interaction, seconds))
            return

        cmd_name = interaction.command.qualified_name if interaction.command else "?"
        log(f"Lỗi không xử lý được ở lệnh '/{cmd_name}': {error}", "error")

        embed = make_embed(
            f"Yui vấp cục đá gì đó rồi, lệnh này bị lỗi mất tiêu! Thử lại sau nha.",
            color=ERROR_COLOR,
            guild=interaction.guild,
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True 
        # Prefix `yui<lệnh>` chạy qua PrefixBridgeCog (prefix_bridge.py), nên command_prefix của discord.py
        # chỉ để giữ chỗ: chỉ phản ứng khi mention bot và không có lệnh ext.commands nào đăng ký.
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, tree_cls=YuiCommandTree)

    async def setup_hook(self):
        await self.add_cog(BadgeCog(self))
        await self.add_cog(UtilityCog(self))
        await self.add_cog(FunCog(self))
        await self.add_cog(GachaCog(self))
        await self.add_cog(EconomyCog(self))
        await self.add_cog(MinigameCog(self))
        await self.add_cog(ProfileCog(self))
        await self.add_cog(TTSCog(self))
        await self.add_cog(PrefixBridgeCog(self))

        await self.tree.sync()
        log("Đã đồng bộ toàn bộ hệ thống bot!", "ok")

bot = MyBot()

@bot.event
async def on_ready():
    activity = discord.Activity(type=discord.ActivityType.listening, name="/help • yui help | Yui Hirasawa")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    log(f"Yui lên sàn! Bot {bot.user} sẵn sàng phục vụ toàn bộ chức năng!", "ok")

async def run_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        return log("BOT_TOKEN is missing", "error")
    try:
        await bot.start(token)
    except Exception as e:
        log(f"Discord error: {e}", "error")

if __name__ == "__main__":
    if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_bot())
