# Persian Telegram Bot — Final (5 Inline Buttons)
Inline keyboard menus, PTB v21, Python 3.11/3.12/3.14. No admin notifications.

## Quick Start
1) Create bot via @BotFather and copy token.
2) Copy `.env.example` → `.env` and fill:
```
TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
SITE_URL="https://designeryas.com"
LOG_LEVEL="INFO"
```
3) Run:
```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
python bot.py
```
