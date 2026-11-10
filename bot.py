import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from scripts.characters import router as characters_router
from scripts.items import router as items_router
from scripts.session import router as session_router
from scripts.enemies import router as enemies_router
from scripts.player import router as player_router
from scripts.admin import (
    router as admin_router,
    AdminOnlyMiddleware,
    is_admin,
)

BASE_DIR = Path(__file__).resolve().parent


def read_token() -> str:
    token_path = BASE_DIR / "configuration" / "token.txt"
    if not token_path.exists():
        raise FileNotFoundError(
            f"Файл с токеном не найден: {token_path}\n"
            f"Создайте его и вставьте токен от @BotFather."
        )
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"Файл {token_path} пуст.")
    return token


logging.basicConfig(level=logging.INFO)
bot = Bot(token=read_token())
dp = Dispatcher(storage=MemoryStorage())

# Middleware: не-админы допускаются только к /player, /start, /admin
dp.message.outer_middleware(AdminOnlyMiddleware())
dp.callback_query.outer_middleware(AdminOnlyMiddleware())

# Роутеры
dp.include_router(admin_router)
dp.include_router(player_router)
dp.include_router(characters_router)
dp.include_router(items_router)
dp.include_router(session_router)
dp.include_router(enemies_router)


def start_keyboard(user_id: int) -> InlineKeyboardMarkup:
    admin = is_admin(user_id)
    rows = []
    if admin:
        rows = [
            [InlineKeyboardButton(text="👤 Персонажи", callback_data="main_characters")],
            [InlineKeyboardButton(text="🎒 Предметы и инвентарь", callback_data="main_items")],
            [InlineKeyboardButton(text="🏕 Сессия (лагерь / бой / торговля)", callback_data="main_session")],
            [InlineKeyboardButton(text="👹 Бестиарий", callback_data="main_enemies")],
        ]
    rows.append([InlineKeyboardButton(text="🎮 Режим игрока", callback_data="player_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    admin = is_admin(user_id)

    if admin:
        text = (
            "👑 *Добро пожаловать, Администратор!*\n\n"
            "Доступные команды:\n"
            "• /characters — управление персонажами\n"
            "• /items — предметы и инвентарь\n"
            "• /session — лагерь, торговля, бой\n"
            "• /enemies — бестиарий существ\n"
            "• /player — режим игрока (просмотр)\n\n"
            "Выберите раздел:"
        )
    else:
        text = (
            "🎮 *Добро пожаловать!*\n\n"
            "Вам доступен режим просмотра персонажей (/player).\n\n"
            "Выберите раздел:"
        )
    await message.answer(text, parse_mode="Markdown", reply_markup=start_keyboard(user_id))


@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    admin = is_admin(user_id)
    if admin:
        text = "👑 *Главное меню:*\n\nВыберите раздел:"
    else:
        text = "🎮 *Главное меню:*\n\nВыберите раздел:"
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=start_keyboard(user_id),
    )
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())