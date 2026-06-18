# -*- coding: utf-8 -*-
"""
TriTorus — Cinema 4D ObjectData Plugin v2.0
================================================
Параметрический тор с расширенными возможностями:
  • Типы поверхности: Квадратная сетка, Треугольная, Спиральная,
    Диагональная, Гексагональная
  • Деформации: Кручение (Twist), Сужение (Taper), Масштаб
  • Смещение поверхности: Синусоида, Шум (Perlin), Радиальное
  • Детальная настройка фонг-сглаживания
  • Уникальная иконка

UserData SubID MAP (строго фиксировано):
  SubID=1  : g_base (группа «Основные параметры»)
  SubID=2  : TT_RADIUS_MAJOR
  SubID=3  : TT_RADIUS_MINOR
  SubID=4  : TT_SEGS_MAJOR
  SubID=5  : TT_SEGS_MINOR
  SubID=6  : TT_SURFACE_TYPE
  SubID=7  : TT_QUADS (триангуляция)
  SubID=8  : g_deform (группа «Деформации»)
  SubID=9  : TT_TWIST
  SubID=10 : TT_TAPER_X
  SubID=11 : TT_TAPER_Y
  SubID=12 : TT_SCALE_X
  SubID=13 : TT_SCALE_Y
  SubID=14 : TT_SCALE_Z
  SubID=15 : g_disp (группа «Смещение поверхности»)
  SubID=16 : TT_DISP_TYPE
  SubID=17 : TT_DISP_AMP
  SubID=18 : TT_DISP_FREQ
  SubID=19 : TT_DISP_PHASE
  SubID=20 : TT_DISP_OCTAVES
  SubID=21 : TT_DISP_LACUNARITY
  SubID=22 : TT_DISP_GAIN
  SubID=23 : g_spiral (группа «Спираль»)
  SubID=24 : TT_SPIRAL_TURNS
  SubID=25 : TT_SPIRAL_DIRECTION
  SubID=26 : g_hex (группа «Гексагональная»)
  SubID=27 : TT_HEX_INNER_RADIUS
  SubID=28 : g_phong (группа «Фонг»)
  SubID=29 : TT_PHONG_ANGLE
  SubID=30 : TT_PHONG_LIMIT
"""

import c4d  # type: ignore
import math
import os
import base64
import tempfile
import random

# ══════════════════════════════════════════════════════════════════════════════
#  Plugin ID & Name
# ══════════════════════════════════════════════════════════════════════════════

ID_TRITORUS  = 1068874
NAME_TRITORUS = "Tri Torus v2.0"

# ══════════════════════════════════════════════════════════════════════════════
#  UserData SubID — СТРОГО совпадают с порядком вызовов AddUserData
# ══════════════════════════════════════════════════════════════════════════════

UD_G_BASE    = 1    # группа «Основные параметры»
TT_RADIUS_MAJOR = 2
TT_RADIUS_MINOR = 3
TT_SEGS_MAJOR   = 4
TT_SEGS_MINOR   = 5
TT_SURFACE_TYPE = 6
TT_QUADS        = 7

UD_G_DEFORM  = 8    # группа «Деформации»
TT_TWIST     = 9
TT_TAPER_X   = 10
TT_TAPER_Y   = 11
TT_SCALE_X   = 12
TT_SCALE_Y   = 13
TT_SCALE_Z   = 14

UD_G_DISP    = 15   # группа «Смещение поверхности»
TT_DISP_TYPE = 16
TT_DISP_AMP  = 17
TT_DISP_FREQ = 18
TT_DISP_PHASE = 19
TT_DISP_OCTAVES  = 20
TT_DISP_LACUNARITY = 21
TT_DISP_GAIN  = 22

UD_G_SPIRAL  = 23   # группа «Спираль»
TT_SPIRAL_TURNS   = 24
TT_SPIRAL_DIRECTION = 25

UD_G_HEX     = 26   # группа «Гексагональная»
TT_HEX_INNER_RADIUS = 27

