# -*- coding: utf-8 -*-
"""
GeodesicDome — Cinema 4D ObjectData Plugin
Параметрический геодезический купол с полным контролем над примитивом.

Поддерживаемые типы покрытия:
  0 — Triangles (Классический триангулированный геодезический купол)
  1 — Hexagons  (Сотовое покрытие: шестиугольники + пятиугольники)
  2 — Quads     (Квадратное покрытие — Quadrilateral Grid)
  3 — Spiral    (Спиральные линии — Phyllotaxis / Golden Angle)
  4 — Voronoi   (Органические ячейки Вороного)
  5 — Diamond   (Ромбическое покрытие — Diamond / Kite Lattice)
  6 — Bricks    (Кирпичная кладка — Staggered Quad Rows)
  7 — Pentagons (Пятиугольное покрытие Пентагональной грани)
  8 — Triacon   (Разбиение Трикон — двойник икосаэдра)
  9 — Weave     (Плетение — перекрёстное разбиение)

Архитектурные решения:
  - Полный купол (сфера)
  - Полукупол (50 %)
  - Усечённый купол (произвольный угол среза)
  - Купол на цилиндрическом основании (drum)
  - Обратный купол (вогнутая форма)
"""

import c4d          # type: ignore
import math
import os
import base64
import tempfile

# ─── Константы ────────────────────────────────────────────────────────────────

ID_GEODOME   = 1069092
NAME_GEODOME = "Geodesic Dome 1.0"

# ─── UserData / Description IDs ───────────────────────────────────────────────

GD_GRP_MAIN    = 3000
GD_GRP_ARCH    = 3001

GD_D_PATTERN   = 3010   # Тип покрытия (Cycle)
GD_D_FREQ      = 3011   # Частота разбиения (1..8)
GD_D_RADIUS    = 3012   # Радиус (мм)
GD_D_CUTANGLE  = 3013   # Угол среза от вершины (0..180°)
GD_D_ARCH      = 3014   # Архитектурный режим (Cycle)
GD_D_DRUM_H    = 3015   # Высота барабана (только для режима Drum)
GD_D_INVERT    = 3016   # Инвертировать нормали (вогнутый купол)
GD_D_SMOOTH    = 3017   # Сглаживание (фаска вершин)
GD_D_SEAMS     = 3018   # Показывать швы (доп. рёбра-разрёзы)
GD_D_OPENBASE  = 3019   # Открытое основание (без нижней крышки)
GD_D_FLATBASE  = 3020   # Плоское основание (заглушка)

# Типы покрытия
PAT_TRIANGLES = 0
PAT_HEXAGONS  = 1
PAT_QUADS     = 2
PAT_SPIRAL    = 3
PAT_VORONOI   = 4
PAT_DIAMOND   = 5
PAT_BRICKS    = 6
PAT_PENTAGONS = 7
PAT_TRIACON   = 8
PAT_WEAVE     = 9

PAT_NAMES = [
    "Triangles (Классический)",
    "Hexagons (Соты)",
    "Quads (Квадраты)",
    "Spiral (Спираль / Phyllotaxis)",
    "Voronoi (Органические ячейки)",
    "Diamond (Ромбы)",
    "Bricks (Кирпичная кладка)",
    "Pentagons (Пятиугольники)",
    "Triacon (Трикон / Двойник)",
    "Weave (Плетение)",
]

# Архитектурные режимы
ARCH_DOME     = 0   # Стандартный купол (полусфера или угол среза)
ARCH_FULL     = 1   # Полная сфера
ARCH_DRUM     = 2   # Купол на барабане (цилиндрическом основании)
ARCH_TUNNEL   = 3   # Туннельный свод (половина цилиндра)
ARCH_ELLIPTIC = 4   # Эллиптический купол (сплюснутая сфера)

ARCH_NAMES = [
    "Dome (Купол)",
    "Full Sphere (Полная сфера)",
    "Drum (На барабане)",
    "Tunnel Vault (Туннель)",
    "Elliptic Dome (Эллипс)",
]

# ─── Утилиты ──────────────────────────────────────────────────────────────────

def _v(x, y, z):
    return c4d.Vector(float(x), float(y), float(z))

def _lerp(a, b, t):
    return a + (b - a) * t

def _normalize(v):
    l = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if l < 1e-12:
        return c4d.Vector(0, 1, 0)
    return c4d.Vector(v.x / l, v.y / l, v.z / l)

def _cross(a, b):
    return c4d.Vector(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    )

def _dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z

def _tri(a, b, c):
    return c4d.CPolygon(a, b, c, c)

def _quad(a, b, c, d):
    return c4d.CPolygon(a, b, c, d)

def _sph(theta, phi, r=1.0):
    """Вершина на единичной сфере по углам theta (elevation) и phi (azimuth)."""
    x = r * math.cos(theta) * math.cos(phi)
    y = r * math.sin(theta)
    z = r * math.cos(theta) * math.sin(phi)
    return c4d.Vector(x, y, z)

def _make_poly_object(points, polys, name):
    obj = c4d.PolygonObject(len(points), len(polys))
    obj.SetName(name)
    for i, pt in enumerate(points):
        obj.SetPoint(i, pt)
    for i, poly in enumerate(polys):
        obj.SetPolygon(i, poly)
    obj.Message(c4d.MSG_UPDATE)
    return obj

# ─── Базовые данные икосаэдра ─────────────────────────────────────────────────

def _icosahedron_base():
    """
    Возвращает (vertices, faces) единичного икосаэдра.
    12 вершин, 20 треугольных граней.
    """
    phi = (1.0 + math.sqrt(5.0)) / 2.0

    verts = [
        _normalize(_v(-1,  phi,  0)),
        _normalize(_v( 1,  phi,  0)),
        _normalize(_v(-1, -phi,  0)),
        _normalize(_v( 1, -phi,  0)),
        _normalize(_v( 0, -1,  phi)),
        _normalize(_v( 0,  1,  phi)),
        _normalize(_v( 0, -1, -phi)),
        _normalize(_v( 0,  1, -phi)),
        _normalize(_v( phi,  0, -1)),
        _normalize(_v( phi,  0,  1)),
        _normalize(_v(-phi,  0, -1)),
        _normalize(_v(-phi,  0,  1)),
    ]

    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]
    return verts, faces

