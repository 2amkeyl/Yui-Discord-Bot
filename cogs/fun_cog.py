import discord
from discord.ext import commands
from discord import app_commands
import json
import random
import asyncio
import requests
from pathlib import Path
from typing import Optional
from datetime import datetime

from core.common import VN_TZ, ROOT_DIR, HEART, make_embed, log, rate_limiter, err_embed

GACHA_DATA_DIR = Path(ROOT_DIR) / "data" / "toinayxemgi"
GACHA_ACTRESSES_PATH = GACHA_DATA_DIR / "actresses.json"
GACHA_IMAGES_DIR = GACHA_DATA_DIR / "actresses"


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


class GachaRerollView(discord.ui.View):
    """Nút 🎲 quay lại /toi-nay-xem-gi (chỉ người gọi lệnh bấm được)."""

    def __init__(self, cog: "FunCog", author_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Cái nút này là của người khác, cậu tự gõ lệnh `/toi-nay-xem-gi` đi nha!", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Quay tiếp", style=discord.ButtonStyle.primary, emoji="🎲")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.send_gacha(interaction, is_reroll=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


def _make_action_command(key: str, description: str) -> app_commands.Command:
    """Tạo lệnh /<key> <member> dùng chung một khuôn: cooldown 5s rồi gọi FunCog._interact."""
    async def callback(self, interaction: discord.Interaction, member: discord.Member):
        await self._interact(interaction, key, member)

    callback.__name__ = key
    # discord.py dựa vào qualname "Lớp.hàm" để biết đây là method của cog (có tham số self)
    callback.__qualname__ = f"FunCog.{key}"
    callback = app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)(callback)
    return app_commands.command(name=key, description=description)(callback)


class FunCog(commands.Cog, name="Tương Tác"):
    """Ôm, cắn, tát... nhau, mâm cơm và gacha tối nay xem gì"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._gacha_list: list[dict] = []
        self._gacha_last: dict[int, int] = {}
        self._load_gacha_data()

    def _load_gacha_data(self):
        try:
            with open(GACHA_ACTRESSES_PATH, "r", encoding="utf-8") as f:
                self._gacha_list = json.load(f)
            log(f"Đã nạp {len(self._gacha_list)} diễn viên cho /toi-nay-xem-gi", "ok")
        except Exception as e:
            log(f"Lỗi nạp data /toi-nay-xem-gi: {e}", "error")

    async def send_gacha(self, interaction: discord.Interaction, is_reroll: bool):
        if not self._gacha_list:
            await interaction.response.send_message(f"Chưa nạp được dữ liệu, thử lại sau nha {HEART}", ephemeral=True)
            return

        user_id = interaction.user.id
        last = self._gacha_last.get(user_id)
        pool = [a for a in self._gacha_list if a["index"] != last] or self._gacha_list
        actress = random.choice(pool)
        self._gacha_last[user_id] = actress["index"]

        image_name = Path(actress["image_file"]).name
        image_path = GACHA_IMAGES_DIR / image_name

        embed = make_embed(
            f"Debut: **{actress['debut']}**  •  Số video: **{actress['videos']}**\n[Xem thêm]({actress['href']})",
            title=actress["name"],
            guild=interaction.guild,
        )
        files = []
        if image_path.exists():
            files.append(discord.File(image_path, filename=image_name))
            embed.set_image(url=f"attachment://{image_name}")

        view = GachaRerollView(self, user_id)
        if is_reroll:
            # attachments=... thay sạch ảnh cũ của tin nhắn hiện tại
            await interaction.response.edit_message(embed=embed, attachments=files, view=view)
            view.message = interaction.message
        else:
            await interaction.response.send_message(embed=embed, files=files, view=view)
            view.message = await interaction.original_response()

    @app_commands.command(name="toi-nay-xem-gi", description="Gacha random 1 diễn viên nên xem tối nay :3")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def toi_nay_xem_gi(self, interaction: discord.Interaction):
        await self.send_gacha(interaction, is_reroll=False)

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


    # 16 lệnh tương tác (/hug, /kiss, /slap...) được sinh từ bảng ACTIONS ở trên, xem _make_action_command.
    locals().update({key: _make_action_command(key, cfg["desc"]) for key, cfg in ACTIONS.items()})

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