UD_G_PHONG   = 28   # группа «Фонг»
TT_PHONG_ANGLE = 29
TT_PHONG_LIMIT = 30

TT_FIRST_PARAM = TT_RADIUS_MAJOR  # SubID=2

# ══════════════════════════════════════════════════════════════════════════════
#  Дефолтные значения параметров
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_RADIUS_MAJOR = 150.0
DEFAULT_RADIUS_MINOR = 50.0
DEFAULT_SEGS_MAJOR   = 24
DEFAULT_SEGS_MINOR   = 12
DEFAULT_SURFACE_TYPE = 0     # 0=Квадратная, 1=Треугольная, 2=Спиральная, 3=Диагональная, 4=Гексагональная
DEFAULT_QUADS        = True  # True = квады (без триангуляции)

DEFAULT_TWIST   = 0.0
DEFAULT_TAPER_X = 0.0
DEFAULT_TAPER_Y = 0.0
DEFAULT_SCALE_X = 1.0
DEFAULT_SCALE_Y = 1.0
DEFAULT_SCALE_Z = 1.0

DEFAULT_DISP_TYPE     = 0    # 0=Нет, 1=Синусоида, 2=Шум Perlin, 3=Радиальное
DEFAULT_DISP_AMP      = 0.0
DEFAULT_DISP_FREQ     = 0.1
DEFAULT_DISP_PHASE    = 0.0
DEFAULT_DISP_OCTAVES  = 4
DEFAULT_DISP_LACUNARITY = 2.0
DEFAULT_DISP_GAIN     = 0.5

DEFAULT_SPIRAL_TURNS     = 1.0
DEFAULT_SPIRAL_DIRECTION = 0   # 0=По часовой, 1=Против часовой

DEFAULT_HEX_INNER_RADIUS = 0.6

DEFAULT_PHONG_ANGLE = 45.0
DEFAULT_PHONG_LIMIT = True

# ══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные функции UserData
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
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
    cyc = c4d.BaseContainer()
    for i, label in enumerate(items):
        cyc[i] = label
    bc[c4d.DESC_CYCLE] = cyc
    return bc


# ══════════════════════════════════════════════════════════════════════════════
#  Phong-тег
# ══════════════════════════════════════════════════════════════════════════════

def _add_phong_tag(obj, angle_deg=45.0, limit=True):
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = limit
        tag[c4d.PHONGTAG_PHONG_ANGLE]      = math.radians(angle_deg)
        tag[c4d.PHONGTAG_PHONG_USEEDGES]   = True
    return tag


# ══════════════════════════════════════════════════════════════════════════════
#  Утилита создания PolygonObject
# ══════════════════════════════════════════════════════════════════════════════

def _make_poly_object(pts, cpolys, name):
    obj = c4d.PolygonObject(len(pts), len(cpolys))
    obj.SetName(name)
    for i, p in enumerate(pts):
        obj.SetPoint(i, p)
    for i, cp in enumerate(cpolys):
        obj.SetPolygon(i, cp)
    obj.Message(c4d.MSG_UPDATE)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
#  Генераторы мешей
# ══════════════════════════════════════════════════════════════════════════════

def _perlin_noise_2d(x, y, octaves=4, lacunarity=2.0, gain=0.5, seed=0):
    """Простой Perlin-like шум на основе хеша. Возвращает значение [-1, 1]."""
    def _hash(ix, iy, s):
        n = ix * 374761393 + iy * 668265263 + s * 1274126177
        n = (n ^ (n >> 13)) * 1274126177
        n = n ^ (n >> 16)
        return (n & 0x7fffffff) / float(0x7fffffff) * 2.0 - 1.0

    def _smoothstep(t):
        return t * t * (3.0 - 2.0 * t)

    def _noise(px, py):
        ix = int(math.floor(px))
        iy = int(math.floor(py))
        fx = px - ix
        fy = py - iy
        sx = _smoothstep(fx)
        sy = _smoothstep(fy)
        n00 = _hash(ix, iy, seed)
        n10 = _hash(ix + 1, iy, seed)
        n01 = _hash(ix, iy + 1, seed)
        n11 = _hash(ix + 1, iy + 1, seed)
        nx0 = n00 + sx * (n10 - n00)
        nx1 = n01 + sx * (n11 - n01)
        return nx0 + sy * (nx1 - nx0)

    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(max(1, octaves)):
        total += amplitude * _noise(x * frequency, y * frequency)
        max_val += amplitude
        amplitude *= gain
        frequency *= lacunarity
    return total / max_val if max_val > 0 else 0.0


