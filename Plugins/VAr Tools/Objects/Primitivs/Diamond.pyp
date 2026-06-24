# -*- coding: utf-8 -*-
"""
Diamond — Cinema 4D ObjectData Plugin
Параметрический драгоценный камень с несколькими видами огранки.

Поддерживаемые огранки:
  1 — Brilliant (Бриллиант / Круглая)
  2 — Brilliant2 (Бриллиант — квадратная корона)
  3 — Princess  (Принцесса / Квадратная)
  4 — Emerald   (Изумруд / Ступенчатая)
  5 — Marquise  (Маркиза / Навет)
  6 — Pear      (Груша)
  7 — Oval      (Овал)
  8 — Cushion   (Кушон / Подушка)
  9 — Asscher   (Ашер / Квадрат-ступени)
  10 — Heart     (Сердце)
  11 — Rose      (Роза — старинная огранка)
  12 — Trillion  (Триллион — треугольный)
  13 — Lozenge   (Ромб — вытянутый ромб)
  14 — Kite      (Кайт — щитовидная)
  15 — Briolette (Бриолетт — двойная капля)
  16 — Coffin    (Гроб — удлинённый шестиугольник)
  17 — Star      (Звезда — лучевая)
  18 — Flower    (Цветок — лепестки)
  19 — Cross     (Крест — крестообразная)
  20 — Leaf      (Лист — асимметричный)
  21 — Arrow     (Стрела — наконечник)
  22 — Butterfly (Бабочка — двухдольная)
  23 — Celtic    (Кельтский — тройной узел)
  24 — Crown     (Корона — зубчатая)
  25 — Dragon    (Дракон — органическая)


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
NAME_DIAMOND = "Diamond v2.15"

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

# ─── Description-based parameter IDs ──────────────────────────────────
DM_GRP          = 2000
DM_D_CUT        = 2001
DM_D_SIZE       = 2002
DM_D_HEIGHT     = 2003
DM_D_CROWN_H    = 2004
DM_D_GIRDLE_H   = 2005
DM_D_SEGS       = 2006
DM_D_TABLE_SIZE = 2007
DM_D_CULET      = 2008
DM_D_STEPS      = 2009

# Индексы огранок
CUT_BRILLIANT  = 0
CUT_BRILLIANT2 = 1
CUT_PRINCESS   = 2
CUT_EMERALD    = 3
CUT_MARQUISE   = 4
CUT_PEAR       = 5
CUT_OVAL       = 6
CUT_CUSHION    = 7
CUT_ASSCHER    = 8
CUT_HEART      = 9
CUT_ROSE       = 10
CUT_TRILLION   = 11
CUT_LOZENGE    = 12
CUT_KITE       = 13
CUT_BRIOLETTE  = 14
CUT_COFFIN     = 15
CUT_STAR       = 16
CUT_FLOWER     = 17
CUT_CROSS      = 18
CUT_LEAF       = 19
CUT_ARROW      = 20
CUT_BUTTERFLY  = 21
CUT_CELTIC     = 22
CUT_CROWN      = 23
CUT_DRAGON     = 24

# ─── Математические утилиты ───────────────────────────────────────────────────

def _lerp(a, b, t):
    return a + (b - a) * t

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
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))

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

    # Центр площадки
    table_center_idx = _add(c4d.Vector(0.0, y_table, 0.0))

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
        # Направление обхода развёрнуто (b,a,c,d вместо a,b,c,d), чтобы ребро
        # gird_b[i]→gird_b[i+1] было общим с полосой рундиста в противоположном
        # направлении (иначе грань выворачивается при Калета (%) > 0).
        n_cr = len(culet_ring)
        for i in range(n_cr):
            a = culet_ring[(i + 1) % n_cr]
            b = culet_ring[i]
            c = gird_b[i]
            d = gird_b[(i + 1) % n_cr]
            polys.append(_quad(a, b, c, d))
        # Замыкающий веер маленького n-гона калеты от центральной точки
        for i in range(n_cr):
            polys.append(_tri(culet_idx, culet_ring[i], culet_ring[(i + 1) % n_cr]))

    # Рундист: тонкая полоса квадов
    # Обход развёрнут (hi, lo вместо lo, hi), чтобы ребро gird_b[i]→gird_b[i+1]
    # было общим с павильоном в противоположном направлении.
    polys += _band(gird_t, gird_b)

    # Корона нижняя (звёздные грани, нижний ряд): рундист → промежуточное кольцо
    # (смещено на полшага). Обход развёрнут (lo_b, lo_a, hi), чтобы ребро
    # gird_t[i]→gird_t[i+1] было общим с рундистом в противоположном направлении.
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi   = crown_mid[i]
        polys.append(_tri(lo_b, lo_a, hi))

    # Корона нижняя (звёздные грани, верхний ряд): заполняют промежуток между
    # соседними нижними звёздными гранями. Этого треугольника не было вовсе —
    # из-за этого по периметру короны были сквозные дырки.
    for i in range(segs):
        a = gird_t[(i + 1) % segs]
        b = crown_mid[i]
        c = crown_mid[(i + 1) % segs]
        polys.append(_tri(a, b, c))

    # Корона верхняя (основные грани к площадке): промежуточное кольцо → площадка.
    # Из-за смещения crown_mid (math.pi / segs) каждый квад crown_mid→table
    # перекручивается, поэтому триангулируем: 2 треугольника на сегмент.
    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        polys.append(_tri(hi_a, ta, tb))
        polys.append(_tri(hi_a, tb, hi_b))

    # Площадка: веер из центральной точки площадки
    # Обход развёрнут (table[i+1], table[i]), чтобы ребро table[i]→table[i+1]
    # было общим с короной верхней в противоположном направлении.
    for i in range(segs):
        polys.append(_tri(table_center_idx, table[(i + 1) % segs], table[i]))

    return pts, polys

def build_brilliant2(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Бриллиант (Квадратная корона) — вариант с выровненным средним кольцом.

    Отличается от build_brilliant:
      • crown_mid без смещения (нет math.pi / segs) — выровнен с gird_t и table.
      • Корона строится четырёхугольниками (квады), а не треугольниками.
    """

    segs = max(8, segs)
    if segs % 2 != 0:
        segs += 1

    r        = size
    r_table  = r * max(0.01, min(0.99, table_size))
    r_culet  = r * max(0.0,  min(0.3,  culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.6, crown_h)))
    pavilion = max(1.0, total_h - crown - girdle)

    y_culet    = -(pavilion + girdle / 2.0)
    y_gird_b   = -girdle / 2.0
    y_gird_t   = +girdle / 2.0
    y_table    = y_gird_t + crown

    pts = []

    def _add(v):
        idx = len(pts)
        pts.append(v)
        return idx

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
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))

    gird_b = [_add(c4d.Vector(r * math.cos(i / segs * 2.0 * math.pi),
                               y_gird_b,
                               r * math.sin(i / segs * 2.0 * math.pi)))
              for i in range(segs)]

    gird_t = [_add(c4d.Vector(r * math.cos(i / segs * 2.0 * math.pi),
                               y_gird_t,
                               r * math.sin(i / segs * 2.0 * math.pi)))
              for i in range(segs)]

    r_mid   = r * 0.85
    y_mid   = y_gird_t + crown * 0.45
    crown_mid = [_add(c4d.Vector(r_mid * math.cos(i / segs * 2.0 * math.pi),
                                  y_mid,
                                  r_mid * math.sin(i / segs * 2.0 * math.pi)))
                 for i in range(segs)]

    table_center_idx = _add(c4d.Vector(0.0, y_table, 0.0))

    table = [_add(c4d.Vector(r_table * math.cos(i / segs * 2.0 * math.pi),
                              y_table,
                              r_table * math.sin(i / segs * 2.0 * math.pi)))
             for i in range(segs)]

    polys = []

    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        n_cr = len(culet_ring)
        for i in range(n_cr):
            a = culet_ring[(i + 1) % n_cr]
            b = culet_ring[i]
            c = gird_b[i]
            d = gird_b[(i + 1) % n_cr]
            polys.append(_quad(a, b, c, d))
        for i in range(n_cr):
            polys.append(_tri(culet_idx, culet_ring[i], culet_ring[(i + 1) % n_cr]))

    polys += _band(gird_t, gird_b)

    # Корона нижняя: квады gird_t → crown_mid (без смещения, чистые квады)
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        polys.append(_quad(lo_b, lo_a, hi_a, hi_b))

    # Корона верхняя: квады crown_mid → table
    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        polys.append(_quad(hi_b, hi_a, ta, tb))

    # Площадка
    for i in range(segs):
        polys.append(_tri(table_center_idx, table[(i + 1) % segs], table[i]))

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

    # Калета
    if r_culet < 0.5:
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _sq_ring(r_culet, y_culet)
        culet_idx = None

    # Ступени павильона (4 угловые точки — без средних)
    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        half = _lerp(sq, r_culet if r_culet >= 0.5 else 0.0, t)
        y    = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_sq_ring(half, y))

    # Нижний рундист (4 угловые точки)
    gird_b = _sq_ring(sq, y_gird_b)

    # Верхний рундист (4 точки)
    gird_t = _sq_ring(sq, y_gird_t)

    # Площадка (4 точки)
    table = _sq_ring(r_table, y_table)

    # ── Полигоны павильона ────────────────────────────────────────────────────
    prev_ring = gird_b
    for pav_ring in pav_rings:
        polys += _band(prev_ring, pav_ring)
        prev_ring = pav_ring

    # Закрываем до калеты
    if culet_ring is None:
        polys += _fan(culet_idx, prev_ring, 0)
    else:
        polys += _band(prev_ring, culet_ring)
        c4_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _fan(c4_idx, culet_ring, 0)

    # Рундист → корона (простые квады, оба кольца 4-точечные)
    polys += _band(gird_t, gird_b)

    # Корона: gird_t(4) → table(4) (простые квады)
    # Обход развёрнут (table, gird_t вместо gird_t, table), чтобы ребро
    # gird_t[i]→gird_t[i+1] было общим с триангуляцией рундиста выше
    # в противоположном направлении (иначе грань выворачивается).
    polys += _band(table, gird_t)

    # Площадка
    # Обход развёрнут (по часовой относительно исходного), чтобы ребро
    # table[i]→table[i+1] было общим с короной в противоположном направлении.
    polys.append(_quad(table[3], table[2], table[1], table[0]))

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
    polys += _band(gird_t, gird_b)

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
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(8):
        polys.append(_tri(table_center, table[(i + 1) % 8], table[i]))

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

    # Веер треугольников к кончикам. closed=False (НЕ замкнутый): замкнутый
    # веер рисовал паразитную диагональ через центр камня между первой и
    # последней точкой полудуги (например gird_b[0]↔gird_b[half-1]) вместо
    # настоящего рундист-ребра gird_b[half-1]↔gird_b[half] — из-за этого
    # по бокам камня (точки экватора) были сквозные дырки.
    polys += _fan(tip_front_idx, front_half, 0, closed=False)
    polys += _fan(tip_back_idx,  back_half,  0, closed=False)

    # Грани-мостики между кончиками: каждая полудуга-веер сама по себе не
    # замкнута на боках камня (точки gird_b[0] и gird_b[half-1]/gird_b[half]),
    # поэтому нужны 4 треугольника, соединяющие оба кончика через каждую из
    # двух боковых точек рундиста — иначе там были дырки.
    p_right_top = gird_b[0]
    p_left_top  = gird_b[half - 1]
    p_left_bot  = gird_b[half]
    p_right_bot = gird_b[-1]
    polys.append(_tri(tip_front_idx, p_left_top, p_left_bot))
    polys.append(_tri(tip_back_idx,  p_right_bot, p_right_top))
    polys.append(_tri(tip_back_idx,  tip_front_idx, p_left_bot))
    polys.append(_tri(tip_front_idx, tip_back_idx, p_right_top))

    # Рундист
    polys += _band(gird_t, gird_b)

    # Корона → площадка
    polys += _band(table, gird_t)

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(segs):
        polys.append(_tri(table_center, table[(i + 1) % segs], table[i]))

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

    gird_b = _pear_ring(rx, rz, y_gird_b)
    gird_t = _pear_ring(rx, rz, y_gird_t)
    table  = _pear_ring(r_table_x, r_table_z, y_table)

    # Павильон — веер от калеты ко всему рундисту
    if r_culet < 0.5:
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _fan(culet_idx, gird_b, 0)
    else:
        culet_ring = _pear_ring(r_culet, r_culet * 1.6, y_culet)
        culet_idx = _add(c4d.Vector(0.0, y_culet, 0.0))
        polys += _band(gird_b, culet_ring)
        polys += _fan(culet_idx, culet_ring, 0)

    # Рундист
    polys += _band(gird_t, gird_b)

    # Корона → площадка
    polys += _band(table, gird_t)

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(segs):
        polys.append(_tri(table_center, table[(i + 1) % segs], table[i]))

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
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

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
        polys += _band(gird_b, culet_ring)
        polys += _fan(culet_idx, culet_ring, 0)

    # Рундист
    polys += _band(gird_t, gird_b)

    # Корона нижняя (квады)
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        polys.append(_quad(lo_b, lo_a, hi_a, hi_b))

    # Корона верхняя (квады)
    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        polys.append(_quad(hi_b, hi_a, ta, tb))

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(segs):
        polys.append(_tri(table_center, table[(i + 1) % segs], table[i]))

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
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    gird_b    = _cushion_ring(r, y_gird_b)
    gird_t    = _cushion_ring(r, y_gird_t)
    y_mid     = y_gird_t + crown * 0.4
    crown_mid = _cushion_ring(r * 0.82, y_mid)
    table     = _cushion_ring(r_table, y_table)

    # Павильон
    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        polys += _band(gird_b, culet_ring)
        polys += _fan(culet_idx, culet_ring, 0)

    # Рундист
    polys += _band(gird_t, gird_b)

    # Корона нижняя (квады)
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        polys.append(_quad(lo_b, lo_a, hi_a, hi_b))

    # Корона верхняя (квады)
    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        polys.append(_quad(hi_b, hi_a, ta, tb))

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(segs):
        polys.append(_tri(table_center, table[(i + 1) % segs], table[i]))

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

    # Цепочка павильона развёрнута (band(pr, prev) вместо band(prev, pr)), чтобы
    # кольцо gird_b отдавало ребро gird_b[i+1]→gird_b[i] (противоположное полосе
    # рундиста ниже, которая использует gird_b[i]→gird_b[i+1] как «lo»-сторону) —
    # иначе рёбра рундиста дублировались, а не сшивались.
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
    polys += _band(gird_t, gird_b)

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
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(8):
        polys.append(_tri(table_center, table[(i + 1) % 8], table[i]))

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
            t = (i + 0.5) / n
            x, z = _heart_xy(t)
            idxs.append(_add(c4d.Vector(x * radius, y, z * radius)))
        return idxs

    # Калета
    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _heart_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    gird_b    = _heart_ring(r, y_gird_b)
    gird_t    = _heart_ring(r, y_gird_t)
    y_mid     = y_gird_t + crown * 0.45
    crown_mid = _heart_ring(r * 0.80, y_mid)
    table     = _heart_ring(r_table, y_table)

    # Павильон
    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        polys += _band(gird_b, culet_ring)
        polys += _fan(culet_idx, culet_ring, 0)

    # Рундист
    polys += _band(gird_t, gird_b)

    # Корона нижняя (квады)
    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        polys.append(_quad(lo_b, lo_a, hi_a, hi_b))

    # Корона верхняя (квады)
    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        polys.append(_quad(hi_b, hi_a, ta, tb))

    # Площадка (веер от центра)
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(segs):
        polys.append(_tri(table_center, table[(i + 1) % segs], table[i]))

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
        polys.append(_tri(base_center, a, b))

    # Рундист
    gird_t = _ring(r, y_gird_t)
    polys += _band(gird_t, base_ring)

    # Корона Розы: квады от рундиста к промежуточному кольцу, затем веер к вершине.
    r_mid  = r * 0.5
    y_mid  = y_gird_t + crown * 0.55
    mid_ring = _ring(r_mid, y_mid)

    # Нижний ярус — квады от gird_t к mid_ring
    polys += _band(mid_ring, gird_t)

    # Вершина — веер треугольников от mid_ring к apex
    apex_idx = _add(c4d.Vector(0.0, y_apex, 0.0))
    polys += _fan(apex_idx, list(reversed(mid_ring)), 0)

    return pts, polys

