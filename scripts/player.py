"""Модуль игрока: просмотр персонажей без редактирования."""
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from scripts.characters import (
    list_characters, load_character,
    format_character, get_current,
)
from scripts.items import get_inventory, format_coins

router = Router(name="player")


async def _safe_edit(message, text, **kwargs):
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _player_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Список персонажей", callback_data="player_list")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_start")],
    ])


def _player_card_text(char) -> str:
    return format_character(char) + "\n\n_🔒 Просмотр без редактирования_"


def _player_card_kb(codename: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить данные",
                              callback_data=f"player_refresh:{codename}")],
        [InlineKeyboardButton(text="🎒 Инвентарь",
                              callback_data=f"player_inv:{codename}")],
        [InlineKeyboardButton(text="📖 Заклинания и ячейки",
                              callback_data=f"player_spells:{codename}")],
        [InlineKeyboardButton(text="🎯 Навыки",
                              callback_data=f"player_skills:{codename}")],
        [InlineKeyboardButton(text="✨ Умения и особенности",
                              callback_data=f"player_features:{codename}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="player_list")],
    ])


@router.message(Command("player"))
async def cmd_player(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🎮 *Режим игрока*\n\n"
        "Здесь вы можете просматривать персонажей — без возможности редактирования.\n\n"
        "Выберите раздел:",
        parse_mode="Markdown",
        reply_markup=_player_menu_kb(),
    )


@router.callback_query(F.data == "player_menu")
async def cb_player_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _safe_edit(
        callback.message,
        "🎮 *Режим игрока*\n\nВыберите раздел:",
        parse_mode="Markdown",
        reply_markup=_player_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "player_list")
async def cb_player_list(callback: CallbackQuery):
    chars = list_characters()
    if not chars:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="player_list")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="player_menu")],
        ])
        await _safe_edit(callback.message, "📭 Нет сохранённых персонажей.", reply_markup=kb)
        await callback.answer()
        return

    kb = []
    for c in chars:
        classes_str = ", ".join(f"{k} {v}" for k, v in c["classes"].items())
        kb.append([InlineKeyboardButton(
            text=f"{c['name']} — {classes_str}",
            callback_data=f"player_view:{c['codename']}")])
    kb.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="player_list")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="player_menu")])

    await _safe_edit(
        callback.message,
        "👤 *Персонажи*\n\nВыберите для просмотра:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("player_view:"))
async def cb_player_view(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        _player_card_text(char),
        parse_mode="Markdown",
        reply_markup=_player_card_kb(codename),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("player_refresh:"))
async def cb_player_refresh(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        _player_card_text(char),
        parse_mode="Markdown",
        reply_markup=_player_card_kb(codename),
    )
    await callback.answer("🔄 Данные обновлены")


@router.callback_query(F.data.startswith("player_inv:"))
async def cb_player_inv(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    inv = get_inventory(char)
    items = inv.get("items", [])
    coins = format_coins(inv.get("coins", {}))

    text = f"🎒 *Инвентарь: {char['name']}*\n\n"
    if not items:
        text += "_Пусто._\n"
    else:
        for i, it in enumerate(items):
            qty = it.get("quantity", 1)
            qty_str = f" ×{qty}" if qty > 1 else ""
            e = int(it.get("enchantment", 0) or 0)
            e_str = f" +{e}" if e else ""
            eq = " 🟢" if it.get("equipped_slot") else ""
            text += f"{i + 1}. *{it.get('name', '?')}*{e_str}{qty_str}{eq}\n"
    text += f"\n💰 Монеты: *{coins}*"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"player_inv:{codename}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"player_view:{codename}")],
    ])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("player_spells:"))
async def cb_player_spells(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    snap = get_current(char)
    prepared = snap.get("prepared_spells", [])
    slots = snap.get("spell_slots", {})

    text = f"📖 *Заклинания и ячейки: {char['name']}*\n\n"
    text += "*Подготовленные:*\n"
    if not prepared:
        text += "_нет._\n"
    else:
        for name in prepared:
            text += f"• {name}\n"

    text += "\n🔮 *Ячейки:*\n"
    any_slots = False
    for lvl in sorted(int(k) for k in slots.keys()):
        d = slots[str(lvl)]
        if d.get("max", 0) > 0:
            any_slots = True
            text += f"Ур. {lvl}: {d.get('current', d['max'])}/{d['max']}\n"
    if not any_slots:
        text += "_нет._"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"player_spells:{codename}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"player_view:{codename}")],
    ])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("player_skills:"))
async def cb_player_skills(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    skills = get_current(char).get("skills", [])

    text = f"🎯 *Навыки: {char['name']}*\n\n"
    if not skills:
        text += "_нет._"
    else:
        for s in skills:
            text += f"• *{s['name']}*"
            if s.get("type"):
                text += f" _{s['type']}_"
            text += f"\n{s.get('description', '')}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"player_skills:{codename}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"player_view:{codename}")],
    ])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("player_features:"))
async def cb_player_features(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    features = get_current(char).get("features", [])

    text = f"✨ *Умения: {char['name']}*\n\n"
    if not features:
        text += "_нет._"
    else:
        for f in features:
            text += f"• *{f['name']}*"
            if f.get("source"):
                text += f" _({f['source']})_"
            text += f"\n{f.get('description', '')}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"player_features:{codename}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"player_view:{codename}")],
    ])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()