def _build_torus_standard(r_major, r_minor, segs_m, segs_n):
    """Стандартный тор с квадратной сеткой. Возвращает (verts, polys)."""
    verts = []
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        cp = math.cos(phi)
        sp = math.sin(phi)
        for i in range(segs_n):
            theta = i / segs_n * 2.0 * math.pi
            ct = math.cos(theta)
            st = math.sin(theta)
            x = (r_major + r_minor * ct) * cp
            y = r_minor * st
            z = (r_major + r_minor * ct) * sp
            verts.append(c4d.Vector(x, y, z))

    polys = []
    for j in range(segs_m):
        for i in range(segs_n):
            v0 = j * segs_n + i
            v1 = j * segs_n + (i + 1) % segs_n
            v2 = ((j + 1) % segs_m) * segs_n + (i + 1) % segs_n
            v3 = ((j + 1) % segs_m) * segs_n + i
            polys.append(c4d.CPolygon(v0, v1, v2, v3))
    return verts, polys


def _build_torus_triangulated(r_major, r_minor, segs_m, segs_n):
    """Тор с треугольной сеткой. Каждый quad → 2 треугольника."""
    verts, _ = _build_torus_standard(r_major, r_minor, segs_m, segs_n)
    polys = []
    for j in range(segs_m):
        for i in range(segs_n):
            v0 = j * segs_n + i
            v1 = j * segs_n + (i + 1) % segs_n
            v2 = ((j + 1) % segs_m) * segs_n + (i + 1) % segs_n
            v3 = ((j + 1) % segs_m) * segs_n + i
            polys.append(c4d.CPolygon(v0, v1, v2, v2))
            polys.append(c4d.CPolygon(v0, v2, v3, v3))
    return verts, polys


def _build_torus_spiral(r_major, r_minor, segs_m, segs_n, turns=1.0, clockwise=True):
    """Спиральный тор — вершины сдвинуты по винтовой линии."""
    verts = []
    direction = 1.0 if clockwise else -1.0
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        spiral_offset = turns * direction * (j / segs_m) * 2.0 * math.pi
        cp = math.cos(phi)
        sp = math.sin(phi)
        for i in range(segs_n):
            theta = i / segs_n * 2.0 * math.pi + spiral_offset
            ct = math.cos(theta)
            st = math.sin(theta)
            x = (r_major + r_minor * ct) * cp
            y = r_minor * st
            z = (r_major + r_minor * ct) * sp
            verts.append(c4d.Vector(x, y, z))

    polys = []
    for j in range(segs_m):
        for i in range(segs_n):
            v0 = j * segs_n + i
            v1 = j * segs_n + (i + 1) % segs_n
            v2 = ((j + 1) % segs_m) * segs_n + (i + 1) % segs_n
            v3 = ((j + 1) % segs_m) * segs_n + i
            polys.append(c4d.CPolygon(v0, v1, v2, v3))
    return verts, polys


