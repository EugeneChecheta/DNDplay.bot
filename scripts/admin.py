"""Управление администратором и middleware для разграничения доступа."""
import logging
from pathlib import Path

from aiogram import Router, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import Message

BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_FILE = BASE_DIR / "configuration" / "admin.txt"

router = Router(name="admin")


def get_admin_id() -> int | None:
    """Возвращает ID администратора или None, если файл пуст/отсутствует."""
    if not ADMIN_FILE.exists():
        return None
    try:
        text = ADMIN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def set_admin_id(user_id: int) -> bool:
    """Пытается записать ID в файл. True — если записано, False — если уже занято."""
    if get_admin_id() is not None:
        return False
    try:
        ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        ADMIN_FILE.write_text(str(user_id), encoding="utf-8")
        return True
    except OSError as e:
        logging.exception("admin: не удалось записать admin.txt: %s", e)
        return False


def is_admin(user_id: int) -> bool:
    return get_admin_id() == user_id


class AdminOnlyMiddleware(BaseMiddleware):
    """Пускает не-админов только к /player, /start, /admin и их колбэкам."""

    ALLOWED_CALLBACKS = {
        "back_to_start",
        "noop",
        "noop_sess",
    }

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        if is_admin(user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            text = (event.text or "").strip()
            if text.startswith(("/start", "/player", "/admin")):
                return await handler(event, data)
            await event.answer(
                "⛔ У вас нет доступа к этому разделу.\n"
                "Используйте /player для просмотра персонажей."
            )
            return

        if isinstance(event, type(event)) and hasattr(event, "data"):
            cb_data = getattr(event, "data", "") or ""
            if cb_data.startswith("player_") or cb_data in self.ALLOWED_CALLBACKS:
                return await handler(event, data)
            try:
                await event.answer("⛔ Доступ запрещён", show_alert=True)
            except Exception:
                pass
            return

        return await handler(event, data)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    current = get_admin_id()

    if current is None:
        if set_admin_id(user_id):
            await message.answer(
                f"👑 *Вы назначены администратором!*\n\n"
                f"Ваш ID `{user_id}` сохранён в `configuration/admin.txt`.\n"
                f"Теперь вам доступны все модули. Используйте /start.",
                parse_mode="Markdown",
            )
        else:
            await message.answer("⛔ Не удалось назначить администратора.")
        return

    if current == user_id:
        await message.answer(
            f"👑 Вы уже администратор (ID: `{user_id}`).\n"
            f"Используйте /start для доступа ко всем модулям.",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        f"⛔ Администратор уже назначен (ID: `{current}`). Команда недоступна.",
        parse_mode="Markdown",
    )