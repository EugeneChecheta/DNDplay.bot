"""Сессия: лагерь, торговля, битва (с монстрами), действия вне боя."""
import json
import math
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
    load_character, list_characters,
    _save_character as save_character,
    get_current,
    damage_character, heal_character, add_temp_hp,
    spend_resource, restore_resource,
    spend_spell_slot, restore_spell_slot,
    long_rest_character,
    get_xp_progress, add_xp,
)
from scripts.items import (
    COIN_TO_MM, COIN_SHORT, COIN_KEYS,
    _mm_to_breakdown, format_coins,
    get_inventory,
)
from scripts.enemies import (
    load_enemies, get_enemy,
    format_enemy_header, format_enemy_details,
    load_battle,
    add_enemy_to_battle, remove_enemy_from_battle, kill_enemy_from_battle,
    damage_battle_enemy, heal_battle_enemy, set_battle_enemy_temp_hp,
)

router = Router(name="session")

BASE_DIR = Path(__file__).resolve().parent.parent
CAMP_FILE = BASE_DIR / "camp" / "camp.json"
CAMP_FILE.parent.mkdir(parents=True, exist_ok=True)

REQUIRED_SATIETY = 40


async def _safe_edit(message: Message, text: str, **kwargs) -> None:
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _extract_char_codename(data: str, prefix: str) -> str | None:
    if not data.startswith(prefix + ":"):
        return None
    rest = data[len(prefix) + 1:]
    if rest.startswith("char:"):
        return rest[5:]
    return rest


# ============================================================
#  Лагерь
# ============================================================
def load_camp() -> dict:
    if not CAMP_FILE.exists():
        camp = {"chest": {"items": [], "coins": {"mm": 0, "sm": 0, "zm": 0, "pm": 0}}}
        save_camp(camp)
        return camp
    with open(CAMP_FILE, "r", encoding="utf-8") as f:
        camp = json.load(f)
    camp.setdefault("chest", {})
    camp["chest"].setdefault("items", [])
    camp["chest"].setdefault("coins", {"mm": 0, "sm": 0, "zm": 0, "pm": 0})
    return camp


def save_camp(camp: dict) -> None:
    with open(CAMP_FILE, "w", encoding="utf-8") as f:
        json.dump(camp, f, ensure_ascii=False, indent=2)


def camp_total_satiety(camp: dict) -> int:
    total = 0
    for it in camp["chest"]["items"]:
        sat = int(it.get("satiety", 0) or 0)
        total += sat * it.get("quantity", 1)
    return total


def consume_satiety(camp: dict, amount: int) -> int:
    remaining = amount
    for it in camp["chest"]["items"]:
        if remaining <= 0:
            break
        sat = int(it.get("satiety", 0) or 0)
        if sat <= 0:
            continue
        qty = it.get("quantity", 1)
        total_sat = sat * qty
        if total_sat <= remaining:
            remaining -= total_sat
            it["quantity"] = 0
        else:
            need_items = min(math.ceil(remaining / sat), qty)
            it["quantity"] = qty - need_items
            remaining -= need_items * sat
    camp["chest"]["items"] = [
        i for i in camp["chest"]["items"] if i.get("quantity", 1) > 0
    ]
    return amount - remaining


# ============================================================
#  Контейнеры
# ============================================================
def _total_mm(coins: dict) -> int:
    return sum(int(coins.get(k, 0) or 0) * COIN_TO_MM[k] for k in COIN_KEYS)


def _breakdown(total_mm: int) -> dict:
    return _mm_to_breakdown(max(0, total_mm))


def _get_container(type_: str, id_: str) -> dict:
    if type_ == "char":
        char = load_character(id_)
        if not char:
            raise ValueError("Персонаж не найден.")
        inv = get_inventory(char)
        return {
            "type": "char",
            "id": id_,
            "items": inv["items"],
            "coins": inv["coins"],
            "name": char["name"],
            "save": lambda: save_character(char),
        }
    camp = load_camp()
    return {
        "type": "camp",
        "id": "",
        "items": camp["chest"]["items"],
        "coins": camp["chest"]["coins"],
        "name": "🏕 Лагерь",
        "save": lambda: save_camp(camp),
    }


def transfer_coins(coins_from: dict, coins_to: dict, currency: str, amount: int) -> None:
    if amount <= 0:
        raise ValueError("Количество должно быть положительным.")
    if currency not in COIN_KEYS:
        raise ValueError("Неизвестная валюта.")
    need_mm = amount * COIN_TO_MM[currency]
    from_total = _total_mm(coins_from)
    if from_total < need_mm:
        raise ValueError(
            f"Недостаточно монет: нужно {amount} {COIN_SHORT[currency]}, "
            f"у источника есть только {format_coins(coins_from)}."
        )
    new_from = _breakdown(from_total - need_mm)
    coins_from.clear()
    coins_from.update(new_from)
    new_to = _breakdown(_total_mm(coins_to) + need_mm)
    coins_to.clear()
    coins_to.update(new_to)


def transfer_item(items_from: list, items_to: list, idx: int, quantity: int) -> tuple:
    if idx < 0 or idx >= len(items_from):
        raise ValueError("Предмет не найден.")
    src = items_from[idx]
    qty_available = int(src.get("quantity", 1))
    if quantity <= 0:
        raise ValueError("Количество должно быть положительным.")
    if quantity > qty_available:
        raise ValueError(f"Недостаточно предметов (есть {qty_available}).")
    src["equipped_slot"] = None
    for dst in items_to:
        if (dst.get("name") == src.get("name")
                and dst.get("source") == src.get("source")
                and int(dst.get("enchantment", 0) or 0) == int(src.get("enchantment", 0) or 0)):
            dst["quantity"] = int(dst.get("quantity", 1)) + quantity
            break
    else:
        new_entry = dict(src)
        new_entry["quantity"] = quantity
        new_entry["equipped_slot"] = None
        items_to.append(new_entry)
    src["quantity"] = qty_available - quantity
    if src["quantity"] <= 0:
        items_from.pop(idx)
    return src["name"], quantity


# ============================================================
#  FSM
# ============================================================
class Transfer(StatesGroup):
    amount = State()
    item_qty = State()


class Battle(StatesGroup):
    damage = State()
    heal = State()
    temp_hp = State()


class EnemyBattle(StatesGroup):
    damage = State()
    heal = State()
    temp_hp = State()


class GiveXP(StatesGroup):
    amount = State()


