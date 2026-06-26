# -*- coding: utf-8 -*-
"""
Tesseract — Cinema 4D ObjectData Plugin
=============================================
Генератор тессеракта (4D гиперкуб) с проекцией в 3D пространство.

Возможности:
  • 16 вершин, 32 ребра, 24 грани, 8 ячеек (кубов) в 4D
  • Поворот в 6 плоскостях 4D пространства (XY, XZ, XW, YZ, YW, ZW)
  • Перспективная проекция 4D → 3D
  • Отображение: каркас, рёбра-трубы, вершины, ячейки с прозрачностью
  • Автоматическая анимация вращения
"""

import c4d  # type: ignore
import math
import os
import base64
import tempfile

# ══════════════════════════════════════════════════════════════════════════════
#  Plugin ID & Name
# ══════════════════════════════════════════════════════════════════════════════

ID_TESSERACT = 1068993
NAME_TESSERACT = "Tesseract v1.7.1"

# ══════════════════════════════════════════════════════════════════════════════
#  Description-based parameter IDs
# ══════════════════════════════════════════════════════════════════════════════

# Group IDs
TS_GRP_CORE = 2000
TS_GRP_ROT = 2001
TS_GRP_ANIM = 2002
TS_GRP_VIS = 2003

# Parameter IDs
TS_SIZE = 2100
TS_PROJ_DIST = 2101
TS_DISPLAY = 2102

TS_ROT_XY = 2110
TS_ROT_XZ = 2111
TS_ROT_XW = 2112
TS_ROT_YZ = 2113
TS_ROT_YW = 2114
TS_ROT_ZW = 2115

TS_AUTO_ROT = 2120
TS_SPEED_XY = 2121
TS_SPEED_XZ = 2122
TS_SPEED_XW = 2123
TS_SPEED_YZ = 2124
TS_SPEED_YW = 2125
TS_SPEED_ZW = 2126
TS_ANIM_PHASE = 2127

TS_EDGE_RADIUS = 2130
TS_EDGE_SEGS = 2131
TS_VERTEX_RADIUS = 2132
TS_VERTEX_SEGS = 2133
TS_SHOW_CELLS = 2134

# First parameter for initialization check
TS_FIRST_PARAM = TS_SIZE

# ══════════════════════════════════════════════════════════════════════════════
#  Дефолтные значения
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_SIZE       = 200.0
DEFAULT_PROJ_DIST  = 400.0
DEFAULT_DISPLAY    = 1     # 0=Каркас, 1=Рёбра+Вершины, 2=Ячейки, 3=Всё

DEFAULT_ROT_XY     = 0.0
DEFAULT_ROT_XZ     = 0.0
DEFAULT_ROT_XW     = math.radians(0.0)  
DEFAULT_ROT_YZ     = 0.0
DEFAULT_ROT_YW     = math.radians(0.0)  
DEFAULT_ROT_ZW     = 0.0

DEFAULT_AUTO_ROT   = False
DEFAULT_SPEED_XY   = 0.0
DEFAULT_SPEED_XZ   = 0.0
DEFAULT_SPEED_XW   = 0.0
DEFAULT_SPEED_YZ   = 0.0
DEFAULT_SPEED_YW   = 0.0
DEFAULT_SPEED_ZW   = 1.0
DEFAULT_ANIM_PHASE = 0.0

DEFAULT_EDGE_RADIUS = 5.0
DEFAULT_EDGE_SEGS   = 9
DEFAULT_VERTEX_RADIUS = 10.0
DEFAULT_VERTEX_SEGS   = 8
DEFAULT_SHOW_CELLS    = False

# ══════════════════════════════════════════════════════════════════════════════
#  4D Математика
# ══════════════════════════════════════════════════════════════════════════════

