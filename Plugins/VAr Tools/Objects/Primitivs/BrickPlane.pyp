# -*- coding: utf-8 -*-
"""
BrickPlane — Cinema 4D ObjectData Plugin
Плоскость с кирпичной сеткой (паттерны: running bond, stack bond, 1/3 bond,
ёлочка, гексагональные, корзинка). Поддерживает швы и displacement по Y.
"""

import c4d # type: ignore
import math
import os
import base64
import tempfile
import random

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_BRICKPLANE = 1068875

NAME_BRICKPLANE = "Brick Plane v1.6.2"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# BrickPlane
BP_WIDTH    = 2
BP_HEIGHT   = 3
BP_SEGS_W   = 4
BP_SEGS_H   = 5
BP_PATTERN  = 6   # Тип паттерна
BP_OFFSET   = 7   # Смещение Y (displacement)
BP_MORTAR   = 8   # Ширина шва (0..1 от размера кирпича)
BP_OFFSET_SCALE = 9  # Масштаб смещения

# ─── Константы паттернов ─────────────────────────────────────────────────────
PAT_RUNNING_BOND = 0   # Кирпичная кладка (бегущая связка, 1/2 смещение)
PAT_STACK_BOND   = 1   # Стековая кладка (без смещения)
PAT_THIRD_BOND   = 2   # Кладка 1/3 смещение
PAT_HERRINGBONE  = 3   # Ёлочка (45°)
PAT_HEXAGONAL    = 4   # Гексагональные плитки
PAT_BASKET       = 5   # Корзинчатое плетение (basket weave)


# ─── Вспомогательные функции UserData ────────────────────────────────────────

def _ud_descid(op, uid):
    """Ищет UserData по SubID. Возвращает (DescID, BaseContainer) или (None, None)."""
    for descid, bc in op.GetUserDataContainer():
        if descid[1].id == uid:
            return descid, bc
    return None, None


def _ud_get(op, uid, default=None):
    did, _ = _ud_descid(op, uid)
    if did is not None:
        val = op[did]
        if val is not None:
            return val
    return default


def _add_group(op, name):
    """Добавляет корневую группу UserData. Возвращает SubID группы."""
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_TITLEBAR]   = 1
    bc[c4d.DESC_DEFAULT]    = 1  # развёрнута по умолчанию
    did = op.AddUserData(bc)
    return did[1].id   # [1] — SubID, [0] — ID_USERDATA(700)


def _add_in_group(op, grp_subid, bc):
    """Добавляет элемент UserData внутрь группы с данным SubID."""
    bc[c4d.DESC_PARENTGROUP] = c4d.DescID(
        c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
        c4d.DescLevel(grp_subid, c4d.DTYPE_GROUP, 0)
    )
    return op.AddUserData(bc)


def _make_float_bc(name, default, minval, maxval, unit=c4d.DESC_UNIT_METER, step=1.0):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_REAL)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_MIN]        = minval
    bc[c4d.DESC_MAX]        = maxval
    bc[c4d.DESC_UNIT]       = unit
    bc[c4d.DESC_STEP]       = step
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


def _make_int_bc(name, default, minval, maxval):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_MIN]        = minval
    bc[c4d.DESC_MAX]        = maxval
    bc[c4d.DESC_STEP]       = 1
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


def _make_cycle_bc(name, default, items_dict):
    """Создаёт UserData типа Cycle (выпадающий список)."""
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
    cycle_bc = c4d.BaseContainer()
    for k, v in items_dict.items():
        cycle_bc[k] = v
    bc[c4d.DESC_CYCLE]      = cycle_bc
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


def _ud_already_created(op, first_field_uid):
    """Проверяет, созданы ли уже UserData по наличию поля с данным SubID."""
    did, _ = _ud_descid(op, first_field_uid)
    return did is not None


def _ud_set_default(op, uid, value):
    """Устанавливает значение поля UserData по SubID."""
    did, _ = _ud_descid(op, uid)
    if did is not None:
        op[did] = value


# ─── Генераторы мешей ─────────────────────────────────────────────────────────