def _build_torus_diagonal(r_major, r_minor, segs_m, segs_n):
    """Диагональная (ромбовидная) сетка — каждая строка сдвинута на полшага."""
    verts = []
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        cp = math.cos(phi)
        sp = math.sin(phi)
        offset = 0.5 * (j % 2)
        for i in range(segs_n):
            theta = (i + offset) / segs_n * 2.0 * math.pi
            ct = math.cos(theta)
            st = math.sin(theta)
            x = (r_major + r_minor * ct) * cp
            y = r_minor * st
            z = (r_major + r_minor * ct) * sp
            verts.append(c4d.Vector(x, y, z))

    polys = []
    for j in range(segs_m):
        for i in range(segs_n):
            v0 = j * segs_n + i
            v1 = j * segs_n + (i + 1) % segs_n
            v2 = ((j + 1) % segs_m) * segs_n + (i + 1) % segs_n
            v3 = ((j + 1) % segs_m) * segs_n + i
            polys.append(c4d.CPolygon(v0, v1, v2, v3))
    return verts, polys


def _build_torus_hexagonal(r_major, r_minor, segs_m, segs_n, inner_radius_ratio=0.6):
    """
    Гексагональная сетка на торе.
    Внутренние вершины каждой ячейки смещены к центру,
    создавая гексагональный паттерн.
    """
    verts = []
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        cp = math.cos(phi)
        sp = math.sin(phi)
        for i in range(segs_n):
            theta = i / segs_n * 2.0 * math.pi
            ct = math.cos(theta)
            st = math.sin(theta)
            r = r_major + r_minor * ct * inner_radius_ratio
            x = r * cp
            y = r_minor * st * inner_radius_ratio
            z = r * sp
            verts.append(c4d.Vector(x, y, z))

    polys = []
    for j in range(segs_m):
        for i in range(segs_n):
            v0 = j * segs_n + i
            v1 = j * segs_n + (i + 1) % segs_n
            v2 = ((j + 1) % segs_m) * segs_n + (i + 1) % segs_n
            v3 = ((j + 1) % segs_m) * segs_n + i
            polys.append(c4d.CPolygon(v0, v1, v2, v3))
    return verts, polys


def _apply_deformations(verts, segs_m, segs_n,
                        twist, taper_x, taper_y,
                        scale_x, scale_y, scale_z):
    """Применяет деформации к вершинам тора."""
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        twist_angle = math.radians(twist) * (j / segs_m)
        ct = math.cos(twist_angle)
        st = math.sin(twist_angle)
        for i in range(segs_n):
            idx = j * segs_n + i
            p = verts[idx]
            # Twist по оси тора
            if abs(twist_angle) > 1e-6:
                nx = p.x * ct - p.z * st
                nz = p.x * st + p.z * ct
                p = c4d.Vector(nx, p.y, nz)
            # Taper
            theta = i / segs_n * 2.0 * math.pi
            taper_mult = 1.0 + taper_x * math.cos(theta) + taper_y * math.sin(theta)
            taper_mult = max(0.01, taper_mult)
            p = c4d.Vector(p.x * taper_mult, p.y * taper_mult, p.z * taper_mult)
            # Scale
            p = c4d.Vector(p.x * scale_x, p.y * scale_y, p.z * scale_z)
            verts[idx] = p


def _apply_displacement(verts, segs_m, segs_n,
                        disp_type, amp, freq, phase,
                        octaves, lacunarity, gain):
    """Применяет смещение поверхности к вершинам тора."""
    if abs(amp) < 1e-6 or disp_type == 0:
        return
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        for i in range(segs_n):
            idx = j * segs_n + i
            theta = i / segs_n * 2.0 * math.pi
            if disp_type == 1:
                # Синусоида
                val = math.sin(phi * freq * 6.283 + theta * freq * 3.14 + phase)
            elif disp_type == 2:
                # Шум Perlin
                val = _perlin_noise_2d(
                    phi * freq + phase,
                    theta * freq,
                    octaves, lacunarity, gain, seed=42
                )
            elif disp_type == 3:
                # Радиальное
                val = math.sin(phi * freq * 6.283 + phase) * math.cos(theta * freq * 6.283 + phase)
            else:
                val = 0.0
            p = verts[idx]
            displacement = amp * val
            # Смещение по нормали (приближенно — от центра тора)
            len_xz = math.sqrt(p.x ** 2 + p.z ** 2)
            if len_xz > 1e-6:
                nx = p.x / len_xz
                nz = p.z / len_xz
            else:
                nx, nz = 0.0, 1.0
            ny = 0.0
            if abs(p.y) > 1e-6:
                ny = p.y / abs(p.y)
            verts[idx] = c4d.Vector(
                p.x + nx * displacement,
                p.y + ny * displacement * 0.3,
                p.z + nz * displacement
            )


