# Story Bot v2.3 REBORN 🚀

Advanced Telegram Store Bot built with **Python**, **aiogram 3.x**, and **aiosqlite**.

## 🌟 Features
- **Modular Architecture:** Clean and maintainable code structure.
- **Precision Finance:** Uses an integer-cents system to prevent floating-point errors.
- **Atomic Transactions:** Ensures data integrity during financial operations.
- **Multi-level Permissions:** Super Admin, Operator, Support, and User roles.
- **Comprehensive Store Management:** Products, Categories, Orders, Coupons, and Payments.
- **Bilingual Support:** Arabic and English translations.
- **Audit Logging:** Tracks all administrative actions for security.

## 🛠️ Tech Stack
- **Language:** Python 3.11+
- **Framework:** [aiogram 3.x](https://github.com/aiogram/aiogram)
- **Database:** [aiosqlite](https://github.com/omnilib/aiosqlite) (SQLite with async support)
- **Environment:** python-dotenv

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/Hashem816/StoryBot_v2.3_Final.git
cd StoryBot_v2.3_Final
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:
```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=your_telegram_id
DB_PATH=store_v2.db
```

### 4. Run the bot
```bash
python main.py
```

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
