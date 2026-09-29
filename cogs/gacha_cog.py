import asyncio
import json
import random
import time
import io
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from discord import app_commands

from core.common import log, HEART, ROOT_DIR
from stores.gacha_store import load_all_states, save_all_states, get_user_state

# Thử import Pillow để xử lý ảnh (Làm mờ/Crop)
try:
    from PIL import Image, ImageFilter
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    log("Chưa cài thư viện Pillow! Tính năng Preview làm mờ ảnh sẽ bị tắt. Hãy chạy 'pip install Pillow'.", "warn")

# ==============================================================================
# ── CẤU HÌNH ───────────────────────────────────────────────────────────────────
# ==============================================================================

DATA_DIR = Path(ROOT_DIR) / "data" / "toinayxemgi"
ACTRESSES_PATH = DATA_DIR / "actresses.json"
RARITY_MAP_PATH = DATA_DIR / "rarity-map.json"
IMAGES_DIR = DATA_DIR / "actresses"

TIER_INFO = {
    0: {"label": "Common", "color": 0x4B69FF},   
    1: {"label": "Rare", "color": 0x8847FF},     
    2: {"label": "Epic", "color": 0xEB4B4B},     
    3: {"label": "Mythic", "color": 0xE4AE39},   
}

PITY_MAX = 90
ROLL_COOLDOWN_SECONDS = 5
MAX_DAILY_ROLLS = 30
VN_TZ = timezone(timedelta(hours=7))

def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_gacha_date() -> str:
    """Trả về ngày hiện tại (Reset lúc 3:00 sáng giờ VN)"""
    now = datetime.now(VN_TZ)
    if now.hour < 3:
        now -= timedelta(days=1)
    return now.strftime("%Y-%m-%d")

# ==============================================================================
# ── VIEW: NÚT QUAY LẠI & LỊCH SỬ ───────────────────────────────────────────────
# ==============================================================================

