#!/usr/bin/env python3
"""
Expense Tracker Telegram bot (SQLite).

Every user gets their own private list of expenses, stored in a local SQLite file.

Commands:
  /add 45.5 food lunch   - add an expense (amount, category, optional note)
  /list                  - last 10 expenses
  /today                 - total spent today
  /month                 - this month by category
  /delete 12             - delete expense number 12
  /help                  - show help

The bot talks to Telegram with plain HTTPS "long polling":
it asks "any new messages?" and waits up to 30 seconds for an answer.

Setup: export TELEGRAM_BOT_TOKEN="token from @BotFather"  then  python3 bot.py
"""

import os
import sqlite3
import time
from datetime import datetime

import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# The API address can be overridden, this is used by the automated test.
API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org") + "/bot" + TOKEN
DB_FILE = os.environ.get("BOT_DB", "expenses.db")

HELP_TEXT = (
    "Expense tracker\n\n"
    "/add 45.5 food lunch - add an expense\n"
    "/list - last 10 expenses\n"
    "/today - spent today\n"
    "/month - this month by category\n"
    "/delete ID - delete an expense\n"
)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    """Open the database and create the table on first run."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,       -- who owns this expense
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL        -- local time, YYYY-MM-DD HH:MM:SS
        )
        """
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Command handlers: each one takes the database, chat id and arguments
# and returns the text to send back.
# ---------------------------------------------------------------------------
def cmd_add(conn, chat_id, args):
    if len(args) < 2:
        return "Usage: /add 45.5 food lunch"
    try:
        amount = float(args[0].replace(",", "."))    # accept 45,5 too
    except ValueError:
        return "The amount must be a number, for example: /add 45.5 food"
    if amount <= 0:
        return "The amount must be greater than zero."
    category = args[1].lower()
    note = " ".join(args[2:])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO expenses (chat_id, amount, category, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (chat_id, amount, category, note, now),
    )
    conn.commit()
    return "Saved #" + str(cursor.lastrowid) + ": " + format(amount, ".2f") + " " + category


def cmd_list(conn, chat_id, args):
    rows = conn.execute(
        "SELECT id, amount, category, note, created_at FROM expenses "
        "WHERE chat_id = ? ORDER BY id DESC LIMIT 10", (chat_id,)
    ).fetchall()
    if not rows:
        return "No expenses yet. Add one with /add 45.5 food"
    lines = []
    for row_id, amount, category, note, created in rows:
        lines.append("#" + str(row_id) + "  " + created[:10] + "  " + format(amount, ".2f")
                     + "  " + category + ("  " + note if note else ""))
    return "\n".join(lines)


def cmd_today(conn, chat_id, args):
    today = datetime.now().strftime("%Y-%m-%d")
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE chat_id = ? AND created_at LIKE ?",
        (chat_id, today + "%"),
    ).fetchone()[0]
    return "Today: " + format(total, ".2f")


def cmd_month(conn, chat_id, args):
    month = datetime.now().strftime("%Y-%m")
    rows = conn.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE chat_id = ? AND created_at LIKE ? "
        "GROUP BY category ORDER BY SUM(amount) DESC", (chat_id, month + "%"),
    ).fetchall()
    if not rows:
        return "Nothing spent this month yet."
    total = sum(amount for _, amount in rows)
    lines = [category + ": " + format(amount, ".2f") for category, amount in rows]
    return "\n".join(lines) + "\n\nTotal: " + format(total, ".2f")


def cmd_delete(conn, chat_id, args):
    if not args or not args[0].isdigit():
        return "Usage: /delete 12"
    # The chat_id check makes sure nobody can delete another user's data.
    cursor = conn.execute(
        "DELETE FROM expenses WHERE id = ? AND chat_id = ?", (int(args[0]), chat_id)
    )
    conn.commit()
    return "Deleted." if cursor.rowcount else "Expense not found."


COMMANDS = {"/add": cmd_add, "/list": cmd_list, "/today": cmd_today,
            "/month": cmd_month, "/delete": cmd_delete}


def handle_text(conn, chat_id, text):
    """Turn an incoming message into a reply."""
    parts = text.strip().split()
    if not parts:
        return HELP_TEXT
    # In groups Telegram sends commands like /add@MyBot, remove the @part.
    command = parts[0].split("@")[0].lower()
    if command in ("/start", "/help"):
        return HELP_TEXT
    handler = COMMANDS.get(command)
    if handler is None:
        return "Unknown command. Send /help"
    return handler(conn, chat_id, parts[1:])


# ---------------------------------------------------------------------------
# Telegram loop
# ---------------------------------------------------------------------------
def send(chat_id, text):
    requests.post(API + "/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=15)


def main():
    if not TOKEN:
        raise SystemExit("Set the TELEGRAM_BOT_TOKEN environment variable first.")
    conn = init_db()
    offset = 0   # id of the next update we want, so we never see a message twice
    print("Bot started. Press Ctrl+C to stop.")
    while True:
        try:
            reply = requests.get(API + "/getUpdates",
                                 params={"offset": offset, "timeout": 30}, timeout=40).json()
            for update in reply.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if message and "text" in message:
                    chat_id = message["chat"]["id"]
                    send(chat_id, handle_text(conn, chat_id, message["text"]))
        except requests.RequestException:
            time.sleep(5)          # network problem: wait and try again
        except KeyboardInterrupt:
            print("Stopped.")
            break


if __name__ == "__main__":
    main()
