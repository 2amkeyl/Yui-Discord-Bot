from typing import Optional
import random

import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

import time

from core.common import ERROR_COLOR, make_embed
from stores.economy_store import (
    economy, COIN_EMOJI, DAILY_REWARD_MIN, DAILY_REWARD_MAX, GIVE_DAILY_LIMIT,
    WORK_REWARD_MIN, WORK_REWARD_MAX, WORK_COOLDOWN_SECONDS, get_vn_today, parse_bet_amount,
)


ECONOMY_ADMIN_ID = 1147592525696204822  # chỉ ID này được dùng /addcoin

WORK_JOBS = [
    "Cậu phụ Yui pha trà chiều cho khách, kiếm được **{reward:,}** {COIN_EMOJI}",
    "Cậu ngồi đàn guitar cho quán nghe, khách boa cho **{reward:,}** {COIN_EMOJI}",
    "Cậu dạy một bạn nhỏ chơi trống, được trả công **{reward:,}** {COIN_EMOJI}",
    "Cậu phụ bếp làm bánh ngọt cả buổi, nhận **{reward:,}** {COIN_EMOJI}",
    "Cậu dọn dẹp phòng nhạc sau giờ tập, được thưởng **{reward:,}** {COIN_EMOJI}",
    "Cậu đứng quầy order cho quán cà phê, kiếm được **{reward:,}** {COIN_EMOJI}",
    "Cậu chép nhạc phổ giúp ban nhạc trường, nhận **{reward:,}** {COIN_EMOJI}",
    "Cậu trông quán giùm chủ tiệm một buổi chiều, được **{reward:,}** {COIN_EMOJI}",
    "Cậu phụ giao bánh quanh khu phố, kiếm được **{reward:,}** {COIN_EMOJI}",
    "Cậu hát vài bài ở quán nhỏ, khách vỗ tay và boa **{reward:,}** {COIN_EMOJI}",
    "Cậu phụ Yui bưng trà ra tận bàn khách, được tip **{reward:,}** {COIN_EMOJI}",
    "Cậu ngồi tính sổ sách giúp quán, chủ trả công **{reward:,}** {COIN_EMOJI}",
    "Cậu rửa mấy cái ly cho quán đông khách, kiếm được **{reward:,}** {COIN_EMOJI}",
    "Cậu phụ dán poster quảng cáo buổi diễn, nhận **{reward:,}** {COIN_EMOJI}",
    "Cậu ngồi bán vé cho buổi hòa nhạc nhỏ, được **{reward:,}** {COIN_EMOJI}",
    "Cậu tranh thủ dạy kèm bài tập cho hàng xóm, nhận **{reward:,}** {COIN_EMOJI}",
    "Cậu phụ tưới cây cho cả dãy ban công, được trả **{reward:,}** {COIN_EMOJI}",
    "Cậu ngồi trông thú cưng giùm cô chủ tiệm, kiếm được **{reward:,}** {COIN_EMOJI}",
]

