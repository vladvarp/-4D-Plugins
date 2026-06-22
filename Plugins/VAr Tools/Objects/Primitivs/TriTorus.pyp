# -*- coding: utf-8 -*-
"""
TriTorus — Cinema 4D ObjectData Plugin
=============================================
Параметрический тор с расширенными возможностями:
  • Типы поверхности: Квадратная, Треугольная, Спиральная, Диагональная
  • Деформации: Кручение (Twist), Сужение (Taper), Масштаб
  • Смещение поверхности: Нет / Синусоида / Шум Перлина / Радиальное
  • Детальная настройка фонг-сглаживания
  • Уникальная иконка

Description Parameter MAP (строго фиксировано):
  GrpID=2000 : TT_GRP_BASE     — группа «Основные»
  ID=2100    : TT_RADIUS_MAJOR
  ID=2101    : TT_RADIUS_MINOR
  ID=2102    : TT_SEGS_MAJOR
  ID=2103    : TT_SEGS_MINOR
  ID=2104    : TT_SURFACE_TYPE

  GrpID=2001 : TT_GRP_DEFORM   — группа «Деформации»
  ID=2110    : TT_TWIST
  ID=2111    : TT_TAPER_X
  ID=2112    : TT_TAPER_Y
  ID=2113    : TT_SCALE_X
  ID=2114    : TT_SCALE_Y
  ID=2115    : TT_SCALE_Z

  GrpID=2002 : TT_GRP_DISP     — группа «Смещение поверхности»
  ID=2120    : TT_DISP_TYPE
  ID=2121    : TT_DISP_AMP
  ID=2122    : TT_DISP_FREQ
  ID=2123    : TT_DISP_PHASE
  ID=2124    : TT_DISP_OCTAVES
  ID=2125    : TT_DISP_LACUNARITY
  ID=2126    : TT_DISP_GAIN

  GrpID=2003 : TT_GRP_SPIRAL   — группа «Спираль»
  ID=2130    : TT_SPIRAL_TURNS
  ID=2131    : TT_SPIRAL_DIRECTION

  GrpID=2004 : TT_GRP_PHONG    — группа «Фонг»
  ID=2140    : TT_PHONG_ANGLE
  ID=2141    : TT_PHONG_LIMIT
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
NAME_TRITORUS = "Tri Torus v2.5"

# ══════════════════════════════════════════════════════════════════════════════
#  Description Parameter IDs
# ══════════════════════════════════════════════════════════════════════════════

TT_GRP_BASE    = 2000
TT_RADIUS_MAJOR = 2100
TT_RADIUS_MINOR = 2101
TT_SEGS_MAJOR   = 2102
TT_SEGS_MINOR   = 2103
TT_SURFACE_TYPE = 2104

TT_GRP_DEFORM  = 2001
TT_TWIST       = 2110
TT_TAPER_X     = 2111
TT_TAPER_Y     = 2112
TT_SCALE_X     = 2113
TT_SCALE_Y     = 2114
TT_SCALE_Z     = 2115

TT_GRP_DISP    = 2002
TT_DISP_TYPE   = 2120
TT_DISP_AMP    = 2121
TT_DISP_FREQ   = 2122
TT_DISP_PHASE  = 2123
TT_DISP_OCTAVES  = 2124
TT_DISP_LACUNARITY = 2125
TT_DISP_GAIN   = 2126

TT_GRP_SPIRAL  = 2003
TT_SPIRAL_TURNS   = 2130
TT_SPIRAL_DIRECTION = 2131

TT_GRP_PHONG   = 2004
TT_PHONG_ANGLE = 2140
TT_PHONG_LIMIT = 2141

# ══════════════════════════════════════════════════════════════════════════════
#  Дефолтные значения
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_RADIUS_MAJOR = 150.0
DEFAULT_RADIUS_MINOR = 50.0
DEFAULT_SEGS_MAJOR   = 24
DEFAULT_SEGS_MINOR   = 12
DEFAULT_SURFACE_TYPE = 0

DEFAULT_TWIST   = 0.0
DEFAULT_TAPER_X = 0.0
DEFAULT_TAPER_Y = 0.0
DEFAULT_SCALE_X = 1.0
DEFAULT_SCALE_Y = 1.0
DEFAULT_SCALE_Z = 1.0

DEFAULT_DISP_TYPE     = 0
DEFAULT_DISP_AMP      = 0.0
DEFAULT_DISP_FREQ     = 0.1
DEFAULT_DISP_PHASE    = 0.0
DEFAULT_DISP_OCTAVES  = 4
DEFAULT_DISP_LACUNARITY = 2.0
DEFAULT_DISP_GAIN     = 0.5

DEFAULT_SPIRAL_TURNS     = 1
DEFAULT_SPIRAL_DIRECTION = 0

DEFAULT_PHONG_ANGLE = 45.0
DEFAULT_PHONG_LIMIT = True

# ══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные функции Description
# ══════════════════════════════════════════════════════════════════════════════

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


def _group_bc(name):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_TITLEBAR]   = 1
    bc[c4d.DESC_DEFAULT]    = 1
    return bc


# ══════════════════════════════════════════════════════════════════════════════
#  Фонг-тег
# ══════════════════════════════════════════════════════════════════════════════

def _add_phong_tag(obj, angle_deg=45.0, limit=True):
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = limit
        tag[c4d.PHONGTAG_PHONG_ANGLE]      = math.radians(angle_deg)
        tag[c4d.PHONGTAG_PHONG_USEEDGES]   = True
    return tag


# ══════════════════════════════════════════════════════════════════════════════
#  PolygonObject утилита + UVW
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


def _build_uv_grid(segs_m, segs_n):
    """Строит UV-координаты для вершин тора на основе сетки segs_m x segs_n.
    U = j / segs_m (воколь кольца), V = i / segs_n (воколь трубы).
    Возвращает словарь {vertex_index: c4d.Vector(u, v, 0)}.
    """
    uv_map = {}
    for j in range(segs_m):
        for i in range(segs_n):
            idx = j * segs_n + i
            u = float(j) / float(segs_m)
            v = float(i) / float(segs_n)
            uv_map[idx] = c4d.Vector(u, v, 0.0)
    return uv_map


def _create_uvw_tag(polys, uv_map, segs_m, segs_n):
    """Создаёт c4d.UVWTag на основе полигональной сетки.

    Полигоны во всех генераторах мешей создаются строго в порядке
    "for j in range(segs_m): for i in range(segs_n): ..." — один квад
    (или два треугольника из него) на итерацию. Поэтому UV для каждого
    полигона строится тем же проходом по (j, i), а не через uv_map по
    индексам вершин: вершины на шве (последний столбец/ряд) физически
    совпадают с вершинами j=0/i=0 (геометрия замкнута через %segs_m и
    %segs_n), поэтому их UV там равны 0.0. Если брать UV по индексу
    вершины, полигоны на шве получают U/V=0.0 вместо 1.0, и текстура
    схлопывается в одну сжатую полосу на шве (видно как частую
    "штриховку"). Прямой проход по (j, i) даёт каждому полигону
    собственные развёрнутые границы U: [j/segs_m, (j+1)/segs_m] и
    V: [i/segs_n, (i+1)/segs_n], независимо от того, какие вершины
    использует геометрия.
    """
    n_polys = len(polys)
    uvw_tag = c4d.UVWTag(n_polys)

    pi = 0
    for j in range(segs_m):
        u0 = float(j) / float(segs_m)
        u1 = float(j + 1) / float(segs_m)
        for i in range(segs_n):
            v0 = float(i) / float(segs_n)
            v1 = float(i + 1) / float(segs_n)

            a = c4d.Vector(u0, v0, 0.0)
            b = c4d.Vector(u0, v1, 0.0)
            c = c4d.Vector(u1, v1, 0.0)
            d = c4d.Vector(u1, v0, 0.0)

            if pi >= n_polys:
                break

            if polys[pi].c == polys[pi].d:
                # Квад разбит на два треугольника (a,b,c,c) и (a,c,d,d)
                uvw_tag.SetSlow(pi, a, b, c, c)
                pi += 1
                if pi < n_polys:
                    uvw_tag.SetSlow(pi, a, c, d, d)
                    pi += 1
            else:
                uvw_tag.SetSlow(pi, a, b, c, d)
                pi += 1
    return uvw_tag


# ══════════════════════════════════════════════════════════════════════════════
#  Шум Перлина (простая реализация)
# ══════════════════════════════════════════════════════════════════════════════

def _hash2d(ix, iy, seed=0):
    n = ix * 374761393 + iy * 668265263 + seed * 1274126177
    n = (n ^ (n >> 13)) * 1274126177
    n = n ^ (n >> 16)
    return (n & 0x7fffffff) / float(0x7fffffff) * 2.0 - 1.0


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise_2d(x, y, seed=0):
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    fx = x - ix
    fy = y - iy
    sx = _smoothstep(fx)
    sy = _smoothstep(fy)
    n00 = _hash2d(ix,     iy,     seed)
    n10 = _hash2d(ix + 1, iy,     seed)
    n01 = _hash2d(ix,     iy + 1, seed)
    n11 = _hash2d(ix + 1, iy + 1, seed)
    nx0 = n00 + sx * (n10 - n00)
    nx1 = n01 + sx * (n11 - n01)
    return nx0 + sy * (nx1 - nx0)


def _perlin_noise_2d(x, y, octaves=4, lacunarity=2.0, gain=0.5, seed=0):
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(max(1, octaves)):
        total += amplitude * _value_noise_2d(x * frequency, y * frequency, seed)
        max_val += amplitude
        amplitude *= gain
        frequency *= lacunarity
    return total / max_val if max_val > 0 else 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  Генераторы мешей
# ══════════════════════════════════════════════════════════════════════════════

def _build_torus_standard(r_major, r_minor, segs_m, segs_n):
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
            polys.append(c4d.CPolygon(v0, v1, v2, v2))
            polys.append(c4d.CPolygon(v0, v2, v3, v3))
    return verts, polys


def _build_torus_spiral(r_major, r_minor, segs_m, segs_n, turns=1.0, clockwise=True):
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


# ══════════════════════════════════════════════════════════════════════════════
#  Деформации
# ══════════════════════════════════════════════════════════════════════════════

def _apply_deformations(verts, segs_m, segs_n,
                        twist, taper_x, taper_y,
                        scale_x, scale_y, scale_z):
    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        twist_angle = twist * (j / max(segs_m - 1, 1))
        ct = math.cos(twist_angle)
        st = math.sin(twist_angle)
        for i in range(segs_n):
            idx = j * segs_n + i
            p = verts[idx]

            if abs(twist_angle) > 1e-6:
                nx = p.x * ct - p.z * st
                nz = p.x * st + p.z * ct
                p = c4d.Vector(nx, p.y, nz)

            theta = i / segs_n * 2.0 * math.pi
            taper_mult = 1.0 + taper_x * math.cos(theta) + taper_y * math.sin(theta)
            taper_mult = max(0.01, taper_mult)
            p = c4d.Vector(p.x * taper_mult, p.y * taper_mult, p.z * taper_mult)

            p = c4d.Vector(p.x * scale_x, p.y * scale_y, p.z * scale_z)
            verts[idx] = p


# ══════════════════════════════════════════════════════════════════════════════
#  Смещение поверхности
# ══════════════════════════════════════════════════════════════════════════════

def _apply_displacement(verts, segs_m, segs_n,
                        disp_type, amp, freq, phase,
                        octaves, lacunarity, gain):
    if abs(amp) < 1e-6 or disp_type == 0:
        return

    for j in range(segs_m):
        phi = j / segs_m * 2.0 * math.pi
        for i in range(segs_n):
            idx = j * segs_n + i
            theta = i / segs_n * 2.0 * math.pi

            if disp_type == 1:
                val = math.sin(phi * freq * 6.283 + theta * freq * 3.14 + phase)
            elif disp_type == 2:
                val = _perlin_noise_2d(
                    phi * freq + phase,
                    theta * freq,
                    octaves, lacunarity, gain, seed=42
                )
            elif disp_type == 3:
                val = (math.sin(phi * freq * 6.283 + phase) *
                       math.cos(theta * freq * 6.283 + phase))
            else:
                val = 0.0

            p = verts[idx]
            displacement = amp * val

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


# ══════════════════════════════════════════════════════════════════════════════
#  Главный генератор меша
# ══════════════════════════════════════════════════════════════════════════════

def _build_mesh(op):
    r_major      = max(1.0,  float(op[TT_RADIUS_MAJOR]))
    r_minor      = max(0.1,  float(op[TT_RADIUS_MINOR]))
    segs_m       = max(3,    int(op[TT_SEGS_MAJOR]))
    segs_n       = max(3,    int(op[TT_SEGS_MINOR]))
    surface_type = int(op[TT_SURFACE_TYPE])

    twist        = float(op[TT_TWIST])
    taper_x      = float(op[TT_TAPER_X])
    taper_y      = float(op[TT_TAPER_Y])
    scale_x      = max(0.01, float(op[TT_SCALE_X]))
    scale_y      = max(0.01, float(op[TT_SCALE_Y]))
    scale_z      = max(0.01, float(op[TT_SCALE_Z]))

    disp_type    = int(op[TT_DISP_TYPE])
    disp_amp     = float(op[TT_DISP_AMP])
    disp_freq    = max(0.001, float(op[TT_DISP_FREQ]))
    disp_phase   = float(op[TT_DISP_PHASE])
    disp_oct     = max(1, int(op[TT_DISP_OCTAVES]))
    disp_lac     = max(1.0, float(op[TT_DISP_LACUNARITY]))
    disp_gain    = max(0.01, float(op[TT_DISP_GAIN]))

    spiral_turns = max(0, int(op[TT_SPIRAL_TURNS]))
    spiral_dir   = int(op[TT_SPIRAL_DIRECTION])

    if surface_type == 0:
        verts, polys = _build_torus_standard(r_major, r_minor, segs_m, segs_n)
    elif surface_type == 1:
        verts, polys = _build_torus_triangulated(r_major, r_minor, segs_m, segs_n)
    elif surface_type == 2:
        clockwise = (spiral_dir == 0)
        verts, polys = _build_torus_spiral(r_major, r_minor, segs_m, segs_n,
                                           spiral_turns, clockwise)
    elif surface_type == 3:
        verts, polys = _build_torus_diagonal(r_major, r_minor, segs_m, segs_n)
    else:
        verts, polys = _build_torus_standard(r_major, r_minor, segs_m, segs_n)

    _apply_deformations(verts, segs_m, segs_n,
                        twist, taper_x, taper_y,
                        scale_x, scale_y, scale_z)

    _apply_displacement(verts, segs_m, segs_n,
                        disp_type, disp_amp, disp_freq, disp_phase,
                        disp_oct, disp_lac, disp_gain)

    uv_map = _build_uv_grid(segs_m, segs_n)

    return verts, polys, uv_map, segs_m, segs_n


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin class
# ══════════════════════════════════════════════════════════════════════════════

class TriTorusObject(c4d.plugins.ObjectData):
    """Параметрический тор с расширенными возможностями."""

    OBJECT_NAME = "Tri Torus"

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
            op[TT_RADIUS_MAJOR]  = DEFAULT_RADIUS_MAJOR
            op[TT_RADIUS_MINOR]  = DEFAULT_RADIUS_MINOR
            op[TT_SEGS_MAJOR]    = DEFAULT_SEGS_MAJOR
            op[TT_SEGS_MINOR]    = DEFAULT_SEGS_MINOR
            op[TT_SURFACE_TYPE]  = DEFAULT_SURFACE_TYPE

            op[TT_TWIST]   = DEFAULT_TWIST
            op[TT_TAPER_X] = DEFAULT_TAPER_X
            op[TT_TAPER_Y] = DEFAULT_TAPER_Y
            op[TT_SCALE_X] = DEFAULT_SCALE_X
            op[TT_SCALE_Y] = DEFAULT_SCALE_Y
            op[TT_SCALE_Z] = DEFAULT_SCALE_Z

            op[TT_DISP_TYPE]       = DEFAULT_DISP_TYPE
            op[TT_DISP_AMP]        = DEFAULT_DISP_AMP
            op[TT_DISP_FREQ]       = DEFAULT_DISP_FREQ
            op[TT_DISP_PHASE]      = DEFAULT_DISP_PHASE
            op[TT_DISP_OCTAVES]    = DEFAULT_DISP_OCTAVES
            op[TT_DISP_LACUNARITY] = DEFAULT_DISP_LACUNARITY
            op[TT_DISP_GAIN]       = DEFAULT_DISP_GAIN

            op[TT_SPIRAL_TURNS]     = DEFAULT_SPIRAL_TURNS
            op[TT_SPIRAL_DIRECTION] = DEFAULT_SPIRAL_DIRECTION

            op[TT_PHONG_ANGLE] = DEFAULT_PHONG_ANGLE
            op[TT_PHONG_LIMIT] = DEFAULT_PHONG_LIMIT
        return True

    def GetVirtualObjects(self, op, hh):
        points, polys, uv_map, segs_m, segs_n = _build_mesh(op)
        obj = _make_poly_object(points, polys, self.OBJECT_NAME)

        uvw_tag = _create_uvw_tag(polys, uv_map, segs_m, segs_n)
        obj.InsertTag(uvw_tag)

        phong_angle_rad = max(0.0, min(math.radians(180.0),
            float(op[TT_PHONG_ANGLE])))
        phong_limit = bool(op[TT_PHONG_LIMIT])
        _add_phong_tag(obj, math.degrees(phong_angle_rad), phong_limit)

        return obj

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        grp_base = c4d.DescID(c4d.DescLevel(TT_GRP_BASE, c4d.DTYPE_GROUP, 0))
        bc = _group_bc("Основные")
        description.SetParameter(grp_base, bc, c4d.ID_LISTHEAD)

        bc = _float_bc("Радиус (большой)", DEFAULT_RADIUS_MAJOR, 1.0, 100000.0)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_RADIUS_MAJOR, c4d.DTYPE_REAL, 0)), bc, grp_base)

        bc = _float_bc("Радиус (малый)", DEFAULT_RADIUS_MINOR, 0.1, 100000.0)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_RADIUS_MINOR, c4d.DTYPE_REAL, 0)), bc, grp_base)

        bc = _int_bc("Сегменты (кольцо)", DEFAULT_SEGS_MAJOR, 3, 500)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SEGS_MAJOR, c4d.DTYPE_LONG, 0)), bc, grp_base)

        bc = _int_bc("Сегменты (труба)", DEFAULT_SEGS_MINOR, 3, 500)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SEGS_MINOR, c4d.DTYPE_LONG, 0)), bc, grp_base)

        bc = _cycle_bc("Тип поверхности", DEFAULT_SURFACE_TYPE,
                       ["Квадратная", "Треугольная", "Спиральная", "Диагональная"])
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SURFACE_TYPE, c4d.DTYPE_LONG, 0)), bc, grp_base)

        grp_deform = c4d.DescID(c4d.DescLevel(TT_GRP_DEFORM, c4d.DTYPE_GROUP, 0))
        bc = _group_bc("Деформации")
        description.SetParameter(grp_deform, bc, c4d.ID_LISTHEAD)

        bc = _float_bc("Кручение (Twist)", DEFAULT_TWIST,
                       math.radians(-3600.0), math.radians(3600.0),
                       unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0))
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_TWIST, c4d.DTYPE_REAL, 0)), bc, grp_deform)

        bc = _float_bc("Сужение X (Taper)", DEFAULT_TAPER_X,
                       -2.0, 2.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_TAPER_X, c4d.DTYPE_REAL, 0)), bc, grp_deform)

        bc = _float_bc("Сужение Y (Taper)", DEFAULT_TAPER_Y,
                       -2.0, 2.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_TAPER_Y, c4d.DTYPE_REAL, 0)), bc, grp_deform)

        bc = _float_bc("Масштаб X", DEFAULT_SCALE_X,
                       0.01, 10.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SCALE_X, c4d.DTYPE_REAL, 0)), bc, grp_deform)

        bc = _float_bc("Масштаб Y", DEFAULT_SCALE_Y,
                       0.01, 10.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SCALE_Y, c4d.DTYPE_REAL, 0)), bc, grp_deform)

        bc = _float_bc("Масштаб Z", DEFAULT_SCALE_Z,
                       0.01, 10.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SCALE_Z, c4d.DTYPE_REAL, 0)), bc, grp_deform)

        grp_disp = c4d.DescID(c4d.DescLevel(TT_GRP_DISP, c4d.DTYPE_GROUP, 0))
        bc = _group_bc("Смещение поверхности")
        description.SetParameter(grp_disp, bc, c4d.ID_LISTHEAD)

        bc = _cycle_bc("Тип смещения", DEFAULT_DISP_TYPE,
                       ["Нет", "Синусоида", "Шум Перлина", "Радиальное"])
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_TYPE, c4d.DTYPE_LONG, 0)), bc, grp_disp)

        bc = _float_bc("Амплитуда", DEFAULT_DISP_AMP, 0.0, 10000.0)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_AMP, c4d.DTYPE_REAL, 0)), bc, grp_disp)

        bc = _float_bc("Частота", DEFAULT_DISP_FREQ,
                       0.001, 10.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_FREQ, c4d.DTYPE_REAL, 0)), bc, grp_disp)

        bc = _float_bc("Фаза (анимировать)", DEFAULT_DISP_PHASE,
                       -1000.0, 1000.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_PHASE, c4d.DTYPE_REAL, 0)), bc, grp_disp)

        bc = _int_bc("Октавы шума", DEFAULT_DISP_OCTAVES, 1, 8)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_OCTAVES, c4d.DTYPE_LONG, 0)), bc, grp_disp)

        bc = _float_bc("Лакунарность", DEFAULT_DISP_LACUNARITY,
                       1.0, 8.0, unit=c4d.DESC_UNIT_FLOAT, step=0.1)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_LACUNARITY, c4d.DTYPE_REAL, 0)), bc, grp_disp)

        bc = _float_bc("Усиление (Gain)", DEFAULT_DISP_GAIN,
                       0.01, 2.0, unit=c4d.DESC_UNIT_FLOAT, step=0.01)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_DISP_GAIN, c4d.DTYPE_REAL, 0)), bc, grp_disp)

        grp_spiral = c4d.DescID(c4d.DescLevel(TT_GRP_SPIRAL, c4d.DTYPE_GROUP, 0))
        bc = _group_bc("Спираль")
        description.SetParameter(grp_spiral, bc, c4d.ID_LISTHEAD)

        bc = _int_bc("Количество витков", int(DEFAULT_SPIRAL_TURNS), 0, 50)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SPIRAL_TURNS, c4d.DTYPE_LONG, 0)), bc, grp_spiral)

        bc = _cycle_bc("Направление", DEFAULT_SPIRAL_DIRECTION,
                       ["По часовой", "Против часовой"])
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_SPIRAL_DIRECTION, c4d.DTYPE_LONG, 0)), bc, grp_spiral)

        grp_phong = c4d.DescID(c4d.DescLevel(TT_GRP_PHONG, c4d.DTYPE_GROUP, 0))
        bc = _group_bc("Фонг")
        description.SetParameter(grp_phong, bc, c4d.ID_LISTHEAD)

        bc = _float_bc("Угол фонга (°)", DEFAULT_PHONG_ANGLE,
                       0.0, math.radians(180.0), unit=c4d.DESC_UNIT_DEGREE,
                       step=math.radians(1.0))
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_PHONG_ANGLE, c4d.DTYPE_REAL, 0)), bc, grp_phong)

        bc = _bool_bc("Ограничение угла", DEFAULT_PHONG_LIMIT)
        description.SetParameter(c4d.DescID(c4d.DescLevel(TT_PHONG_LIMIT, c4d.DTYPE_BOOL, 0)), bc, grp_phong)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  Иконка
# ══════════════════════════════════════════════════════════════════════════════

_ICON_TT = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzM6NTMrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzM6NTMrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjI5YjMxZWUxLWYxODItMDQ0OS04OTkwLTNjNWUwNzJiNDg2NSIgeG1wTU06RG9jdW1lbnRJRD0i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"
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
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_TRITORUS,
        str         = NAME_TRITORUS,
        g           = TriTorusObject,
        description = "Obase",
        icon        = ICO_TT,
        info        = c4d.OBJECT_GENERATOR,
    )
