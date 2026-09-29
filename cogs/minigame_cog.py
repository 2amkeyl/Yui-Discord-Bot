import asyncio
import os
import random
import re
import unicodedata
from typing import Optional

import discord
import requests
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

from core.common import EMBED_COLOR, ERROR_COLOR, make_embed, log, rate_limiter, ROOT_DIR
from stores.economy_store import economy, COIN_EMOJI, NOITU_WIN_REWARD, parse_bet_amount

GAME_COOLDOWN_SECONDS = 10.0

# ==============================================================================
# ── HẠ TẦNG NHỎ: REACT/REPLY CÓ RATE LIMIT (dùng riêng cho nối từ) ────────────
# ==============================================================================

async def _safe_react(message: discord.Message, emoji: str):
    await rate_limiter.acquire()
    try: await message.add_reaction(emoji)
    except discord.HTTPException as e: log(f"Lỗi khi react tin nhắn: {e}", "warn")

async def _safe_reply(message: discord.Message, content: str):
    await rate_limiter.acquire()
    try: await message.reply(content)
    except discord.HTTPException as e: log(f"Lỗi khi reply tin nhắn: {e}", "warn")

EMOJI_CORRECT = "<a:klquyt:1544282397040844850>"
EMOJI_INCORRECT = "<a:klwqquyt2:1544282445766066237>"

# ==============================================================================
# ── GAME NỐI TỪ ───────────────────────────────────────────────────────────────
# ==============================================================================

def norm(s: str) -> str:
    return unicodedata.normalize('NFC', s).strip().lower()

def _build_prefix_map(words_set: set) -> dict:
    pm = {}
    for w in words_set:
        w1, w2 = w.split(" ", 1)
        pm.setdefault(w1, set()).add(w2)
    return pm

def split_two_words(content: str):
    parts = re.sub(r'[^\w\s]', '', content).strip().split()
    if len(parts) != 2 or not (parts[0].isalpha() and parts[1].isalpha()):
        return None
    return norm(parts[0]), norm(parts[1])

# ==============================================================================
# ── DÒ MÌN (MINES) ────────────────────────────────────────────────────────────
# ==============================================================================

MINES_TOTAL_CELLS = 9
MINES_MIN_MINES, MINES_MAX_MINES = 1, 8
MINES_MAX_BET = 250_000
MINES_HOUSE_EDGE = 0.94

active_mines_players = set()

def calc_mines_multiplier(total: int, mines: int, picks: int) -> float:
    safe = total - mines
    mult = MINES_HOUSE_EDGE
    for i in range(picks):
        mult *= (total - i) / (safe - i)
    return mult

MINE_HIDDEN_LABEL = "?"

class MineCellButton(discord.ui.Button):
    def __init__(self, game: "MinesView", index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label=MINE_HIDDEN_LABEL)
        self.game = game
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.game.handle_pick(interaction, self.index)

class MineCashOutButton(discord.ui.Button):
    def __init__(self, game: "MinesView"):
        super().__init__(style=discord.ButtonStyle.success, label="Rút Tiền", emoji=COIN_EMOJI)
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        await self.game.handle_cashout(interaction)