class EconomyCog(commands.Cog, name="Kinh Tế"):
    """Ví Yui Coin, điểm danh hàng ngày, bảng xếp hạng, chuyển tiền"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Nhận quà điểm danh mỗi ngày :3")
    async def daily(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        await economy.ensure_user(uid)
        today = get_vn_today()

        async with economy.lock:
            if economy.data[uid].get("last_daily") == today:
                already_claimed = True
                reward = 0
            else:
                already_claimed = False
                reward = random.randint(DAILY_REWARD_MIN, DAILY_REWARD_MAX)
                economy.data[uid]["coins"] += reward
                economy.data[uid]["last_daily"] = today

        if already_claimed:
            return await interaction.response.send_message(embed=make_embed(f"Hôm nay cậu nhận quà rồi! Mai nha", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        await economy.save()
        await interaction.response.send_message(embed=make_embed(
            f"Tada! Cậu nhận được **{reward:,}** {COIN_EMOJI}",
            title="Quà Hàng Ngày", guild=interaction.guild,
        ))

    @app_commands.command(name="work", description=f"Đi làm việc vặt kiếm {WORK_REWARD_MIN:,}-{WORK_REWARD_MAX:,} Yui Coin, mỗi {WORK_COOLDOWN_SECONDS // 60} phút làm được 1 lần")
    async def work(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        await economy.ensure_user(uid)

        now = time.time()
        last_work = economy.data[uid].get("last_work", 0)
        elapsed = now - last_work

        if elapsed < WORK_COOLDOWN_SECONDS:
            remain = round(WORK_COOLDOWN_SECONDS - elapsed)
            ready_ts = round(now + remain)
            return await interaction.response.send_message(
                f"Cậu vừa làm việc xong, nghỉ tay chút đã nào! Quay lại lúc <t:{ready_ts}:R> nha :3",
                ephemeral=True,
            )

        reward = random.randint(WORK_REWARD_MIN, WORK_REWARD_MAX)
        async with economy.lock:
            economy.data[uid]["coins"] += reward
            economy.data[uid]["last_work"] = now
        await economy.save()

        line = random.choice(WORK_JOBS).format(reward=reward, COIN_EMOJI=COIN_EMOJI)
        await interaction.response.send_message(line)

    @app_commands.command(name="cash", description="Xem số Yui Coin trong ví của bạn")
    async def cash(self, interaction: discord.Interaction):
        coins = economy.data.get(str(interaction.user.id), {}).get("coins", 0)
        await interaction.response.send_message(f"**{interaction.user.display_name}**, cậu đang có **{coins:,}** {COIN_EMOJI}")

    @app_commands.command(name="top", description="Xem bảng xếp hạng Yui Coin hoặc Nối từ")
    @app_commands.choices(loai=[Choice(name="Đại Gia (Coin)", value="coins"), Choice(name="Nối Từ (Wins)", value="wins")])
    async def top(self, interaction: discord.Interaction, loai: Choice[str]):
        k = loai.value
        sorted_u = sorted([i for i in economy.data.items() if i[1].get(k, 0) > 0], key=lambda x: x[1].get(k, 0), reverse=True)[:10]
        if not sorted_u:
            return await interaction.response.send_message(embed=make_embed("Chưa có ai lọt top cả", color=ERROR_COLOR, guild=interaction.guild))
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        unit = "trận thắng" if k == "wins" else COIN_EMOJI
        lines = [f"{medals.get(i, f'**#{i}**')} <@{u}> — **{d.get(k, 0):,}** {unit}" for i, (u, d) in enumerate(sorted_u, 1)]
        title = "👑 Bảng Vàng Đại Gia" if k == "coins" else "🏆 Bảng Vàng Cao Thủ Nối Từ"
        await interaction.response.send_message(embed=make_embed("\n".join(lines), title=title, guild=interaction.guild))

    @app_commands.command(name="addcoin", description="(Admin) Cộng hoặc trừ Yui Coin cho một ID")
    @app_commands.describe(user_id="ID người dùng Discord", amount="Số coin cần cộng (nhập số âm để trừ)")
    async def addcoin(self, interaction: discord.Interaction, user_id: str, amount: app_commands.Range[int, -1_000_000_000_000, 1_000_000_000_000]):
        if interaction.user.id != ECONOMY_ADMIN_ID:
            return await interaction.response.send_message(embed=make_embed("Lệnh này không dành cho cậu nha!", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        uid = user_id.strip()
        if not (uid.isdigit() and 15 <= len(uid) <= 20):
            return await interaction.response.send_message(embed=make_embed("ID không hợp lệ, phải là dãy số ID Discord (17-19 chữ số) nha!", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        await economy.ensure_user(uid)
        # Sửa trực tiếp dữ liệu đang chạy trong bot (có khoá) rồi lưu -> không bị bot ghi đè như khi sửa tay file JSON
        async with economy.lock:
            before = economy.data[uid]["coins"]
            economy.data[uid]["coins"] = max(0, before + amount)
            after = economy.data[uid]["coins"]
        await economy.save()

        sign = "+" if amount >= 0 else ""
        await interaction.response.send_message(embed=make_embed(
            f"<@{uid}> (`{uid}`)\n**{before:,}** → **{after:,}** {COIN_EMOJI}  ({sign}{amount:,})",
            title="Đã cập nhật ví", guild=interaction.guild,
        ), ephemeral=True)

    @app_commands.command(name="give", description="Chuyển Yui Coin cho người khác (giới hạn 5,000,000/ngày)")
    @app_commands.describe(member="Người nhận tiền", amount="Số tiền muốn chuyển (có thể gõ all để chuyển hết ví)")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: str):
        giver, receiver = interaction.user, member
        if receiver.id == giver.id:
            return await interaction.response.send_message(embed=make_embed(f"Cậu hổng thể tự chuyển tiền cho chính mình đâu!", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if receiver.bot:
            return await interaction.response.send_message(embed=make_embed("Hổng thể chuyển tiền cho bot được đâu nha :3", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        uid, rid = str(giver.id), str(receiver.id)
        await economy.ensure_user(uid)
        await economy.ensure_user(rid)

        today = get_vn_today()
        error_msg = None
        send_amount = None

        async with economy.lock:
            balance = economy.data[uid]["coins"]
            send_amount = parse_bet_amount(amount, balance)

            if send_amount is None or send_amount <= 0:
                error_msg = "Số tiền không hợp lệ, thử lại nha :3"
            elif send_amount > balance:
                error_msg = f"Cậu hổng đủ tiền đâu! Ví hiện có **{balance:,}** {COIN_EMOJI}"
            else:
                if economy.data[uid].get("give_date") != today:
                    economy.data[uid]["give_date"], economy.data[uid]["give_today"] = today, 0
                given_today = economy.data[uid].get("give_today", 0)

                if given_today + send_amount > GIVE_DAILY_LIMIT:
                    remain = max(GIVE_DAILY_LIMIT - given_today, 0)
                    error_msg = f"Cậu chỉ được chuyển tối đa **{GIVE_DAILY_LIMIT:,}** {COIN_EMOJI} mỗi ngày thôi!\nHôm nay cậu còn chuyển được: **{remain:,}** {COIN_EMOJI}"
                else:
                    economy.data[uid]["coins"] = max(0, economy.data[uid]["coins"] - send_amount)
                    economy.data[uid]["give_today"] = given_today + send_amount
                    economy.data[rid]["coins"] += send_amount

        if error_msg:
            return await interaction.response.send_message(embed=make_embed(error_msg, color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        await economy.save()
        await interaction.response.send_message(embed=make_embed(
            f"{giver.mention} đã chuyển **{send_amount:,}** {COIN_EMOJI} cho {receiver.mention}!",
            title=f"Chuyển Khoản Thành Công", guild=interaction.guild,
        ))