def _midpoint_key(a, b):
    return (min(a, b), max(a, b))

def _subdivide_sphere(verts, faces, freq):
    """
    Подразделяет треугольные грани икосаэдра freq раз,
    проецируя новые вершины на единичную сферу.
    Возвращает (verts, triangles) — списки Vector и троек индексов.
    """
    verts = list(verts)
    mid_cache = {}

    def _get_mid(a, b):
        key = _midpoint_key(a, b)
        if key in mid_cache:
            return mid_cache[key]
        mid = _normalize(c4d.Vector(
            (verts[a].x + verts[b].x) * 0.5,
            (verts[a].y + verts[b].y) * 0.5,
            (verts[a].z + verts[b].z) * 0.5,
        ))
        idx = len(verts)
        verts.append(mid)
        mid_cache[key] = idx
        return idx

    triangles = list(faces)
    for _ in range(freq):
        new_tris = []
        mid_cache.clear()
        for (a, b, c) in triangles:
            ab = _get_mid(a, b)
            bc = _get_mid(b, c)
            ca = _get_mid(c, a)
            new_tris.append((a, ab, ca))
            new_tris.append((b, bc, ab))
            new_tris.append((c, ca, bc))
            new_tris.append((ab, bc, ca))
        triangles = new_tris

    return verts, triangles

# ─── Преобразования купола ────────────────────────────────────────────────────

def _apply_dome_cut(verts, triangles, cut_angle_deg, arch_mode,
                    radius, drum_h, elliptic_scale):
    """
    Принимает (verts, triangles) единичной сферы и применяет:
      - Масштаб по радиусу (и эллипс по Y)
      - Срез купола по высоте
      - Drum: добавляет цилиндрическое основание
    Возвращает (pts, tris, edge_verts_y_min) — точки, треугольники,
    минимальный Y рундиста для заглушки.
    """
    cut_angle = max(0.0, min(180.0, cut_angle_deg))
    # y_cut: при cut=90 → полусфера (y_cut=0), при cut=0 → полная сфера снизу
    # Угол меряется от верхнего полюса (+Y): 0=только вершина, 90=полусфера, 180=всё
    y_cut = math.cos(math.radians(cut_angle))  # от -1 до 1

    if arch_mode == ARCH_FULL:
        y_cut = -2.0  # пропустить все вершины

    # Масштабируем вершины
    def _scale(v):
        vy = v.y * elliptic_scale
        return c4d.Vector(v.x * radius, vy * radius, v.z * radius)

    # Фильтруем треугольники выше y_cut
    if arch_mode == ARCH_FULL:
        pts = [_scale(v) for v in verts]
        tris = triangles
        return pts, tris, -radius * elliptic_scale

    # Собираем только те треугольники, где все три вершины выше y_cut
    used = set()
    filtered = []
    for (a, b, c) in triangles:
        if verts[a].y >= y_cut and verts[b].y >= y_cut and verts[c].y >= y_cut:
            used.update([a, b, c])
            filtered.append((a, b, c))

    # Переиндексируем
    old_to_new = {}
    pts = []
    for old_idx in sorted(used):
        old_to_new[old_idx] = len(pts)
        pts.append(_scale(verts[old_idx]))

    tris = [(old_to_new[a], old_to_new[b], old_to_new[c]) for (a, b, c) in filtered]

    y_base = y_cut * radius * elliptic_scale
    return pts, tris, y_base


def _add_drum(pts, tris, y_base, radius, drum_height):
    """
    Добавляет к куполу цилиндрическое основание (drum).
    Находит вершины на уровне y_base, опускает их копии вниз
    и строит боковую стенку цилиндра.
    Возвращает (pts, tris, polys_drum) — pts расширен, polys_drum —
    список CPolygon.
    """
    eps = radius * 0.01
    rim_indices = [i for i, p in enumerate(pts) if abs(p.y - y_base) < eps]

    if len(rim_indices) < 3:
        return pts, tris, []

    # Сортируем по азимуту
    rim_indices.sort(key=lambda i: math.atan2(pts[i].z, pts[i].x))

    # Добавляем нижнее кольцо
    y_drum = y_base - abs(drum_height)
    new_ring = []
    for ri in rim_indices:
        p = pts[ri]
        new_ring.append(len(pts))
        pts.append(c4d.Vector(p.x, y_drum, p.z))

    # Строим квады боковой стенки
    polys = []
    n = len(rim_indices)
    for i in range(n):
        a = rim_indices[i]
        b = rim_indices[(i + 1) % n]
        c = new_ring[(i + 1) % n]
        d = new_ring[i]
        polys.append(_quad(a, b, c, d))

    return pts, tris, polys, y_drum


def _add_flat_base(pts, y_level, radius):
    """
    Возвращает центральную точку заглушки и rim_indices для веера.
    """
    eps = radius * 0.02
    rim = [(i, math.atan2(p.z, p.x)) for i, p in enumerate(pts)
           if abs(p.y - y_level) < eps]
    if not rim:
        return None, []
    rim.sort(key=lambda x: x[1])
    rim_idx = [r[0] for r in rim]
    center_idx = len(pts)
    pts.append(c4d.Vector(0.0, y_level, 0.0))
    polys = []
    n = len(rim_idx)
    for i in range(n):
        a = rim_idx[(i + 1) % n]
        b = rim_idx[i]
        polys.append(_tri(center_idx, a, b))
    return center_idx, polys


# ═══════════════════════════════════════════════════════════════════════════════
# ТИПЫ ПОКРЫТИЯ (Pattern Builders)
# ═══════════════════════════════════════════════════════════════════════════════

