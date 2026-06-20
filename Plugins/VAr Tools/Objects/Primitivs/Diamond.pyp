# -*- coding: utf-8 -*-
"""
Diamond — Cinema 4D ObjectData Plugin
Параметрический драгоценный камень с несколькими видами огранки.

Поддерживаемые огранки:
  0 — Brilliant (Бриллиант / Круглая)
  1 — Princess  (Принцесса / Квадратная)
  2 — Emerald   (Изумруд / Ступенчатая)
  3 — Marquise  (Маркиза / Навет)
  4 — Pear      (Груша)
  5 — Oval      (Овал)
  6 — Cushion   (Кушон / Подушка)
  7 — Asscher   (Ашер / Квадрат-ступени)
  8 — Heart     (Сердце)
  9 — Rose      (Роза — старинная огранка)
  
"""

import c4d  # type: ignore
import math
import os
import base64
import tempfile

if not hasattr(c4d, "DESC_UNIT_NONE"):
    c4d.DESC_UNIT_NONE = 0

# ─── Plugin ID & Name ────────────────────────────────────────────────────────

ID_DIAMOND   = 1069031
NAME_DIAMOND = "Diamond v1.0"

# ─── UserData SubID ───────────────────────────────────────────────────────────
# SubID=1 зарезервирован под группу. Поля начинаются с 2.

UD_GROUP       = 1

DM_CUT        = 2   # Тип огранки (Cycle)
DM_SIZE       = 3   # Размер (радиус описывающей окружности)
DM_HEIGHT     = 4   # Полная высота камня
DM_CROWN_H    = 5   # Доля высоты короны (0..1)
DM_GIRDLE_H   = 6   # Толщина рундиста (мм)
DM_SEGS       = 7   # Число граней (для огранок на основе n-гона)
DM_TABLE_SIZE = 8   # Размер площадки (0..1 от размера камня)
DM_CULET      = 9   # Размер калеты (кончик павильона, 0..1)
DM_STEPS      = 10  # Число ступеней (для Emerald / Asscher)

# Индексы огранок
CUT_BRILLIANT = 0
CUT_PRINCESS  = 1
CUT_EMERALD   = 2
CUT_MARQUISE  = 3
CUT_PEAR      = 4
CUT_OVAL      = 5
CUT_CUSHION   = 6
CUT_ASSCHER   = 7
CUT_HEART     = 8
CUT_ROSE      = 9


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
    return did[1].id


def _add_in_group(op, grp_subid, bc):
    """Добавляет элемент UserData внутрь группы с данным SubID."""
    bc[c4d.DESC_PARENTGROUP] = c4d.DescID(
        c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
        c4d.DescLevel(grp_subid, c4d.DTYPE_GROUP, 0)
    )
    return op.AddUserData(bc)


def _make_float_bc(name, default, minval, maxval,
                   unit=c4d.DESC_UNIT_METER, step=1.0):
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


def _make_cycle_bc(name, default, items):
    """Создаёт поле-выпадающий список (CUSTOMGUI_CYCLE)."""
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
    cycle_bc = c4d.BaseContainer()
    for i, label in enumerate(items):
        cycle_bc[i] = label
    bc[c4d.DESC_CYCLE] = cycle_bc
    return bc


def _ud_already_created(op, first_field_uid):
    did, _ = _ud_descid(op, first_field_uid)
    return did is not None


def _ud_set_default(op, uid, value):
    did, _ = _ud_descid(op, uid)
    if did is not None:
        op[did] = value


# ─── Математические утилиты ───────────────────────────────────────────────────

def _lerp(a, b, t):
    return a + (b - a) * t


def _circle_pts(n, radius, y, start_angle=0.0):
    """n равномерных точек по окружности радиуса radius на высоте y."""
    pts = []
    for i in range(n):
        a = start_angle + i / n * 2.0 * math.pi
        pts.append(c4d.Vector(radius * math.cos(a), y, radius * math.sin(a)))
    return pts


def _ellipse_pts(n, rx, rz, y, start_angle=0.0):
    """n равномерных точек по эллипсу (rx, rz) на высоте y."""
    pts = []
    for i in range(n):
        a = start_angle + i / n * 2.0 * math.pi
        pts.append(c4d.Vector(rx * math.cos(a), y, rz * math.sin(a)))
    return pts


def _make_poly_object(points, polys, name):
    """
    Создаёт c4d.PolygonObject.
    polys — список c4d.CPolygon.
    """
    obj = c4d.PolygonObject(len(points), len(polys))
    obj.SetName(name)
    for i, pt in enumerate(points):
        obj.SetPoint(i, pt)
    for i, poly in enumerate(polys):
        obj.SetPolygon(i, poly)
    obj.Message(c4d.MSG_UPDATE)
    return obj


# ─── Утилиты построения граней ───────────────────────────────────────────────

def _quad(a, b, c, d):
    """Четырёхугольник (a→b→c→d)."""
    return c4d.CPolygon(a, b, c, d)


def _tri(a, b, c):
    """Треугольник (a→b→c), четвёртая вершина дублирует третью."""
    return c4d.CPolygon(a, b, c, c)


def _fan(hub, ring, start, closed=True):
    """
    Веер треугольников из hub во все рёбра кольца ring[start..].
    ring — список индексов вершин.
    closed — замыкать последнее ребро на ring[start].
    Возвращает список CPolygon.
    """
    polys = []
    n = len(ring)
    end = n if closed else n - 1
    for i in range(end):
        a = ring[i]
        b = ring[(i + 1) % n]
        polys.append(_tri(hub, a, b))
    return polys


