import json
from pathlib import Path

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

# ---------- Таблица опыта (D&D 5e 2024) ----------
XP_TABLE = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000,
    10: 64000, 11: 85000, 12: 100000, 13: 120000,
    14: 140000, 15: 165000, 16: 195000, 17: 225000,
    18: 265000, 19: 305000, 20: 355000,
}

# Уровни, на которых выдаётся увеличение характеристик
ASI_LEVELS = [4, 8, 12, 16, 19]

ALL_SKILLS = [
    "Акробатика", "Анализ", "Атлетика", "Внимательность", "Выживание",
    "Выступление", "Запугивание", "История", "Ловкость рук", "Магия",
    "Медицина", "Обман", "Природа", "Проницательность", "Религия",
    "Скрытность", "Убеждение", "Уход за животными",
]

ALL_STATS = ["Сила", "Ловкость", "Телосложение",
             "Интеллект", "Мудрость", "Харизма"]


# ---------- Таблицы ячеек заклинаний ----------
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


# ---------- Работа с JSON ----------
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

    full_level = 0
    for cls, lvl in classes.items():
        if cls in FULL_CASTER_CLASSES:
            full_level += lvl
    if full_level > 0:
        arr = FULL_CASTER_SLOTS.get(min(full_level, 20), [])
        for i, cnt in enumerate(arr, start=1):
            slots[i] += cnt

    half_level = 0
    for cls, lvl in classes.items():
        if cls in HALF_CASTER_CLASSES:
            half_level += lvl
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
    return {str(lvl): {"max": m} for lvl, m in max_slots.items()}


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


# ---------- XP и грузоподъёмность ----------
def get_xp_for_level(level: int) -> int:
    return XP_TABLE.get(level, 0)


def get_xp_progress(char) -> tuple:
    current = char.get("current_level", 1)
    xp = XP_TABLE.get(current, 0)
    if current < MAX_LEVEL:
        return xp, XP_TABLE.get(current + 1)
    return xp, None


def get_max_carry_weight(stats: dict) -> int:
    return stats.get("Сила", 10) * 15


def get_pending_asi_levels(char) -> list:
    max_lvl = max(int(k) for k in char["levels"].keys())
    choices = char.get("asi_choices", {})
    return [lvl for lvl in ASI_LEVELS
            if lvl <= max_lvl and str(lvl) not in choices]


# ---------- Характеристики ----------
def _ensure_alt_stats(char) -> None:
    """Для старых персонажей-альтернативных людей восстанавливает alt_stats
    из base_stats и уровня 1 (если поле отсутствует)."""
    if char.get("race_variant") != "alternative":
        return
    if "alt_stats" in char:
        return
    base = char.get("base_stats", {})
    lvl1 = char.get("levels", {}).get("1", {}).get("stats", {})
    alt = [stat for stat in ALL_STATS
           if lvl1.get(stat, 10) > base.get(stat, 10)]
    char["alt_stats"] = alt


def _ensure_alternative_race(char) -> None:
    """Для альтернативного варианта расы убирает стандартные расовые
    навыки и умения (например, «Универсальность» у человека)."""
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
    """Вычисляет характеристики для уровня up_to_level:
    base_stats + расовые бонусы + ASI (уровни 4/8/12/16/19).
    """
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