def build_triangles(verts, triangles, pts, tris):
    """
    PAT_TRIANGLES — классическое триангулированное покрытие.
    Прямое использование subdivision triangles.
    """
    polys = [_tri(a, b, c) for (a, b, c) in tris]
    return pts, polys


def build_hexagons(verts_raw, triangles_raw, pts, tris):
    """
    PAT_HEXAGONS — сотовое покрытие.
    Алгоритм: двойник (dual) триангулированной сферы.
    Каждый треугольник становится вершиной, каждая вершина — полигоном.

    Строим центроиды треугольников как вершины гексагонов/пентагонов.
    Для каждой исходной вершины собираем окружающие треугольники
    и строим из их центроидов многоугольную грань.
    """
    polys_out = []

    # Центроиды треугольников
    tri_centers = []
    for (a, b, c) in tris:
        cx = (pts[a].x + pts[b].x + pts[c].x) / 3.0
        cy = (pts[a].y + pts[b].y + pts[c].y) / 3.0
        cz = (pts[a].z + pts[b].z + pts[c].z) / 3.0
        # Нормируем на сферу и возвращаем радиус
        length = math.sqrt(cx * cx + cy * cy + cz * cz)
        if length > 1e-10:
            # Сохраняем длину как радиус (точки уже масштабированы)
            tri_centers.append(c4d.Vector(cx, cy, cz))
        else:
            tri_centers.append(c4d.Vector(cx, cy, cz))

    # Для каждой вершины находим окружающие треугольники
    vert_to_tris = {}
    for ti, (a, b, c) in enumerate(tris):
        for v in (a, b, c):
            vert_to_tris.setdefault(v, []).append(ti)

    new_pts = list(tri_centers)  # новые точки = центроиды
    # pts исходные вершины (купол) нам уже не нужны напрямую —
    # полигоны строятся из центроидов

    for vi, tri_list in vert_to_tris.items():
        if len(tri_list) < 3:
            continue
        # Сортируем треугольники вокруг вершины vi по азимуту их центроидов
        vp = pts[vi]
        # Базис: случайный вектор перпендикулярен нормали (= vp нормированный)
        nrm = _normalize(vp)
        # Выбираем базисный вектор, не параллельный нормали
        if abs(nrm.y) < 0.9:
            tmp = c4d.Vector(0, 1, 0)
        else:
            tmp = c4d.Vector(1, 0, 0)
        tang = _normalize(_cross(nrm, tmp))
        btan = _cross(nrm, tang)

        def angle_for(ti):
            c_pt = tri_centers[ti]
            d = c4d.Vector(c_pt.x - vp.x, c_pt.y - vp.y, c_pt.z - vp.z)
            u = _dot(d, tang)
            v2 = _dot(d, btan)
            return math.atan2(v2, u)

        sorted_tris = sorted(tri_list, key=angle_for)
        n = len(sorted_tris)

        if n == 3:
            a, b, c_ = sorted_tris
            polys_out.append(_tri(a, b, c_))
        elif n == 4:
            a, b, c_, d = sorted_tris
            polys_out.append(_quad(a, b, c_, d))
        elif n == 5:
            # Пятиугольник → 3 треугольника
            a, b, c_, d, e = sorted_tris
            polys_out.append(_tri(a, b, c_))
            polys_out.append(_tri(a, c_, d))
            polys_out.append(_tri(a, d, e))
        elif n == 6:
            # Шестиугольник → 4 треугольника (веер)
            a, b, c_, d, e, f = sorted_tris
            polys_out.append(_quad(a, b, c_, d))
            polys_out.append(_quad(a, d, e, f))
        else:
            # Общий случай: веер треугольников
            for i in range(1, n - 1):
                polys_out.append(_tri(sorted_tris[0], sorted_tris[i], sorted_tris[i + 1]))

    return new_pts, polys_out


def build_quads(verts_raw, triangles_raw, pts, tris, freq):
    """
    PAT_QUADS — квадратное покрытие.
    Строим сетку по сферическим координатам (UV-grid, проецируем на сферу).
    Частота freq задаёт число рядов/столбцов.
    """
    rows = max(2, freq * 4)
    cols = max(4, freq * 8)

    new_pts = []
    polys_out = []

    # Вычисляем y_min и y_max из существующих pts (результат среза)
    if pts:
        ys = [p.y for p in pts]
        y_min = min(ys)
        y_max = max(ys)
    else:
        y_min, y_max = 0.0, 0.0

    # Радиус = максимальный из pts
    r = max((math.sqrt(p.x**2 + p.y**2 + p.z**2) for p in pts), default=100.0)

    # Определяем диапазон theta (elevation)
    theta_max = math.pi / 2.0         # верхний полюс
    theta_min = math.asin(max(-1.0, min(1.0, y_min / r)))

    theta_range = [theta_min + (theta_max - theta_min) * j / rows for j in range(rows + 1)]
    phi_range   = [2.0 * math.pi * k / cols for k in range(cols)]

    # Строим вершины
    grid = []
    for j in range(rows + 1):
        ring = []
        for k in range(cols):
            theta = theta_range[j]
            phi   = phi_range[k]
            x = r * math.cos(theta) * math.cos(phi)
            y = r * math.sin(theta)
            z = r * math.cos(theta) * math.sin(phi)
            ring.append(len(new_pts))
            new_pts.append(c4d.Vector(x, y, z))
        grid.append(ring)

    # Квады
    for j in range(rows):
        for k in range(cols):
            a = grid[j][k]
            b = grid[j][(k + 1) % cols]
            c_ = grid[j + 1][(k + 1) % cols]
            d = grid[j + 1][k]
            polys_out.append(_quad(a, b, c_, d))

    # Верхняя крышка (пирамида к полюсу)
    pole_idx = len(new_pts)
    new_pts.append(c4d.Vector(0.0, r, 0.0))
    top_ring = grid[rows]
    for k in range(cols):
        a = top_ring[k]
        b = top_ring[(k + 1) % cols]
        polys_out.append(_tri(pole_idx, b, a))

    return new_pts, polys_out


