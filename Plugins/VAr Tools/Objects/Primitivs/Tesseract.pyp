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
  • Глубинная подсветка (color by depth)
  • Фонг-сглаживание
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
NAME_TESSERACT = "Tesseract v1.1"

# ══════════════════════════════════════════════════════════════════════════════
#  UserData SubID — строго фиксированы
# ══════════════════════════════════════════════════════════════════════════════

# Группа «Основные»
UD_G_CORE    = 1
TS_SIZE      = 2    # размер гиперкуба (float)
TS_PROJ_DIST = 3    # расстояние проекции (float)
TS_DISPLAY   = 4    # режим отображения (cycle)

# Группа «Поворот 4D»
UD_G_ROT     = 5
TS_ROT_XY    = 6    # угол поворота XY (float, °)
TS_ROT_XZ    = 7    # угол поворота XZ (float, °)
TS_ROT_XW    = 8    # угол поворота XW (float, °)
TS_ROT_YZ    = 9    # угол поворота YZ (float, °)
TS_ROT_YW    = 10   # угол поворота YW (float, °)
TS_ROT_ZW    = 11   # угол поворота ZW (float, °)

# Группа «Автовращение»
UD_G_ANIM    = 12
TS_AUTO_ROT  = 13   # галочка авто-вращения
TS_SPEED_XY  = 14   # скорость XY
TS_SPEED_XZ  = 15
TS_SPEED_XW  = 16
TS_SPEED_YZ  = 17
TS_SPEED_YW  = 18
TS_SPEED_ZW  = 19
TS_ANIM_PHASE = 20  # фаза (для анимации извне)

# Группа «Визуал»
UD_G_VIS     = 21
TS_EDGE_RADIUS = 22  # радиус рёбер-трубок (float)
TS_EDGE_SEGS   = 23  # сегменты окружности рёбер (int)
TS_VERTEX_RADIUS = 24  # радиус вершин (float)
TS_VERTEX_SEGS   = 25  # сегменты окружности вершин (int)
TS_SHOW_CELLS    = 26  # показывать ячейки (bool)
TS_CELL_ALPHA    = 27  # прозрачность ячеек (float 0..1)
TS_COLOR_DEPTH   = 28  # окраска по глубине (bool)

# Первый параметр данных (проверка инициализации)
TS_FIRST_PARAM = TS_SIZE

# ══════════════════════════════════════════════════════════════════════════════
#  Дефолтные значения
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_SIZE       = 200.0
DEFAULT_PROJ_DIST  = 400.0
DEFAULT_DISPLAY    = 0     # 0=Каркас, 1=Рёбра+Вершины, 2=Ячейки, 3=Всё

DEFAULT_ROT_XY     = 0.0
DEFAULT_ROT_XZ     = 0.0
DEFAULT_ROT_XW     = math.radians(25.0)  # начальный поворот для красоты
DEFAULT_ROT_YZ     = 0.0
DEFAULT_ROT_YW     = math.radians(15.0)  # начальный поворот для красоты
DEFAULT_ROT_ZW     = 0.0

DEFAULT_AUTO_ROT   = False
DEFAULT_SPEED_XY   = 0.3
DEFAULT_SPEED_XZ   = 0.0
DEFAULT_SPEED_XW   = 0.5
DEFAULT_SPEED_YZ   = 0.0
DEFAULT_SPEED_YW   = 0.4
DEFAULT_SPEED_ZW   = 0.0
DEFAULT_ANIM_PHASE = 0.0

DEFAULT_EDGE_RADIUS = 2.0
DEFAULT_EDGE_SEGS   = 4
DEFAULT_VERTEX_RADIUS = 5.0
DEFAULT_VERTEX_SEGS   = 6
DEFAULT_SHOW_CELLS    = False
DEFAULT_CELL_ALPHA    = 0.3
DEFAULT_COLOR_DEPTH   = True

# ══════════════════════════════════════════════════════════════════════════════
#  UserData helpers
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


