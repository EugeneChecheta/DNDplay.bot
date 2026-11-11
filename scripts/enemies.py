"""Загрузка противников (монстров), управление состоянием боя и просмотр бестиария."""
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

BASE_DIR = Path(__file__).resolve().parent.parent
ENEMIES_FILE = BASE_DIR / "archive" / "enemies" / "enemies.json"
BATTLE_FILE = BASE_DIR / "camp" / "battle.json"
BATTLE_FILE.parent.mkdir(parents=True, exist_ok=True)

router = Router(name="enemies")

SOURCE_TITLES = {
    "all": "📚 Все противники",
}


async def _safe_edit(message, text, **kwargs):
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_enemies() -> list:
    data = _load_json(ENEMIES_FILE)
    if not data:
        return []
    return data.get("enemies", [])


def get_enemy(name: str):
    for e in load_enemies():
        if e.get("name") == name:
            return e
    return None


def format_enemy_header(enemy: dict) -> str:
    cr = enemy.get("cr", 0)
    return f"{enemy['name']} (ОП {cr})"


def _fmt_mod(value: int) -> str:
    mod = (int(value) - 10) // 2
    return f"+{mod}" if mod >= 0 else str(mod)


def _stats_line(stats: dict) -> str:
    parts = []
    for k in ["Сила", "Ловкость", "Телосложение", "Интеллект", "Мудрость", "Харизма"]:
        if k in stats:
            v = stats[k]
            parts.append(f"{k} {v} ({_fmt_mod(v)})")
    return ", ".join(parts)


def format_enemy_details(enemy: dict) -> str:
    lines = [f"👹 *{enemy['name']}*" + (f" _{enemy.get('name_en', '')}_" if enemy.get("name_en") else "")]
    src = enemy.get("source")
    if isinstance(src, list):
        src = ", ".join(src)
    if src:
        lines.append(f"📖 Источник: {src}")
    size = enemy.get("size", "?")
    typ = enemy.get("type", "?")
    align = enemy.get("alignment", "—")
    lines.append(f"*{size} {typ}*, {align}")
    lines.append("")
    ac_str = f"{enemy.get('ac', '?')}"
    if enemy.get("ac_type"):
        ac_str += f" ({enemy['ac_type']})"
    lines.append(f"🛡 КД: {ac_str}")
    hp_str = f"{enemy.get('hp', '?')}"
    if enemy.get("hit_dice"):
        hp_str += f" ({enemy['hit_dice']})"
    lines.append(f"❤️ Хиты: {hp_str}")
    lines.append(f"🏃 Скорость: {enemy.get('speed', '?')}")
    lines.append("")
    lines.append(f"📊 {_stats_line(enemy.get('stats', {}))}")
    if enemy.get("senses"):
        lines.append(f"👁 Чувства: {enemy['senses']}")
    if enemy.get("damage_vulnerabilities"):
        lines.append(f"⚠ Уязвимость к урону: {enemy['damage_vulnerabilities']}")
    if enemy.get("damage_immunities"):
        lines.append(f"🛡 Иммунитет к урону: {enemy['damage_immunities']}")
    if enemy.get("condition_immunities"):
        lines.append(f"🛡 Иммунитет к состояниям: {enemy['condition_immunities']}")
    if enemy.get("languages"):
        lines.append(f"🗣 Языки: {enemy['languages']}")
    lines.append(f"⚔ Опасность: *{enemy.get('cr', '?')}* (ОП {enemy.get('xp', '?')})")
    lines.append(f"Бонус мастерства: +{enemy.get('pb', 2)}")
    if enemy.get("habitat"):
        lines.append(f"🌍 Местность обитания: {', '.join(enemy['habitat'])}")
    actions = enemy.get("actions", [])
    if actions:
        lines.append("\n📜 *Действия:*")
        for a in actions:
            lines.append(f"\n*{a['name']}.* {a.get('description', '')}")
    if enemy.get("description"):
        lines.append(f"\n{enemy['description']}")
    return "\n".join(lines)


# ============================================================
#  Управление боем
# ============================================================
def load_battle() -> dict:
    data = _load_json(BATTLE_FILE)
    if not data:
        return {"enemies": [], "players": []}
    data.setdefault("enemies", [])
    data.setdefault("players", [])
    return data


def save_battle(battle: dict) -> None:
    _save_json(BATTLE_FILE, battle)


def add_enemy_to_battle(enemy_name: str, count: int = 1) -> dict:
    enemy = get_enemy(enemy_name)
    if not enemy:
        raise ValueError("Противник не найден.")
    if count <= 0:
        raise ValueError("Количество должно быть положительным.")
    battle = load_battle()
    for _ in range(count):
        hp = int(enemy.get("hp", 1))
        battle["enemies"].append({
            "name": enemy["name"],
            "max_hp": hp,
            "current_hp": hp,
            "temp_hp": 0,
        })
    save_battle(battle)
    return battle