def build_spiral(verts_raw, triangles_raw, pts, tris, freq):
    """
    PAT_SPIRAL — спиральное / Phyllotaxis покрытие.
    Используем золотой угол (137.5°) для расположения точек на сфере,
    затем строим Делоне-треугольники через proximity на сфере.
    Для C4D: аппроксимируем через концентрические кольца со смещением.
    """
    r = max((math.sqrt(p.x**2 + p.y**2 + p.z**2) for p in pts), default=100.0)
    ys = [p.y for p in pts] if pts else [0.0, r]
    y_min = min(ys)

    golden_angle = math.pi * (3.0 - math.sqrt(5.0))  # ~137.5°
    n_rings = max(3, freq * 3)
    n_per_ring = max(6, freq * 6)

    new_pts = []
    polys_out = []

    theta_max = math.pi / 2.0
    theta_min = math.asin(max(-1.0, min(1.0, y_min / r)))

    # Строим точки по phyllotaxis (золотой угол) + концентрические спирали
    rings = []
    for j in range(n_rings + 1):
        t = j / n_rings
        theta = theta_min + (theta_max - theta_min) * t
        # Смещение азимута пропорционально j
        ring = []
        offset = j * golden_angle
        for k in range(n_per_ring):
            phi = offset + k / n_per_ring * 2.0 * math.pi
            x = r * math.cos(theta) * math.cos(phi)
            y = r * math.sin(theta)
            z = r * math.cos(theta) * math.sin(phi)
            ring.append(len(new_pts))
            new_pts.append(c4d.Vector(x, y, z))
        rings.append(ring)

    # Квады между кольцами с учётом смещения
    for j in range(n_rings):
        lo = rings[j]
        hi = rings[j + 1]
        n = n_per_ring
        # Вычисляем угловое смещение между кольцами
        offset_angle = golden_angle
        dphi = offset_angle / (2.0 * math.pi / n)
        k_offset = int(round(dphi)) % n

        for k in range(n):
            a = lo[k]
            b = lo[(k + 1) % n]
            c_ = hi[(k + 1 + k_offset) % n]
            d  = hi[(k + k_offset) % n]
            polys_out.append(_quad(a, b, c_, d))

    # Полюс
    pole = len(new_pts)
    new_pts.append(c4d.Vector(0.0, r, 0.0))
    top = rings[n_rings]
    for k in range(n_per_ring):
        polys_out.append(_tri(pole, top[(k + 1) % n_per_ring], top[k]))

    return new_pts, polys_out


def build_voronoi(verts_raw, triangles_raw, pts, tris):
    """
    PAT_VORONOI — органические ячейки.
    Используем двойник Вороного как расширение сотового покрытия:
    добавляем случайный шум к позиции центроидов, затем строим
    те же ячейки-двойники, но с возмущёнными центрами.
    """
    import random
    rng = random.Random(42)   # детерминированный seed

    polys_out = []

    # Немного возмущаем центроиды треугольников
    tri_centers = []
    for (a, b, c) in tris:
        cx = (pts[a].x + pts[b].x + pts[c].x) / 3.0
        cy = (pts[a].y + pts[b].y + pts[c].y) / 3.0
        cz = (pts[a].z + pts[b].z + pts[c].z) / 3.0
        r  = math.sqrt(cx * cx + cy * cy + cz * cz)
        if r < 1e-10:
            tri_centers.append(c4d.Vector(cx, cy, cz))
            continue
        # Возмущение: 5% по касательной
        noise = 0.05
        tx = rng.uniform(-noise, noise)
        ty = rng.uniform(-noise, noise)
        tz = rng.uniform(-noise, noise)
        # Проецируем на сферу
        nx = cx / r + tx
        ny = cy / r + ty
        nz = cz / r + tz
        l2 = math.sqrt(nx * nx + ny * ny + nz * nz)
        tri_centers.append(c4d.Vector(nx * r / l2, ny * r / l2, nz * r / l2))

    vert_to_tris = {}
    for ti, (a, b, c) in enumerate(tris):
        for v in (a, b, c):
            vert_to_tris.setdefault(v, []).append(ti)

    new_pts = list(tri_centers)

    for vi, tri_list in vert_to_tris.items():
        if len(tri_list) < 3:
            continue
        vp = pts[vi]
        nrm = _normalize(vp)
        if abs(nrm.y) < 0.9:
            tmp = c4d.Vector(0, 1, 0)
        else:
            tmp = c4d.Vector(1, 0, 0)
        tang = _normalize(_cross(nrm, tmp))
        btan = _cross(nrm, tang)

        def angle_for(ti):
            c_pt = tri_centers[ti]
            d = c4d.Vector(c_pt.x - vp.x, c_pt.y - vp.y, c_pt.z - vp.z)
            u = _dot(d, tang)
            v2 = _dot(d, btan)
            return math.atan2(v2, u)

        sorted_tris = sorted(tri_list, key=angle_for)
        n = len(sorted_tris)

        if n == 3:
            polys_out.append(_tri(*sorted_tris))
        elif n == 4:
            polys_out.append(_quad(*sorted_tris))
        elif n == 5:
            a, b, c_, d, e = sorted_tris
            polys_out.append(_tri(a, b, c_))
            polys_out.append(_tri(a, c_, d))
            polys_out.append(_tri(a, d, e))
        elif n == 6:
            a, b, c_, d, e, f = sorted_tris
            polys_out.append(_quad(a, b, c_, d))
            polys_out.append(_quad(a, d, e, f))
        else:
            for i in range(1, n - 1):
                polys_out.append(_tri(sorted_tris[0], sorted_tris[i], sorted_tris[i + 1]))

    return new_pts, polys_out