def _band(ring_lo, ring_hi, closed=True):
    """
    Полоса квадов между двумя кольцами одинакового размера.
    ring_lo / ring_hi — списки индексов вершин нижнего и верхнего колец.
    closed — замыкать последнее ребро.
    Возвращает список CPolygon.
    """
    polys = []
    n = len(ring_lo)
    end = n if closed else n - 1
    for i in range(end):
        a = ring_lo[i]
        b = ring_lo[(i + 1) % n]
        c = ring_hi[(i + 1) % n]
        d = ring_hi[i]
        polys.append(_quad(a, b, c, d))
    return polys


def _band_mixed(ring_lo, ring_hi):
    """
    Полоса треугольников/квадов между кольцами разного размера
    (ring_hi вдвое больше ring_lo).
    Используется при переходе от площадки к короне у бриллианта.
    """
    polys = []
    n_lo = len(ring_lo)
    n_hi = len(ring_hi)
    ratio = n_hi // n_lo   # обычно 2 или 4
    for i in range(n_lo):
        lo_a = ring_lo[i]
        lo_b = ring_lo[(i + 1) % n_lo]
        hi_start = i * ratio
        for j in range(ratio):
            hi_a = ring_hi[(hi_start + j) % n_hi]
            hi_b = ring_hi[(hi_start + j + 1) % n_hi]
            if j == 0:
                polys.append(_tri(lo_a, hi_a, hi_b))
            elif j == ratio - 1:
                polys.append(_tri(lo_b, hi_a, hi_b))
            else:
                polys.append(_tri(hi_a, lo_a, hi_b))
    return polys


# ─── Огранки ─────────────────────────────────────────────────────────────────
#
# Для каждой огранки реализована отдельная функция build_*.
# Все функции возвращают (points, polys) — списки c4d.Vector и c4d.CPolygon.
#
# Система координат:
#   Y↑  — вверх
#   Камень ориентирован вершиной (калетой) вниз, площадкой вверх.
#   Центр камня — на уровне рундиста (girdle).
#
# Параметры огранки:
#   size       — радиус рундиста (mm)
#   height     — полная высота (mm)
#   crown_h    — доля высоты короны  [0..1]
#   girdle_h   — толщина рундиста (mm)
#   table_size — радиус площадки / size [0..1]
#   culet      — радиус калеты / size   [0..1]
#   segs       — число сегментов по окружности
#   steps      — число ступеней павильона/короны (для изумруда, ашера)
#
# Высоты (y-координаты) отсчитываются так:
#   y_culet    — нижняя вершина / калета
#   y_girdle_b — нижний край рундиста
#   y_girdle_t — верхний край рундиста
#   y_table    — площадка
#
# ─────────────────────────────────────────────────────────────────────────────

