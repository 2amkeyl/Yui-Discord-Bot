<div align="center">

<img src="https://giffiles.alphacoders.com/349/34964.gif" alt="Yui" width="40%" />

# 🎸 Yui Discord Bot

</div>

<!-- Language Switcher Bar -->
<p align="center">
  <a href="#-tiếng-việt"><b>Tiếng Việt</b></a> •
  <a href="#-english"><b>English</b></a>
</p>

<!-- Badges -->
<p align="center">
  <img src="https://img.shields.io/badge/Version-beta_v1.0b-orange.svg?style=flat-square" alt="Version" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/discord.py-v2.x-5865F2.svg?style=flat-square&logo=discord&logoColor=white" alt="discord.py" />
  <a href="https://discord.gg/ErGMVF77Pc"><img src="https://img.shields.io/badge/Support_Server-Join_Discord-5865F2.svg?style=flat-square&logo=discord&logoColor=white" alt="Discord Support Server" /></a>
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License" />
</p>

---

<p align="center">
  <b>Một Discord bot phong cách Yui Hirasawa (K-ON!)</b>
</p>

---

<a name="-tiếng-việt"></a>
## Tiếng Việt

### 📑 Mục Lục

1. [Tổng quan](#tong-quan)
2. [Tính năng nổi bật](#tinh-nang-noi-bat)
3. [Yêu cầu hệ thống](#yeu-cau-he-thong)
4. [Hướng dẫn cài đặt & Triển khai](#cai-dat-trien-khai)
5. [Danh sách lệnh (Commands)](#danh-sach-lenh)
6. [Xử lý sự cố (Troubleshooting)](#xu-ly-su-co)
7. [Công nghệ sử dụng](#cong-nghe-su-dung)
8. [Giấy phép & Bản quyền](#giay-phep-ban-quyen)

---

<a id="tong-quan"></a>
### 🌟 Tổng quan

**Yui** là một Discord bot self-hosted lấy cảm hứng từ nhân vật **Yui Hirasawa** trong anime *K-ON!*, phản hồi hoàn toàn bằng tiếng Việt với văn phong dễ thương, thân thiện.

> ⚠️ **Lưu ý về phương thức điều khiển:** Mọi lệnh đều là **Slash Commands (`/`)**. Ngoài ra, hầu hết lệnh còn gọi được bằng **prefix `yui`** viết liền với tên lệnh (vd `yuicash`, `yuihug @ai_đó`) nhờ `PrefixBridgeCog`. Riêng `/quest`, `/hypesquad`, `/badge` chỉ dùng được bằng Slash vì cần nhập thông tin riêng tư. Tính năng nối từ đọc trực tiếp tin nhắn thường trong kênh đang chơi.

---

<a id="tinh-nang-noi-bat"></a>
### ✨ Tính năng nổi bật

* **🗣️ Đọc giọng nói (TTS):** `/say` để Yui vào phòng voice và đọc to nội dung bạn nhập bằng gTTS. Hỗ trợ 5 ngôn ngữ (Tiếng Việt, English, 日本語, 한국어, 中文), lưu ngôn ngữ riêng từng người bằng `/language`, có hàng chờ, giới hạn độ dài và tự rời phòng khi rảnh. Bot đọc thầm lặng, không gửi thông báo vào kênh chat.
* **🔤 Nối từ tiếng Việt:** Trò chơi nối từ ngay trong kênh chat, có kiểm tra từ điển, chống lặp từ trong 50 lượt gần nhất, và không cho một người nối liên tiếp 2 lượt.
* **💰 Hệ thống Yui Coin:** Điểm danh mỗi ngày (`/daily`), đi làm việc vặt kiếm tiền (`/work`), xem ví (`/cash`), bảng xếp hạng (`/top`) và chuyển tiền cho nhau (`/give`), có giới hạn chống lạm dụng.
* **🎲 Minigame cá cược:** Dò Mìn (`/mine`) và Tung đồng xu (`/coinflip`) — cược Yui Coin để nhân thưởng.
* **🎰 Gacha "Tối nay xem gì":** Quay ngẫu nhiên với 4 độ hiếm (Common / Rare / Epic / Mythic), có cơ chế pity, giới hạn lượt quay mỗi ngày (reset 3:00 sáng giờ VN), lịch sử, thống kê, bảng xếp hạng và kho đồ sưu tập.
* **🛠️ Công cụ tiện ích (Độc quyền):** Tự động cày nhiệm vụ Discord (`/quest`), cày huy hiệu Game Variety & Play Time (`/badge`) và đổi nhà HypeSquad (`/hypesquad`) thông qua UI Modal. Các lệnh này chỉ dùng được trong kênh được cấu hình sẵn.
* **🖼️ Avatar & Banner:** `/avatar` và `/banner` xem ảnh đại diện/banner cá nhân lẫn ảnh riêng theo từng server (nếu người dùng có đặt).
* **🤗 Tương tác vui:** Loạt lệnh tương tác kiểu "anime" (`/hug`, `/kiss`, `/pat`, `/slap`, `/dance`...) và gợi ý `/hom-nay-an-gi`.
* **🔔 Thông báo ra/vào voice:** Lệnh `/thongbao` (cần quyền Manage Server) bật/tắt lời chào cho toàn server khi có người vào/ra kênh thoại, với tin nhắn ngẫu nhiên theo phong cách Yui.
* **📖 Menu lệnh:** `/help` mở menu chọn danh mục để tra cứu lệnh ngay trong Discord, tự cập nhật theo các lệnh đang có.

---

<a id="yeu-cau-he-thong"></a>
### 📦 Yêu cầu hệ thống

- **Python** `>= 3.11`.
- **FFmpeg** đã cài trong hệ thống (bắt buộc cho TTS).
- **Discord Bot Token:** Tạo tại [Discord Developer Portal](https://discord.com/developers/applications) *(cần bật **Message Content Intent** và **Server Members Intent**)*.

---

<a id="cai-dat-trien-khai"></a>
### 🚀 Hướng dẫn cài đặt & Triển khai

#### 1. Clone mã nguồn
```bash
git clone https://github.com/2amkeyl/yui-beta-v1.0b.git
cd yui-beta-v1.0b
```

#### 2. Thiết lập biến môi trường
Tạo file `.env` ở thư mục gốc của repo với nội dung:
```env
BOT_TOKEN=your_discord_bot_token_here
```

#### 3. Chạy trực tiếp bằng Python
```bash
pip install -r requirements.txt
python main.py
```

> 💡 Nếu dùng `/quest`, `/badge`, `/hypesquad`, hãy đổi `QUEST_CHANNEL_ID` trong `cogs/badge_cog.py` thành ID kênh của server bạn.

---

<a id="danh-sach-lenh"></a>
### 🕹️ Danh sách lệnh (Commands)

**🗣️ Đọc giọng nói (TTS)**

| Lệnh | Mô tả |
| :--- | :--- |
| `/say <nội dung> [ngôn ngữ]` | Yui vào phòng voice của bạn và đọc to nội dung (tối đa 200 ký tự). |
| `/language [ngôn ngữ]` | Chọn ngôn ngữ giọng đọc riêng cho bạn (bỏ trống để xem ngôn ngữ hiện tại). |
| `/leave` | Cho Yui rời phòng voice (chỉ người đang ở cùng phòng với Yui). |

**🔤 Nối từ**

| Lệnh | Mô tả |
| :--- | :--- |
| `/noitu` | Bắt đầu ván nối từ trong kênh hiện tại. |
| `/noitu_stop` | Dừng ván nối từ đang diễn ra. |

**💰 Kinh tế (Yui Coin)**

| Lệnh | Mô tả |
| :--- | :--- |
| `/daily` | Điểm danh nhận Yui Coin miễn phí mỗi ngày. |
| `/work` | Đi làm việc vặt kiếm 200–1,000 Yui Coin, 30 phút làm được 1 lần. |
| `/cash [thành viên]` | Xem số dư ví và số trận thắng nối từ (mặc định là chính bạn). |
| `/top <coins \| wins>` | Xem bảng xếp hạng đại gia Yui Coin hoặc cao thủ nối từ. |
| `/give <thành viên> <số tiền>` | Chuyển Yui Coin cho người khác (tối đa 5,000,000/ngày). |

**🎲 Minigame**

| Lệnh | Mô tả |
| :--- | :--- |
| `/mine [cược] [số mìn]` | Dò Mìn — mở ô an toàn để nhân thưởng, trúng mìn là mất cược. Bỏ trống: cược 1 coin, 3 mìn. |
| `/coinflip [cược] [mặt]` | Tung đồng xu, đoán đúng để x2 tiền cược. Bỏ trống: cược 1 coin, mặt Ngửa. Prefix: `yuicoinflip 100 sap` hoặc `yuicoinflip ngua 100`. |

**🎰 Gacha "Tối nay xem gì"**

| Lệnh | Mô tả |
| :--- | :--- |
| `/toi-nay-xem-gi` | Quay gacha ngẫu nhiên (cooldown 5 giây, tối đa 30 lượt/ngày, pity 90). |
| `/toi-nay-lichsu` | Xem lịch sử 100 lần quay gần nhất. |
| `/toi-nay-thongke` | Xem thống kê "nhân phẩm" gacha của bạn. |
| `/toi-nay-top` | Bảng xếp hạng nhân phẩm gacha toàn server. |
| `/toi-nay-kho-do` | Khoe bộ sưu tập Mythic và Epic. |

**🖼️ Hồ sơ**

| Lệnh | Mô tả |
| :--- | :--- |
| `/avatar [thành viên]` | Xem avatar cá nhân và avatar riêng theo server (nếu có) của một người. |
| `/banner [thành viên]` | Xem banner cá nhân và banner riêng theo server (nếu có) của một người. |

**🛠️ Công cụ tiện ích độc quyền** *(chỉ Slash, chỉ dùng trong kênh được cấu hình)*

| Lệnh | Mô tả |
| :--- | :--- |
| `/quest` | Mở bảng nhập token để Yui treo máy cày Discord Quest. |
| `/badge` | Mở bảng nhập token/cookie để cày huy hiệu Game Variety & Play Time. |
| `/hypesquad <house>` | Gán, đổi hoặc gỡ huy hiệu nhà HypeSquad. |

**🤗 Tương tác vui**

| Lệnh | Mô tả |
| :--- | :--- |
| `/hug`, `/cuddle`, `/kiss`, `/pat`, `/slap`, `/kill`, `/poke`, `/highfive`, `/handhold`, `/tickle`, `/cry`, `/dance`, `/nom`, `/punch`, `/snuggle`, `/stare` | Gửi GIF tương tác kiểu anime tới một thành viên khác. |
| `/hom-nay-an-gi` | Gợi ý ngẫu nhiên "hôm nay ăn gì" cho người lười nghĩ. |

**🔔 Thông báo voice & trợ giúp**

| Lệnh | Mô tả |
| :--- | :--- |
| `/thongbao <on \| off>` | Bật/tắt thông báo ra vào kênh voice cho toàn server (cần quyền **Manage Server**). |
| `/help` | Mở menu chọn danh mục để xem toàn bộ lệnh của Yui. |

---

<a id="xu-ly-su-co"></a>
### 🛠️ Xử lý sự cố (Troubleshooting)

<details>
<summary><b>1. Bot vào voice channel nhưng không phát tiếng rồi tự thoát?</b></summary>

- Kiểm tra `FFmpeg` và `PyNaCl` (kèm `davey`) đã được cài đặt đúng.
- Đảm bảo bot có quyền `Connect` và `Speak` trong phòng voice.
- Bot tự rời phòng sau 60 giây không có gì để đọc, đây là hành vi bình thường.
</details>

<details>
<summary><b>2. Lệnh Slash (`/`) không hiện ra trong Discord?</b></summary>

- Slash Command cần tối đa vài phút để đồng bộ toàn cục sau lần khởi động đầu tiên — hãy đợi hoặc thử `/` lại sau khi bot báo "Đã đồng bộ toàn bộ hệ thống bot!" trong log.
- Kiểm tra bot đã được mời vào server với scope `applications.commands`.
</details>

<details>
<summary><b>3. Lệnh prefix (`yui...`) không phản hồi?</b></summary>

- Đảm bảo đã bật **Message Content Intent** trong Developer Portal.
- Viết liền prefix với tên lệnh, vd `yuicash`. Xem cách gọi từng lệnh trong `/help`.
</details>

<details>
<summary><b>4. `/say` không đọc hoặc báo lỗi tạo giọng?</b></summary>

- `gTTS` cần kết nối mạng tới Google, hãy kiểm tra mạng của máy chủ.
- Cậu phải đang ở trong một phòng voice, nội dung tối đa 200 ký tự và mỗi người phải đợi vài giây giữa hai lần dùng.
</details>

---

<a id="cong-nghe-su-dung"></a>
### 🧰 Công nghệ sử dụng

* **Core Runtime:** [Python 3.11+](https://www.python.org/)
* **Discord API Wrapper:** [discord.py v2.x](https://github.com/Rapptz/discord.py) (Slash Commands)
* **Text-to-Speech:** [gTTS](https://github.com/pndurette/gTTS) & [FFmpeg](https://ffmpeg.org/)
* **Xử lý ảnh:** [Pillow](https://python-pillow.org/)

---

<a id="giay-phep-ban-quyen"></a>
### 📄 Giấy phép & Bản quyền

Dự án được cấp phép theo **MIT License**. Xem chi tiết tại file [LICENSE](LICENSE).

*Dự án được chia sẻ với mục đích học tập và sử dụng cá nhân phi thương mại. Vui lòng tôn trọng [Discord](https://discord.com/terms).*

---

<div align="center">
  <p>Được thực hiện bởi <b>Keyl</b> • Tham gia <a href="https://discord.gg/ErGMVF77Pc"><b>Discord Support Server</b></a> 🎸</p>
</div>

---
---

<a name="-english"></a>
## English

### 📑 Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Prerequisites](#prerequisites)
4. [Installation & Deployment](#installation)
5. [Command Reference](#commands)
6. [Troubleshooting](#troubleshooting)
7. [Tech Stack](#tech-stack)
8. [License & Disclaimer](#license)

---

<a id="overview"></a>
### 🌟 Overview

**Yui** is a self-hosted Discord bot inspired by **Yui Hirasawa** from the anime *K-ON!*, responding entirely in friendly, casual Vietnamese.

> ⚠️ **Control Mode:** Every command is a **Slash Command (`/`)**. Most commands can also be triggered with the **`yui` prefix** written directly against the command name (e.g. `yuicash`, `yuihug @someone`) via `PrefixBridgeCog`. `/quest`, `/hypesquad` and `/badge` are Slash-only because they collect private information. The word-chain game reads plain messages directly in the active channel.

---

<a id="key-features"></a>
### ✨ Key Features

* **🗣️ Text-to-Speech:** `/say` makes Yui join your voice channel and read your text aloud using gTTS. Supports 5 languages (Vietnamese, English, Japanese, Korean, Chinese), per-user language preference via `/language`, a playback queue, length limits and auto-leave when idle. Playback is silent in chat, with no announcement message.
* **🔤 Vietnamese Word-Chain Game:** A dictionary-checked word-chaining game played directly in chat, with anti-repeat protection over the last 50 turns and no back-to-back turns for the same player.
* **💰 Yui Coin Economy:** Daily rewards (`/daily`), odd jobs (`/work`), wallet lookup (`/cash`), leaderboards (`/top`), and peer-to-peer transfers (`/give`) with anti-abuse limits.
* **🎲 Betting Minigames:** Minesweeper (`/mine`) and Coinflip (`/coinflip`) — wager Yui Coin for a chance to multiply your winnings.
* **🎰 "Tonight's Pick" Gacha:** Random rolls across 4 rarities (Common / Rare / Epic / Mythic) with a pity system, daily roll cap (resets at 3:00 AM Vietnam time), history, stats, leaderboard and a showcase of your collection.
* **🛠️ Exclusive Utilities:** Automated Discord Quest completion (`/quest`), Game Variety & Play Time badge farming (`/badge`) and HypeSquad house switcher (`/hypesquad`) through Modals. These only work in a pre-configured channel.
* **🖼️ Avatar & Banner Lookup:** `/avatar` and `/banner` show personal and per-server avatars/banners.
* **🤗 Fun Interactions:** Anime-style reaction commands (`/hug`, `/kiss`, `/pat`, `/slap`, `/dance`, ...) and `/hom-nay-an-gi` food suggestions.
* **🔔 Voice Join/Leave Notifications:** `/thongbao` (requires Manage Server) toggles server-wide greetings when someone joins or leaves a voice channel.
* **📖 In-Discord Command Menu:** `/help` opens an interactive category picker that updates automatically with the available commands.

---

<a id="prerequisites"></a>
### 📦 Prerequisites

* **Python** `>= 3.11`.
* **FFmpeg** installed on the host (required for TTS).
* **Discord Bot Token** from [Discord Developer Portal](https://discord.com/developers/applications) *(**Message Content Intent** and **Server Members Intent** must be enabled)*.

---

<a id="installation"></a>
### 🚀 Installation & Deployment

#### 1. Clone the Repository
```bash
git clone https://github.com/2amkeyl/yui-beta-v1.0b.git
cd yui-beta-v1.0b
```

#### 2. Configure Environment Variables
Create a `.env` file in the repo root with:
```env
BOT_TOKEN=your_discord_bot_token_here
```

#### 3. Run directly with Python
```bash
pip install -r requirements.txt
python main.py
```

> 💡 If you use `/quest`, `/badge` or `/hypesquad`, change `QUEST_CHANNEL_ID` in `cogs/badge_cog.py` to your own server's channel ID.

---

<a id="commands"></a>
### 🕹️ Command Reference

**🗣️ Text-to-Speech**

| Command | Description |
| :--- | :--- |
| `/say <text> [language]` | Yui joins your voice channel and reads the text aloud (max 200 characters). |
| `/language [language]` | Sets your personal TTS language (leave empty to see the current one). |
| `/leave` | Makes Yui leave the voice channel (only for members in the same channel). |

**🔤 Word Chain**

| Command | Description |
| :--- | :--- |
| `/noitu` | Starts a word-chain round. |
| `/noitu_stop` | Stops the word-chain round. |

**💰 Economy (Yui Coin)**

| Command | Description |
| :--- | :--- |
| `/daily` | Claim free daily Yui Coin reward. |
| `/work` | Do odd jobs for 200–1,000 Yui Coin, once every 30 minutes. |
| `/cash [member]` | Shows wallet balance and win count. |
| `/top <coins \| wins>` | Shows economic leaderboards. |
| `/give <member> <amount>` | Transfers Yui Coin to another member (up to 5,000,000/day). |

**🎲 Minigames**

| Command | Description |
| :--- | :--- |
| `/mine [bet] [mine count]` | Minesweeper minigame. Defaults: bet 1 coin, 3 mines. |
| `/coinflip [bet] [side]` | Coinflip minigame. Defaults: bet 1 coin, heads. Prefix: `yuicoinflip 100 sap` (tails) or `yuicoinflip ngua 100` (heads). |

**🎰 "Tonight's Pick" Gacha**

| Command | Description |
| :--- | :--- |
| `/toi-nay-xem-gi` | Rolls the gacha (5s cooldown, max 30 rolls/day, pity at 90). |
| `/toi-nay-lichsu` | Shows your last 100 rolls. |
| `/toi-nay-thongke` | Shows your gacha luck stats. |
| `/toi-nay-top` | Server-wide gacha luck leaderboard. |
| `/toi-nay-kho-do` | Showcases your Mythic and Epic collection. |

**🖼️ Profile**

| Command | Description |
| :--- | :--- |
| `/avatar [member]` | Shows global and server avatars. |
| `/banner [member]` | Shows global and server banners. |

**🛠️ Utilities** *(Slash-only, pre-configured channel only)*

| Command | Description |
| :--- | :--- |
| `/quest` | Opens the token form so Yui can farm Discord Quests. |
| `/badge` | Opens the token/cookie form to farm Game Variety & Play Time badges. |
| `/hypesquad <house>` | Assigns, changes or removes your HypeSquad house. |

**🤗 Fun Interactions**

| Command | Description |
| :--- | :--- |
| `/hug`, `/cuddle`, `/kiss`, `/pat`, `/slap`, `/kill`, `/poke`, `/highfive`, `/handhold`, `/tickle`, `/cry`, `/dance`, `/nom`, `/stare`, `/punch`, `/snuggle` | Anime interaction GIF. |
| `/hom-nay-an-gi` | Random food suggestions. |

**🔔 Voice Notifications & Help**

| Command | Description |
| :--- | :--- |
| `/thongbao <on \| off>` | Toggles voice join/leave announcements (requires **Manage Server**). |
| `/help` | Opens interactive command directory. |

---

<a id="troubleshooting"></a>
### 🛠️ Troubleshooting

<details>
<summary><b>1. Bot joins voice channel but plays no sound and leaves?</b></summary>

- Verify `FFmpeg` and `PyNaCl` (plus `davey`) are correctly installed.
- Ensure the bot has `Connect` and `Speak` permissions.
- The bot leaves after 60 seconds with nothing to read, which is expected.
</details>

<details>
<summary><b>2. Slash commands (`/`) don't show up in Discord?</b></summary>

- Global slash command sync can take a few minutes after initial startup.
- Verify bot invite scope includes `applications.commands`.
</details>

<details>
<summary><b>3. Prefix commands (`yui...`) don't respond?</b></summary>

- Make sure **Message Content Intent** is enabled in the Developer Portal.
- Write the prefix directly against the command name, e.g. `yuicash`. See `/help` for usage of each command.
</details>

<details>
<summary><b>4. `/say` doesn't speak or reports a voice generation error?</b></summary>

- `gTTS` needs internet access to Google, so check your host's connection.
- You must be in a voice channel, keep the text under 200 characters, and wait a few seconds between uses.
</details>

---

<a id="tech-stack"></a>
### 🧰 Tech Stack

* **Core Runtime:** [Python 3.11+](https://www.python.org/)
* **Discord API Wrapper:** [discord.py v2.x](https://github.com/Rapptz/discord.py)
* **Text-to-Speech:** [gTTS](https://github.com/pndurette/gTTS) & [FFmpeg](https://ffmpeg.org/)
* **Image Processing:** [Pillow](https://python-pillow.org/)

---

<a id="license"></a>
### 📄 License & Disclaimer

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

*This project is shared for educational and personal, non-commercial use. Please respect [Discord's Terms of Service](https://discord.com/terms).*

---

<div align="center">
  <p>Made by <b>Keyl</b> • Join the <a href="https://discord.gg/ErGMVF77Pc"><b>Discord Support Server</b></a> 🎸</p>
</div>
