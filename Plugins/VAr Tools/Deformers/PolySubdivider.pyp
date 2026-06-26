# ============================================================
#  PolySubdivider — плагин для Cinema 4D R26
#  Эксперементальный налог Divider: несколько алгоритмов разбиения
#  полигонов с возможностью лёгкого добавления новых типов.
#
#  Установка:
#    Положить файл PolySubdivider.pyp в папку:
#    ..\AppData\Roaming\Maxon\Cinema 4D R26_xxx\plugins\VAr Tools\
#
#  ID плагина: 1068837
# ============================================================

import c4d # type: ignore
from c4d import plugins, utils # type: ignore
import math
import random
import os
import base64
import tempfile

# ── ID плагина ──
PLUGIN_ID = 1068837
MENU_NAME = "Poly Subdivider"
MENU_NAME_V = "Poly Subdivider v1.0.3 (Experimental)"

# ============================================================
#  ID параметров (должны быть > 999, не пересекаться с C4D)
# ============================================================
PAR_ALGORITHM   = 1100
PAR_ITERATIONS  = 1101
PAR_SLIDER_X    = 1102
PAR_SLIDER_Y    = 1103
PAR_SLIDER_Z    = 1104
PAR_RANDOM_SEED = 1105
PAR_NOISE_AMT   = 1106
PAR_NOISE_FREQ  = 1107
PAR_NOISE_LOOP  = 1108
PAR_PATTERN_ROT = 1109
PAR_GRID_SCALE  = 1110

GRP_SETTINGS    = 1200
GRP_NOISE       = 1201

# ============================================================
#  Индексы алгоритмов
# ============================================================
ALG_UNIFORM     = 0
ALG_RANDOM      = 1
ALG_DIAGONAL    = 2
ALG_HERRINGBONE = 3
ALG_RADIAL      = 4
ALG_VORONOI     = 5

ALG_NAMES = [
    "Равномерное",
    "Случайное",
    "Диагональ",
    "Ёлочка",
    "Радиальное",
    "Вороной",
]

# ============================================================
#  Вспомогательные функции
# ============================================================

def lerp(a, b, t):
    return a + (b - a) * t

def mid_pt(a, b):
    return (a + b) * 0.5

def simple_noise(x, y, z, freq=1.0):
    x, y, z = x * freq, y * freq, z * freq
    return math.sin(x * 127.1 + y * 311.7 + z * 74.9)

# ============================================================
#  Строитель меша
# ============================================================

class MeshBuilder(object):
    def __init__(self):
        self.verts = []
        self.polys = []

    def add_vert(self, v):
        idx = len(self.verts)
        self.verts.append(c4d.Vector(v.x, v.y, v.z))
        return idx

    def add_quad(self, a, b, c, d):
        self.polys.append((a, b, c, d))

    def add_tri(self, a, b, c):
        self.polys.append((a, b, c, c))

    def build(self):
        if not self.verts or not self.polys:
            return None
        obj = c4d.PolygonObject(len(self.verts), len(self.polys))
        for i, v in enumerate(self.verts):
            obj.SetPoint(i, v)
        for i, p in enumerate(self.polys):
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[3]))
        obj.Message(c4d.MSG_UPDATE)
        return obj

# ============================================================
#  Утилиты
# ============================================================

def get_source_polys(src_obj):
    pts = [src_obj.GetPoint(i) for i in range(src_obj.GetPointCount())]
    result = []
    for i in range(src_obj.GetPolygonCount()):
        p = src_obj.GetPolygon(i)
        if p.c == p.d:
            result.append([pts[p.a], pts[p.b], pts[p.c]])
        else:
            result.append([pts[p.a], pts[p.b], pts[p.c], pts[p.d]])
    return result

def ensure_quad(poly):
    if len(poly) == 3:
        return [poly[0], poly[1], poly[2], poly[2]]
    return list(poly)

# ============================================================
#  Алгоритмы подразделения
# ============================================================

