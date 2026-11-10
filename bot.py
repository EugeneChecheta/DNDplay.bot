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
dp.include_router(characters_router)
dp.include_router(items_router)


def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Персонажи", callback_data="main_characters")],
        [InlineKeyboardButton(text="🎒 Предметы и инвентарь", callback_data="main_items")],
    ])


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я бот для D&D 5e (2024).\n\n"
        "• /characters — управление персонажами\n"
        "• /items — предметы и инвентарь\n\n"
        "Выберите раздел:",
        reply_markup=start_keyboard(),
    )


@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:\n\n"
        "• /characters — персонажи\n"
        "• /items — предметы",
        reply_markup=start_keyboard(),
    )
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())