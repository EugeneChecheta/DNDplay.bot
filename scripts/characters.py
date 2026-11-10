import json
import logging
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router(name="characters")

# ---------- Пути проекта ----------
BASE_DIR = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = BASE_DIR / "characters"
RULES_CLASSES_DIR = BASE_DIR / "rules" / "classes"
RULES_RACES_DIR = BASE_DIR / "rules" / "races"
ARCHIVE_SKILLS_CLASSES = BASE_DIR / "archive" / "skills" / "classes"
ARCHIVE_SKILLS_RACES = BASE_DIR / "archive" / "skills" / "races"
ARCHIVE_BACKGROUNDS = BASE_DIR / "archive" / "backgrounds" / "backgrounds.json"
ARCHIVE_TRAITS = BASE_DIR / "archive" / "traits" / "traits.json"
ARCHIVE_SPELLS = BASE_DIR / "archive" / "spells" / "spells.json"

CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)

MAX_LEVEL = 20

VALID_EQUIP_SLOTS = {"armor", "melee_main", "melee_off", "ranged_main", "ranged_off"}

WEAPON_PROFICIENCY_MAP = {
    "simple_melee": "Простое оружие",
    "simple_ranged": "Простое оружие",
    "martial_melee": "Воинское оружие",
    "martial_ranged": "Воинское оружие",
}

XP_TABLE = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000,
    10: 64000, 11: 85000, 12: 100000, 13: 120000,
    14: 140000, 15: 165000, 16: 195000, 17: 225000,
    18: 265000, 19: 305000, 20: 355000,
}

ASI_LEVELS = [4, 8, 12, 16, 19]

ALL_SKILLS = [
    "Акробатика", "Анализ", "Атлетика", "Внимательность", "Выживание",
    "Выступление", "Запугивание", "История", "Ловкость рук", "Магия",
    "Медицина", "Обман", "Природа", "Проницательность", "Религия",
    "Скрытность", "Убеждение", "Уход за животными",
]

ALL_STATS = ["Сила", "Ловкость", "Телосложение",
             "Интеллект", "Мудрость", "Харизма"]

FULL_CASTER_SLOTS = {
    1: [2], 2: [3], 3: [4, 2], 4: [4, 3], 5: [4, 3, 2],
    6: [4, 3, 3], 7: [4, 3, 3, 1], 8: [4, 3, 3, 2], 9: [4, 3, 3, 3, 1],
    10: [4, 3, 3, 3, 2], 11: [4, 3, 3, 3, 2, 1], 12: [4, 3, 3, 3, 2, 1],
    13: [4, 3, 3, 3, 2, 1, 1], 14: [4, 3, 3, 3, 2, 1, 1],
    15: [4, 3, 3, 3, 2, 1, 1, 1], 16: [4, 3, 3, 3, 2, 1, 1, 1],
    17: [4, 3, 3, 3, 2, 1, 1, 1, 1], 18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
    19: [4, 3, 3, 3, 3, 2, 1, 1, 1], 20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
}
HALF_CASTER_SLOTS = {
    1: [], 2: [2], 3: [3], 4: [3], 5: [4, 2], 6: [4, 2], 7: [4, 3],
    8: [4, 3], 9: [4, 3, 2], 10: [4, 3, 2], 11: [4, 3, 3],
    12: [4, 3, 3], 13: [4, 3, 3, 1], 14: [4, 3, 3, 1],
    15: [4, 3, 3, 2], 16: [4, 3, 3, 2], 17: [4, 3, 3, 3, 1],
    18: [4, 3, 3, 3, 1], 19: [4, 3, 3, 3, 2], 20: [4, 3, 3, 3, 2],
}
THIRD_CASTER_SLOTS = {
    1: [], 2: [], 3: [2], 4: [3], 5: [3], 6: [3], 7: [4, 2], 8: [4, 2],
    9: [4, 2], 10: [4, 3], 11: [4, 3], 12: [4, 3], 13: [4, 3, 2],
    14: [4, 3, 2], 15: [4, 3, 2], 16: [4, 3, 3], 17: [4, 3, 3],
    18: [4, 3, 3], 19: [4, 3, 3, 1], 20: [4, 3, 3, 1],
}
FULL_CASTER_CLASSES = {"Волшебник", "Жрец", "Друид", "Бард", "Чародей"}
HALF_CASTER_CLASSES = {"Паладин", "Следопыт"}
THIRD_CASTER_ARCHETYPES = {"Мистический рыцарь", "Мистический ловкач"}
THIRD_CASTER_CLASS = "Воин"

_COIN_TO_MM = {"mm": 1, "sm": 10, "zm": 100, "pm": 1000}
_COIN_SHORT = {"mm": "мм", "sm": "см", "zm": "зм", "pm": "пм"}


def _fmt_coins(coins: dict) -> str:
    if not coins:
        return "0 зм"
    total = sum(coins.get(k, 0) * _COIN_TO_MM[k] for k in _COIN_TO_MM)
    if total == 0:
        return "0 зм"
    pm = total // 1000; total %= 1000
    zm = total // 100; total %= 100
    sm = total // 10; mm = total % 10
    parts = []
    if pm: parts.append(f"{pm} пм")
    if zm: parts.append(f"{zm} зм")
    if sm: parts.append(f"{sm} см")
    if mm: parts.append(f"{mm} мм")
    return ", ".join(parts)


# ---------- Транслитерация ----------
_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def _transliterate(text: str) -> str:
    result = []
    for ch in text.lower():
        if ch in _TRANSLIT:
            result.append(_TRANSLIT[ch])
        elif ch.isascii() and (ch.isalnum() or ch in '_-'):
            result.append(ch)
        elif ch in ' \t':
            result.append('_')
    slug = ''.join(result).strip('_')
    return slug[:40] or 'character'


def _generate_codename(name: str) -> str:
    base = _transliterate(name)
    codename = base
    counter = 2
    while (CHARACTERS_DIR / f"{codename}.json").exists():
        codename = f"{base}_{counter}"
        counter += 1
    return codename


# ---------- JSON ----------
def _load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_json_by_name(directory: Path, name: str):
    if not directory.exists():
        return None, None
    for p in sorted(directory.glob("*.json")):
        try:
            data = _load_json(p)
        except Exception:
            continue
        if data and data.get("name") == name:
            return p, data
    for p in sorted(directory.glob("*.json")):
        if p.stem.lower() == name.lower():
            return p, _load_json(p)
    return None, None


# ---------- Доступные опции ----------
def get_available_races():
    if not RULES_RACES_DIR.exists():
        return []
    result = []
    for p in sorted(RULES_RACES_DIR.glob("*.json")):
        data = _load_json(p)
        if data and data.get("name"):
            result.append(data["name"])
    return result


def get_available_classes():
    if not RULES_CLASSES_DIR.exists():
        return []
    result = []
    for p in sorted(RULES_CLASSES_DIR.glob("*.json")):
        data = _load_json(p)
        if data and data.get("name"):
            result.append(data["name"])
    return result


def get_available_backgrounds():
    data = _load_json(ARCHIVE_BACKGROUNDS)
    if not data:
        return []
    return [bg["name"] for bg in data.get("backgrounds", []) if bg.get("name")]


def get_available_traits():
    data = _load_json(ARCHIVE_TRAITS)
    if not data:
        return []
    return [t["name"] for t in data.get("traits", []) if t.get("name")]


def get_fighting_styles(char_class: str):
    data = get_class_data(char_class)
    if not data:
        return []
    return data.get("fighting_styles", [])


def get_available_archetypes(char_class: str):
    data = get_class_data(char_class)
    if not data:
        return []
    return data.get("archetypes", [])


def get_race_data(name: str):
    _, data = _find_json_by_name(RULES_RACES_DIR, name)
    return data


def get_class_data(name: str):
    _, data = _find_json_by_name(RULES_CLASSES_DIR, name)
    return data


def get_background_data(name: str):
    data = _load_json(ARCHIVE_BACKGROUNDS)
    if not data:
        return None
    for bg in data.get("backgrounds", []):
        if bg.get("name") == name:
            return bg
    return None


def get_trait_data(name: str):
    data = _load_json(ARCHIVE_TRAITS)
    if not data:
        return None
    for t in data.get("traits", []):
        if t.get("name") == name:
            return t
    return None


# ---------- Владения (proficiency) ----------
def get_character_proficiencies(char) -> dict:
    profs = {"weapons": set(), "armor": set()}
    try:
        current = get_current(char)
    except Exception:
        return profs
    for cls in current.get("classes", {}):
        data = get_class_data(cls)
        if not data:
            continue
        for w in data.get("weapon_proficiencies", []) or []:
            profs["weapons"].add(w)
        for a in data.get("armor_proficiencies", []) or []:
            profs["armor"].add(a)
    return profs


def has_weapon_proficiency(char, item) -> bool:
    subcat = item.get("subcategory")
    if not subcat:
        return True
    needed = WEAPON_PROFICIENCY_MAP.get(subcat)
    if not needed:
        return True
    profs = get_character_proficiencies(char)
    return needed in profs["weapons"]


# ---------- Заклинания ----------
def get_all_spells() -> list:
    data = _load_json(ARCHIVE_SPELLS)
    if not data:
        return []
    return data.get("spells", [])


def get_spell_data(name: str):
    for s in get_all_spells():
        if s.get("name") == name:
            return s
    return None


def get_spells_by_level(level: int) -> list:
    return [s for s in get_all_spells() if s.get("level", 0) == level]


def get_available_spell_levels() -> list:
    return sorted({int(s.get("level", 0)) for s in get_all_spells()})


# ---------- Навыки ----------
def _load_skills_from(category: str, name: str, level: int = 1, archetype=None):
    base = ARCHIVE_SKILLS_CLASSES if category == "classes" else ARCHIVE_SKILLS_RACES
    _, data = _find_json_by_name(base, name)
    if not data:
        return []
    result = []
    for s in data.get("skills", []):
        if s.get("level", 1) > level:
            continue
        s_arch = s.get("archetype")
        if s_arch and s_arch != archetype:
            continue
        result.append(dict(s))
    return result


# ---------- Ячейки заклинаний ----------
def _slots_for_level(classes: dict, char_level: int, archetype=None) -> dict:
    slots = {i: 0 for i in range(1, 10)}
    full_level = sum(lvl for cls, lvl in classes.items() if cls in FULL_CASTER_CLASSES)
    if full_level > 0:
        arr = FULL_CASTER_SLOTS.get(min(full_level, 20), [])
        for i, cnt in enumerate(arr, start=1):
            slots[i] += cnt
    half_level = sum(lvl for cls, lvl in classes.items() if cls in HALF_CASTER_CLASSES)
    if half_level > 0:
        arr = HALF_CASTER_SLOTS.get(min(half_level, 20), [])
        for i, cnt in enumerate(arr, start=1):
            slots[i] += cnt
    third_level = 0
    if archetype in THIRD_CASTER_ARCHETYPES:
        for cls, lvl in classes.items():
            if cls == THIRD_CASTER_CLASS:
                third_level += lvl // 3
    if third_level > 0:
        arr = THIRD_CASTER_SLOTS.get(min(third_level, 20), [])
        for i, cnt in enumerate(arr, start=1):
            slots[i] += cnt
    return slots


def _init_spell_slots(classes, char_level, archetype=None) -> dict:
    max_slots = _slots_for_level(classes, char_level, archetype)
    return {str(lvl): {"max": m, "current": m} for lvl, m in max_slots.items()}


# ---------- Ресурсы (ярость, второе дыхание и т.п.) ----------
_RAGE_USES = [0, 2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 6, 6, 6]


def _init_resources(classes: dict, level: int, archetype=None) -> dict:
    resources = {}
    for cls, lvl in classes.items():
        if cls == "Варвар":
            rage = _RAGE_USES[min(lvl, 20)]
            resources["Ярость"] = {"max": rage, "current": rage, "reset": "long"}
        elif cls == "Воин":
            resources["Второе дыхание"] = {"max": 1, "current": 1, "reset": "long"}
            if lvl >= 2:
                resources["Всплеск действий"] = {"max": 1, "current": 1, "reset": "short"}
    return resources