def subdivide_uniform(src_obj, p):
    """Равномерная UV-сетка — аналог Dmitris."""
    div   = max(1, p["iterations"])
    sx    = p["slider_x"] - 0.5
    sy    = p["slider_y"] - 0.5
    sz    = (p["slider_z"] - 0.5) * 200.0
    noise = p["noise_amt"]
    freq  = max(0.01, p["noise_freq"])
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly
        edge_u = p1 - p0
        edge_v = p3 - p0
        poly_normal = edge_u.Cross(edge_v)
        n_len = poly_normal.GetLength()
        if n_len > 0.0001:
            poly_normal = poly_normal / n_len
        grid = []
        for row in range(div + 1):
            tv = row / float(div)
            if 0 < row < div:
                tv = max(0.0, min(1.0, tv + sy / div))
            grid_row = []
            for col in range(div + 1):
                tu = col / float(div)
                if 0 < col < div:
                    tu = max(0.0, min(1.0, tu + sx / div))
                bot = lerp(p0, p1, tu)
                top = lerp(p3, p2, tu)
                pt  = lerp(bot, top, tv)
                if noise > 0:
                    n = simple_noise(pt.x, pt.y, pt.z, freq)
                    j = noise * rng.uniform(0.8, 1.2)
                    pt = pt + c4d.Vector(n * j, n * j * 0.5, n * j)
                if sz != 0.0 and 0 < row < div and 0 < col < div:
                    pt = pt + poly_normal * sz
                grid_row.append(mb.add_vert(pt))
            grid.append(grid_row)
        for row in range(div):
            for col in range(div):
                mb.add_quad(grid[row][col], grid[row][col+1],
                            grid[row+1][col+1], grid[row+1][col])
    return mb


def subdivide_random(src_obj, p):
    """Случайные горизонтальные / вертикальные разрезы."""
    iters = max(1, p["iterations"])
    bias  = p["slider_x"]
    noise = p["noise_amt"]
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    def split_h(quad, t):
        a, b, c, d = quad
        return [a, b, lerp(b, c, t), lerp(a, d, t)], \
               [lerp(a, d, t), lerp(b, c, t), c, d]

    def split_v(quad, t):
        a, b, c, d = quad
        return [a, lerp(a, b, t), lerp(d, c, t), d], \
               [lerp(a, b, t), b, c, lerp(d, c, t)]

    for poly in get_source_polys(src_obj):
        pieces = [ensure_quad(poly)]
        for _ in range(iters):
            nxt = []
            for piece in pieces:
                t = rng.uniform(0.15, 0.85)
                t = t * (1.0 - bias) + bias * rng.uniform(0.4, 0.6)
                t = max(0.1, min(0.9, t))
                if noise > 0:
                    t += simple_noise(piece[0].x, piece[0].y,
                                      piece[0].z) * noise * 0.1
                    t = max(0.1, min(0.9, t))
                if rng.random() < 0.5:
                    nxt.extend(split_h(piece, t))
                else:
                    nxt.extend(split_v(piece, t))
            pieces = nxt
        for piece in pieces:
            mb.add_quad(*[mb.add_vert(v) for v in piece])
    return mb


