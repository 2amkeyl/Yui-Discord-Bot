import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import requests
from typing import Optional

from core.common import make_embed, log, rate_limiter, err_embed

NEKOS_BEST_BASE = "https://nekos.best/api/v2"

GIF_CACHE_MAX = 30
_gif_cache: dict[str, list[str]] = {}

def _cache_add(category: str, url: str) -> None:
    bucket = _gif_cache.setdefault(category, [])
    if url in bucket:
        bucket.remove(url)
    bucket.append(url)
    if len(bucket) > GIF_CACHE_MAX:
        del bucket[0]

def _cache_pick(category: str) -> Optional[str]:
    bucket = _gif_cache.get(category)
    return random.choice(bucket) if bucket else None

def _fetch_gif_sync(category: str) -> Optional[str]:
    try:
        r = requests.get(f"{NEKOS_BEST_BASE}/{category}", timeout=6)
        if r.status_code == 429:
            log(f"RATE LIMITED [{category}] status=429", level="warn")
            return None
        if r.status_code != 200:
            log(f"Fetch fail [{category}] status={r.status_code}", level="warn")
            return None
        res = r.json().get("results")
        url = res[0].get("url") if res else None
        if url:
            _cache_add(category, url)
        return url
    except Exception as e:
        log(f"Fetch error [{category}]: {e}", level="error")
        return None

async def fetch_action_gif(category: str) -> Optional[str]:
    url = await asyncio.to_thread(_fetch_gif_sync, category)
    if url:
        return url

    cached = _cache_pick(category)
    if cached:
        log(f"Using cached gif [{category}] (API unavailable)", level="warn")
        return cached
    return None

ACTIONS: dict[str, dict] = {
    "hug": {"desc": "Ôm 1 đứa thật chặt", "category": "hug", "lines": ["{a} lao vào ôm chầm lấy {b}", "{a} đè {b} ra ôm cứng ngắc, đéo cho thoát!"]},
    "cuddle": {"desc": "Cọ cọ vào người 1 đứa", "category": "cuddle", "lines": ["{a} rúc vào người {b} cọ cọ như con cờ hó!", "{a} dụi dụi vào người {b} tởm vãi lều!"]},
    "kiss": {"desc": "Bú mỏ 1 đứa", "category": "kiss", "lines": ["{a} đè {b} ra bú mỏ chùn chụt!", "{a} cưỡng hôn {b} ướt nhẹp cmn hết cái mặt!"]},
    "pat": {"desc": "Xoa đầu 1 đứa ngốc", "category": "pat", "lines": ["{a} xoa đầu {b} như xoa đầu cún!", "{a} vuốt ve cái đầu ngu ngốc của {b}!"]},
    "slap": {"desc": "Tát 1 đứa lật mặt", "category": "slap", "lines": ["{a} vả vỡ mẹ mõm {b}!", "{a} tát lật cmn mặt {b}, chừa cái thói láo cá chó đi!"]},
    "kill": {"desc": "Tiễn 1 đứa lên bảng đếm số", "category": "kick", "lines": ["{a} xiên chết cụ {b}!", "{a} tiễn {b} về chầu ông bà cmnl!"]},
    "poke": {"desc": "Chọc ngoáy 1 đứa", "category": "poke", "lines": ["{a} chọc lủng cmn má {b}!", "{a} lấy ngón tay chọt chọt trêu chó {b}!"]},
    "highfive": {"desc": "Đập tay mẻ xương", "category": "highfive", "lines": ["{a} đập tay {b} cái chát đau điếng cmn tay!", "{a} đập tay với {b} bung cmn móng!"]},
    "handhold": {"desc": "Nắm chặt tay 1 đứa", "category": "handhold", "lines": ["{a} nắm chặt tay {b} đéo buông, ớn lạnh vãi!", "{a} đan tay {b} sến súa vãi cớt!"]},
    "tickle": {"desc": "Cù léc 1 đứa sặc luôn", "category": "tickle", "lines": ["{a} thò tay móc nách cù léc {b} cười sặc cmn cứt!", "{a} cù léc {b} giãy đành đạch như chó dại!"]},
    "cry": {"desc": "Ăn vạ 1 đứa", "category": "cry", "lines": ["{a} khóc rống lên bám áo {b} ăn vạ!", "{a} rớt nước mắt cá sấu ướt cmn áo {b}!"]},
    "dance": {"desc": "Kéo 1 đứa lên múa quạt", "category": "dance", "lines": ["{a} kéo {b} lên nhảy múa quạt như thằng ngáo đá!", "{a} và {b} quẩy tung cmn nóc, sập mẹ sàn rồi!"]},
    "nom": {"desc": "Cắn ngấu nghiến 1 đứa", "category": "nom", "lines": ["{a} ngoạm cmn một miếng {b}, ngon vãi cả cứt!", "{a} cắn nghiến {b} như cẩu đói ba ngày!"]},
    "stare": {"desc": "Trợn mắt nhìn 1 đứa", "category": "stare", "lines": ["{a} trợn mắt nhìn {b} như nhìn thứ ba đầu sáu tay!", "{a} nhìn {b} chằm chằm, dòm cái gì mà dòm lắm thế?!"]},
    "punch": {"desc": "Đấm 1 đứa cho tỉnh", "category": "punch", "lines": ["{a} đấm vỡ mẹ mồm {b}!", "{a} nện {b} một cú trời giáng, gãy cmn răng luôn!"]},
    "snuggle": {"desc": "Rúc sát vào 1 đứa", "category": "cuddle", "lines": ["{a} rúc sát vào {b} như con đỉa bám!", "{a} chui tọt vào lòng {b}, đéo chịu ra!"]},
}


def _make_action_command(key: str, description: str) -> app_commands.Command:
    async def callback(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, key, member)

    callback.__name__ = key
    callback.__qualname__ = f"FunCog.{key}"
    callback = app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)(callback)
    return app_commands.command(name=key, description=description)(callback)


class FunCog(commands.Cog, name="Tương Tác"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _interact(self, interaction: discord.Interaction, action_key: str, member: discord.Member):
        if member.id == interaction.user.id:
            await interaction.response.send_message("Bắt buộc phải tag người khác cơ mà, tự tag mình chi vậy trời", ephemeral=True)
            return

        await interaction.response.defer()
        cfg = ACTIONS.get(action_key)
        if not cfg:
            log(f"Action key không tồn tại trong ACTIONS: '{action_key}'", "error")
            await interaction.followup.send(
                embed=err_embed(
                    "Yui bị lỗi nội bộ với lệnh này rồi, báo admin giùm nha!",
                    interaction.guild,
                )
            )
            return
        actor, target = interaction.user, member

        gif_url = await fetch_action_gif(cfg["category"])

        desc = random.choice(cfg["lines"]).format(a=actor.mention, b=target.mention)
        embed = make_embed(desc, guild=interaction.guild)
        if gif_url:
            embed.set_image(url=gif_url)

        await rate_limiter.acquire()
        await interaction.followup.send(embed=embed)

    locals().update({key: _make_action_command(key, cfg["desc"]) for key, cfg in ACTIONS.items()})
