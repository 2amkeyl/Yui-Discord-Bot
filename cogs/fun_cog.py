import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import requests
from typing import Optional
from datetime import datetime, timedelta, timezone

from core.common import ERROR_COLOR, make_embed, log, rate_limiter

VN_TZ = timezone(timedelta(hours=7))

# ==============================================================================
# ── CẤU HÌNH API LẤY GIF ──────────────────────────────────────────────────────
# ==============================================================================

NEKOS_BEST_BASE = "https://nekos.best/api/v2"
NEKOS_CATEGORIES = {
    "hug", "cuddle", "kiss", "pat", "slap",
    "poke", "highfive", "handhold", "cry", "dance", "nom",
    "kick", "tickle", "stare", "punch"
}

# ── CACHE GIF theo category ──
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
    "hug": {"category": "hug", "lines": ["{a} lao vào ôm chầm lấy {b}", "{a} đè {b} ra ôm cứng ngắc, đéo cho thoát!"]},
    "cuddle": {"category": "cuddle", "lines": ["{a} rúc vào người {b} cọ cọ như con cờ hó!", "{a} dụi dụi vào người {b} tởm vãi lều!"]},
    "kiss": {"category": "kiss", "lines": ["{a} đè {b} ra bú mỏ chùn chụt!", "{a} cưỡng hôn {b} ướt nhẹp cmn hết cái mặt!"]},
    "pat": {"category": "pat", "lines": ["{a} xoa đầu {b} như xoa đầu cún!", "{a} vuốt ve cái đầu ngu ngốc của {b}!"]},
    "slap": {"category": "slap", "lines": ["{a} vả vỡ mẹ mõm {b}!", "{a} tát lật cmn mặt {b}, chừa cái thói láo cá chó đi!"]},
    "kill": {"category": "kick", "lines": ["{a} xiên chết cụ {b}!", "{a} tiễn {b} về chầu ông bà cmnl!"]},
    "poke": {"category": "poke", "lines": ["{a} chọc lủng cmn má {b}!", "{a} lấy ngón tay chọt chọt trêu chó {b}!"]},
    "highfive": {"category": "highfive", "lines": ["{a} đập tay {b} cái chát đau điếng cmn tay!", "{a} đập tay với {b} bung cmn móng!"]},
    "handhold": {"category": "handhold", "lines": ["{a} nắm chặt tay {b} đéo buông, ớn lạnh vãi!", "{a} đan tay {b} sến súa vãi cớt!"]},
    "tickle": {"category": "tickle", "lines": ["{a} thò tay móc nách cù léc {b} cười sặc cmn cứt!", "{a} cù léc {b} giãy đành đạch như chó dại!"]},
    "cry": {"category": "cry", "lines": ["{a} khóc rống lên bám áo {b} ăn vạ!", "{a} rớt nước mắt cá sấu ướt cmn áo {b}!"]},
    "dance": {"category": "dance", "lines": ["{a} kéo {b} lên nhảy múa quạt như thằng ngáo đá!", "{a} và {b} quẩy tung cmn nóc, sập mẹ sàn rồi!"]},
    "nom": {"category": "nom", "lines": ["{a} ngoạm cmn một miếng {b}, ngon vãi cả cứt!", "{a} cắn nghiến {b} như cẩu đói ba ngày!"]},
    "stare": {"category": "stare", "lines": ["{a} trợn mắt nhìn {b} như nhìn thứ ba đầu sáu tay!", "{a} nhìn {b} chằm chằm, dòm cái gì mà dòm lắm thế?!"]},
    "punch": {"category": "punch", "lines": ["{a} đấm vỡ mẹ mồm {b}!", "{a} nện {b} một cú trời giáng, gãy cmn răng luôn!"]},
    "snuggle": {"category": "cuddle", "lines": ["{a} rúc sát vào {b} như con đỉa bám!", "{a} chui tọt vào lòng {b}, đéo chịu ra!"]},
}

