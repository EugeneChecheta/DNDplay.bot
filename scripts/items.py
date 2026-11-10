import json
from pathlib import Path

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from scripts.characters import (
    load_character,
    _save_character as save_character,
    has_weapon_proficiency,
)

router = Router(name="items")

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_ITEMS_DIR = BASE_DIR / "archive" / "items"
ARCHIVE_ITEMS_DIR.mkdir(parents=True, exist_ok=True)

COIN_KEYS = ["mm", "sm", "zm", "pm"]
COIN_TO_MM = {"mm": 1, "sm": 10, "zm": 100, "pm": 1000}
COIN_SHORT = {"mm": "мм", "sm": "см", "zm": "зм", "pm": "пм"}
COIN_NAMES = {"mm": "медь (мм)", "sm": "серебро (см)", "zm": "золото (зм)", "pm": "платина (пм)"}

SOURCE_TITLES = {
    "arms": "⚔️ Оружие",
    "armor": "🛡 Доспехи и щиты",
    "tools": "🛠 Инструменты",
    "food": "🍖 Еда и припасы",
    "quests": "📜 Квестовые предметы",
    "other": "📦 Снаряжение",
}
SOURCE_KEYS = {
    "arms": "weapons",
    "armor": None,   # есть armor + shields
    "tools": "tools",
    "food": "food",
    "quests": "quests",
    "other": "other",
}

# ---------- Экипировка ----------
VALID_SLOTS = ["armor", "melee_main", "melee_off", "ranged_main", "ranged_off"]
SLOT_TITLES = {
    "armor": "🛡 Доспех",
    "melee_main": "⚔️ Бл. осн.",
    "melee_off": "⚔️ Бл. втор.",
    "ranged_main": "🏹 Дал. осн.",
    "ranged_off": "🏹 Дал. втор.",
}
SLOT_INDEX = {
    "armor": "0",
    "melee_main": "1",
    "melee_off": "2",
    "ranged_main": "3",
    "ranged_off": "4",
}
SLOT_FROM_INDEX = {v: k for k, v in SLOT_INDEX.items()}

EQUIPPABLE_CATEGORIES = {"weapon", "armor", "shield"}

# Множитель цены зачарования (в процентах)
ENCHANT_MULT = {0: 0, 1: 20, 2: 45, 3: 100, 4: 175, 5: 250}


# ---------- Безопасное редактирование сообщения ----------
async def _safe_edit(message: Message, text: str, **kwargs) -> None:
    """edit_text, который не падает, если содержимое не изменилось."""
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ---------- JSON ----------
def _load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_items_by_source(source: str) -> list:
    data = _load_json(ARCHIVE_ITEMS_DIR / f"{source}.json")
    if not data:
        return []
    result = []
    if source == "armor":
        for item in data.get("armor", []):
            item = dict(item); item["source"] = "armor"; result.append(item)
        for item in data.get("shields", []):
            item = dict(item); item["source"] = "armor"; result.append(item)
    else:
        key = SOURCE_KEYS.get(source, "items")
        for item in data.get(key, []):
            item = dict(item); item["source"] = source; result.append(item)
    return result


def get_all_items() -> list:
    result = []
    for source in SOURCE_TITLES:
        result.extend(get_items_by_source(source))
    return result


def get_item_by_name(name: str):
    for it in get_all_items():
        if it.get("name") == name:
            return it
    return None


# ---------- Монеты ----------
def normalize_coins(coins: dict) -> dict:
    total = sum(coins.get(k, 0) * COIN_TO_MM[k] for k in COIN_KEYS)
    return _mm_to_breakdown(total)


def _mm_to_breakdown(total_mm: int) -> dict:
    pm = total_mm // 1000; total_mm %= 1000
    zm = total_mm // 100; total_mm %= 100
    sm = total_mm // 10; mm = total_mm % 10
    return {"mm": mm, "sm": sm, "zm": zm, "pm": pm}


def format_coins(coins: dict) -> str:
    coins = normalize_coins(coins)
    parts = [f"{coins[k]} {COIN_SHORT[k]}" for k in ["pm", "zm", "sm", "mm"] if coins.get(k, 0)]
    return ", ".join(parts) if parts else "0 зм"


def format_price(price: dict) -> str:
    if not price:
        return "—"
    return f"{price.get('value', 0)} {price.get('currency', 'зм')}"


def apply_enchant_price(price: dict, enchantment: int) -> dict:
    """Возвращает новый price с учётом множителя зачарования."""
    if not price or enchantment == 0:
        return dict(price) if price else price
    mult = ENCHANT_MULT.get(enchantment, 0)
    base = price.get("value", 0)
    return {
        "value": int(round(base * (1 + mult / 100))),
        "currency": price.get("currency", "зм"),
    }