def build_trillion(size, height, crown_h, girdle_h, segs, table_size, culet):
    """
    Огранка Триллион (Trillion / Trilliant) — треугольный камень.

    Форма в плане: равносторонний треугольник.
    Структура: павильон (веер к калете), рундист, корона (два яруса квадов),
    площадка (веер от центра).
    """

    segs = max(12, segs)
    if segs % 3 != 0:
        segs = ((segs + 2) // 3) * 3

    r       = size
    r_table = r * max(0.15, min(0.9, table_size))
    r_culet = r * max(0.0,  min(0.15, culet))

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

    def _tri_ring(radius, y):
        """segs точек по равностороннему треугольнику."""
        idxs = []
        side_n = segs // 3
        corners = []
        for c in range(3):
            a = math.pi / 2.0 + c * 2.0 * math.pi / 3.0
            corners.append((radius * math.cos(a), radius * math.sin(a)))
        for side in range(3):
            v0 = corners[side]
            v1 = corners[(side + 1) % 3]
            for j in range(side_n):
                t = float(j) / side_n
                px = v0[0] + (v1[0] - v0[0]) * t
                pz = v0[1] + (v1[1] - v0[1]) * t
                idxs.append(_add(c4d.Vector(px, y, pz)))
        return idxs

    gird_b = _tri_ring(r, y_gird_b)
    gird_t = _tri_ring(r, y_gird_t)
    table  = _tri_ring(r_table, y_table)

    # Калета
    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _tri_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    # Павильон
    if culet_ring is None:
        polys += _fan(culet_idx, gird_b, 0)
    else:
        polys += _band(gird_b, culet_ring)
        polys += _fan(culet_idx, culet_ring, 0)

    # Рундист
    polys += _band(gird_t, gird_b)

    # Корона: два яруса квадов (как brilliant2)
    r_mid  = r * 0.65
    y_mid  = y_gird_t + crown * 0.45
    crown_mid = _tri_ring(r_mid, y_mid)

    for i in range(segs):
        lo_a = gird_t[i]
        lo_b = gird_t[(i + 1) % segs]
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        polys.append(_quad(lo_b, lo_a, hi_a, hi_b))

    for i in range(segs):
        hi_a = crown_mid[i]
        hi_b = crown_mid[(i + 1) % segs]
        ta   = table[i]
        tb   = table[(i + 1) % segs]
        polys.append(_quad(hi_b, hi_a, ta, tb))

    # Площадка — веер от центра
    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(segs):
        polys.append(_tri(table_center, table[(i + 1) % segs], table[i]))

    return pts, polys

def build_lozenge(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Ромб (Lozenge) — вытянутый ромб со ступенчатыми гранями.

    Форма в плане: ромб (4 угла), вытянутый вдоль Z в 1.5 раза.
    Павильон и корона — ступенчатые (как Emerald/Asscher), управляемые steps.
    """

    rx       = size
    rz       = size * 1.5
    r_table_x = rx * max(0.1, min(0.9, table_size))
    r_table_z = rz * max(0.1, min(0.9, table_size))
    r_culet_x = rx * max(0.0, min(0.15, culet))
    r_culet_z = rz * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    def _loz_ring(rx, rz, y, n):
        """Ромб: 4 угла, segs/4 точек на сторону, обход ПРОТИВ часовой (вид сверху)."""
        n = max(4, n)
        if n % 4 != 0:
            n = ((n + 3) // 4) * 4
        corners = [(rx, 0.0), (0.0, rz), (-rx, 0.0), (0.0, -rz)]
        per_side = n // 4
        idxs = []
        for side in range(4):
            x0, z0 = corners[side]
            x1, z1 = corners[(side + 1) % 4]
            for j in range(per_side):
                t = float(j) / per_side
                px = x0 + (x1 - x0) * t
                pz = z0 + (z1 - z0) * t
                idxs.append(_add(c4d.Vector(px, y, pz)))
        return idxs

    gird_b = _loz_ring(rx, rz, y_gird_b, segs)
    gird_t = _loz_ring(rx, rz, y_gird_t, segs)
    table  = _loz_ring(r_table_x, r_table_z, y_table, segs)

    if r_culet_x < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _loz_ring(r_culet_x, r_culet_z, y_culet, segs)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    n = len(gird_b)

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        srx = _lerp(rx, r_culet_x if r_culet_x >= 0.5 else 0.001, t)
        srz = _lerp(rz, r_culet_z if r_culet_z >= 0.5 else 0.001, t)
        sy  = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_loz_ring(srx, srz, sy, segs))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        crx = _lerp(rx, r_table_x, t)
        crz = _lerp(rz, r_table_z, t)
        cy  = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_loz_ring(crx, crz, cy, segs))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(n):
        polys.append(_tri(table_center, table[(i + 1) % n], table[i]))

    return pts, polys

def build_kite(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Кайт (Kite) — щитовидная форма.

    План: верхняя часть шире, нижняя — уже и длиннее.
    4 основных угла + segs/4 точек на сторону.
    Ступенчатые павильон и корона.
    """

    r_w      = size            # полуширина
    l_top    = size * 1.0      # длина верхней части
    l_bot    = size * 1.8      # длина нижней части

    r_tw = r_w * max(0.1, min(0.9, table_size))
    lt   = l_top * max(0.1, min(0.9, table_size))
    lb   = l_bot * max(0.1, min(0.9, table_size))
    r_culet = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    def _kite_ring(rw, lt_len, lb_len, y, n):
        """Кайт: 4 угла (верх, право, низ, лево), обход ПРОТИВ часовой."""
        n = max(4, n)
        if n % 4 != 0:
            n = ((n + 3) // 4) * 4
        corners = [
            ( rw,  0.0),
            ( 0.0, lt_len),
            (-rw,  0.0),
            ( 0.0, -lb_len),
        ]
        per_side = n // 4
        idxs = []
        for side in range(4):
            x0, z0 = corners[side]
            x1, z1 = corners[(side + 1) % 4]
            for j in range(per_side):
                t = float(j) / per_side
                px = x0 + (x1 - x0) * t
                pz = z0 + (z1 - z0) * t
                idxs.append(_add(c4d.Vector(px, y, pz)))
        return idxs

    gird_b = _kite_ring(r_w, l_top, l_bot, y_gird_b, segs)
    gird_t = _kite_ring(r_w, l_top, l_bot, y_gird_t, segs)
    table  = _kite_ring(r_tw, lt, lb, y_table, segs)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        cw = r_w * (r_culet / size) * 0.7
        culet_ring = _kite_ring(cw, r_culet * 0.7, r_culet * 1.2, y_culet, segs)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    n = len(gird_b)

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sw  = _lerp(r_w,  r_w * 0.01, t)
        slt = _lerp(l_top, 0.01, t)
        slb = _lerp(l_bot, 0.01, t)
        sy  = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_kite_ring(sw, slt, slb, sy, segs))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cw = _lerp(r_w,  r_tw, t)
        clt = _lerp(l_top, lt, t)
        clb = _lerp(l_bot, lb, t)
        cy  = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_kite_ring(cw, clt, clb, cy, segs))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(n):
        polys.append(_tri(table_center, table[(i + 1) % n], table[i]))

    return pts, polys

def build_briolette(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Бриолетт (Briolette) — двойная капля.

    Вытянутый эллипс 1:2, ступенчатые павильон и корона.
    """

    rx = size
    rz = size * 2.0

    r_table_x = rx * max(0.1, min(0.8, table_size))
    r_table_z = rz * max(0.1, min(0.8, table_size))
    r_culet   = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    segs2 = max(8, segs)
    if segs2 % 2 != 0:
        segs2 += 1

    def _brio_ring(rbx, rbz, y):
        idxs = []
        for i in range(segs2):
            a = i / segs2 * 2.0 * math.pi
            idxs.append(_add(c4d.Vector(rbx * math.cos(a), y,
                                         rbz * math.sin(a))))
        return idxs

    gird_b = _brio_ring(rx, rz, y_gird_b)
    gird_t = _brio_ring(rx, rz, y_gird_t)
    table  = _brio_ring(r_table_x, r_table_z, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _brio_ring(r_culet, r_culet * 1.5, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    n = len(gird_b)

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        srx = _lerp(rx, r_culet if r_culet >= 0.5 else 0.001, t)
        srz = _lerp(rz, r_culet * 1.5 if r_culet >= 0.5 else 0.001, t)
        sy  = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_brio_ring(srx, srz, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        crx = _lerp(rx, r_table_x, t)
        crz = _lerp(rz, r_table_z, t)
        cy  = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_brio_ring(crx, crz, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(n):
        polys.append(_tri(table_center, table[(i + 1) % n], table[i]))

    return pts, polys

def build_coffin(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Гроб (Coffin) — удлинённый 8-угольник.

    Прямоугольник 1:2 со срезанными углами, ступенчатые павильон и корона.
    """

    rx       = size * 0.85
    rz       = size * 1.7
    cut_cf   = 0.25

    r_tx = rx * max(0.2, min(0.9, table_size))
    r_tz = rz * max(0.2, min(0.9, table_size))
    r_culet = size * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    def _coffin_ring(cx, cz, y):
        """8-угольник: прямоугольник со срезанными углами."""
        cf = cut_cf
        raw = [
            c4d.Vector( cx,              y,  cz - cf * cz),
            c4d.Vector( cx - cf * cx,    y,  cz           ),
            c4d.Vector(-(cx - cf * cx),  y,  cz           ),
            c4d.Vector(-cx,              y,  cz - cf * cz),
            c4d.Vector(-cx,              y, -(cz - cf * cz)),
            c4d.Vector(-(cx - cf * cx),  y, -cz           ),
            c4d.Vector( cx - cf * cx,    y, -cz           ),
            c4d.Vector( cx,              y, -(cz - cf * cz)),
        ]
        return [_add(p) for p in raw]

    gird_b = _coffin_ring(rx, rz, y_gird_b)
    gird_t = _coffin_ring(rx, rz, y_gird_t)
    table  = _coffin_ring(r_tx, r_tz, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _coffin_ring(r_culet * 0.85, r_culet * 1.7, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        srx = _lerp(rx, r_culet * 0.85 if r_culet >= 0.5 else 0.001, t)
        srz = _lerp(rz, r_culet * 1.7 if r_culet >= 0.5 else 0.001, t)
        sy  = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_coffin_ring(srx, srz, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        crx = _lerp(rx, r_tx, t)
        crz = _lerp(rz, r_tz, t)
        cy  = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_coffin_ring(crx, crz, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(8):
        polys.append(_tri(table_center, table[(i + 1) % 8], table[i]))

    return pts, polys

def build_star(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Звезда (Star) — лучевая огранка.

    N-конечная звезда (N = max(3, segs // 4)).
    Чередование внешних и внутренних вершин, ступенчатые павильон и корона.
    """

    r        = size
    n_points = max(3, segs // 4)
    n_verts  = n_points * 2

    r_inner  = r * 0.45
    r_table_o = r * max(0.1, min(0.9, table_size))
    r_table_i = r_inner * max(0.1, min(0.9, table_size))
    r_culet  = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    def _star_ring(r_out, r_in, y):
        idxs = []
        for i in range(n_verts):
            a = i / n_verts * 2.0 * math.pi
            if i % 2 == 0:
                px = r_out * math.cos(a)
                pz = r_out * math.sin(a)
            else:
                px = r_in * math.cos(a)
                pz = r_in * math.sin(a)
            idxs.append(_add(c4d.Vector(px, y, pz)))
        return idxs

    gird_b = _star_ring(r, r_inner, y_gird_b)
    gird_t = _star_ring(r, r_inner, y_gird_t)
    table  = _star_ring(r_table_o, r_table_i, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _star_ring(r_culet, r_culet * 0.45, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        so = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        si = _lerp(r_inner, r_culet * 0.45 if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_star_ring(so, si, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        co = _lerp(r, r_table_o, t)
        ci = _lerp(r_inner, r_table_i, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_star_ring(co, ci, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(n_verts):
        polys.append(_tri(table_center, table[(i + 1) % n_verts], table[i]))

    return pts, polys

def build_flower(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Цветок (Flower) — форма с лепестками.

    Параметрическая кривая: r = r_base + r_petal * cos(N_petals * angle).
    segs задаёт число точек контура, steps — ступени павильона/короны.
    """

    r        = size
    n_petals = max(3, min(8, segs // 4))
    amp      = 0.4

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(12, segs)

    def _flower_ring(radius, y):
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            rd = radius * (1.0 + amp * math.cos(n_petals * a))
            idxs.append(_add(c4d.Vector(rd * math.cos(a), y, rd * math.sin(a))))
        return idxs

    gird_b = _flower_ring(r, y_gird_b)
    gird_t = _flower_ring(r, y_gird_t)
    table  = _flower_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _flower_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_flower_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_flower_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_cross(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Крест (Cross) — крестообразная форма.

    4 луча креста с закруглёнными концами. Параметр segs задаёт
    детализацию контура, steps — ступени павильона/короны.
    """

    r        = size
    arm      = r * 0.35
    length   = r * 0.95

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(12, segs)

    def _cross_ring(radius, y):
        """Крест: 4 луча, контур через max(|cos|,|sin|)."""
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            ca = math.cos(a)
            sa = math.sin(a)
            d = max(abs(ca), abs(sa))
            rd = radius * (0.4 + 0.6 * d)
            idxs.append(_add(c4d.Vector(rd * ca, y, rd * sa)))
        return idxs

    gird_b = _cross_ring(r, y_gird_b)
    gird_t = _cross_ring(r, y_gird_t)
    table  = _cross_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _cross_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_cross_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_cross_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_leaf(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Лист (Leaf) — асимметричная форма листа.

    Одна сторона шире другой. Верхний кончик заострён, нижний — более
    закруглён. Контур через параметрическую кривую.
    """

    r        = size
    asym     = 0.35

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(12, segs)

    def _leaf_ring(radius, y):
        """Лист: асимметрия через sin(angle)*asymmetry."""
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            base = radius * (1.0 + asym * math.sin(a))
            idxs.append(_add(c4d.Vector(base * math.cos(a), y, radius * math.sin(a))))
        return idxs

    gird_b = _leaf_ring(r, y_gird_b)
    gird_t = _leaf_ring(r, y_gird_t)
    table  = _leaf_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _leaf_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_leaf_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_leaf_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_arrow(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Стрела (Arrow) — наконечник стрелы.

    Заострённый конец по +Z, расширенная задняя часть по -Z.
    Контур: передняя половина — заострение, задняя — расширение с вырезом.
    """

    r        = size

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(12, segs)

    def _arrow_ring(radius, y):
        """Стрела: полярный радиус с крыльями и вырезом сзади."""
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            ca = math.cos(a)
            sa = math.sin(a)
            wing_r = 1.0 + 0.5 * abs(sa)
            notch = max(0.0, -ca) * 0.4
            rd = radius * (wing_r - notch)
            idxs.append(_add(c4d.Vector(rd * ca, y, rd * sa)))
        return idxs

    gird_b = _arrow_ring(r, y_gird_b)
    gird_t = _arrow_ring(r, y_gird_t)
    table  = _arrow_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _arrow_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_arrow_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_arrow_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_butterfly(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Бабочка (Butterfly) — двухдольная симметричная форма.

    Две верхние доли (широкие) и две нижние (меньше), сужение на «талии».
    Контур через комбинацию синусоид.
    """

    r        = size
    top_amp  = 0.5
    bot_amp  = 0.25
    waist    = 0.3

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(16, segs)

    def _butter_ring(radius, y):
        """Бабочка: верхние доли + нижние доли + сужение на талии."""
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            sin_a = math.sin(a)
            cos_a = math.cos(a)
            if sin_a >= 0:
                lobe = 1.0 + top_amp * abs(cos_a)
            else:
                lobe = 1.0 + bot_amp * abs(cos_a)
            waist_factor = 1.0 - waist * abs(cos_a) * abs(cos_a)
            rd = radius * lobe * waist_factor
            idxs.append(_add(c4d.Vector(rd * cos_a, y, rd * sin_a)))
        return idxs

    gird_b = _butter_ring(r, y_gird_b)
    gird_t = _butter_ring(r, y_gird_t)
    table  = _butter_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _butter_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_butter_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_butter_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_celtic(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Кельтский (Celtic) — тройной узел.

    Три петли через cos(3a) и cos(6a) + девятая гармоника для переплетения.
    """

    r        = size

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(24, segs)

    def _celtic_ring(radius, y):
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            rd = radius * (1.0 + 0.35 * math.cos(3.0 * a)
                                + 0.12 * math.cos(6.0 * a)
                                + 0.15 * math.sin(9.0 * a))
            idxs.append(_add(c4d.Vector(rd * math.cos(a), y, rd * math.sin(a))))
        return idxs

    gird_b = _celtic_ring(r, y_gird_b)
    gird_t = _celtic_ring(r, y_gird_t)
    table  = _celtic_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _celtic_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_celtic_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_celtic_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_crown(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Корона (Crown) — зубчатая.

    Чередование заострённых зубцов и глубоких впадин.
    Форма зубцов через cos(n*angle) с показателем степени 0.6.
    """

    r        = size
    n_teeth  = max(5, segs // 3)
    depth    = 0.4

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(16, segs)

    def _crown_ring(radius, y):
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            tooth = math.cos(n_teeth * a)
            sharp = math.copysign(abs(tooth) ** 0.6, tooth)
            rd = radius * (1.0 - depth * (1.0 - sharp))
            idxs.append(_add(c4d.Vector(rd * math.cos(a), y, rd * math.sin(a))))
        return idxs

    gird_b = _crown_ring(r, y_gird_b)
    gird_t = _crown_ring(r, y_gird_t)
    table  = _crown_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _crown_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_crown_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_crown_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

def build_dragon(size, height, crown_h, girdle_h, segs, table_size, culet, steps):
    """
    Огранка Дракон (Dragon) — органическая асимметрия.

    5 гармоник с фазовыми сдвигами: 2a, 3a, 5a, 7a, 11a.
    Результат — плавно текущий асимметричный контур.
    """

    r        = size

    r_table = r * max(0.1, min(0.85, table_size))
    r_culet = r * max(0.0, min(0.15, culet))

    total_h  = max(1.0, height)
    girdle   = max(0.5, girdle_h)
    crown    = max(1.0, total_h * max(0.05, min(0.5, crown_h)))
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

    nv = max(24, segs)

    def _dragon_ring(radius, y):
        idxs = []
        for i in range(nv):
            a = i / nv * 2.0 * math.pi
            rd = radius * (1.0 + 0.30 * math.sin(2.0 * a + 0.3)
                                + 0.18 * math.cos(3.0 * a - 0.7)
                                + 0.12 * math.sin(5.0 * a + 1.1)
                                + 0.08 * math.cos(7.0 * a - 0.4)
                                + 0.05 * math.sin(11.0 * a + 2.0))
            idxs.append(_add(c4d.Vector(rd * math.cos(a), y, rd * math.sin(a))))
        return idxs

    gird_b = _dragon_ring(r, y_gird_b)
    gird_t = _dragon_ring(r, y_gird_t)
    table  = _dragon_ring(r_table, y_table)

    if r_culet < 0.5:
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))
        culet_ring = None
    else:
        culet_ring = _dragon_ring(r_culet, y_culet)
        culet_idx  = _add(c4d.Vector(0.0, y_culet, 0.0))

    pav_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        sr = _lerp(r, r_culet if r_culet >= 0.5 else 0.001, t)
        sy = _lerp(y_gird_b, y_culet, t)
        pav_rings.append(_dragon_ring(sr, sy))

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

    polys += _band(gird_t, gird_b)

    crown_rings = []
    for s in range(steps):
        t = (s + 1) / (steps + 1)
        cr = _lerp(r, r_table, t)
        cy = _lerp(y_gird_t, y_table, t)
        crown_rings.append(_dragon_ring(cr, cy))

    prev = gird_t
    for cr in crown_rings:
        polys += _band(cr, prev)
        prev = cr
    polys += _band(table, prev)

    table_center = _add(c4d.Vector(0.0, y_table, 0.0))
    for i in range(nv):
        polys.append(_tri(table_center, table[(i + 1) % nv], table[i]))

    return pts, polys

# ─── Диспетчер огранок ───────────────────────────────────────────────────────

def build_diamond_mesh(cut, size, height, crown_h, girdle_h,
                       segs, table_size, culet, steps):
    """
    Диспетчер: по типу огранки вызывает нужный генератор.
    Возвращает (points, polys).
    """

    if cut == CUT_BRILLIANT:
        return build_brilliant(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_BRILLIANT2:
        return build_brilliant2(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_PRINCESS:
        return build_princess(size, height, crown_h, girdle_h, table_size, culet, steps)
    elif cut == CUT_EMERALD:
        return build_emerald(size, height, crown_h, girdle_h, table_size, culet, steps)
    elif cut == CUT_MARQUISE:
        return build_marquise(size, height, crown_h, girdle_h,  segs, table_size, culet)
    elif cut == CUT_PEAR:
        return build_pear(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_OVAL:
        return build_oval(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_CUSHION:
        return build_cushion(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_ASSCHER:
        return build_asscher(size, height, crown_h, girdle_h, table_size, culet, steps)
    elif cut == CUT_HEART:
        return build_heart(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_ROSE:
        return build_rose(size, height, crown_h, girdle_h, segs, culet)
    elif cut == CUT_TRILLION:
        return build_trillion(size, height, crown_h, girdle_h, segs, table_size, culet)
    elif cut == CUT_LOZENGE:
        return build_lozenge(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_KITE:
        return build_kite(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_BRIOLETTE:
        return build_briolette(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_COFFIN:
        return build_coffin(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_STAR:
        return build_star(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_FLOWER:
        return build_flower(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_CROSS:
        return build_cross(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_LEAF:
        return build_leaf(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_ARROW:
        return build_arrow(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_BUTTERFLY:
        return build_butterfly(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_CELTIC:
        return build_celtic(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_CROWN:
        return build_crown(size, height, crown_h, girdle_h, segs, table_size, culet, steps)
    elif cut == CUT_DRAGON:
        return build_dragon(size, height, crown_h, girdle_h, segs, table_size, culet, steps)

    else:
        return build_brilliant(size, height, crown_h, girdle_h,
                               segs, table_size, culet)

# ─── Базовый класс плагина ───────────────────────────────────────────────────

class _MeshPrimitiveBase(c4d.plugins.ObjectData):
    """
    Базовый класс для mesh-примитивов.
    Использует Description-систему для UI (вкладки в Attributes Manager).
    Подклассы определяют:
      OBJECT_NAME     — имя объекта по умолчанию
      GetDDescription() — описание UI (вкладки и параметры)
      _set_defaults() — установка значений по умолчанию
      _build_mesh()   — генерация (points, polys)
    """

    OBJECT_NAME = "MeshPrimitive"

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
            self._set_defaults(op)
        return True

    def GetVirtualObjects(self, op, hh):
        points, polys = self._build_mesh(op)
        return _make_poly_object(points, polys, self.OBJECT_NAME)

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags
        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK

    def _set_defaults(self, op):
        pass

    def _build_mesh(self, op):
        return [], []


# ─── DiamondObject ───────────────────────────────────────────────────────────

class DiamondObject(_MeshPrimitiveBase):
    """Параметрический алмаз с выбором огранки."""

    OBJECT_NAME = "Diamond"

    def _set_defaults(self, op):
        op[DM_D_CUT]        = CUT_BRILLIANT
        op[DM_D_SIZE]       = 100.0
        op[DM_D_HEIGHT]     = 65.0
        op[DM_D_CROWN_H]    = 0.35
        op[DM_D_GIRDLE_H]   = 3.0
        op[DM_D_SEGS]       = 32
        op[DM_D_TABLE_SIZE] = 0.55
        op[DM_D_CULET]      = 0.0
        op[DM_D_STEPS]      = 2

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_GRP, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid = c4d.DescID(c4d.DescLevel(DM_GRP, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Огранка"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = CUT_BRILLIANT
        cyc = c4d.BaseContainer()
        cyc[0] = "Бриллиант (Круглая)"
        cyc[1] = "Бриллиант (Квадратная)"
        cyc[2] = "Принцесса (Квадратная)"
        cyc[3] = "Изумруд (Ступенчатая)"
        cyc[4] = "Маркиза (Навет)"
        cyc[5] = "Груша (Teardrop)"
        cyc[6] = "Овал"
        cyc[7] = "Кушон (Подушка)"
        cyc[8] = "Ашер (Квадрат-ступени)"
        cyc[9] = "Сердце"
        cyc[10] = "Роза (Старинная)"
        cyc[11] = "Триллион (Треугольный)"
        cyc[12] = "Ромб (Lozenge)"
        cyc[13] = "Кайт (Kite)"
        cyc[14] = "Бриолетт (Briolette)"
        cyc[15] = "Гроб (Coffin)"
        cyc[16] = "Звезда (Star)"
        cyc[17] = "Цветок (Flower)"
        cyc[18] = "Крест (Cross)"
        cyc[19] = "Лист (Leaf)"
        cyc[20] = "Стрела (Arrow)"
        cyc[21] = "Бабочка (Butterfly)"
        cyc[22] = "Кельтский (Celtic)"
        cyc[23] = "Корона (Crown)"
        cyc[24] = "Дракон (Dragon)"
        bc[c4d.DESC_CYCLE] = cyc
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_CUT, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Размер"
        bc[c4d.DESC_DEFAULT]   = 100.0
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 20.0
        bc[c4d.DESC_MAXSLIDER] = 200.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_SIZE, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Высота"
        bc[c4d.DESC_DEFAULT]   = 65.0
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 20.0
        bc[c4d.DESC_MAXSLIDER] = 200.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_HEIGHT, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Высота короны"
        bc[c4d.DESC_DEFAULT]   = 0.35
        bc[c4d.DESC_MIN]       = 0.05
        bc[c4d.DESC_MAX]       = 0.6
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_STEP]      = 0.01
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_CROWN_H, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Рундист"
        bc[c4d.DESC_DEFAULT]   = 3.0
        bc[c4d.DESC_MIN]       = 0.5
        bc[c4d.DESC_MAX]       = 50.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 0.5
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.5
        bc[c4d.DESC_MAXSLIDER] = 10.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_GIRDLE_H, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Грани"
        bc[c4d.DESC_DEFAULT]   = 32
        bc[c4d.DESC_MIN]       = 8
        bc[c4d.DESC_MAX]       = 128
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_SEGS, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Площадка"
        bc[c4d.DESC_DEFAULT]   = 0.55
        bc[c4d.DESC_MIN]       = 0.05
        bc[c4d.DESC_MAX]       = 0.95
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_STEP]      = 0.01
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_TABLE_SIZE, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Калета"
        bc[c4d.DESC_DEFAULT]   = 0.0
        bc[c4d.DESC_MIN]       = 0.0
        bc[c4d.DESC_MAX]       = 0.3
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_STEP]      = 0.005
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_CULET, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Ступени"
        bc[c4d.DESC_DEFAULT]   = 2
        bc[c4d.DESC_MIN]       = 1
        bc[c4d.DESC_MAX]       = 5
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DM_D_STEPS, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def _build_mesh(self, op):
        cut        = int(op[DM_D_CUT])
        size       = float(op[DM_D_SIZE])
        height     = float(op[DM_D_HEIGHT])
        crown_h    = float(op[DM_D_CROWN_H])
        girdle_h   = float(op[DM_D_GIRDLE_H])
        segs       = max(8, int(op[DM_D_SEGS]))
        table_size = float(op[DM_D_TABLE_SIZE])
        culet      = float(op[DM_D_CULET])
        steps      = max(1, min(5, int(op[DM_D_STEPS])))

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
        description = "Obase",
        icon        = ICO_DIAMOND,
        info        = c4d.OBJECT_GENERATOR,
    )