def _apply_displacement(verts, polys, offset_amount, mortar_frac):
    """
    Смещает вершины каждого полигона по Y на offset_amount.
    Каждый полигон получает уникальные (не шаренные) вершины,
    чтобы смещение было независимым — как реальные кирпичи.
    mortar_frac не используется здесь, но сигнатура единая.
    """
    if abs(offset_amount) < 1e-6:
        return verts, polys

    new_verts = []
    new_polys = []
    vi = 0
    for poly in polys:
        if isinstance(poly, c4d.CPolygon):
            idx = [poly.a, poly.b, poly.c, poly.d]
            is_tri = (poly.c == poly.d)
        else:
            idx = list(poly)
            is_tri = False

        # Уникальные вершины для этого полигона
        local_pts = [c4d.Vector(verts[i]) for i in idx]

        # Случайное смещение на основе центроида (детерминированное)
        cx = sum(p.x for p in local_pts) / len(local_pts)
        cz = sum(p.z for p in local_pts) / len(local_pts)
        seed = (int(abs(cx * 73856093)) ^ int(abs(cz * 19349663)) ^ int(abs(cx + cz) * 83492791)) % 65537
        rng = random.Random(seed)
        dy = (rng.random() * 2.0 - 1.0) * offset_amount

        for pt in local_pts:
            pt.y += dy
            new_verts.append(pt)

        a, b, c_, d_ = vi, vi+1, vi+2, vi+3 if len(local_pts) == 4 else vi+2
        if is_tri or len(local_pts) == 3:
            new_polys.append(c4d.CPolygon(a, b, c_, c_))
        else:
            new_polys.append(c4d.CPolygon(a, b, c_, d_))
        vi += len(local_pts)

    return new_verts, new_polys


def build_brickplane(width, height, segs_w, segs_h, pattern=PAT_RUNNING_BOND,
                     offset_amount=0.0, mortar_frac=0.0):
    """
    Диспетчер: выбирает нужный генератор по паттерну.
    Возвращает (points, polys).
    """
    # Генерация базовой топологии
    if pattern == PAT_RUNNING_BOND:
        verts, polys = _build_running_bond(width, height, segs_w, segs_h, mortar_frac)
    elif pattern == PAT_STACK_BOND:
        verts, polys = _build_stack_bond(width, height, segs_w, segs_h, mortar_frac)
    elif pattern == PAT_THIRD_BOND:
        verts, polys = _build_third_bond(width, height, segs_w, segs_h, mortar_frac)
    elif pattern == PAT_HERRINGBONE:
        verts, polys = _build_herringbone(width, height, segs_w, segs_h, mortar_frac)
    elif pattern == PAT_HEXAGONAL:
        verts, polys = _build_hexagonal(width, height, segs_w, segs_h, mortar_frac)
    elif pattern == PAT_BASKET:
        verts, polys = _build_basket_weave(width, height, segs_w, segs_h, mortar_frac)
    else:
        verts, polys = _build_running_bond(width, height, segs_w, segs_h, mortar_frac)

    # Применяем displacement (независимое смещение каждого кирпича по Y)
    if abs(offset_amount) > 1e-6:
        verts, polys = _apply_displacement(verts, polys, offset_amount, mortar_frac)

    return verts, polys