# ---------- Хиты ----------
def _get_hit_die(char_class: str) -> int:
    data = get_class_data(char_class)
    if data and "hit_die" in data:
        return data["hit_die"]
    return 8


def calculate_hp(char) -> int:
    classes = char["classes"]
    level = char["level"]
    stats = char["stats"]
    con_mod = (stats.get("Телосложение", 10) - 10) // 2
    total = 0
    starting_class = next(iter(classes), None)
    for cls, lvl in classes.items():
        hit_die = _get_hit_die(cls)
        if cls == starting_class:
            total += hit_die
            if lvl > 1:
                total += (lvl - 1) * (hit_die // 2 + 1)
        else:
            total += lvl * (hit_die // 2 + 1)
    total += con_mod * level
    return max(total, 1)


# ---------- XP и груз ----------
def get_char_xp(char) -> int:
    """Возвращает накопленный XP персонажа. Если поле отсутствует — выводим из уровня."""
    xp = char.get("xp")
    if xp is None:
        xp = XP_TABLE.get(char.get("current_level", 1), 0)
    return int(xp)


def level_from_xp(xp: int) -> int:
    level = 1
    for lvl in range(1, MAX_LEVEL + 1):
        if xp >= XP_TABLE[lvl]:
            level = lvl
    return level


def get_xp_for_level(level: int) -> int:
    return XP_TABLE.get(level, 0)


def get_xp_progress(char) -> tuple:
    current = char.get("current_level", 1)
    xp = get_char_xp(char)
    if current < MAX_LEVEL:
        return xp, XP_TABLE.get(current + 1)
    return xp, None


def get_max_carry_weight(stats: dict) -> int:
    return stats.get("Сила", 10) * 15


def get_pending_asi_levels(char) -> list:
    max_lvl = max(int(k) for k in char["levels"].keys())
    choices = char.get("asi_choices", {})
    return [lvl for lvl in ASI_LEVELS if lvl <= max_lvl and str(lvl) not in choices]


# ---------- AC (КД) ----------
def _has_unarmored_defense(char) -> bool:
    """Проверяет, есть ли у персонажа 'Защита без доспехов'."""
    classes = char.get("classes", {})
    if "Варвар" in classes:
        return True
    try:
        snap = get_current(char)
    except Exception:
        return False
    for s in snap.get("skills", []):
        if s.get("name") == "Защита без доспехов":
            return True
    return False


def _calc_ac(char) -> int:
    snap = get_current(char)
    dex_mod = (snap["stats"].get("Ловкость", 10) - 10) // 2
    con_mod = (snap["stats"].get("Телосложение", 10) - 10) // 2
    inv = char.get("inventory", {}) or {}
    items = inv.get("items", []) or []
    armor = None
    shield = None
    for it in items:
        slot = it.get("equipped_slot")
        if slot == "armor" and it.get("category") == "armor" and armor is None:
            armor = it
        elif (it.get("category") == "shield"
              and slot in ("melee_off", "ranged_off")
              and shield is None):
            shield = it
    if armor:
        ac = armor.get("ac_base", 10) + int(armor.get("enchantment", 0) or 0)
        dxt = armor.get("ac_dex", "full")
        if dxt == "full":
            ac += dex_mod
        elif dxt == "max2":
            ac += min(dex_mod, 2)
    else:
        # Без доспехов — учитываем Защиту без доспехов (варвар)
        if _has_unarmored_defense(char):
            ac = 10 + dex_mod + con_mod
        else:
            ac = 10 + dex_mod
    if shield:
        ac += (shield.get("ac_bonus", 2)
               + int(shield.get("enchantment", 0) or 0))
    return ac


# ---------- Характеристики ----------
def _ensure_alt_stats(char) -> None:
    if char.get("race_variant") != "alternative":
        return
    if "alt_stats" in char:
        return
    base = char.get("base_stats", {})
    lvl1 = char.get("levels", {}).get("1", {}).get("stats", {})
    alt = [stat for stat in ALL_STATS if lvl1.get(stat, 10) > base.get(stat, 10)]
    char["alt_stats"] = alt


def _ensure_alternative_race(char) -> None:
    if char.get("race_variant") != "alternative":
        return
    for snap in char.get("levels", {}).values():
        if "skills" in snap:
            snap["skills"] = [s for s in snap["skills"]
                              if s.get("name") != "Универсальность"]
        if "features" in snap:
            snap["features"] = [f for f in snap["features"]
                                if not (f.get("name") == "Универсальность"
                                        and f.get("source", "").startswith("Раса"))]


def _compute_stats(char, up_to_level: int) -> dict:
    stats = dict(char.get("base_stats", {}))
    race_data = get_race_data(char["race"])
    if char.get("race_variant") == "alternative":
        for stat in char.get("alt_stats", []):
            if stat in stats:
                stats[stat] += 1
    else:
        if race_data:
            for stat, bonus in race_data.get("ability_bonuses", {}).items():
                if stat in stats:
                    stats[stat] += bonus
    asi_choices = char.get("asi_choices", {})
    for asi_level in ASI_LEVELS:
        if asi_level > up_to_level:
            break
        choice = asi_choices.get(str(asi_level))
        if choice and choice.get("type") == "stats":
            for stat, bonus in choice.get("stat_bonuses", {}).items():
                if stat in stats:
                    stats[stat] = min(20, stats[stat] + bonus)
    return stats


def _rebuild(char, snapshot):
    level = snapshot["level"]
    archetype = char.get("archetype")

    snapshot["stats"] = _compute_stats(char, level)
    snapshot["proficiency_bonus"] = 2 + (level - 1) // 4

    skills = []
    if char.get("race_variant") != "alternative":
        skills.extend(_load_skills_from("races", char["race"], level))
    for cls, lvl in snapshot["classes"].items():
        skills.extend(_load_skills_from("classes", cls, lvl, archetype))

    bg = get_background_data(char["background"])
    if bg:
        for skill_name in bg.get("skill_proficiencies", []):
            skills.append({"name": skill_name,
                           "description": "Владение навыком (предыстория)",
                           "source": "background", "type": "passive"})
    for skill_name in char.get("extra_skills", []):
        skills.append({"name": skill_name,
                       "description": "Владение навыком (особенность)",
                       "source": "variant", "type": "passive"})
    seen = set()
    unique = []
    for s in skills:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    snapshot["skills"] = unique

    features = []
    race_data = get_race_data(char["race"])

    if race_data:
        variant = char.get("race_variant")
        if variant != "alternative":
            for f in race_data.get("features", []):
                features.append({**f, "source": f"Раса: {char['race']}"})

    if race_data and char.get("race_variant"):
        vinfo = race_data.get("variants", {}).get(char["race_variant"], {})
        for f in vinfo.get("features", []):
            features.append({**f,
                             "source": f"Раса: {char['race']} ({vinfo.get('name', '')})"})

    if bg and bg.get("feature"):
        features.append({**bg["feature"],
                         "source": f"Предыстория: {char['background']}"})

    for trait_name in char.get("traits", []):
        trait_data = get_trait_data(trait_name)
        if trait_data:
            features.append({
                "name": trait_data["name"],
                "description": trait_data.get("description", ""),
                "source": "Черта",
            })

    for asi_level in ASI_LEVELS:
        if asi_level > level:
            break
        choice = char.get("asi_choices", {}).get(str(asi_level))
        if choice and choice.get("type") == "feat":
            feat_name = choice.get("feat")
            trait_data = get_trait_data(feat_name) if feat_name else None
            if trait_data:
                features.append({
                    "name": trait_data["name"],
                    "description": trait_data.get("description", ""),
                    "source": f"Черта (ASI, ур. {asi_level})",
                })

    if archetype:
        for cls in snapshot["classes"]:
            arch_data = get_class_data(cls)
            if not arch_data:
                continue
            for arch in arch_data.get("archetypes", []):
                if arch.get("name") != archetype:
                    continue
                for f in arch.get("features", []):
                    if f.get("level", 1) <= snapshot["classes"][cls]:
                        features.append({
                            "name": f["name"],
                            "description": f.get("description", ""),
                            "source": f"Архетип: {archetype}",
                        })

    fs = char.get("fighting_style")
    if fs:
        for cls in snapshot["classes"]:
            cls_data = get_class_data(cls)
            if not cls_data:
                continue
            for style in cls_data.get("fighting_styles", []):
                if style.get("name") == fs:
                    features.append({
                        "name": f"Боевой стиль: {fs}",
                        "description": style.get("description", ""),
                        "source": "Боевой стиль",
                    })

    snapshot["features"] = features
    snapshot.setdefault("prepared_spells", [])

    # Ячейки заклинаний — сохраняем текущие значения
    old_slots = snapshot.get("spell_slots", {})
    new_slots = _init_spell_slots(
        snapshot["classes"], snapshot["level"], archetype)
    for lvl_str, info in new_slots.items():
        if lvl_str in old_slots:
            old_cur = old_slots[lvl_str].get("current",
                                             old_slots[lvl_str].get("max", 0))
            info["current"] = min(int(old_cur), info["max"])
    snapshot["spell_slots"] = new_slots

    # HP (максимум)
    snapshot["hp"] = calculate_hp({
        "classes": snapshot["classes"],
        "level": snapshot["level"],
        "stats": snapshot["stats"],
    })

    # Ресурсы (ярость и т.п.) — сохраняем текущие
    old_resources = snapshot.get("resources", {})
    new_resources = _init_resources(
        snapshot["classes"], snapshot["level"], archetype)
    for name, info in new_resources.items():
        if name in old_resources:
            old_cur = old_resources[name].get("current", info["max"])
            info["current"] = min(int(old_cur), info["max"])
    snapshot["resources"] = new_resources

    # Текущие и временные HP
    if "current_hp" not in snapshot:
        snapshot["current_hp"] = snapshot["hp"]
    else:
        snapshot["current_hp"] = min(int(snapshot["current_hp"]), snapshot["hp"])
    snapshot.setdefault("temp_hp", 0)


def _sync_top_level(char):
    current = get_current(char)
    char["current_level"] = current["level"]
    for key in ("level", "classes", "stats", "proficiency_bonus",
                "hp", "skills", "features", "spell_slots",
                "current_hp", "temp_hp", "resources"):
        if key in current:
            char[key] = current[key]
    char["prepared_spells"] = current.get("prepared_spells", [])


def _save_character(char):
    _sync_top_level(char)
    path = CHARACTERS_DIR / f"{char['codename']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(char, f, ensure_ascii=False, indent=2)


# ---------- Создание ----------
def create_character(name: str, race: str, char_class: str,
                     background: str, stats: dict,
                     race_variant=None, alt_stats=None,
                     alt_skills=None, alt_traits=None,
                     fighting_style=None,
                     existing_codename=None,
                     preselected_archetype=None) -> dict:
    codename = existing_codename if existing_codename else _generate_codename(name)
    base_stats = dict(stats)
    char = {
        "name": name,
        "codename": codename,
        "race": race,
        "background": background,
        "base_stats": base_stats,
        "alt_stats": list(alt_stats) if (race_variant == "alternative" and alt_stats) else [],
        "levels": {},
        "current_level": 1,
        "extra_skills": list(alt_skills or []),
        "traits": list(alt_traits or []),
        "race_variant": race_variant,
        "fighting_style": fighting_style,
        "archetype": preselected_archetype,
        "asi_choices": {},
        "xp": 0,
        "inventory": {
            "items": [],
            "coins": {"mm": 0, "sm": 0, "zm": 0, "pm": 0},
        },
    }
    snapshot = {
        "level": 1, "classes": {char_class: 1}, "stats": {},
        "proficiency_bonus": 0, "hp": 0, "skills": [], "features": [],
        "prepared_spells": [], "spell_slots": {},
    }
    char["levels"]["1"] = snapshot
    _rebuild(char, snapshot)
    _save_character(char)
    return char


# ---------- Загрузка / список ----------
def _migrate_equipment(char) -> None:
    inv = char.setdefault("inventory", {})
    inv.setdefault("items", [])
    for it in inv["items"]:
        try:
            it["enchantment"] = int(it.get("enchantment", 0) or 0)
        except (TypeError, ValueError):
            it["enchantment"] = 0
        slot = it.get("equipped_slot")
        if slot is None and it.get("equipped"):
            cat = it.get("category")
            if cat == "armor":
                it["equipped_slot"] = "armor"
            elif cat == "shield":
                it["equipped_slot"] = "melee_off"
            else:
                it["equipped_slot"] = None
        elif slot is not None and slot not in VALID_EQUIP_SLOTS:
            it["equipped_slot"] = None
        it.setdefault("equipped_slot", None)


def _migrate_combat_state(char) -> None:
    """Добавляет поля current_hp, temp_hp, resources, current в spell_slots."""
    for lvl_str, snap in char.get("levels", {}).items():
        snap.setdefault("current_hp", snap.get("hp", 1))
        snap.setdefault("temp_hp", 0)
        if "resources" not in snap:
            snap["resources"] = _init_resources(
                snap.get("classes", {}),
                snap.get("level", 1),
                char.get("archetype"),
            )
        for slot in snap.get("spell_slots", {}).values():
            slot.setdefault("current", slot.get("max", 0))


def load_character(codename: str):
    path = CHARACTERS_DIR / f"{codename}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        char = json.load(f)
    _ensure_alt_stats(char)
    _ensure_alternative_race(char)
    char.setdefault("asi_choices", {})
    char.setdefault("inventory", {"items": [], "coins": {"mm": 0, "sm": 0, "zm": 0, "pm": 0}})
    char["inventory"].setdefault("items", [])
    char["inventory"].setdefault("coins", {"mm": 0, "sm": 0, "zm": 0, "pm": 0})
    _migrate_equipment(char)
    _migrate_combat_state(char)
    if "xp" not in char:
        char["xp"] = XP_TABLE.get(char.get("current_level", 1), 0)
    return char


def list_characters():
    if not CHARACTERS_DIR.exists():
        return []
    result = []
    for p in sorted(CHARACTERS_DIR.glob("*.json")):
        try:
            data = _load_json(p)
        except Exception:
            continue
        if not data or "levels" not in data:
            continue
        result.append({
            "codename": p.stem,
            "name": data.get("name", p.stem),
            "level": data.get("level", 1),
            "race": data.get("race", "?"),
            "classes": data.get("classes", {}),
        })
    return result


# ---------- Просмотр ----------
def get_current(char) -> dict:
    return char["levels"][str(char["current_level"])]


def get_max_level(char) -> int:
    return max(int(k) for k in char["levels"].keys())


def get_character_skills(char) -> list:
    return get_current(char).get("skills", [])


def get_character_features(char) -> list:
    return get_current(char).get("features", [])


def get_character_prepared_spells(char) -> list:
    return get_current(char).get("prepared_spells", [])


# ---------- Подготовка заклинаний ----------
def toggle_prepared_spell(codename: str, spell_name: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    prepared = snap.setdefault("prepared_spells", [])
    if spell_name in prepared:
        prepared.remove(spell_name)
    else:
        if not get_spell_data(spell_name):
            raise ValueError(f"Заклинание «{spell_name}» не найдено.")
        prepared.append(spell_name)
    _save_character(char)
    return char


def get_spell_slots(char) -> dict:
    return get_current(char).get("spell_slots", {})


# ---------- Мультикласс ----------
def _check_multiclass_requirements(snapshot, new_class: str):
    data = get_class_data(new_class)
    if not data:
        return
    reqs = data.get("multiclass_requirements", {})
    stats = snapshot.get("stats", {})
    for stat, min_val in reqs.items():
        if stats.get(stat, 0) < min_val:
            raise ValueError(
                f"Для мультикласса в «{new_class}» требуется {stat} ≥ {min_val} "
                f"(у вас {stats.get(stat, 0)})."
            )


# ---------- Уровни ----------
def add_level(codename: str, char_class: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    levels = char["levels"]
    max_lvl = get_max_level(char)
    if max_lvl >= MAX_LEVEL:
        raise ValueError(f"Достигнут максимальный уровень ({MAX_LEVEL}).")
    new_lvl = max_lvl + 1
    max_snapshot = levels[str(max_lvl)]
    new_classes = dict(max_snapshot["classes"])
    if char_class in new_classes:
        new_classes[char_class] += 1
    else:
        _check_multiclass_requirements(max_snapshot, char_class)
        new_classes[char_class] = 1
    new_snapshot = {
        "level": new_lvl, "classes": new_classes, "stats": {},
        "proficiency_bonus": 0, "hp": 0, "skills": [], "features": [],
        "prepared_spells": list(max_snapshot.get("prepared_spells", [])),
        "spell_slots": {},
    }
    _rebuild(char, new_snapshot)
    levels[str(new_lvl)] = new_snapshot
    char["current_level"] = new_lvl
    # XP не опускается ниже порога для достигнутого уровня
    char["xp"] = max(get_char_xp(char), XP_TABLE.get(new_lvl, 0))
    _save_character(char)
    return char


def switch_level(codename: str, level: int) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if str(level) not in char["levels"]:
        raise ValueError(f"Уровень {level} недоступен.")
    char["current_level"] = level
    _save_character(char)
    return char


def reset_levels(codename: str, keep_above: bool = False) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    levels = char["levels"]
    if keep_above:
        current = char["current_level"]
        for lvl_str in list(levels.keys()):
            if int(lvl_str) > current:
                del levels[lvl_str]
    else:
        min_lvl = min(int(k) for k in levels.keys())
        for lvl_str in list(levels.keys()):
            if int(lvl_str) != min_lvl:
                del levels[lvl_str]
        char["current_level"] = min_lvl
        char["xp"] = XP_TABLE.get(min_lvl, 0)
    _save_character(char)
    return char


# ---------- Архетип и боевой стиль ----------
def set_archetype(codename: str, archetype: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    char["archetype"] = archetype
    for lvl_str, snap in char["levels"].items():
        _rebuild(char, snap)
    _save_character(char)
    return char


def set_fighting_style(codename: str, style: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    char["fighting_style"] = style
    for lvl_str, snap in char["levels"].items():
        _rebuild(char, snap)
    _save_character(char)
    return char


# ---------- ASI: характеристики или черта ----------
def _validate_asi_available(char, asi_level: int):
    max_lvl = get_max_level(char)
    if asi_level > max_lvl:
        raise ValueError(f"Уровень {asi_level} ещё не достигнут.")
    if asi_level not in ASI_LEVELS:
        raise ValueError(f"Уровень {asi_level} не даёт увеличения характеристик.")
    if str(asi_level) in char.get("asi_choices", {}):
        raise ValueError(f"Увеличение на уровне {asi_level} уже применено.")


def set_asi_stats(codename: str, asi_level: int, stat_bonuses: dict) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    _validate_asi_available(char, asi_level)

    if not stat_bonuses:
        raise ValueError("Не выбраны характеристики.")
    total = sum(stat_bonuses.values())
    if total != 2:
        raise ValueError("Сумма бонусов должна быть 2.")
    if len(stat_bonuses) > 2:
        raise ValueError("Можно выбрать не более двух характеристик.")
    if len(stat_bonuses) == 1 and list(stat_bonuses.values())[0] != 2:
        raise ValueError("При выборе одной характеристики бонус должен быть +2.")
    if len(stat_bonuses) == 2 and any(v != 1 for v in stat_bonuses.values()):
        raise ValueError("При выборе двух характеристик бонус каждой должен быть +1.")
    for stat in stat_bonuses:
        if stat not in ALL_STATS:
            raise ValueError(f"Неизвестная характеристика: {stat}")

    prev_lvl = asi_level - 1
    prev_snap = char["levels"].get(str(prev_lvl)) or char["levels"]["1"]
    prev_stats = prev_snap.get("stats", {})
    for stat, bonus in stat_bonuses.items():
        cur = prev_stats.get(stat, 10)
        if cur + bonus > 20:
            raise ValueError(
                f"{stat} не может превысить 20 (сейчас {cur}, бонус +{bonus}).")

    char.setdefault("asi_choices", {})[str(asi_level)] = {
        "type": "stats",
        "stat_bonuses": dict(stat_bonuses),
    }
    for lvl_str, snap in char["levels"].items():
        if int(lvl_str) >= asi_level:
            _rebuild(char, snap)
    _save_character(char)
    return char


def _taken_feat_names(char) -> set:
    taken = set(char.get("traits", []))
    for choice in char.get("asi_choices", {}).values():
        if choice.get("type") == "feat" and choice.get("feat"):
            taken.add(choice["feat"])
    return taken


def set_asi_feat(codename: str, asi_level: int, feat_name: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    _validate_asi_available(char, asi_level)

    trait = get_trait_data(feat_name)
    if not trait:
        raise ValueError(f"Черта «{feat_name}» не найдена.")
    if feat_name in _taken_feat_names(char):
        raise ValueError(f"Черта «{feat_name}» уже есть у персонажа.")

    char.setdefault("asi_choices", {})[str(asi_level)] = {
        "type": "feat",
        "feat": feat_name,
    }
    for lvl_str, snap in char["levels"].items():
        if int(lvl_str) >= asi_level:
            _rebuild(char, snap)
    _save_character(char)
    return char


# ---------- Боевое состояние ----------
def damage_character(codename: str, amount: int) -> dict:
    """Наносит урон. Сначала списываются временные хиты, затем основные."""
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if amount <= 0:
        raise ValueError("Урон должен быть положительным.")
    snap = get_current(char)
    temp = int(snap.get("temp_hp", 0) or 0)
    cur = int(snap.get("current_hp", snap.get("hp", 1)))
    if temp > 0:
        absorbed = min(temp, amount)
        temp -= absorbed
        amount -= absorbed
        snap["temp_hp"] = temp
    cur = max(0, cur - amount)
    snap["current_hp"] = cur
    _save_character(char)
    return char


def heal_character(codename: str, amount: int) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if amount <= 0:
        raise ValueError("Лечение должно быть положительным.")
    snap = get_current(char)
    cur = int(snap.get("current_hp", snap.get("hp", 1)))
    max_hp = int(snap["hp"])
    snap["current_hp"] = min(max_hp, cur + amount)
    _save_character(char)
    return char


def add_temp_hp(codename: str, amount: int) -> dict:
    """Временные хиты не складываются — берётся максимум."""
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if amount < 0:
        raise ValueError("Количество временных хитов не может быть отрицательным.")
    snap = get_current(char)
    current_temp = int(snap.get("temp_hp", 0) or 0)
    snap["temp_hp"] = max(current_temp, amount)
    _save_character(char)
    return char


def clear_temp_hp(codename: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    snap["temp_hp"] = 0
    _save_character(char)
    return char


def spend_resource(codename: str, resource_name: str, amount: int = 1) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    resources = snap.get("resources", {})
    if resource_name not in resources:
        raise ValueError(f"Ресурс «{resource_name}» не найден.")
    r = resources[resource_name]
    if r.get("current", 0) < amount:
        raise ValueError(
            f"Недостаточно «{resource_name}» (осталось {r.get('current', 0)}).")
    r["current"] = r["current"] - amount
    _save_character(char)
    return char


def restore_resource(codename: str, resource_name: str, amount: int = 1) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    resources = snap.get("resources", {})
    if resource_name not in resources:
        raise ValueError(f"Ресурс «{resource_name}» не найден.")
    r = resources[resource_name]
    r["current"] = min(r.get("max", 0), r.get("current", 0) + amount)
    _save_character(char)
    return char


def spend_spell_slot(codename: str, level: int, amount: int = 1) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    slots = snap.get("spell_slots", {})
    key = str(level)
    if key not in slots:
        raise ValueError(f"Ячейки уровня {level} недоступны.")
    info = slots[key]
    cur = info.get("current", info.get("max", 0))
    if cur < amount:
        raise ValueError(
            f"Недостаточно ячеек уровня {level} (осталось {cur}).")
    info["current"] = cur - amount
    _save_character(char)
    return char


def restore_spell_slot(codename: str, level: int, amount: int = 1) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    slots = snap.get("spell_slots", {})
    key = str(level)
    if key not in slots:
        raise ValueError(f"Ячейки уровня {level} недоступны.")
    info = slots[key]
    cur = info.get("current", info.get("max", 0))
    info["current"] = min(info.get("max", 0), cur + amount)
    _save_character(char)
    return char


def long_rest_character(codename: str) -> dict:
    """Долгий отдых: полные хиты, ячейки, ресурсы; временные хиты снимаются."""
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    snap["current_hp"] = int(snap["hp"])
    snap["temp_hp"] = 0
    for slot in snap.get("spell_slots", {}).values():
        slot["current"] = slot.get("max", 0)
    for r in snap.get("resources", {}).values():
        r["current"] = r.get("max", 0)
    _save_character(char)
    return char


# ---------- Опыт ----------
def add_xp(codename: str, amount: int) -> dict:
    """Начисляет опыт персонажу.

    Возвращает словарь с результатом:
      - char: обновлённый персонаж
      - old_level, new_level, target_level
      - xp_gained, old_xp, total_xp
      - advanced: True если current_level повышен
      - need_add_level: True если целевой уровень не добавлен в /characters
      - next_missing_level: номер первого недостающего уровня
    """
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if amount <= 0:
        raise ValueError("Опыт должен быть положительным.")

    old_xp = get_char_xp(char)
    new_xp = old_xp + amount
    char["xp"] = new_xp

    target_level = level_from_xp(new_xp)
    old_level = char.get("current_level", 1)
    available_levels = sorted(int(k) for k in char["levels"].keys())

    result = {
        "char": char,
        "old_level": old_level,
        "target_level": target_level,
        "new_level": old_level,
        "xp_gained": amount,
        "old_xp": old_xp,
        "total_xp": new_xp,
        "advanced": False,
        "need_add_level": False,
        "next_missing_level": None,
    }

    if target_level > old_level:
        candidates = [lvl for lvl in available_levels
                      if old_level < lvl <= target_level]
        if candidates:
            new_level = max(candidates)
            char["current_level"] = new_level
            result["new_level"] = new_level
            result["advanced"] = True

        missing = [lvl for lvl in range(old_level + 1, target_level + 1)
                   if lvl not in available_levels]
        if missing:
            result["need_add_level"] = True
            result["next_missing_level"] = missing[0]

    _save_character(char)
    return result


# ---------- Правка максимальных хитов уровня ----------
def set_level_max_hp(codename: str, level: int, hp: int) -> dict:
    """Устанавливает максимальное значение HP для указанного уровня."""
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    key = str(level)
    if key not in char["levels"]:
        raise ValueError(f"Уровень {level} не найден.")
    if hp < 1:
        raise ValueError("Хиты должны быть не меньше 1.")
    snap = char["levels"][key]
    old_hp = snap.get("hp", 1)
    snap["hp"] = hp
    if "current_hp" in snap:
        if snap["current_hp"] >= old_hp:
            # Если был на максимуме — поднимаем/опускаем текущие до нового максимума
            snap["current_hp"] = hp
        else:
            snap["current_hp"] = min(snap["current_hp"], hp)
    _save_character(char)
    return char


# ---------- Формат карточки ----------
def format_character(char) -> str:
    current = get_current(char)
    levels = char.get("levels", {})
    max_lvl = max((int(k) for k in levels.keys()), default=current["level"])
    classes_str = ", ".join(f"{c} {lvl}" for c, lvl in current["classes"].items())
    stats_str = ", ".join(f"{k}: {v}" for k, v in current["stats"].items())
    level_str = f"уровень {current['level']}"
    if max_lvl > current["level"]:
        level_str = f"уровень {current['level']} из {max_lvl}"

    prepared_count = len(current.get("prepared_spells", []))
    spells_line = f"\nЗаклинаний: {prepared_count}" if prepared_count else ""

    slots = current.get("spell_slots", {})
    slot_parts = []
    for lvl in sorted(int(k) for k in slots.keys()):
        data = slots[str(lvl)]
        mx = data.get("max", 0)
        if mx > 0:
            cur = data.get("current", mx)
            slot_parts.append(f"{lvl}ур {cur}/{mx}")
    slots_line = f"\n🔮 Ячейки: {', '.join(slot_parts)}" if slot_parts else ""

    resources = current.get("resources", {})
    res_parts = []
    for name, r in resources.items():
        mx = r.get("max", 0)
        if mx <= 0:
            continue
        cur = r.get("current", mx)
        res_parts.append(f"{name} {cur}/{mx}")
    resources_line = f"\n⚡ Ресурсы: {', '.join(res_parts)}" if res_parts else ""

    extra = ""
    if char.get("archetype"):
        suffix = " _(предварительно)_" if current["level"] < 3 else ""
        extra += f"\nАрхетип: {char['archetype']}{suffix}"
    if char.get("fighting_style"):
        extra += f"\nБоевой стиль: {char['fighting_style']}"

    xp, next_xp = get_xp_progress(char)
    if next_xp is None:
        xp_str = f"\n📊 Опыт: {xp} (макс.)"
    elif xp >= next_xp:
        xp_str = f"\n📊 Опыт: {xp} ⬆️ (следующий ур. доступен)"
    else:
        xp_str = f"\n📊 Опыт: {xp} / {next_xp}"

    carry = get_max_carry_weight(current["stats"])
    ac = _calc_ac(char)

    inv = char.get("inventory", {}) or {}
    inv_items = inv.get("items", []) or []
    weight = sum((it.get("weight") or 0) * it.get("quantity", 1) for it in inv_items)
    coins_str = _fmt_coins(inv.get("coins", {}))

    def _slot_find(s):
        for it in inv_items:
            if it.get("equipped_slot") == s:
                return it
        return None

    def _it_label(it):
        if not it:
            return "—"
        e = int(it.get("enchantment", 0) or 0)
        return f"{it['name']}{f' +{e}' if e else ''}"

    eq_melee_m = _slot_find("melee_main")
    eq_melee_o = _slot_find("melee_off")
    eq_ranged_m = _slot_find("ranged_main")
    eq_ranged_o = _slot_find("ranged_off")
    weapons_line = ""
    if eq_melee_m or eq_melee_o or eq_ranged_m or eq_ranged_o:
        weapons_line = (
            f"\n⚔️ Бл. бой: {_it_label(eq_melee_m)} / {_it_label(eq_melee_o)}"
            f"\n🏹 Дал. бой: {_it_label(eq_ranged_m)} / {_it_label(eq_ranged_o)}"
        )

    pending = get_pending_asi_levels(char)
    asi_note = ""
    if pending:
        asi_note = f"\n🎯 Увеличение характеристик (или черта): ур. {', '.join(map(str, pending))}"

    cur_hp = current.get("current_hp", current["hp"])
    max_hp = current["hp"]
    temp_hp = int(current.get("temp_hp", 0) or 0)
    hp_str = f"❤️ Хиты: {cur_hp}/{max_hp}"
    if temp_hp > 0:
        hp_str += f"  ✨ Вр: +{temp_hp}"

    return (
        f"📜 *{char['name']}* ({level_str})\n"
        f"Раса: {char['race']}\n"
        f"Класс: {classes_str}\n"
        f"Предыстория: {char['background']}"
        f"{extra}\n"
        f"{hp_str}  🛡 КД: {ac}\n"
        f"Бонус мастерства: +{current['proficiency_bonus']}"
        f"{spells_line}{slots_line}{resources_line}"
        f"{weapons_line}\n"
        f"⚖️ Грузоподъёмность: {carry} фнт | Инвентарь: {weight:.2f} фнт\n"
        f"💰 Монеты: {coins_str}"
        f"{xp_str}{asi_note}\n"
        f"Характеристики: {stats_str}"
    )


# ============================================================
#  FSM
# ============================================================
class CreateCharacter(StatesGroup):
    name = State()
    race = State()
    race_variant = State()
    alt_stats = State()
    alt_skill = State()
    alt_trait = State()
    char_class = State()
    fighting_style = State()
    archetype = State()
    background = State()
    background_confirm = State()
    stats = State()


class ASISelect(StatesGroup):
    plus1 = State()


class HPEdit(StatesGroup):
    value = State()


# ============================================================
#  Клавиатуры
# ============================================================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Создать персонажа", callback_data="create")],
        [InlineKeyboardButton(text="📂 Мои персонажи", callback_data="list")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_start")],
    ])


def race_keyboard():
    kb = [[InlineKeyboardButton(text=r, callback_data=f"race:{r}")]
          for r in get_available_races()]
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def class_keyboard():
    kb = [[InlineKeyboardButton(text=c, callback_data=f"class:{c}")]
          for c in get_available_classes()]
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def fighting_style_keyboard(char_class: str):
    styles = get_fighting_styles(char_class)
    kb = []
    for i, s in enumerate(styles):
        kb.append([InlineKeyboardButton(
            text=f"{s['name']} — {s.get('short', s.get('description', ''))[:40]}",
            callback_data=f"fstyle_view:{i}",
        )])
    kb.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data="fstyle_skip")])
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def background_keyboard():
    kb = [[InlineKeyboardButton(text=b, callback_data=f"bg_view:{b}")]
          for b in get_available_backgrounds()]
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def archetype_select_keyboard(char_class: str):
    archetypes = get_available_archetypes(char_class)
    kb = []
    for i, a in enumerate(archetypes):
        kb.append([InlineKeyboardButton(
            text=a["name"], callback_data=f"redo_arch_view:{i}")])
    kb.append([InlineKeyboardButton(text="⏭ Пропустить (выбрать позже)",
                                    callback_data="redo_arch_skip")])
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def stats_allocation_keyboard(stats: dict):
    kb = []
    for stat in ALL_STATS:
        val = stats.get(stat, 10)
        kb.append([
            InlineKeyboardButton(text="◀", callback_data=f"stat_dec:{stat}"),
            InlineKeyboardButton(text=f"{stat} {val}", callback_data=f"stat_reset:{stat}"),
            InlineKeyboardButton(text="▶", callback_data=f"stat_inc:{stat}"),
        ])
    kb.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data="stats_confirm")])
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def char_view_keyboard(codename: str, char=None):
    rows = [
        [InlineKeyboardButton(text="🎯 Навыки", callback_data=f"skills:{codename}")],
        [InlineKeyboardButton(text="✨ Умения", callback_data=f"features:{codename}")],
        [InlineKeyboardButton(text="📖 Заклинания", callback_data=f"spells:{codename}")],
        [InlineKeyboardButton(text="🔮 Ячейки заклинаний", callback_data=f"slots:{codename}")],
        [InlineKeyboardButton(text="📊 Уровни", callback_data=f"levels:{codename}")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data=f"items_char:{codename}")],
        [InlineKeyboardButton(text="❤️ Макс. хиты", callback_data=f"hp_edit:{codename}")],
    ]
    if char is not None and char.get("current_level", 1) >= 3 and not char.get("archetype"):
        rows.append([InlineKeyboardButton(
            text="🎖 Выбрать архетип", callback_data=f"select_archetype:{codename}")])
    if char is not None:
        pending = get_pending_asi_levels(char)
        for lvl in pending:
            rows.append([InlineKeyboardButton(
                text=f"🎯 ASI / черта (ур. {lvl})",
                callback_data=f"asi_menu:{codename}:{lvl}")])
    rows.append([InlineKeyboardButton(text="🔙 К списку", callback_data="list")])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def levels_keyboard(codename: str, char):
    current_lvl = char["current_level"]
    levels = sorted(int(k) for k in char["levels"].keys())
    kb = []
    row = []
    for lvl in levels:
        text = f"Ур. {lvl}"
        if lvl == current_lvl:
            text = f"✅ {text}"
        row.append(InlineKeyboardButton(
            text=text, callback_data=f"switch_lvl:{codename}:{lvl}"))
        if len(row) == 4:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(
        text="➕ Добавить уровень", callback_data=f"add_lvl:{codename}")])
    if len(levels) > 1:
        kb.append([InlineKeyboardButton(
            text="🗑 Сбросить уровни", callback_data=f"reset_lvls:{codename}")])
    kb.append([InlineKeyboardButton(
        text="🔙 К карточке", callback_data=f"view:{codename}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _collect_all_classes(char):
    max_lvl = max(int(k) for k in char["levels"].keys())
    current_classes = char["levels"][str(max_lvl)]["classes"]
    available = get_available_classes()
    all_classes = list(available)
    for c in current_classes:
        if c not in all_classes:
            all_classes.append(c)
    return all_classes, current_classes


def add_level_class_keyboard(codename: str, char):
    all_classes, current_classes = _collect_all_classes(char)
    kb = []
    for i, c in enumerate(all_classes):
        if c in current_classes:
            kb.append([InlineKeyboardButton(
                text=f"⬆️ {c} (сейчас {current_classes[c]})",
                callback_data=f"add_lvl_cls:{codename}:{i}",
            )])
        else:
            kb.append([InlineKeyboardButton(
                text=f"➕ {c} — мультикласс",
                callback_data=f"add_lvl_cls:{codename}:{i}",
            )])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"levels:{codename}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def reset_levels_keyboard(codename: str, char):
    current = char["current_level"]
    max_lvl = max(int(k) for k in char["levels"].keys())
    kb = []
    if max_lvl > current:
        kb.append([InlineKeyboardButton(
            text=f"🗑 Сбросить уровни выше {current}",
            callback_data=f"reset_lvls_above:{codename}")])
    kb.append([InlineKeyboardButton(
        text="🗑 Сбросить ВСЕ уровни (оставить 1)",
        callback_data=f"reset_lvls_all:{codename}")])
    kb.append([InlineKeyboardButton(
        text="🔄 Пересоздать (заново выбрать расу/класс/черты)",
        callback_data=f"redo_char:{codename}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"levels:{codename}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def race_variant_keyboard(race_data):
    variants = race_data.get("variants", {})
    kb = []
    for vid, vinfo in variants.items():
        kb.append([InlineKeyboardButton(
            text=vinfo.get("name", vid), callback_data=f"rvariant:{vid}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_race")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def alt_stats_keyboard(selected):
    kb = []
    for stat in ALL_STATS:
        mark = "✅" if stat in selected else "◻"
        kb.append([InlineKeyboardButton(text=f"{mark} {stat}",
                                        callback_data=f"alt_toggle:{stat}")])
    kb.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data="alt_stats_confirm")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_variant")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def alt_skill_keyboard():
    kb = [[InlineKeyboardButton(text=s, callback_data=f"alt_skill:{s}")]
          for s in ALL_SKILLS]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_alt_stats")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def alt_trait_keyboard():
    traits = get_available_traits()
    kb = [[InlineKeyboardButton(text=f"📖 {t}", callback_data=f"alt_trait_view:{i}")]
          for i, t in enumerate(traits)]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_alt_skill")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ============================================================
#  Handlers — вход в раздел
# ============================================================
@router.message(Command("characters"))
async def cmd_characters(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Раздел персонажей:", reply_markup=main_menu())


@router.callback_query(F.data == "main_characters")
async def cb_main_characters(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Раздел персонажей:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Раздел персонажей:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_cmd(callback: CallbackQuery):
    text = (
        "📖 *Как пользоваться ботом:*\n\n"
        "*Персонажи (раздел /characters):*\n"
        "1. «Создать персонажа» → имя, раса, класс, боевой стиль, предыстория, характеристики.\n"
        "2. В карточке: навыки, умения, заклинания, ячейки, уровни, инвентарь, макс. хиты.\n"
        "3. Архетип выбирается в карточке после 3 уровня.\n\n"
        "🎯 *Увеличение характеристик:* на 4, 8, 12, 16, 19 ур. можно взять\n"
        "  • +2 к одной характеристике, или\n"
        "  • +1 к двум, или\n"
        "  • *взять черту* вместо характеристик.\n\n"
        "❤️ *Макс. хиты* — редактируются в карточке персонажа для каждого уровня отдельно.\n\n"
        "🎒 *Предметы (раздел /items):*\n"
        "• Выберите персонажа → его инвентарь.\n"
        "• Добавляйте предметы из каталога, надевайте доспехи и щиты (влияет на КД).\n"
        "• *Экипировка по слотам:* armor / melee_main / melee_off / ranged_main / ranged_off.\n"
        "• *Зачарование +1…+5* задаётся при добавлении предмета.\n"
        "• Управляйте монетами — конвертация автоматическая.\n\n"
        "🏕 *Сессия (раздел /session):*\n"
        "• Лагерь с безлимитным сундуком.\n"
        "• Долгий отдых: 40 единиц сытости в сундуке лагеря, либо *сюжетный* без еды.\n"
        "• Передача монет и предметов между персонажами и лагерем.\n"
        "• Битва: урон (сначала списываются временные хиты), лечение, трата ячеек и ресурсов.\n"
        "• *Вне боя:* лечение/урон/ячейки/ресурсы + начисление опыта.\n"
        "  При получении опыта, если целевой уровень уже добавлен в /characters,\n"
        "  персонаж автоматически перескочит на него со всеми бонусами.\n"
        "  Если уровень не добавлен — бот предложит перейти в меню прокачки.\n\n"
        "⚖️ *Грузоподъёмность* = Сила × 15 фнт.\n\n"
        "🔄 *Пересоздание:* «Уровни» → «🗑 Сбросить уровни» → «🔄 Пересоздать»."
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu())
    await callback.answer()


# ============================================================
#  Создание персонажа
# ============================================================
@router.callback_query(F.data == "create")
async def create_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not get_available_races():
        await callback.message.edit_text("В проекте нет ни одного файла расы.",
                                         reply_markup=main_menu())
        await callback.answer()
        return
    await state.set_state(CreateCharacter.name)
    await callback.message.edit_text("Введите имя персонажа (можно с пробелами):")
    await callback.answer()


@router.message(CreateCharacter.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Попробуй ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(CreateCharacter.race)
    await message.answer(f"Отлично, {name}! Теперь выбери расу:",
                         reply_markup=race_keyboard())


@router.callback_query(F.data.startswith("race:"), CreateCharacter.race)
async def process_race(callback: CallbackQuery, state: FSMContext):
    race = callback.data.split(":", 1)[1]
    await state.update_data(race=race)
    race_data = get_race_data(race)
    if race_data and race_data.get("variants"):
        await state.set_state(CreateCharacter.race_variant)
        await callback.message.edit_text(
            f"Раса: {race}\n\nВыберите вариант особенностей:",
            reply_markup=race_variant_keyboard(race_data),
        )
        await callback.answer()
        return
    await _proceed_to_class(callback, state)


@router.callback_query(F.data == "back_to_race", CreateCharacter.race_variant)
async def back_to_race(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCharacter.race)
    await callback.message.edit_text("Выбери расу:", reply_markup=race_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("rvariant:"), CreateCharacter.race_variant)
async def process_race_variant(callback: CallbackQuery, state: FSMContext):
    variant = callback.data.split(":", 1)[1]
    data = await state.get_data()
    race = data.get("race")
    race_data = get_race_data(race) if race else None
    if not race_data or variant not in race_data.get("variants", {}):
        await callback.answer("Вариант недоступен", show_alert=True)
        return
    await state.update_data(race_variant=variant)
    vinfo = race_data["variants"][variant]
    if variant == "alternative":
        await state.update_data(alt_stats=[])
        await state.set_state(CreateCharacter.alt_stats)
        await callback.message.edit_text(
            f"*{vinfo['name']}*\n\n{vinfo.get('description', '')}\n\n"
            f"Выберите две разные характеристики для +1:",
            parse_mode="Markdown",
            reply_markup=alt_stats_keyboard([]),
        )
    else:
        await _proceed_to_class(callback, state)
    await callback.answer()


@router.callback_query(F.data == "back_to_variant", CreateCharacter.alt_stats)
async def back_to_variant(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    race = data.get("race")
    race_data = get_race_data(race) if race else None
    if not race_data or not race_data.get("variants"):
        await callback.answer("Варианты недоступны", show_alert=True)
        return
    await state.set_state(CreateCharacter.race_variant)
    await callback.message.edit_text("Выберите вариант особенностей:",
                                     reply_markup=race_variant_keyboard(race_data))
    await callback.answer()


@router.callback_query(F.data.startswith("alt_toggle:"), CreateCharacter.alt_stats)
async def alt_toggle_stat(callback: CallbackQuery, state: FSMContext):
    stat = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = list(data.get("alt_stats", []))
    if stat in selected:
        selected.remove(stat)
    else:
        if len(selected) >= 2:
            await callback.answer("Можно выбрать только 2 характеристики", show_alert=True)
            return
        selected.append(stat)
    await state.update_data(alt_stats=selected)
    await callback.message.edit_reply_markup(reply_markup=alt_stats_keyboard(selected))
    await callback.answer()


@router.callback_query(F.data == "alt_stats_confirm", CreateCharacter.alt_stats)
async def alt_stats_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("alt_stats", [])
    if len(selected) != 2:
        await callback.answer("Выберите ровно 2 характеристики", show_alert=True)
        return
    await state.set_state(CreateCharacter.alt_skill)
    await callback.message.edit_text(
        "Выберите навык, которым будет владеть персонаж:",
        reply_markup=alt_skill_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_alt_stats", CreateCharacter.alt_skill)
async def back_to_alt_stats(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("alt_stats", [])
    await state.set_state(CreateCharacter.alt_stats)
    await callback.message.edit_text(
        "Выберите две разные характеристики для +1:",
        reply_markup=alt_stats_keyboard(selected))
    await callback.answer()


@router.callback_query(F.data.startswith("alt_skill:"), CreateCharacter.alt_skill)
async def alt_skill_select(callback: CallbackQuery, state: FSMContext):
    skill = callback.data.split(":", 1)[1]
    if skill not in ALL_SKILLS:
        await callback.answer("Навык не найден", show_alert=True)
        return
    await state.update_data(alt_skill=skill)
    await state.set_state(CreateCharacter.alt_trait)
    await callback.message.edit_text(
        f"Навык: {skill}.\n\nВыберите черту (нажмите для просмотра):",
        reply_markup=alt_trait_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_alt_skill", CreateCharacter.alt_trait)
async def back_to_alt_skill(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCharacter.alt_skill)
    await callback.message.edit_text(
        "Выберите навык, которым будет владеть персонаж:",
        reply_markup=alt_skill_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("alt_trait_view:"), CreateCharacter.alt_trait)
async def alt_trait_view(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]
    try:
        idx = int(raw)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    traits = get_available_traits()
    if idx < 0 or idx >= len(traits):
        await callback.answer("Черта не найдена", show_alert=True)
        return
    trait_name = traits[idx]
    trait = get_trait_data(trait_name)
    if not trait:
        await callback.answer("Черта не найдена", show_alert=True)
        return
    await state.update_data(viewed_trait=trait_name)
    text = f"📖 *{trait['name']}*\n\n{trait.get('description', '')}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выбрать эту черту", callback_data="alt_trait_pick")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="back_to_trait_list")],
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "back_to_trait_list", CreateCharacter.alt_trait)
async def back_to_trait_list(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите черту (нажмите для просмотра описания):",
        reply_markup=alt_trait_keyboard())
    await callback.answer()


@router.callback_query(F.data == "alt_trait_pick", CreateCharacter.alt_trait)
async def alt_trait_select(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    trait = data.get("viewed_trait")
    if not trait or trait not in get_available_traits():
        await callback.answer("Черта не выбрана", show_alert=True)
        return
    await state.update_data(alt_trait=trait)
    await _proceed_to_class(callback, state)


async def _proceed_to_class(callback: CallbackQuery, state: FSMContext):
    if not get_available_classes():
        await callback.message.edit_text("В проекте нет ни одного файла класса.",
                                         reply_markup=main_menu())
        await state.clear()
        await callback.answer()
        return
    await state.set_state(CreateCharacter.char_class)
    data = await state.get_data()
    race = data.get("race", "")
    await callback.message.edit_text(
        f"Раса: {race}. Теперь выбери класс:",
        reply_markup=class_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("class:"), CreateCharacter.char_class)
async def process_class(callback: CallbackQuery, state: FSMContext):
    try:
        char_class = callback.data.split(":", 1)[1]
        await state.update_data(char_class=char_class)
        styles = get_fighting_styles(char_class)
        if styles:
            await state.set_state(CreateCharacter.fighting_style)
            await callback.message.edit_text(
                f"Класс: {char_class}.\n\nВыберите боевой стиль:",
                reply_markup=fighting_style_keyboard(char_class))
            await callback.answer()
            return
        await _proceed_to_archetype_or_background(callback, state)
    except Exception as e:
        logging.exception("process_class error")
        try:
            await callback.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass


@router.callback_query(F.data.startswith("fstyle_view:"), CreateCharacter.fighting_style)
async def fstyle_view(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]
    try:
        idx = int(raw)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    data = await state.get_data()
    char_class = data.get("char_class")
    styles = get_fighting_styles(char_class) if char_class else []
    if idx < 0 or idx >= len(styles):
        await callback.answer("Стиль не найден", show_alert=True)
        return
    style = styles[idx]
    await state.update_data(viewed_style=style["name"])
    text = f"⚔️ *{style['name']}*\n\n{style.get('description', '')}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выбрать", callback_data="fstyle_pick")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="fstyle_back")],
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "fstyle_back", CreateCharacter.fighting_style)
async def fstyle_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    char_class = data.get("char_class")
    await callback.message.edit_text(
        f"Класс: {char_class}.\n\nВыберите боевой стиль:",
        reply_markup=fighting_style_keyboard(char_class))
    await callback.answer()


@router.callback_query(F.data == "fstyle_pick", CreateCharacter.fighting_style)
async def fstyle_pick(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    style_name = data.get("viewed_style")
    if not style_name:
        await callback.answer("Стиль не выбран", show_alert=True)
        return
    await state.update_data(fighting_style=style_name)
    await _proceed_to_archetype_or_background(callback, state)


@router.callback_query(F.data == "fstyle_skip", CreateCharacter.fighting_style)
async def fstyle_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fighting_style=None)
    await _proceed_to_archetype_or_background(callback, state)


async def _proceed_to_archetype_or_background(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    char_class = data.get("char_class")
    redo_codename = data.get("redo_codename")
    if redo_codename and char_class:
        archetypes = get_available_archetypes(char_class)
        if archetypes:
            await state.set_state(CreateCharacter.archetype)
            await callback.message.edit_text(
                f"🎖 *{char_class}* — выберите архетип.\n\n"
                f"Можно пропустить и выбрать позже через карточку.",
                parse_mode="Markdown",
                reply_markup=archetype_select_keyboard(char_class))
            await callback.answer()
            return
    await _proceed_to_background(callback, state)


@router.callback_query(F.data.startswith("redo_arch_view:"), CreateCharacter.archetype)
async def redo_arch_view(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]
    try:
        idx = int(raw)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    data = await state.get_data()
    char_class = data.get("char_class")
    archetypes = get_available_archetypes(char_class) if char_class else []
    if idx < 0 or idx >= len(archetypes):
        await callback.answer("Архетип не найден", show_alert=True)
        return
    arch = archetypes[idx]
    text = f"🎖 *{arch['name']}*\n\n{arch.get('description', '')}\n"
    for f in arch.get("features", []):
        text += f"\n*{f['name']}* (ур. {f.get('level', '?')})\n{f.get('description', '')}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выбрать этот архетип",
                              callback_data=f"redo_arch_pick:{idx}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="redo_arch_back")],
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "redo_arch_back", CreateCharacter.archetype)
async def redo_arch_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    char_class = data.get("char_class")
    await callback.message.edit_text(
        f"🎖 *{char_class}* — выберите архетип.",
        parse_mode="Markdown",
        reply_markup=archetype_select_keyboard(char_class))
    await callback.answer()


@router.callback_query(F.data.startswith("redo_arch_pick:"), CreateCharacter.archetype)
async def redo_arch_pick(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]
    try:
        idx = int(raw)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    data = await state.get_data()
    char_class = data.get("char_class")
    archetypes = get_available_archetypes(char_class) if char_class else []
    if idx < 0 or idx >= len(archetypes):
        await callback.answer("Архетип не найден", show_alert=True)
        return
    await state.update_data(preselected_archetype=archetypes[idx]["name"])
    await _proceed_to_background(callback, state)


@router.callback_query(F.data == "redo_arch_skip", CreateCharacter.archetype)
async def redo_arch_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(preselected_archetype=None)
    await _proceed_to_background(callback, state)


async def _proceed_to_background(callback: CallbackQuery, state: FSMContext):
    if not get_available_backgrounds():
        await callback.message.edit_text("В проекте нет ни одной предыстории.",
                                         reply_markup=main_menu())
        await state.clear()
        await callback.answer()
        return
    await state.set_state(CreateCharacter.background)
    data = await state.get_data()
    char_class = data.get("char_class", "")
    await callback.message.edit_text(
        f"Класс: {char_class}. Теперь выбери предысторию:",
        reply_markup=background_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("bg_view:"), CreateCharacter.background)
async def view_background(callback: CallbackQuery, state: FSMContext):
    bg_name = callback.data.split(":", 1)[1]
    bg = get_background_data(bg_name)
    if not bg:
        await callback.answer("Предыстория не найдена", show_alert=True)
        return
    await state.update_data(background=bg_name)
    await state.set_state(CreateCharacter.background_confirm)
    skills = ", ".join(bg.get("skill_proficiencies", [])) or "—"
    tools = ", ".join(bg.get("tool_proficiencies", [])) or "—"
    text = (f"📖 *{bg['name']}*\n\n{bg.get('description', '')}\n\n"
            f"*Владения навыками:* {skills}\n"
            f"*Владения инструментами:* {tools}\n")
    if bg.get("languages"):
        text += f"*Языки:* +{bg['languages']}\n"
    if bg.get("feature"):
        text += f"\n*Умение:* {bg['feature']['name']}\n{bg['feature']['description']}"
    if bg.get("equipment"):
        text += f"\n\n*Снаряжение:* {', '.join(bg['equipment'])}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"bg_confirm:{bg_name}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="bg_list")],
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "bg_list", CreateCharacter.background_confirm)
async def back_to_bg_list(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCharacter.background)
    await callback.message.edit_text("Выбери предысторию:", reply_markup=background_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("bg_confirm:"), CreateCharacter.background_confirm)
async def confirm_background(callback: CallbackQuery, state: FSMContext):
    bg = callback.data.split(":", 1)[1]
    stats = {s: 10 for s in ALL_STATS}
    await state.update_data(background=bg, stats=stats)
    await state.set_state(CreateCharacter.stats)
    await callback.message.edit_text(
        "Распредели характеристики.\n"
        "◀ / ▶ — изменить на 1, нажатие на название — сброс к 10.\n\n"
        "Когда закончишь — нажми «✅ Подтвердить».",
        reply_markup=stats_allocation_keyboard(stats))
    await callback.answer()


@router.callback_query(F.data.startswith("stat_"), CreateCharacter.stats)
async def process_stat_change(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 1)
    action = parts[0]
    stat = parts[1] if len(parts) > 1 else None
    if not stat or stat not in ALL_STATS:
        await callback.answer()
        return
    data = await state.get_data()
    stats = data.get("stats") or {s: 10 for s in ALL_STATS}
    if action == "stat_inc":
        stats[stat] = min(20, stats[stat] + 1)
    elif action == "stat_dec":
        stats[stat] = max(1, stats[stat] - 1)
    elif action == "stat_reset":
        stats[stat] = 10
    await state.update_data(stats=stats)
    await callback.message.edit_reply_markup(reply_markup=stats_allocation_keyboard(stats))
    await callback.answer()


@router.callback_query(F.data == "stats_confirm", CreateCharacter.stats)
async def process_stats_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        alt_skills = [data["alt_skill"]] if data.get("alt_skill") else []
        alt_traits = [data["alt_trait"]] if data.get("alt_trait") else []
        char = create_character(
            name=data["name"], race=data["race"], char_class=data["char_class"],
            background=data["background"], stats=data["stats"],
            race_variant=data.get("race_variant"),
            alt_stats=data.get("alt_stats"),
            alt_skills=alt_skills, alt_traits=alt_traits,
            fighting_style=data.get("fighting_style"),
            existing_codename=data.get("redo_codename"),
            preselected_archetype=data.get("preselected_archetype"))
        await state.clear()
        title = (f"✅ Персонаж *{char['name']}* пересоздан заново!\n"
                 if data.get("redo_codename")
                 else f"✅ Персонаж *{char['name']}* создан!\n")
        text = f"{title}Файл: `characters/{char['codename']}.json`\n\n{format_character(char)}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Открыть карточку", callback_data=f"view:{char['codename']}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
        ])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logging.exception("create_character error")
        await callback.message.edit_text(f"Ошибка: {e}", reply_markup=main_menu())
    await callback.answer()


# ============================================================
#  Список и карточка
# ============================================================
@router.callback_query(F.data == "list")
async def list_chars(callback: CallbackQuery):
    chars = list_characters()
    if not chars:
        await callback.message.edit_text("У тебя пока нет сохранённых персонажей.",
                                         reply_markup=main_menu())
        await callback.answer()
        return
    kb = []
    for c in chars:
        classes_str = ", ".join(f"{k} {v}" for k, v in c["classes"].items())
        kb.append([InlineKeyboardButton(
            text=f"{c['name']} — {classes_str}", callback_data=f"view:{c['codename']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    await callback.message.edit_text("Выбери персонажа:",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("view:"))
async def view_character(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    await callback.message.edit_text(
        format_character(char), parse_mode="Markdown",
        reply_markup=char_view_keyboard(codename, char))
    await callback.answer()


# ============================================================
#  Редактирование максимальных хитов
# ============================================================
@router.callback_query(F.data.startswith("hp_edit:"))
async def hp_edit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    levels = sorted(int(k) for k in char["levels"].keys())
    cur_lvl = char["current_level"]
    kb = []
    for lvl in levels:
        hp_val = char["levels"][str(lvl)].get("hp", 0)
        mark = " ✅" if lvl == cur_lvl else ""
        kb.append([InlineKeyboardButton(
            text=f"Ур. {lvl}: {hp_val} HP{mark}",
            callback_data=f"hp_edit_lvl:{codename}:{lvl}")])
    kb.append([InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")])
    await callback.message.edit_text(
        f"❤️ *Максимальные хиты — {char['name']}*\n\n"
        f"Выберите уровень для редактирования:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("hp_edit_lvl:"))
async def hp_edit_lvl(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        lvl = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char or str(lvl) not in char["levels"]:
        await callback.answer("Уровень не найден", show_alert=True)
        return
    current_hp = char["levels"][str(lvl)].get("hp", 1)
    await state.update_data(hp_edit_codename=codename, hp_edit_level=lvl)
    await state.set_state(HPEdit.value)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"hp_edit:{codename}")]])
    await callback.message.edit_text(
        f"❤️ Уровень {lvl}: текущий максимум *{current_hp}* HP.\n\n"
        f"Введите новое значение (целое, ≥ 1):",
        parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.message(HPEdit.value)
async def hp_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    codename = data.get("hp_edit_codename")
    lvl = data.get("hp_edit_level")
    if not codename or lvl is None:
        await state.clear()
        await message.answer("Сессия истекла, начните заново.")
        return
    try:
        new_hp = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    if new_hp < 1:
        await message.answer("Хиты должны быть ≥ 1.")
        return
    try:
        char = set_level_max_hp(codename, lvl, new_hp)
    except ValueError as e:
        await state.clear()
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()
    await message.answer(
        f"✅ Максимум хитов для уровня {lvl} установлен: *{new_hp}*.\n\n"
        f"Текущие: {char['levels'][str(lvl)].get('current_hp', '?')}/{new_hp}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Ещё изменить", callback_data=f"hp_edit:{codename}")],
            [InlineKeyboardButton(text="👤 К карточке", callback_data=f"view:{codename}")],
        ]))


# ============================================================
#  Архетип из карточки
# ============================================================
@router.callback_query(F.data.startswith("select_archetype:"))
async def select_archetype(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    archetypes = []
    for cls in char.get("classes", {}):
        archetypes = get_available_archetypes(cls)
        if archetypes:
            break
    if not archetypes:
        await callback.answer("Для вашего класса нет архетипов", show_alert=True)
        return
    kb = []
    for i, a in enumerate(archetypes):
        kb.append([InlineKeyboardButton(text=a["name"],
                                        callback_data=f"arch_view:{codename}:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")])
    await callback.message.edit_text(
        "🎖 *Выбор архетипа*\n\nВыберите архетип для вашего класса:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("arch_view:"))
async def arch_view(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, idx_s = parts[1], parts[2]
    try:
        idx = int(idx_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    archetypes = []
    for cls in char.get("classes", {}):
        archetypes = get_available_archetypes(cls)
        if archetypes:
            break
    if idx < 0 or idx >= len(archetypes):
        await callback.answer("Архетип не найден", show_alert=True)
        return
    arch_data = archetypes[idx]
    text = f"🎖 *{arch_data['name']}*\n\n{arch_data.get('description', '')}\n"
    for f in arch_data.get("features", []):
        text += f"\n*{f['name']}* (ур. {f.get('level', '?')})\n{f.get('description', '')}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выбрать этот архетип",
                              callback_data=f"arch_pick:{codename}:{idx}")],
        [InlineKeyboardButton(text="🔙 Назад",
                              callback_data=f"select_archetype:{codename}")],
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("arch_pick:"))
async def arch_pick(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, idx_s = parts[1], parts[2]
    try:
        idx = int(idx_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    archetypes = []
    for cls in char.get("classes", {}):
        archetypes = get_available_archetypes(cls)
        if archetypes:
            break
    if idx < 0 or idx >= len(archetypes):
        await callback.answer("Архетип не найден", show_alert=True)
        return
    arch_name = archetypes[idx]["name"]
    try:
        char = set_archetype(codename, arch_name)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.message.edit_text(
        f"✅ Архетип *{arch_name}* выбран.\n\n{format_character(char)}",
        parse_mode="Markdown", reply_markup=char_view_keyboard(codename, char))
    await callback.answer()


# ============================================================
#  Навыки / умения
# ============================================================
@router.callback_query(F.data.startswith("skills:"))
async def view_skills(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    skills = get_character_skills(char)
    if not skills:
        text = "У персонажа пока нет навыков."
    else:
        text = "🎯 *Навыки:*\n\n"
        for s in skills:
            text += f"• *{s['name']}*"
            if s.get("type"):
                text += f" _{s['type']}_"
            text += f"\n{s.get('description', '')}\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")]])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("features:"))
async def view_features(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    features = get_character_features(char)
    if not features:
        text = "У персонажа пока нет умений."
    else:
        text = "✨ *Умения и особенности:*\n\n"
        for f in features:
            text += f"• *{f['name']}*"
            if f.get("source"):
                text += f" _({f['source']})_"
            text += f"\n{f.get('description', '')}\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")]])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


