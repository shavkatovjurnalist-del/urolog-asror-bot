"""Telegram Mini App `initData` ni tekshirish.

Mini App'dan kelgan so'rov haqiqatan ham Telegram foydalanuvchisidan ekanini
bot tokeni yordamida HMAC-SHA256 orqali tasdiqlaymiz.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.config import BOT_TOKEN

MAX_AGE = 24 * 60 * 60  # 24 soat


class InitDataError(Exception):
    pass


def parse_init_data(init_data: str, max_age: int = MAX_AGE) -> dict:
    """initData ni tekshirib, ichidagi ma'lumotni qaytaradi. Xato bo'lsa — InitDataError."""
    if not init_data:
        raise InitDataError("initData bo'sh")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("hash yo'q")

    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        raise InitDataError("imzo mos kelmadi")

    auth_date = int(pairs.get("auth_date", "0"))
    if max_age and time.time() - auth_date > max_age:
        raise InitDataError("initData eskirgan")

    user = json.loads(pairs["user"]) if pairs.get("user") else None
    return {"user": user, "raw": pairs}


class TgUser:
    """aiogram User ga o'xshash minimal obyekt (repo.upsert_user uchun)."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.username = data.get("username", "")
        self.first_name = data.get("first_name", "")
        self.last_name = data.get("last_name", "")
