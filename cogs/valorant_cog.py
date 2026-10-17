import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.common import EMBED_COLOR, make_embed, log, err_embed
from core.riot import (
    MANUAL_LOGIN_URL, VP_CURRENCY, Assets, NotLoggedIn, RiotError, SessionExpired, SkinInfo, ValorantService,
    login_with_tokens, parse_pasted_tokens,
)
from stores.valorant_store import valorant_store

# Emoji VP hiện sau giá. Bot cần ở trong server chứa emoji, và ở server khác thì cần quyền "Use External Emojis".
VP = "<:VP:1560259333269491752>"

# Emoji độ hiếm đặt trước tên skin: Select < Deluxe < Premium < Exclusive < Ultra.
# Để trống ("") một bậc thì bậc đó dùng icon nhỏ của Riot cạnh tên skin.
TIER_EMOJI = {
    "Select": "<:SE:1560264300335988756>",
    "Deluxe": "<:DE:1560264355604602890>",
    "Premium": "<:PE:1560264388928077894>",
    "Exclusive": "<:EE:1560264482352275506>",
    "Ultra": "<:UE:1560264531501125692>",
}

# Ghi đè màu viền embed theo độ hiếm (dạng 0xRRGGBB). Bỏ trống thì dùng màu gốc của Riot.
TIER_COLOR: dict = {}


def _tier_emoji(tier_name: str) -> str:
    """Tìm emoji theo tên bậc, không phân biệt hoa/thường (chịu được 'Ultra Edition', 'ultra'...)."""
    name = (tier_name or "").lower()
    for key, emoji in TIER_EMOJI.items():
        if emoji and name.startswith(key.lower()):
            return emoji
    return ""


def _vp(cost: dict) -> int:
    if VP_CURRENCY in cost:
        return int(cost[VP_CURRENCY])
    return int(next(iter(cost.values()), 0))


def _skin_embed(assets: Assets, item_id: str, price_text: str) -> discord.Embed:
    info = assets.skins.get(item_id) or SkinInfo(name="Skin chưa rõ tên", icon=None, tier=None)
    tier = assets.tiers.get(info.tier) if info.tier else None
    tier_name = tier.name if tier else ""
    color = TIER_COLOR.get(tier_name, tier.color if tier and tier.color is not None else EMBED_COLOR)
    embed = discord.Embed(description=price_text, color=color)
    emoji = _tier_emoji(tier_name)
    if emoji:
        embed.title = f"{emoji} {info.name}"
    else:
        embed.set_author(name=info.name, icon_url=tier.icon if tier and tier.icon else None)
    if info.icon:
        embed.set_thumbnail(url=info.icon)
    return embed


def build_daily(name: str, sf: dict, assets: Assets, guild) -> list[discord.Embed]:
    layout = sf.get("SkinsPanelLayout") or {}
    prices = {}
    for o in layout.get("SingleItemStoreOffers", []):
        price = _vp(o.get("Cost") or {})
        prices[o.get("OfferID")] = price
        for rw in o.get("Rewards", []):
            prices.setdefault(rw.get("ItemID"), price)
    ends = int(time.time()) + int(layout.get("SingleItemOffersRemainingDurationInSeconds", 0))
    embeds = [make_embed(f"Cửa hàng ngày hôm nay của **{name}**\n(làm mới <t:{ends}:R>)", guild=guild)]
    for item_id in layout.get("SingleItemOffers", []):
        price = prices.get(item_id)
        embeds.append(_skin_embed(assets, item_id, f"**{price}** {VP}" if price is not None else f"**?** {VP}"))
    return embeds


def build_night(name: str, sf: dict, assets: Assets, guild) -> Optional[list[discord.Embed]]:
    bonus = sf.get("BonusStore")
    if not bonus or not bonus.get("BonusStoreOffers"):
        return None
    ends = int(time.time()) + int(bonus.get("BonusStoreRemainingDurationInSeconds", 0))
    embeds = [make_embed(f"Night Market của **{name}**\n(kết thúc <t:{ends}:R>)", guild=guild)]
    for o in bonus["BonusStoreOffers"]:
        offer = o.get("Offer") or {}
        rewards = offer.get("Rewards") or [{}]
        item_id = rewards[0].get("ItemID", "")
        original = _vp(offer.get("Cost") or {})
        sale = _vp(o.get("DiscountCosts") or {})
        pct = int(o.get("DiscountPercent", 0))
        embeds.append(_skin_embed(assets, item_id, f"~~{original}~~ → **{sale}** {VP}  (-{pct}%)"))
    return embeds


