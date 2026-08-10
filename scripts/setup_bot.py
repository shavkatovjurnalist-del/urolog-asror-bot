"""Bot sozlamalarini Telegram tomonida o'rnatish.

Ishlatish:  python -m scripts.setup_bot
BASE_URL .env da https bo'lishi shart (Render manzili).
"""
from __future__ import annotations

import asyncio

import httpx

from app.config import BASE_URL, BOT_TOKEN, WEBAPP_URL, WEBHOOK_PATH

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

COMMANDS = [
    {"command": "start", "description": "Botni ishga tushirish"},
    {"command": "menu", "description": "Asosiy menyu"},
    {"command": "id", "description": "Telegram ID raqamim"},
]


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        me = (await c.get(f"{API}/getMe")).json()
        print("Bot:", me["result"]["username"] if me.get("ok") else me)

        r = (await c.post(f"{API}/setMyCommands", json={"commands": COMMANDS})).json()
        print("setMyCommands:", r.get("ok"), r.get("description", ""))

        r = (await c.post(f"{API}/setMyDescription", json={
            "description": "Urolog-androlog Dr. Asror To'rayev rasmiy boti. "
                           "Xizmatlar, jarrohlik usullari, qabul joylari va onlayn yozilish."
        })).json()
        print("setMyDescription:", r.get("ok"), r.get("description", ""))

        r = (await c.post(f"{API}/setMyShortDescription", json={
            "short_description": "Urolog-androlog Dr. Asror To'rayev — Samarqand. "
                                 "Qabulga onlayn yozilish."
        })).json()
        print("setMyShortDescription:", r.get("ok"), r.get("description", ""))

        if not BASE_URL.startswith("https://"):
            print("⚠️  BASE_URL https emas — webhook va Mini App tugmasi o'rnatilmadi.")
            return

        r = (await c.post(f"{API}/setChatMenuButton", json={
            "menu_button": {
                "type": "web_app",
                "text": "Sayt",
                "web_app": {"url": WEBAPP_URL},
            }
        })).json()
        print("setChatMenuButton:", r.get("ok"), r.get("description", ""))

        r = (await c.post(f"{API}/setWebhook", json={
            "url": f"{BASE_URL}{WEBHOOK_PATH}",
            "drop_pending_updates": True,
            "allowed_updates": ["message", "callback_query", "my_chat_member"],
        })).json()
        print("setWebhook:", r.get("ok"), r.get("description", ""))


if __name__ == "__main__":
    asyncio.run(main())