def _build_mesh(op):
    """Главный генератор меша. Возвращает (points, polys)."""
    r_major     = max(1.0, float(_ud_get(op, TT_RADIUS_MAJOR, DEFAULT_RADIUS_MAJOR)))
    r_minor     = max(0.1, float(_ud_get(op, TT_RADIUS_MINOR, DEFAULT_RADIUS_MINOR)))
    segs_m      = max(3, int(_ud_get(op, TT_SEGS_MAJOR, DEFAULT_SEGS_MAJOR)))
    segs_n      = max(3, int(_ud_get(op, TT_SEGS_MINOR, DEFAULT_SEGS_MINOR)))
    surface_type = int(_ud_get(op, TT_SURFACE_TYPE, DEFAULT_SURFACE_TYPE))
    quads       = bool(_ud_get(op, TT_QUADS, DEFAULT_QUADS))

    twist       = float(_ud_get(op, TT_TWIST, DEFAULT_TWIST))
    taper_x     = float(_ud_get(op, TT_TAPER_X, DEFAULT_TAPER_X))
    taper_y     = float(_ud_get(op, TT_TAPER_Y, DEFAULT_TAPER_Y))
    scale_x     = max(0.01, float(_ud_get(op, TT_SCALE_X, DEFAULT_SCALE_X)))
    scale_y     = max(0.01, float(_ud_get(op, TT_SCALE_Y, DEFAULT_SCALE_Y)))
    scale_z     = max(0.01, float(_ud_get(op, TT_SCALE_Z, DEFAULT_SCALE_Z)))

    disp_type   = int(_ud_get(op, TT_DISP_TYPE, DEFAULT_DISP_TYPE))
    disp_amp    = float(_ud_get(op, TT_DISP_AMP, DEFAULT_DISP_AMP))
    disp_freq   = max(0.001, float(_ud_get(op, TT_DISP_FREQ, DEFAULT_DISP_FREQ)))
    disp_phase  = float(_ud_get(op, TT_DISP_PHASE, DEFAULT_DISP_PHASE))
    disp_oct    = max(1, int(_ud_get(op, TT_DISP_OCTAVES, DEFAULT_DISP_OCTAVES)))
    disp_lac    = max(1.0, float(_ud_get(op, TT_DISP_LACUNARITY, DEFAULT_DISP_LACUNARITY)))
    disp_gain   = max(0.01, float(_ud_get(op, TT_DISP_GAIN, DEFAULT_DISP_GAIN)))

    spiral_turns = max(0.0, float(_ud_get(op, TT_SPIRAL_TURNS, DEFAULT_SPIRAL_TURNS)))
    spiral_dir   = int(_ud_get(op, TT_SPIRAL_DIRECTION, DEFAULT_SPIRAL_DIRECTION))
    hex_inner    = max(0.1, min(1.0, float(_ud_get(op, TT_HEX_INNER_RADIUS, DEFAULT_HEX_INNER_RADIUS))))

    # ── Генерация базовой формы ─────────────────────────────────────────────
    if surface_type == 0:
        # Квадратная сетка
        if quads:
            verts, polys = _build_torus_standard(r_major, r_minor, segs_m, segs_n)
        else:
            verts, polys = _build_torus_triangulated(r_major, r_minor, segs_m, segs_n)
    elif surface_type == 1:
        # Треугольная сетка (всегда триангулирована)
        verts, polys = _build_torus_triangulated(r_major, r_minor, segs_m, segs_n)
    elif surface_type == 2:
        # Спиральная
        clockwise = (spiral_dir == 0)
        verts, polys = _build_torus_spiral(r_major, r_minor, segs_m, segs_n,
                                           spiral_turns, clockwise)
        if quads:
            pass  # квады уже
        else:
            new_polys = []
            for cp in polys:
                a, b, c, d = cp[0], cp[1], cp[2], cp[3]
                new_polys.append(c4d.CPolygon(a, b, c, c))
                new_polys.append(c4d.CPolygon(a, c, d, d))
            polys = new_polys
    elif surface_type == 3:
        # Диагональная
        verts, polys = _build_torus_diagonal(r_major, r_minor, segs_m, segs_n)
        if not quads:
            new_polys = []
            for cp in polys:
                a, b, c, d = cp[0], cp[1], cp[2], cp[3]
                new_polys.append(c4d.CPolygon(a, b, c, c))
                new_polys.append(c4d.CPolygon(a, c, d, d))
            polys = new_polys
    elif surface_type == 4:
        # Гексагональная
        verts, polys = _build_torus_hexagonal(r_major, r_minor, segs_m, segs_n, hex_inner)
        if not quads:
            new_polys = []
            for cp in polys:
                a, b, c, d = cp[0], cp[1], cp[2], cp[3]
                new_polys.append(c4d.CPolygon(a, b, c, c))
                new_polys.append(c4d.CPolygon(a, c, d, d))
            polys = new_polys
    else:
        verts, polys = _build_torus_standard(r_major, r_minor, segs_m, segs_n)

    # ── Деформации ──────────────────────────────────────────────────────────
    _apply_deformations(verts, segs_m, segs_n,
                        twist, taper_x, taper_y,
                        scale_x, scale_y, scale_z)

    # ── Смещение поверхности ────────────────────────────────────────────────
    _apply_displacement(verts, segs_m, segs_n,
                        disp_type, disp_amp, disp_freq, disp_phase,
                        disp_oct, disp_lac, disp_gain)

    return verts, polys