class OwnerView(discord.ui.View):
    """View chỉ người gọi lệnh bấm được."""

    def __init__(self, owner_id: int, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("Nút này của người khác rồi, cậu tự gõ lệnh nha!", interaction.guild), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message is not None:
            try: await self.message.edit(view=None)
            except discord.HTTPException: pass


class LoginView(OwnerView):
    def __init__(self, cog: "ValorantCog", kind: str, owner_id: int):
        super().__init__(owner_id)
        self.cog, self.kind = cog, kind
        self.add_item(discord.ui.Button(label="Mở trang đăng nhập Riot", style=discord.ButtonStyle.link, url=MANUAL_LOGIN_URL))
        paste = discord.ui.Button(label="Dán link", style=discord.ButtonStyle.primary)
        paste.callback = self._paste
        self.add_item(paste)

    async def _paste(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LinkModal(self.cog, self.kind))


class AccountView(OwnerView):
    def __init__(self, cog: "ValorantCog", owner_id: int):
        super().__init__(owner_id)
        self.cog = cog

    @discord.ui.button(label="Đăng xuất", style=discord.ButtonStyle.danger)
    async def logout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.logout(interaction)


class _SafeModal(discord.ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        # Chỉ log tên lỗi, không log nội dung (có thể chứa link/token đăng nhập).
        log(f"Lỗi modal Valorant: {type(error).__name__}", "error")
        embed = err_embed("Yui vấp cục đá rồi, thử lại sau nha!", interaction.guild)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass


class LinkModal(_SafeModal, title="Dán link đăng nhập Riot"):
    text = discord.ui.TextInput(label="Link sau khi đăng nhập", style=discord.TextStyle.paragraph,
                                min_length=20, max_length=4000)

    def __init__(self, cog: "ValorantCog", kind: str):
        super().__init__()
        self.cog, self.kind = cog, kind

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.begin_link_login(interaction, self.text.value, self.kind)


class ValorantCog(commands.Cog, name="Valorant"):
    """Xem cửa hàng skin hằng ngày và Night Market Valorant"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = ValorantService(valorant_store)

    async def cog_unload(self):
        await self.service.close()

    @app_commands.command(name="shop", description="Xem cửa hàng skin Valorant hôm nay của cậu :3")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def shop(self, interaction: discord.Interaction):
        await self._run(interaction, "daily")

    @app_commands.command(name="nightmarket", description="Xem Night Market Valorant của cậu :3")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def nightmarket(self, interaction: discord.Interaction):
        await self._run(interaction, "night")

    async def _run(self, interaction: discord.Interaction, kind: str):
        if not valorant_store.available():
            return await interaction.response.send_message(
                embed=err_embed("Tính năng này cần thư viện `cryptography` nhưng máy chủ của Yui chưa cài, nhờ chủ bot cài giúp nha!",
                           interaction.guild), ephemeral=True)
        uid = str(interaction.user.id)
        if not valorant_store.has(uid):
            return await interaction.response.send_message(
                embed=self._login_embed(interaction.guild), view=LoginView(self, kind, interaction.user.id), ephemeral=True)
        await interaction.response.defer()
        await self._deliver(interaction, kind, ephemeral=False)

    def _login_embed(self, guild, *, expired: bool = False) -> discord.Embed:
        head = ("Phiên đăng nhập Riot của cậu hết hạn rồi (link chỉ sống khoảng 1 giờ), cậu lấy link mới để Yui xem shop tiếp nha!"
                if expired else "Để xem cửa hàng, Yui cần cậu đăng nhập Riot trước nè!")
        body = (
            f"{head}\n\n"
            "**1.** Bấm **Mở trang đăng nhập Riot** và đăng nhập như bình thường (đây là trang chính thức của Riot, Yui không thấy mật khẩu).\n"
            "**2.** Đăng nhập xong trình duyệt sẽ nhảy sang trang `playvalorant.com`, trang này báo lỗi hoặc trống là **bình thường**.\n"
            "**3.** Chạm vào thanh địa chỉ, **copy toàn bộ địa chỉ** (rất dài, có chữ `#access_token=`), rồi bấm **Dán link** ở đây.\n\n"
            "• Link cho phép xem tài khoản của cậu trong khoảng 1 giờ, **chỉ dán vào form của Yui**, đừng gửi cho ai khác. Yui chỉ **xem** cửa hàng, không mua gì hết.\n"
            "• Nếu địa chỉ mất phần `#access_token=`, thử mở trang đăng nhập bằng tab ẩn danh hoặc trình duyệt khác."
        )
        return make_embed(body, title="Đăng nhập Riot", guild=guild)

    async def _deliver(self, interaction: discord.Interaction, kind: str, *, ephemeral: bool):
        uid = str(interaction.user.id)
        guild = interaction.guild
        try:
            acct, sf = await self.service.storefront(uid)
            assets = await self.service.assets()
        except (NotLoggedIn, SessionExpired) as e:
            valorant_store.remove(uid)
            self.service.forget(uid)
            return await interaction.followup.send(
                embed=self._login_embed(guild, expired=isinstance(e, SessionExpired)),
                view=LoginView(self, kind, interaction.user.id), ephemeral=True)
        except RiotError as e:
            return await interaction.followup.send(embed=err_embed(e.user_message, guild), ephemeral=True)

        if kind == "night":
            embeds = build_night(acct["name"], sf, assets, guild)
            if embeds is None:
                return await interaction.followup.send(
                    embed=make_embed("Night Market chưa mở nè, khi nào có Yui sẽ hiện ở đây nha!", guild=guild), ephemeral=ephemeral)
        else:
            embeds = build_daily(acct["name"], sf, assets, guild)

        view = AccountView(self, interaction.user.id)
        view.message = await interaction.followup.send(embeds=embeds, view=view, ephemeral=ephemeral)

    async def begin_link_login(self, interaction: discord.Interaction, text: str, kind: str):
        uid = str(interaction.user.id)
        try:
            account, tokens = await login_with_tokens(parse_pasted_tokens(text))
        except RiotError as e:
            return await interaction.followup.send(embed=err_embed(e.user_message, interaction.guild), ephemeral=True)
        valorant_store.set(uid, account)
        self.service.prime(uid, tokens)
        await self._deliver(interaction, kind, ephemeral=True)

    async def logout(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        valorant_store.remove(uid)
        self.service.forget(uid)
        await interaction.response.send_message(
            embed=make_embed("Yui xoá phiên đăng nhập Riot của cậu rồi nha! Muốn chắc ăn hơn thì cậu đăng xuất các thiết bị trong cài đặt tài khoản Riot nữa nhé.",
                             guild=interaction.guild), ephemeral=True)
