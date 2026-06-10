# -*- coding: utf-8 -*-
"""
BrickPlane — Cinema 4D ObjectData Plugin
Плоскость с кирпичной сеткой (running bond).
"""

import c4d
import math
import os
import base64
import tempfile
import random

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_BRICKPLANE = 1068875

NAME_BRICKPLANE = "BrickPlane v1.2"

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
    Рёбра на границах нечётных рядов разрезаются дополнительными вершинами.
    mortar_frac — доля шва от размера кирпича (0 = без шва, 0.1 = 10%).
    """
    # Стратегия: для корректной топологии без T-стыков используем
    # сетку с двойным количеством вершин по X и треугольниками на стыках

    m = max(0.0, min(mortar_frac, 0.45))  # ограничиваем шов
    step_x = width  / segs_w
    step_y = height / segs_h
    # Половина шва в единицах
    hm_x = step_x * m * 0.5
    hm_y = step_y * m * 0.5

    # Строим полную сетку вершин: (segs_w*2 + 1) × (segs_h + 1)
    # Это даёт нам все нужные точки для смещённых рядов
    nx = segs_w * 2 + 1   # вершин по X
    ny = segs_h + 1        # вершин по Y (ряды)

    verts = []
    # Все вершины: каждый ряд чередует обычные и смещённые позиции
    for row in range(ny):
        y_pos = row / segs_h * height - height / 2.0
        for col in range(nx):
            # col идёт с шагом step_x/2
            x_pos = col * (step_x / 2.0) - width / 2.0
            verts.append(c4d.Vector(x_pos, 0.0, y_pos))

    polys = []
    for row in range(segs_h):
        if row % 2 == 0:
            # Чётный ряд: кирпичи начинаются с 0, каждый кирпич = 2 шага по X
            for brick in range(segs_w):
                # Нижние вершины кирпича (в глобальной сетке col*2 и col*2+2)
                bl = row * nx + brick * 2
                br = row * nx + brick * 2 + 2
                tl = (row + 1) * nx + brick * 2
                tr = (row + 1) * nx + brick * 2 + 2
                # Средние вершины на верхнем и нижнем ребре
                bm = row * nx + brick * 2 + 1
                tm = (row + 1) * nx + brick * 2 + 1

                # Полный кирпич = quad (bl, br, tr, tl)
                # Но нам нужны средние точки для стыковки с нечётным рядом
                # Нижняя половина кирпича
                polys.append(c4d.CPolygon(bl, tl, tm, bm))
                polys.append(c4d.CPolygon(bm, tm, tr, br))
        else:
            # Нечётный ряд: смещение на полкирпича
            # Первый полукирпич у левого края
            bl = row * nx + 0
            br = row * nx + 1
            tl = (row + 1) * nx + 0
            tr = (row + 1) * nx + 1
            polys.append(c4d.CPolygon(bl, tl, tr, br))

            # Полные кирпичи в середине
            for brick in range(segs_w - 1):
                col_start = brick * 2 + 1
                bl = row * nx + col_start
                br = row * nx + col_start + 2
                tl = (row + 1) * nx + col_start
                tr = (row + 1) * nx + col_start + 2
                bm = row * nx + col_start + 1
                tm = (row + 1) * nx + col_start + 1
                polys.append(c4d.CPolygon(bl, tl, tm, bm))
                polys.append(c4d.CPolygon(bm, tm, tr, br))

            # Последний полукирпич у правого края
            col_start = (segs_w - 1) * 2 + 1
            bl = row * nx + col_start
            br = row * nx + col_start + 1
            tl = (row + 1) * nx + col_start
            tr = (row + 1) * nx + col_start + 1
            polys.append(c4d.CPolygon(bl, tl, tr, br))

    # Если шов задан — применяем inset к каждому полигону
    if m > 1e-6:
        verts, polys = _inset_polys(verts, polys, hm_x, hm_y)

    return verts, polys


def _build_stack_bond(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Стековая кладка (stack bond) — кирпичи без смещения, ряды ровно над рядами.
    Каждый кирпич — отдельный quad.
    """
    m     = max(0.0, min(mortar_frac, 0.45))
    step_x = width  / segs_w
    step_y = height / segs_h
    hm_x  = step_x * m * 0.5
    hm_y  = step_y * m * 0.5

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
    hm_x  = step_x * m * 0.5
    hm_y  = step_y * m * 0.5

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
    Ёлочка (herringbone / паркет 45°).
    Чередует горизонтальные и вертикальные прямоугольники 1×2.
    segs_w и segs_h определяют число пар по X и Y.
    """
    m    = max(0.0, min(mortar_frac, 0.45))
    # Базовый размер одного "кирпича" ёлочки
    tile_w = width  / (segs_w * 2.0)  # одна единица
    tile_h = height / (segs_h * 2.0)
    hm_x  = tile_w * m * 0.5
    hm_y  = tile_h * m * 0.5

    verts = []
    polys = []

    for row in range(segs_h * 2):
        for col in range(segs_w * 2):
            # Чётность суммы определяет ориентацию: горизонтальный или вертикальный
            if (row + col) % 2 == 0:
                # Горизонтальный кирпич: ширина = 2*tile_w, высота = tile_h
                x0 = col * tile_w - width  / 2.0
                z0 = row * tile_h - height / 2.0
                x1 = x0 + 2.0 * tile_w
                z1 = z0 + tile_h
                # Пропускаем, если выходим за правую границу
                if x1 > width / 2.0 + 1e-4:
                    continue
            else:
                # Вертикальный кирпич: ширина = tile_w, высота = 2*tile_h
                x0 = col * tile_w - width  / 2.0
                z0 = row * tile_h - height / 2.0
                x1 = x0 + tile_w
                z1 = z0 + 2.0 * tile_h
                if z1 > height / 2.0 + 1e-4:
                    continue

            base = len(verts)
            verts.append(c4d.Vector(x0 + hm_x, 0.0, z0 + hm_y))
            verts.append(c4d.Vector(x1 - hm_x, 0.0, z0 + hm_y))
            verts.append(c4d.Vector(x1 - hm_x, 0.0, z1 - hm_y))
            verts.append(c4d.Vector(x0 + hm_x, 0.0, z1 - hm_y))
            if (x1 - hm_x) - (x0 + hm_x) < 1e-6 or (z1 - hm_y) - (z0 + hm_y) < 1e-6:
                continue
            polys.append(c4d.CPolygon(base, base+3, base+2, base+1))

    return verts, polys


def _build_hexagonal(width, height, segs_w, segs_h, mortar_frac=0.0):
    """
    Гексагональные плитки (flat-top ориентация, рядовая укладка).
    segs_w — число гексагонов по X, segs_h — по Y.
    Каждый гексагон — 6-угольник (6 вершин, триангулируется в 4 треугольника).
    mortar_frac — уменьшает радиус каждого гексагона.
    """
    m       = max(0.0, min(mortar_frac, 0.45))
    # Радиус гексагона (от центра до вершины)
    hex_r   = min(width / (segs_w * 2.0), height / (segs_h * math.sqrt(3))) * (1.0 - m)
    # Шаг по X и Y для flat-top гексагональной сетки
    step_x  = hex_r * 2.0 * (width  / (segs_w * hex_r * 2.0)) if hex_r > 1e-6 else 1.0
    step_y  = hex_r * math.sqrt(3)

    # Пересчитываем реальные шаги равномерно
    sx = width  / segs_w
    sy = height / segs_h
    r  = min(sx, sy / math.sqrt(3)) * 0.5 * (1.0 - m)

    verts = []
    polys = []

    real_sx = sx
    real_sy = sy * math.sqrt(3) / 2.0  # вертикальный шаг между рядами

    for row in range(segs_h):
        x_offset = (row % 2) * (real_sx * 0.5)  # нечётные ряды смещены
        for col in range(segs_w):
            cx = col * real_sx + x_offset - width  / 2.0 + real_sx * 0.5
            cz = row * (sy * 0.75) - height / 2.0 + sy * 0.5

            # Вершины flat-top гексагона (6 точек по кругу, 0° = вправо)
            hex_pts = []
            actual_r = min(real_sx, sy) * 0.5 * (1.0 - m)
            for i in range(6):
                angle = math.radians(60.0 * i)
                hx = cx + actual_r * math.cos(angle)
                hz = cz + actual_r * math.sin(angle)
                hex_pts.append(c4d.Vector(hx, 0.0, hz))

            base = len(verts)
            verts.extend(hex_pts)
            # Центральная вершина для веерной триангуляции
            verts.append(c4d.Vector(cx, 0.0, cz))
            center_idx = base + 6

            # 6 треугольников из центра
            for i in range(6):
                a = base + i
                b = base + (i + 1) % 6
                # Используем CPolygon с вырожденным 4-м индексом (треугольник)
                # Обход CW сверху: center → b → a
                polys.append(c4d.CPolygon(center_idx, b, a, a))

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
    # Кирпич = cell/2 × cell
    bw     = cell_w * 0.5
    bh     = cell_h
    hm_x   = bw * m * 0.5
    hm_y   = cell_h * 0.5 * m * 0.5

    verts = []
    polys = []

    def _add_brick(x0, z0, x1, z1):
        """Добавляет один кирпич (quad) в mesh."""
        dx = (x1 - x0) * m * 0.5
        dz = (z1 - z0) * m * 0.5
        if (x1 - x0 - 2*dx) < 1e-6 or (z1 - z0 - 2*dz) < 1e-6:
            return
        base = len(verts)
        verts.append(c4d.Vector(x0 + dx, 0.0, z0 + dz))
        verts.append(c4d.Vector(x1 - dx, 0.0, z0 + dz))
        verts.append(c4d.Vector(x1 - dx, 0.0, z1 - dz))
        verts.append(c4d.Vector(x0 + dx, 0.0, z1 - dz))
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

    OBJECT_NAME  = "BrickPlane"
    _first_ud_id = BP_WIDTH

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Ширина", 400.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Высота", 400.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Кирпичей (X)", 4, 1, 200))
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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAApElEQVR4nO1XQQ6AIAzbCP8SH+ZFHwa+DE9LkCwyTKQe6AlIgcK6LGMqkELINAAhJZYxj7xYE+IQF5dg1OsF8B/w9cIS42HZeK7r1sM1C2htILqL7OFqgIcALkANgTW2vVwN8DTknPP+ROh1e4tbm9Zri4K3brecJ4CbEC7AE9mc/FVmwLNg1gK4CeECZi2YtQBuQriAWQtc2SiOxj96w3KCaM8vfQqEBgGNXZYAAAAASUVORK5CYII="
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