# ============================================================
#  Клавиатуры
# ============================================================
def session_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏕 Лагерь", callback_data="sess_camp")],
        [InlineKeyboardButton(text="⚔️ Битва", callback_data="sess_battle")],
        [InlineKeyboardButton(text="🛠 Вне боя", callback_data="sess_ooc")],
        [InlineKeyboardButton(text="💱 Передача", callback_data="sess_transfer")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_start")],
    ])


def camp_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Сундук лагеря", callback_data="sess_chest_view")],
        [InlineKeyboardButton(text="🍖 Сытость", callback_data="sess_satiety")],
        [InlineKeyboardButton(text="😴 Долгий отдых (за еду)", callback_data="sess_rest_long")],
        [InlineKeyboardButton(text="🎬 Сюжетный долгий отдых (бесплатно)", callback_data="sess_rest_long_free")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sess_menu")],
    ])


def chars_list_kb(prefix: str, include_camp: bool = False,
                  exclude_codename: str = None, back_cb: str = "sess_menu"):
    chars = list_characters()
    kb = []
    for c in chars:
        if exclude_codename and c["codename"] == exclude_codename:
            continue
        kb.append([InlineKeyboardButton(
            text=c["name"],
            callback_data=f"{prefix}:char:{c['codename']}")])
    if include_camp:
        kb.append([InlineKeyboardButton(
            text="🏕 Лагерь", callback_data=f"{prefix}:camp")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ============================================================
#  Вход в раздел
# ============================================================
@router.message(Command("session"))
async def cmd_session(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏕 Раздел сессии:", reply_markup=session_menu())


@router.callback_query(F.data == "main_session")
async def cb_main_session(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _safe_edit(callback.message, "🏕 Раздел сессии:", reply_markup=session_menu())
    await callback.answer()


@router.callback_query(F.data == "sess_menu")
async def cb_sess_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _safe_edit(callback.message, "🏕 Раздел сессии:", reply_markup=session_menu())
    await callback.answer()


# ============================================================
#  Лагерь
# ============================================================
@router.callback_query(F.data == "sess_camp")
async def cb_camp(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    camp = load_camp()
    sat = camp_total_satiety(camp)
    await _safe_edit(
        callback.message,
        f"🏕 *Лагерь*\n\n"
        f"🍖 Сытость в сундуке: *{sat}* / {REQUIRED_SATIETY}",
        parse_mode="Markdown",
        reply_markup=camp_menu())
    await callback.answer()


@router.callback_query(F.data == "sess_chest_view")
async def cb_chest_view(callback: CallbackQuery):
    camp = load_camp()
    chest = camp["chest"]
    items = chest["items"]
    coins_str = format_coins(chest["coins"])
    sat = camp_total_satiety(camp)

    text = "📦 *Сундук лагеря*\n\n"
    if not items:
        text += "_Пусто._\n\n"
    else:
        for i, it in enumerate(items):
            qty = int(it.get("quantity", 1))
            qty_str = f" ×{qty}" if qty > 1 else ""
            s = int(it.get("satiety", 0) or 0)
            s_str = f" (сытость: {s * qty})" if s else ""
            text += f"{i + 1}. {it.get('name', '?')}{qty_str}{s_str}\n"
        text += "\n"
    text += f"🍖 Сытость: *{sat}* / {REQUIRED_SATIETY}\n"
    text += f"💰 Монеты: *{coins_str}*"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sess_camp")]])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "sess_satiety")
async def cb_satiety(callback: CallbackQuery):
    camp = load_camp()
    sat = camp_total_satiety(camp)
    need = max(0, REQUIRED_SATIETY - sat)
    items = camp["chest"]["items"]
    food_lines = []
    for it in items:
        s = int(it.get("satiety", 0) or 0)
        if s <= 0:
            continue
        qty = int(it.get("quantity", 1))
        food_lines.append(f"• {it.get('name')} ×{qty} — {s * qty} сытости")
    text = (
        f"🍖 *Сытость лагеря*\n\n"
        f"Собрано: *{sat}* / {REQUIRED_SATIETY}\n"
    )
    if need > 0:
        text += f"Не хватает: *{need}*\n"
    else:
        text += "✅ Можно провести долгий отдых.\n"
    if food_lines:
        text += "\n*Еда в сундуке:*\n" + "\n".join(food_lines)
    else:
        text += "\n_Еды в сундуке нет._"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sess_camp")]])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "sess_rest_long")
async def cb_rest_long(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    camp = load_camp()
    sat = camp_total_satiety(camp)
    if sat < REQUIRED_SATIETY:
        await callback.answer(
            f"Недостаточно еды в сундуке лагеря: {sat}/{REQUIRED_SATIETY}",
            show_alert=True)
        return
    chars = list_characters()
    if not chars:
        await callback.answer("Нет персонажей для отдыха.", show_alert=True)
        return
    consumed = consume_satiety(camp, REQUIRED_SATIETY)
    save_camp(camp)
    rest_lines = []
    for c in chars:
        try:
            char = long_rest_character(c["codename"])
            snap = get_current(char)
            rest_lines.append(f"• {char['name']}: ❤️ {snap['hp']}/{snap['hp']}, "
                              f"🔮 ячейки полны, ⚡ ресурсы полны")
        except Exception as e:
            rest_lines.append(f"• {c['name']}: ошибка — {e}")
    text = (
        f"😴 *Долгий отдых завершён!*\n\n"
        f"Израсходовано {consumed} сытости.\n"
        f"Осталось в сундуке: *{camp_total_satiety(camp)}*.\n\n"
        f"*Восстановлены персонажи:*\n" + "\n".join(rest_lines)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏕 В лагерь", callback_data="sess_camp")]])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "sess_rest_long_free")
async def cb_rest_long_free(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    chars = list_characters()
    if not chars:
        await callback.answer("Нет персонажей для отдыха.", show_alert=True)
        return
    rest_lines = []
    for c in chars:
        try:
            char = long_rest_character(c["codename"])
            snap = get_current(char)
            rest_lines.append(f"• {char['name']}: ❤️ {snap['hp']}/{snap['hp']}, "
                              f"🔮 ячейки полны, ⚡ ресурсы полны")
        except Exception as e:
            rest_lines.append(f"• {c['name']}: ошибка — {e}")
    text = (
        f"🎬 *Сюжетный долгий отдых завершён!*\n\n"
        f"Еда не потрачена.\n\n"
        f"*Восстановлены персонажи:*\n" + "\n".join(rest_lines)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏕 В лагерь", callback_data="sess_camp")]])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


# ============================================================
#  Битва
# ============================================================
async def _render_battle_menu(callback: CallbackQuery):
    battle = load_battle()
    enemies = battle.get("enemies", [])

    text = "⚔️ *Битва*\n\n"
    if enemies:
        text += "*Активные противники:*\n"
        for i, e in enumerate(enemies):
            cur = int(e.get("current_hp", 0))
            mx = int(e.get("max_hp", 0))
            tmp = int(e.get("temp_hp", 0) or 0)
            marker = "💀" if cur <= 0 else "👹"
            tmp_str = f" (+{tmp} вр)" if tmp > 0 else ""
            text += f"{i + 1}. {marker} {e['name']} — {cur}/{mx}{tmp_str}\n"
        text += "\n"
    else:
        text += "_Противников нет._\n\n"
    text += "Выберите действие:"

    kb_rows = []
    if enemies:
        kb_rows.append([InlineKeyboardButton(
            text=f"👹 Противники ({len(enemies)})",
            callback_data="sess_battle_enemies")])
    kb_rows.append([InlineKeyboardButton(
        text="👤 Персонажи",
        callback_data="sess_battle_chars")])
    kb_rows.append([InlineKeyboardButton(
        text="➕ Добавить противника",
        callback_data="sess_battle_add")])
    kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="sess_menu")])

    await _safe_edit(callback.message, text, parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data == "sess_battle")
async def cb_battle(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _render_battle_menu(callback)
    await callback.answer()


@router.callback_query(F.data == "sess_battle_chars")
async def cb_battle_chars(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = chars_list_kb("sess_battle_char", back_cb="sess_battle")
    await _safe_edit(callback.message, "⚔️ Выберите персонажа:",
                     reply_markup=kb)
    await callback.answer()


def _battle_card_text(char):
    snap = get_current(char)
    cur_hp = snap.get("current_hp", snap["hp"])
    max_hp = snap["hp"]
    temp = int(snap.get("temp_hp", 0) or 0)
    slots = snap.get("spell_slots", {})
    slot_parts = []
    for lvl in sorted(int(k) for k in slots.keys()):
        d = slots[str(lvl)]
        if d.get("max", 0) > 0:
            slot_parts.append(f"{lvl}ур {d.get('current', d['max'])}/{d['max']}")
    resources = snap.get("resources", {})
    res_parts = []
    for name, r in resources.items():
        if r.get("max", 0) > 0:
            res_parts.append(f"{name} {r.get('current', r['max'])}/{r['max']}")
    lines = [f"⚔️ *{char['name']}*",
             f"❤️ HP: {cur_hp}/{max_hp}"]
    if temp > 0:
        lines.append(f"✨ Временные: +{temp}")
    if slot_parts:
        lines.append(f"🔮 Ячейки: {', '.join(slot_parts)}")
    if res_parts:
        lines.append(f"⚡ Ресурсы: {', '.join(res_parts)}")
    return "\n".join(lines)


def _battle_card_kb(codename, mode="battle"):
    if mode == "battle":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💔 Нанести урон",
                                  callback_data=f"sess_dmg:{codename}")],
            [InlineKeyboardButton(text="💚 Лечение",
                                  callback_data=f"sess_heal:{codename}")],
            [InlineKeyboardButton(text="✨ Временные хиты",
                                  callback_data=f"sess_temp:{codename}")],
            [InlineKeyboardButton(text="🔮 Ячейки заклинаний",
                                  callback_data=f"sess_slots_menu:{codename}")],
            [InlineKeyboardButton(text="⚡ Ресурсы",
                                  callback_data=f"sess_res_menu:{codename}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="sess_battle_chars")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💔 Нанести урон",
                              callback_data=f"sess_ooc_dmg:{codename}")],
        [InlineKeyboardButton(text="💚 Лечение",
                              callback_data=f"sess_ooc_heal:{codename}")],
        [InlineKeyboardButton(text="✨ Временные хиты",
                              callback_data=f"sess_ooc_temp:{codename}")],
        [InlineKeyboardButton(text="🔮 Ячейки заклинаний",
                              callback_data=f"sess_ooc_slots_menu:{codename}")],
        [InlineKeyboardButton(text="⚡ Ресурсы",
                              callback_data=f"sess_ooc_res_menu:{codename}")],
        [InlineKeyboardButton(text="📊 Дать опыт",
                              callback_data=f"sess_ooc_xp:{codename}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sess_ooc")],
    ])


@router.callback_query(F.data.startswith("sess_battle_char:"))
async def cb_battle_char(callback: CallbackQuery):
    codename = _extract_char_codename(callback.data, "sess_battle_char")
    if not codename:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден.", show_alert=True)
        return
    await _safe_edit(callback.message, _battle_card_text(char), parse_mode="Markdown",
                     reply_markup=_battle_card_kb(codename, "battle"))
    await callback.answer()


# ---------- Управление противниками в бою ----------
@router.callback_query(F.data == "sess_battle_enemies")
async def cb_battle_enemies(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    battle = load_battle()
    enemies = battle.get("enemies", [])
    if not enemies:
        await callback.answer("Нет активных противников", show_alert=True)
        return
    kb = []
    for i, e in enumerate(enemies):
        cur = int(e.get("current_hp", 0))
        mx = int(e.get("max_hp", 0))
        marker = "💀" if cur <= 0 else "👹"
        kb.append([InlineKeyboardButton(
            text=f"{marker} {e['name']} — {cur}/{mx}",
            callback_data=f"sess_battle_enemy:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="sess_battle")])
    await _safe_edit(callback.message,
                     "👹 *Активные противники*\n\nВыберите:",
                     parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


def _enemy_card_text(entry: dict) -> str:
    cur = int(entry.get("current_hp", 0))
    mx = int(entry.get("max_hp", 0))
    tmp = int(entry.get("temp_hp", 0) or 0)
    marker = "💀" if cur <= 0 else "👹"
    text = f"{marker} *{entry['name']}*\n\n"
    text += f"❤️ HP: *{cur}/{mx}*\n"
    if tmp > 0:
        text += f"✨ Временные: +{tmp}\n"
    enemy_data = get_enemy(entry["name"])
    if enemy_data:
        text += (f"⚔ Опасность: {enemy_data.get('cr', '?')} "
                 f"(ОП {enemy_data.get('xp', '?')})\n")
        if enemy_data.get("ac"):
            text += f"🛡 КД: {enemy_data['ac']}\n"
    return text


def _enemy_card_kb(idx: int, entry: dict) -> InlineKeyboardMarkup:
    cur = int(entry.get("current_hp", 0))
    rows = [
        [InlineKeyboardButton(text="💔 Урон", callback_data=f"sess_enemy_dmg:{idx}"),
         InlineKeyboardButton(text="💚 Лечение", callback_data=f"sess_enemy_heal:{idx}")],
        [InlineKeyboardButton(text="✨ Временные хиты", callback_data=f"sess_enemy_temp:{idx}")],
    ]
    if cur <= 0:
        rows.append([InlineKeyboardButton(
            text="💀 Убить (+опыт)", callback_data=f"sess_enemy_kill:{idx}")])
    rows.append([InlineKeyboardButton(
        text="🗑 Убрать (без опыта)", callback_data=f"sess_enemy_remove:{idx}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="sess_battle_enemies")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("sess_battle_enemy:"))
async def cb_battle_enemy(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    battle = load_battle()
    if idx < 0 or idx >= len(battle["enemies"]):
        await callback.answer("Противник не найден", show_alert=True)
        return
    entry = battle["enemies"][idx]
    await _safe_edit(callback.message, _enemy_card_text(entry),
                     parse_mode="Markdown",
                     reply_markup=_enemy_card_kb(idx, entry))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_enemy_dmg:"))
async def cb_enemy_dmg(callback: CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.clear()
    await state.update_data(enemy_idx=idx)
    await state.set_state(EnemyBattle.damage)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_battle_enemy:{idx}")]])
    await _safe_edit(callback.message, "💔 Введите количество урона (целое число):",
                     reply_markup=kb)
    await callback.answer()


@router.message(EnemyBattle.damage)
async def process_enemy_damage(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("enemy_idx", -1)
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if amount <= 0:
        await message.answer("Урон должен быть положительным.")
        return
    try:
        battle = damage_battle_enemy(idx, amount)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()
    if idx >= len(battle["enemies"]):
        await message.answer(
            "Противник больше не в бою.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ В битву", callback_data="sess_battle")]]))
        return
    entry = battle["enemies"][idx]
    cur = int(entry.get("current_hp", 0))
    tmp = int(entry.get("temp_hp", 0) or 0)
    temp_note = f"\n✨ Временные: +{tmp}" if tmp > 0 else ""
    killed_note = "\n\n💀 *Противник повержен!* Появилась кнопка «Убить»." if cur <= 0 else ""
    await message.answer(
        f"💔 Нанесено *{amount}* урона.\n\n{_enemy_card_text(entry).split(chr(10), 1)[1].lstrip()}{temp_note}{killed_note}",
        parse_mode="Markdown",
        reply_markup=_enemy_card_kb(idx, entry))


@router.callback_query(F.data.startswith("sess_enemy_heal:"))
async def cb_enemy_heal(callback: CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.clear()
    await state.update_data(enemy_idx=idx)
    await state.set_state(EnemyBattle.heal)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_battle_enemy:{idx}")]])
    await _safe_edit(callback.message, "💚 Введите количество лечения (целое число):",
                     reply_markup=kb)
    await callback.answer()


@router.message(EnemyBattle.heal)
async def process_enemy_heal(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("enemy_idx", -1)
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if amount <= 0:
        await message.answer("Лечение должно быть положительным.")
        return
    try:
        battle = heal_battle_enemy(idx, amount)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()
    if idx >= len(battle["enemies"]):
        await message.answer(
            "Противник больше не в бою.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ В битву", callback_data="sess_battle")]]))
        return
    entry = battle["enemies"][idx]
    await message.answer(
        f"💚 Восстановлено *{amount}* HP.\n\n{_enemy_card_text(entry)}",
        parse_mode="Markdown",
        reply_markup=_enemy_card_kb(idx, entry))


@router.callback_query(F.data.startswith("sess_enemy_temp:"))
async def cb_enemy_temp(callback: CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.clear()
    await state.update_data(enemy_idx=idx)
    await state.set_state(EnemyBattle.temp_hp)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0 (снять)",
                              callback_data=f"sess_enemy_temp_set:{idx}:0")],
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_battle_enemy:{idx}")]])
    await _safe_edit(callback.message,
                     "✨ Введите количество временных хитов (целое, 0 — снять):",
                     reply_markup=kb)
    await callback.answer()


@router.message(EnemyBattle.temp_hp)
async def process_enemy_temp_hp(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("enemy_idx", -1)
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое неотрицательное число.")
        return
    if amount < 0:
        await message.answer("Не может быть отрицательным.")
        return
    try:
        battle = set_battle_enemy_temp_hp(idx, amount)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()
    if idx >= len(battle["enemies"]):
        await message.answer(
            "Противник больше не в бою.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ В битву", callback_data="sess_battle")]]))
        return
    entry = battle["enemies"][idx]
    await message.answer(
        f"✨ Временные хиты: *{entry.get('temp_hp', 0)}*.\n\n{_enemy_card_text(entry)}",
        parse_mode="Markdown",
        reply_markup=_enemy_card_kb(idx, entry))


@router.callback_query(F.data.startswith("sess_enemy_temp_set:"))
async def cb_enemy_temp_set(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        idx = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.clear()
    try:
        battle = set_battle_enemy_temp_hp(idx, amount)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    if idx >= len(battle["enemies"]):
        await callback.answer("Противник больше не в бою", show_alert=True)
        return
    entry = battle["enemies"][idx]
    await callback.answer(f"Временные хиты: {entry.get('temp_hp', 0)}")
    await _safe_edit(callback.message, _enemy_card_text(entry),
                     parse_mode="Markdown",
                     reply_markup=_enemy_card_kb(idx, entry))


@router.callback_query(F.data.startswith("sess_enemy_kill:"))
async def cb_enemy_kill(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        _, xp, enemy_name = kill_enemy_from_battle(idx)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    chars = list_characters()
    results = []
    for c in chars:
        char = load_character(c["codename"])
        if not char:
            continue
        snap = get_current(char)
        cur_hp = int(snap.get("current_hp", snap.get("hp", 1)))
        if cur_hp <= 0:
            results.append(f"• {char['name']}: без сознания (0 HP) — без опыта")
            continue
        try:
            result = add_xp(c["codename"], xp)
            note = f"• {char['name']}: +{xp} опыта"
            if result.get("advanced"):
                note += f" (⬆️ ур. {result['old_level']} → {result['new_level']})"
            if result.get("need_add_level"):
                note += f" (⚠️ нужно добавить уровень {result['next_missing_level']})"
            results.append(note)
        except Exception as e:
            results.append(f"• {char['name']}: ошибка — {e}")

    text = f"💀 *{enemy_name}* убит!\n\n"
    text += f"📊 Опыт за убийство: *{xp}*\n\n"
    if results:
        text += "*Получили опыт:*\n" + "\n".join(results)
    else:
        text += "_Некому давать опыт._"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ В битву", callback_data="sess_battle")],
        [InlineKeyboardButton(text="🏕 Меню сессии", callback_data="sess_menu")],
    ])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer("Опыт начислен")


@router.callback_query(F.data.startswith("sess_enemy_remove:"))
async def cb_enemy_remove(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        remove_enemy_from_battle(idx)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer("Убран из боя")
    await _render_battle_menu(callback)


# ---------- Каталог противников ----------
@router.callback_query(F.data == "sess_battle_add")
async def cb_battle_add(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    enemies = load_enemies()
    if not enemies:
        await callback.answer("Нет доступных противников в каталоге", show_alert=True)
        return
    items = list(enumerate(enemies))
    items.sort(key=lambda x: (x[1].get("cr", 0), x[1].get("name", "")))
    kb = []
    for idx, e in items:
        kb.append([InlineKeyboardButton(
            text=format_enemy_header(e),
            callback_data=f"sess_battle_add_view:{idx}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="sess_battle")])
    await _safe_edit(callback.message,
                     "➕ *Добавить противника*\n\nВыберите из каталога:",
                     parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_battle_add_view:"))
async def cb_battle_add_view(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        idx = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    enemies = load_enemies()
    if idx < 0 or idx >= len(enemies):
        await callback.answer("Противник не найден", show_alert=True)
        return
    enemy = enemies[idx]
    text = format_enemy_details(enemy)
    text += "\n\n*Добавить в бой:*"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ×1",
                              callback_data=f"sess_battle_add_do:{idx}:1")],
        [InlineKeyboardButton(text="➕ Добавить ×2",
                              callback_data=f"sess_battle_add_do:{idx}:2")],
        [InlineKeyboardButton(text="➕ Добавить ×3",
                              callback_data=f"sess_battle_add_do:{idx}:3")],
        [InlineKeyboardButton(text="🔙 К каталогу", callback_data="sess_battle_add")],
    ])
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_battle_add_do:"))
async def cb_battle_add_do(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        idx = int(parts[1])
        count = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    enemies = load_enemies()
    if idx < 0 or idx >= len(enemies):
        await callback.answer("Противник не найден", show_alert=True)
        return
    enemy = enemies[idx]
    try:
        add_enemy_to_battle(enemy["name"], count)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer(f"Добавлено: {enemy['name']} ×{count}")
    await _render_battle_menu(callback)


# ---------- Урон / лечение персонажа в бою ----------
async def _rerender_battle(callback: CallbackQuery, codename: str):
    char = load_character(codename)
    await _safe_edit(callback.message, _battle_card_text(char), parse_mode="Markdown",
                     reply_markup=_battle_card_kb(codename, "battle"))


@router.callback_query(F.data.startswith("sess_dmg:"))
async def cb_dmg(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(battle_codename=codename, back_mode="battle")
    await state.set_state(Battle.damage)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_battle_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "💔 Введите количество урона (целое число):",
                     reply_markup=kb)
    await callback.answer()


@router.message(Battle.damage)
async def process_damage(message: Message, state: FSMContext):
    data = await state.get_data()
    codename = data.get("battle_codename")
    back_mode = data.get("back_mode", "battle")
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if amount <= 0:
        await message.answer("Урон должен быть положительным.")
        return
    try:
        char = damage_character(codename, amount)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        return
    snap = get_current(char)
    cur = snap.get("current_hp", snap["hp"])
    temp = int(snap.get("temp_hp", 0) or 0)
    note = f"\n✨ Временные хиты: {temp}" if temp > 0 else ""
    await state.clear()

    if back_mode == "ooc":
        back_cb = f"sess_ooc_char:char:{codename}"
        menu_cb = "sess_ooc"
        card_text = "⚔️ К карточке"
        menu_text = "🔙 В меню вне боя"
    else:
        back_cb = f"sess_battle_char:char:{codename}"
        menu_cb = "sess_battle"
        card_text = "⚔️ К карточке боя"
        menu_text = "🔙 В меню битвы"

    await message.answer(
        f"💔 Нанесено *{amount}* урона.\n\n"
        f"❤️ HP: *{cur}/{snap['hp']}*{note}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card_text, callback_data=back_cb)],
            [InlineKeyboardButton(text=menu_text, callback_data=menu_cb)],
        ]))


@router.callback_query(F.data.startswith("sess_heal:"))
async def cb_heal(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(battle_codename=codename, back_mode="battle")
    await state.set_state(Battle.heal)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_battle_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "💚 Введите количество лечения (целое число):",
                     reply_markup=kb)
    await callback.answer()


@router.message(Battle.heal)
async def process_heal(message: Message, state: FSMContext):
    data = await state.get_data()
    codename = data.get("battle_codename")
    back_mode = data.get("back_mode", "battle")
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if amount <= 0:
        await message.answer("Лечение должно быть положительным.")
        return
    try:
        char = heal_character(codename, amount)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        return
    snap = get_current(char)
    await state.clear()

    if back_mode == "ooc":
        back_cb = f"sess_ooc_char:char:{codename}"
        menu_cb = "sess_ooc"
        card_text = "⚔️ К карточке"
        menu_text = "🔙 В меню вне боя"
    else:
        back_cb = f"sess_battle_char:char:{codename}"
        menu_cb = "sess_battle"
        card_text = "⚔️ К карточке боя"
        menu_text = "🔙 В меню битвы"

    await message.answer(
        f"💚 Восстановлено *{amount}* HP.\n\n"
        f"❤️ HP: *{snap['current_hp']}/{snap['hp']}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card_text, callback_data=back_cb)],
            [InlineKeyboardButton(text=menu_text, callback_data=menu_cb)],
        ]))


@router.callback_query(F.data.startswith("sess_temp:"))
async def cb_temp(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(battle_codename=codename, back_mode="battle")
    await state.set_state(Battle.temp_hp)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0 (снять)",
                              callback_data=f"sess_temp_set:{codename}:0")],
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_battle_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "✨ Введите количество временных хитов (целое, 0 — снять):",
                     reply_markup=kb)
    await callback.answer()


@router.message(Battle.temp_hp)
async def process_temp_hp(message: Message, state: FSMContext):
    data = await state.get_data()
    codename = data.get("battle_codename")
    back_mode = data.get("back_mode", "battle")
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое неотрицательное число.")
        return
    if amount < 0:
        await message.answer("Не может быть отрицательным.")
        return
    try:
        char = add_temp_hp(codename, amount)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        return
    snap = get_current(char)
    await state.clear()

    if back_mode == "ooc":
        back_cb = f"sess_ooc_char:char:{codename}"
        menu_cb = "sess_ooc"
        card_text = "⚔️ К карточке"
        menu_text = "🔙 В меню вне боя"
    else:
        back_cb = f"sess_battle_char:char:{codename}"
        menu_cb = "sess_battle"
        card_text = "⚔️ К карточке боя"
        menu_text = "🔙 В меню битвы"

    await message.answer(
        f"✨ Временные хиты: *{snap.get('temp_hp', 0)}*.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card_text, callback_data=back_cb)],
            [InlineKeyboardButton(text=menu_text, callback_data=menu_cb)],
        ]))


@router.callback_query(F.data.startswith("sess_temp_set:"))
async def cb_temp_set(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, amount_s = parts[1], parts[2]
    try:
        amount = int(amount_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = add_temp_hp(codename, amount)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    snap = get_current(char)
    await callback.answer(f"Временные хиты: {snap.get('temp_hp', 0)}")
    await _rerender_battle(callback, codename)


@router.callback_query(F.data.startswith("sess_slots_menu:"))
async def cb_slots_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    snap = get_current(char)
    slots = snap.get("spell_slots", {})
    active_levels = []
    for lvl in sorted(int(k) for k in slots.keys()):
        d = slots[str(lvl)]
        if d.get("max", 0) > 0:
            active_levels.append((lvl, d))
    if not active_levels:
        await callback.answer("У персонажа нет ячеек заклинаний", show_alert=True)
        return
    kb = []
    for lvl, d in active_levels:
        cur = d.get("current", d["max"])
        kb.append([
            InlineKeyboardButton(
                text=f"➖ {lvl}ур",
                callback_data=f"sess_slot_chg:{codename}:{lvl}:-1"),
            InlineKeyboardButton(
                text=f"{lvl}ур {cur}/{d['max']}",
                callback_data="noop_sess"),
            InlineKeyboardButton(
                text=f"➕ {lvl}ур",
                callback_data=f"sess_slot_chg:{codename}:{lvl}:1"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"sess_battle_char:char:{codename}")])
    await _safe_edit(callback.message,
                     "🔮 *Ячейки заклинаний*\n\nНажмите ➖ чтобы потратить, ➕ чтобы восстановить.",
                     parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_slot_chg:"))
async def cb_slot_chg(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]
    try:
        lvl = int(parts[2]); delta = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        if delta < 0:
            char = spend_spell_slot(codename, lvl, 1)
        else:
            char = restore_spell_slot(codename, lvl, 1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer("OK")
    await cb_slots_menu(callback)


@router.callback_query(F.data.startswith("sess_res_menu:"))
async def cb_res_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    snap = get_current(char)
    resources = snap.get("resources", {})
    active = [(n, r) for n, r in resources.items() if r.get("max", 0) > 0]
    if not active:
        await callback.answer("У персонажа нет ресурсов", show_alert=True)
        return
    kb = []
    for name, r in active:
        cur = r.get("current", r["max"])
        kb.append([
            InlineKeyboardButton(text=f"➖ {name}",
                                 callback_data=f"sess_res_chg:{codename}:{name}:-1"),
            InlineKeyboardButton(text=f"{name} {cur}/{r['max']}",
                                 callback_data="noop_sess"),
            InlineKeyboardButton(text=f"➕ {name}",
                                 callback_data=f"sess_res_chg:{codename}:{name}:1"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"sess_battle_char:char:{codename}")])
    await _safe_edit(callback.message,
                     "⚡ *Ресурсы*\n\n➖ — потратить 1, ➕ — восстановить 1.",
                     parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_res_chg:"))
async def cb_res_chg(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]; name = parts[2]
    try:
        delta = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        if delta < 0:
            char = spend_resource(codename, name, 1)
        else:
            char = restore_resource(codename, name, 1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer("OK")
    await cb_res_menu(callback)


@router.callback_query(F.data == "noop_sess")
async def noop_sess(callback: CallbackQuery):
    await callback.answer()


# ============================================================
#  Вне боя
# ============================================================
@router.callback_query(F.data == "sess_ooc")
async def cb_ooc(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = chars_list_kb("sess_ooc_char", back_cb="sess_menu")
    await _safe_edit(callback.message, "🛠 Выберите персонажа:",
                     reply_markup=kb)
    await callback.answer()


def _ooc_card_text(char):
    snap = get_current(char)
    cur_hp = snap.get("current_hp", snap["hp"])
    max_hp = snap["hp"]
    temp = int(snap.get("temp_hp", 0) or 0)
    slots = snap.get("spell_slots", {})
    slot_parts = []
    for lvl in sorted(int(k) for k in slots.keys()):
        d = slots[str(lvl)]
        if d.get("max", 0) > 0:
            slot_parts.append(f"{lvl}ур {d.get('current', d['max'])}/{d['max']}")
    resources = snap.get("resources", {})
    res_parts = []
    for name, r in resources.items():
        if r.get("max", 0) > 0:
            res_parts.append(f"{name} {r.get('current', r['max'])}/{r['max']}")
    xp, next_xp = get_xp_progress(char)
    if next_xp is None:
        xp_str = f"{xp} (макс.)"
    elif xp >= next_xp:
        xp_str = f"{xp} ⬆️ (следующий ур. доступен)"
    else:
        xp_str = f"{xp} / {next_xp}"
    lines = [f"🛠 *{char['name']}*",
             f"❤️ HP: {cur_hp}/{max_hp}"]
    if temp > 0:
        lines.append(f"✨ Временные: +{temp}")
    if slot_parts:
        lines.append(f"🔮 Ячейки: {', '.join(slot_parts)}")
    if res_parts:
        lines.append(f"⚡ Ресурсы: {', '.join(res_parts)}")
    lines.append(f"📊 Опыт: {xp_str}")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("sess_ooc_char:"))
async def cb_ooc_char(callback: CallbackQuery):
    codename = _extract_char_codename(callback.data, "sess_ooc_char")
    if not codename:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден.", show_alert=True)
        return
    await _safe_edit(callback.message, _ooc_card_text(char), parse_mode="Markdown",
                     reply_markup=_battle_card_kb(codename, "ooc"))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_ooc_dmg:"))
async def cb_ooc_dmg(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(battle_codename=codename, back_mode="ooc")
    await state.set_state(Battle.damage)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_ooc_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "💔 Введите количество урона (целое число):",
                     reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_ooc_heal:"))
async def cb_ooc_heal(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(battle_codename=codename, back_mode="ooc")
    await state.set_state(Battle.heal)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_ooc_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "💚 Введите количество лечения (целое число):",
                     reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_ooc_temp:"))
async def cb_ooc_temp(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(battle_codename=codename, back_mode="ooc")
    await state.set_state(Battle.temp_hp)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0 (снять)",
                              callback_data=f"sess_ooc_temp_set:{codename}:0")],
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_ooc_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "✨ Введите количество временных хитов (целое, 0 — снять):",
                     reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_ooc_temp_set:"))
async def cb_ooc_temp_set(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, amount_s = parts[1], parts[2]
    try:
        amount = int(amount_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = add_temp_hp(codename, amount)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    snap = get_current(char)
    await callback.answer(f"Временные хиты: {snap.get('temp_hp', 0)}")
    char = load_character(codename)
    await _safe_edit(callback.message, _ooc_card_text(char), parse_mode="Markdown",
                     reply_markup=_battle_card_kb(codename, "ooc"))


@router.callback_query(F.data.startswith("sess_ooc_slots_menu:"))
async def cb_ooc_slots_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    snap = get_current(char)
    slots = snap.get("spell_slots", {})
    active_levels = []
    for lvl in sorted(int(k) for k in slots.keys()):
        d = slots[str(lvl)]
        if d.get("max", 0) > 0:
            active_levels.append((lvl, d))
    if not active_levels:
        await callback.answer("У персонажа нет ячеек заклинаний", show_alert=True)
        return
    kb = []
    for lvl, d in active_levels:
        cur = d.get("current", d["max"])
        kb.append([
            InlineKeyboardButton(
                text=f"➖ {lvl}ур",
                callback_data=f"sess_ooc_slot_chg:{codename}:{lvl}:-1"),
            InlineKeyboardButton(
                text=f"{lvl}ур {cur}/{d['max']}",
                callback_data="noop_sess"),
            InlineKeyboardButton(
                text=f"➕ {lvl}ур",
                callback_data=f"sess_ooc_slot_chg:{codename}:{lvl}:1"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"sess_ooc_char:char:{codename}")])
    await _safe_edit(callback.message,
                     "🔮 *Ячейки заклинаний*\n\nНажмите ➖ чтобы потратить, ➕ чтобы восстановить.",
                     parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_ooc_slot_chg:"))
async def cb_ooc_slot_chg(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]
    try:
        lvl = int(parts[2]); delta = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        if delta < 0:
            char = spend_spell_slot(codename, lvl, 1)
        else:
            char = restore_spell_slot(codename, lvl, 1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer("OK")
    await cb_ooc_slots_menu(callback)


@router.callback_query(F.data.startswith("sess_ooc_res_menu:"))
async def cb_ooc_res_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    snap = get_current(char)
    resources = snap.get("resources", {})
    active = [(n, r) for n, r in resources.items() if r.get("max", 0) > 0]
    if not active:
        await callback.answer("У персонажа нет ресурсов", show_alert=True)
        return
    kb = []
    for name, r in active:
        cur = r.get("current", r["max"])
        kb.append([
            InlineKeyboardButton(text=f"➖ {name}",
                                 callback_data=f"sess_ooc_res_chg:{codename}:{name}:-1"),
            InlineKeyboardButton(text=f"{name} {cur}/{r['max']}",
                                 callback_data="noop_sess"),
            InlineKeyboardButton(text=f"➕ {name}",
                                 callback_data=f"sess_ooc_res_chg:{codename}:{name}:1"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"sess_ooc_char:char:{codename}")])
    await _safe_edit(callback.message,
                     "⚡ *Ресурсы*\n\n➖ — потратить 1, ➕ — восстановить 1.",
                     parse_mode="Markdown",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("sess_ooc_res_chg:"))
async def cb_ooc_res_chg(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]; name = parts[2]
    try:
        delta = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        if delta < 0:
            char = spend_resource(codename, name, 1)
        else:
            char = restore_resource(codename, name, 1)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.answer("OK")
    await cb_ooc_res_menu(callback)


# ---------- Опыт во вне боя ----------
@router.callback_query(F.data.startswith("sess_ooc_xp:"))
async def cb_ooc_xp(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    await state.clear()
    await state.update_data(xp_codename=codename)
    await state.set_state(GiveXP.amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data=f"sess_ooc_char:char:{codename}")]])
    await _safe_edit(callback.message,
                     "📊 Сколько опыта добавить? Введите целое положительное число:",
                     reply_markup=kb)
    await callback.answer()


@router.message(GiveXP.amount)
async def process_ooc_xp(message: Message, state: FSMContext):
    data = await state.get_data()
    codename = data.get("xp_codename")
    if not codename:
        await state.clear()
        await message.answer("Сессия истекла.")
        return
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if amount <= 0:
        await message.answer("Опыт должен быть положительным.")
        return
    try:
        result = add_xp(codename, amount)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()

    char = result["char"]
    snap = get_current(char)

    text = f"📊 Начислено *{result['xp_gained']}* опыта.\n"
    text += f"Всего опыта: *{result['total_xp']}* (было {result['old_xp']}).\n"

    if result["advanced"]:
        text += (f"\n⬆️ Уровень повышен: *{result['old_level']}* → "
                 f"*{result['new_level']}*\n")
        text += f"❤️ HP: {snap.get('current_hp', snap['hp'])}/{snap['hp']}\n"
        text += f"Бонус мастерства: +{snap['proficiency_bonus']}\n"

    if result["need_add_level"]:
        text += (f"\n⚠️ Уровень *{result['target_level']}* ещё не добавлен в /characters.\n"
                 f"Перейдите в меню прокачки персонажа и добавьте уровень "
                 f"*{result['next_missing_level']}*.\n")

    if not result["advanced"] and not result["need_add_level"]:
        text += "\nℹ️ Уровень не изменился."

    kb_rows = []
    if result["need_add_level"]:
        kb_rows.append([InlineKeyboardButton(
            text="🎯 Перейти к прокачке",
            callback_data=f"levels:{codename}")])
    kb_rows.append([InlineKeyboardButton(
        text="🛠 К персонажу", callback_data=f"sess_ooc_char:char:{codename}")])
    kb_rows.append([InlineKeyboardButton(
        text="🔙 Меню сессии", callback_data="sess_menu")])

    await message.answer(text, parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


# ============================================================
#  Передача
# ============================================================
@router.callback_query(F.data == "sess_transfer")
async def cb_transfer_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = chars_list_kb("sess_tr_src", include_camp=True, back_cb="sess_menu")
    await _safe_edit(callback.message,
                     "💱 *Передача*\n\nВыберите *источник* (откуда):",
                     parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_tr_src:"))
async def cb_transfer_src(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    if len(parts) < 2:
        await callback.answer()
        return
    src_type = parts[1]
    src_id = parts[2] if len(parts) > 2 else ""
    await state.update_data(tr_src_type=src_type, tr_src_id=src_id)

    exclude = src_id if src_type == "char" else None
    include_camp = src_type != "camp"
    kb = chars_list_kb("sess_tr_dst", include_camp=include_camp,
                       exclude_codename=exclude, back_cb="sess_transfer")
    src_name = "🏕 Лагерь" if src_type == "camp" else (
        load_character(src_id) or {}).get("name", src_id)
    await _safe_edit(callback.message,
                     f"💱 Из: *{src_name}*\n\nВыберите *приёмник* (куда):",
                     parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_tr_dst:"))
async def cb_transfer_dst(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    if len(parts) < 2:
        await callback.answer()
        return
    dst_type = parts[1]
    dst_id = parts[2] if len(parts) > 2 else ""
    await state.update_data(tr_dst_type=dst_type, tr_dst_id=dst_id)

    data = await state.get_data()
    src_name = "🏕 Лагерь" if data.get("tr_src_type") == "camp" else (
        load_character(data.get("tr_src_id", "")) or {}).get("name", data.get("tr_src_id", ""))
    dst_name = "🏕 Лагерь" if dst_type == "camp" else (
        load_character(dst_id) or {}).get("name", dst_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 Монеты",
                              callback_data="sess_tr_type:coins")],
        [InlineKeyboardButton(text="📦 Предметы",
                              callback_data="sess_tr_type:items")],
        [InlineKeyboardButton(text="🔙 Назад",
                              callback_data="sess_transfer")],
    ])
    await _safe_edit(callback.message,
                     f"💱 *{src_name}* → *{dst_name}*\n\nЧто передаём?",
                     parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_tr_type:"))
async def cb_transfer_type(callback: CallbackQuery, state: FSMContext):
    type_ = callback.data.split(":", 1)[1]
    await state.update_data(tr_kind=type_)
    data = await state.get_data()

    if type_ == "coins":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{COIN_SHORT[k]} ({k})",
                                  callback_data=f"sess_tr_cur:{k}")]
            for k in ["mm", "sm", "zm", "pm"]
        ])
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text="🔙 Назад", callback_data="sess_tr_back_type")])
        await _safe_edit(callback.message,
                         "🪙 Выберите валюту для передачи:",
                         reply_markup=kb)
        await callback.answer()
        return

    try:
        src = _get_container(data["tr_src_type"], data["tr_src_id"])
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    items = src["items"]
    if not items:
        await callback.answer("У источника нет предметов", show_alert=True)
        return
    kb = []
    for i, it in enumerate(items):
        qty = int(it.get("quantity", 1))
        qty_str = f" ×{qty}" if qty > 1 else ""
        e = int(it.get("enchantment", 0) or 0)
        e_str = f" +{e}" if e else ""
        kb.append([InlineKeyboardButton(
            text=f"{it.get('name', '?')}{e_str}{qty_str}",
            callback_data=f"sess_tr_item:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data="sess_tr_back_type")])
    await _safe_edit(callback.message,
                     "📦 Выберите предмет для передачи:",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data == "sess_tr_back_type")
async def cb_tr_back_type(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    src_name = "🏕 Лагерь" if data.get("tr_src_type") == "camp" else (
        load_character(data.get("tr_src_id", "")) or {}).get("name", "?")
    dst_name = "🏕 Лагерь" if data.get("tr_dst_type") == "camp" else (
        load_character(data.get("tr_dst_id", "")) or {}).get("name", "?")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 Монеты",
                              callback_data="sess_tr_type:coins")],
        [InlineKeyboardButton(text="📦 Предметы",
                              callback_data="sess_tr_type:items")],
        [InlineKeyboardButton(text="🔙 Назад",
                              callback_data="sess_transfer")],
    ])
    await _safe_edit(callback.message,
                     f"💱 *{src_name}* → *{dst_name}*\n\nЧто передаём?",
                     parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sess_tr_cur:"))
async def cb_tr_currency(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.split(":", 1)[1]
    if currency not in COIN_KEYS:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.update_data(tr_currency=currency)
    await state.set_state(Transfer.amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data="sess_transfer")]])
    await _safe_edit(callback.message,
                     f"🪙 Сколько {COIN_SHORT[currency]} передать?\n"
                     f"Введите целое число.",
                     reply_markup=kb)
    await callback.answer()


@router.message(Transfer.amount)
async def process_tr_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if amount <= 0:
        await message.answer("Число должно быть больше нуля.")
        return

    src_type = data.get("tr_src_type")
    src_id = data.get("tr_src_id", "")
    dst_type = data.get("tr_dst_type")
    dst_id = data.get("tr_dst_id", "")
    currency = data.get("tr_currency")

    try:
        src = _get_container(src_type, src_id)
        dst = _get_container(dst_type, dst_id)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return

    try:
        transfer_coins(src["coins"], dst["coins"], currency, amount)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return

    src["save"]()
    dst["save"]()

    await state.clear()
    await message.answer(
        f"✅ Передано *{amount} {COIN_SHORT[currency]}* из *{src['name']}* "
        f"в *{dst['name']}*.\n\n"
        f"💰 {src['name']}: {format_coins(src['coins'])}\n"
        f"💰 {dst['name']}: {format_coins(dst['coins'])}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💱 Снова", callback_data="sess_transfer")],
            [InlineKeyboardButton(text="🏕 Меню", callback_data="sess_menu")],
        ]))


@router.callback_query(F.data.startswith("sess_tr_item:"))
async def cb_tr_item(callback: CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.update_data(tr_item_idx=idx)
    await state.set_state(Transfer.item_qty)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена",
                              callback_data="sess_transfer")]])
    await _safe_edit(callback.message,
                     "📦 Сколько передать? Введите целое число:",
                     reply_markup=kb)
    await callback.answer()


@router.message(Transfer.item_qty)
async def process_tr_item_qty(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        qty = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return
    if qty <= 0:
        await message.answer("Число должно быть больше нуля.")
        return

    src_type = data.get("tr_src_type")
    src_id = data.get("tr_src_id", "")
    dst_type = data.get("tr_dst_type")
    dst_id = data.get("tr_dst_id", "")
    idx = data.get("tr_item_idx", -1)

    try:
        src = _get_container(src_type, src_id)
        dst = _get_container(dst_type, dst_id)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return

    try:
        item_name, moved = transfer_item(src["items"], dst["items"], idx, qty)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return

    src["save"]()
    dst["save"]()

    await state.clear()
    await message.answer(
        f"✅ Передано *{item_name}* ×{moved} из *{src['name']}* "
        f"в *{dst['name']}*.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💱 Снова", callback_data="sess_transfer")],
            [InlineKeyboardButton(text="🏕 Меню", callback_data="sess_menu")],
        ]))