def build_diamond(verts_raw, triangles_raw, pts, tris, freq):
    """
    PAT_DIAMOND — ромбическое покрытие (Kite / Diamond Grid).
    Каждое ребро триангуляции становится ромбом: объединяем
    два смежных треугольника, делящих ребро, в квадрат/ромб.
    """
    # Строим словарь рёбер → смежные треугольники
    edge_to_tris = {}
    for ti, (a, b, c) in enumerate(tris):
        for edge in [_midpoint_key(a, b), _midpoint_key(b, c), _midpoint_key(a, c)]:
            edge_to_tris.setdefault(edge, []).append(ti)

    # Центроиды треугольников
    tri_centers_idx = []
    new_pts = list(pts)
    for (a, b, c) in tris:
        cx = (pts[a].x + pts[b].x + pts[c].x) / 3.0
        cy = (pts[a].y + pts[b].y + pts[c].y) / 3.0
        cz = (pts[a].z + pts[b].z + pts[c].z) / 3.0
        tri_centers_idx.append(len(new_pts))
        new_pts.append(c4d.Vector(cx, cy, cz))

    # Средина рёбер
    edge_mid_idx = {}
    for edge, tris_list in edge_to_tris.items():
        a, b = edge
        mx = (pts[a].x + pts[b].x) * 0.5
        my = (pts[a].y + pts[b].y) * 0.5
        mz = (pts[a].z + pts[b].z) * 0.5
        edge_mid_idx[edge] = len(new_pts)
        new_pts.append(c4d.Vector(mx, my, mz))

    polys_out = []
    used_edges = set()

    for ti, (a, b, c) in enumerate(tris):
        # Для каждого треугольника строим 3 ромба (по одному на каждое ребро)
        tc = tri_centers_idx[ti]
        for (ea, eb) in [_midpoint_key(a, b), _midpoint_key(b, c), _midpoint_key(a, c)]:
            edge = (ea, eb)
            if edge in used_edges:
                continue
            adj = [t for t in edge_to_tris[edge] if t != ti]
            if not adj:
                continue
            tj = adj[0]
            tc2 = tri_centers_idx[tj]
            em = edge_mid_idx[edge]
            # Ромб: центр ti → середина ребра → центр tj → середина ребра (обход)
            # Используем 4 точки: tc, ea-mid, tc2, eb-mid
            # Реально строим quad из двух центроидов и двух вершин ребра
            polys_out.append(_quad(tc, ea, tc2, eb))
            used_edges.add(edge)

    return new_pts, polys_out


def build_bricks(verts_raw, triangles_raw, pts, tris, freq):
    """
    PAT_BRICKS — кирпичная кладка.
    Горизонтальные ряды (latitude), чётные и нечётные смещены
    на полшага (staggered), формируя квады в шахматном порядке.
    """
    r = max((math.sqrt(p.x**2 + p.y**2 + p.z**2) for p in pts), default=100.0)
    ys = [p.y for p in pts] if pts else [0.0, r]
    y_min = min(ys)

    n_rows = max(3, freq * 4)
    n_cols = max(6, freq * 8)

    theta_max = math.pi / 2.0
    theta_min = math.asin(max(-1.0, min(1.0, y_min / r)))

    new_pts = []
    polys_out = []

    grids = []
    for j in range(n_rows + 1):
        t = j / n_rows
        theta = theta_min + (theta_max - theta_min) * t
        # Кирпичное смещение: нечётные ряды сдвинуты на полшага
        offset = (0.5 / n_cols) * 2.0 * math.pi if j % 2 == 1 else 0.0
        ring = []
        for k in range(n_cols):
            phi = offset + k / n_cols * 2.0 * math.pi
            x = r * math.cos(theta) * math.cos(phi)
            y = r * math.sin(theta)
            z = r * math.cos(theta) * math.sin(phi)
            ring.append(len(new_pts))
            new_pts.append(c4d.Vector(x, y, z))
        grids.append(ring)

    # Квады между рядами (с учётом смещения нечётных рядов)
    for j in range(n_rows):
        lo = grids[j]
        hi = grids[j + 1]
        n = n_cols
        # Если нечётный переход → смещение 0.5
        shift = 0 if j % 2 == 0 else 0

        for k in range(n):
            if j % 2 == 0:
                # Чётные → нечётные: hi сдвинуто на 0.5
                a = lo[k]
                b = lo[(k + 1) % n]
                # Ближайшие два в hi
                c_ = hi[(k + 1) % n]
                d  = hi[k]
                polys_out.append(_quad(a, b, c_, d))
            else:
                # Нечётные → чётные
                a = lo[k]
                b = lo[(k + 1) % n]
                c_ = hi[(k + 1) % n]
                d  = hi[k]
                polys_out.append(_quad(a, b, c_, d))

    # Полюс
    pole = len(new_pts)
    new_pts.append(c4d.Vector(0.0, r, 0.0))
    top = grids[n_rows]
    for k in range(n_cols):
        polys_out.append(_tri(pole, top[(k + 1) % n_cols], top[k]))

    return new_pts, polys_out