# ==============================================================================
# ── /HOM-NAY-AN-GI: MÂM CƠM NGẪU NHIÊN + NÚT ĐỔI MÓN RIÊNG TỪNG LOẠI ──────────
# ==============================================================================

class FoodRerollView(discord.ui.View):
    """3 nút 🎲 đổi riêng món chính / món phụ / đồ uống, không đổi cả mâm."""

    def __init__(self, food_menu: dict, author_id: int, buoi: str, main: str, side: str, drink: str,
                 flavor: str, outro: str, now_vn: datetime, guild: Optional[discord.Guild]):
        super().__init__(timeout=120)
        self.food_menu = food_menu
        self.author_id = author_id
        self.buoi = buoi
        self.main = main
        self.side = side
        self.drink = drink
        self.flavor = flavor
        self.outro = outro
        self.now_vn = now_vn
        self.guild = guild
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Cái này không phải mâm của cậu đâu, tự gọi lệnh đi nha!", ephemeral=True)
            return False
        return True

    def build_embed(self) -> discord.Embed:
        desc = (
            f"**Hốc cái này**: {self.main}\n"
            f"**Tráng miệng**: {self.side}\n"
            f"**Tu nốt**: {self.drink}\n\n"
            f"{self.flavor}\n"
            f"{self.outro}\n\n"
            f"-# Giờ VN: {self.now_vn.strftime('%H:%M')}"
        )
        return make_embed(desc, title=f"Hôm nay nạp gì? ({self.buoi})", guild=self.guild)

    def _reroll(self, category: str, current: str) -> str:
        options = self.food_menu[self.buoi][category]
        choices = [o for o in options if o != current] or options
        return random.choice(choices)

    @discord.ui.button(label="Đổi món chính", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def reroll_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.main = self._reroll("main", self.main)
        await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(label="Đổi món phụ", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def reroll_side(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.side = self._reroll("side", self.side)
        await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(label="Đổi đồ uống", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def reroll_drink(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.drink = self._reroll("drink", self.drink)
        await interaction.response.edit_message(embed=self.build_embed())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class FunCog(commands.Cog, name="Tương Tác"):
    """Ôm, cắn, tát... nhau và mâm cơm ngẫu nhiên mỗi ngày"""

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
                embed=make_embed(
                    f"Yui bị lỗi nội bộ với lệnh này rồi, báo admin giùm nha!",
                    color=ERROR_COLOR,
                    guild=interaction.guild,
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

    # ── TƯƠNG TÁC (ACTIONS) ───────────────────────────────────────────

    @app_commands.command(name="hug", description="Ôm 1 đứa thật chặt")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def hug(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "hug", member)

    @app_commands.command(name="cuddle", description="Cọ cọ vào người 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def cuddle(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "cuddle", member)

    @app_commands.command(name="kiss", description="Bú mỏ 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def kiss(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "kiss", member)

    @app_commands.command(name="pat", description="Xoa đầu 1 đứa ngốc")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def pat(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "pat", member)

    @app_commands.command(name="slap", description="Tát 1 đứa lật mặt")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def slap(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "slap", member)

    @app_commands.command(name="kill", description="Tiễn 1 đứa lên bảng đếm số")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def kill(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "kill", member)

    @app_commands.command(name="poke", description="Chọc ngoáy 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def poke(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "poke", member)

    @app_commands.command(name="highfive", description="Đập tay mẻ xương")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def highfive(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "highfive", member)

    @app_commands.command(name="handhold", description="Nắm chặt tay 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def handhold(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "handhold", member)

    @app_commands.command(name="tickle", description="Cù léc 1 đứa sặc luôn")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def tickle(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "tickle", member)

    @app_commands.command(name="cry", description="Ăn vạ 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def cry(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "cry", member)

    @app_commands.command(name="dance", description="Kéo 1 đứa lên múa quạt")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def dance(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "dance", member)

    @app_commands.command(name="nom", description="Cắn ngấu nghiến 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def nom(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "nom", member)

    @app_commands.command(name="stare", description="Trợn mắt nhìn 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def stare(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "stare", member)

    @app_commands.command(name="punch", description="Đấm 1 đứa cho tỉnh")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def punch(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "punch", member)

    @app_commands.command(name="snuggle", description="Rúc sát vào 1 đứa")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def snuggle(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, "snuggle", member)

    # ── /hom-nay-an-gi ────────────────────────────────────────────────
    FOOD_MENU = {
        "Buổi sáng": {
            "main": ["Cháo sườn", "Bánh mì trứng", "Xôi gà", "Phở bò", "Bún riêu", "Bánh cuốn"],
            "side": ["Dưa lưới", "Sữa chua", "Chuối", "Táo", "Xoài"],
            "drink": ["Sữa đậu nành", "Cà phê sữa đá", "Trà đào", "Sinh tố bơ"],
        },
        "Buổi trưa": {
            "main": ["Cơm sườn", "Bún bò Huế", "Cơm gà xối mỡ", "Mì Quảng", "Bánh xèo", "Cơm tấm"],
            "side": ["Dưa hấu", "Chè đậu xanh", "Trái cây thập cẩm", "Sữa chua nếp cẩm"],
            "drink": ["Trà tắc", "Nước mía", "Trà sữa trân châu", "Nước cam"],
        },
        "Buổi tối": {
            "main": ["Lẩu thái", "Cơm chiên dương châu", "Bún chả", "Cháo lòng", "Hủ tiếu", "Bò kho bánh mì"],
            "side": ["Kem", "Bánh flan", "Chè khúc bạch", "Trái cây dầm"],
            "drink": ["Trà chanh", "Nước ép ổi", "Cacao nóng", "Nước lọc"],
        },
    }

    FLAVOR_LINES = [
        "Ăn lẹ đi rồi còn xách đít lên làm việc!",
        "Nuốt cho trôi, cấm chê dở nha!",
        "Ăn xong rửa chén, đừng có lười!",
        "Bày đặt chê ỏng chê eo tao nhét nguyên cái bát vào mồm giờ!",
        "Ngon thế này mà chê nữa thì mài cạo rỉ sắt ra mà ăn nhé con lợn!",
        "Cơm bưng nước rót tận miệng rồi, hốc nhanh đi khóc lóc cái gì?",
        "Dạo này cái nọng cằm mài sắp rớt xuống gối rồi đấy, táp vừa vừa thôi!",
        "Ế mốc meo ra thì lo mà ăn cho có sức chống chọi với cô đơn đi cưng!",
        "Thực đơn vip pro, không ăn thì nhịn đói ráng chịu nha cái đồ kén cá chọn canh!",
    ]

    OUTRO_LINES = [
        "Uống từ từ thôi kẻo sặc nước đéo ai rảnh gọi cấp cứu đâu!",
        "Tu nhanh lên rồi cút đi rửa bát, lười như hủi!",
        "Ăn xong cái mồm thối um cả server rồi, nhớ đi đánh răng giùm!",
        "Nhai cho kỹ vào kẻo nghẹn, tao không chịu trách nhiệm đâu!",
        "Ăn xong thì đứng lên đi lại cho tiêu cơm, ngồi trương thây ra đấy à?",
        "Táp ít thôi coi chừng mập!",
    ]

    @app_commands.command(name="hom-nay-an-gi", description="Nấu mâm cơm cho những đứa lười suy nghĩ")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def hom_nay_an_gi(self, interaction: discord.Interaction):
        now_vn = datetime.now(VN_TZ)
        hour = now_vn.hour
        if hour < 10:
            buoi = "Buổi sáng"
        elif hour < 16:
            buoi = "Buổi trưa"
        else:
            buoi = "Buổi tối"

        menu = self.FOOD_MENU[buoi]
        main = random.choice(menu["main"])
        side = random.choice(menu["side"])
        drink = random.choice(menu["drink"])
        flavor = random.choice(self.FLAVOR_LINES)
        outro = random.choice(self.OUTRO_LINES)

        view = FoodRerollView(self.FOOD_MENU, interaction.user.id, buoi, main, side, drink, flavor, outro, now_vn, interaction.guild)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()