class RerollView(discord.ui.View):
    def __init__(self, cog: "GachaCog", author_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"Cái nút này là của người khác, cậu tự gõ lệnh `/toi-nay-xem-gi` đi nha!", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Quay tiếp", style=discord.ButtonStyle.primary, emoji="🎲")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_roll(interaction, is_reroll=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class HistoryView(discord.ui.View):
    def __init__(self, history: list, author_id: int):
        super().__init__(timeout=180)
        self.history = history
        self.author_id = author_id
        self.page = 0
        self.max_page = max(0, (len(history) - 1) // 10)
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page == self.max_page)

    def build_embed(self) -> discord.Embed:
        start = self.page * 10
        end = start + 10
        items = self.history[start:end]
        
        lines = []
        for i, item in enumerate(items, start=start + 1):
            tier_info = TIER_INFO.get(item["tier"], TIER_INFO[0])
            time_str = f"<t:{item['time']}:R>"
            lines.append(f"**{i}.** [{tier_info['label']}] **{item['name']}** - {time_str}")
        
        embed = discord.Embed(title="Lịch Sử Gacha 📜", description="\n".join(lines), color=0xFFB6C1)
        embed.set_footer(text=f"Trang {self.page + 1}/{self.max_page + 1} | Tổng: {len(self.history)} roll (tối đa 100)")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Cậu không xem trộm lịch sử của người khác được đâu!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


# ==============================================================================
# ── COG CHÍNH ──────────────────────────────────────────────────────────────────
# ==============================================================================

class GachaCog(commands.Cog, name="Tối Nay Xem Gì"):
    """Gacha random 1 diễn viên nên xem tối nay"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._actresses_by_index: dict[int, dict] = {}
        self._rarity_map: dict[int, list[int]] = {}
        self._index_to_tier: dict[int, int] = {}
        self._last_roll_monotonic: dict[int, float] = {}
        self._states = load_all_states()
        self._load_data()

    def _load_data(self):
        try:
            actresses = _load_json(ACTRESSES_PATH)
            self._actresses_by_index = {a["index"]: a for a in actresses}

            raw_rarity = _load_json(RARITY_MAP_PATH)
            self._rarity_map = {int(tier): indices for tier, indices in raw_rarity.items()}
            
            self._index_to_tier = {}
            for tier, indices in self._rarity_map.items():
                for idx in indices:
                    self._index_to_tier[idx] = tier
                    
            log(f"Đã nạp {len(actresses)} diễn viên cho /toi-nay-xem-gi", "ok")
        except Exception as e:
            log(f"Lỗi nạp data /toi-nay-xem-gi: {e}", "error")

    def _create_preview_image(self, img_path: Path) -> Optional[io.BytesIO]:
        """Cắt một góc ảnh ngẫu nhiên và làm mờ tịt đi để tạo độ suy đoán"""
        if not HAS_PILLOW: return None
        try:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                w, h = img.size
                # Crop góc phần tư giữa, thiên về dưới một chút
                left, top, right, bottom = w * 0.2, h * 0.3, w * 0.8, h * 0.8
                cropped = img.crop((left, top, right, bottom))
                
                # Blur mờ tịt (radius 25)
                blurred = cropped.filter(ImageFilter.GaussianBlur(radius=25))
                out = io.BytesIO()
                blurred.save(out, format="JPEG")
                out.seek(0)
                return out
        except Exception as e:
            log(f"Lỗi tạo ảnh preview: {e}", "warn")
            return None

    def _remaining_cooldown(self, user_id: int) -> float:
        last = self._last_roll_monotonic.get(user_id)
        if not last: return 0.0
        return max(0.0, ROLL_COOLDOWN_SECONDS - (time.monotonic() - last))

    def _roll(self, user_id: int) -> Optional[Tuple[int, dict, str]]:
        present_tiers = [t for t in self._rarity_map if self._rarity_map[t]]
        if not present_tiers: return None

        state = get_user_state(self._states, user_id)
        pity = state["pity_counter"]

        mythic_rate = 0.005 + (pity * 0.002) 

        is_gold_hit = False
        if pity >= PITY_MAX - 1:
            is_gold_hit = True
        elif random.random() < mythic_rate:
            is_gold_hit = True

        tier, status_note = 0, ""

        if is_gold_hit:
            tier = 3
            state["pity_counter"] = 0
            status_note = "✨ Nổ Vàng!"
        else:
            state["pity_counter"] += 1
            tier = random.choices([0, 1, 2], weights=[0.80, 0.16, 0.035], k=1)[0]

        if tier not in present_tiers:
            tier = min(present_tiers, key=lambda t: abs(t - tier))

        pool = self._rarity_map[tier]
        last_index = state["last_index"]
        candidates = [i for i in pool if i != last_index] or pool
        index = random.choice(candidates)
        actress = self._actresses_by_index.get(index)
        if not actress: return None

        # Cập nhật state
        state["last_index"] = index
        state["total_rolls"] += 1
        state["daily_rolls"] += 1
        state["tier_counts"][str(tier)] = state["tier_counts"].get(str(tier), 0) + 1
        state["actress_counts"][str(index)] = state["actress_counts"].get(str(index), 0) + 1
        
        # Cập nhật lịch sử (chèn lên đầu, giữ max 100)
        history = state["history"]
        history.insert(0, {
            "tier": tier,
            "name": actress["name"],
            "time": int(time.time())
        })
        if len(history) > 100:
            history.pop()

        save_all_states(self._states)
        return tier, actress, status_note

    async def handle_roll(self, interaction: discord.Interaction, is_reroll: bool):
        user_id = interaction.user.id
        
        # 1. Kiểm tra Cooldown chống spam nút
        remaining = self._remaining_cooldown(user_id)
        if remaining > 0:
            await interaction.response.send_message(
                f"Chờ thêm **{max(1, round(remaining))}s** rồi quay tiếp nha {HEART}", ephemeral=True
            )
            return

        # 2. Kiểm tra giới hạn 30 lượt quay/ngày
        state = get_user_state(self._states, user_id)
        current_date = get_gacha_date()
        
        if state["last_reset_date"] != current_date:
            state["daily_rolls"] = 0
            state["last_reset_date"] = current_date
            save_all_states(self._states)

        if state["daily_rolls"] >= MAX_DAILY_ROLLS:
            await interaction.response.send_message(
                f"Hôm nay cậu đã xoay đủ 30 nháy rồi, giữ gìn sức khoẻ nhé! Hẹn 3h sáng mai quay lại nha :3", ephemeral=True
            )
            return

        self._last_roll_monotonic[user_id] = time.monotonic()

        # Thực hiện random data
        result = self._roll(user_id)
        if result is None:
            await interaction.response.send_message(f"Chưa nạp được dữ liệu, thử lại sau nha {HEART}", ephemeral=True)
            return

        tier, actress, status_note = result
        image_name = Path(actress["image_file"]).name
        image_path = IMAGES_DIR / image_name

        # ==========================================
        # PHA 1: ANIMATION XÁO THẺ (CÓ MỜ ẢNH)
        # ==========================================
        preview_embed = discord.Embed(
            title="[???] Đang giải mã thẻ...",
            description="Nhân phẩm đang được nạp!",
            color=0x2b2d31
        )
        
        preview_attachments = []
        if image_path.exists() and HAS_PILLOW:
            # Tạo ảnh mờ bằng thead phụ để không block bot
            preview_bytes = await asyncio.to_thread(self._create_preview_image, image_path)
            if preview_bytes:
                preview_attachments.append(discord.File(preview_bytes, filename="preview.jpg"))
                preview_embed.set_image(url="attachment://preview.jpg")

        if is_reroll:
            # Dùng attachments=... để REPLACES sạch mọi ảnh cũ trong msg hiện tại
            await interaction.response.edit_message(embed=preview_embed, attachments=preview_attachments, view=None)
        else:
            await interaction.response.send_message(embed=preview_embed, files=preview_attachments)

        # Chờ suspense giống mở hòm (2.5s)
        await asyncio.sleep(2.5)

        # ==========================================
        # PHA 2: LỘ THẺ (SHOW FULL)
        # ==========================================
        info = TIER_INFO.get(tier, TIER_INFO[0])
        final_embed = discord.Embed(
            title=f"[{info['label']}] {actress['name']}",
            description=(
                f"Debut: **{actress['debut']}**  •  Số video: **{actress['videos']}**\n"
                f"[Xem thêm]({actress['href']})"
            ),
            color=info["color"],
        )
        
        guild_name = interaction.guild.name if interaction.guild else "Câu lạc bộ Nhạc Nhẹ"
        footer_text = f"Yui Hirasawa • {guild_name} 🎲 | (Vé {state['daily_rolls']}/{MAX_DAILY_ROLLS})"
        if status_note: footer_text += f" - {status_note}"
        final_embed.set_footer(text=footer_text)

        view = RerollView(self, author_id=user_id)
        final_attachments = []
        if image_path.exists():
            final_file = discord.File(image_path, filename=image_name)
            final_embed.set_image(url=f"attachment://{image_name}")
            final_attachments.append(final_file)

        # Cập nhật thẳng vào tin nhắn đang chạy preview
        msg = await interaction.edit_original_response(embed=final_embed, attachments=final_attachments, view=view)
        view.message = msg


    @app_commands.command(name="toi-nay-xem-gi", description="Gacha random 1 diễn viên nên xem tối nay :3")
    async def toi_nay_xem_gi(self, interaction: discord.Interaction):
        await self.handle_roll(interaction, is_reroll=False)

    @app_commands.command(name="toi-nay-lichsu", description="Xem lịch sử 100 lần gacha gần nhất của cậu")
    async def toi_nay_lichsu(self, interaction: discord.Interaction):
        state = get_user_state(self._states, interaction.user.id)
        history = state.get("history", [])

        if not history:
            await interaction.response.send_message(f"Cậu chưa quay lần nào cả, vào gacha đi rồi xem {HEART}", ephemeral=True)
            return

        view = HistoryView(history, interaction.user.id)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="toi-nay-thongke", description="Xem nhân phẩm gacha của cậu")
    async def toi_nay_thongke(self, interaction: discord.Interaction):
        state = get_user_state(self._states, interaction.user.id)
        total = state["total_rolls"]
        tier_counts = state["tier_counts"]
        actress_counts = state["actress_counts"]

        lines = [f"Tổng số lần quay: **{total}**", ""]
        for tier in (0, 1, 2, 3):
            info = TIER_INFO[tier]
            count = tier_counts.get(str(tier), 0)
            pct = (count / total * 100) if total else 0
            lines.append(f"{info['label']}: **{count}** lần ({pct:.1f}%)")

        if actress_counts:
            top_index, top_count = max(actress_counts.items(), key=lambda kv: kv[1])
            top_actress = self._actresses_by_index.get(int(top_index))
            top_name = top_actress["name"] if top_actress else f"#{top_index}"
            lines.append(f"\nRa nhiều nhất: **{top_name}** ({top_count} lần)")

        pity_current = state["pity_counter"]
        lines.append(f"\n*Đã quay **{pity_current}/{PITY_MAX}** roll kể từ lần nổ Mythic cuối.*")

        embed = discord.Embed(
            title=f"Thống kê Nhân Phẩm của {interaction.user.display_name} 📊",
            description="\n".join(lines),
            color=0xFFB6C1,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="toi-nay-top", description="Bảng xếp hạng nhân phẩm toàn server :3")
    async def toi_nay_top(self, interaction: discord.Interaction):
        leaderboard = []
        for uid_str, state in self._states.items():
            mythic_count = state.get("tier_counts", {}).get("3", 0)
            total_rolls = state.get("total_rolls", 0)
            if total_rolls > 0:
                leaderboard.append((int(uid_str), mythic_count, total_rolls))

        if not leaderboard:
            await interaction.response.send_message(f"Server mình chưa ai chơi gacha cả! {HEART}", ephemeral=True)
            return

        leaderboard.sort(key=lambda x: (x[1], -x[2]), reverse=True)

        lines = []
        for rank, (uid, m_count, rolls) in enumerate(leaderboard[:10], 1):
            user_mention = f"<@{uid}>"
            if m_count > 0:
                rate = (m_count / rolls) * 100
                lines.append(f"**#{rank}** {user_mention}: **{m_count}** Mythic / {rolls} roll ({rate:.1f}%)")
            else:
                lines.append(f"**#{rank}** {user_mention}: Đáy xã hội (0 Mythic / {rolls} roll)")

        embed = discord.Embed(
            title=f"Bảng Xếp Hạng Nhân Phẩm 🏆",
            description="\n".join(lines),
            color=0xE4AE39
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="toi-nay-kho-do", description="Khoe bộ sưu tập Mythic và Epic của cậu :3")
    async def toi_nay_kho_do(self, interaction: discord.Interaction):
        state = get_user_state(self._states, interaction.user.id)
        actress_counts = state.get("actress_counts", {})

        mythics = []
        epics = []

        for idx_str, count in actress_counts.items():
            idx = int(idx_str)
            tier = self._index_to_tier.get(idx, 0)
            if tier >= 2:
                actress = self._actresses_by_index.get(idx)
                if actress:
                    if tier == 3:
                        mythics.append((actress["name"], count))
                    elif tier == 2:
                        epics.append((actress["name"], count))

        mythics.sort(key=lambda x: x[1], reverse=True)
        epics.sort(key=lambda x: x[1], reverse=True)

        def format_list(item_list):
            if not item_list: return "*Chưa có gì cả...*"
            lines = [f"• **{name}** (x{count})" for name, count in item_list[:15]]
            if len(item_list) > 15:
                lines.append(f"... và {len(item_list) - 15} waifu nữa.")
            return "\n".join(lines)

        embed = discord.Embed(
            title=f"Kho Đồ của {interaction.user.display_name}",
            color=0xE4AE39
        )

        embed.add_field(name="💛 Mythic", value=format_list(mythics), inline=False)
        embed.add_field(name="❤️ Epic", value=format_list(epics), inline=False)
        
        total = state.get("total_rolls", 0)
        embed.set_footer(text=f"Đã cống hiến tổng cộng {total} lượt quay 🎲")

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(GachaCog(bot))