def build_pentagons(verts_raw, triangles_raw, pts, tris):
    """
    PAT_PENTAGONS — пятиугольное покрытие.
    Берём двойник додекаэдра (12 пятиугольных граней) через
    двойник икосаэдра с частотой 0 и аппроксимируем.
    Для выcоких частот: каждую пятиугольную грань подразделяем.

    Строим через комбинацию шестиугольников и пятиугольников,
    где все пятиугольники выделены явно.
    """
    polys_out = []

    # Центроиды
    tri_centers = []
    for (a, b, c) in tris:
        cx = (pts[a].x + pts[b].x + pts[c].x) / 3.0
        cy = (pts[a].y + pts[b].y + pts[c].y) / 3.0
        cz = (pts[a].z + pts[b].z + pts[c].z) / 3.0
        tri_centers.append(c4d.Vector(cx, cy, cz))

    vert_to_tris = {}
    for ti, (a, b, c) in enumerate(tris):
        for v in (a, b, c):
            vert_to_tris.setdefault(v, []).append(ti)

    new_pts = list(tri_centers)

    for vi, tri_list in vert_to_tris.items():
        n = len(tri_list)
        if n < 3:
            continue
        vp = pts[vi]
        nrm = _normalize(vp)
        if abs(nrm.y) < 0.9:
            tmp = c4d.Vector(0, 1, 0)
        else:
            tmp = c4d.Vector(1, 0, 0)
        tang = _normalize(_cross(nrm, tmp))
        btan = _cross(nrm, tang)

        def angle_for(ti):
            c_pt = tri_centers[ti]
            d = c4d.Vector(c_pt.x - vp.x, c_pt.y - vp.y, c_pt.z - vp.z)
            return math.atan2(_dot(d, btan), _dot(d, tang))

        sorted_tris = sorted(tri_list, key=angle_for)

        # Явно размечаем пятиугольники (вершины с 5 смежными треугольниками)
        # и шестиугольники (6 смежных)
        if n == 5:
            # Пятиугольник → 3 треугольника
            a, b, c_, d, e = sorted_tris
            polys_out.append(_tri(a, b, e))
            polys_out.append(_tri(b, c_, e))
            polys_out.append(_tri(c_, d, e))
        elif n == 6:
            # Шестиугольник → 4 треугольника
            a, b, c_, d, e, f = sorted_tris
            polys_out.append(_quad(a, b, c_, f))
            polys_out.append(_quad(c_, d, e, f))
        else:
            # Общий: веер
            for i in range(1, n - 1):
                polys_out.append(_tri(sorted_tris[0], sorted_tris[i], sorted_tris[i + 1]))

    return new_pts, polys_out


def build_triacon(verts_raw, triangles_raw, pts, tris):
    """
    PAT_TRIACON — разбиение Трикон.
    Двойник икосаэдра: каждая грань оригинального икосаэдра
    порождает треугольник, в котором вставляются промежуточные вершины,
    образуя ромбоэдры (Triacon Chord Rhombus).

    Реализация: каждый треугольник делим на 4 ромба через центр
    и середины рёбер.
    """
    # Для каждого треугольника: центроид + серединные точки рёбер
    edge_mid_cache = {}
    new_pts = list(pts)

    def get_mid(a, b):
        key = _midpoint_key(a, b)
        if key in edge_mid_cache:
            return edge_mid_cache[key]
        # Нормируем на сферу
        r1 = math.sqrt(pts[a].x**2 + pts[a].y**2 + pts[a].z**2)
        mx = (pts[a].x + pts[b].x) * 0.5
        my = (pts[a].y + pts[b].y) * 0.5
        mz = (pts[a].z + pts[b].z) * 0.5
        l = math.sqrt(mx**2 + my**2 + mz**2)
        if l > 1e-10:
            mx, my, mz = mx / l * r1, my / l * r1, mz / l * r1
        idx = len(new_pts)
        new_pts.append(c4d.Vector(mx, my, mz))
        edge_mid_cache[key] = idx
        return idx

    polys_out = []

    for (a, b, c) in tris:
        ab = get_mid(a, b)
        bc = get_mid(b, c)
        ca = get_mid(c, a)
        # Центроид треугольника
        cx = (pts[a].x + pts[b].x + pts[c].x) / 3.0
        cy = (pts[a].y + pts[b].y + pts[c].y) / 3.0
        cz = (pts[a].z + pts[b].z + pts[c].z) / 3.0
        r0 = math.sqrt(pts[a].x**2 + pts[a].y**2 + pts[a].z**2)
        l = math.sqrt(cx**2 + cy**2 + cz**2)
        if l > 1e-10:
            cx, cy, cz = cx / l * r0, cy / l * r0, cz / l * r0
        ctr = len(new_pts)
        new_pts.append(c4d.Vector(cx, cy, cz))

        # 3 ромба внутри треугольника: a-ab-ctr-ca, b-bc-ctr-ab, c-ca-ctr-bc
        polys_out.append(_quad(a, ab, ctr, ca))
        polys_out.append(_quad(b, bc, ctr, ab))
        polys_out.append(_quad(c, ca, ctr, bc))

    return new_pts, polys_out


def build_weave(verts_raw, triangles_raw, pts, tris, freq):
    """
    PAT_WEAVE — плетение (перекрёстное разбиение).
    Два набора спиральных линий (левые и правые) образуют
    ромбические ячейки, напоминающие плетёную корзину.

    Реализация: два набора longitude-рядов со смещением.
    """
    r = max((math.sqrt(p.x**2 + p.y**2 + p.z**2) for p in pts), default=100.0)
    ys = [p.y for p in pts] if pts else [0.0, r]
    y_min = min(ys)

    n_strands = max(4, freq * 4)  # число прядей в каждом направлении
    n_steps   = max(6, freq * 6)  # шаги по высоте

    theta_max = math.pi / 2.0
    theta_min = math.asin(max(-1.0, min(1.0, y_min / r)))

    new_pts = []
    polys_out = []

    # Строим два набора наклонных линий
    # A-strands: наклон +45°, B-strands: наклон -45°
    # Каждая прядь — спираль на сфере
    twist = math.pi / n_strands  # угол закручивания

    def strand_pt(strand_i, step_j, direction):
        t = step_j / n_steps
        theta = theta_min + (theta_max - theta_min) * t
        # Базовый азимут прядi + скручивание
        phi_base = strand_i / n_strands * 2.0 * math.pi
        phi = phi_base + direction * twist * step_j
        x = r * math.cos(theta) * math.cos(phi)
        y = r * math.sin(theta)
        z = r * math.cos(theta) * math.sin(phi)
        return c4d.Vector(x, y, z)

    # Строим сетку A (direction = +1)
    grid_a = []
    for si in range(n_strands):
        col = []
        for sj in range(n_steps + 1):
            col.append(len(new_pts))
            new_pts.append(strand_pt(si, sj, +1))
        grid_a.append(col)

    # Строим сетку B (direction = -1), со смещением на полшага
    grid_b = []
    for si in range(n_strands):
        col = []
        for sj in range(n_steps + 1):
            col.append(len(new_pts))
            new_pts.append(strand_pt(si + 0.5, sj, -1))
        grid_b.append(col)

    # Строим ромбы из пересечений прядей
    # Каждый квадрат: A[i][j] - B[i][j] - A[i+1][j+1] - B[i][j+1] ... 
    # Упрощённо: квады между соседними шагами A-сетки
    for si in range(n_strands):
        for sj in range(n_steps):
            a = grid_a[si][sj]
            b = grid_a[(si + 1) % n_strands][sj]
            c_ = grid_a[(si + 1) % n_strands][sj + 1]
            d  = grid_a[si][sj + 1]
            polys_out.append(_quad(a, b, c_, d))

    # Добавляем квады из B-сетки (ромбы поперёк)
    for si in range(n_strands):
        for sj in range(n_steps):
            a = grid_b[si][sj]
            b = grid_b[(si + 1) % n_strands][sj]
            c_ = grid_b[(si + 1) % n_strands][sj + 1]
            d  = grid_b[si][sj + 1]
            polys_out.append(_quad(a, b, c_, d))

    # Полюс
    pole = len(new_pts)
    new_pts.append(c4d.Vector(0.0, r, 0.0))
    for si in range(n_strands):
        a = grid_a[si][n_steps]
        b = grid_a[(si + 1) % n_strands][n_steps]
        polys_out.append(_tri(pole, b, a))
    for si in range(n_strands):
        a = grid_b[si][n_steps]
        b = grid_b[(si + 1) % n_strands][n_steps]
        polys_out.append(_tri(pole, b, a))

    return new_pts, polys_out