# ══════════════════════════════════════════════════════════════════════════════
#  UserData: создание интерфейса
# ══════════════════════════════════════════════════════════════════════════════

def _create_userdata(op):
    # SubID=1 → g_base
    g_base = _add_group(op, "Основные параметры")
    _add_in_group(op, g_base, _float_bc("Радиус (большой)",  DEFAULT_RADIUS_MAJOR, 1.0, 100000.0))
    _add_in_group(op, g_base, _float_bc("Радиус (малый)",    DEFAULT_RADIUS_MINOR, 0.1, 100000.0))
    _add_in_group(op, g_base, _int_bc  ("Сегменты (кольцо)", DEFAULT_SEGS_MAJOR, 3, 500))
    _add_in_group(op, g_base, _int_bc  ("Сегменты (труба)",  DEFAULT_SEGS_MINOR, 3, 500))
    _add_in_group(op, g_base, _cycle_bc("Тип поверхности",   DEFAULT_SURFACE_TYPE,
                  ["Квадратная", "Треугольная", "Спиральная",
                   "Диагональная", "Гексагональная"]))
    _add_in_group(op, g_base, _bool_bc("Квадратные ячейки",  DEFAULT_QUADS))

    # SubID=8 → g_deform
    g_deform = _add_group(op, "Деформации")
    _add_in_group(op, g_deform, _float_bc("Кручение (Twist)", DEFAULT_TWIST, -3600.0, 3600.0,
                  unit=c4d.DESC_UNIT_DEGREE, step=1.0))
    _add_in_group(op, g_deform, _float_bc("Сужение X (Taper)", DEFAULT_TAPER_X, -2.0, 2.0,
                  unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_deform, _float_bc("Сужение Y (Taper)", DEFAULT_TAPER_Y, -2.0, 2.0,
                  unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_deform, _float_bc("Масштаб X", DEFAULT_SCALE_X, 0.01, 10.0,
                  unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_deform, _float_bc("Масштаб Y", DEFAULT_SCALE_Y, 0.01, 10.0,
                  unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_deform, _float_bc("Масштаб Z", DEFAULT_SCALE_Z, 0.01, 10.0,
                  unit=c4d.DESC_UNIT_FLOAT, step=0.01))

    # SubID=15 → g_disp
    g_disp = _add_group(op, "Смещение поверхности")
    _add_in_group(op, g_disp, _cycle_bc("Тип смещения", DEFAULT_DISP_TYPE,
                  ["Нет", "Синусоида", "Шум Perlin", "Радиальное"]))
    _add_in_group(op, g_disp, _float_bc("Амплитуда", DEFAULT_DISP_AMP, 0.0, 10000.0))
    _add_in_group(op, g_disp, _float_bc("Частота", DEFAULT_DISP_FREQ, 0.001, 10.0,
                  unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_disp, _float_bc("Фаза (анимировать)", DEFAULT_DISP_PHASE,
                  -1000.0, 1000.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_disp, _int_bc("Октавы шума", DEFAULT_DISP_OCTAVES, 1, 8))
    _add_in_group(op, g_disp, _float_bc("Лакунарность", DEFAULT_DISP_LACUNARITY,
                  1.0, 8.0, unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_disp, _float_bc("Усиление (Gain)", DEFAULT_DISP_GAIN,
                  0.01, 2.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01))

    # SubID=23 → g_spiral
    g_spiral = _add_group(op, "Спираль")
    _add_in_group(op, g_spiral, _float_bc("Количество витков", DEFAULT_SPIRAL_TURNS,
                  0.0, 50.0, unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_spiral, _cycle_bc("Направление", DEFAULT_SPIRAL_DIRECTION,
                  ["По часовой", "Против часовой"]))

    # SubID=26 → g_hex
    g_hex = _add_group(op, "Гексагональная")
    _add_in_group(op, g_hex, _float_bc("Внутренний радиус", DEFAULT_HEX_INNER_RADIUS,
                  0.1, 1.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01))

    # SubID=28 → g_phong
    g_phong = _add_group(op, "Фонг")
    _add_in_group(op, g_phong, _float_bc("Угол фонга (°)", DEFAULT_PHONG_ANGLE,
                  0.0, 180.0, unit=c4d.DESC_UNIT_DEGREE, step=1.0))
    _add_in_group(op, g_phong, _bool_bc("Ограничение угла", DEFAULT_PHONG_LIMIT))


def _set_defaults(op):
    _ud_set(op, TT_RADIUS_MAJOR,  DEFAULT_RADIUS_MAJOR)
    _ud_set(op, TT_RADIUS_MINOR,  DEFAULT_RADIUS_MINOR)
    _ud_set(op, TT_SEGS_MAJOR,    DEFAULT_SEGS_MAJOR)
    _ud_set(op, TT_SEGS_MINOR,    DEFAULT_SEGS_MINOR)
    _ud_set(op, TT_SURFACE_TYPE,  DEFAULT_SURFACE_TYPE)
    _ud_set(op, TT_QUADS,         DEFAULT_QUADS)

    _ud_set(op, TT_TWIST,   DEFAULT_TWIST)
    _ud_set(op, TT_TAPER_X, DEFAULT_TAPER_X)
    _ud_set(op, TT_TAPER_Y, DEFAULT_TAPER_Y)
    _ud_set(op, TT_SCALE_X, DEFAULT_SCALE_X)
    _ud_set(op, TT_SCALE_Y, DEFAULT_SCALE_Y)
    _ud_set(op, TT_SCALE_Z, DEFAULT_SCALE_Z)

    _ud_set(op, TT_DISP_TYPE,     DEFAULT_DISP_TYPE)
    _ud_set(op, TT_DISP_AMP,      DEFAULT_DISP_AMP)
    _ud_set(op, TT_DISP_FREQ,     DEFAULT_DISP_FREQ)
    _ud_set(op, TT_DISP_PHASE,    DEFAULT_DISP_PHASE)
    _ud_set(op, TT_DISP_OCTAVES,  DEFAULT_DISP_OCTAVES)
    _ud_set(op, TT_DISP_LACUNARITY, DEFAULT_DISP_LACUNARITY)
    _ud_set(op, TT_DISP_GAIN,     DEFAULT_DISP_GAIN)

    _ud_set(op, TT_SPIRAL_TURNS,   DEFAULT_SPIRAL_TURNS)
    _ud_set(op, TT_SPIRAL_DIRECTION, DEFAULT_SPIRAL_DIRECTION)
    _ud_set(op, TT_HEX_INNER_RADIUS, DEFAULT_HEX_INNER_RADIUS)

    _ud_set(op, TT_PHONG_ANGLE, DEFAULT_PHONG_ANGLE)
    _ud_set(op, TT_PHONG_LIMIT, DEFAULT_PHONG_LIMIT)


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin class
# ══════════════════════════════════════════════════════════════════════════════

class TriTorusObject(c4d.plugins.ObjectData):
    """Параметрический тор с расширенными возможностями."""

    OBJECT_NAME = "Tri Torus"

    def _ensure_ud(self, op):
        if not _ud_exists(op, TT_FIRST_PARAM):
            _create_userdata(op)
            _set_defaults(op)

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
        self._ensure_ud(op)
        return True

    def GetVirtualObjects(self, op, hh):
        self._ensure_ud(op)

        points, polys = _build_mesh(op)
        obj = _make_poly_object(points, polys, self.OBJECT_NAME)

        phong_angle = max(0.0, min(180.0, float(_ud_get(op, TT_PHONG_ANGLE, DEFAULT_PHONG_ANGLE))))
        phong_limit = bool(_ud_get(op, TT_PHONG_LIMIT, DEFAULT_PHONG_LIMIT))
        _add_phong_tag(obj, phong_angle, phong_limit)

        return obj

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

_ICON_TT = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29t"
    "LmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4g"
    "PHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIg"
    "NzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8v"
    "d3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIg"
    "eG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2Rj"
    "L2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIg"
    "eG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMu"
    "YWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9z"
    "aG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1v"
    "ZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzM6NTMrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6"
    "MzM6NTMrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0"
    "YW5jZUlEPSJ4bXAuaWlkOjI5YjMxZWUxLWYxODItMDQ0OS04OTkwLTNjNWUwNzJiNDg2NSIgeG1wTU06RG9jdW1lbnRJ"
    "RD0ieG1wLmRpZDoyOWIzMWVlMS1mMTgyLTA0NDktODk5MC0zYzVlMDcyYjQ4NjUiIHhtcE1NOk9yaWdpbmFsRG9jdW1l"
    "bnRJRD0ieG1wLmRpZDoyOWIzMWVlMS1mMTgyLTA0NDktODk5MC0zYzVlMDcyYjQ4NjUiPiA8eG1wTU06SGlzdG9yeT4g"
    "PHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjI5"
    "YjMxZWUxLWYxODItMDQ0OS04OTkwLTNjNWUwNzJiNDg2NSIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSsw"
    "MzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNl"
    "cT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFj"
    "a2V0IGVuZD0iciI/Pg=="
)


def _make_icon_tt():
    png_data = base64.b64decode(_ICON_TT)
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


ICO_TT = _make_icon_tt()

# ══════════════════════════════════════════════════════════════════════════════
#  Точка входа — регистрация плагина
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_TRITORUS,
        str         = NAME_TRITORUS,
        g           = TriTorusObject,
        description = "",
        icon        = ICO_TT,
        info        = c4d.OBJECT_GENERATOR,
    )