def build_brilliant(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Классическая круглая бриллиантовая огранка.

    Структура:
      Павильон (8 главных граней + 8 нижних полуграней на 16-гон):
        • 16 нижних звёздных граней (треугольники) от рундиста к калете.
      Рундист:
        • тонкая полоса квадов.
      Корона (8 главных граней + 8 звёздных + 16 верхних полуграней):
        • кольцо звёздных треугольников.
        • переход к площадке.
      Площадка: замыкающий n-гон.

    Для управляемой геометрии используем segs граней (кратное 8,
    минимум 16). Внутри всё строим через два кольца: рундист и площадка.
    """

    # Приводим segs к чётному числу ≥ 8
    segs = max(8, segs)
    if segs % 2 != 0:
        segs += 1

    r        = size                     # радиус рундиста
    r_table  = r * max(0.01, min(0.99, table_size))
    r_culet  = r * max(0.0,  min(0.3,  culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.6, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    # y-уровни
    y_culet    = -(pavilion + girdle / 2.0)
    y_gird_b   = -girdle / 2.0
    y_gird_t   = +girdle / 2.0
    y_table    = y_gird_t + crown

    # ── Вершины ──────────────────────────────────────────────────────────────
    pts = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    # Калета (одна вершина или маленькое кольцо)
    if r_culet < 0.5:
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = []
        for i in range(segs):
            a = i / segs * 2.0 * math.pi
            culet_ring.append(_add(c4d.Vector(r_culet * math.cos(a),
                                               y_culet,
                                               r_culet * math.sin(a))))
        culet_idx = None

    # Нижний рундист
    gird_b = [_add(c4d.Vector(r * math.cos(i / segs * 2.0 * math.pi),
                               y_gird_b,
                               r * math.sin(i / segs * 2.0 * math.pi)))
              for i in range(segs)]

    # Верхний рундист
    gird_t = [_add(c4d.Vector(r * math.cos(i / segs * 2.0 * math.pi),
                               y_gird_t,
                               r * math.sin(i / segs * 2.0 * math.pi)))
              for i in range(segs)]

    # Промежуточное кольцо короны (половинная высота, уменьшенный радиус)
    r_mid   = r * 0.85
    y_mid   = y_gird_t + crown * 0.45
    crown_mid = [_add(c4d.Vector(r_mid * math.cos(i / segs * 2.0 * math.pi + math.pi / segs),
                                  y_mid,
                                  r_mid * math.sin(i / segs * 2.0 * math.pi + math.pi / segs)))
                 for i in range(segs)]

    # Площадка
    table = [_add(c4d.Vector(r_table * math.cos(i / segs * 2.0 * math.pi),
                              y_table,
                              r_table * math.sin(i / segs * 2.0 * math.pi)))
             for i in range(segs)]

    # ── Полигоны ─────────────────────────────────────────────────────────────
    polys = []

    # Павильон: от калеты до рундиста
    if culet_ring is None:
        # точечная калета → веер треугольников
        polys += _fan(culet_idx, gird_b, 0)
    else:
        # кольцо калеты → полоса квадов + замыкающий веер
        polys += _band(culet_ring, gird_b)

    # Рундист: тонкая полоса квадов
    polys += _band(gird_b, gird_t)

    # Корона нижняя: рундист → промежуточное кольцо (смещено на полшага)
    # Чередуем «остроугольные» треугольники (как главные грани бриллианта)
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi   = crown_mid[i]
        polys.append(_tri(lo_a, lo_b, hi))

    # Корона верхняя: промежуточное кольцо → площадка (тоже смещена)
    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        # Чередуем: ромбы к площадке
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        # Квад со срезанными углами — стандартный бриллиант
        polys.append(_quad(hi_a, hi_b, tb, ta))

    # Площадка: веер из первой вершины площадки
    hub = table[0]
    for i in range(1, segs - 1):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_princess(size, height, crown_h, girdle_h, table_size, culet, steps):
    """
    Огранка Принцесса (Princess Cut) — квадрат в плане.

    Особенности:
      • Павильон: квадратное основание сужается к калете.
        Грани образуют «шевроны» (угловые грани + центральные).
      • Рундист: квадратное кольцо.
      • Корона: невысокая пирамида с площадкой-квадратом.
    """

    r        = size
    r_table  = r * max(0.2, min(0.95, table_size))
    r_culet  = r * max(0.0,  min(0.2,  culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    steps = max(1, min(6, steps))

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    # Угол 45° — квадрат вписан в окружность радиуса r
    sq = r  # полудиагональ квадрата

    def _sq_ring(half, y):
        """4 угловые точки квадрата (по часовой)."""
        return [
            _add(c4d.Vector( half, y,  half)),
            _add(c4d.Vector(-half, y,  half)),
            _add(c4d.Vector(-half, y, -half)),
            _add(c4d.Vector( half, y, -half)),
        ]

    def _sq_ring8(half, y):
        """
        8 точек квадрата (углы + середины сторон).
        Позволяет строить грани-шевроны павильона.
        """
        h = half
        m = half  # середина стороны = половина стороны квадрата
        # Порядок: угол, середина, угол, …
        pts_list = [
            c4d.Vector( h, y,  0),   # 0  правая середина
            c4d.Vector( h, y,  h),   # 1  правый-передний угол
            c4d.Vector( 0, y,  h),   # 2  передняя середина
            c4d.Vector(-h, y,  h),   # 3  левый-передний угол
            c4d.Vector(-h, y,  0),   # 4  левая середина
            c4d.Vector(-h, y, -h),   # 5  левый-задний угол
            c4d.Vector( 0, y, -h),   # 6  задняя середина
            c4d.Vector( h, y, -h),   # 7  правый-задний угол
        ]
        return [_add(p) for p in pts_list]

    # Калета
    if r_culet < 0.5:
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _sq_ring(r_culet, y_culet)
        culet_idx = None

    # Ступени павильона
    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        half = _lerp(sq, r_culet if r_culet >= 0.5 else 0.0, t)
        y    = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_sq_ring8(half, y))

    # Нижний рундист (8 точек)
    gird_b = _sq_ring8(sq, y_gird_b)

    # Верхний рундист (4 точки)
    gird_t = _sq_ring(sq, y_gird_t)

    # Площадка (4 точки)
    table = _sq_ring(r_table, y_table)

    # ── Полигоны павильона ────────────────────────────────────────────────────
    # Павильон строится «шевронами» между gird_b и калетой через ступени.
    # gird_b имеет 8 точек (чередование угол/середина).
    # Для каждой грани (4 основные + 4 угловые) строим вееры.

    prev_ring = gird_b
    for pav_ring in pav_rings:
        # Квады между текущим и предыдущим кольцами (оба 8-точечные)
        polys += _band(prev_ring, pav_ring)
        prev_ring = pav_ring

    # Закрываем до калеты
    if culet_ring is None:
        # Веер треугольников к точке
        polys += _fan(culet_idx, prev_ring, 0)
    else:
        polys += _band(prev_ring, culet_ring)
        # Кольцо калеты → точка (если culet_ring — 4 точки)
        c4_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _fan(c4_idx, culet_ring, 0)

    # Рундист: gird_b(8) → gird_t(4): чередуем квады и треугольники
    # gird_b: [0=R-mid, 1=RF, 2=F-mid, 3=LF, 4=L-mid, 5=LB, 6=B-mid, 7=RB]
    # gird_t: [0=RF, 1=LF, 2=LB, 3=RB]
    for i in range(4):
        # Каждый угол верхнего рундиста связывает 3 точки нижнего
        lo0 = gird_b[i * 2]         # середина стороны
        lo1 = gird_b[i * 2 + 1]     # угол
        lo2 = gird_b[(i * 2 + 2) % 8]  # следующая середина
        hi  = gird_t[i]
        polys.append(_tri(lo0, lo1, hi))
        polys.append(_tri(lo1, lo2, hi))

    # Корона: gird_t(4) → table(4) (простые квады)
    polys += _band(gird_t, table)

    # Площадка
    polys.append(_quad(table[0], table[1], table[2], table[3]))

    return pts, polys


def build_emerald(size, height, crown_h, girdle_h, table_size, culet, steps):
    """
    Огранка Изумруд (Emerald Cut) — прямоугольник со срезанными углами,
    ступенчатые грани.

    Форма в плане: октагон (прямоугольник 1:1.5 со срезанными углами).
    Ступени задаются параметром steps (1..5).
    """

    # Размер: size — полудиагональ по ширине; длина = 1.5 × ширина
    rx       = size         # полуширина (X)
    rz       = size * 1.4   # полудлина  (Z)
    cut      = size * 0.25  # длина фаски на углу

    r_table_x = rx * max(0.3, min(0.95, table_size))
    r_table_z = rz * max(0.3, min(0.95, table_size))
    r_culet   = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.45, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)
    steps    = max(1, min(5, steps))

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _oct_ring(rx, rz, cut_frac, y):
        """
        8-вершинный октагон (прямоугольник со срезанными углами).
        cut_frac — относительная длина фаски от rx.
        Порядок вершин по часовой: начиная с (+rx, 0, cut_frac*rz).
        """
        cf = cut_frac
        raw = [
            c4d.Vector( rx,          y,  rz - cf * rz),
            c4d.Vector( rx - cf*rx,  y,  rz           ),
            c4d.Vector(-(rx - cf*rx), y,  rz           ),
            c4d.Vector(-rx,          y,  rz - cf * rz),
            c4d.Vector(-rx,          y, -(rz - cf*rz)),
            c4d.Vector(-(rx - cf*rx), y, -rz           ),
            c4d.Vector( rx - cf*rx,  y, -rz           ),
            c4d.Vector( rx,          y, -(rz - cf*rz)),
        ]
        return [_add(p) for p in raw]

    cut_main = 0.25  # фаска рундиста
    cut_tab  = 0.20  # фаска площадки (чуть меньше)

    # Рундист
    gird_b = _oct_ring(rx, rz, cut_main, y_gird_b)
    gird_t = _oct_ring(rx, rz, cut_main, y_gird_t)

    # Площадка
    table = _oct_ring(r_table_x, r_table_z, cut_tab, y_table)

    # Калета
    if r_culet < 0.5:
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _oct_ring(r_culet, r_culet * 1.4, cut_main, y_culet)
        culet_idx = None

    # Ступени павильона
    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        srx  = _lerp(rx, r_culet if r_culet >= 0.5 else 0.001, t)
        srz  = _lerp(rz, r_culet * 1.4 if r_culet >= 0.5 else 0.001, t)
        sy   = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_oct_ring(srx, srz, cut_main, sy))

    # Полигоны: павильон
    prev = gird_b
    for pr in pav_rings:
        polys += _band(prev, pr)
        prev = pr

    if culet_ring is None:
        polys += _fan(culet_idx, prev, 0)
    else:
        polys += _band(prev, culet_ring)
        c4c = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _fan(c4c, culet_ring, 0)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Ступени короны
    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        crx = _lerp(rx, r_table_x, t)
        crz = _lerp(rz, r_table_z, t)
        cy  = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_oct_ring(crx, crz, cut_main, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(prev, cr)
        prev = cr
    polys += _band(prev, table)

    # Площадка (веер)
    hub = table[0]
    for i in range(1, 7):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_marquise(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Огранка Маркиза (Marquise / Navette) — эллиптическая, заострённая
    на обоих концах.

    Форма: эллипс 1:2 с двумя острыми точками (на ±Z).
    Грани: бриллиантовая нарезка по эллипсу.
    """

    rx = size          # полуось X
    rz = size * 2.0    # полуось Z (длина)

    segs = max(6, segs)
    if segs % 2 != 0:
        segs += 1

    r_table_x = rx * max(0.1, min(0.9, table_size))
    r_table_z = rz * max(0.1, min(0.9, table_size))
    r_culet   = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _marquise_ring(rx, rz, y):
        """segs вершин по эллипсу."""
        idxs = []
        for i in range(segs):
            a = i / segs * 2.0 * math.pi
            idxs.append(_add(c4d.Vector(rx * math.cos(a), y,
                                         rz * math.sin(a))))
        return idxs

    # Острые концы (полюса по Z)
    tip_front_idx  = _add(c4d.Vector(0.0, y_culet,  rz))
    tip_back_idx   = _add(c4d.Vector(0.0, y_culet, -rz))

    gird_b  = _marquise_ring(rx, rz, y_gird_b)
    gird_t  = _marquise_ring(rx, rz, y_gird_t)
    table   = _marquise_ring(r_table_x, r_table_z, y_table)

    # Калета (полоска между двумя острыми точками)
    # Для маркизы павильон замыкается двумя полюсами
    half = segs // 2
    # Нижняя полуокружность (Z > 0) → к переднему кончику
    front_half = gird_b[:half]
    back_half  = gird_b[half:]

    # Веер треугольников к кончикам
    polys += _fan(tip_front_idx, list(reversed(front_half)), 0)
    polys += _fan(tip_back_idx,  list(reversed(back_half)),  0)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Корона → площадка
    polys += _band(gird_t, table)

    # Площадка (веер)
    hub = table[0]
    for i in range(1, segs - 1):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_pear(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Огранка Груша (Pear / Teardrop) — эллипс с острым кончиком с одной стороны
    и широким закруглением с другой.

    Конструкция: одна заострённая точка по +Z, закруглённый низ.
    """

    rx = size
    rz = size * 1.6    # немного вытянута

    segs = max(8, segs)
    if segs % 2 != 0:
        segs += 1

    r_table_x = rx * max(0.1, min(0.9, table_size))
    r_table_z = rz * max(0.1, min(0.9, table_size))
    r_culet   = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _pear_ring(rx, rz, y):
        """
        segs вершин по форме груши.
        Верхняя половина (Z > 0) — острее (сужается к точке),
        нижняя половина — нормальный эллипс.
        """
        idxs = []
        for i in range(segs):
            a = i / segs * 2.0 * math.pi
            sin_a = math.sin(a)
            cos_a = math.cos(a)
            # Верхняя часть (sin_a > 0) заострена
            if sin_a > 0:
                # Сужаем X пропорционально
                scale_x = 1.0 - sin_a * 0.6
                px = rx * cos_a * scale_x
                pz = rz * sin_a
            else:
                px = rx * cos_a
                pz = rz * sin_a
            idxs.append(_add(c4d.Vector(px, y, pz)))
        return idxs

    # Кончик груши
    tip_idx = _add(c4d.Vector(0.0, y_culet, rz))

    gird_b = _pear_ring(rx, rz, y_gird_b)
    gird_t = _pear_ring(rx, rz, y_gird_t)
    table  = _pear_ring(r_table_x, r_table_z, y_table)

    # Верхняя «острая» половина павильона → к точке
    half_f = segs // 4
    half_b = segs - half_f
    front_arc = gird_b[half_f:half_b]  # верхняя дуга

    polys += _fan(tip_idx, front_arc, 0)

    # Нижняя дуга → к калете
    bottom_arc = gird_b[half_b:] + gird_b[:half_f]
    if r_culet < 0.5:
        culet_idx = _add(c4d.Vector(0.0, y_culet, -rz * 0.5))
        polys += _fan(culet_idx, list(reversed(bottom_arc)), 0)
    else:
        culet_ring = _pear_ring(r_culet, r_culet * 1.6, y_culet)
        polys += _band(bottom_arc, culet_ring)
        c4c = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _fan(c4c, culet_ring, 0)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Корона → площадка
    polys += _band(gird_t, table)

    # Площадка
    hub = table[0]
    for i in range(1, segs - 1):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_oval(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Огранка Овал (Oval Cut) — эллипс, как у бриллианта, но вытянутый.
    Бриллиантовая нарезка граней по эллиптическому рундисту.
    """

    rx = size
    rz = size * 1.5

    segs = max(8, segs)
    if segs % 2 != 0:
        segs += 1

    r_table_x = rx * max(0.1, min(0.9, table_size))
    r_table_z = rz * max(0.1, min(0.9, table_size))
    r_culet   = size * max(0.0, min(0.2, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _oval_ring(rx, rz, y):
        idxs = []
        for i in range(segs):
            a = i / segs * 2.0 * math.pi
            idxs.append(_add(c4d.Vector(rx * math.cos(a), y,
                                         rz * math.sin(a))))
        return idxs

    # Калета
    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _oval_ring(r_culet, r_culet * 1.5, y_culet)
        culet_idx  = None

    gird_b   = _oval_ring(rx, rz, y_gird_b)
    gird_t   = _oval_ring(rx, rz, y_gird_t)
    crown_mid_r = [rx * 0.85, rz * 0.85]
    y_mid       = y_gird_t + crown * 0.45
    crown_mid   = _oval_ring(crown_mid_r[0], crown_mid_r[1], y_mid)
    table       = _oval_ring(r_table_x, r_table_z, y_table)

    # Павильон
    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        polys += _band(culet_ring, gird_b)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Корона нижняя (треугольники)
    for i in range(segs):
        polys.append(_tri(gird_t[i], gird_t[(i + 1) % segs], crown_mid[i]))

    # Корона верхняя (квады)
    for i in range(segs):
        polys.append(_quad(crown_mid[i], crown_mid[(i + 1) % segs],
                           table[(i + 1) % segs], table[i]))

    # Площадка
    hub = table[0]
    for i in range(1, segs - 1):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_cushion(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Огранка Кушон (Cushion Cut) — квадрат с плавно скруглёнными углами,
    бриллиантовая нарезка граней. Своеобразная «квадратная подушка».

    Конструкция: segs точек по «суперэллипсу» (кваземи-квадратный контур).
    """

    r = size
    segs = max(8, segs)
    if segs % 4 != 0:
        segs = ((segs + 3) // 4) * 4  # кратно 4

    r_table  = r * max(0.3, min(0.95, table_size))
    r_culet  = r * max(0.0, min(0.2, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _cushion_ring(r, y, n=None):
        """
        Суперэллипс (степень 4 — «подушка»).
        |x/r|^4 + |z/r|^4 = 1
        """
        if n is None:
            n = segs
        idxs = []
        for i in range(n):
            a = i / n * 2.0 * math.pi
            ca = math.cos(a)
            sa = math.sin(a)
            # Суперэллипс: x = r * |cos(a)|^(1/2) * sign(cos)
            px = r * math.copysign(abs(ca) ** 0.5, ca)
            pz = r * math.copysign(abs(sa) ** 0.5, sa)
            idxs.append(_add(c4d.Vector(px, y, pz)))
        return idxs

    # Калета
    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _cushion_ring(r_culet, y_culet)
        culet_idx  = None

    gird_b    = _cushion_ring(r, y_gird_b)
    gird_t    = _cushion_ring(r, y_gird_t)
    y_mid     = y_gird_t + crown * 0.4
    crown_mid = _cushion_ring(r * 0.82, y_mid)
    table     = _cushion_ring(r_table, y_table)

    # Павильон
    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        polys += _band(culet_ring, gird_b)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Корона нижняя
    for i in range(segs):
        polys.append(_tri(gird_t[i], gird_t[(i + 1) % segs], crown_mid[i]))

    # Корона верхняя
    for i in range(segs):
        polys.append(_quad(crown_mid[i], crown_mid[(i + 1) % segs],
                           table[(i + 1) % segs], table[i]))

    # Площадка
    hub = table[0]
    for i in range(1, segs - 1):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_asscher(size, height, crown_h, girdle_h, table_size, culet, steps):
    """
    Огранка Ашер (Asscher Cut) — квадратный вариант огранки Изумруд,
    1:1 в плане, ступенчатые грани, срезанные углы.
    """

    rx = size
    rz = size  # квадрат

    cut  = 0.30  # доля фаски
    r_tx = rx * max(0.3, min(0.9, table_size))
    r_tz = rz * max(0.3, min(0.9, table_size))
    r_culet = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.45, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)
    steps    = max(1, min(5, steps))

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _asscher_ring(rx, rz, y):
        """8-вершинный октагон (квадрат со срезанными углами)."""
        cf = cut
        raw = [
            c4d.Vector( rx,          y,  rz - cf * rz),
            c4d.Vector( rx - cf*rx,  y,  rz           ),
            c4d.Vector(-(rx - cf*rx), y,  rz           ),
            c4d.Vector(-rx,          y,  rz - cf * rz),
            c4d.Vector(-rx,          y, -(rz - cf*rz)),
            c4d.Vector(-(rx - cf*rx), y, -rz           ),
            c4d.Vector( rx - cf*rx,  y, -rz           ),
            c4d.Vector( rx,          y, -(rz - cf*rz)),
        ]
        return [_add(p) for p in raw]

    gird_b = _asscher_ring(rx, rz, y_gird_b)
    gird_t = _asscher_ring(rx, rz, y_gird_t)
    table  = _asscher_ring(r_tx, r_tz, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _asscher_ring(r_culet, r_culet, y_culet)
        culet_idx  = None

    # Ступени павильона
    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        srx = _lerp(rx, r_culet if r_culet >= 0.5 else 0.001, t)
        srz = _lerp(rz, r_culet if r_culet >= 0.5 else 0.001, t)
        sy  = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_asscher_ring(srx, srz, sy))

    prev = gird_b
    for pr in pav_rings:
        polys += _band(prev, pr)
        prev = pr

    if culet_ring is None:
        polys += _fan(culet_idx, prev, 0)
    else:
        polys += _band(prev, culet_ring)
        c4c = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _fan(c4c, culet_ring, 0)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Ступени короны
    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        crx = _lerp(rx, r_tx, t)
        crz = _lerp(rz, r_tz, t)
        cy  = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_asscher_ring(crx, crz, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(prev, cr)
        prev = cr
    polys += _band(prev, table)

    # Площадка
    hub = table[0]
    for i in range(1, 7):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_heart(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Огранка Сердце (Heart Cut).

    Контур рундиста: верхняя часть — две «дольки» (bumps), нижняя — острый клин.
    Используем параметрическую кривую для контура.
    """

    segs = max(12, segs)
    # Сделаем segs кратным 4 для симметрии
    segs = ((segs + 3) // 4) * 4

    r = size
    r_table  = r * max(0.15, min(0.9, table_size))
    r_culet  = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet  = -(pavilion + girdle / 2.0)
    y_gird_b = -girdle / 2.0
    y_gird_t = +girdle / 2.0
    y_table  = y_gird_t + crown

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _heart_xy(t):
        """
        Параметрический контур сердца.
        t ∈ [0, 1) → (x, z), нормированные примерно к единице.
        Формула: классическое «сердечко» через тригонометрию.
        """
        a = t * 2.0 * math.pi
        # Сердечко: x = 16 sin^3(a), y = 13cos - 5cos2 - 2cos3 - cos4
        # (нормируем к r)
        x =  16.0 * math.sin(a) ** 3
        z = -(13.0 * math.cos(a)
              - 5.0 * math.cos(2 * a)
              - 2.0 * math.cos(3 * a)
              -       math.cos(4 * a))
        # Нормировка: max x ≈ 16, max z ≈ 13
        return x / 17.0, z / 17.0

    def _heart_ring(radius, y, n=None):
        if n is None:
            n = segs
        idxs = []
        for i in range(n):
            t = i / n
            x, z = _heart_xy(t)
            idxs.append(_add(c4d.Vector(x * radius, y, z * radius)))
        return idxs

    # Калета
    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _heart_ring(r_culet, y_culet)
        culet_idx  = None

    gird_b    = _heart_ring(r, y_gird_b)
    gird_t    = _heart_ring(r, y_gird_t)
    y_mid     = y_gird_t + crown * 0.45
    crown_mid = _heart_ring(r * 0.80, y_mid)
    table     = _heart_ring(r_table, y_table)

    # Павильон
    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        polys += _band(culet_ring, gird_b)

    # Рундист
    polys += _band(gird_b, gird_t)

    # Корона нижняя
    for i in range(segs):
        polys.append(_tri(gird_t[i], gird_t[(i + 1) % segs], crown_mid[i]))

    # Корона верхняя
    for i in range(segs):
        polys.append(_quad(crown_mid[i], crown_mid[(i + 1) % segs],
                           table[(i + 1) % segs], table[i]))

    # Площадка
    hub = table[0]
    for i in range(1, segs - 1):
        polys.append(_tri(hub, table[i], table[i + 1]))

    return pts, polys


def build_rose(size, height, crown_h, girdle_h, segs, culet):
    """
    Огранка Роза (Rose Cut) — старинная плоскодонная огранка.

    Особенности:
      • Нижняя часть совершенно плоская (нет павильона).
      • Верхняя часть — куполообразная корона с треугольными гранями-«лепестками».
      • Площадки нет — вершина сходится в одной точке.
      • Рундист — плоский многоугольник.
    """

    segs = max(6, segs)
    if segs % 6 != 0:
        segs = ((segs + 5) // 6) * 6  # кратно 6

    r = size

    total_h  = max(1.0, height)
    girdle   = max(0.3, girdle_h)
    crown    = max(1.0, total_h * max(0.3, min(0.9, crown_h)))

    y_base   = -girdle / 2.0         # нижняя плоская поверхность
    y_gird_t = +girdle / 2.0         # верхний рундист
    y_apex   = y_gird_t + crown      # вершина купола

    pts   = []
    polys = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

    def _ring(radius, y):
        idxs = []
        for i in range(segs):
            a = i / segs * 2.0 * math.pi
            idxs.append(_add(c4d.Vector(radius * math.cos(a), y,
                                         radius * math.sin(a))))
        return idxs

    # Нижняя плоская поверхность
    base_ring = _ring(r, y_base)
    base_center = _add(c4d.Vector(0.0, y_base, 0.0))

    # Нижняя грань (плоское основание) — веер вниз (нормали вниз)
    for i in range(segs):
        a = base_ring[i]
        b = base_ring[(i + 1) % segs]
        polys.append(_tri(base_center, b, a))  # перевёрнут: нормаль вниз

    # Рундист
    gird_b = base_ring
    gird_t = _ring(r, y_gird_t)
    polys += _band(gird_b, gird_t)

    # Корона Розы: два яруса треугольников к вершине.
    # Первый ярус: промежуточное кольцо
    r_mid  = r * 0.5
    y_mid  = y_gird_t + crown * 0.55
    mid_ring = _ring(r_mid, y_mid)

    # Нижние «лепестки» — треугольники от gird_t к mid_ring
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi   = mid_ring[i]
        polys.append(_tri(lo_a, lo_b, hi))

    # «Звёздные» треугольники между нижними лепестками и средним кольцом
    for i in range(segs):
        hi_a = mid_ring[i]
        hi_b = mid_ring[(i + 1) % segs]
        lo   = gird_t[(i + 1) % segs]
        polys.append(_tri(lo, hi_a, hi_b))

    # Вершина
    apex_idx = _add(c4d.Vector(0.0, y_apex, 0.0))
    polys += _fan(apex_idx, list(reversed(mid_ring)), 0)

    return pts, polys


# ─── Диспетчер огранок ───────────────────────────────────────────────────────

def build_diamond_mesh(cut, size, height, crown_h, girdle_h,
                       segs, table_size, culet, steps):
    """
    Диспетчер: по типу огранки вызывает нужный генератор.
    Возвращает (points, polys).
    """

    if cut == CUT_BRILLIANT:
        return build_brilliant(size, height, crown_h, girdle_h,
                               segs, table_size, culet)
    elif cut == CUT_PRINCESS:
        return build_princess(size, height, crown_h, girdle_h,
                              table_size, culet, steps)
    elif cut == CUT_EMERALD:
        return build_emerald(size, height, crown_h, girdle_h,
                             table_size, culet, steps)
    elif cut == CUT_MARQUISE:
        return build_marquise(size, height, crown_h, girdle_h,
                              segs, table_size, culet)
    elif cut == CUT_PEAR:
        return build_pear(size, height, crown_h, girdle_h,
                          segs, table_size, culet)
    elif cut == CUT_OVAL:
        return build_oval(size, height, crown_h, girdle_h,
                          segs, table_size, culet)
    elif cut == CUT_CUSHION:
        return build_cushion(size, height, crown_h, girdle_h,
                             segs, table_size, culet)
    elif cut == CUT_ASSCHER:
        return build_asscher(size, height, crown_h, girdle_h,
                             table_size, culet, steps)
    elif cut == CUT_HEART:
        return build_heart(size, height, crown_h, girdle_h,
                           segs, table_size, culet)
    elif cut == CUT_ROSE:
        return build_rose(size, height, crown_h, girdle_h, segs, culet)
    else:
        return build_brilliant(size, height, crown_h, girdle_h,
                               segs, table_size, culet)


# ─── Базовый класс плагина ───────────────────────────────────────────────────

class _MeshPrimitiveBase(c4d.plugins.ObjectData):
    """
    Базовый класс для mesh-примитивов.
    Подклассы определяют:
      OBJECT_NAME   — имя объекта по умолчанию
      _first_ud_id  — SubID первого поля UserData
      _create_ud()  — создание UserData-полей
      _set_defaults() — установка значений по умолчанию
      _build_mesh() — генерация (points, polys)
    """

    OBJECT_NAME  = "MeshPrimitive"
    _first_ud_id = DM_CUT

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

    def _create_ud(self, op, grp_subid):
        pass

    def _set_defaults(self, op):
        pass

    def _build_mesh(self, op):
        return [], []


# ─── DiamondObject ───────────────────────────────────────────────────────────

class DiamondObject(_MeshPrimitiveBase):
    """Параметрический алмаз с выбором огранки."""

    OBJECT_NAME  = "Diamond"
    _first_ud_id = DM_CUT

    def _create_ud(self, op, grp_subid):
        # 1. Тип огранки
        _add_in_group(op, grp_subid, _make_cycle_bc(
            "Огранка", CUT_BRILLIANT, [
                "Бриллиант (Круглая)",
                "Принцесса (Квадратная)",
                "Изумруд (Ступенчатая)",
                "Маркиза (Навет)",
                "Груша (Teardrop)",
                "Овал",
                "Кушон (Подушка)",
                "Ашер (Квадрат-ступени)",
                "Сердце",
                "Роза (Старинная)",
            ]))

        # 2. Общий размер
        _add_in_group(op, grp_subid, _make_float_bc(
            "Размер", 100.0, 1.0, 100000.0,
            unit=c4d.DESC_UNIT_METER, step=1.0))

        # 3. Высота
        _add_in_group(op, grp_subid, _make_float_bc(
            "Высота", 65.0, 1.0, 100000.0,
            unit=c4d.DESC_UNIT_METER, step=1.0))

        # 4. Доля короны
        _add_in_group(op, grp_subid, _make_float_bc(
            "Высота короны (%)", 0.35, 0.05, 0.6,
            unit=c4d.DESC_UNIT_PERCENT, step=0.01))

        # 5. Толщина рундиста
        _add_in_group(op, grp_subid, _make_float_bc(
            "Рундист", 3.0, 0.5, 50.0,
            unit=c4d.DESC_UNIT_METER, step=0.5))

        # 6. Число граней (сегментов)
        _add_in_group(op, grp_subid, _make_int_bc(
            "Грани", 32, 8, 128))

        # 7. Размер площадки
        _add_in_group(op, grp_subid, _make_float_bc(
            "Площадка (%)", 0.55, 0.05, 0.95,
            unit=c4d.DESC_UNIT_PERCENT, step=0.01))

        # 8. Размер калеты
        _add_in_group(op, grp_subid, _make_float_bc(
            "Калета (%)", 0.0, 0.0, 0.3,
            unit=c4d.DESC_UNIT_PERCENT, step=0.005))

        # 9. Ступени (для Изумруд / Ашер / Принцесса)
        _add_in_group(op, grp_subid, _make_int_bc(
            "Ступени", 2, 1, 5))

    def _set_defaults(self, op):
        _ud_set_default(op, DM_CUT,        CUT_BRILLIANT)
        _ud_set_default(op, DM_SIZE,        100.0)
        _ud_set_default(op, DM_HEIGHT,       65.0)
        _ud_set_default(op, DM_CROWN_H,       0.35)
        _ud_set_default(op, DM_GIRDLE_H,      3.0)
        _ud_set_default(op, DM_SEGS,          32)
        _ud_set_default(op, DM_TABLE_SIZE,     0.55)
        _ud_set_default(op, DM_CULET,          0.0)
        _ud_set_default(op, DM_STEPS,          2)

    def _build_mesh(self, op):
        cut        = int(_ud_get(op, DM_CUT,        CUT_BRILLIANT))
        size       = float(_ud_get(op, DM_SIZE,      100.0))
        height     = float(_ud_get(op, DM_HEIGHT,     65.0))
        crown_h    = float(_ud_get(op, DM_CROWN_H,    0.35))
        girdle_h   = float(_ud_get(op, DM_GIRDLE_H,   3.0))
        segs       = max(8, int(_ud_get(op, DM_SEGS,  32)))
        table_size = float(_ud_get(op, DM_TABLE_SIZE,  0.55))
        culet      = float(_ud_get(op, DM_CULET,       0.0))
        steps      = max(1, min(5, int(_ud_get(op, DM_STEPS, 2))))

        return build_diamond_mesh(
            cut, size, height, crown_h, girdle_h,
            segs, table_size, culet, steps
        )


# ─── Иконка ──────────────────────────────────────────────────────────────────

_ICON_DIAMOND = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAAE+ElEQVRYhe2XbUyVdRjGf/dzXlA8heC7aYmA8mKgZsvyDaN0Sz+4NqwE05blC9rU1OXMtemcrVy2jBXppk5oDbW3D66mpOk0nUzlJAMHR3xDnIF68IDAc85z90UQxXMOMb/Z9en/3Lv+13Xt/v/vPc8D/+Nxh4QjaCE2LidlATC4rEBmEniUfHvYiJcSs0F3AKyO2LgY98wLoeirqwqHbNSdz9/dK1C+MxTfCOd/0dnnida107TbwvHbc9rvDYawHRiWvnVQ1tVDze/v714Vf3pWjRbY3xBEH8ZVVPKzlu79q1+fyK1TmoYUDEwfBIkh9UPfgbKyXpiOKtDcHZ/G+0VJiYk8d2p64rTvZKXn+n3mX47o92vpnvdu+oaPFeHUnI8qHWAsQXUoafHXg1mE7oBpXwFioGwWeLFf1LEzGXE5uwPq+uSXeZUbbzXGNQD0jKhwBczM1a8lvGUUnf8m85rvBROH/yimIwfRZcDqYBbB70BZWS+QHLC2kBZ/PSBU1DfFrUMFVemwTy0RAG9T7DoCeEhKqgPNBWMJJZV9g9kEPwJ3xUYwloyq6J7ywd4B7wjMFih/umfRlto7ycsztw+c0p6+Z071/uge5Z9fufXyfIVUYN8Pr17b/NtzDW7QXFITHtqFDkegnyUlNDkcW4pOr8s44Ft0cOTRsQeAfXZhlGmx6EZ9RkmDRdyD+3zmwHircaBbhRPNPZjt9LHqzf39i0bfOnl6XPSWlemb00ZFqn+xLC+tDBkAQzd1C7RMnfbPSeLNbRMy5g0qqu7dMgDYluaJjIn22aa/fjimn+tE1Y++7pYfwHXHsHu3BfrsnHhjT50r0OSOaxwD8FSts6zoeF7G8MBJGzAVkU3AjPvsOgSQeyN2tW+9r7p3S2Pr89khjTeH1nSLro3y18fWRLTNeGyN88naKLM+tjoipnRI483WenXvlsaa/rd999prdRjfDndAv0iJV7U2FUWnTlicuLD5nCs2hdRn2kS3z9INhuAASucUyM67tbmiJGFgzi2Qj9vEij1Rieal0q/L8yLTb5QctgXMD2VVpae9X4cjuHtGMyj5KRaxnwF/HjCzXeKLlhAlAZLb2igkY3DNUm7fJ+a0csudg6NeGblhNKPiKh70glBjmJZYhWgOaCZuT1Zr2Q+/Y9ETg5R7bSMFi142gwNttb8rskGyQBYEMw8dAODZhHzQAtBvOe1JAJj3vVw0BAdK0j1/khWcb++SKgBKymNRyQXZTWpcQSiLsC8jWowcoBabFlBc7ABQpRkwCjPVVZipLsASuAPAwYN2xJ4PeME+P5x8+ABj4rwYZAOjcUStARAoFuVqk43EBidJAjVqUAxAr0FrgbGgs9tf3q4HABgRfxR0AyJrcVdM8nfjDwRTbaSgpKgSsCuHOFs5DmQNqutJTfizM9KdCwBQd2U9cBxk17tLL9kV6tUi2RCSEbzZy84LFvnAKUzvhs7Kdj7A5Ml+1J8NRIE/T+GSCGkKaSJcwGnlAr0JSBZjxpiPPgDcN5o/j6/zqpAmMHLP+LrbnRm5Rwd3Rb5R4rm9PVvrt2ep1zjj8eL2FHZF6r91oBUtRs7whove9IQFPSYlLHQNa7rc0JmRexjCfpYHQ81XLx3p33JjPMC1iJgjA5Ycm9gVna51AOhv3qxrWzfX1YXihkL4/4JgEGMF6ldElEBgZZd1Hnv8C8di9QRamaG9AAAAAElFTkSuQmCC"


def _make_icon():
    if _ICON_DIAMOND == "000":
        # Иконка не задана — возвращаем None, C4D использует иконку по умолчанию
        return None
    try:
        png_data = base64.b64decode(_ICON_DIAMOND)
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
    except Exception:
        return None


ICO_DIAMOND = _make_icon()


# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_DIAMOND,
        str         = NAME_DIAMOND,
        g           = DiamondObject,
        description = "",
        icon        = ICO_DIAMOND,
        info        = c4d.OBJECT_GENERATOR,
    )
