# Expense Tracker Telegram Bot

A small Telegram bot that keeps a private list of your expenses in SQLite. Every user sees only their own data. No framework is needed, the bot talks to the Telegram HTTP API directly with long polling.

## Commands

| Command | What it does |
|---|---|
| /add 45.5 food lunch | Add an expense: amount, category, optional note |
| /list | Last 10 expenses |
| /today | Total spent today |
| /month | This month grouped by category |
| /delete 12 | Delete expense number 12 |
| /help | Show help |

## Setup

1. Create a bot with @BotFather in Telegram and copy the token.
2. Install the dependency and run:

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456:ABC..."
python3 bot.py
```

3. Open your bot in Telegram and send /start.

Data is stored in expenses.db next to the script (change it with the BOT_DB variable).

## How it works

- getUpdates with a 30 second timeout waits for new messages (long polling)
- Each command is a small function that reads or writes SQLite and returns the reply text
- Every query filters by chat_id, so users cannot see or delete expenses of other users
- The token is read from an environment variable and is never stored in the code

## Run in the background on Linux

Use a systemd service with Restart=always, or run it inside tmux or screen.

## License

MIT