def subdivide_diagonal(src_obj, p):
    """Рекурсивное fan-деление через смещённый центр."""
    iters = max(1, p["iterations"])
    sx    = p["slider_x"]
    sy    = p["slider_y"]
    noise = p["noise_amt"]
    freq  = max(0.01, p["noise_freq"])
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    def diag_split(quad, depth):
        p0, p1, p2, p3 = quad
        center = lerp(lerp(p0, p1, sx), lerp(p3, p2, sx), sy)
        if noise > 0:
            n = simple_noise(center.x, center.y, center.z, freq)
            j = noise * rng.uniform(0.5, 1.5)
            center = center + c4d.Vector(n*j, n*j*0.3, n*j)
        if depth <= 1:
            ci = mb.add_vert(center)
            i0, i1 = mb.add_vert(p0), mb.add_vert(p1)
            i2, i3 = mb.add_vert(p2), mb.add_vert(p3)
            mb.add_tri(i0, i1, ci)
            mb.add_tri(i1, i2, ci)
            mb.add_tri(i2, i3, ci)
            mb.add_tri(i3, i0, ci)
        else:
            m01, m12 = mid_pt(p0,p1), mid_pt(p1,p2)
            m23, m30 = mid_pt(p2,p3), mid_pt(p3,p0)
            diag_split([p0,  m01, center, m30], depth-1)
            diag_split([m01, p1,  m12, center], depth-1)
            diag_split([center, m12, p2,  m23], depth-1)
            diag_split([m30, center, m23, p3 ], depth-1)

    for poly in get_source_polys(src_obj):
        diag_split(ensure_quad(poly), iters)
    return mb


def subdivide_herringbone(src_obj, p):
    """Паркетный паттерн «Ёлочка» со смещением чётных строк."""
    div   = max(1, p["iterations"])
    sx    = p["slider_x"]
    sy    = p["slider_y"]
    noise = p["noise_amt"]
    freq  = max(0.01, p["noise_freq"])
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly
        grid = []
        for row in range(div + 1):
            tv     = row / float(div)
            tv_adj = min(tv * (0.5 + sy * 0.5) * 2.0, 1.0)
            shift  = sx * 0.5 if (row % 2 == 1) else 0.0
            grid_row = []
            for col in range(div + 1):
                tu  = (col / float(div) + shift) % 1.0
                bot = lerp(p0, p1, tu)
                top = lerp(p3, p2, tu)
                pt  = lerp(bot, top, tv_adj)
                if noise > 0:
                    n = simple_noise(pt.x, pt.y, pt.z, freq)
                    j = noise * rng.uniform(0.7, 1.3)
                    pt = pt + c4d.Vector(n*j, n*j*0.4, n*j)
                grid_row.append(mb.add_vert(pt))
            grid.append(grid_row)
        for row in range(div):
            for col in range(div):
                mb.add_quad(grid[row][col], grid[row][col+1],
                            grid[row+1][col+1], grid[row+1][col])
    return mb


