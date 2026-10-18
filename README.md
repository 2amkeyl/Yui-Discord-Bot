<div align="center">

<img src="https://giffiles.alphacoders.com/349/34964.gif" alt="Yui" width="35%" />

# Yui Discord Bot

[Tiếng Việt](#-tiếng-việt) • [English](#-english)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-v2.6+-5865F2.svg?style=flat-square&logo=discord&logoColor=white)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)

*A self-hosted Discord bot inspired by Yui Hirasawa from K-ON!*

</div>

---

## 🇻🇳 Tiếng Việt

Yui là Discord bot tự host lấy cảm hứng từ **Yui Hirasawa (K-ON!)**, cung cấp tính năng voice, trò chơi, Valorant và tiện ích giải trí.

### ✨ Tóm tắt chức năng

| Chức năng | Mô tả |
| :--- | :--- |
| 🗣️ **TTS** | Đọc văn bản trong voice bằng 5 ngôn ngữ; có cài đặt ngôn ngữ riêng. |
| 🔤 **Nối từ** | Chơi nối từ tiếng Việt, kiểm tra từ điển và lưu bảng thắng. |
| 💰 **Yui Coin** | Nhận thưởng hằng ngày, làm việc kiếm coin, xem số dư, xếp hạng và chuyển coin. |
| 🎲 **Minigame** | Dò Mìn và Tung đồng xu với hệ thống cược bằng Yui Coin. |
| 🎯 **Valorant** | Xem cửa hàng, Night Market và tạo ảnh bộ sưu tập skin. |
| 🛠️ **Tiện ích** | Xem avatar/banner, thông báo và các tiện ích Discord khác. |
| 🎉 **Giải trí** | Lệnh tương tác như ôm, vỗ đầu, hôn, nhảy; gợi ý món ăn/phim. |

### 🎮 Danh sách lệnh

Hầu hết lệnh hỗ trợ prefix `yui` viết liền với tên lệnh (ví dụ `yuicash`). Các lệnh được đánh dấu **Slash** chỉ dùng bằng `/`. Dùng `/help` để xem hướng dẫn đầy đủ.

| Nhóm | Lệnh | Chức năng |
| :--- | :--- | :--- |
| **TTS** | `/say`, `/language`, `/leave` | Đọc văn bản trong voice, đổi ngôn ngữ, rời voice. |
| **Nối từ** | `/noitu`, `/noitu_stop` | Bắt đầu hoặc dừng ván nối từ. |
| **Yui Coin** | `/daily`, `/work`, `/cash`, `/top`, `/give` | Nhận coin, làm việc, xem ví/bảng xếp hạng, chuyển coin. |
| **Minigame** | `/mine`, `/coinflip` | Chơi Dò Mìn hoặc Tung đồng xu. |
| **Hồ sơ** | `/avatar`, `/banner` | Xem avatar và banner. |
| **Valorant** | `/shop`, `/nightmarket`, `/skins` *(Slash)* | Xem cửa hàng, Night Market và bộ sưu tập skin. |
| **Tiện ích** | `/quest`, `/hypesquad` *(Slash)*, `/thongbao`, `/help` | Tiện ích Discord, thông báo và trợ giúp. |
| **Giải trí** | `/hug`, `/pat`, `/kiss`, `/dance`, `/hom-nay-an-gi`, `/toi-nay-xem-gi` | Tương tác vui, gợi ý món ăn và phim. |

> **Lưu ý bảo mật:** `/quest` và `/hypesquad` yêu cầu Discord user token và có thể khiến tài khoản gặp rủi ro. Chỉ sử dụng nếu bạn hiểu rõ hậu quả. Không chia sẻ token hoặc thông tin đăng nhập.

### 📦 Yêu cầu
- Python **3.11+**, `discord.py` **2.6+**
- FFmpeg cho TTS
- Discord Bot Token; bật **Message Content Intent** và **Server Members Intent**
- Giữ thư mục `assets/fonts/` để tạo ảnh `/skins`

### 🚀 Cài đặt

```bash
git clone https://github.com/2amkeyl/Yui-Discord-Bot.git
cd Yui-Discord-Bot
```

Tạo file `.env` ở thư mục gốc:

```env
BOT_TOKEN=your_discord_bot_token_here
# Tuỳ chọn: khoá mã hoá phiên Valorant
VALORANT_SECRET_KEY=your_secret_key
```

Chạy bot:

```bash
pip install -r requirements.txt
python main.py
```

Nếu không đặt `VALORANT_SECRET_KEY`, bot tạo `valorant.key` khi cần. **Hãy sao lưu khoá này**; mất hoặc đổi khoá sẽ khiến phiên Valorant đã lưu không thể giải mã. `proxies.txt` là tuỳ chọn cho `/quest`.

### 🛠️ Xử lý sự cố
- **TTS không phát tiếng:** kiểm tra FFmpeg, PyNaCl/davey, quyền `Connect`/`Speak` và mạng.
- **Không thấy slash command:** chờ đồng bộ và kiểm tra scope `applications.commands`.
- **Prefix không phản hồi:** bật **Message Content Intent**.
- **Lỗi Valorant:** giữ nguyên `valorant.key`/`VALORANT_SECRET_KEY` và dùng link Riot còn hạn.
- **Ảnh skin/emoji lỗi:** kiểm tra `assets/fonts/`, kết nối `valorant-api.com` và quyền **Use External Emojis**.

### 📄 Giấy phép
Dự án được phát hành theo **GNU General Public License v3.0 (GPL-3.0)**. Xem [LICENSE](LICENSE).

---

## 🇬🇧 English

Yui is a self-hosted Discord bot inspired by **Yui Hirasawa from K-ON!**, with voice, games, Valorant features, and entertainment utilities.

### ✨ Feature Summary

| Feature | Description |
| :--- | :--- |
| 🗣️ **TTS** | Reads text in voice channels in five languages, with per-user language settings. |
| 🔤 **Word chain** | Vietnamese word-chain game with dictionary checks and a win leaderboard. |
| 💰 **Yui Coin** | Daily rewards, odd jobs, wallet balances, leaderboards, and transfers. |
| 🎲 **Minigames** | Minesweeper and Coinflip using Yui Coin bets. |
| 🎯 **Valorant** | View the daily store and Night Market, and render your skin collection. |
| 🛠️ **Utilities** | Avatar/banner lookup, announcements, and other Discord utilities. |
| 🎉 **Fun** | Interaction commands and food/movie suggestions. |

### 🎮 Command Reference

Most commands also support the `yui` prefix directly before the command (e.g. `yuicash`). Commands marked **Slash** are slash-only. Use `/help` for full usage details.

| Category | Commands | Description |
| :--- | :--- | :--- |
| **TTS** | `/say`, `/language`, `/leave` | Read text in voice, set language, or leave voice. |
| **Word chain** | `/noitu`, `/noitu_stop` | Start or stop a word-chain round. |
| **Yui Coin** | `/daily`, `/work`, `/cash`, `/top`, `/give` | Earn coins, view wallet/leaderboards, and transfer coins. |
| **Minigames** | `/mine`, `/coinflip` | Play Minesweeper or Coinflip. |
| **Profile** | `/avatar`, `/banner` | View avatars and banners. |
| **Valorant** | `/shop`, `/nightmarket`, `/skins` *(Slash)* | View the store, Night Market, and skin collection. |
| **Utilities** | `/quest`, `/hypesquad` *(Slash)*, `/thongbao`, `/help` | Discord utilities, announcements, and help. |
| **Fun** | `/hug`, `/pat`, `/kiss`, `/dance`, `/hom-nay-an-gi`, `/toi-nay-xem-gi` | Interaction commands and food/movie suggestions. |

> **Security warning:** `/quest` and `/hypesquad` require a Discord user token and may put your account at risk. Use them only if you understand the consequences. Never share tokens or login credentials.

### 📦 Requirements
- Python **3.11+**, `discord.py` **2.6+`
- FFmpeg for TTS
- A Discord Bot Token; enable **Message Content Intent** and **Server Members Intent**
- Keep `assets/fonts/` for `/skins` image rendering

### 🚀 Installation

```bash
git clone https://github.com/2amkeyl/Yui-Discord-Bot.git
cd Yui-Discord-Bot
```

Create a `.env` file in the repository root:

```env
BOT_TOKEN=your_discord_bot_token_here
# Optional: encryption key for Valorant sessions
VALORANT_SECRET_KEY=your_secret_key
```

Install dependencies and run:

```bash
pip install -r requirements.txt
python main.py
```

If `VALORANT_SECRET_KEY` is unset, Yui creates `valorant.key` when needed. **Back up this key**; losing or changing it prevents saved Valorant sessions from being decrypted. `proxies.txt` is optional for `/quest`.

### 🛠️ Troubleshooting
- **No TTS audio:** check FFmpeg, PyNaCl/davey, `Connect`/`Speak` permissions, and network access.
- **Slash commands missing:** wait for sync and check the `applications.commands` scope.
- **Prefix commands do not respond:** enable **Message Content Intent**.
- **Valorant errors:** keep `valorant.key`/`VALORANT_SECRET_KEY` unchanged and use a valid Riot login link.
- **Skin images/emojis fail:** check `assets/fonts/`, access to `valorant-api.com`, and **Use External Emojis** permission.

### 📄 License
Released under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE).

---

<div align="center">

Made by **Keyl** • [Discord Support Server](https://discord.gg/ErGMVF77Pc)

</div>