def _make_quad_face(indices_3d, all_pts, all_polys):
    """Добавляет 4-угольный полигон по 4 индексам 3D-точек."""
    if len(indices_3d) == 4:
        all_polys.append(c4d.CPolygon(*indices_3d))


def _add_phong_tag(obj, angle_deg=45.0):
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
        tag[c4d.PHONGTAG_PHONG_ANGLE]      = math.radians(angle_deg)
        tag[c4d.PHONGTAG_PHONG_USEEDGES]   = True


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор тессеракта
# ══════════════════════════════════════════════════════════════════════════════

def _build_tesseract(op):
    """Строит тессеракт и возвращает иерархию объектов (Null-контейнер)."""

    # ── Параметры ────────────────────────────────────────────────────────
    size        = max(10.0, float(_ud_get(op, TS_SIZE, DEFAULT_SIZE)))
    proj_dist   = max(50.0, float(_ud_get(op, TS_PROJ_DIST, DEFAULT_PROJ_DIST)))
    display     = int(_ud_get(op, TS_DISPLAY, DEFAULT_DISPLAY))

    rot_xy = float(_ud_get(op, TS_ROT_XY, DEFAULT_ROT_XY))
    rot_xz = float(_ud_get(op, TS_ROT_XZ, DEFAULT_ROT_XZ))
    rot_xw = float(_ud_get(op, TS_ROT_XW, DEFAULT_ROT_XW))
    rot_yz = float(_ud_get(op, TS_ROT_YZ, DEFAULT_ROT_YZ))
    rot_yw = float(_ud_get(op, TS_ROT_YW, DEFAULT_ROT_YW))
    rot_zw = float(_ud_get(op, TS_ROT_ZW, DEFAULT_ROT_ZW))

    auto_rot   = bool(_ud_get(op, TS_AUTO_ROT, DEFAULT_AUTO_ROT))
    speed_xy   = float(_ud_get(op, TS_SPEED_XY, DEFAULT_SPEED_XY))
    speed_xz   = float(_ud_get(op, TS_SPEED_XZ, DEFAULT_SPEED_XZ))
    speed_xw   = float(_ud_get(op, TS_SPEED_XW, DEFAULT_SPEED_XW))
    speed_yz   = float(_ud_get(op, TS_SPEED_YZ, DEFAULT_SPEED_YZ))
    speed_yw   = float(_ud_get(op, TS_SPEED_YW, DEFAULT_SPEED_YW))
    speed_zw   = float(_ud_get(op, TS_SPEED_ZW, DEFAULT_SPEED_ZW))
    phase      = float(_ud_get(op, TS_ANIM_PHASE, DEFAULT_ANIM_PHASE))

    edge_r     = max(0.5, float(_ud_get(op, TS_EDGE_RADIUS, DEFAULT_EDGE_RADIUS)))
    edge_segs  = max(3, int(_ud_get(op, TS_EDGE_SEGS, DEFAULT_EDGE_SEGS)))
    vert_r     = max(1.0, float(_ud_get(op, TS_VERTEX_RADIUS, DEFAULT_VERTEX_RADIUS)))
    vert_segs  = max(3, int(_ud_get(op, TS_VERTEX_SEGS, DEFAULT_VERTEX_SEGS)))
    show_cells = bool(_ud_get(op, TS_SHOW_CELLS, DEFAULT_SHOW_CELLS))
    cell_alpha = max(0.0, min(1.0, float(_ud_get(op, TS_CELL_ALPHA, DEFAULT_CELL_ALPHA))))
    color_depth = bool(_ud_get(op, TS_COLOR_DEPTH, DEFAULT_COLOR_DEPTH))

    # ── Автовращение: добавляем фазу к углам ────────────────────────────
    if auto_rot:
        doc = op.GetDocument()
        if doc:
            t = doc.GetTime().Get()
        else:
            t = 0.0
        rot_xy += speed_xy * t
        rot_xz += speed_xz * t
        rot_xw += speed_xw * t
        rot_yz += speed_yz * t
        rot_yw += speed_yw * t
        rot_zw += speed_zw * t

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
                v_obj.InsertUnder(root)

    # ── Ячейки (грани кубов) ────────────────────────────────────────────
    if show_cells_mesh:
        for cell_idx, cell_verts in enumerate(_TESS_CELLS):
            cell_pts_3d = [verts_3d[vi] for vi in cell_verts]
            cell_pt_indices = list(range(len(cell_pts_3d)))

            # Грань — 24 квадрата, каждый строим как полигон
            # Индексы cell_verts: 8 вершин куба
            # Грани куба: пары вершин, differing in 1 bit (within the cell subset)
            cell_polys = []
            for bi in range(3):
                for bval in (0, 1):
                    face = []
                    for ci, vi in enumerate(cell_verts):
                        if ((vi >> bi) & 1) == bval:
                            face.append(ci)
                    if len(face) == 4:
                        # Сортируем вершины квадрата по углу вокруг нормали
                        cx = sum(cell_pts_3d[f][0] for f in face) / 4.0
                        cy = sum(cell_pts_3d[f][1] for f in face) / 4.0
                        cz = sum(cell_pts_3d[f][2] for f in face) / 4.0
                        def _sort_key(fi, _cx=cx, _cy=cy, _cz=cz):
                            p = cell_pts_3d[fi]
                            return math.atan2(p[1]-_cy, p[0]-_cx)
                        face.sort(key=_sort_key)
                        cell_polys.append(c4d.CPolygon(face[0], face[1], face[2], face[3]))

            if cell_pts_3d and cell_polys:
                c_obj = c4d.PolygonObject(len(cell_pts_3d), len(cell_polys))
                c_obj.SetName("Cell_%d" % cell_idx)
                for i, p in enumerate(cell_pts_3d):
                    c_obj.SetPoint(i, c4d.Vector(p[0], p[1], p[2]))
                for i, pl in enumerate(cell_polys):
                    c_obj.SetPolygon(i, pl)
                c_obj.Message(c4d.MSG_UPDATE)

                _add_phong_tag(c_obj, 80.0)
                c_obj.InsertUnder(root)

    return root