class MinesView(discord.ui.LayoutView):
    """Toàn bộ game nằm trong 1 container (Components V2): tiêu đề, nội dung, lưới nút, nút rút tiền."""

    def __init__(self, player: discord.abc.User, bet: int, mines: int, guild: Optional[discord.Guild]):
        super().__init__(timeout=120)
        self.player = player
        self.bet = bet
        self.mines_count = mines
        self.guild = guild
        self.total = MINES_TOTAL_CELLS
        self.safe_total = self.total - mines
        self.mine_positions = set(random.sample(range(self.total), mines))
        self.picked: set = set()
        self.picks = 0
        self.finished = False
        self.message = None

        # ── Dựng container ──
        self.body_text = discord.ui.TextDisplay("")
        self.container = discord.ui.Container(accent_colour=EMBED_COLOR)
        self.container.add_item(self.body_text)
        self.container.add_item(discord.ui.Separator())

        self.cell_buttons = []
        for r in range(3):
            row = discord.ui.ActionRow()
            for c in range(3):
                btn = MineCellButton(self, r * 3 + c)
                self.cell_buttons.append(btn)
                row.add_item(btn)
            self.container.add_item(row)

        self.container.add_item(discord.ui.Separator())
        self.cashout_btn = MineCashOutButton(self)
        self.cashout_btn.disabled = True  # chưa mở ô nào thì chưa rút được
        cash_row = discord.ui.ActionRow()
        cash_row.add_item(self.cashout_btn)
        self.container.add_item(cash_row)

        self.add_item(self.container)
        self.refresh(status="playing")

    # ── Tính toán ──
    def current_value(self) -> int:
        return 0 if self.picks == 0 else round(self.bet * calc_mines_multiplier(self.total, self.mines_count, self.picks))

    def current_mult(self) -> float:
        return 0.0 if self.picks == 0 else calc_mines_multiplier(self.total, self.mines_count, self.picks)

    def next_mult(self) -> float:
        return calc_mines_multiplier(self.total, self.mines_count, self.picks + 1)

    def fmt(self, num: int) -> str:
        """Format số có dấu chấm (vd: 10,000)"""
        return f"{num:,}"

    # ── Cập nhật nội dung + màu container ──
    def refresh(self, *, status: str = "playing", win_amount: int = 0):
        mention = self.player.mention
        cash_val = self.current_value()
        cash_mult = self.current_mult()
        bet_line = f"**Cược**: `{self.fmt(self.bet)}`  **Mìn**: `{self.mines_count}`"

        def cash_line(label: str) -> str:
            return f"**{label}**: `{self.fmt(cash_val)}` `({cash_mult:.2f}x)`"

        def next_line() -> str:
            if self.picks >= self.safe_total:
                return ""
            return f"**Tiếp theo**: `{self.fmt(round(self.bet * self.next_mult()))}` `({self.next_mult():.2f}x)`"

        if status == "playing":
            title = f"💣 {mention} **bắt đầu ván dò mìn.**" if self.picks == 0 else f"💣 {mention} **đang dò mìn.**"
            lines = [bet_line, cash_line("Rút tiền"), next_line()]
            color = EMBED_COLOR if self.picks == 0 else discord.Colour.green()
        elif status == "boom":
            title = f"💥 {mention} **đạp trúng mìn!**"
            lines = [bet_line, f"~~{cash_line('Rút tiền')}~~", f"~~{next_line()}~~"]
            color = ERROR_COLOR
        else:
            if status == "win":
                title = f"💎 {mention} **đã mở hết ô an toàn!**"
            elif status == "timeout":
                title = f"⏰ {mention} **hết giờ, tự động rút tiền!**"
            else:
                title = f"💎 {mention} **đã rút tiền!**"
            nl = next_line()
            lines = [bet_line, cash_line("Tiền thắng"), f"~~{nl}~~" if nl else ""]
            color = discord.Colour.green()

        self.body_text.content = "\n".join([f"### {title}"] + [l for l in lines if l])
        self.container.accent_colour = color

    # ── Lật toàn bộ bàn khi kết thúc (giống hình 2) ──
    def reveal_all(self, exploded_index: int = -1):
        for i, btn in enumerate(self.cell_buttons):
            btn.label = None
            if i in self.mine_positions:
                if i == exploded_index:
                    btn.style = discord.ButtonStyle.danger
                    btn.emoji = "💥"
                else:
                    btn.style = discord.ButtonStyle.secondary
                    btn.emoji = "💣"
            else:
                btn.emoji = "💎"
                btn.style = discord.ButtonStyle.success if i in self.picked else discord.ButtonStyle.secondary
            btn.disabled = True

        self.cashout_btn.disabled = True

    async def _pay(self, amount: int):
        if amount > 0:
            uid = str(self.player.id)
            await economy.ensure_user(uid)
            async with economy.lock:
                economy.data[uid]["coins"] += amount
            await economy.save()

    async def finish(self, interaction: discord.Interaction, status: str, win_amount: int = 0, exploded_index: int = -1):
        self.finished = True
        active_mines_players.discard(self.player.id)
        await self._pay(win_amount)

        self.reveal_all(exploded_index)
        self.refresh(status=status, win_amount=win_amount)
        self.stop()
        await interaction.response.edit_message(view=self)

    async def handle_pick(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message(embed=make_embed("Đây hổng phải ván của cậu đâu! :3", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if self.finished or index in self.picked:
            return await interaction.response.defer()

        if index in self.mine_positions:
            return await self.finish(interaction, "boom", 0, exploded_index=index)

        self.picks += 1
        self.picked.add(index)
        btn = self.cell_buttons[index]
        btn.label = None
        btn.style = discord.ButtonStyle.success
        btn.emoji = "💎"
        btn.disabled = True

        if self.picks >= self.safe_total:
            return await self.finish(interaction, "win", self.current_value())

        self.cashout_btn.disabled = False
        self.refresh(status="playing")
        await interaction.response.edit_message(view=self)

    async def handle_cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message(embed=make_embed("Đây hổng phải ván của cậu đâu! :3", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if self.finished:
            return await interaction.response.defer()
        await self.finish(interaction, "cashout", self.current_value())

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        active_mines_players.discard(self.player.id)
        win = self.current_value()
        await self._pay(win)

        self.reveal_all()
        self.refresh(status="timeout", win_amount=win)

        if self.message:
            try: await self.message.edit(view=self)
            except discord.HTTPException: pass

# ==============================================================================
# ── COINFLIP ───────────────────────────────────────────────────────────────────
# ==============================================================================

COINFLIP_MAX_BET = 250_000
COINFLIP_SPIN_EMOJI = "<a:giphy:1544584832129048606>"
COINFLIP_HEAD_EMOJI = "<:headkl:1544584406596063312>"
COINFLIP_TAIL_EMOJI = "<:tailkl:1544584549793534004>"
COINFLIP_SPIN_GIF_URL = "https://cdn.discordapp.com/emojis/1544584832129048606.gif?size=240&quality=lossless"
COINFLIP_HEAD_IMG_URL = "https://cdn.discordapp.com/emojis/1544584406596063312.png?size=240&quality=lossless"
COINFLIP_TAIL_IMG_URL = "https://cdn.discordapp.com/emojis/1544584549793534004.png?size=240&quality=lossless"


class MinigameCog(commands.Cog, name="Trò Chơi"):
    """Dò mìn, tung đồng xu cá cược, và nối từ tiếng Việt cùng Yui"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, dict] = {}
        self.game_locks: dict[int, asyncio.Lock] = {}
        self.words: set = set()
        self.words_list: list = []
        self.prefix_map: dict = {}

    async def cog_load(self):
        await asyncio.to_thread(self._load_dictionary_sync)

    def _get_game_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self.game_locks:
            self.game_locks[channel_id] = asyncio.Lock()
        return self.game_locks[channel_id]

    def _use_fallback_words(self):
        self.words = {norm("bánh ngọt"), norm("trà chiều"), norm("âm nhạc")}
        self.words_list = list(self.words)
        self.prefix_map = _build_prefix_map(self.words)

    def _load_dictionary_sync(self):
        dict_file = os.path.join(ROOT_DIR, "vietnamese_words.txt")
        if not os.path.exists(dict_file):
            headers = {"User-Agent": "Mozilla/5.0"}
            for url in [
                "https://raw.githubusercontent.com/duyet/vietnamese-wordlist/master/Viet74K.txt",
                "https://cdn.jsdelivr.net/gh/duyet/vietnamese-wordlist/Viet74K.txt",
            ]:
                try:
                    r = requests.get(url, headers=headers, timeout=20)
                    if r.status_code == 200 and len(r.text) > 50000:
                        with open(dict_file, "w", encoding="utf-8") as f: f.write(r.text)
                        break
                except Exception:
                    continue
        try:
            ws = set()
            with open(dict_file, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().lower().replace("_", " ")
                    parts = w.split()
                    if len(parts) == 2 and parts[0].isalpha() and parts[1].isalpha():
                        ws.add(norm(w))
            if len(ws) > 1000:
                self.words, self.words_list = ws, list(ws)
                self.prefix_map = _build_prefix_map(ws)
            else:
                self._use_fallback_words()
        except Exception:
            self._use_fallback_words()

    def _has_valid_next_word(self, end_word: str) -> bool:
        return bool(self.prefix_map.get(end_word))

    def _get_random_start_word(self) -> tuple:
        if not self.words_list:
            return ("âm", "nhạc")
        for _ in range(20):
            w1, w2 = random.choice(self.words_list).split()
            if self._has_valid_next_word(w2):
                return w1, w2
        return tuple(random.choice(self.words_list).split())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        channel_id = message.channel.id
        content = message.content.strip()

        if channel_id not in self.games or content.startswith('/'):
            return

        async with self._get_game_lock(channel_id):
            game = self.games.get(channel_id)
            if not game:
                return

            parts = split_two_words(content)
            if not parts:
                return
            w1, w2 = parts
            if game.get('current') and w1 != game['current'][1]:
                return

            phrase_key = f"{w1} {w2}"
            if game.get('last_author_id') == message.author.id:
                await _safe_react(message, EMOJI_INCORRECT)
                await _safe_reply(message, "Cậu vừa nối rồi, nhường người khác nha! :3")
                return

            if phrase_key in game['history'][-50:]:
                await _safe_react(message, EMOJI_INCORRECT)
                await _safe_reply(message, "Từ này vừa dùng rùi, chờ tý nha!")
                return

            if phrase_key not in self.words:
                await _safe_react(message, EMOJI_INCORRECT)
                await _safe_reply(message, "Từ này hổng có trong từ điển tiếng Việt của Yui! :3")
                return

            game['current'], game['last_author_id'] = (w1, w2), message.author.id
            game['history'].append(phrase_key)
            await _safe_react(message, EMOJI_CORRECT)

            if not self._has_valid_next_word(w2):
                new_w1, new_w2 = self._get_random_start_word()
                game['current'], game['history'], game['last_author_id'] = (new_w1, new_w2), [f"{new_w1} {new_w2}"], None

                reward = NOITU_WIN_REWARD
                uid = str(message.author.id)
                await economy.ensure_user(uid)
                async with economy.lock:
                    economy.data[uid]["wins"] += 1
                    economy.data[uid]["coins"] += reward
                await economy.save()

                await message.channel.send(f"Hết từ nối rồi! **{message.author.display_name}** thắng nha!\n**Thưởng:** {reward:,} {COIN_EMOJI}\nLượt mới: **{new_w1} {new_w2}**")

    @app_commands.command(name="noitu", description="Bắt đầu ván game nối từ cùng Yui nè :3")
    async def start_noitu(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        async with self._get_game_lock(channel_id):
            existing = self.games.get(channel_id)
            if existing:
                w1, w2 = existing['current']
                await interaction.response.send_message(
                    f"Đang có ván nối từ chưa xong nè! Tiếp chữ `{w2}` đi, hoặc `/noitu_stop` nếu muốn dừng lại nha :3",
                    ephemeral=True,
                )
                return
            w1, w2 = self._get_random_start_word()
            self.games[channel_id] = {'history': [f"{w1} {w2}"], 'current': (w1, w2), 'last_author_id': None}
        await interaction.response.send_message(f"Yui mở màn: **{w1} {w2}** :3\nTiếp chữ `{w2}` đi!")

    @app_commands.command(name="noitu_stop", description="Dừng chơi nối từ :3")
    async def stop_noitu(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        async with self._get_game_lock(channel_id):
            if channel_id in self.games:
                del self.games[channel_id]
                await interaction.response.send_message("Yui dẹp bàn nối từ rồi nha! :3")
            else:
                await interaction.response.send_message("Ơ có chơi đâu mà dừng!")

    @app_commands.command(name="mine", description="Chơi Dò Mìn - dò ô an toàn để nhân thưởng, cẩn thận trúng mìn nha!")
    @app_commands.describe(bet="Số tiền cược (tối đa 250,000 - gõ all để cược mức tối đa, bỏ trống = 1)", mines=f"Số lượng mìn ({MINES_MIN_MINES}-{MINES_MAX_MINES}, bỏ trống = 3)")
    @app_commands.checks.cooldown(1, GAME_COOLDOWN_SECONDS, key=lambda i: i.user.id)
    async def mine_game(self, interaction: discord.Interaction, bet: str = "1", mines: app_commands.Range[int, MINES_MIN_MINES, MINES_MAX_MINES] = 3):
        uid = str(interaction.user.id)
        await economy.ensure_user(uid)

        if interaction.user.id in active_mines_players:
            return await interaction.response.send_message(embed=make_embed("Cậu đang có một ván Dò Mìn khác chưa xong nè! :3", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        balance = economy.data[uid]["coins"]
        bet_amount = parse_bet_amount(bet, balance, max_cap=MINES_MAX_BET)

        if bet_amount is None or bet_amount <= 0:
            return await interaction.response.send_message(embed=make_embed("Số tiền cược không hợp lệ, thử lại nha! :3", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if bet_amount > balance:
            return await interaction.response.send_message(embed=make_embed(f"Cậu hổng đủ tiền cược đâu! Ví hiện có **{balance:,}** {COIN_EMOJI}", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if bet_amount > MINES_MAX_BET:
            return await interaction.response.send_message(embed=make_embed(f"Cậu chỉ được cược tối đa **{MINES_MAX_BET:,}** {COIN_EMOJI} thôi nha!", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        async with economy.lock:
            economy.data[uid]["coins"] = max(0, economy.data[uid]["coins"] - bet_amount)
        await economy.save()

        active_mines_players.add(interaction.user.id)
        view = MinesView(interaction.user, bet_amount, mines, interaction.guild)
        try:
            await interaction.response.send_message(view=view)
            view.message = await interaction.original_response()
        except Exception as e:
            active_mines_players.discard(interaction.user.id)
            view.finished = True
            view.stop()
            async with economy.lock:
                economy.data[uid]["coins"] = max(0, economy.data[uid]["coins"] + bet_amount)
            await economy.save()
            log(f"Lỗi khi mở ván mine: {e}", "warn")
            try:
                await interaction.followup.send(embed=make_embed(
                    "Có lỗi khi mở ván Dò Mìn, Yui đã hoàn tiền cho cậu rồi nha!", color=ERROR_COLOR, guild=interaction.guild
                ), ephemeral=True)
            except discord.HTTPException:
                pass

    @app_commands.command(name="coinflip", description="Tung đồng xu, đoán mặt Ngửa/Sấp để x2 tiền cược!")
    @app_commands.describe(bet="Số tiền cược (gõ all để cược hết ví, bỏ trống = 1)", mat="Đoán đồng xu sẽ rơi mặt nào (bỏ trống = Ngửa)")
    @app_commands.choices(mat=[Choice(name="Ngửa (Heads)", value="heads"), Choice(name="Sấp (Tails)", value="tails")])
    @app_commands.checks.cooldown(1, GAME_COOLDOWN_SECONDS, key=lambda i: i.user.id)
    async def coinflip(self, interaction: discord.Interaction, bet: str = "1", mat: Optional[Choice[str]] = None):
        pick = mat.value if mat else "heads"  # bỏ trống -> mặc định Ngửa
        uid = str(interaction.user.id)
        await economy.ensure_user(uid)

        balance = economy.data[uid]["coins"]
        bet_amount = parse_bet_amount(bet, balance, max_cap=COINFLIP_MAX_BET)
        if bet_amount is None or bet_amount <= 0:
            return await interaction.response.send_message(embed=make_embed("Số tiền cược không hợp lệ, thử lại nha! :3", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if bet_amount > balance:
            return await interaction.response.send_message(embed=make_embed(f"Cậu hổng đủ tiền cược đâu! Ví hiện có **{balance:,}** {COIN_EMOJI}", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)
        if bet_amount > COINFLIP_MAX_BET:
            return await interaction.response.send_message(embed=make_embed(f"Cậu chỉ được cược tối đa **{COINFLIP_MAX_BET:,}** {COIN_EMOJI} thôi nha!", color=ERROR_COLOR, guild=interaction.guild), ephemeral=True)

        async with economy.lock:
            economy.data[uid]["coins"] = max(0, economy.data[uid]["coins"] - bet_amount)
        await economy.save()

        pick_label = "Ngửa" if pick == "heads" else "Sấp"
        pick_emoji = COINFLIP_HEAD_EMOJI if pick == "heads" else COINFLIP_TAIL_EMOJI

        await interaction.response.send_message(view=self._coinflip_view(
            interaction.user, bet_amount, pick_label, pick_emoji, status="spinning",
        ))

        await asyncio.sleep(5)

        result = random.choice(["heads", "tails"])
        won = result == pick

        if won:
            async with economy.lock:
                economy.data[uid]["coins"] += bet_amount * 2
            await economy.save()

        await interaction.edit_original_response(view=self._coinflip_view(
            interaction.user, bet_amount, pick_label, pick_emoji,
            status="win" if won else "lose", result=result,
        ))

    @staticmethod
    def _coinflip_view(user, bet: int, pick_label: str, pick_emoji: str, *, status: str,
                       result: str = "") -> discord.ui.LayoutView:
        fmt = lambda n: f"{n:,}"
        bet_line = f"**Cược**: `{fmt(bet)}`  **Chọn**: {pick_emoji} **{pick_label}**"

        if status == "spinning":
            title = f"{COINFLIP_SPIN_EMOJI} {user.mention} **tung đồng xu...**"
            body = f"### {title}\n{bet_line}\n\n**Đồng xu đang xoay, chờ xíu nha!**"
            thumb = COINFLIP_SPIN_GIF_URL
            color = EMBED_COLOR
        else:
            res_label = "Ngửa" if result == "heads" else "Sấp"
            res_emoji = COINFLIP_HEAD_EMOJI if result == "heads" else COINFLIP_TAIL_EMOJI
            thumb = COINFLIP_HEAD_IMG_URL if result == "heads" else COINFLIP_TAIL_IMG_URL
            if status == "win":
                title = f"{res_emoji} {user.mention} **đoán trúng!**"
                money = f"**Thắng**: `+{fmt(bet)}` {COIN_EMOJI}"
                color = discord.Colour.green()
            else:
                title = f"{res_emoji} {user.mention} **đoán trật rồi!**"
                money = f"**Thua**: `-{fmt(bet)}` {COIN_EMOJI}"
                color = ERROR_COLOR
            body = f"### {title}\n{bet_line}\n**Kết quả**: {res_emoji} **{res_label}**\n\n{money}"

        container = discord.ui.Container(accent_colour=color)
        container.add_item(discord.ui.Section(
            discord.ui.TextDisplay(body), accessory=discord.ui.Thumbnail(thumb),
        ))
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(container)
        return view

async def setup(bot: commands.Bot):
    await bot.add_cog(MinigameCog(bot))