def subdivide_radial(src_obj, p):
    """Радиальные секторы из смещённого центра полигона."""
    iters   = max(1, p["iterations"])
    cx      = p["slider_x"]
    cy      = p["slider_y"]
    sectors = iters * 2 + 4
    noise   = p["noise_amt"]
    freq    = max(0.01, p["noise_freq"])
    rng     = random.Random(p["random_seed"])
    mb      = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly
        center = lerp(lerp(p0, p1, cx), lerp(p3, p2, cx), cy)
        if noise > 0:
            n = simple_noise(center.x, center.y, center.z, freq)
            j = noise * rng.uniform(0.4, 1.2)
            center = center + c4d.Vector(n*j, n*j*0.3, n*j)
        ci  = mb.add_vert(center)
        seg = max(1, sectors // 4)
        rim = []
        for ea, eb in [(p0,p1),(p1,p2),(p2,p3),(p3,p0)]:
            for k in range(seg):
                rim.append(lerp(ea, eb, k / float(seg)))
        rim_ids = [mb.add_vert(v) for v in rim]
        n_rim   = len(rim_ids)
        for k in range(n_rim):
            mb.add_tri(ci, rim_ids[k], rim_ids[(k+1) % n_rim])
    return mb


def subdivide_voronoi(src_obj, p):
    """Вороной-подобная сетка из случайных точек-сайтов."""
    iters     = max(1, p["iterations"])
    num_sites = min(iters * iters + 2, 30)
    noise     = p["noise_amt"]
    freq      = max(0.01, p["noise_freq"])
    rng       = random.Random(p["random_seed"])
    mb        = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly
        sites = []
        for _ in range(num_sites):
            u   = rng.uniform(0.05, 0.95)
            v   = rng.uniform(0.05, 0.95)
            pt  = lerp(lerp(p0, p1, u), lerp(p3, p2, u), v)
            if noise > 0:
                n  = simple_noise(pt.x, pt.y, pt.z, freq)
                j  = noise * rng.uniform(0.2, 0.8)
                pt = pt + c4d.Vector(n*j, n*j, n*j)
            sites.append(pt)
        sids = [mb.add_vert(s) for s in sites]
        for i, si in enumerate(sites):
            dists = sorted(
                ((( si - sites[j]).GetLength(), j)
                 for j in range(len(sites)) if j != i)
            )
            for k in range(min(3, len(dists))):
                j  = dists[k][1]
                mi = mb.add_vert(mid_pt(si, sites[j]))
                mb.add_tri(sids[i], sids[j], mi)
    return mb

# ============================================================
#  Реестр алгоритмов — добавьте сюда новый ALG_* + функцию
# ============================================================
ALGORITHM_REGISTRY = {
    ALG_UNIFORM:     subdivide_uniform,
    ALG_RANDOM:      subdivide_random,
    ALG_DIAGONAL:    subdivide_diagonal,
    ALG_HERRINGBONE: subdivide_herringbone,
    ALG_RADIAL:      subdivide_radial,
    ALG_VORONOI:     subdivide_voronoi,
}

# ============================================================
#  Класс плагина
# ============================================================

class PolySubdividerObject(plugins.ObjectData):
    """
    Генераторный ObjectData-плагин Cinema 4D R26.
    Берёт первого дочернего потомка и разбивает его полигоны
    выбранным алгоритмом.
    """

    def Init(self, op):
        """Значения атрибутов по умолчанию."""
        op[PAR_ALGORITHM]   = ALG_UNIFORM
        op[PAR_ITERATIONS]  = 3
        op[PAR_SLIDER_X]    = 0.18
        op[PAR_SLIDER_Y]    = 0.35
        op[PAR_SLIDER_Z]    = 0.50
        op[PAR_RANDOM_SEED] = 1235
        op[PAR_NOISE_AMT]   = 0.5
        op[PAR_NOISE_FREQ]  = 3.0
        op[PAR_NOISE_LOOP]  = 0.0
        op[PAR_PATTERN_ROT] = 0.0
        op[PAR_GRID_SCALE]  = 1.0
        return True

    def GetVirtualObjects(self, op, hh):
        """Генерация геометрии при каждом обновлении сцены."""
        child = op.GetDown()
        if child is None:
            return None

        # Получаем полигональное представление child
        src = child.GetDeformCache()
        if src is None:
            src = child.GetCache(hh)
        if src is None:
            src = child

        # Конвертируем примитив в полигоны если нужно
        if not src.CheckType(c4d.Opolygon):
            res_csto = utils.SendModelingCommand(
                command = c4d.MCOMMAND_CURRENTSTATETOOBJECT,
                list    = [src.GetClone()],
                mode    = c4d.MODELINGCOMMANDMODE_ALL,
                doc     = op.GetDocument()
            )
            if not res_csto or not res_csto[0].CheckType(c4d.Opolygon):
                return None
            src = res_csto[0]

        # Защита: нет геометрии (объект деактивирован)
        if src.GetPointCount() == 0:
            return None

        params = {
            "iterations":  op[PAR_ITERATIONS],
            "slider_x":    op[PAR_SLIDER_X],
            "slider_y":    op[PAR_SLIDER_Y],
            "slider_z":    op[PAR_SLIDER_Z],
            "random_seed": op[PAR_RANDOM_SEED],
            "noise_amt":   op[PAR_NOISE_AMT],
            "noise_freq":  op[PAR_NOISE_FREQ],
            "noise_loop":  op[PAR_NOISE_LOOP],
            "pattern_rot": op[PAR_PATTERN_ROT],
            "grid_scale":  op[PAR_GRID_SCALE],
        }

        alg  = op[PAR_ALGORITHM]
        func = ALGORITHM_REGISTRY.get(alg)
        if func is None:
            return None

        try:
            res = func(src, params).build()
        except Exception as e:
            print("[PolySubdivider] Ошибка: {}".format(e))
            import traceback; traceback.print_exc()
            return None

        if res is None:
            return None

        alg_name = ALG_NAMES[alg] if alg < len(ALG_NAMES) else str(alg)
        res.SetName("PolySubdivider [{}]".format(alg_name))
        return res

    def GetDDescription(self, op, description, flags):
        """Программное построение панели Атрибуты."""
        description.LoadDescription("Obase")  # базовый дескриптор даёт вкладки «Общее» и «Координаты»

        # ── Группа «Настройки подразделения» ─────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Настройки подразделения"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GRP_SETTINGS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid = c4d.DescID(c4d.DescLevel(GRP_SETTINGS, c4d.DTYPE_GROUP, 0))

        # Алгоритм
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Алгоритм"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = ALG_UNIFORM
        cyc = c4d.BaseContainer()
        for i, name in enumerate(ALG_NAMES):
            cyc[i] = name
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_ALGORITHM, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # Итерации
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Итерации"
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 8
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_DEFAULT] = 3
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_ITERATIONS, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # Смещение X
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Смещение X"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 1.0
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 0.18
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_X, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Смещение Y
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Смещение Y"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 1.0
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 0.35
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_Y, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Смещение Z
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Смещение Z"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 1.0
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 0.50
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_Z, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Угол паттерна
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Угол паттерна"
        bc[c4d.DESC_MIN]     = -math.pi
        bc[c4d.DESC_MAX]     = math.pi
        bc[c4d.DESC_STEP]    = math.radians(1.0)
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_DEFAULT] = 0.0
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_PATTERN_ROT, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Зерно случайности
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Зерно случайности"
        bc[c4d.DESC_MIN]     = 0
        bc[c4d.DESC_MAX]     = 99999
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_DEFAULT] = 0
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0
        bc[c4d.DESC_MAXSLIDER] = 100
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_RANDOM_SEED, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # ── Группа «Шум» ──────────────────────────────────────
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Шум"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GRP_NOISE, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        nid = c4d.DescID(c4d.DescLevel(GRP_NOISE, c4d.DTYPE_GROUP, 0))

        # Величина шума
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Величина шума"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 50.0
        bc[c4d.DESC_STEP]    = 0.1
        bc[c4d.DESC_DEFAULT] = 0.5
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_AMT, c4d.DTYPE_REAL, 0)),
            bc, nid
        )

        # Частота шума
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Частота шума"
        bc[c4d.DESC_MIN]     = 0.1
        bc[c4d.DESC_MAX]     = 20.0
        bc[c4d.DESC_STEP]    = 0.1
        bc[c4d.DESC_DEFAULT] = 3.0
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_FREQ, c4d.DTYPE_REAL, 0)),
            bc, nid
        )

        # Петля шума
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Петля шума"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 1.0
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 0.0
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_LOOP, c4d.DTYPE_REAL, 0)),
            bc, nid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "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"

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



# ============================================================
#  Регистрация плагина
#  ВАЖНО: description должен быть "Obase" — базовый объект C4D,
#  который существует всегда и не требует .res файлов.
#  Весь кастомный UI строится через GetDDescription выше.
# ============================================================
if __name__ == "__main__":
    ok = plugins.RegisterObjectPlugin(
        id          = PLUGIN_ID,
        str         = MENU_NAME_V,
        g           = PolySubdividerObject,
        description = "Obase",
        icon        = _make_icon(),
        info        = c4d.OBJECT_GENERATOR | c4d.OBJECT_INPUT,
    )
    if not ok:
        raise RuntimeError("PolySubdivider: регистрация не удалась")
    print("PolySubdivider: плагин зарегистрирован (ID={})".format(PLUGIN_ID))