def _mat4_mul(A, B):
    """Умножение двух 4x4 матриц (список списков row-major)."""
    C = [[0.0]*4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            s = 0.0
            for k in range(4):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return C


def _mat4_identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def _rot4d(axis1, axis2, angle_rad):
    """
    Матрица поворота в 4D в плоскости (axis1, axis2).
    axis1, axis2 — индексы 0..3 (x, y, z, w).
    angle_rad — угол в радианах (Значения передаются непосредственно из пользовательских данных).
    """
    a = angle_rad
    c = math.cos(a)
    s = math.sin(a)
    m = _mat4_identity()
    m[axis1][axis1] =  c
    m[axis1][axis2] = -s
    m[axis2][axis1] =  s
    m[axis2][axis2] =  c
    return m


def _apply_mat4(m, p):
    """Применяет 4x4 матрицу к 4D-точке (x, y, z, w)."""
    x, y, z, w = p
    return (
        m[0][0]*x + m[0][1]*y + m[0][2]*z + m[0][3]*w,
        m[1][0]*x + m[1][1]*y + m[1][2]*z + m[1][3]*w,
        m[2][0]*x + m[2][1]*y + m[2][2]*z + m[2][3]*w,
        m[3][0]*x + m[3][1]*y + m[3][2]*z + m[3][3]*w,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Геометрия тессеракта
# ══════════════════════════════════════════════════════════════════════════════

# 16 вершин тессеракта: все комбинации (±1, ±1, ±1, ±1)
_TESS_VERTS = []
for i in range(16):
    _TESS_VERTS.append((
        1.0 if (i & 1) else -1.0,
        1.0 if (i & 2) else -1.0,
        1.0 if (i & 4) else -1.0,
        1.0 if (i & 8) else -1.0,
    ))

# 32 ребра: пары вершин, differing in exactly 1 bit
_TESS_EDGES = []
for i in range(16):
    for bit in range(4):
        j = i ^ (1 << bit)
        if i < j:
            _TESS_EDGES.append((i, j))

# 8 ячеек (кубов): каждая фиксирует одну координату (0 или 1 по биту)
# Ячейка k фиксирует бит k: вершины, у которых бит k == 0 или == 1
_TESS_CELLS = []
for bit in range(4):
    for val in (0, 1):
        cell = []
        for i in range(16):
            if ((i >> bit) & 1) == val:
                cell.append(i)
        _TESS_CELLS.append(cell)

# 24 грани (квадраты): каждая фиксирует 2 координаты
_TESS_FACES = []
for b1 in range(4):
    for b2 in range(b1 + 1, 4):
        for v1 in (0, 1):
            for v2 in (0, 1):
                face = []
                for i in range(16):
                    if ((i >> b1) & 1) == v1 and ((i >> b2) & 1) == v2:
                        face.append(i)
                _TESS_FACES.append(tuple(sorted(face)))


def _perspective_project(point_4d, dist):
    """
    Перспективная проекция 4D → 3D.
    point_4d: (x, y, z, w)
    dist: расстояние от наблюдателя до начала координат вдоль W.
    Возвращает (x3, y3, z3).
    """
    x, y, z, w = point_4d
    denom = dist - w
    if abs(denom) < 0.001:
        denom = 0.001 if denom >= 0 else -0.001
    factor = dist / denom
    return (x * factor, y * factor, z * factor)


def _build_rotation_matrix(rot_xy, rot_xz, rot_xw, rot_yz, rot_yw, rot_zw):
    """Составная матрица поворота из 6 углов (в градусах)."""
    m = _mat4_identity()
    if rot_zw != 0.0:
        m = _mat4_mul(m, _rot4d(2, 3, rot_zw))
    if rot_yw != 0.0:
        m = _mat4_mul(m, _rot4d(1, 3, rot_yw))
    if rot_yz != 0.0:
        m = _mat4_mul(m, _rot4d(1, 2, rot_yz))
    if rot_xw != 0.0:
        m = _mat4_mul(m, _rot4d(0, 3, rot_xw))
    if rot_xz != 0.0:
        m = _mat4_mul(m, _rot4d(0, 2, rot_xz))
    if rot_xy != 0.0:
        m = _mat4_mul(m, _rot4d(0, 1, rot_xy))
    return m


def _rotate_verts(mat, size):
    """Поворачивает и масштабирует 16 вершин тессеракта."""
    half = size * 0.5
    return [_apply_mat4(mat, tuple(v[i] * half for i in range(4))) for v in _TESS_VERTS]


# ══════════════════════════════════════════════════════════════════════════════
#  Генерация 3D меша
# ══════════════════════════════════════════════════════════════════════════════

def _make_cylinder_between(p_a, p_b, radius, segs, all_pts, all_polys):
    """
    Генерирует цилиндр между двумя 3D-точками.
    segs — количество сегментов окружности (3..16).
    Добавляет вершины и полигоны в списки all_pts / all_polys.
    Возвращает (start_idx, count) — диапазон добавленных вершин.
    """
    if segs < 3:
        segs = 3
    ax, ay, az = p_a
    bx, by, bz = p_b
    dx, dy, dz = bx - ax, by - ay, bz - az
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    if length < 1e-6:
        return len(all_pts), 0

    start = len(all_pts)

    # Ось цилиндра = direction
    nx, ny, nz = dx/length, dy/length, dz/length

    # Находим вспомогательный вектор, не параллельный nx
    if abs(nx) < 0.9:
        tx, ty, tz = 1.0, 0.0, 0.0
    else:
        tx, ty, tz = 0.0, 1.0, 0.0
    dot = tx*nx + ty*ny + tz*nz
    tx -= dot*nx; ty -= dot*ny; tz -= dot*nz
    td = math.sqrt(tx*tx + ty*ty + tz*tz)
    tx /= td; ty /= td; tz /= td
    # b = n × t
    bx2 = ny*tz - nz*ty
    by2 = nz*tx - nx*tz
    bz2 = nx*ty - ny*tx

    for row in range(2):
        cx = ax if row == 0 else bx
        cy = ay if row == 0 else by
        cz = az if row == 0 else bz
        for i in range(segs):
            ang = i / segs * 2.0 * math.pi
            co = math.cos(ang) * radius
            si = math.sin(ang) * radius
            px = cx + tx*co + bx2*si
            py = cy + ty*co + by2*si
            pz = cz + tz*co + bz2*si
            all_pts.append(c4d.Vector(px, py, pz))

    for i in range(segs):
        ni = (i + 1) % segs
        # Полигон: нижнее кольцо (row=0), верхнее (row=1)
        b1 = start + i
        b2 = start + ni
        t1 = start + segs + i
        t2 = start + segs + ni
        all_polys.append(c4d.CPolygon(b1, t1, t2, b2))

    return start, segs * 2


def _make_sphere(center, radius, segs_r, segs_h, all_pts, all_polys):
    """
    Генерирует сферу в точке center.
    segs_r — сегменты окружности, segs_h — сегменты по высоте.
    """
    if segs_r < 3:
        segs_r = 3
    if segs_h < 2:
        segs_h = 2

    cx, cy, cz = center
    start = len(all_pts)

    for row in range(segs_h + 1):
        phi = row / segs_h * math.pi
        sp = math.sin(phi)
        cp = math.cos(phi)
        for col in range(segs_r):
            theta = col / segs_r * 2.0 * math.pi
            px = cx + radius * sp * math.cos(theta)
            py = cy + radius * cp
            pz = cz + radius * sp * math.sin(theta)
            all_pts.append(c4d.Vector(px, py, pz))

    for row in range(segs_h):
        for col in range(segs_r):
            nc = (col + 1) % segs_r
            bl = start + row * segs_r + col
            br = start + row * segs_r + nc
            tl = start + (row + 1) * segs_r + col
            tr = start + (row + 1) * segs_r + nc
            all_polys.append(c4d.CPolygon(bl, tl, tr, br))




def _add_phong_tag(obj, angle_deg=45.0):
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
        tag[c4d.PHONGTAG_PHONG_ANGLE]      = math.radians(angle_deg)
        tag[c4d.PHONGTAG_PHONG_USEEDGES]   = True


def _apply_selection_tag(obj, selection_name):
    n_polys = obj.GetPolygonCount()
    if n_polys == 0:
        return
    tag = obj.MakeTag(c4d.Tpolygonselection)
    if tag is None:
        return
    tag.SetName(selection_name)
    sel = tag.GetBaseSelect()
    for pi in range(n_polys):
        sel.Select(pi)


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор тессеракта
# ══════════════════════════════════════════════════════════════════════════════

def _build_tesseract(op):
    """Строит тессеракт и возвращает иерархию объектов (Null-контейнер)."""

    # ── Параметры ────────────────────────────────────────────────────────
    size        = max(10.0, float(op[TS_SIZE]))
    proj_dist   = max(50.0, float(op[TS_PROJ_DIST]))
    display     = int(op[TS_DISPLAY])

    rot_xy = float(op[TS_ROT_XY])
    rot_xz = float(op[TS_ROT_XZ])
    rot_xw = float(op[TS_ROT_XW])
    rot_yz = float(op[TS_ROT_YZ])
    rot_yw = float(op[TS_ROT_YW])
    rot_zw = float(op[TS_ROT_ZW])

    auto_rot   = bool(op[TS_AUTO_ROT])
    speed_xy   = float(op[TS_SPEED_XY])
    speed_xz   = float(op[TS_SPEED_XZ])
    speed_xw   = float(op[TS_SPEED_XW])
    speed_yz   = float(op[TS_SPEED_YZ])
    speed_yw   = float(op[TS_SPEED_YW])
    speed_zw   = float(op[TS_SPEED_ZW])
    phase      = float(op[TS_ANIM_PHASE])

    edge_r     = max(0.5, float(op[TS_EDGE_RADIUS]))
    edge_segs  = max(3, int(op[TS_EDGE_SEGS]))
    vert_r     = max(1.0, float(op[TS_VERTEX_RADIUS]))
    vert_segs  = max(3, int(op[TS_VERTEX_SEGS]))
    show_cells = bool(op[TS_SHOW_CELLS])

    # ── Автовращение: добавляем фазу к углам ────────────────────────────
    if auto_rot:
        doc = op.GetDocument()
        if doc:
            t = doc.GetTime().Get()
        else:
            t = 0.0
        rot_xy += speed_xy * t + phase
        rot_xz += speed_xz * t + phase
        rot_xw += speed_xw * t + phase
        rot_yz += speed_yz * t + phase
        rot_yw += speed_yw * t + phase
        rot_zw += speed_zw * t + phase

    # ── 4D → 3D ──────────────────────────────────────────────────────────
    mat = _build_rotation_matrix(rot_xy, rot_xz, rot_xw, rot_yz, rot_yw, rot_zw)
    verts_4d = _rotate_verts(mat, size)

    # Проекция в 3D
    verts_3d = []
    for v in verts_4d:
        projected = _perspective_project(v, proj_dist)
        verts_3d.append(projected)

    # ── Определяем видимость по W ────────────────────────────────────────
    w_vals = [v[3] for v in verts_4d]
    w_min = min(w_vals)
    w_max = max(w_vals)
    w_range = w_max - w_min if w_max - w_min > 0.001 else 1.0

    # ── Создаём корневой Null ────────────────────────────────────────────
    root = c4d.BaseObject(c4d.Onull)
    root.SetName("Tesseract")

    # ── Каркас (рёбра) ──────────────────────────────────────────────────
    show_edges = display in (0, 1, 3)
    show_verts = display in (1, 3)
    show_cells_mesh = display in (2, 3) or show_cells

    if show_edges:
        edge_pts = []
        edge_polys = []
        for i_a, i_b in _TESS_EDGES:
            _make_cylinder_between(
                verts_3d[i_a], verts_3d[i_b],
                edge_r, edge_segs,
                edge_pts, edge_polys
            )

        if edge_pts:
            edge_obj = c4d.PolygonObject(len(edge_pts), len(edge_polys))
            edge_obj.SetName("Edges")
            for i, p in enumerate(edge_pts):
                edge_obj.SetPoint(i, p)
            for i, pl in enumerate(edge_polys):
                edge_obj.SetPolygon(i, pl)
            edge_obj.Message(c4d.MSG_UPDATE)
            _add_phong_tag(edge_obj, 60.0)
            _apply_selection_tag(edge_obj, "K")
            edge_obj.InsertUnder(root)

    # ── Вершины ──────────────────────────────────────────────────────────
    if show_verts:
        for idx, (px, py, pz) in enumerate(verts_3d):
            v_pts = []
            v_polys = []
            _make_sphere((px, py, pz), vert_r, vert_segs, vert_segs, v_pts, v_polys)
            if v_pts:
                v_obj = c4d.PolygonObject(len(v_pts), len(v_polys))
                v_obj.SetName("V_%02d" % idx)
                for i, p in enumerate(v_pts):
                    v_obj.SetPoint(i, p)
                for i, pl in enumerate(v_polys):
                    v_obj.SetPolygon(i, pl)
                v_obj.Message(c4d.MSG_UPDATE)
                _add_phong_tag(v_obj, 45.0)
                _apply_selection_tag(v_obj, "P")
                v_obj.InsertUnder(root)

    # ── Ячейки (грани кубов) ────────────────────────────────────────────
    if show_cells_mesh:
        for cell_idx, cell_verts in enumerate(_TESS_CELLS):
            fixed_bit = cell_idx // 2
            free_bits = [b for b in range(4) if b != fixed_bit]

            all_cell_pts = []
            all_cell_polys = []

            for face_fixed in free_bits:
                face_bits = [b for b in free_bits if b != face_fixed]

                for face_val in (0, 1):
                    face_vi = []
                    for vi in cell_verts:
                        if ((vi >> face_fixed) & 1) == face_val:
                            face_vi.append(vi)
                    if len(face_vi) != 4:
                        continue

                    pts3 = [verts_3d[vi] for vi in face_vi]

                    # 2D-проекция: опорная плоскость = среднее нормалей 2 рёбер
                    e0 = (pts3[1][0]-pts3[0][0], pts3[1][1]-pts3[0][1], pts3[1][2]-pts3[0][2])
                    e1 = (pts3[2][0]-pts3[0][0], pts3[2][1]-pts3[0][1], pts3[2][2]-pts3[0][2])
                    nx = e0[1]*e1[2] - e0[2]*e1[1]
                    ny = e0[2]*e1[0] - e0[0]*e1[2]
                    nz = e0[0]*e1[1] - e0[1]*e1[0]
                    nl = math.sqrt(nx*nx + ny*ny + nz*nz)
                    if nl < 1e-12:
                        nx, ny, nz = 0, 0, 1
                    else:
                        nx /= nl; ny /= nl; nz /= nl

                    if abs(nx) > 0.9:
                        u = (0, 1, 0)
                    else:
                        u = (1, 0, 0)
                    ux = u[0] - (u[0]*nx + u[1]*ny + u[2]*nz)*nx
                    uy = u[1] - (u[0]*nx + u[1]*ny + u[2]*nz)*ny
                    uz = u[2] - (u[0]*nx + u[1]*ny + u[2]*nz)*nz
                    ul = math.sqrt(ux*ux + uy*uy + uz*uz)
                    ux /= ul; uy /= ul; uz /= ul
                    vx = ny*uz - nz*uy
                    vy = nz*ux - nx*uz
                    vz = nx*uy - ny*ux

                    def proj2d(p):
                        return (p[0]*ux + p[1]*uy + p[2]*uz,
                                p[0]*vx + p[1]*vy + p[2]*vz)

                    pts2d = [proj2d(p) for p in pts3]

                    # 2D convex hull (Graham scan)
                    ptsIndexed = list(enumerate(pts2d))
                    ptsIndexed.sort(key=lambda x: (x[1][1], x[1][0]))
                    p0 = ptsIndexed[0][1]
                    ptsIndexed[1:] = sorted(ptsIndexed[1:],
                        key=lambda x: math.atan2(x[1][1]-p0[1], x[1][0]-p0[0]))
                    hull = [ptsIndexed[0][0]]
                    for idx, pt in ptsIndexed[1:]:
                        while len(hull) > 1:
                            a = pts2d[hull[-2]]
                            b = pts2d[hull[-1]]
                            cross = (b[0]-a[0])*(pt[1]-a[1]) - (b[1]-a[1])*(pt[0]-a[0])
                            if cross <= 0:
                                hull.pop()
                            else:
                                break
                        hull.append(idx)

                    if len(hull) < 3:
                        continue

                    base = len(all_cell_pts)
                    for hi in hull:
                        v = pts3[hi]
                        all_cell_pts.append(c4d.Vector(v[0], v[1], v[2]))
                    n = len(hull)
                    if n == 3:
                        all_cell_polys.append(c4d.CPolygon(base, base+1, base+2, base+2))
                    elif n == 4:
                        all_cell_polys.append(c4d.CPolygon(base, base+1, base+2, base+3))
                    elif n == 5:
                        all_cell_polys.append(c4d.CPolygon(base, base+1, base+2, base+3))
                        all_cell_polys.append(c4d.CPolygon(base, base+3, base+4, base+4))
                    elif n == 6:
                        all_cell_polys.append(c4d.CPolygon(base, base+1, base+2, base+3))
                        all_cell_polys.append(c4d.CPolygon(base, base+3, base+4, base+5))

            if all_cell_pts and all_cell_polys:
                c_obj = c4d.PolygonObject(len(all_cell_pts), len(all_cell_polys))
                c_obj.SetName("Cell_%d" % cell_idx)
                for i, p in enumerate(all_cell_pts):
                    c_obj.SetPoint(i, p)
                for i, pl in enumerate(all_cell_polys):
                    c_obj.SetPolygon(i, pl)
                c_obj.Message(c4d.MSG_UPDATE)

                _add_phong_tag(c_obj, 80.0)
                _apply_selection_tag(c_obj, "C")
                c_obj.InsertUnder(root)

    return root


# ══════════════════════════════════════════════════════════════════════════════
#  Description: создание интерфейса
# ══════════════════════════════════════════════════════════════════════════════
class TesseractObject(c4d.plugins.ObjectData):
    """Генератор тессеракта (4D гиперкуб) с проекцией в 3D."""

    OBJECT_NAME = "Tesseract"

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
            op[TS_SIZE] = DEFAULT_SIZE
            op[TS_PROJ_DIST] = DEFAULT_PROJ_DIST
            op[TS_DISPLAY] = DEFAULT_DISPLAY
            op[TS_ROT_XY] = DEFAULT_ROT_XY
            op[TS_ROT_XZ] = DEFAULT_ROT_XZ
            op[TS_ROT_XW] = DEFAULT_ROT_XW
            op[TS_ROT_YZ] = DEFAULT_ROT_YZ
            op[TS_ROT_YW] = DEFAULT_ROT_YW
            op[TS_ROT_ZW] = DEFAULT_ROT_ZW
            op[TS_AUTO_ROT] = DEFAULT_AUTO_ROT
            op[TS_SPEED_XY] = DEFAULT_SPEED_XY
            op[TS_SPEED_XZ] = DEFAULT_SPEED_XZ
            op[TS_SPEED_XW] = DEFAULT_SPEED_XW
            op[TS_SPEED_YZ] = DEFAULT_SPEED_YZ
            op[TS_SPEED_YW] = DEFAULT_SPEED_YW
            op[TS_SPEED_ZW] = DEFAULT_SPEED_ZW
            op[TS_ANIM_PHASE] = DEFAULT_ANIM_PHASE
            op[TS_EDGE_RADIUS] = DEFAULT_EDGE_RADIUS
            op[TS_EDGE_SEGS] = DEFAULT_EDGE_SEGS
            op[TS_VERTEX_RADIUS] = DEFAULT_VERTEX_RADIUS
            op[TS_VERTEX_SEGS] = DEFAULT_VERTEX_SEGS
            op[TS_SHOW_CELLS] = DEFAULT_SHOW_CELLS
        return True

    def GetVirtualObjects(self, op, hh):
        return _build_tesseract(op)

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        # ── Основные ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Основные"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_GRP_CORE, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_core = c4d.DescID(c4d.DescLevel(TS_GRP_CORE, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Размер"
        bc[c4d.DESC_DEFAULT] = DEFAULT_SIZE
        bc[c4d.DESC_MIN]     = 10.0
        bc[c4d.DESC_MAX]     = 5000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_SIZE, c4d.DTYPE_REAL, 0)),
            bc, gid_core
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Расстояние проекции"
        bc[c4d.DESC_DEFAULT] = DEFAULT_PROJ_DIST
        bc[c4d.DESC_MIN]     = 50.0
        bc[c4d.DESC_MAX]     = 10000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_PROJ_DIST, c4d.DTYPE_REAL, 0)),
            bc, gid_core
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Отображение"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DISPLAY
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        cyc = c4d.BaseContainer()
        cyc[0] = "Каркас (K)"
        cyc[1] = "Рёбра (K) + Вершины (P)"
        cyc[2] = "Ячейки (C)"
        cyc[3] = "Всё"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_DISPLAY, c4d.DTYPE_LONG, 0)),
            bc, gid_core
        )

        # ── Поворот 4D ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Поворот 4D"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_GRP_ROT, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_rot = c4d.DescID(c4d.DescLevel(TS_GRP_ROT, c4d.DTYPE_GROUP, 0))

        for name, pid, default in [
            ("Поворот XY", TS_ROT_XY, DEFAULT_ROT_XY),
            ("Поворот XZ", TS_ROT_XZ, DEFAULT_ROT_XZ),
            ("Поворот XW", TS_ROT_XW, DEFAULT_ROT_XW),
            ("Поворот YZ", TS_ROT_YZ, DEFAULT_ROT_YZ),
            ("Поворот YW", TS_ROT_YW, DEFAULT_ROT_YW),
            ("Поворот ZW", TS_ROT_ZW, DEFAULT_ROT_ZW),
        ]:
            bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
            bc[c4d.DESC_NAME]      = name
            bc[c4d.DESC_DEFAULT]   = default
            bc[c4d.DESC_MIN]       = math.radians(-360.0)
            bc[c4d.DESC_MAX]       = math.radians(360.0)
            bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_DEGREE
            bc[c4d.DESC_STEP]      = math.radians(1.0)
            bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
            bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
            bc[c4d.DESC_MINSLIDER] = math.radians(-360.0)
            bc[c4d.DESC_MAXSLIDER] = math.radians(360.0)
            description.SetParameter(
                c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_REAL, 0)),
                bc, gid_rot
            )

        # ── Автовращение ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Автовращение"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_GRP_ANIM, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_anim = c4d.DescID(c4d.DescLevel(TS_GRP_ANIM, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Включить"
        bc[c4d.DESC_DEFAULT] = DEFAULT_AUTO_ROT
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_AUTO_ROT, c4d.DTYPE_BOOL, 0)),
            bc, gid_anim
        )

        for name, pid, default in [
            ("Скорость XY", TS_SPEED_XY, DEFAULT_SPEED_XY),
            ("Скорость XZ", TS_SPEED_XZ, DEFAULT_SPEED_XZ),
            ("Скорость XW", TS_SPEED_XW, DEFAULT_SPEED_XW),
            ("Скорость YZ", TS_SPEED_YZ, DEFAULT_SPEED_YZ),
            ("Скорость YW", TS_SPEED_YW, DEFAULT_SPEED_YW),
            ("Скорость ZW", TS_SPEED_ZW, DEFAULT_SPEED_ZW),
        ]:
            bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
            bc[c4d.DESC_NAME]      = name
            bc[c4d.DESC_DEFAULT]   = default
            bc[c4d.DESC_MIN]       = -5.0
            bc[c4d.DESC_MAX]       = 5.0
            bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
            bc[c4d.DESC_STEP]      = 0.1
            bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
            bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
            bc[c4d.DESC_MINSLIDER] = -5.0
            bc[c4d.DESC_MAXSLIDER] = 5.0
            description.SetParameter(
                c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_REAL, 0)),
                bc, gid_anim
            )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Фаза"
        bc[c4d.DESC_DEFAULT] = DEFAULT_ANIM_PHASE
        bc[c4d.DESC_MIN]     = -10000.0
        bc[c4d.DESC_MAX]     = 10000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = -4
        bc[c4d.DESC_MAXSLIDER] = 4
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_ANIM_PHASE, c4d.DTYPE_REAL, 0)),
            bc, gid_anim
        )

        # ── Визуал ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Визуал"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_GRP_VIS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_vis = c4d.DescID(c4d.DescLevel(TS_GRP_VIS, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Радиус рёбер (K)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_EDGE_RADIUS
        bc[c4d.DESC_MIN]       = 0.1
        bc[c4d.DESC_MAX]       = 100.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 0.5
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.1
        bc[c4d.DESC_MAXSLIDER] = 100.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_EDGE_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid_vis
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Сегменты рёбер (K)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_EDGE_SEGS
        bc[c4d.DESC_MIN]       = 3
        bc[c4d.DESC_MAX]       = 16
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 16
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_EDGE_SEGS, c4d.DTYPE_LONG, 0)),
            bc, gid_vis
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Радиус вершин (P)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_VERTEX_RADIUS
        bc[c4d.DESC_MIN]       = 0.1
        bc[c4d.DESC_MAX]       = 200.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.1
        bc[c4d.DESC_MAXSLIDER] = 200.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_VERTEX_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid_vis
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Сегменты вершин (P)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_VERTEX_SEGS
        bc[c4d.DESC_MIN]       = 3
        bc[c4d.DESC_MAX]       = 16
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 16
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_VERTEX_SEGS, c4d.DTYPE_LONG, 0)),
            bc, gid_vis
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Показать ячейки (C)"
        bc[c4d.DESC_DEFAULT] = DEFAULT_SHOW_CELLS
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TS_SHOW_CELLS, c4d.DTYPE_BOOL, 0)),
            bc, gid_vis
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  Иконка (программно сгенерированная — гиперкуб)
# ══════════════════════════════════════════════════════════════════════════════



_ICON_TC = (
    "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"
)

def _make_icon_tc():
    png_data = base64.b64decode(_ICON_TC)
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

ICO_TS = _make_icon_tc()


# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_TESSERACT,
        str         = NAME_TESSERACT,
        g           = TesseractObject,
        description = "Obase",
        icon        = ICO_TS,
        info        = c4d.OBJECT_GENERATOR,
    )