# ══════════════════════════════════════════════════════════════════════════════
#  UserData: создание интерфейса
# ══════════════════════════════════════════════════════════════════════════════

def _create_userdata(op):
    # SubID=1 → «Основные»
    g_core = _add_group(op, "Основные")
    _add_in_group(op, g_core, _float_bc(
        "Размер", DEFAULT_SIZE, 10.0, 5000.0))
    _add_in_group(op, g_core, _float_bc(
        "Расстояние проекции", DEFAULT_PROJ_DIST, 50.0, 10000.0))
    _add_in_group(op, g_core, _cycle_bc(
        "Отображение", DEFAULT_DISPLAY,
        ["Каркас", "Рёбра + Вершины", "Ячейки", "Всё"]))

    # SubID=5 → «Поворот 4D»
    # Все значения min/max/step в радианах (DESC_UNIT_DEGREE хранит радианы)
    g_rot = _add_group(op, "Поворот 4D")
    _add_in_group(op, g_rot, _float_bc(
        "Поворот XY", DEFAULT_ROT_XY,
        math.radians(-360.0), math.radians(360.0),
        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))
    _add_in_group(op, g_rot, _float_bc(
        "Поворот XZ", DEFAULT_ROT_XZ,
        math.radians(-360.0), math.radians(360.0),
        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))
    _add_in_group(op, g_rot, _float_bc(
        "Поворот XW", DEFAULT_ROT_XW,
        math.radians(-360.0), math.radians(360.0),
        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))
    _add_in_group(op, g_rot, _float_bc(
        "Поворот YZ", DEFAULT_ROT_YZ,
        math.radians(-360.0), math.radians(360.0),
        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))
    _add_in_group(op, g_rot, _float_bc(
        "Поворот YW", DEFAULT_ROT_YW,
        math.radians(-360.0), math.radians(360.0),
        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))
    _add_in_group(op, g_rot, _float_bc(
        "Поворот ZW", DEFAULT_ROT_ZW,
        math.radians(-360.0), math.radians(360.0),
        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))

    # SubID=12 → «Автовращение»
    g_anim = _add_group(op, "Автовращение")
    _add_in_group(op, g_anim, _bool_bc(
        "Включить", DEFAULT_AUTO_ROT))
    _add_in_group(op, g_anim, _float_bc(
        "Скорость XY", DEFAULT_SPEED_XY, -5.0, 5.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_anim, _float_bc(
        "Скорость XZ", DEFAULT_SPEED_XZ, -5.0, 5.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_anim, _float_bc(
        "Скорость XW", DEFAULT_SPEED_XW, -5.0, 5.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_anim, _float_bc(
        "Скорость YZ", DEFAULT_SPEED_YZ, -5.0, 5.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_anim, _float_bc(
        "Скорость YW", DEFAULT_SPEED_YW, -5.0, 5.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_anim, _float_bc(
        "Скорость ZW", DEFAULT_SPEED_ZW, -5.0, 5.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.1))
    _add_in_group(op, g_anim, _float_bc(
        "Фаза", DEFAULT_ANIM_PHASE, -10000.0, 10000.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.01))

    # SubID=21 → «Визуал»
    g_vis = _add_group(op, "Визуал")
    _add_in_group(op, g_vis, _float_bc(
        "Радиус рёбер", DEFAULT_EDGE_RADIUS, 0.1, 100.0))
    _add_in_group(op, g_vis, _int_bc(
        "Сегменты рёбер", DEFAULT_EDGE_SEGS, 3, 16))
    _add_in_group(op, g_vis, _float_bc(
        "Радиус вершин", DEFAULT_VERTEX_RADIUS, 0.1, 200.0))
    _add_in_group(op, g_vis, _int_bc(
        "Сегменты вершин", DEFAULT_VERTEX_SEGS, 3, 16))
    _add_in_group(op, g_vis, _bool_bc(
        "Показать ячейки", DEFAULT_SHOW_CELLS))
    _add_in_group(op, g_vis, _float_bc(
        "Прозрачность ячеек", DEFAULT_CELL_ALPHA, 0.0, 1.0,
        unit=c4d.DESC_UNIT_FLOAT, step=0.05))
    _add_in_group(op, g_vis, _bool_bc(
        "Цвет по глубине", DEFAULT_COLOR_DEPTH))


def _set_defaults(op):
    _ud_set(op, TS_SIZE,        DEFAULT_SIZE)
    _ud_set(op, TS_PROJ_DIST,   DEFAULT_PROJ_DIST)
    _ud_set(op, TS_DISPLAY,     DEFAULT_DISPLAY)

    _ud_set(op, TS_ROT_XY,      DEFAULT_ROT_XY)
    _ud_set(op, TS_ROT_XZ,      DEFAULT_ROT_XZ)
    _ud_set(op, TS_ROT_XW,      DEFAULT_ROT_XW)
    _ud_set(op, TS_ROT_YZ,      DEFAULT_ROT_YZ)
    _ud_set(op, TS_ROT_YW,      DEFAULT_ROT_YW)
    _ud_set(op, TS_ROT_ZW,      DEFAULT_ROT_ZW)

    _ud_set(op, TS_AUTO_ROT,    DEFAULT_AUTO_ROT)
    _ud_set(op, TS_SPEED_XY,    DEFAULT_SPEED_XY)
    _ud_set(op, TS_SPEED_XZ,    DEFAULT_SPEED_XZ)
    _ud_set(op, TS_SPEED_XW,    DEFAULT_SPEED_XW)
    _ud_set(op, TS_SPEED_YZ,    DEFAULT_SPEED_YZ)
    _ud_set(op, TS_SPEED_YW,    DEFAULT_SPEED_YW)
    _ud_set(op, TS_SPEED_ZW,    DEFAULT_SPEED_ZW)
    _ud_set(op, TS_ANIM_PHASE,  DEFAULT_ANIM_PHASE)

    _ud_set(op, TS_EDGE_RADIUS,   DEFAULT_EDGE_RADIUS)
    _ud_set(op, TS_EDGE_SEGS,     DEFAULT_EDGE_SEGS)
    _ud_set(op, TS_VERTEX_RADIUS, DEFAULT_VERTEX_RADIUS)
    _ud_set(op, TS_VERTEX_SEGS,   DEFAULT_VERTEX_SEGS)
    _ud_set(op, TS_SHOW_CELLS,    DEFAULT_SHOW_CELLS)
    _ud_set(op, TS_CELL_ALPHA,    DEFAULT_CELL_ALPHA)
    _ud_set(op, TS_COLOR_DEPTH,   DEFAULT_COLOR_DEPTH)


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin class
# ══════════════════════════════════════════════════════════════════════════════

class TesseractObject(c4d.plugins.ObjectData):
    """Генератор тессеракта (4D гиперкуб) с проекцией в 3D."""

    OBJECT_NAME = "Tesseract"

    def _ensure_ud(self, op):
        if not _ud_exists(op, TS_FIRST_PARAM):
            _create_userdata(op)
            _set_defaults(op)

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
        self._ensure_ud(op)
        return True

    def GetVirtualObjects(self, op, hh):
        self._ensure_ud(op)
        return _build_tesseract(op)

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
#  Иконка (программно сгенерированная — гиперкуб)
# ══════════════════════════════════════════════════════════════════════════════

def _create_icon():
    """Создаёт простую иконку — куб с проекцией тессеракта."""
    size = 128
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.Init(size, size, 24)

    # Тёмный фон
    for y in range(size):
        for x in range(size):
            bmp.SetPixel(x, y, 20, 22, 30)

    # Упрощённая проекция тессеракта (8 вершин → 2D)
    cx, cy = 64, 64
    s = 35
    # Внешний куб
    outer = [(-1,-1,-1), (1,-1,-1), (1,1,-1), (-1,1,-1),
             (-1,-1,1), (1,-1,1), (1,1,1), (-1,1,1)]
    # Внутренний куб (проекция)
    inner = [(-0.5,-0.5,-0.5), (0.5,-0.5,-0.5), (0.5,0.5,-0.5), (-0.5,0.5,-0.5),
             (-0.5,-0.5,0.5), (0.5,-0.5,0.5), (0.5,0.5,0.5), (-0.5,0.5,0.5)]

    def proj(p):
        return (cx + int(p[0]*s + p[2]*s*0.3), cy + int(p[1]*s - p[2]*s*0.2))

    edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]

    # Рисуем линии (упрощённо — пикселями)
    def draw_line(x0, y0, x1, y1, r, g, b, w=1):
        steps = max(abs(x1-x0), abs(y1-y0), 1)
        for t in range(steps + 1):
            f = t / steps
            px = int(x0 + (x1-x0)*f)
            py = int(y0 + (y1-y0)*f)
            for dy in range(-w//2, w//2+1):
                for dx in range(-w//2, w//2+1):
                    nx, ny = px+dx, py+dy
                    if 0 <= nx < size and 0 <= ny < size:
                        bmp.SetPixel(nx, ny, r, g, b)

    for a, b_ in edges:
        p0 = proj(outer[a])
        p1 = proj(outer[b_])
        draw_line(p0[0], p0[1], p1[0], p1[1], 80, 140, 220, 1)
        p0 = proj(inner[a])
        p1 = proj(inner[b_])
        draw_line(p0[0], p0[1], p1[0], p1[1], 120, 180, 255, 1)
    # Соединения внутрь-наружу
    for i in range(8):
        p0 = proj(outer[i])
        p1 = proj(inner[i])
        draw_line(p0[0], p0[1], p1[0], p1[1], 60, 100, 160, 1)

    return bmp


ICO_TS = _create_icon()


# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_TESSERACT,
        str         = NAME_TESSERACT,
        g           = TesseractObject,
        description = "",
        icon        = ICO_TS,
        info        = c4d.OBJECT_GENERATOR,
    )