# ============================================================
#  Заклинания
# ============================================================
def _format_spell(sp: dict) -> str:
    lvl = sp.get("level", 0)
    lvl_str = "Заговор" if lvl == 0 else f"{lvl} уровень"
    text = f"📖 *{sp['name']}*\n_{lvl_str}, {sp.get('school', '—')}_\n\n"
    text += f"*Время накладывания:* {sp.get('casting_time', '—')}\n"
    text += f"*Дистанция:* {sp.get('range', '—')}\n"
    text += f"*Компоненты:* {sp.get('components', '—')}\n"
    text += f"*Длительность:* {sp.get('duration', '—')}\n"
    if sp.get("damage"):
        dmg = sp["damage"]
        text += f"*Урон:* {dmg.get('dice', '—')} ({dmg.get('type', '—')})\n"
    if sp.get("classes"):
        text += f"*Классы:* {', '.join(sp['classes'])}\n"
    text += f"\n{sp.get('description', '')}"
    return text


@router.callback_query(F.data.startswith("spells:"))
async def view_character_spells(callback: CallbackQuery):
    parts = callback.data.split(":", 1)
    if len(parts) < 2 or not parts[1]:
        await callback.answer()
        return
    codename = parts[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    prepared = get_character_prepared_spells(char)
    text = f"📖 *Заклинания {char['name']}* (уровень {char['current_level']})\n\n"
    kb = []
    if not prepared:
        text += "_Заклинания не подготовлены._\n"
    else:
        by_lvl = {}
        for name in prepared:
            sp = get_spell_data(name)
            if sp:
                by_lvl.setdefault(sp.get("level", 0), []).append(name)
        for lvl in sorted(by_lvl.keys()):
            lvl_name = "Заговоры" if lvl == 0 else f"{lvl} уровень"
            text += f"*{lvl_name}:*\n"
            level_spells = get_spells_by_level(lvl)
            for name in by_lvl[lvl]:
                idx = None
                for i, s in enumerate(level_spells):
                    if s["name"] == name:
                        idx = i
                        break
                text += f"• {name}\n"
                if idx is not None:
                    kb.append([InlineKeyboardButton(
                        text=f"📖 {name}",
                        callback_data=f"spell_view:{codename}:{lvl}:{idx}")])
            text += "\n"
    kb.append([InlineKeyboardButton(text="⚙️ Управление заклинаниями",
                                    callback_data=f"spells_manage:{codename}")])
    kb.append([InlineKeyboardButton(text="🔮 Ячейки заклинаний",
                                    callback_data=f"slots:{codename}")])
    kb.append([InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")])
    await callback.message.edit_text(text, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("spells_manage:"))
async def spells_manage_levels(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    levels = get_available_spell_levels()
    if not levels:
        await callback.answer("Список заклинаний пуст", show_alert=True)
        return
    kb = []
    for lvl in levels:
        lvl_name = "Заговоры" if lvl == 0 else f"{lvl} уровень"
        count = len(get_spells_by_level(lvl))
        kb.append([InlineKeyboardButton(text=f"{lvl_name} ({count})",
                                        callback_data=f"spells_lvl:{codename}:{lvl}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"spells:{codename}")])
    await callback.message.edit_text(
        f"*Управление заклинаниями {char['name']}*\n\nВыберите уровень.\n"
        f"✅ — уже подготовлено.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("spells_lvl:"))
async def spells_show_level(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    codename, lvl_s = parts[1], parts[2]
    try:
        lvl = int(lvl_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    prepared = set(get_character_prepared_spells(char))
    spells = get_spells_by_level(lvl)
    if not spells:
        await callback.answer("Нет заклинаний этого уровня", show_alert=True)
        return
    kb = []
    for i, sp in enumerate(spells):
        mark = "✅ " if sp["name"] in prepared else "◻ "
        kb.append([InlineKeyboardButton(
            text=f"{mark}{sp['name']}",
            callback_data=f"spell_view:{codename}:{lvl}:{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"spells_manage:{codename}")])
    lvl_name = "Заговоры" if lvl == 0 else f"{lvl} уровень"
    await callback.message.edit_text(
        f"*{lvl_name}*\n\n✅ — подготовлено, ◻ — нет.\nНажмите на заклинание.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("spell_view:"))
async def spell_view(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename, lvl_s, idx_s = parts[1], parts[2], parts[3]
    try:
        lvl = int(lvl_s); idx = int(idx_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    spells = get_spells_by_level(lvl)
    if idx < 0 or idx >= len(spells):
        await callback.answer("Заклинание не найдено", show_alert=True)
        return
    sp = spells[idx]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    prepared = get_character_prepared_spells(char)
    is_prep = sp["name"] in prepared
    toggle_text = "➖ Убрать из подготовленных" if is_prep else "✅ Подготовить"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text,
                              callback_data=f"spell_toggle:{codename}:{lvl}:{idx}")],
        [InlineKeyboardButton(text="🔙 К списку",
                              callback_data=f"spells_lvl:{codename}:{lvl}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")],
    ])
    await callback.message.edit_text(_format_spell(sp), parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("spell_toggle:"))
async def spell_toggle(callback: CallbackQuery):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename, lvl_s, idx_s = parts[1], parts[2], parts[3]
    try:
        lvl = int(lvl_s); idx = int(idx_s)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    spells = get_spells_by_level(lvl)
    if idx < 0 or idx >= len(spells):
        await callback.answer("Заклинание не найдено", show_alert=True)
        return
    sp = spells[idx]
    try:
        char = toggle_prepared_spell(codename, sp["name"])
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    prepared = get_character_prepared_spells(char)
    is_prep = sp["name"] in prepared
    toggle_text = "➖ Убрать из подготовленных" if is_prep else "✅ Подготовить"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text,
                              callback_data=f"spell_toggle:{codename}:{lvl}:{idx}")],
        [InlineKeyboardButton(text="🔙 К списку",
                              callback_data=f"spells_lvl:{codename}:{lvl}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")],
    ])
    await callback.message.edit_text(_format_spell(sp), parse_mode="Markdown", reply_markup=kb)
    await callback.answer("Заклинание подготовлено" if is_prep else "Заклинание убрано")


@router.callback_query(F.data.startswith("slots:"))
async def view_slots(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    slots = get_spell_slots(char)
    if not slots:
        text = "🔮 *Ячейки заклинаний*\n\n_У персонажа нет ячеек заклинаний._"
    else:
        text = "🔮 *Ячейки заклинаний*\n\n"
        any_slots = False
        for lvl in sorted(int(k) for k in slots.keys()):
            data = slots[str(lvl)]
            mx = data.get("max", 0)
            if mx <= 0:
                continue
            any_slots = True
            cur = data.get("current", mx)
            text += f"Ур. {lvl}: {cur}/{mx}\n"
        if not any_slots:
            text += "_Нет доступных ячеек._"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")]])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


# ============================================================
#  Уровни
# ============================================================
@router.callback_query(F.data.startswith("levels:"))
async def view_levels(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    extra = f"\nАрхетип: *{char['archetype']}*" if char.get("archetype") else ""
    await callback.message.edit_text(
        f"📊 *Уровни {char['name']}*\n\n"
        f"Текущий уровень: *{char['current_level']}*{extra}\n\n"
        f"Нажми на уровень, чтобы переключиться.",
        parse_mode="Markdown", reply_markup=levels_keyboard(codename, char))
    await callback.answer()


@router.callback_query(F.data.startswith("switch_lvl:"))
async def switch_level_cb(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    try:
        char = switch_level(codename, level)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.message.edit_text(
        f"📊 *Уровни {char['name']}*\n\nТекущий: *{char['current_level']}*\n\n"
        f"{format_character(char)}",
        parse_mode="Markdown", reply_markup=levels_keyboard(codename, char))
    await callback.answer(f"Активирован уровень {level}")


@router.callback_query(F.data.startswith("add_lvl:"))
async def add_level_cb(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    max_lvl = max(int(k) for k in char["levels"].keys())
    if max_lvl >= 20:
        await callback.answer("Достигнут максимальный уровень (20)", show_alert=True)
        return
    await callback.message.edit_text(
        f"Добавление уровня {max_lvl + 1}. Выбери класс:",
        reply_markup=add_level_class_keyboard(codename, char))
    await callback.answer()


@router.callback_query(F.data.startswith("add_lvl_cls:"))
async def add_level_class_cb(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    codename = parts[1]
    try:
        idx = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    all_classes, _ = _collect_all_classes(char)
    if idx < 0 or idx >= len(all_classes):
        await callback.answer("Класс недоступен", show_alert=True)
        return
    cls = all_classes[idx]
    try:
        char = add_level(codename, cls)
    except ValueError as e:
        await callback.message.edit_text(
            f"❌ Не удалось добавить уровень:\n{e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"levels:{codename}")]]))
        await callback.answer()
        return
    hint = ""
    if char["current_level"] >= 3 and not char.get("archetype"):
        for cls_name in char.get("classes", {}):
            if get_available_archetypes(cls_name):
                hint = "\n\n🎖 Не забудьте выбрать архетип в карточке."
                break
    pending = get_pending_asi_levels(char)
    if pending:
        hint += f"\n\n🎯 Доступно ASI/черта: ур. {', '.join(map(str, pending))}"
    await callback.message.edit_text(
        f"✅ Добавлен уровень {char['current_level']} ({cls}).\n\n"
        f"📊 *Уровни {char['name']}*\nТекущий: *{char['current_level']}*{hint}",
        parse_mode="Markdown", reply_markup=levels_keyboard(codename, char))
    await callback.answer()


@router.callback_query(F.data.startswith("reset_lvls_all:"))
async def reset_levels_all_cb(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    try:
        char = reset_levels(codename, keep_above=False)
    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {e}", reply_markup=main_menu())
        await callback.answer()
        return
    await callback.message.edit_text(
        f"✅ Все уровни сброшены. Текущий уровень: *{char['current_level']}*.",
        parse_mode="Markdown", reply_markup=levels_keyboard(codename, char))
    await callback.answer()


@router.callback_query(F.data.startswith("reset_lvls_above:"))
async def reset_levels_above_cb(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    try:
        char = reset_levels(codename, keep_above=True)
    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {e}", reply_markup=main_menu())
        await callback.answer()
        return
    await callback.message.edit_text(
        f"✅ Уровни выше *{char['current_level']}* сброшены.",
        parse_mode="Markdown", reply_markup=levels_keyboard(codename, char))
    await callback.answer()


@router.callback_query(F.data.startswith("reset_lvls:"))
async def reset_lvls_menu(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    max_lvl = max(int(k) for k in char["levels"].keys())
    await callback.message.edit_text(
        f"📊 *Сброс уровней {char['name']}*\n\n"
        f"Текущий уровень: *{char['current_level']}*\n"
        f"Максимальный уровень: *{max_lvl}*\n\n"
        f"Выберите, что сбросить.",
        parse_mode="Markdown", reply_markup=reset_levels_keyboard(codename, char))
    await callback.answer()


# ============================================================
#  Пересоздание
# ============================================================
@router.callback_query(F.data.startswith("redo_char:"))
async def redo_character_start(callback: CallbackQuery):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, начать заново",
                              callback_data=f"redo_confirm:{codename}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"reset_lvls:{codename}")],
    ])
    await callback.message.edit_text(
        f"🔄 *Пересоздание персонажа*\n\n"
        f"Персонаж: *{char['name']}*\n\n"
        f"Будут сброшены: раса, класс, архетип, предыстория, черта,\n"
        f"характеристики, уровни (до 1), ASI.\n\n"
        f"Имя и файл сохранятся.\n\nПродолжить?",
        parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("redo_confirm:"))
async def redo_character_confirm(callback: CallbackQuery, state: FSMContext):
    codename = callback.data.split(":", 1)[1]
    char = load_character(codename)
    if not char:
        await callback.message.edit_text("Персонаж не найден.", reply_markup=main_menu())
        await callback.answer()
        return
    if not get_available_races():
        await callback.message.edit_text("В проекте нет ни одного файла расы.",
                                         reply_markup=main_menu())
        await callback.answer()
        return
    name = char["name"]
    await state.clear()
    await state.update_data(name=name, redo_codename=codename)
    await state.set_state(CreateCharacter.race)
    await callback.message.edit_text(
        f"🔄 Пересоздание *{name}*.\n\nВыбери расу заново:",
        parse_mode="Markdown", reply_markup=race_keyboard())
    await callback.answer()


# ============================================================
#  ASI (характеристики или черта)
# ============================================================
def _asi_menu_kb(codename: str, level: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 +2 к одной характеристике",
                              callback_data=f"asi_plus2_pick:{codename}:{level}")],
        [InlineKeyboardButton(text="📈 +1 к двум характеристикам",
                              callback_data=f"asi_plus1_pick:{codename}:{level}")],
        [InlineKeyboardButton(text="🎖 Взять черту (вместо характеристик)",
                              callback_data=f"asi_feat_pick:{codename}:{level}")],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"view:{codename}")],
    ])


@router.callback_query(F.data.startswith("asi_menu:"))
async def asi_menu(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.clear()
    await state.update_data(asi_codename=codename, asi_level=level)
    await callback.message.edit_text(
        f"🎯 *Увеличение характеристик* (уровень {level})\n\nВыберите вариант:",
        parse_mode="Markdown", reply_markup=_asi_menu_kb(codename, level))
    await callback.answer()


@router.callback_query(F.data.startswith("asi_plus2_pick:"))
async def asi_plus2_pick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    prev_lvl = level - 1
    prev_snap = char["levels"].get(str(prev_lvl)) or char["levels"]["1"]
    current_stats = prev_snap.get("stats", {})
    kb = []
    for stat in ALL_STATS:
        val = current_stats.get(stat, 10)
        if val >= 20:
            continue
        new_val = min(20, val + 2)
        kb.append([InlineKeyboardButton(
            text=f"{stat} ({val} → {new_val})",
            callback_data=f"asi_plus2_apply:{codename}:{level}:{stat}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад",
                                    callback_data=f"asi_menu:{codename}:{level}")])
    await callback.message.edit_text(
        f"🎯 *+2 к одной характеристике*\n\nВыберите:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("asi_plus2_apply:"))
async def asi_plus2_apply(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    stat = parts[3]
    try:
        char = set_asi_stats(codename, level, {stat: 2})
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        f"✅ *{stat}* увеличена на +2.\n\n{format_character(char)}",
        parse_mode="Markdown", reply_markup=char_view_keyboard(codename, char))
    await callback.answer("Характеристика улучшена")


def _asi_plus1_keyboard(char, level, selected):
    prev_lvl = level - 1
    prev_snap = char["levels"].get(str(prev_lvl)) or char["levels"]["1"]
    current_stats = prev_snap.get("stats", {})
    kb = []
    for stat in ALL_STATS:
        val = current_stats.get(stat, 10)
        if val >= 20 and stat not in selected:
            continue
        mark = "✅" if stat in selected else "◻"
        kb.append([InlineKeyboardButton(
            text=f"{mark} {stat} ({val})",
            callback_data=f"asi_plus1_toggle:{stat}")])
    kb.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data="asi_plus1_confirm")])
    kb.append([InlineKeyboardButton(
        text="🔙 Назад", callback_data=f"asi_back_menu:{char['codename']}:{level}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("asi_plus1_pick:"))
async def asi_plus1_pick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.update_data(asi_codename=codename, asi_level=level, asi_selected=[])
    await state.set_state(ASISelect.plus1)
    char = load_character(codename)
    await callback.message.edit_text(
        f"🎯 *+1 к двум характеристикам*\n\nВыберите две:",
        parse_mode="Markdown", reply_markup=_asi_plus1_keyboard(char, level, []))
    await callback.answer()


@router.callback_query(F.data.startswith("asi_plus1_toggle:"), ASISelect.plus1)
async def asi_plus1_toggle(callback: CallbackQuery, state: FSMContext):
    stat = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = list(data.get("asi_selected", []))
    codename = data.get("asi_codename")
    level = data.get("asi_level")
    if stat in selected:
        selected.remove(stat)
    else:
        if len(selected) >= 2:
            await callback.answer("Можно выбрать только 2 характеристики", show_alert=True)
            return
        selected.append(stat)
    await state.update_data(asi_selected=selected)
    char = load_character(codename)
    await callback.message.edit_reply_markup(
        reply_markup=_asi_plus1_keyboard(char, level, selected))
    await callback.answer()


@router.callback_query(F.data == "asi_plus1_confirm", ASISelect.plus1)
async def asi_plus1_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("asi_selected", [])
    codename = data.get("asi_codename")
    level = data.get("asi_level")
    if len(selected) != 2:
        await callback.answer("Выберите ровно 2 характеристики", show_alert=True)
        return
    try:
        char = set_asi_stats(codename, level, {s: 1 for s in selected})
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        f"✅ *{selected[0]}* и *{selected[1]}* увеличены на +1.\n\n{format_character(char)}",
        parse_mode="Markdown", reply_markup=char_view_keyboard(codename, char))
    await callback.answer("Характеристики улучшены")


@router.callback_query(F.data.startswith("asi_back_menu:"), ASISelect.plus1)
async def asi_back_menu(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        f"🎯 *Увеличение характеристик* (уровень {level})\n\nВыберите вариант:",
        parse_mode="Markdown", reply_markup=_asi_menu_kb(codename, level))
    await callback.answer()


@router.callback_query(F.data.startswith("asi_feat_pick:"))
async def asi_feat_pick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    char = load_character(codename)
    if not char:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    taken = _taken_feat_names(char)
    traits = get_available_traits()
    kb = []
    for i, name in enumerate(traits):
        mark = "✅ (уже есть) " if name in taken else ""
        kb.append([InlineKeyboardButton(
            text=f"{mark}{name}",
            callback_data=f"asi_feat_view:{codename}:{level}:{i}")])
    kb.append([InlineKeyboardButton(
        text="🔙 Назад", callback_data=f"asi_menu:{codename}:{level}")])
    await callback.message.edit_text(
        f"🎖 *Взять черту* (уровень {level})\n\nВыберите черту для просмотра:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()


@router.callback_query(F.data.startswith("asi_feat_view:"))
async def asi_feat_view(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2]); idx = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    traits = get_available_traits()
    if idx < 0 or idx >= len(traits):
        await callback.answer("Черта не найдена", show_alert=True)
        return
    feat_name = traits[idx]
    trait = get_trait_data(feat_name)
    char = load_character(codename)
    if not trait or not char:
        await callback.answer("Не найдено", show_alert=True)
        return
    taken = _taken_feat_names(char)
    text = f"📖 *{feat_name}*\n\n{trait.get('description', '')}"
    rows = []
    if feat_name in taken:
        rows.append([InlineKeyboardButton(
            text="⚠ Уже есть у персонажа", callback_data="noop")])
    else:
        rows.append([InlineKeyboardButton(
            text="✅ Взять эту черту",
            callback_data=f"asi_feat_apply:{codename}:{level}:{idx}")])
    rows.append([InlineKeyboardButton(
        text="🔙 К списку", callback_data=f"asi_feat_pick:{codename}:{level}")])
    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("asi_feat_apply:"))
async def asi_feat_apply(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    codename = parts[1]
    try:
        level = int(parts[2]); idx = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    traits = get_available_traits()
    if idx < 0 or idx >= len(traits):
        await callback.answer("Черта не найдена", show_alert=True)
        return
    feat_name = traits[idx]
    try:
        char = set_asi_feat(codename, level, feat_name)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        f"✅ Получена черта *{feat_name}*.\n\n{format_character(char)}",
        parse_mode="Markdown", reply_markup=char_view_keyboard(codename, char))
    await callback.answer("Черта получена")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()