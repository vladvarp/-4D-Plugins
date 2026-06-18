# -*- coding: utf-8 -*-
"""
FloorGenerator — Cinema 4D ObjectData Plugin v1.0
==================================================
Генератор напольных покрытий (аналог Floor Generator для 3ds Max).
Берёт дочерний плоский полигон как границу и генерирует внутри неё
покрытие выбранного типа: ёлочка, паркет, соты.

Паттерны:
  • HERRINGBONE  — шеврон с заполнением пустот (P1, P2)
  • PARQUET      — обычный паркет со смещением рядов
  • HONEYCOMB    — гексагональные плитки (соты)
  • HERRINGBONE_V2 — ёлка (паркетная кладка под 90°)

Возможности:
  • Регулируемая толщина плиток
  • Фаска (bevel) на кромках
  • Швы: включение/отключение, ширина
  • Угол поворота паттерна
  • Рандомизированные UV с настройкой ширины, длины, угла
  • Индивидуальный рандом угла UV для каждой плитки
  • Группы текстур через теги выделения (P — плитки, S — фаски/швы)

ID плагина: 1068969
"""

import c4d
import math
import random
import os
import base64
import tempfile


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin ID & Name
# ══════════════════════════════════════════════════════════════════════════════

ID_FLOORGEN   = 1068969
NAME_FLOORGEN = "Floor Generator v2.4"

# ══════════════════════════════════════════════════════════════════════════════
#  Паттерны
# ══════════════════════════════════════════════════════════════════════════════

PAT_HERRINGBONE    = 0
PAT_PARQUET        = 1
PAT_HONEYCOMB      = 2
PAT_HERRINGBONE_V2 = 3

PAT_NAMES = ["Шеврон", "Паркет", "Соты", "Ёлка"]


# ══════════════════════════════════════════════════════════════════════════════
#  UserData SubID — порядок вызовов AddUserData
# ══════════════════════════════════════════════════════════════════════════════

# Группа «Паттерн»
UD_G_PAT    = 1
FG_PATTERN  = 2
FG_TILE_W   = 3
FG_TILE_H   = 4
FG_PAT_X    = 5
FG_PAT_Y    = 6
FG_ANGLE    = 7
FG_OFFSET   = 8
FG_SEED     = 9
FG_PARQ_RAND_W = 10

# Группа «Толщина и фаска»
UD_G_THK    = 11
FG_THICKNESS = 12
FG_BEVEL    = 13

# Группа «Швы»
UD_G_SEAM   = 14
FG_SEAM_ON  = 15
FG_SEAM_W   = 16

# Группа «UV»
UD_G_UV     = 17
FG_UV_SX    = 18
FG_UV_SY    = 19
FG_UV_ROT   = 20
FG_UV_RAND  = 21
FG_UV_RANDR = 22
FG_UV_RANDOFF   = 23
FG_UV_RANDOFF_X = 24
FG_UV_RANDOFF_Y = 25
FG_UV_RAND_SEED = 26

FG_FIRST_PARAM = FG_PATTERN


# ══════════════════════════════════════════════════════════════════════════════
#  Дефолтные значения
# ══════════════════════════════════════════════════════════════════════════════

DEF_PATTERN   = PAT_HERRINGBONE
DEF_TILE_W    = 100.0
DEF_TILE_H    = 20.0
DEF_PAT_X     = 0.0
DEF_PAT_Y     = 0.0
DEF_ANGLE     = 0.0
DEF_OFFSET    = 0.5
DEF_SEED      = 0

DEF_THICKNESS = 1.0
DEF_BEVEL     = 0.2

DEF_SEAM_ON   = True
DEF_SEAM_W    = 0.1

DEF_UV_SX     = 100.0
DEF_UV_SY     = 100.0
DEF_UV_ROT    = 0.0
DEF_UV_RAND   = False
DEF_UV_RANDR  = 0.0
DEF_UV_RANDOFF   = False
DEF_UV_RANDOFF_X = 100.0
DEF_UV_RANDOFF_Y = 100.0
DEF_UV_RAND_SEED = 0

DEF_PARQ_RAND_W = 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  UserData helpers (following MHL pattern)
# ══════════════════════════════════════════════════════════════════════════════

def _ud_descid(op, uid):
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

def _ud_set(op, uid, value):
    did, _ = _ud_descid(op, uid)
    if did is not None:
        op[did] = value

def _ud_exists(op, uid):
    did, _ = _ud_descid(op, uid)
    return did is not None

def _add_group(op, name):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_TITLEBAR]   = 1
    bc[c4d.DESC_DEFAULT]    = 1
    did = op.AddUserData(bc)
    return did[1].id

def _add_in_group(op, grp_subid, bc):
    bc[c4d.DESC_PARENTGROUP] = c4d.DescID(
        c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
        c4d.DescLevel(grp_subid, c4d.DTYPE_GROUP, 0)
    )
    return op.AddUserData(bc)

def _float_bc(name, default, minval, maxval, unit=c4d.DESC_UNIT_METER, step=1.0):
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

def _int_bc(name, default, minval, maxval):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_MIN]        = minval
    bc[c4d.DESC_MAX]        = maxval
    bc[c4d.DESC_STEP]       = 1
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc

def _bool_bc(name, default):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BOOL)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc

def _cycle_bc(name, default, items):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
    cyc = c4d.BaseContainer()
    for i, label in enumerate(items):
        cyc[i] = label
    bc[c4d.DESC_CYCLE]   = cyc
    bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
    return bc