# ---------- Инвентарь ----------
def get_inventory(char) -> dict:
    inv = char.setdefault("inventory", {})
    inv.setdefault("items", [])
    inv.setdefault("coins", {"mm": 0, "sm": 0, "zm": 0, "pm": 0})
    for it in inv["items"]:
        it.setdefault("enchantment", 0)
        it.setdefault("equipped_slot", None)
    return inv


def get_inventory_weight(char) -> float:
    total = 0.0
    for entry in get_inventory(char)["items"]:
        w = entry.get("weight") or 0
        total += w * entry.get("quantity", 1)
    return total


def format_item_line(entry, idx: int) -> str:
    qty = entry.get("quantity", 1)
    qty_str = f" ×{qty}" if qty > 1 else ""
    eq = " 🟢" if entry.get("equipped_slot") else ""
    e = entry.get("enchantment", 0)
    en = f" +{e}" if e else ""
    return f"{idx + 1}. {entry.get('name', '?')}{en}{qty_str}{eq}"


# ---------- Изменение инвентаря ----------
def add_item_to_char(codename: str, item: dict, quantity: int = 1,
                     enchantment: int = 0) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    inv = get_inventory(char)
    # ищем тот же предмет с тем же зачарованием
    for entry in inv["items"]:
        if (entry.get("name") == item.get("name")
                and entry.get("source") == item.get("source")
                and int(entry.get("enchantment", 0)) == enchantment):
            entry["quantity"] = entry.get("quantity", 1) + quantity
            save_character(char)
            return char
    new_entry = dict(item)
    new_entry["quantity"] = quantity
    new_entry["enchantment"] = enchantment
    new_entry["equipped_slot"] = None
    if enchantment > 0:
        new_entry["price"] = apply_enchant_price(new_entry.get("price", {}), enchantment)
    inv["items"].append(new_entry)
    save_character(char)
    return char


def remove_item_from_char(codename: str, idx: int, quantity: int = None) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    inv = get_inventory(char)
    if idx < 0 or idx >= len(inv["items"]):
        raise ValueError("Предмет не найден.")
    if quantity is None:
        inv["items"].pop(idx)
    else:
        entry = inv["items"][idx]
        entry["quantity"] = entry.get("quantity", 1) - quantity
        if entry["quantity"] <= 0:
            inv["items"].pop(idx)
    save_character(char)
    return char


# ---------- Логика экипировки ----------
def _is_two_handed(item) -> bool:
    props = item.get("properties") or []
    return any("Двуручное" in str(p) for p in props)


def _equippable_slots(item) -> list:
    cat = item.get("category")
    if cat == "armor":
        return ["armor"]
    if cat == "shield":
        return ["melee_off", "ranged_off"]
    if cat == "weapon":
        sub = item.get("subcategory", "")
        if "melee" in sub:
            return ["melee_main", "melee_off"]
        if "ranged" in sub:
            return ["ranged_main", "ranged_off"]
        return ["melee_main", "melee_off"]
    return []


def can_equip_to_slot(item, slot: str) -> bool:
    if slot not in _equippable_slots(item):
        return False
    if slot in ("melee_off", "ranged_off"):
        if item.get("category") == "weapon" and _is_two_handed(item):
            return False
    return True