# ─── Главная функция построения меша ─────────────────────────────────────────

def build_geodome_mesh(pattern, freq, radius, cut_angle,
                       arch_mode, drum_h, elliptic_scale,
                       open_base, flat_base):
    """
    Главный диспетчер: строит геодезический купол заданного типа.
    Возвращает (points, polys).
    """
    freq = max(1, min(8, freq))

    # 1. Базовый икосаэдр
    ico_verts, ico_faces = _icosahedron_base()

    # 2. Подразделение по частоте
    # Частота для паттернов, работающих непосредственно с триангуляцией:
    subdiv_freq = freq - 1  # 0 = чистый икосаэдр (20 граней)
    verts_s, tris_s = _subdivide_sphere(ico_verts, ico_faces, subdiv_freq)

    # 3. Применяем срез купола и масштаб
    if arch_mode == ARCH_FULL:
        pts_raw, tris_raw, y_base = _apply_dome_cut(
            verts_s, tris_s, 180.0, ARCH_FULL, radius, drum_h, elliptic_scale)
    elif arch_mode == ARCH_ELLIPTIC:
        pts_raw, tris_raw, y_base = _apply_dome_cut(
            verts_s, tris_s, cut_angle, ARCH_DOME, radius, drum_h, elliptic_scale)
    elif arch_mode == ARCH_TUNNEL:
        # Туннель: половина цилиндра — используем особую логику
        pts_raw, tris_raw, y_base = _apply_dome_cut(
            verts_s, tris_s, cut_angle, ARCH_DOME, radius, drum_h, 1.0)
    else:
        pts_raw, tris_raw, y_base = _apply_dome_cut(
            verts_s, tris_s, cut_angle, arch_mode, radius, drum_h, elliptic_scale)

    pts_raw  = list(pts_raw)
    tris_raw = list(tris_raw)

    # 4. Строим паттерн
    if pattern == PAT_TRIANGLES:
        pts_out, polys_out = build_triangles(verts_s, tris_s, pts_raw, tris_raw)

    elif pattern == PAT_HEXAGONS:
        pts_out, polys_out = build_hexagons(verts_s, tris_s, pts_raw, tris_raw)

    elif pattern == PAT_QUADS:
        pts_out, polys_out = build_quads(verts_s, tris_s, pts_raw, tris_raw, freq)

    elif pattern == PAT_SPIRAL:
        pts_out, polys_out = build_spiral(verts_s, tris_s, pts_raw, tris_raw, freq)

    elif pattern == PAT_VORONOI:
        pts_out, polys_out = build_voronoi(verts_s, tris_s, pts_raw, tris_raw)

    elif pattern == PAT_DIAMOND:
        pts_out, polys_out = build_diamond(verts_s, tris_s, pts_raw, tris_raw, freq)

    elif pattern == PAT_BRICKS:
        pts_out, polys_out = build_bricks(verts_s, tris_s, pts_raw, tris_raw, freq)

    elif pattern == PAT_PENTAGONS:
        pts_out, polys_out = build_pentagons(verts_s, tris_s, pts_raw, tris_raw)

    elif pattern == PAT_TRIACON:
        pts_out, polys_out = build_triacon(verts_s, tris_s, pts_raw, tris_raw)

    elif pattern == PAT_WEAVE:
        pts_out, polys_out = build_weave(verts_s, tris_s, pts_raw, tris_raw, freq)

    else:
        pts_out, polys_out = build_triangles(verts_s, tris_s, pts_raw, tris_raw)

    # 5. Барабан (drum)
    drum_polys = []
    y_drum = y_base
    if arch_mode == ARCH_DRUM and drum_h > 0.0:
        result = _add_drum(pts_out, tris_raw, y_base, radius, drum_h)
        pts_out, _, drum_polys_raw, y_drum = result
        drum_polys = drum_polys_raw

    polys_out.extend(drum_polys)

    # 6. Плоское основание (заглушка)
    if flat_base and not open_base:
        y_level = y_drum if arch_mode == ARCH_DRUM else y_base
        _, base_polys = _add_flat_base(pts_out, y_level, radius)
        polys_out.extend(base_polys)

    return pts_out, polys_out


# ─── Plugin Class ─────────────────────────────────────────────────────────────