# ══════════════════════════════════════════════════════════════════════════════
#  Математика / утилиты
# ══════════════════════════════════════════════════════════════════════════════

def _v3_len(v):
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)

def _v3_normalize(v):
    d = _v3_len(v)
    if d < 1e-12:
        return c4d.Vector(0, 1, 0)
    return c4d.Vector(v.x / d, v.y / d, v.z / d)

def _v3_dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z

def _v3_cross(a, b):
    return c4d.Vector(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x
    )


def _rotate_pt_2d(px, py, cx, cy, angle):
    dx, dy = px - cx, py - cy
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return dx * cos_a - dy * sin_a + cx, dx * sin_a + dy * cos_a + cy


def _polygon_center_2d(poly):
    n = len(poly)
    sx = sum(p[0] for p in poly) / n
    sy = sum(p[1] for p in poly) / n
    return sx, sy


def _point_in_polygon(px, py, polygon):
    """Ray casting — point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _build_frame(normal):
    """Orthonormal basis from normal: returns (u, v, n)."""
    n = _v3_normalize(normal)
    if abs(n.x) < 0.9:
        helper = c4d.Vector(1, 0, 0)
    else:
        helper = c4d.Vector(0, 1, 0)
    u = _v3_normalize(_v3_cross(helper, n))
    v = _v3_normalize(_v3_cross(n, u))
    return u, v, n


def _to_3d(u, v, origin, u_axis, v_axis, normal, h=0.0):
    return origin + u_axis * u + v_axis * v + normal * h


def _bbox_2d(pts):
    us = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    return min(us), max(us), min(vs), max(vs)


def _inset_polygon(poly, amount):
    """Inset convex polygon by `amount` (positive = shrink).
    Returns new list of (u, v) or None if degenerate.
    Works correctly for rectangles, hexagons and any convex N-gon."""
    n = len(poly)
    if n < 3 or amount <= 0:
        return list(poly) if n >= 3 else None

    normals = []
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            normals.append((0.0, 0.0))
            continue
        normals.append((-dy / length, dx / length))

    result = []
    for i in range(n):
        prev = (i - 1) % n

        p1x = poly[prev][0] + normals[prev][0] * amount
        p1y = poly[prev][1] + normals[prev][1] * amount
        d1x = poly[i][0] - poly[prev][0]
        d1y = poly[i][1] - poly[prev][1]

        p2x = poly[i][0] + normals[i][0] * amount
        p2y = poly[i][1] + normals[i][1] * amount
        d2x = poly[(i + 1) % n][0] - poly[i][0]
        d2y = poly[(i + 1) % n][1] - poly[i][1]

        det = -d1x * d2y + d1y * d2x

        if abs(det) < 1e-10:
            result.append(((p1x + p2x) * 0.5, (p1y + p2y) * 0.5))
            continue

        rhs_x = p2x - p1x
        rhs_y = p2y - p1y
        t = (-d2y * rhs_x + d2x * rhs_y) / det
        result.append((p1x + t * d1x, p1y + t * d1y))

    cx = sum(p[0] for p in result) / n
    cy = sum(p[1] for p in result) / n
    min_d = min(math.sqrt((p[0] - cx) ** 2 + (p[1] - cy) ** 2) for p in result)
    if min_d < 0.001:
        return None

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Получение границы плоского меша
# ══════════════════════════════════════════════════════════════════════════════

def _get_boundary_info(mesh):
    """
    Возвращает (normal, origin, boundary_2d, u_axis, v_axis) или None.
    boundary_2d — список (u, v) вершин контура.
    """
    if mesh.GetPolygonCount() == 0 or mesh.GetPointCount() < 3:
        return None

    p0 = mesh.GetPolygon(0)
    pa = mesh.GetPoint(p0.a)
    pb = mesh.GetPoint(p0.b)
    pc = mesh.GetPoint(p0.c)

    if p0.c == p0.d:
        normal = _v3_cross(pb - pa, pc - pa)
    else:
        pd = mesh.GetPoint(p0.d)
        normal = _v3_cross(pb - pa, pd - pa)

    n_len = _v3_len(normal)
    if n_len < 1e-9:
        return None
    normal = normal / n_len

    origin = pa
    u_axis, v_axis, n_axis = _build_frame(normal)

    n_pts = mesh.GetPointCount()
    pts_2d = []
    for i in range(n_pts):
        pt = mesh.GetPoint(i)
        d = pt - origin
        pts_2d.append((_v3_dot(d, u_axis), _v3_dot(d, v_axis)))

    boundary = _find_boundary_loop(mesh)
    if boundary is None:
        boundary = list(range(n_pts))

    boundary_2d = [pts_2d[i] for i in boundary]

    is_ccw = _poly_area_2d(boundary_2d) > 0
    if not is_ccw:
        boundary_2d.reverse()

    return normal, origin, boundary_2d, u_axis, v_axis


def _poly_area_2d(poly):
    """Signed area (Shoelace). Positive = CCW."""
    n = len(poly)
    area = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return area * 0.5


def _find_boundary_loop(mesh):
    """Найти граничные рёбра меша и соединить в замкнутый контур."""
    edge_count = {}
    n_polys = mesh.GetPolygonCount()

    for i in range(n_polys):
        p = mesh.GetPolygon(i)
        if p.c == p.d:
            verts = [p.a, p.b, p.c]
        else:
            verts = [p.a, p.b, p.c, p.d]
        nv = len(verts)
        for j in range(nv):
            a = verts[j]
            b = verts[(j + 1) % nv]
            key = (min(a, b), max(a, b))
            edge_count[key] = edge_count.get(key, 0) + 1

    boundary_edges = [e for e, c in edge_count.items() if c == 1]

    if not boundary_edges:
        return None

    adj = {}
    for e in boundary_edges:
        adj.setdefault(e[0], []).append(e[1])
        adj.setdefault(e[1], []).append(e[0])

    start = boundary_edges[0][0]
    loop = [start]
    visited = {start}
    cur = start

    while True:
        neighbors = adj.get(cur, [])
        nxt = None
        for nb in neighbors:
            if nb not in visited:
                nxt = nb
                break
        if nxt is None:
            for nb in neighbors:
                if nb == start and len(loop) > 2:
                    return loop
            break
        loop.append(nxt)
        visited.add(nxt)
        cur = nxt

    return loop if len(loop) >= 3 else None


# ══════════════════════════════════════════════════════════════════════════════
#  Генераторы паттернов — возвращают список 2D-полигонов (списков (u, v))
# ══════════════════════════════════════════════════════════════════════════════

def _gen_herringbone(tw, th, angle_rad, boundary_2d, seed,
                     offset_x=0.0, offset_y=0.0):
    unit = tw + th

    mu, Mu, mv, Mv = _bbox_2d(boundary_2d)
    margin = max(tw, th) * 3
    mu -= margin
    Mu += margin
    mv -= margin
    Mv += margin

    cx = (mu + Mu) * 0.5
    cy = (mv + Mv) * 0.5

    cols = int(math.ceil((Mu - mu) / unit)) + 2
    rows = int(math.ceil((Mv - mv) / unit)) + 2

    tiles_h = []
    tiles_v = []
    fills_p1 = []
    fills_p2 = []

    for row in range(-1, rows):
        for col in range(-1, cols):
            ux = mu + col * unit
            uy = mv + row * unit

            h_tile = [(ux, uy), (ux + tw, uy),
                      (ux + tw, uy + th), (ux, uy + th)]
            if abs(angle_rad) > 1e-8:
                h_tile = [_rotate_pt_2d(p[0], p[1], cx, cy, angle_rad) for p in h_tile]
            h_tile = [(p[0] + offset_x, p[1] + offset_y) for p in h_tile]
            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in h_tile):
                tiles_h.append(h_tile)

            v_tile = [(ux + tw, uy + th),
                      (ux + tw + th, uy + th),
                      (ux + tw + th, uy + th + tw),
                      (ux + tw, uy + th + tw)]
            if abs(angle_rad) > 1e-8:
                v_tile = [_rotate_pt_2d(p[0], p[1], cx, cy, angle_rad) for p in v_tile]
            v_tile = [(p[0] + offset_x, p[1] + offset_y) for p in v_tile]
            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in v_tile):
                tiles_v.append(v_tile)

            f0 = [(ux, uy + th), (ux + tw, uy + th),
                  (ux + tw, uy + th + tw), (ux, uy + th + tw)]
            if abs(angle_rad) > 1e-8:
                f0 = [_rotate_pt_2d(p[0], p[1], cx, cy, angle_rad) for p in f0]
            f0 = [(p[0] + offset_x, p[1] + offset_y) for p in f0]
            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in f0):
                fills_p1.append(f0)

            f1 = [(ux + tw, uy), (ux + tw + th, uy),
                  (ux + tw + th, uy + th), (ux + tw, uy + th)]
            if abs(angle_rad) > 1e-8:
                f1 = [_rotate_pt_2d(p[0], p[1], cx, cy, angle_rad) for p in f1]
            f1 = [(p[0] + offset_x, p[1] + offset_y) for p in f1]
            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in f1):
                fills_p2.append(f1)

    return tiles_h, tiles_v, fills_p1, fills_p2


def _gen_parquet(tw, th, angle_rad, offset, boundary_2d, seed,
                 rand_w_range=0.0, offset_x=0.0, offset_y=0.0):
    angle = angle_rad
    mu, Mu, mv, Mv = _bbox_2d(boundary_2d)
    margin = tw + th
    mu -= margin
    Mu += margin
    mv -= margin
    Mv += margin
    cx = (mu + Mu) * 0.5
    cy = (mv + Mv) * 0.5

    cols = int(math.ceil((Mu - mu) / tw)) + 2
    rows = int(math.ceil((Mv - mv) / th)) + 2

    rng_off = random.Random(seed) if seed != 0 else None
    rng_w = random.Random(seed + 31337) if seed != 0 else random.Random(1)

    tiles = []
    for row in range(rows):
        row_offset = offset
        if rng_off:
            row_offset += rng_off.uniform(-offset, offset)
        x_shift = (row % 2) * tw * row_offset

        x_cursor = mu + x_shift
        for col in range(-1, cols):
            cur_tw = tw
            if rng_w:
                cur_tw = tw * (1.0 + rng_w.uniform(-rand_w_range, rand_w_range))

            x0 = x_cursor
            y0 = mv + row * th
            tile = [(x0, y0), (x0 + cur_tw, y0),
                     (x0 + cur_tw, y0 + th), (x0, y0 + th)]

            x_cursor += cur_tw

            if abs(angle) > 1e-8:
                tile = [_rotate_pt_2d(p[0], p[1], cx, cy, angle) for p in tile]
            tile = [(p[0] + offset_x, p[1] + offset_y) for p in tile]

            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in tile):
                tiles.append(tile)

    return tiles


def _gen_honeycomb(size, angle_rad, boundary_2d, seed,
                   offset_x=0.0, offset_y=0.0):
    angle = angle_rad
    mu, Mu, mv, Mv = _bbox_2d(boundary_2d)
    margin = size * 3
    mu -= margin
    Mu += margin
    mv -= margin
    Mv += margin
    cx = (mu + Mu) * 0.5
    cy = (mv + Mv) * 0.5

    h_space = 1.5 * size
    v_space = math.sqrt(3.0) * size
    cols = int(math.ceil((Mu - mu) / h_space)) + 1
    rows = int(math.ceil((Mv - mv) / v_space)) + 1

    tiles = []
    for col in range(cols):
        for row in range(rows):
            hx = mu + col * h_space
            hy = mv + row * v_space
            if col % 2 == 1:
                hy += v_space * 0.5

            hex_pts = []
            for i in range(6):
                a = math.radians(60 * i)
                px = hx + size * math.cos(a)
                py = hy + size * math.sin(a)
                if abs(angle) > 1e-8:
                    px, py = _rotate_pt_2d(px, py, cx, cy, angle)
                hex_pts.append((px + offset_x, py + offset_y))

            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in hex_pts):
                tiles.append(hex_pts)

    return tiles


def _gen_herringbone_v2(tw, th, angle_rad, boundary_2d, seed,
                        offset_x=0.0, offset_y=0.0):
    n = int(round(tw / th))
    if n < 1:
        n = 1

    period = 2 * n
    cell = th

    mu, Mu, mv, Mv = _bbox_2d(boundary_2d)
    margin = max(tw, th) * 3
    mu -= margin
    Mu += margin
    mv -= margin
    Mv += margin

    cx = (mu + Mu) * 0.5
    cy = (mv + Mv) * 0.5

    min_row = int(math.floor(mv / cell)) - period
    max_row = int(math.ceil(Mv / cell)) + period
    min_col = int(math.floor(mu / cell)) - period
    max_col = int(math.ceil(Mu / cell)) + period

    tiles_h = []
    tiles_v = []

    for r in range(min_row, max_row + 1):
        anchor_c = r % period
        if anchor_c < 0:
            anchor_c += period

        k_min = int(math.floor((min_col - anchor_c) / period)) - 1
        k_max = int(math.ceil((max_col - anchor_c) / period)) + 1

        for k in range(k_min, k_max + 1):
            x0 = (anchor_c + k * period) * cell
            y0 = r * cell
            tile = [(x0, y0), (x0 + tw, y0), (x0 + tw, y0 + th), (x0, y0 + th)]

            if abs(angle_rad) > 1e-8:
                tile = [_rotate_pt_2d(p[0], p[1], cx, cy, angle_rad) for p in tile]
            tile = [(p[0] + offset_x, p[1] + offset_y) for p in tile]

            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in tile):
                tiles_h.append(tile)

    for c in range(min_col, max_col + 1):
        base_anchor = (c + 1) % period
        if base_anchor < 0:
            base_anchor += period

        k_min = int(math.floor((min_row - base_anchor) / period)) - 1
        k_max = int(math.ceil((max_row - base_anchor) / period)) + 1

        for k in range(k_min, k_max + 1):
            r = base_anchor + k * period
            x0 = c * cell
            y0 = r * cell
            tile = [(x0, y0), (x0 + th, y0), (x0 + th, y0 + tw), (x0, y0 + tw)]

            if abs(angle_rad) > 1e-8:
                tile = [_rotate_pt_2d(p[0], p[1], cx, cy, angle_rad) for p in tile]
            tile = [(p[0] + offset_x, p[1] + offset_y) for p in tile]

            if any(_point_in_polygon(p[0], p[1], boundary_2d) for p in tile):
                tiles_v.append(tile)

    return tiles_h, tiles_v


# ══════════════════════════════════════════════════════════════════════════════
#  Строитель 3D-геометрии одной плитки
# ══════════════════════════════════════════════════════════════════════════════

def _build_tile_3d(tile_2d, thickness, bevel_size, seam_on, seam_w,
                   origin, u_axis, v_axis, normal):
    """
    Строит 3D-геометрию одной плитки.
    Возвращает (verts, top_polys, side_polys, tile_center_3d).
    verts      — список c4d.Vector
    top_polys  — список кортежей индексов (верхняя грань)
    side_polys — список кортежей индексов (боковые + фаска)
    """
    n = len(tile_2d)
    if n < 3:
        return [], [], [], None

    bevel = max(0.0, bevel_size)
    t = max(0.001, thickness)

    cx_2d = sum(p[0] for p in tile_2d) / n
    cy_2d = sum(p[1] for p in tile_2d) / n
    center_3d = _to_3d(cx_2d, cy_2d, origin, u_axis, v_axis, normal)

    if seam_on and seam_w > 1e-6:
        inset_pts = _inset_polygon(tile_2d, seam_w * 0.5)
        if inset_pts is None:
            return [], [], [], None
    else:
        inset_pts = list(tile_2d)

    if bevel > 1e-6:
        top_pts = _inset_polygon(inset_pts, bevel)
        if top_pts is None:
            top_pts = list(inset_pts)
    else:
        top_pts = list(inset_pts)

    verts = []
    top_polys = []
    side_polys = []

    idx_bottom = []
    idx_bevel = []
    idx_top = []

    for i in range(n):
        idx_bottom.append(len(verts))
        verts.append(_to_3d(inset_pts[i][0], inset_pts[i][1],
                            origin, u_axis, v_axis, normal, 0.0))

    for i in range(n):
        idx_bevel.append(len(verts))
        verts.append(_to_3d(inset_pts[i][0], inset_pts[i][1],
                            origin, u_axis, v_axis, normal, t - bevel))

    for i in range(n):
        idx_top.append(len(verts))
        verts.append(_to_3d(top_pts[i][0], top_pts[i][1],
                            origin, u_axis, v_axis, normal, t))

    if n == 4:
        top_polys.append(tuple(idx_top))
    else:
        for i in range(1, n - 1):
            top_polys.append((idx_top[0], idx_top[i], idx_top[i + 1], idx_top[i + 1]))

    for i in range(n):
        j = (i + 1) % n
        side_polys.append((idx_bottom[i], idx_bottom[j], idx_bevel[j], idx_bevel[i]))

    for i in range(n):
        j = (i + 1) % n
        side_polys.append((idx_bevel[i], idx_bevel[j], idx_top[j], idx_top[i]))

    if n == 4:
        bot_order = list(reversed(idx_bottom))
        side_polys.append(tuple(bot_order))
    else:
        for i in range(1, n - 1):
            side_polys.append((idx_bottom[0], idx_bottom[i + 1], idx_bottom[i], idx_bottom[i]))

    return verts, top_polys, side_polys, center_3d


# ══════════════════════════════════════════════════════════════════════════════
#  UV-карты
# ══════════════════════════════════════════════════════════════════════════════

def _compute_tile_uvs(tile_2d, uv_sx, uv_sy, uv_rot_rad,
                      random_rot, random_range_rad, tile_seed,
                      random_off, off_range_x, off_range_y, uv_rand_seed):
    """UV для одного полигона верхней грани.
    Локальные координаты плитки нормализуются к размеру текстуры
    (uv_sx, uv_sy), так что текстура тайлится корректно на каждой плитке."""
    n = len(tile_2d)
    total_rot = uv_rot_rad

    rng_rot = random.Random(tile_seed)
    if random_rot:
        r_angle = rng_rot.uniform(-random_range_rad, random_range_rad)
        total_rot = uv_rot_rad + r_angle

    off_u = 0.0
    off_v = 0.0
    if random_off:
        rng_off = random.Random(uv_rand_seed + tile_seed)
        off_u = rng_off.uniform(-off_range_x, off_range_x)
        off_v = rng_off.uniform(-off_range_y, off_range_y)

    us = [p[0] for p in tile_2d]
    vs = [p[1] for p in tile_2d]
    min_u = min(us)
    min_v = min(vs)

    uvs = []
    for px, py in tile_2d:
        u = (px - min_u) / uv_sx if abs(uv_sx) > 1e-9 else 0.0
        v = (py - min_v) / uv_sy if abs(uv_sy) > 1e-9 else 0.0
        if abs(total_rot) > 1e-8:
            cos_r = math.cos(total_rot)
            sin_r = math.sin(total_rot)
            ru = u * cos_r - v * sin_r
            rv = u * sin_r + v * cos_r
            u, v = ru, rv
        u += off_u / uv_sx if abs(uv_sx) > 1e-9 else 0.0
        v += off_v / uv_sy if abs(uv_sy) > 1e-9 else 0.0
        uvs.append(c4d.Vector(u, v, 0.0))

    return uvs


# ══════════════════════════════════════════════════════════════════════════════
#  Теги выделения
# ══════════════════════════════════════════════════════════════════════════════

def _apply_selection(obj, name, poly_indices):
    tag = obj.MakeTag(c4d.Tpolygonselection)
    if tag is None:
        return
    tag.SetName(name)
    sel = tag.GetBaseSelect()
    for pi in poly_indices:
        sel.Select(pi)


# ══════════════════════════════════════════════════════════════════════════════
#  Главная функция сборки
# ══════════════════════════════════════════════════════════════════════════════

def _build_floor(op):
    child = op.GetDown()
    if child is None:
        return None

    src = child.GetDeformCache()
    if src is None:
        src = child.GetCache()
    if src is None:
        src = child

    if not src.CheckType(c4d.Opolygon):
        try:
            import c4d.utils as utils
            res = utils.SendModelingCommand(
                command=c4d.MCOMMAND_CURRENTSTATETOOBJECT,
                list=[src.Clone()],
                mode=c4d.MODELINGCOMMANDMODE_ALL,
                doc=op.GetDocument()
            )
            if not res or not res[0].CheckType(c4d.Opolygon):
                return None
            src = res[0]
        except Exception:
            return None

    if src.GetPointCount() < 3 or src.GetPolygonCount() == 0:
        return None

    info = _get_boundary_info(src)
    if info is None:
        print("[FloorGenerator] Не удалось определить границу плоскости.")
        return None

    normal, origin, boundary_2d, u_axis, v_axis = info

    pattern    = int(_ud_get(op, FG_PATTERN,   DEF_PATTERN))
    tile_w     = max(1.0, float(_ud_get(op, FG_TILE_W,    DEF_TILE_W)))
    tile_h     = max(1.0, float(_ud_get(op, FG_TILE_H,    DEF_TILE_H)))
    pat_x      = float(_ud_get(op, FG_PAT_X,  DEF_PAT_X))
    pat_y      = float(_ud_get(op, FG_PAT_Y,  DEF_PAT_Y))
    angle      = float(_ud_get(op, FG_ANGLE,  DEF_ANGLE))
    offset     = float(_ud_get(op, FG_OFFSET, DEF_OFFSET))
    seed       = int(_ud_get(op, FG_SEED,     DEF_SEED))
    thickness  = max(0.001, float(_ud_get(op, FG_THICKNESS, DEF_THICKNESS)))
    bevel      = max(0.0, float(_ud_get(op, FG_BEVEL, DEF_BEVEL)))
    seam_on    = bool(_ud_get(op, FG_SEAM_ON, DEF_SEAM_ON))
    seam_w     = max(0.0, float(_ud_get(op, FG_SEAM_W, DEF_SEAM_W)))

    uv_sx      = max(0.1, float(_ud_get(op, FG_UV_SX, DEF_UV_SX)))
    uv_sy      = max(0.1, float(_ud_get(op, FG_UV_SY, DEF_UV_SY)))
    uv_rot     = float(_ud_get(op, FG_UV_ROT, DEF_UV_ROT))
    uv_rand    = bool(_ud_get(op, FG_UV_RAND, DEF_UV_RAND))
    uv_rand_r  = float(_ud_get(op, FG_UV_RANDR, DEF_UV_RANDR))
    uv_rand_off    = bool(_ud_get(op, FG_UV_RANDOFF, DEF_UV_RANDOFF))
    uv_rand_off_x  = float(_ud_get(op, FG_UV_RANDOFF_X, DEF_UV_RANDOFF_X))
    uv_rand_off_y  = float(_ud_get(op, FG_UV_RANDOFF_Y, DEF_UV_RANDOFF_Y))
    uv_rand_seed   = int(_ud_get(op, FG_UV_RAND_SEED, DEF_UV_RAND_SEED))
    parq_rand_w    = float(_ud_get(op, FG_PARQ_RAND_W, DEF_PARQ_RAND_W)) / 100.0

    fills_p1_2d = []
    fills_p2_2d = []

    if pattern == PAT_HERRINGBONE_V2:
        n = max(1, int(round(tile_w / tile_h)))
        tile_w = tile_h * n

    if pattern == PAT_HERRINGBONE:
        tiles_h_2d, tiles_v_2d, fills_p1_2d, fills_p2_2d = _gen_herringbone(
            tile_w, tile_h, angle, boundary_2d, seed, pat_x, pat_y)
        tiles_2d = tiles_h_2d + tiles_v_2d
        h_count = len(tiles_h_2d)
    elif pattern == PAT_PARQUET:
        tiles_2d = _gen_parquet(tile_w, tile_h, angle, offset, boundary_2d, seed,
                                parq_rand_w, pat_x, pat_y)
        h_count = 0
    elif pattern == PAT_HONEYCOMB:
        tiles_2d = _gen_honeycomb(tile_w, angle, boundary_2d, seed, pat_x, pat_y)
        h_count = 0
    elif pattern == PAT_HERRINGBONE_V2:
        tiles_h_2d, tiles_v_2d = _gen_herringbone_v2(
            tile_w, tile_h, angle, boundary_2d, seed, pat_x, pat_y)
        tiles_2d = tiles_h_2d + tiles_v_2d
        h_count = len(tiles_h_2d)
    else:
        tiles_h_2d, tiles_v_2d, fills_p1_2d, fills_p2_2d = _gen_herringbone(
            tile_w, tile_h, angle, boundary_2d, seed, pat_x, pat_y)
        tiles_2d = tiles_h_2d + tiles_v_2d
        h_count = len(tiles_h_2d)

    if not tiles_2d:
        return None

    all_verts = []
    all_polys = []
    top_indices = []
    side_indices = []
    h_top_indices = []
    v_top_indices = []
    uv_list = []

    for ti, tile in enumerate(tiles_2d):
        v, tp, sp, _ = _build_tile_3d(
            tile, thickness, bevel, seam_on, seam_w,
            origin, u_axis, v_axis, normal)

        if not v:
            continue

        base_v = len(all_verts)
        all_verts.extend(v)

        base_p = len(all_polys)

        for p in tp:
            shifted = tuple(idx + base_v for idx in p)
            all_polys.append(shifted)
            idx = len(all_polys) - 1
            top_indices.append(idx)
            if h_count > 0:
                if ti < h_count:
                    h_top_indices.append(idx)
                else:
                    v_top_indices.append(idx)

        for p in sp:
            shifted = tuple(idx + base_v for idx in p)
            all_polys.append(shifted)
            side_indices.append(len(all_polys) - 1)

        is_v = h_count > 0 and ti >= h_count
        cur_uv_sx = uv_sy if is_v else uv_sx
        cur_uv_sy = uv_sx if is_v else uv_sy
        uvs = _compute_tile_uvs(
            tile, cur_uv_sx, cur_uv_sy,
            uv_rot + (math.pi * 0.5 if is_v else 0.0),
            uv_rand, uv_rand_r, seed + ti * 7919,
            uv_rand_off, uv_rand_off_x, uv_rand_off_y, uv_rand_seed)
        uv_list.append((base_p, base_v, tp, uvs, len(tile)))

    fills_p1_indices = []
    fills_p2_indices = []
    if pattern == PAT_HERRINGBONE:
        for fi, fill in enumerate(fills_p1_2d):
            v, tp, sp, _ = _build_tile_3d(
                fill, thickness, bevel, seam_on, seam_w,
                origin, u_axis, v_axis, normal)
            if not v:
                continue
            base_v = len(all_verts)
            all_verts.extend(v)
            base_p = len(all_polys)
            for p in tp:
                shifted = tuple(idx + base_v for idx in p)
                all_polys.append(shifted)
                fills_p1_indices.append(len(all_polys) - 1)
            for p in sp:
                shifted = tuple(idx + base_v for idx in p)
                all_polys.append(shifted)
                side_indices.append(len(all_polys) - 1)
            uvs = _compute_tile_uvs(
                fill, uv_sx, uv_sy, uv_rot, uv_rand, uv_rand_r,
                seed + fi * 7919 + 50000,
                uv_rand_off, uv_rand_off_x, uv_rand_off_y, uv_rand_seed)
            uv_list.append((base_p, base_v, tp, uvs, len(fill)))

        for fi, fill in enumerate(fills_p2_2d):
            v, tp, sp, _ = _build_tile_3d(
                fill, thickness, bevel, seam_on, seam_w,
                origin, u_axis, v_axis, normal)
            if not v:
                continue
            base_v = len(all_verts)
            all_verts.extend(v)
            base_p = len(all_polys)
            for p in tp:
                shifted = tuple(idx + base_v for idx in p)
                all_polys.append(shifted)
                fills_p2_indices.append(len(all_polys) - 1)
            for p in sp:
                shifted = tuple(idx + base_v for idx in p)
                all_polys.append(shifted)
                side_indices.append(len(all_polys) - 1)
            uvs = _compute_tile_uvs(
                fill, uv_sx, uv_sy, uv_rot, uv_rand, uv_rand_r,
                seed + fi * 7919 + 100000,
                uv_rand_off, uv_rand_off_x, uv_rand_off_y, uv_rand_seed)
            uv_list.append((base_p, base_v, tp, uvs, len(fill)))

    if not all_verts:
        return None

    child_matrix = child.GetMl()
    for i in range(len(all_verts)):
        all_verts[i] = child_matrix * all_verts[i]

    obj = c4d.PolygonObject(len(all_verts), len(all_polys))
    obj.SetName("Floor")

    for i, v in enumerate(all_verts):
        obj.SetPoint(i, v)

    for i, p in enumerate(all_polys):
        if len(p) == 4:
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[3]))
        elif len(p) == 3:
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[2]))
        else:
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[2]))

    obj.Message(c4d.MSG_UPDATE)

    if top_indices:
        _apply_selection(obj, "P", top_indices)
    if side_indices:
        _apply_selection(obj, "S", side_indices)
    if fills_p1_indices:
        _apply_selection(obj, "P1", fills_p1_indices)
    if fills_p2_indices:
        _apply_selection(obj, "P2", fills_p2_indices)

    uvw = c4d.UVWTag(len(all_polys))
    for base_p, base_v, tp, uvs, n_tile in uv_list:
        top_off = 2 * n_tile
        for pi_offset in range(len(tp)):
            pi = base_p + pi_offset
            if pi >= len(all_polys):
                continue
            p_idx = all_polys[pi]
            n_v = len(p_idx)

            li0 = p_idx[0] - base_v - top_off
            li1 = p_idx[1] - base_v - top_off
            li2 = p_idx[2] - base_v - top_off

            uv_a = uvs[li0] if 0 <= li0 < len(uvs) else c4d.Vector()
            uv_b = uvs[li1] if 0 <= li1 < len(uvs) else c4d.Vector()
            uv_c = uvs[li2] if 0 <= li2 < len(uvs) else c4d.Vector()

            if n_v == 4:
                li3 = p_idx[3] - base_v - top_off
                uv_d = uvs[li3] if 0 <= li3 < len(uvs) else c4d.Vector()
            else:
                uv_d = uv_c

            uvw.SetSlow(pi, uv_a, uv_b, uv_c, uv_d)

    obj.InsertTag(uvw)

    return obj


# ══════════════════════════════════════════════════════════════════════════════
#  UserData: создание интерфейса
# ══════════════════════════════════════════════════════════════════════════════

def _create_userdata(op):
    g1 = _add_group(op, "Паттерн")
    _add_in_group(op, g1, _cycle_bc("Тип", DEF_PATTERN, PAT_NAMES))
    _add_in_group(op, g1, _float_bc("Ширина плитки", DEF_TILE_W, 1.0, 10000.0))
    _add_in_group(op, g1, _float_bc("Длина плитки", DEF_TILE_H, 1.0, 10000.0))
    _add_in_group(op, g1, _float_bc("Смещение X", DEF_PAT_X,
                  -10000.0, 10000.0, c4d.DESC_UNIT_METER, 1.0))
    _add_in_group(op, g1, _float_bc("Смещение Y", DEF_PAT_Y,
                  -10000.0, 10000.0, c4d.DESC_UNIT_METER, 1.0))
    _add_in_group(op, g1, _float_bc("Угол поворота", DEF_ANGLE,
                  -180.0, 180.0, c4d.DESC_UNIT_DEGREE, math.radians(1.0)))
    _add_in_group(op, g1, _float_bc("Смещение рядов", DEF_OFFSET,
                  0.0, 1.0, c4d.DESC_UNIT_PERCENT, 0.01))
    _add_in_group(op, g1, _int_bc("Зерно", DEF_SEED, 0, 99999))
    _add_in_group(op, g1, _float_bc("Разброс ширины", DEF_PARQ_RAND_W,
                  0.0, 100.0, c4d.DESC_UNIT_REAL, 1.0))

    g2 = _add_group(op, "Толщина и фаска")
    _add_in_group(op, g2, _float_bc("Толщина", DEF_THICKNESS, 0.001, 1000.0))
    _add_in_group(op, g2, _float_bc("Фаска", DEF_BEVEL, 0.0, 100.0))

    g3 = _add_group(op, "Швы")
    _add_in_group(op, g3, _bool_bc("Швы включены", DEF_SEAM_ON))
    _add_in_group(op, g3, _float_bc("Ширина шва", DEF_SEAM_W, 0.0, 50.0))

    g4 = _add_group(op, "UV")
    _add_in_group(op, g4, _float_bc("Ширина UV", DEF_UV_SX, 0.1, 10000.0))
    _add_in_group(op, g4, _float_bc("Длина UV", DEF_UV_SY, 0.1, 10000.0))
    _add_in_group(op, g4, _float_bc("Угол UV", DEF_UV_ROT,
                  -180.0, 180.0, c4d.DESC_UNIT_DEGREE, math.radians(1.0)))
    _add_in_group(op, g4, _bool_bc("Рандом угла UV", DEF_UV_RAND))
    _add_in_group(op, g4, _float_bc("Диапазон рандома", DEF_UV_RANDR,
                  0.0, 180.0, c4d.DESC_UNIT_DEGREE, math.radians(1.0)))
    _add_in_group(op, g4, _bool_bc("Рандом смещения UV", DEF_UV_RANDOFF))
    _add_in_group(op, g4, _float_bc("Смещение X", DEF_UV_RANDOFF_X,
                  0.0, 10000.0, c4d.DESC_UNIT_METER, 1.0))
    _add_in_group(op, g4, _float_bc("Смещение Y", DEF_UV_RANDOFF_Y,
                  0.0, 10000.0, c4d.DESC_UNIT_METER, 1.0))
    _add_in_group(op, g4, _int_bc("Сид смещения", DEF_UV_RAND_SEED, 0, 99999))


def _set_defaults(op):
    _ud_set(op, FG_PATTERN,   DEF_PATTERN)
    _ud_set(op, FG_TILE_W,    DEF_TILE_W)
    _ud_set(op, FG_TILE_H,    DEF_TILE_H)
    _ud_set(op, FG_PAT_X,     DEF_PAT_X)
    _ud_set(op, FG_PAT_Y,     DEF_PAT_Y)
    _ud_set(op, FG_ANGLE,     DEF_ANGLE)
    _ud_set(op, FG_OFFSET,    DEF_OFFSET)
    _ud_set(op, FG_SEED,      DEF_SEED)
    _ud_set(op, FG_PARQ_RAND_W, DEF_PARQ_RAND_W)
    _ud_set(op, FG_THICKNESS, DEF_THICKNESS)
    _ud_set(op, FG_BEVEL,     DEF_BEVEL)
    _ud_set(op, FG_SEAM_ON,   DEF_SEAM_ON)
    _ud_set(op, FG_SEAM_W,    DEF_SEAM_W)
    _ud_set(op, FG_UV_SX,     DEF_UV_SX)
    _ud_set(op, FG_UV_SY,     DEF_UV_SY)
    _ud_set(op, FG_UV_ROT,    DEF_UV_ROT)
    _ud_set(op, FG_UV_RAND,   DEF_UV_RAND)
    _ud_set(op, FG_UV_RANDR,  DEF_UV_RANDR)
    _ud_set(op, FG_UV_RANDOFF,    DEF_UV_RANDOFF)
    _ud_set(op, FG_UV_RANDOFF_X,  DEF_UV_RANDOFF_X)
    _ud_set(op, FG_UV_RANDOFF_Y,  DEF_UV_RANDOFF_Y)
    _ud_set(op, FG_UV_RAND_SEED,  DEF_UV_RAND_SEED)


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin class
# ══════════════════════════════════════════════════════════════════════════════

class FloorGeneratorObject(c4d.plugins.ObjectData):

    def _ensure_ud(self, op):
        if not _ud_exists(op, FG_FIRST_PARAM):
            _create_userdata(op)
            _set_defaults(op)

    def Init(self, op, isload=False):
        if not isload:
            op.SetName("Floor Generator")
        self._ensure_ud(op)
        return True

    def GetVirtualObjects(self, op, hh):
        self._ensure_ud(op)
        try:
            result = _build_floor(op)
        except Exception as e:
            print("[FloorGenerator] Ошибка: {}".format(e))
            import traceback
            traceback.print_exc()
            return None
        return result

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription(op.GetType()):
            return False, flags
        self._ensure_ud(op)
        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  Иконка
# ══════════════════════════════════════════════════════════════════════════════

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA6ElEQVR4nO2VvRHCMAyFJS6juEjlMaiYgIohGCNDUDFBKsZwReFdRAEJIbFsy2ccc+ErkyfpWf4RwNbB+QfqWgIAwPMdwVjiAul2eCbY91GFnHqtsGEjjCXQamFw5GUUtHoblehZrbHkW3kWfdrPDIUd+uZD4GuhpJhAj0nJpQT3PYTLoM+0VD+FupaGq+hLttAl6ndRrlajQOsr7kChg1dpBwpeu8qn4ZT5K+Z6A2L0/2m4WnGGctPwZ2CnXKIupK/0JdwS4tN5OVJw309XjM47CmMS52Qwyc+CQKAPyWJQGpATyVZ9jQfmCuimY/PsggAAAABJRU5ErkJggg=="
)


def _make_icon():
    """Декодирует встроенный base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(_ICON_B64.replace(" ", ""))
        fd, tmp = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, data)
            os.close(fd)
            bmp.InitWith(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return None
    return bmp


# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_FLOORGEN,
        str         = NAME_FLOORGEN,
        g           = FloorGeneratorObject,
        description = "",
        icon        = _make_icon(),
        info        = c4d.OBJECT_GENERATOR,
    )
    print("Floor Generator: плагин зарегистрирован (ID={})".format(ID_FLOORGEN))