# ---------- Пересчёт производных значений ----------
def _rebuild(char, snapshot):
    level = snapshot["level"]
    archetype = char.get("archetype")

    # Пересчитываем характеристики с учётом ASI
    snapshot["stats"] = _compute_stats(char, level)
    snapshot["proficiency_bonus"] = 2 + (level - 1) // 4

    # Навыки
    skills = []
    # Для альтернативного варианта расовые навыки не добавляются
    if char.get("race_variant") != "alternative":
        skills.extend(_load_skills_from("races", char["race"], level))
    for cls, lvl in snapshot["classes"].items():
        skills.extend(_load_skills_from("classes", cls, lvl, archetype))

    bg = get_background_data(char["background"])
    if bg:
        for skill_name in bg.get("skill_proficiencies", []):
            skills.append({
                "name": skill_name,
                "description": "Владение навыком (предыстория)",
                "source": "background",
                "type": "passive",
            })

    for skill_name in char.get("extra_skills", []):
        skills.append({
            "name": skill_name,
            "description": "Владение навыком (особенность)",
            "source": "variant",
            "type": "passive",
        })

    seen = set()
    unique = []
    for s in skills:
        key = s["name"]
        if key not in seen:
            seen.add(key)
            unique.append(s)
    snapshot["skills"] = unique

    # Умения
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
            features.append({**f, "source": f"Раса: {char['race']} ({vinfo.get('name', '')})"})

    if bg and bg.get("feature"):
        features.append({
            **bg["feature"],
            "source": f"Предыстория: {char['background']}",
        })

    for trait_name in char.get("traits", []):
        trait_data = get_trait_data(trait_name)
        if trait_data:
            features.append({
                "name": trait_data["name"],
                "description": trait_data.get("description", ""),
                "source": "Черта",
            })

    # Умения архетипа (для любого класса)
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

    # Выбранный боевой стиль
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

    # Заклинания
    snapshot.setdefault("prepared_spells", [])

    # Ячейки заклинаний (только максимум, без затрат)
    snapshot["spell_slots"] = _init_spell_slots(
        snapshot["classes"], snapshot["level"], archetype)

    # HP
    snapshot["hp"] = calculate_hp({
        "classes": snapshot["classes"],
        "level": snapshot["level"],
        "stats": snapshot["stats"],
    })


def _sync_top_level(char):
    current = get_current(char)
    char["current_level"] = current["level"]
    for key in ("level", "classes", "stats", "proficiency_bonus",
                "hp", "skills", "features", "spell_slots"):
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
    if existing_codename:
        codename = existing_codename
    else:
        codename = _generate_codename(name)

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
    }

    snapshot = {
        "level": 1,
        "classes": {char_class: 1},
        "stats": {},
        "proficiency_bonus": 0,
        "hp": 0,
        "skills": [],
        "features": [],
        "prepared_spells": [],
        "spell_slots": {},
    }
    char["levels"]["1"] = snapshot
    _rebuild(char, snapshot)
    _save_character(char)
    return char


# ---------- Загрузка / список ----------
def load_character(codename: str):
    path = CHARACTERS_DIR / f"{codename}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        char = json.load(f)
    _ensure_alt_stats(char)
    _ensure_alternative_race(char)
    char.setdefault("asi_choices", {})
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
def prepare_spell(codename: str, spell_name: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    if not get_spell_data(spell_name):
        raise ValueError(f"Заклинание «{spell_name}» не найдено.")
    snap = get_current(char)
    prepared = snap.setdefault("prepared_spells", [])
    if spell_name not in prepared:
        prepared.append(spell_name)
    _save_character(char)
    return char


def unprepare_spell(codename: str, spell_name: str) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")
    snap = get_current(char)
    prepared = snap.setdefault("prepared_spells", [])
    if spell_name in prepared:
        prepared.remove(spell_name)
    _save_character(char)
    return char


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


# ---------- Ячейки заклинаний (только просмотр) ----------
def get_spell_slots(char) -> dict:
    snap = get_current(char)
    return snap.get("spell_slots", {})


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
        "level": new_lvl,
        "classes": new_classes,
        "stats": {},
        "proficiency_bonus": 0,
        "hp": 0,
        "skills": [],
        "features": [],
        "prepared_spells": list(max_snapshot.get("prepared_spells", [])),
        "spell_slots": {},
    }
    _rebuild(char, new_snapshot)

    levels[str(new_lvl)] = new_snapshot
    char["current_level"] = new_lvl
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


# ---------- Увеличение характеристик (ASI) ----------
def set_asi_stats(codename: str, asi_level: int, stat_bonuses: dict) -> dict:
    char = load_character(codename)
    if not char:
        raise ValueError("Персонаж не найден.")

    max_lvl = get_max_level(char)
    if asi_level > max_lvl:
        raise ValueError(f"Уровень {asi_level} ещё не достигнут.")
    if asi_level not in ASI_LEVELS:
        raise ValueError(f"Уровень {asi_level} не даёт увеличения характеристик.")

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
                f"{stat} не может превысить 20 (сейчас {cur}, бонус +{bonus})."
            )

    char.setdefault("asi_choices", {})[str(asi_level)] = {
        "type": "stats",
        "stat_bonuses": dict(stat_bonuses),
    }

    for lvl_str, snap in char["levels"].items():
        if int(lvl_str) >= asi_level:
            _rebuild(char, snap)

    _save_character(char)
    return char