def equip_item(codename: str, idx: int, slot: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    inv = get_inventory(char)
    if idx < 0 or idx >= len(inv["items"]):
        raise ValueError("Предмет не найден.")
    if slot not in VALID_SLOTS:
        raise ValueError("Неверный слот.")
    item = inv["items"][idx]
    if not can_equip_to_slot(item, slot):
        raise ValueError("Этот предмет нельзя экипировать в этот слот.")

    # Снять текущий предмет из этого слота
    for other in inv["items"]:
        if other is not item and other.get("equipped_slot") == slot:
            other["equipped_slot"] = None

    # Если цепляем в off, а main двуручный — снять main
    if slot in ("melee_off", "ranged_off"):
        main_slot = "melee_main" if slot == "melee_off" else "ranged_main"
        for other in inv["items"]:
            if other is not item and other.get("equipped_slot") == main_slot and _is_two_handed(other):
                other["equipped_slot"] = None

    # Если цепляем двуручный в main — освободить off
    if slot in ("melee_main", "ranged_main") and _is_two_handed(item):
        off_slot = "melee_off" if slot == "melee_main" else "ranged_off"
        for other in inv["items"]:
            if other is not item and other.get("equipped_slot") == off_slot:
                other["equipped_slot"] = None

    item["equipped_slot"] = slot
    save_character(char)
    return char


def unequip_slot(codename: str, slot: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    inv = get_inventory(char)
    for it in inv["items"]:
        if it.get("equipped_slot") == slot:
            it["equipped_slot"] = None
            break
    save_character(char)
    return char


def change_quantity(codename: str, idx: int, delta: int) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    inv = get_inventory(char)
    if idx < 0 or idx >= len(inv["items"]):
        raise ValueError("Предмет не найден.")
    entry = inv["items"][idx]
    entry["quantity"] = max(1, entry.get("quantity", 1) + delta)
    save_character(char)
    return char


def change_coins(codename: str, currency: str, delta: int) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if currency not in COIN_KEYS:
        raise ValueError("Неизвестная валюта.")
    inv = get_inventory(char)
    coins = inv["coins"]
    total_mm = sum(coins.get(k, 0) * COIN_TO_MM[k] for k in COIN_KEYS)
    total_mm += delta * COIN_TO_MM[currency]
    if total_mm < 0:
        raise ValueError("Недостаточно монет.")
    inv["coins"] = _mm_to_breakdown(total_mm)
    save_character(char)
    return char


def add_custom_item(codename: str, name: str, category: str,
                    weight: float, price: dict, description: str,
                    enchantment: int = 0) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    inv = get_inventory(char)
    final_price = apply_enchant_price(price, enchantment)
    inv["items"].append({
        "name": name,
        "category": category,
        "source": "custom",
        "weight": weight,
        "price": final_price,
        "description": description,
        "enchantment": enchantment,
        "quantity": 1,
        "equipped_slot": None,
    })
    save_character(char)
    return char


# ============================================================
#  FSM и клавиатуры
# ============================================================
class CustomItem(StatesGroup):
    name = State()
    details = State()
    enchant = State()


def items_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Инвентарь персонажа", callback_data="items_char_list")],
        [InlineKeyboardButton(text="📚 Каталог предметов", callback_data="items_browse")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="items_help")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_start")],
    ])


