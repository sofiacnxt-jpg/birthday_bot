import os
import csv
import logging
import asyncio
from datetime import date
from io import StringIO

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.environ["BOT_TOKEN"]
CHAT_ID    = os.environ["CHAT_ID"]
SHEETS_ID  = os.environ["SHEETS_ID"]

REMINDER_DAYS = {21, 14, 7, 1, 0}

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEETS_ID}/export?format=csv"


def get_records():
    resp = requests.get(CSV_URL, timeout=15)
    resp.raise_for_status()
    reader = csv.DictReader(StringIO(resp.text))
    return list(reader)


def days_until_birthday(date_str: str):
    today = date.today()
    try:
        day, month = int(date_str.strip().split(".")[0]), int(date_str.strip().split(".")[1])
        bday = date(today.year, month, day)
        if bday < today:
            bday = date(today.year + 1, month, day)
        return (bday - today).days
    except Exception as exc:
        logger.warning("Не вдалося розпарсити дату '%s': %s", date_str, exc)
        return None


def send_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )
    if not resp.ok:
        logger.error("Помилка надсилання: %s", resp.text)
    return resp.ok


def check_birthdays():
    logger.info("Перевіряю дні народження...")
    try:
        records = get_records()
    except Exception as exc:
        logger.error("Помилка читання таблиці: %s", exc)
        send_message(f"⚠️ Не вдалося прочитати таблицю:\n{exc}")
        return

    sent = 0
    for row in records:
        name     = str(row.get("Full Name", "")).strip()
        position = str(row.get("Position",  "")).strip()
        business = str(row.get("Business",  "")).strip()
        bday_str = str(row.get("Date",      "")).strip()

        if not name or not bday_str:
            continue

        days = days_until_birthday(bday_str)
        if days is None or days not in REMINDER_DAYS:
            continue

        if days == 0:
            header = "🎂 <b>Сьогодні день народження!</b>"
        elif days == 1:
            header = "🔔 <b>Завтра день народження!</b>"
        elif days == 7:
            header = "📅 <b>Через 1 тиждень день народження!</b>"
        elif days == 14:
            header = "📅 <b>Через 2 тижні день народження!</b>"
        else:
            header = "📅 <b>Через 3 тижні день народження!</b>"

        text = f"{header}\n\n👤 <b>{name}</b>"
        if position:
            text += f"\n💼 {position}"
        if business:
            text += f"\n🏢 {business}"

        if send_message(text):
            sent += 1
            logger.info("Надіслано: %s (%d дн.)", name, days)

    logger.info("Готово. Надіслано нагадувань: %d", sent)


async def main():
    logger.info("Бот запускається...")
    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
    scheduler.add_job(check_birthdays, "cron", hour=9, minute=0)
    scheduler.start()
    send_message("✅ Бот запущено! Нагадування надходитимуть щодня о <b>9:00</b> за Київським часом.")
    logger.info("Бот працює.")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
