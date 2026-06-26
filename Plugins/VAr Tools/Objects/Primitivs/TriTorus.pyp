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

# ══════════════════════════════════════════════════════════════════════════════
#  Plugin ID & Name
# ══════════════════════════════════════════════════════════════════════════════

ID_TRITORUS  = 1068874
NAME_TRITORUS = "Tri Torus v2.6.1"

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

        # ── Основные ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Основные"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_GRP_BASE, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_base = c4d.DescID(c4d.DescLevel(TT_GRP_BASE, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Радиус (большой)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_RADIUS_MAJOR
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 10.0
        bc[c4d.DESC_MAXSLIDER] = 300.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_RADIUS_MAJOR, c4d.DTYPE_REAL, 0)),
            bc, gid_base
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Радиус (малый)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_RADIUS_MINOR
        bc[c4d.DESC_MIN]       = 0.1
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 0.5
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1.0
        bc[c4d.DESC_MAXSLIDER] = 100.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_RADIUS_MINOR, c4d.DTYPE_REAL, 0)),
            bc, gid_base
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Сегменты (кольцо)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SEGS_MAJOR
        bc[c4d.DESC_MIN]       = 3
        bc[c4d.DESC_MAX]       = 1000
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 100
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_SEGS_MAJOR, c4d.DTYPE_LONG, 0)),
            bc, gid_base
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Сегменты (труба)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SEGS_MINOR
        bc[c4d.DESC_MIN]       = 3
        bc[c4d.DESC_MAX]       = 500
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 100
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_SEGS_MINOR, c4d.DTYPE_LONG, 0)),
            bc, gid_base
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Тип поверхности"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SURFACE_TYPE
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        cyc = c4d.BaseContainer()
        cyc[0] = "Квадратная"
        cyc[1] = "Треугольная"
        cyc[2] = "Спиральная"
        cyc[3] = "Диагональная"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_SURFACE_TYPE, c4d.DTYPE_LONG, 0)),
            bc, gid_base
        )

        # ── Деформации ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Деформации"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_GRP_DEFORM, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_deform = c4d.DescID(c4d.DescLevel(TT_GRP_DEFORM, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Кручение (Twist)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_TWIST
        bc[c4d.DESC_MIN]       = math.radians(-3600.0)
        bc[c4d.DESC_MAX]       = math.radians(3600.0)
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_STEP]      = math.radians(1.0)
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = math.radians(-90.0)
        bc[c4d.DESC_MAXSLIDER] = math.radians(90.0)
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_TWIST, c4d.DTYPE_REAL, 0)),
            bc, gid_deform
        )

        for name, pid, default in [
            ("Сужение X (Taper)", TT_TAPER_X, DEFAULT_TAPER_X),
            ("Сужение Y (Taper)", TT_TAPER_Y, DEFAULT_TAPER_Y),
        ]:
            bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
            bc[c4d.DESC_NAME]      = name
            bc[c4d.DESC_DEFAULT]   = default
            bc[c4d.DESC_MIN]       = -2.0
            bc[c4d.DESC_MAX]       = 2.0
            bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
            bc[c4d.DESC_STEP]      = 0.01
            bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
            bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
            description.SetParameter(
                c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_REAL, 0)),
                bc, gid_deform
            )

        for name, pid, default in [
            ("Масштаб X", TT_SCALE_X, DEFAULT_SCALE_X),
            ("Масштаб Y", TT_SCALE_Y, DEFAULT_SCALE_Y),
            ("Масштаб Z", TT_SCALE_Z, DEFAULT_SCALE_Z),
        ]:
            bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
            bc[c4d.DESC_NAME]      = name
            bc[c4d.DESC_DEFAULT]   = default
            bc[c4d.DESC_MIN]       = 0.01
            bc[c4d.DESC_MAX]       = 10.0
            bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
            bc[c4d.DESC_STEP]      = 0.01
            bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
            bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
            description.SetParameter(
                c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_REAL, 0)),
                bc, gid_deform
            )

        # ── Смещение поверхности ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Смещение поверхности"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_GRP_DISP, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_disp = c4d.DescID(c4d.DescLevel(TT_GRP_DISP, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Тип смещения"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISP_TYPE
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        cyc = c4d.BaseContainer()
        cyc[0] = "Нет"
        cyc[1] = "Синусоида"
        cyc[2] = "Шум Перлина"
        cyc[3] = "Радиальное"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_TYPE, c4d.DTYPE_LONG, 0)),
            bc, gid_disp
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Амплитуда"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISP_AMP
        bc[c4d.DESC_MIN]       = 0.0
        bc[c4d.DESC_MAX]       = 10000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 50.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_AMP, c4d.DTYPE_REAL, 0)),
            bc, gid_disp
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Частота"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISP_FREQ
        bc[c4d.DESC_MIN]       = 0.001
        bc[c4d.DESC_MAX]       = 10.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]      = 0.01
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_FREQ, c4d.DTYPE_REAL, 0)),
            bc, gid_disp
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Фаза (анимировать)"
        bc[c4d.DESC_DEFAULT] = DEFAULT_DISP_PHASE
        bc[c4d.DESC_MIN]     = -1000.0
        bc[c4d.DESC_MAX]     = 1000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 10.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_PHASE, c4d.DTYPE_REAL, 0)),
            bc, gid_disp
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Октавы шума"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISP_OCTAVES
        bc[c4d.DESC_MIN]       = 1
        bc[c4d.DESC_MAX]       = 8
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_OCTAVES, c4d.DTYPE_LONG, 0)),
            bc, gid_disp
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Лакунарность"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISP_LACUNARITY
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 8.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]      = 0.1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_LACUNARITY, c4d.DTYPE_REAL, 0)),
            bc, gid_disp
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Усиление (Gain)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISP_GAIN
        bc[c4d.DESC_MIN]       = 0.01
        bc[c4d.DESC_MAX]       = 2.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]      = 0.01
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_DISP_GAIN, c4d.DTYPE_REAL, 0)),
            bc, gid_disp
        )

        # ── Спираль ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Спираль"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_GRP_SPIRAL, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_spiral = c4d.DescID(c4d.DescLevel(TT_GRP_SPIRAL, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Количество витков"
        bc[c4d.DESC_DEFAULT]   = int(DEFAULT_SPIRAL_TURNS)
        bc[c4d.DESC_MIN]       = 0
        bc[c4d.DESC_MAX]       = 50
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0
        bc[c4d.DESC_MAXSLIDER] = 10
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_SPIRAL_TURNS, c4d.DTYPE_LONG, 0)),
            bc, gid_spiral
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Направление"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SPIRAL_DIRECTION
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        cyc = c4d.BaseContainer()
        cyc[0] = "По часовой"
        cyc[1] = "Против часовой"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_SPIRAL_DIRECTION, c4d.DTYPE_LONG, 0)),
            bc, gid_spiral
        )

        # ── Фонг ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Фонг"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_GRP_PHONG, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_phong = c4d.DescID(c4d.DescLevel(TT_GRP_PHONG, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Угол фонга"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_PHONG_ANGLE
        bc[c4d.DESC_MIN]       = 0.0
        bc[c4d.DESC_MAX]       = math.radians(180.0)
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_STEP]      = math.radians(1.0)
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 180.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_PHONG_ANGLE, c4d.DTYPE_REAL, 0)),
            bc, gid_phong
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Ограничение угла"
        bc[c4d.DESC_DEFAULT] = DEFAULT_PHONG_LIMIT
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TT_PHONG_LIMIT, c4d.DTYPE_BOOL, 0)),
            bc, gid_phong
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  Иконка
# ══════════════════════════════════════════════════════════════════════════════

_ICON_TT = (
    "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"
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