class GeodesicDomeObject(c4d.plugins.ObjectData):
    """Параметрический геодезический купол для Cinema 4D."""

    OBJECT_NAME = "Geodesic Dome"

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
            self._set_defaults(op)
        return True

    def _set_defaults(self, op):
        op[GD_D_PATTERN]  = PAT_TRIANGLES
        op[GD_D_FREQ]     = 3
        op[GD_D_RADIUS]   = 200.0
        op[GD_D_CUTANGLE] = 90.0
        op[GD_D_ARCH]     = ARCH_DOME
        op[GD_D_DRUM_H]   = 50.0
        op[GD_D_INVERT]   = False
        op[GD_D_SMOOTH]   = False
        op[GD_D_SEAMS]    = False
        op[GD_D_OPENBASE] = False
        op[GD_D_FLATBASE] = True

    def GetVirtualObjects(self, op, hh):
        try:
            pts, polys = self._build_mesh(op)
            obj = _make_poly_object(pts, polys, self.OBJECT_NAME)

            # Инвертирование нормалей (вогнутый купол)
            invert = bool(op[GD_D_INVERT])
            if invert:
                for i in range(len(polys)):
                    p = obj.GetPolygon(i)
                    obj.SetPolygon(i, c4d.CPolygon(p.a, p.d, p.c, p.b))

            # Phong-сглаживание
            smooth = bool(op[GD_D_SMOOTH])
            if smooth:
                phong = obj.MakeTag(c4d.Tphong)
                if phong:
                    phong[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
                    phong[c4d.PHONGTAG_PHONG_ANGLE] = math.radians(60.0)

            return obj
        except Exception as e:
            # Fallback: возвращаем пустой объект
            obj = c4d.PolygonObject(0, 0)
            obj.SetName(self.OBJECT_NAME)
            return obj

    def _build_mesh(self, op):
        pattern  = int(op[GD_D_PATTERN]  or 0)
        freq     = int(op[GD_D_FREQ]     or 3)
        radius   = float(op[GD_D_RADIUS] or 200.0)
        cut_ang  = float(op[GD_D_CUTANGLE] or 90.0)
        arch     = int(op[GD_D_ARCH]     or 0)
        drum_h   = float(op[GD_D_DRUM_H] or 50.0)
        open_b   = bool(op[GD_D_OPENBASE])
        flat_b   = bool(op[GD_D_FLATBASE])

        # Эллиптический масштаб
        elliptic_scale = 0.6 if arch == ARCH_ELLIPTIC else 1.0

        pts, polys = build_geodome_mesh(
            pattern, freq, radius, cut_ang,
            arch, drum_h, elliptic_scale,
            open_b, flat_b
        )
        return pts, polys

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        # ── Основная группа параметров ─────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Geodesic Dome"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_GRP_MAIN, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid = c4d.DescID(c4d.DescLevel(GD_GRP_MAIN, c4d.DTYPE_GROUP, 0))

        # ── Тип покрытия ──────────────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Тип покрытия"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = PAT_TRIANGLES
        cyc = c4d.BaseContainer()
        for i, name in enumerate(PAT_NAMES):
            cyc[i] = name
        bc[c4d.DESC_CYCLE]   = cyc
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_PATTERN, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # ── Частота ───────────────────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Частота"
        bc[c4d.DESC_DEFAULT]   = 3
        bc[c4d.DESC_MIN]       = 1
        bc[c4d.DESC_MAX]       = 8
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 8
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_FREQ, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # ── Радиус ────────────────────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Радиус"
        bc[c4d.DESC_DEFAULT]   = 200.0
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 5.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 10.0
        bc[c4d.DESC_MAXSLIDER] = 1000.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # ── Угол среза ────────────────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Угол среза (°)"
        bc[c4d.DESC_DEFAULT]   = 90.0
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 180.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 10.0
        bc[c4d.DESC_MAXSLIDER] = 180.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_CUTANGLE, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # ── Архитектурный режим ───────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Режим"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = ARCH_DOME
        cyc = c4d.BaseContainer()
        for i, name in enumerate(ARCH_NAMES):
            cyc[i] = name
        bc[c4d.DESC_CYCLE]   = cyc
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_ARCH, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # ── Высота барабана ───────────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Высота барабана"
        bc[c4d.DESC_DEFAULT]   = 50.0
        bc[c4d.DESC_MIN]       = 0.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 5.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 500.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_DRUM_H, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # ── Группа флагов ─────────────────────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Опции"
        bc[c4d.DESC_COLUMNS] = 2
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_GRP_ARCH, c4d.DTYPE_GROUP, 0)),
            bc, gid
        )
        aid = c4d.DescID(c4d.DescLevel(GD_GRP_ARCH, c4d.DTYPE_GROUP, 0))

        # Инвертировать
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Инвертировать (вогнутый)"
        bc[c4d.DESC_DEFAULT] = False
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_INVERT, c4d.DTYPE_BOOL, 0)),
            bc, aid
        )

        # Сглаживание
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Phong-сглаживание"
        bc[c4d.DESC_DEFAULT] = False
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_SMOOTH, c4d.DTYPE_BOOL, 0)),
            bc, aid
        )

        # Открытое основание
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Открытое основание"
        bc[c4d.DESC_DEFAULT] = False
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_OPENBASE, c4d.DTYPE_BOOL, 0)),
            bc, aid
        )

        # Плоская заглушка
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Плоская заглушка"
        bc[c4d.DESC_DEFAULT] = True
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GD_D_FLATBASE, c4d.DTYPE_BOOL, 0)),
            bc, aid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ─── Иконка ──────────────────────────────────────────────────────────────────

_ICON_DC = (
    "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"
)

def _make_icon():
    png_data = base64.b64decode(_ICON_DC)
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


ICO_GEODOME = _make_icon()


# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_GEODOME,
        str         = NAME_GEODOME,
        g           = GeodesicDomeObject,
        description = "Obase",
        icon        = ICO_GEODOME,
        info        = c4d.OBJECT_GENERATOR,
    )