def remove_enemy_from_battle(idx: int) -> dict:
    battle = load_battle()
    if idx < 0 or idx >= len(battle["enemies"]):
        raise ValueError("Противник не найден.")
    battle["enemies"].pop(idx)
    save_battle(battle)
    return battle


def kill_enemy_from_battle(idx: int) -> tuple:
    battle = load_battle()
    if idx < 0 or idx >= len(battle["enemies"]):
        raise ValueError("Противник не найден.")
    entry = battle["enemies"].pop(idx)
    save_battle(battle)
    enemy_data = get_enemy(entry["name"])
    xp = int(enemy_data.get("xp", 0)) if enemy_data else 0
    return battle, xp, entry["name"]


def damage_battle_enemy(idx: int, amount: int) -> dict:
    battle = load_battle()
    if idx < 0 or idx >= len(battle["enemies"]):
        raise ValueError("Противник не найден.")
    if amount <= 0:
        raise ValueError("Урон должен быть положительным.")
    entry = battle["enemies"][idx]
    temp = int(entry.get("temp_hp", 0) or 0)
    if temp > 0:
        absorbed = min(temp, amount)
        temp -= absorbed
        amount -= absorbed
        entry["temp_hp"] = temp
    entry["current_hp"] = max(0, int(entry.get("current_hp", 0)) - amount)
    save_battle(battle)
    return battle


def heal_battle_enemy(idx: int, amount: int) -> dict:
    battle = load_battle()
    if idx < 0 or idx >= len(battle["enemies"]):
        raise ValueError("Противник не найден.")
    if amount <= 0:
        raise ValueError("Лечение должно быть положительным.")
    entry = battle["enemies"][idx]
    entry["current_hp"] = min(int(entry.get("max_hp", 1)),
                              int(entry.get("current_hp", 0)) + amount)
    save_battle(battle)
    return battle


def set_battle_enemy_temp_hp(idx: int, amount: int) -> dict:
    battle = load_battle()
    if idx < 0 or idx >= len(battle["enemies"]):
        raise ValueError("Противник не найден.")
    if amount < 0:
        raise ValueError("Временные хиты не могут быть отрицательными.")
    entry = battle["enemies"][idx]
    entry["temp_hp"] = max(int(entry.get("temp_hp", 0) or 0), amount)
    save_battle(battle)
    return battle


# ---------- Участники боя (группа) ----------
def add_player_to_battle(codename: str) -> dict:
    battle = load_battle()
    if codename not in battle["players"]:
        battle["players"].append(codename)
    save_battle(battle)
    return battle


def remove_player_from_battle(codename: str) -> dict:
    battle = load_battle()
    if codename in battle["players"]:
        battle["players"].remove(codename)
    save_battle(battle)
    return battle


def is_player_in_battle(codename: str) -> bool:
    battle = load_battle()
    return codename in battle.get("players", [])


# ============================================================
#  Роутер: бестиарий (/enemies)
# ============================================================
def _build_catalog():
    enemies = load_enemies()
    if not enemies:
        return None, "📭 Каталог противников пуст."
    items = list(enumerate(enemies))
    items.sort(key=lambda x: (x[1].get("cr", 0), x[1].get("name", "")))
    kb = []
    for idx, e in items:
        kb.append([InlineKeyboardButton(
            text=format_enemy_header(e),
            callback_data=f"enemy_view:{idx}")])
    return (InlineKeyboardMarkup(inline_keyboard=kb),
            "👹 *Каталог противников*\n\nВыберите для просмотра:")


@router.message(Command("enemies"))
async def cmd_enemies(message: Message, state: FSMContext):
    await state.clear()
    kb, text = _build_catalog()
    if kb is None:
        await message.answer(text)
        return
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "main_enemies")
async def cb_main_enemies(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb, text = _build_catalog()
    if kb is None:
        await _safe_edit(callback.message, text)
        await callback.answer()
        return
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "enemy_list")
async def cb_enemy_list(callback: CallbackQuery):
    kb, text = _build_catalog()
    if kb is None:
        await callback.answer("Каталог пуст", show_alert=True)
        return
    await _safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("enemy_view:"))
async def cb_enemy_view(callback: CallbackQuery):
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К каталогу", callback_data="enemy_list")]])
    await _safe_edit(
        callback.message,
        format_enemy_details(enemy),
        parse_mode="Markdown",
        reply_markup=kb,
    )
    await callback.answer()