def _build_running_bond(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Кирпичная кладка (running bond / половинное смещение).
    Нечётные ряды смещены на полшага по X.
    Каждый кирпич — отдельный quad с уникальными вершинами.
    mortar_frac — доля шва (0 = без шва, 0.4 = максимум).
    """
    m      = max(0.0, min(mortar_frac, 0.45))
    step_x = width  / segs_w
    step_y = height / segs_h
    # Единое абсолютное значение полушва — равномерное по обеим осям
    hm     = min(step_x, step_y) * m * 0.5

    verts = []
    polys = []

    for row in range(segs_h):
        z0 = row       / segs_h * height - height / 2.0
        z1 = (row + 1) / segs_h * height - height / 2.0

        if row % 2 == 0:
            # Чётный ряд: кирпичи начинаются с 0, каждый кирпич = step_x
            for brick in range(segs_w):
                x0 = brick * step_x - width / 2.0
                x1 = x0 + step_x
                base = len(verts)
                verts.append(c4d.Vector(x0 + hm, 0.0, z0 + hm))
                verts.append(c4d.Vector(x1 - hm, 0.0, z0 + hm))
                verts.append(c4d.Vector(x1 - hm, 0.0, z1 - hm))
                verts.append(c4d.Vector(x0 + hm, 0.0, z1 - hm))
                polys.append(c4d.CPolygon(base, base+3, base+2, base+1))
        else:
            # Нечётный ряд: смещение на полкирпича
            # Первый полукирпич у левого края
            x0 = -width / 2.0
            x1 = x0 + step_x * 0.5
            base = len(verts)
            verts.append(c4d.Vector(x0,        0.0, z0 + hm))
            verts.append(c4d.Vector(x1 - hm,   0.0, z0 + hm))
            verts.append(c4d.Vector(x1 - hm,   0.0, z1 - hm))
            verts.append(c4d.Vector(x0,        0.0, z1 - hm))
            polys.append(c4d.CPolygon(base, base+3, base+2, base+1))

            # Полные кирпичи в середине
            for brick in range(segs_w - 1):
                x0 = brick * step_x + step_x * 0.5 - width / 2.0
                x1 = x0 + step_x
                base = len(verts)
                verts.append(c4d.Vector(x0 + hm, 0.0, z0 + hm))
                verts.append(c4d.Vector(x1 - hm, 0.0, z0 + hm))
                verts.append(c4d.Vector(x1 - hm, 0.0, z1 - hm))
                verts.append(c4d.Vector(x0 + hm, 0.0, z1 - hm))
                polys.append(c4d.CPolygon(base, base+3, base+2, base+1))

            # Последний полукирпич у правого края
            x0 = (segs_w - 1) * step_x + step_x * 0.5 - width / 2.0
            x1 = width / 2.0
            base = len(verts)
            verts.append(c4d.Vector(x0 + hm, 0.0, z0 + hm))
            verts.append(c4d.Vector(x1,      0.0, z0 + hm))
            verts.append(c4d.Vector(x1,      0.0, z1 - hm))
            verts.append(c4d.Vector(x0 + hm, 0.0, z1 - hm))
            polys.append(c4d.CPolygon(base, base+3, base+2, base+1))

    return verts, polys


def _build_stack_bond(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Стековая кладка (stack bond) — кирпичи без смещения, ряды ровно над рядами.
    Каждый кирпич — отдельный quad.
    """
    m     = max(0.0, min(mortar_frac, 0.45))
    step_x = width  / segs_w
    step_y = height / segs_h
    hm_x  = min(step_x, step_y) * m * 0.5
    hm_y  = hm_x

    verts = []
    polys = []
    for row in range(segs_h):
        z0 = row / segs_h * height - height / 2.0
        z1 = (row + 1) / segs_h * height - height / 2.0
        for col in range(segs_w):
            x0 = col / segs_w * width - width / 2.0
            x1 = (col + 1) / segs_w * width - width / 2.0
            base = len(verts)
            # Уникальные вершины каждого кирпича
            verts.append(c4d.Vector(x0 + hm_x, 0.0, z0 + hm_y))  # bl
            verts.append(c4d.Vector(x1 - hm_x, 0.0, z0 + hm_y))  # br
            verts.append(c4d.Vector(x1 - hm_x, 0.0, z1 - hm_y))  # tr
            verts.append(c4d.Vector(x0 + hm_x, 0.0, z1 - hm_y))  # tl
            polys.append(c4d.CPolygon(base, base+3, base+2, base+1))
    return verts, polys


def _build_third_bond(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Кладка с 1/3 смещением (третья связка, flemish-style offset).
    Каждый следующий ряд смещается на 1/3 кирпича.
    """
    m     = max(0.0, min(mortar_frac, 0.45))
    step_x = width  / segs_w
    step_y = height / segs_h
    hm_x  = min(step_x, step_y) * m * 0.5
    hm_y  = hm_x

    verts = []
    polys = []
    for row in range(segs_h):
        z0 = row / segs_h * height - height / 2.0
        z1 = (row + 1) / segs_h * height - height / 2.0
        # Смещение ряда = (row % 3) * 1/3 кирпича
        x_shift = (row % 3) * (step_x / 3.0)
        # Число целых кирпичей + возможные обрезки слева и справа
        for col in range(-1, segs_w + 1):
            x0 = col * step_x + x_shift - width / 2.0
            x1 = x0 + step_x
            # Обрезаем по границам плоскости
            cx0 = max(x0, -width / 2.0)
            cx1 = min(x1,  width / 2.0)
            if cx1 - cx0 < 1e-6:
                continue
            base = len(verts)
            verts.append(c4d.Vector(cx0 + hm_x, 0.0, z0 + hm_y))
            verts.append(c4d.Vector(cx1 - hm_x, 0.0, z0 + hm_y))
            verts.append(c4d.Vector(cx1 - hm_x, 0.0, z1 - hm_y))
            verts.append(c4d.Vector(cx0 + hm_x, 0.0, z1 - hm_y))
            if (cx1 - hm_x) - (cx0 + hm_x) < 1e-6 or (z1 - hm_y) - (z0 + hm_y) < 1e-6:
                continue
            polys.append(c4d.CPolygon(base, base+3, base+2, base+1))
    return verts, polys


def _build_herringbone(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Ёлочка (herringbone): чередование H- и V-кирпичей 1×2 без перекрытий.
    Каждая «мета-ячейка» 2×2 содержит ровно 2 кирпича:
      - чётные блоки (row+col чётное): горизонтальный (2×1)
      - нечётные блоки (row+col нечётное): вертикальный (1×2)
    """
    m      = max(0.0, min(mortar_frac, 0.45))
    tile_w = width  / (segs_w * 2.0)
    tile_h = height / (segs_h * 2.0)
    hm_x   = min(tile_w, tile_h) * m * 0.5
    hm_y   = hm_x

    verts = []
    polys = []

    # Итерируем по строкам и столбцам с шагом 1,
    # но ориентация определяется чётностью (row//1 + col//1),
    # и каждый тип кирпича занимает 2 ячейки — поэтому шагаем через 2
    for row in range(0, segs_h * 2, 1):
        for col in range(0, segs_w * 2, 1):
            parity = (row + col) % 4  # период паттерна = 4

            if parity == 0:
                # Горизонтальный кирпич: 2 tile_w × 1 tile_h
                x0 = col * tile_w - width  / 2.0
                z0 = row * tile_h - height / 2.0
                x1 = x0 + 2.0 * tile_w
                z1 = z0 + tile_h
                if x1 > width / 2.0 + 1e-4:
                    continue
            elif parity == 2:
                # Вертикальный кирпич: 1 tile_w × 2 tile_h
                x0 = col * tile_w - width  / 2.0
                z0 = row * tile_h - height / 2.0
                x1 = x0 + tile_w
                z1 = z0 + 2.0 * tile_h
                if z1 > height / 2.0 + 1e-4:
                    continue
            else:
                # Ячейки parity 1 и 3 — уже заняты соседними кирпичами
                continue

            eff_w = (x1 - hm_x) - (x0 + hm_x)
            eff_h = (z1 - hm_y) - (z0 + hm_y)
            if eff_w < 1e-6 or eff_h < 1e-6:
                continue

            base = len(verts)
            verts.append(c4d.Vector(x0 + hm_x, 0.0, z0 + hm_y))
            verts.append(c4d.Vector(x1 - hm_x, 0.0, z0 + hm_y))
            verts.append(c4d.Vector(x1 - hm_x, 0.0, z1 - hm_y))
            verts.append(c4d.Vector(x0 + hm_x, 0.0, z1 - hm_y))
            polys.append(c4d.CPolygon(base, base+3, base+2, base+1))

    return verts, polys


def _build_hexagonal(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Гексагональные плитки (flat-top ориентация).
    segs_w — число гексагонов по X, segs_h — по Y.
    Flat-top: верхняя/нижняя грань горизонтальны.
      circumradius r  → ширина гекса = 2*r, высота = r*sqrt(3)
      шаг по X: 1.5*r  (между центрами соседних колонок)
      шаг по Z: r*sqrt(3)  (строки внутри колонки)
      нечётные колонки смещены по Z на r*sqrt(3)/2
    segs_w и segs_h задают число гексагонов по X и Y сетки.
    mortar_frac — уменьшает радиус каждого гексагона (шов).
    """
    m = max(0.0, min(mortar_frac, 0.45))

    # Flat-top hex grid: step_x = 1.5*r (не 3*r!), step_z = r*sqrt(3)
    # По X: segs_w колонок → total_x = 1.5*r*(segs_w-1) + 2*r = r*(1.5*segs_w + 0.5)
    # По Z: segs_h строк   → total_z = r*sqrt(3)*(segs_h + 0.5) (с учётом смещения нечётных колонок)
    r_from_x = width  / (1.5 * segs_w + 0.5)
    r_from_z = height / (math.sqrt(3) * (segs_h + 0.5))
    r_full   = min(r_from_x, r_from_z)
    r        = r_full * (1.0 - m)  # уменьшаем на шов

    # Шаги сетки (по центрам, не зависят от m)
    step_x = 1.5 * r_full           # шаг по X между центрами соседних колонок
    step_z = r_full * math.sqrt(3)  # шаг по Z между центрами строк

    # Полный размер сетки и центрирование
    total_x = step_x * (segs_w - 1) + 2.0 * r_full
    total_z = step_z * segs_h + step_z * 0.5
    off_x   = -total_x * 0.5 + r_full
    off_z   = -total_z * 0.5 + step_z * 0.5

    verts = []
    polys = []

    for col in range(segs_w):
        cx = col * step_x + off_x
        # Нечётные колонки смещены по Z на полшага
        z_shift = (step_z * 0.5) if (col % 2 == 1) else 0.0

        for row in range(segs_h):
            cz = row * step_z + z_shift + off_z

            # 6 вершин flat-top гексагона: 0° = вправо, вершины через 60°
            hex_pts = []
            for i in range(6):
                angle = math.radians(60.0 * i)
                hx = cx + r * math.cos(angle)
                hz = cz + r * math.sin(angle)
                hex_pts.append(c4d.Vector(hx, 0.0, hz))

            base = len(verts)
            verts.extend(hex_pts)

            # Один N-гон (6 вершин) — без триангуляции
            # C4D CPolygon поддерживает только quads, поэтому используем 4+2:
            # quad0: v0,v3,v2,v1  quad1: v0,v5,v4,v3  (CCW → нормаль вверх)
            polys.append(c4d.CPolygon(base+0, base+3, base+2, base+1))
            polys.append(c4d.CPolygon(base+0, base+5, base+4, base+3))

    return verts, polys


def _build_basket_weave(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Корзинчатое плетение (basket weave): пары горизонтальных и вертикальных кирпичей,
    чередующихся в шахматном порядке.
    segs_w и segs_h — число пар по X и Y.
    """
    m     = max(0.0, min(mortar_frac, 0.45))
    # Каждая ячейка = 2 кирпича (1×2 или 2×1)
    cell_w = width  / segs_w
    cell_h = height / segs_h
    # Единый абсолютный полушов от наименьшего измерения полуячейки
    hm    = min(cell_w * 0.5, cell_h * 0.5) * m * 0.5

    verts = []
    polys = []

    def _add_brick(x0, z0, x1, z1):
        """Добавляет один кирпич (quad) в mesh."""
        if (x1 - x0 - 2*hm) < 1e-6 or (z1 - z0 - 2*hm) < 1e-6:
            return
        base = len(verts)
        verts.append(c4d.Vector(x0 + hm, 0.0, z0 + hm))
        verts.append(c4d.Vector(x1 - hm, 0.0, z0 + hm))
        verts.append(c4d.Vector(x1 - hm, 0.0, z1 - hm))
        verts.append(c4d.Vector(x0 + hm, 0.0, z1 - hm))
        polys.append(c4d.CPolygon(base, base+3, base+2, base+1))

    for row in range(segs_h):
        z0 = row * cell_h - height / 2.0
        z1 = z0 + cell_h
        zm = (z0 + z1) * 0.5
        for col in range(segs_w):
            x0 = col * cell_w - width / 2.0
            x1 = x0 + cell_w
            xm = (x0 + x1) * 0.5
            if (row + col) % 2 == 0:
                # Два горизонтальных кирпича (широкие по X, узкие по Z)
                _add_brick(x0, z0, x1, zm)
                _add_brick(x0, zm, x1, z1)
            else:
                # Два вертикальных кирпича (узкие по X, высокие по Z)
                _add_brick(x0, z0, xm, z1)
                _add_brick(xm, z0, x1, z1)

    return verts, polys


def _inset_polys(verts, polys, hm_x, hm_y):
    """
    Вспомогательная функция для running bond: создаёт уникальные вершины
    для каждого полигона с inset (швом) по X и Z.
    Для running bond вершины шаренные, поэтому нужна перестройка.
    """
    new_verts = []
    new_polys = []
    for poly in polys:
        if isinstance(poly, c4d.CPolygon):
            idx = [poly.a, poly.b, poly.c, poly.d]
            is_tri = (poly.c == poly.d)
        else:
            idx = list(poly)
            is_tri = False

        pts = [c4d.Vector(verts[i]) for i in idx]
        # Центр полигона
        n = len(pts) if not is_tri else 3
        cx = sum(p.x for p in pts[:n]) / n
        cz = sum(p.z for p in pts[:n]) / n
        # Inset: сдвигаем каждую вершину к центру (уменьшаем кирпич)
        new_pts = []
        for p in pts[:n]:
            dx = -hm_x if p.x >= cx else hm_x
            dz = -hm_y if p.z >= cz else hm_y
            new_pts.append(c4d.Vector(p.x + dx, p.y, p.z + dz))

        base = len(new_verts)
        new_verts.extend(new_pts)
        if n == 3:
            new_polys.append(c4d.CPolygon(base, base+1, base+2, base+2))
        else:
            new_polys.append(c4d.CPolygon(base, base+1, base+2, base+3))

    return new_verts, new_polys


# ─── Создание PolygonObject из вершин и полигонов ─────────────────────────────

def _make_poly_object(points, polys, name):
    """
    Создаёт c4d.PolygonObject.
    polys — список c4d.CPolygon или списков индексов вершин (n-гоны).
    """
    cpoly_list = []

    for item in polys:
        if isinstance(item, c4d.CPolygon):
            cpoly_list.append(item)
            continue
        cpoly_list.append(item)

    obj = c4d.PolygonObject(len(points), len(cpoly_list))
    obj.SetName(name)
    for i, pt in enumerate(points):
        obj.SetPoint(i, pt)
    for i, poly in enumerate(cpoly_list):
        obj.SetPolygon(i, poly)

    obj.Message(c4d.MSG_UPDATE)
    return obj


# ─── Базовый класс плагина ───────────────────────────────────────────────────

class _MeshPrimitiveBase(c4d.plugins.ObjectData):
    """
    Базовый класс для всех mesh-примитивов.
    Подклассы определяют:
      OBJECT_NAME   — имя объекта по умолчанию
      _first_ud_id  — SubID первого поля UserData (для проверки инициализации)
      _create_ud()  — создание UserData-полей
      _set_defaults() — установка значений по умолчанию
      _build_mesh() — генерация (points, polys)
    """

    OBJECT_NAME  = "MeshPrimitive"
    _first_ud_id = BP_WIDTH   # переопределяется в подклассах

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
        if not _ud_already_created(op, self._first_ud_id):
            grp_subid = _add_group(op, "Параметры")
            self._create_ud(op, grp_subid)
            self._set_defaults(op)
        return True

    def GetVirtualObjects(self, op, hh):
        if not _ud_already_created(op, self._first_ud_id):
            grp_subid = _add_group(op, "Параметры")
            self._create_ud(op, grp_subid)
            self._set_defaults(op)

        points, polys = self._build_mesh(op)
        return _make_poly_object(points, polys, self.OBJECT_NAME)

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription(op.GetType()):
            return False, flags
        if not _ud_already_created(op, self._first_ud_id):
            grp_subid = _add_group(op, "Параметры")
            self._create_ud(op, grp_subid)
            self._set_defaults(op)
        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK

    # Переопределить в подклассах:
    def _create_ud(self, op, grp_subid):
        pass

    def _set_defaults(self, op):
        pass

    def _build_mesh(self, op):
        return [], []


# ─── BrickPlane ───────────────────────────────────────────────────────────────

class BrickPlaneObject(_MeshPrimitiveBase):
    """Плоскость с кирпичной сеткой (running bond)."""

    OBJECT_NAME  = "Brick Plane"
    _first_ud_id = BP_WIDTH

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Ширина", 400.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Высота", 400.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Рядов (X)", 4, 1, 200))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Рядов (Y)", 4, 1, 200))
        # Тип паттерна (выпадающий список)
        _add_in_group(op, grp_subid, _make_cycle_bc(
            "Паттерн", PAT_RUNNING_BOND, {
                PAT_RUNNING_BOND: "Кирпич (1/2)",
                PAT_STACK_BOND:   "Кирпич (стек)",
                PAT_THIRD_BOND:   "Кирпич (1/3)",
                PAT_HERRINGBONE:  "Ёлочка",
                PAT_HEXAGONAL:    "Гексагональные",
                PAT_BASKET:       "Корзинка",
            }))
        # Смещение кирпичей по Y (displacement)
        _add_in_group(op, grp_subid, _make_float_bc(
            "Смещение (Y)", 0.0, 0.0, 10000.0, c4d.DESC_UNIT_METER))
        # Ширина шва (0..0.4, безразмерная — DESC_UNIT_FLOAT доступен во всех версиях)
        _add_in_group(op, grp_subid, _make_float_bc(
            "Шов (0-0.4)", 0.0, 0.0, 0.4, c4d.DESC_UNIT_FLOAT, step=0.005))

    def _set_defaults(self, op):
        _ud_set_default(op, BP_WIDTH,   400.0)
        _ud_set_default(op, BP_HEIGHT,  400.0)
        _ud_set_default(op, BP_SEGS_W,  4)
        _ud_set_default(op, BP_SEGS_H,  4)
        _ud_set_default(op, BP_PATTERN, PAT_RUNNING_BOND)
        _ud_set_default(op, BP_OFFSET,  0.0)
        _ud_set_default(op, BP_MORTAR,  0.0)

    def _build_mesh(self, op):
        w       = _ud_get(op, BP_WIDTH,   400.0)
        h       = _ud_get(op, BP_HEIGHT,  400.0)
        segs_w  = max(1, int(_ud_get(op, BP_SEGS_W,  4)))
        segs_h  = max(1, int(_ud_get(op, BP_SEGS_H,  4)))
        pattern = int(_ud_get(op, BP_PATTERN, PAT_RUNNING_BOND))
        offset  = float(_ud_get(op, BP_OFFSET,  0.0))
        mortar  = float(_ud_get(op, BP_MORTAR,  0.0))
        return build_brickplane(w, h, segs_w, segs_h, pattern, offset, mortar)


_ICON_BP = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6Mzg6NDMrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6Mzg6NDMrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjExMWUxMTM0LTlhZmUtMTc0NS05N2YyLWNhNzM5Y2ZmZjM4OCIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDoxMTFlMTEzNC05YWZlLTE3NDUtOTdmMi1jYTczOWNmZmYzODgiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDoxMTFlMTEzNC05YWZlLTE3NDUtOTdmMi1jYTczOWNmZmYzODgiPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjExMWUxMTM0LTlhZmUtMTc0NS05N2YyLWNhNzM5Y2ZmZjM4OCIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/Pt36DtgAAAFRSURBVFiFY/z//z/DQAKmAbV91AGDwQEsyJx3Ey3eszD8EShWS2aYI+NOA+v+MTB84bD6bylzHCaCEgInBVQFvjGzMfxmZsHUSxXAyMDA9asYRej///9wzHDh7hqGS3f/M1y4uwZd64Io/PmVkPzcmH//GS7d+c9w4e4aZDvpnAYYMUQGVyKEgfa5MkGS0f9/owj+Z2BYgC5Ggvw/HBGEOwT+ozmOkeEPJfIvhX5hdwKuREhposOQRzJ7ABMhJhhwBzAiV8eMF++tYWBiCG6fLfNf8i0bI0a8IoP/DCykyD8X+sVcmfqEkeEfw9r/+kohMHHcIUBhokOXF3/HhlkIMDDQuyQcTYSYYLQkHC0J6ewAzEDDWhLSwuqEp7sZOm8vYLjCLffTKWklB0wcNQS+sfUyMPyjhf0MzAz/GNj+/WbQ//roG7I442jXbNQBA+0AAOznE6qxnljLAAAAAElFTkSuQmCC"
)

def _make_icon_bp():
    png_data = base64.b64decode(_ICON_BP)
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        bmp.InitWith(tmp.name)
    finally:
        os.unlink(tmp.name)
    return bmp


ICO_BP = _make_icon_bp()

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_BRICKPLANE,
        str         = NAME_BRICKPLANE,
        g           = BrickPlaneObject,
        description = "",
        icon        = ICO_BP,
        info        = c4d.OBJECT_GENERATOR,
    )