def categories_kb(codename=None):
    rows = []
    for key, title in SOURCE_TITLES.items():
        if codename:
            cb = f"items_add_src:{codename}:{key}"
        else:
            cb = f"items_browse_src:{key}"
        rows.append([InlineKeyboardButton(text=title, callback_data=cb)])
    if codename:
        rows.append([InlineKeyboardButton(text="🔙 Назад",
                                          callback_data=f"items_char:{codename}")])
    else:
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="items_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inventory_kb(codename: str, items: list):
    rows = [
        [InlineKeyboardButton(text="➕ Добавить предмет",
                              callback_data=f"items_add_src_menu:{codename}")],
        [InlineKeyboardButton(text="✨ Создать свой предмет",
                              callback_data=f"items_custom:{codename}")],
        [InlineKeyboardButton(text="🪙 Монеты",
                              callback_data=f"items_coins:{codename}")],
        [InlineKeyboardButton(text="⚙️ Экипировка",
                              callback_data=f"iem:{codename}")],
    ]
    if items:
        rows.append([InlineKeyboardButton(text="✏️ Кол-во",
                                          callback_data=f"items_qty_menu:{codename}")])
        rows.append([InlineKeyboardButton(text="🗑 Удалить предмет",
                                          callback_data=f"items_del_menu:{codename}")])
    rows.append([InlineKeyboardButton(text="🔙 К персонажу",
                                      callback_data=f"view:{codename}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fmt_en(it) -> str:
    e = int(it.get("enchantment", 0) or 0)
    return f" +{e}" if e else ""


def _format_inventory(char) -> str:
    inv = get_inventory(char)
    items = inv.get("items", [])
    weight = sum((it.get("weight") or 0) * it.get("quantity", 1) for it in items)
    coins = format_coins(inv.get("coins", {}))

    def _slot_item(slot):
        for it in items:
            if it.get("equipped_slot") == slot:
                return it
        return None

    text = f"🎒 *Инвентарь: {char['name']}*\n\n"
    text += "📦 *Экипировано:*\n"
    a = _slot_item("armor")
    text += (f"  🛡 Доспех: *{a['name']}*{_fmt_en(a)}\n" if a
             else "  🛡 Доспех: —\n")
    mm_ = _slot_item("melee_main"); mo_ = _slot_item("melee_off")
    text += ("  ⚔️ Ближний: "
             + (f"*{mm_['name']}*{_fmt_en(mm_)}" if mm_ else "—")
             + " / "
             + (f"*{mo_['name']}*{_fmt_en(mo_)}" if mo_ else "—")
             + "\n")
    rm_ = _slot_item("ranged_main"); ro_ = _slot_item("ranged_off")
    text += ("  🏹 Дальний: "
             + (f"*{rm_['name']}*{_fmt_en(rm_)}" if rm_ else "—")
             + " / "
             + (f"*{ro_['name']}*{_fmt_en(ro_)}" if ro_ else "—")
             + "\n\n")

    if not items:
        text += "_Пусто._\n\n"
    else:
        text += "📋 *Предметы:*\n"
        for i, entry in enumerate(items):
            cat = entry.get("category", "other")
            slot = entry.get("equipped_slot")
            eq = " 🟢" if slot else ""
            qty = entry.get("quantity", 1)
            qty_str = f" ×{qty}" if qty > 1 else ""
            w = entry.get("weight") or 0
            weight_str = f", {w * qty:g} фнт" if w else ""
            text += f"{i + 1}. *{entry.get('name', '?')}*{_fmt_en(entry)}{qty_str}{eq}\n"
            text += f"   _{cat}{weight_str}_\n"
        text += "\n"
    text += f"⚖️ Всего весит: *{weight:.2f} фнт*\n"
    text += f"💰 Монеты: *{coins}*"
    return text


def _item_details_text(item: dict, char=None) -> str:
    cat = item.get("category", "other")
    ench = int(item.get("enchantment", 0) or 0)
    text = f"📦 *{item.get('name', '?')}*\n"
    text += f"_{cat}_\n\n"
    if ench:
        text += f"✨ Зачарование: +{ench}\n"
    if item.get("damage"):
        dmg_str = item["damage"]
        if ench:
            dmg_str += f" +{ench}"
        text += f"🎯 Урон: {dmg_str}\n"
    if item.get("properties"):
        text += f"🔧 Свойства: {', '.join(item['properties'])}\n"
    if item.get("ac_base"):
        ac_str = item["ac_base"] + ench
        text += f"🛡 КД база: {ac_str}\n"
        text += f"   Ловкость: {item.get('ac_dex', 'full')}\n"
    if item.get("strength_req"):
        text += f"💪 Требует Силы: {item['strength_req']}\n"
    if item.get("stealth_disadvantage"):
        text += "🚫 Помеха на Скрытность\n"
    if item.get("ac_bonus"):
        bonus_str = item["ac_bonus"] + ench
        text += f"🛡 КД бонус: +{bonus_str}\n"
    w = item.get("weight")
    if w is not None:
        text += f"⚖️ Вес: {w} фнт\n"
    if item.get("price"):
        text += f"💰 Цена: {format_price(item['price'])}\n"
    if item.get("description"):
        text += f"\n{item['description']}"

    if (char is not None and item.get("category") == "weapon"
            and not has_weapon_proficiency(char, item)):
        text += "\n\n⚠️ _У персонажа нет владения этим оружием._"
    return text


# ============================================================
#  Handlers
# ============================================================
@router.message(Command("items"))
async def cmd_items(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Раздел предметов:", reply_markup=items_menu())


@router.callback_query(F.data == "main_items")
async def cb_main_items(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _safe_edit(callback.message, "Раздел предметов:", reply_markup=items_menu())
    await callback.answer()


@router.callback_query(F.data == "items_menu")
async def cb_items_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _safe_edit(callback.message, "Раздел предметов:", reply_markup=items_menu())
    await callback.answer()


@router.callback_query(F.data == "items_help")
async def items_help(callback: CallbackQuery):
    text = (
        "🎒 *Предметы и инвентарь*\n\n"
        "• Выберите персонажа, чтобы открыть его инвентарь.\n"
        "• «Добавить предмет» — из каталога (оружие, доспехи, инструменты, квестовые, снаряжение).\n"
        "• «Создать свой предмет» — добавьте уникальный.\n"
        "• «⚙️ Экипировка» — распределение по слотам:\n"
        "   🛡 `armor` — доспех,\n"
        "   ⚔️ `melee_main` / `melee_off` — набор ближнего боя,\n"
        "   🏹 `ranged_main` / `ranged_off` — набор дальнего боя.\n"
        "   Оружие, которым персонаж не владеет, помечается «(Нет навыка)».\n"
        "   Двуручное оружие занимает основную руку, вторая освобождается.\n"
        "   Можно одновременно носить оба набора.\n"
        "• *Зачарование* — при добавлении предмета можно выбрать +0…+5.\n"
        "   Урон/КД увеличивается на значение зачарования,\n"
        "   цена — на +20%/+45%/+100%/+175%/+250%.\n"
        "   Зачарование не редактируется.\n"
        "• «Кол-во» — изменить количество.\n"
        "• «Монеты» — управление, конвертация автоматическая:\n"
        "   10 мм = 1 см, 10 см = 1 зм, 10 зм = 1 пм.\n\n"
        "⚖️ Суммарный вес показан в инвентаре.\n"
        "🧮 Все предметы имеют вес, цену и описание."
    )
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=items_menu())
    await callback.answer()


# ---------- Список персонажей для инвентаря ----------
@router.callback_query(F.data == "items_char_list")
async def items_char_list(callback: CallbackQuery):
    from scripts.characters import list_characters
    chars = list_characters()
    if not chars:
        await _safe_edit(
            callback.message,
            "Сначала создайте персонажа в разделе /characters.",
            reply_markup=items_menu())
        await callback.answer()
        return
    kb = []
    for c in chars:
        classes = ", ".join(f"{k} {v}" for k, v in c["classes"].items())
        kb.append([InlineKeyboardButton(
            text=f"{c['name']} — {classes}",
            callback_data=f"items_char:{c['codename']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="items_menu")])
    await _safe_edit(
        callback.message,
        "К какому персонажу?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("items_char:"))
async def items_char(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await _safe_edit(callback.message, "Персонаж не найден.", reply_markup=items_menu())
        await callback.answer()
        return
    inv = get_inventory(char)
    await _safe_edit(
        callback.message,
        _format_inventory(char),
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer()


# ---------- Экипировка ----------
@router.callback_query(F.data.startswith("iem:"))
async def items_equip_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    inv = get_inventory(char)
    items = inv["items"]

    def _slot_item(s):
        for it in items:
            if it.get("equipped_slot") == s:
                return it
        return None

    lines = ["⚙️ *Экипировка*", ""]
    for slot_key, title in SLOT_TITLES.items():
        cur = _slot_item(slot_key)
        val = f"*{cur['name']}*{_fmt_en(cur)}" if cur else "—"
        lines.append(f"{title}: {val}")
    text = "\n".join(lines) + "\n\nНажмите на слот для изменения:"

    kb = []
    for slot_key, title in SLOT_TITLES.items():
        kb.append([InlineKeyboardButton(
            text=title, callback_data=f"ies:{codename}:{SLOT_INDEX[slot_key]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"items_char:{codename}")])
    await _safe_edit(callback.message, text, parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("ies:"))
async def items_equip_slot_select(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, slot_idx = parts[1], parts[2]
    slot = SLOT_FROM_INDEX.get(slot_idx)
    if not slot:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    inv = get_inventory(char)
    items = inv["items"]

    available = []
    for i, entry in enumerate(items):
        if entry.get("equipped_slot") == slot:
            continue
        if not can_equip_to_slot(entry, slot):
            continue
        available.append((i, entry))

    current_item = None
    for it in items:
        if it.get("equipped_slot") == slot:
            current_item = it
            break

    if not available and not current_item:
        await callback.answer("Нет подходящих предметов", show_alert=True)
        return

    text = f"*{SLOT_TITLES[slot]}*\n\n"
    if current_item:
        text += f"Сейчас: *{current_item['name']}*{_fmt_en(current_item)}\n\n"
    text += "Выберите предмет:"

    kb = []
    for i, entry in available:
        label = entry["name"] + _fmt_en(entry)
        if (entry.get("category") == "weapon"
                and not has_weapon_proficiency(char, entry)):
            label += " (Нет навыка)"
        kb.append([InlineKeyboardButton(
            text=label, callback_data=f"iea:{codename}:{i}:{slot_idx}")])

    if current_item:
        kb.append([InlineKeyboardButton(
            text="❌ Снять", callback_data=f"iec:{codename}:{slot_idx}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"iem:{codename}")])

    await _safe_edit(callback.message, text, parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("iea:"))
async def items_equip_apply(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename, idx_s, slot_idx = parts[1], parts[2], parts[3]
    try:
        idx = int(idx_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    slot = SLOT_FROM_INDEX.get(slot_idx)
    if not slot:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = equip_item(codename, idx, slot)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    await _safe_edit(callback.message, _format_inventory(char),
                     parse_mode="Markdown",
                     reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer("Экипировано")


@router.callback_query(F.data.startswith("iec:"))
async def items_equip_clear(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, slot_idx = parts[1], parts[2]
    slot = SLOT_FROM_INDEX.get(slot_idx)
    if not slot:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = unequip_slot(codename, slot)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    await _safe_edit(callback.message, _format_inventory(char),
                     parse_mode="Markdown",
                     reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer("Снято")


# ---------- Каталог ----------
@router.callback_query(F.data == "items_browse")
async def items_browse(callback: CallbackQuery):
    await _safe_edit(
        callback.message,
        "📚 *Каталог предметов*\n\nВыберите категорию:",
        parse_mode="Markdown",
        reply_markup=categories_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("items_browse_src:"))
async def items_browse_src(callback: CallbackQuery):
    source = callback.data.split(":", 1)[1]
    items = get_items_by_source(source)
    if not items:
        await callback.answer("Категория пуста", show_alert=True)
        return
    text = f"📚 *{SOURCE_TITLES.get(source, source)}*\n\n"
    for it in items:
        w = it.get("weight") or 0
        text += f"• *{it['name']}* — {format_price(it.get('price'))}, {w} фнт\n"
    await _safe_edit(
        callback.message,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К категориям", callback_data="items_browse")]]))
    await callback.answer()


# ---------- Добавление предмета ----------
@router.callback_query(F.data.startswith("items_add_src_menu:"))
async def items_add_src_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    await _safe_edit(
        callback.message,
        "➕ *Добавить предмет*\n\nВыберите категорию:",
        parse_mode="Markdown",
        reply_markup=categories_kb(codename=codename))
    await callback.answer()


@router.callback_query(F.data.startswith("items_add_src:"))
async def items_add_src(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, source = parts[1], parts[2]
    items = get_items_by_source(source)
    if not items:
        await callback.answer("Пусто", show_alert=True)
        return
    kb = []
    for i, it in enumerate(items):
        kb.append([InlineKeyboardButton(
            text=it["name"], callback_data=f"iav:{codename}:{source}:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"items_add_src_menu:{codename}")])
    await _safe_edit(
        callback.message,
        f"➕ *{SOURCE_TITLES.get(source, source)}*\n\nВыберите предмет:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("iav:"))
async def items_add_view(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename, source, idx_s = parts[1], parts[2], parts[3]
    try:
        idx = int(idx_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    items = get_items_by_source(source)
    if idx < 0 or idx >= len(items):
        await callback.answer("Не найдено", show_alert=True)
        return
    item = items[idx]
    char = load_character(codename)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить (1)",
                              callback_data=f"iaq:{codename}:{source}:{idx}:1")],
        [InlineKeyboardButton(text="➕ Добавить (5)",
                              callback_data=f"iaq:{codename}:{source}:{idx}:5")],
        [InlineKeyboardButton(text="🔙 Назад",
                              callback_data=f"items_add_src:{codename}:{source}")],
    ])
    await _safe_edit(callback.message, _item_details_text(item, char),
                     parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("iaq:"))
async def items_add_qty(callback: CallbackQuery):
    parts = callback.data.split(":", 4)
    if len(parts) != 5:
        await callback.answer()
        return
    codename, source, idx_s, qty_s = parts[1], parts[2], parts[3], parts[4]
    try:
        idx = int(idx_s); qty = int(qty_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    items = get_items_by_source(source)
    if idx < 0 or idx >= len(items):
        await callback.answer("Не найдено", show_alert=True)
        return
    item = items[idx]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return

    if item.get("category") in EQUIPPABLE_CATEGORIES:
        kb = []
        for ench in [0, 1, 2, 3, 4, 5]:
            label = ("Без зачарования" if ench == 0
                     else f"+{ench} (+{ENCHANT_MULT[ench]}%)")
            kb.append([InlineKeyboardButton(
                text=label,
                callback_data=f"iaf:{codename}:{source}:{idx}:{qty}:{ench}")])
        kb.append([InlineKeyboardButton(
            text="🔙 Отмена",
            callback_data=f"iav:{codename}:{source}:{idx}")])
        text = (f"✨ *Зачарование для {item['name']}*\n\n"
                f"Количество: ×{qty}\n\n"
                f"Выберите уровень зачарования.\n"
                f"_Зачарование постоянно и не может быть изменено._")
        await _safe_edit(callback.message, text, parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        await callback.answer()
        return

    try:
        char = add_item_to_char(codename, item, qty, enchantment=0)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    await _safe_edit(
        callback.message,
        f"✅ Добавлено: *{item['name']}* ×{qty}\n\n{_format_inventory(char)}",
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer("Добавлено")


@router.callback_query(F.data.startswith("iaf:"))
async def items_add_final(callback: CallbackQuery):
    parts = callback.data.split(":", 5)
    if len(parts) != 6:
        await callback.answer()
        return
    codename, source, idx_s, qty_s, ench_s = (
        parts[1], parts[2], parts[3], parts[4], parts[5])
    try:
        idx = int(idx_s); qty = int(qty_s); ench = int(ench_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    if ench not in ENCHANT_MULT:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    items = get_items_by_source(source)
    if idx < 0 or idx >= len(items):
        await callback.answer("Не найдено", show_alert=True)
        return
    item = items[idx]
    try:
        char = add_item_to_char(codename, item, qty, enchantment=ench)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    ench_str = f" +{ench}" if ench else ""
    await _safe_edit(
        callback.message,
        f"✅ Добавлено: *{item['name']}*{ench_str} ×{qty}\n\n{_format_inventory(char)}",
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer("Добавлено")


# ---------- Кол-во ----------
@router.callback_query(F.data.startswith("items_qty_menu:"))
async def items_qty_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    inv = get_inventory(char)
    kb = []
    for i, entry in enumerate(inv["items"]):
        label = entry["name"] + _fmt_en(entry) + f" (×{entry.get('quantity', 1)})"
        kb.append([InlineKeyboardButton(
            text=label,
            callback_data=f"items_qty_pick:{codename}:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"items_char:{codename}")])
    await _safe_edit(
        callback.message,
        "✏️ *Изменить количество*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("items_qty_pick:"))
async def items_qty_pick(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        idx = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    inv = get_inventory(char)
    if idx < 0 or idx >= len(inv["items"]):
        await callback.answer("Не найдено", show_alert=True)
        return
    entry = inv["items"][idx]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➖1", callback_data=f"items_qty_delta:{codename}:{idx}:-1"),
         InlineKeyboardButton(text=f"×{entry.get('quantity', 1)}", callback_data="noop"),
         InlineKeyboardButton(text="➕1", callback_data=f"items_qty_delta:{codename}:{idx}:1")],
        [InlineKeyboardButton(text="➕5", callback_data=f"items_qty_delta:{codename}:{idx}:5")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"items_qty_menu:{codename}")],
    ])
    await _safe_edit(
        callback.message,
        f"✏️ *{entry['name']}*\nТекущее количество: {entry.get('quantity', 1)}",
        parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("items_qty_delta:"))
async def items_qty_delta(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]
    try:
        idx = int(parts[2]); delta = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = change_quantity(codename, idx, delta)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    await _safe_edit(
        callback.message,
        _format_inventory(char),
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer()


# ---------- Удаление ----------
@router.callback_query(F.data.startswith("items_del_menu:"))
async def items_del_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    inv = get_inventory(char)
    kb = []
    for i, entry in enumerate(inv["items"]):
        label = f"🗑 {entry['name']}{_fmt_en(entry)} (×{entry.get('quantity', 1)})"
        kb.append([InlineKeyboardButton(
            text=label, callback_data=f"items_del:{codename}:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"items_char:{codename}")])
    await _safe_edit(
        callback.message,
        "🗑 *Удалить предмет*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("items_del:"))
async def items_del(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        idx = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = remove_item_from_char(codename, idx)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    await _safe_edit(
        callback.message,
        _format_inventory(char),
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer("Удалено")


# ---------- Монеты ----------
def _coins_kb(codename: str) -> InlineKeyboardMarkup:
    kb = []
    for k in COIN_KEYS:
        kb.append([
            InlineKeyboardButton(text=f"➖1 {COIN_SHORT[k]}",
                                 callback_data=f"items_coin_chg:{codename}:{k}:-1"),
            InlineKeyboardButton(text=f"➖10 {COIN_SHORT[k]}",
                                 callback_data=f"items_coin_chg:{codename}:{k}:-10"),
        ])
        kb.append([
            InlineKeyboardButton(text=f"➕1 {COIN_SHORT[k]}",
                                 callback_data=f"items_coin_chg:{codename}:{k}:1"),
            InlineKeyboardButton(text=f"➕10 {COIN_SHORT[k]}",
                                 callback_data=f"items_coin_chg:{codename}:{k}:10"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"items_char:{codename}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("items_coins:"))
async def items_coins(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    inv = get_inventory(char)
    coins = format_coins(inv.get("coins", {}))
    await _safe_edit(
        callback.message,
        f"🪙 *Монеты {char['name']}*\n\nСейчас: *{coins}*\n\n"
        f"Автоконвертация: 10 мм = 1 см, 10 см = 1 зм, 10 зм = 1 пм.",
        parse_mode="Markdown",
        reply_markup=_coins_kb(codename))
    await callback.answer()


@router.callback_query(F.data.startswith("items_coin_chg:"))
async def items_coin_chg(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]; currency = parts[2]
    try:
        delta = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = change_coins(codename, currency, delta)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    inv = get_inventory(char)
    coins = format_coins(inv.get("coins", {}))
    await _safe_edit(
        callback.message,
        f"🪙 *Монеты {char['name']}*\n\nСейчас: *{coins}*",
        parse_mode="Markdown",
        reply_markup=_coins_kb(codename))
    await callback.answer()


# ---------- Свой предмет ----------
@router.callback_query(F.data.startswith("items_custom:"))
async def items_custom(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(custom_codename=codename)
    await state.set_state(CustomItem.name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"items_char:{codename}")]])
    await _safe_edit(
        callback.message,
        "✨ *Создать свой предмет*\n\nВведите название предмета:",
        parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.message(CustomItem.name)
async def custom_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Ещё раз:")
        return
    await state.update_data(custom_name=name)
    await state.set_state(CustomItem.details)
    await message.answer(
        "Введите данные в формате:\n"
        "`категория | вес | цена | описание`\n\n"
        "Категории: `weapon`, `armor`, `shield`, `tool`, `quest`, `other`.\n"
        "Цена: число и валюта (`мм`/`см`/`зм`/`пм`), например `15 зм`.\n\n"
        "Пример: `weapon | 3 | 15 зм | Мой любимый меч`",
        parse_mode="Markdown")


@router.message(CustomItem.details)
async def custom_details(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await message.answer(
            "Формат: `категория | вес | цена | описание`\nПопробуйте ещё раз.",
            parse_mode="Markdown")
        return
    category = parts[0].lower()
    if category not in ("weapon", "armor", "shield", "tool", "quest", "other"):
        await message.answer("Неизвестная категория. Попробуйте ещё раз.")
        return
    try:
        weight = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("Вес должен быть числом. Попробуйте ещё раз.")
        return
    price_parts = parts[2].split()
    try:
        value = int(float(price_parts[0]))
        currency = price_parts[1] if len(price_parts) > 1 else "зм"
        if currency not in COIN_KEYS and currency not in ("мм", "см", "зм", "пм"):
            currency = "зм"
    except (ValueError, IndexError):
        await message.answer("Цена должна быть вида `15 зм`. Попробуйте ещё раз.")
        return
    description = parts[3] if len(parts) > 3 else ""

    await state.update_data(
        custom_category=category,
        custom_weight=weight,
        custom_price_value=value,
        custom_price_currency=currency,
        custom_description=description,
    )

    data = await state.get_data()
    name = data.get("custom_name", "?")

    if category in EQUIPPABLE_CATEGORIES:
        await state.set_state(CustomItem.enchant)
        kb_rows = []
        for ench in [0, 1, 2, 3, 4, 5]:
            label = ("Без зачарования" if ench == 0
                     else f"+{ench} (+{ENCHANT_MULT[ench]}%)")
            kb_rows.append([InlineKeyboardButton(
                text=label, callback_data=f"custom_enchant:{ench}")])
        kb_rows.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="items_menu")])
        await message.answer(
            f"✨ *Зачарование для {name}*\n\n"
            f"Выберите уровень зачарования.\n"
            f"_Зачарование постоянно и не может быть изменено._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        return

    # Не экипируемое — добавляем сразу
    codename = data.get("custom_codename")
    try:
        char = add_custom_item(
            codename, name, category, weight,
            {"value": value, "currency": currency},
            description, enchantment=0)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        return
    await state.clear()
    inv = get_inventory(char)
    await message.answer(
        f"✅ Создан предмет *{name}*.\n\n{_format_inventory(char)}",
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))


@router.callback_query(F.data.startswith("custom_enchant:"), CustomItem.enchant)
async def custom_enchant(callback: CallbackQuery, state: FSMContext):
    try:
        ench = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    if ench not in ENCHANT_MULT:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    data = await state.get_data()
    codename = data.get("custom_codename")
    name = data.get("custom_name")
    category = data.get("custom_category")
    weight = data.get("custom_weight")
    price_value = data.get("custom_price_value")
    price_currency = data.get("custom_price_currency", "зм")
    description = data.get("custom_description", "")
    if not codename or not name or not category:
        await callback.answer("Сессия истекла, начните заново", show_alert=True)
        await state.clear()
        return
    try:
        char = add_custom_item(
            codename, name, category, weight,
            {"value": price_value, "currency": price_currency},
            description, enchantment=ench)
    except ValueError as e:
        await _safe_edit(callback.message, f"Ошибка: {e}", reply_markup=items_menu())
        await state.clear()
        await callback.answer()
        return
    await state.clear()
    inv = get_inventory(char)
    ench_str = f" +{ench}" if ench else ""
    await _safe_edit(
        callback.message,
        f"✅ Создан предмет *{name}*{ench_str}.\n\n{_format_inventory(char)}",
        parse_mode="Markdown",
        reply_markup=inventory_kb(codename, inv["items"]))
    await callback.answer("Создан")