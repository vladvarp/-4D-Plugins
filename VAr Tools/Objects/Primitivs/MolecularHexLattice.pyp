# -*- coding: utf-8 -*-
"""
MolecularHexLattice — Cinema 4D ObjectData Plugin v1.0
=======================================================
Генератор молекулярных связей:
  • Узлы — гексагональные шары (dual icosphere) с удалёнными гексагонами
    в местах подключения трубок
  • Трубки — цилиндры, строго стыкующиеся к отверстиям в шарах
  • Фаска на стыке шар↔трубка с регулируемым размером и подразделением
  • Регулировка каркаса по X/Y/Z, плотности узлов, плотности связей, seed
  • «Strip» — плавное смещение узлов по синусоиде без разрыва трубок
  • Материальные теги: M — шары, T — трубки, F — фаски
  • Фонг-сглаживание 45° на всех объектах
  • Уникальная иконка (генерируется программно)

UserData SubID MAP (строго фиксировано):
  SubID=1  : g_lat (группа «Каркас»)
  SubID=2  : ML_SIZE_X
  SubID=3  : ML_SIZE_Y
  SubID=4  : ML_SIZE_Z
  SubID=5  : ML_DENSITY
  SubID=6  : ML_BOND_DENS
  SubID=7  : ML_SEED
  SubID=8  : ML_JITTER
  SubID=9  : g_strip (группа «Strip»)
  SubID=10 : ML_STRIP_AMP
  SubID=11 : ML_STRIP_FREQ
  SubID=12 : ML_STRIP_PHASE
  SubID=13 : ML_STRIP_AXIS
  SubID=14 : g_sph (группа «Шары»)
  SubID=15 : ML_SPHERE_RADIUS
  SubID=16 : ML_SPHERE_SUBDIV
  SubID=24 : ML_SPHERE_PHONG
  SubID=17 : g_tub (группа «Трубки»)
  SubID=18 : ML_TUBE_RADIUS
  SubID=19 : ML_TUBE_SEGS_R
  SubID=20 : ML_TUBE_SEGS_H
  SubID=21 : g_bev (группа «Фаска»)
  SubID=22 : ML_BEVEL_SIZE
  SubID=23 : ML_BEVEL_SUBDIV
  SubID=24 : ML_SPHERE_PHONG
"""

import c4d
import math
import random
import os
import base64
import tempfile
import struct
import zlib


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin ID & Name
# ══════════════════════════════════════════════════════════════════════════════

ID_MOLHEXLATTICE  = 1068899
NAME_MOLHEXLATTICE = "MolecularHexLattice v1.9"

# ══════════════════════════════════════════════════════════════════════════════
#  UserData SubID — СТРОГО совпадают с порядком вызовов AddUserData
# ══════════════════════════════════════════════════════════════════════════════

# Группы (занимают SubID наравне с полями)
UD_G_LAT    = 1    # группа «Каркас»
ML_SIZE_X   = 2
ML_SIZE_Y   = 3
ML_SIZE_Z   = 4
ML_DENSITY  = 5
ML_BOND_DENS = 6
ML_SEED     = 7
ML_JITTER   = 8

UD_G_STRIP  = 9    # группа «Strip»
ML_STRIP_AMP   = 10
ML_STRIP_FREQ  = 11
ML_STRIP_PHASE = 12
ML_STRIP_AXIS  = 13

UD_G_SPH    = 14   # группа «Шары»
ML_SPHERE_RADIUS = 15
ML_SPHERE_SUBDIV = 16

UD_G_TUB    = 17   # группа «Трубки»
ML_TUBE_RADIUS  = 18
ML_TUBE_SEGS_R  = 19
ML_TUBE_SEGS_H  = 20

UD_G_BEV    = 21   # группа «Фаска»
ML_BEVEL_SIZE   = 22
ML_BEVEL_SUBDIV = 23

ML_SPHERE_PHONG = 24   # угол фонг-сглаживания шаров (градусы)
ML_HIDE_ISOLATED = 25  # галочка «Скрывать одиночные шары (без связей)»

# Первый «настоящий» параметр данных (используется для проверки инициализации)
ML_FIRST_PARAM = ML_SIZE_X  # SubID=2

# ══════════════════════════════════════════════════════════════════════════════
#  Дефолтные значения параметров
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_SIZE_X        = 401.0
DEFAULT_SIZE_Y        = 401.0
DEFAULT_SIZE_Z        = 401.0
DEFAULT_DENSITY       = 200.0
DEFAULT_BOND_DENS     = 250.0
DEFAULT_SEED          = 0
DEFAULT_JITTER        = 0

DEFAULT_STRIP_AMP     = 0.0
DEFAULT_STRIP_FREQ    = 0.01
DEFAULT_STRIP_PHASE   = 0.0
DEFAULT_STRIP_AXIS    = 1

DEFAULT_SPHERE_RADIUS = 35.0
DEFAULT_SPHERE_SUBDIV = 1
DEFAULT_SPHERE_PHONG  = math.radians(0.0)   # в радианах (единица хранения C4D)

DEFAULT_TUBE_RADIUS   = 6.0
DEFAULT_TUBE_SEGS_R   = 9
DEFAULT_TUBE_SEGS_H   = 2

DEFAULT_BEVEL_SIZE    = 3.0
DEFAULT_BEVEL_SUBDIV  = 0

DEFAULT_HIDE_ISOLATED = True  # галочка «Скрывать одиночные шары»

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
    """Добавляет корневую группу UserData. Возвращает SubID группы."""
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_TITLEBAR]   = 1
    bc[c4d.DESC_DEFAULT]    = 1
    did = op.AddUserData(bc)
    return did[1].id


def _add_in_group(op, grp_subid, bc):
    """Добавляет элемент UserData внутрь группы с данным SubID."""
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


def _bool_bc(name, default):
    """Чекбокс (Bool) для UserData."""
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BOOL)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


# ══════════════════════════════════════════════════════════════════════════════
#  Математика
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_tuple(v):
    d = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if d < 1e-12:
        return (v[0], v[1], v[2])
    return (v[0]/d, v[1]/d, v[2]/d)


def _midpoint_sphere(a, b):
    return _normalize_tuple(((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2))


def _v3_normalize(v):
    d = math.sqrt(v.x**2 + v.y**2 + v.z**2)
    if d < 1e-12:
        return c4d.Vector(0, 1, 0)
    return c4d.Vector(v.x/d, v.y/d, v.z/d)


def _v3_len(v):
    return math.sqrt(v.x**2 + v.y**2 + v.z**2)


def _v3_dot(a, b):
    return a.x*b.x + a.y*b.y + a.z*b.z


def _v3_cross(a, b):
    return c4d.Vector(
        a.y*b.z - a.z*b.y,
        a.z*b.x - a.x*b.z,
        a.x*b.y - a.y*b.x
    )


def _v3_lerp(a, b, t):
    return c4d.Vector(
        a.x + (b.x - a.x)*t,
        a.y + (b.y - a.y)*t,
        a.z + (b.z - a.z)*t
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Dual Icosphere
# ══════════════════════════════════════════════════════════════════════════════

def _icosphere_tris(subdivisions):
    """Икосаэдр с midpoint-подразделением. Возвращает (verts, faces)."""
    PHI = (1.0 + math.sqrt(5.0)) / 2.0
    raw = [
        ( 0,  1,  PHI), ( 0, -1,  PHI), ( 0,  1, -PHI), ( 0, -1, -PHI),
        ( 1,  PHI, 0),  (-1,  PHI, 0),  ( 1, -PHI, 0),  (-1, -PHI, 0),
        ( PHI, 0,  1),  (-PHI, 0,  1),  ( PHI, 0, -1),  (-PHI, 0, -1),
    ]
    verts = [list(_normalize_tuple(v)) for v in raw]
    faces = [
        [0,1,8],  [0,8,4],  [0,4,5],  [0,5,9],  [0,9,1],
        [1,6,8],  [8,6,10], [8,10,4], [4,10,2],  [4,2,5],
        [5,2,11], [5,11,9], [9,11,7], [9,7,1],   [1,7,6],
        [3,6,7],  [3,7,11], [3,11,2], [3,2,10],  [3,10,6],
    ]
    for _ in range(subdivisions):
        new_faces  = []
        edge_cache = {}

        def get_mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in edge_cache:
                edge_cache[key] = len(verts)
                verts.append(list(_midpoint_sphere(verts[a], verts[b])))
            return edge_cache[key]

        for f in faces:
            a, b, c = f[0], f[1], f[2]
            ab = get_mid(a, b)
            bc = get_mid(b, c)
            ca = get_mid(c, a)
            new_faces += [[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]]
        faces = new_faces
    return verts, faces


def _dual_mesh(ico_verts, ico_faces):
    """
    Dual mesh треугольной сетки.
    Центры треугольников становятся вершинами dual_polys (гексагонов/пятиугольников).
    """
    n_verts = len(ico_verts)
    dual_verts = []
    for f in ico_faces:
        cx = (ico_verts[f[0]][0] + ico_verts[f[1]][0] + ico_verts[f[2]][0]) / 3.0
        cy = (ico_verts[f[0]][1] + ico_verts[f[1]][1] + ico_verts[f[2]][1]) / 3.0
        cz = (ico_verts[f[0]][2] + ico_verts[f[1]][2] + ico_verts[f[2]][2]) / 3.0
        dual_verts.append(list(_normalize_tuple((cx, cy, cz))))

    vert_to_faces = [[] for _ in range(n_verts)]
    for fi, f in enumerate(ico_faces):
        for vi in f:
            vert_to_faces[vi].append(fi)

    dual_polys     = []
    face_normals   = []   # unit-вектор «наружу» для каждого полигона

    for vi in range(n_verts):
        adj = vert_to_faces[vi]
        if len(adj) < 3:
            continue

        # Нормаль полигона = направление ico-вершины (она на сфере)
        nx, ny, nz = ico_verts[vi]

        # Касательная система для сортировки по углу
        if abs(nx) < 0.9:
            tx, ty, tz = 1.0, 0.0, 0.0
        else:
            tx, ty, tz = 0.0, 1.0, 0.0
        dot = tx*nx + ty*ny + tz*nz
        tx -= dot*nx; ty -= dot*ny; tz -= dot*nz
        td = math.sqrt(tx**2 + ty**2 + tz**2)
        tx /= td; ty /= td; tz /= td
        bx = ny*tz - nz*ty
        by = nz*tx - nx*tz
        bz = nx*ty - ny*tx

        def _angle(fi, _nx=nx,_ny=ny,_nz=nz,_tx=tx,_ty=ty,_tz=tz,_bx=bx,_by=by,_bz=bz):
            dvx = dual_verts[fi][0] - _nx
            dvy = dual_verts[fi][1] - _ny
            dvz = dual_verts[fi][2] - _nz
            u = dvx*_tx + dvy*_ty + dvz*_tz
            v = dvx*_bx + dvy*_by + dvz*_bz
            return math.atan2(v, u)

        ordered = sorted(adj, key=_angle)

        # Проверяем ориентацию нормали (должна смотреть наружу)
        p0 = c4d.Vector(*dual_verts[ordered[0]])
        p1 = c4d.Vector(*dual_verts[ordered[1]])
        p2 = c4d.Vector(*dual_verts[ordered[2]])
        normal = (p1 - p0).Cross(p2 - p0)
        centroid = c4d.Vector()
        for idx in ordered:
            centroid += c4d.Vector(*dual_verts[idx])
        centroid /= float(len(ordered))
        if normal.Dot(centroid) < 0.0:
            ordered = list(reversed(ordered))

        dual_polys.append(ordered)
        face_normals.append((nx, ny, nz))

    return dual_verts, dual_polys, face_normals


def _build_hex_sphere_data(radius, subdivisions):
    """
    Возвращает (sphere_pts, dual_polys, face_normals_unit, dual_verts_unit).
    sphere_pts       — c4d.Vector на сфере (масштабированы на radius)
    dual_polys       — индексные списки (гексагоны/пятиугольники)
    face_normals     — unit-нормали каждой грани (направление наружу)
    dual_verts_unit  — нормализованные координаты вершин dual mesh
    """
    subdivisions = max(1, min(4, int(subdivisions)))
    ico_verts, ico_faces = _icosphere_tris(subdivisions)
    dual_verts, dual_polys, face_normals = _dual_mesh(ico_verts, ico_faces)
    sphere_pts = [c4d.Vector(v[0]*radius, v[1]*radius, v[2]*radius)
                  for v in dual_verts]
    return sphere_pts, dual_polys, face_normals, dual_verts


# ══════════════════════════════════════════════════════════════════════════════
#  Phong-тег
# ══════════════════════════════════════════════════════════════════════════════

def _add_phong_tag(obj, angle_deg=45.0):
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
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
#  Гексагональная сфера — цельная, полигоны не удаляются
# ══════════════════════════════════════════════════════════════════════════════

def _fan_triangulate(indices, pts):
    """N-гон → список c4d.CPolygon.
    Для n==3,4 — стандартная триангуляция.
    Для n>=5 (пятиугольники, гексагоны) — через центральную вершину (звезда):
    центральная точка добавляется в pts, её индекс = len(pts) перед вызовом.
    Возвращает список CPolygon; для n>=5 pts расширяется на 1 элемент (центр).
    """
    n = len(indices)
    if n == 3:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[2])]
    if n == 4:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[3])]
    # n >= 5: вычисляем центральную точку грани и добавляем в pts
    cx = sum(pts[idx].x for idx in indices) / n
    cy = sum(pts[idx].y for idx in indices) / n
    cz = sum(pts[idx].z for idx in indices) / n
    center_idx = len(pts)
    pts.append(c4d.Vector(cx, cy, cz))
    # Каждый треугольник: центр + два соседних периметральных угла
    result = []
    for k in range(n):
        a = indices[k]
        b = indices[(k + 1) % n]
        result.append(c4d.CPolygon(center_idx, a, b, b))
    return result


def _build_sphere_with_holes(radius, subdivisions, hole_face_indices, phong_angle=45.0):
    """
    Строит цельную dual icosphere — полигоны НЕ удаляются.
    Зазор между шаром и трубкой закрывается фаской с цилиндрической экструзией.

    Возвращает:
      (PolygonObject, hole_centers, hole_normals)
      hole_centers — c4d.Vector точек на поверхности сферы (центры граней связей)
      hole_normals — unit c4d.Vector нормалей этих граней (наружу)
    """
    sphere_pts, dual_polys, face_normals, dual_verts_unit = \
        _build_hex_sphere_data(radius, subdivisions)

    pts    = list(sphere_pts)
    cpols  = []
    hidden = []

    # Центры и нормали граней связей — нужны для позиционирования фасок
    hole_centers = []
    hole_normals = []

    for fi, poly_idx_list in enumerate(dual_polys):
        if fi in set(hole_face_indices):
            # Вычисляем центр грани на поверхности сферы (для фаски)
            cx = cy = cz = 0.0
            for idx in poly_idx_list:
                cx += pts[idx].x
                cy += pts[idx].y
                cz += pts[idx].z
            n_p = len(poly_idx_list)
            cx /= n_p; cy /= n_p; cz /= n_p
            hole_centers.append(c4d.Vector(cx, cy, cz))
            hole_normals.append(c4d.Vector(*face_normals[fi]))
            # Полигон НЕ пропускаем — шар остаётся цельным

        start = len(cpols)
        new_cps = _fan_triangulate(poly_idx_list, pts)
        cpols.extend(new_cps)

        # Для звёздной триангуляции (n>=5) — все внутренние рёбра скрыты
        # (рёбра от центра к вершинам периметра — edge 0 каждого треугольника)
        n = len(poly_idx_list)
        if n > 4:
            for t in range(n):
                pi = start + t
                hidden.append(4 * pi + 0)  # ребро центр→вершина_a

    obj = _make_poly_object(pts, cpols, "MHL_Sphere")

    if hidden:
        eh = obj.GetEdgeH()
        for eid in hidden:
            eh.Select(eid)

    _add_phong_tag(obj, phong_angle)
    return obj, hole_centers, hole_normals


# ══════════════════════════════════════════════════════════════════════════════
#  Матрица поворота: ось Y → direction
# ══════════════════════════════════════════════════════════════════════════════

def _matrix_y_to_dir(direction):
    """
    Строит c4d.Matrix, выравнивающую ось Y объекта вдоль direction.
    Используется для позиционирования трубок и фасок.
    """
    up = _v3_normalize(direction)

    # Выбираем вспомогательный вектор, не параллельный up
    helper = c4d.Vector(0, 0, 1)
    if abs(_v3_dot(up, helper)) > 0.99:
        helper = c4d.Vector(1, 0, 0)

    right  = _v3_normalize(_v3_cross(helper, up))
    fwd    = _v3_normalize(_v3_cross(up, right))

    # c4d.Matrix(off, v1, v2, v3): v1=X, v2=Y, v3=Z
    mg = c4d.Matrix()
    mg.v1 = right
    mg.v2 = up
    mg.v3 = fwd
    mg.off = c4d.Vector(0, 0, 0)
    return mg


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор трубки (основной цилиндр + фаски на концах)
# ══════════════════════════════════════════════════════════════════════════════

def _build_tube_between(pt_a, pt_b, tube_radius, segs_r, segs_h,
                         bevel_size, bevel_subdiv):
    """
    Строит трубку от pt_a до pt_b.
    Трубка позиционируется и ориентируется в мировом пространстве.

    Возвращает (tube_obj, bevel_list):
      tube_obj   — PolygonObject основного цилиндра
      bevel_list — список PolygonObject фасок (0, 1 или 2 штуки)
    """
    diff   = pt_b - pt_a
    length = _v3_len(diff)
    if length < 1e-6:
        return None, []

    direction = _v3_normalize(diff)
    midpoint  = _v3_lerp(pt_a, pt_b, 0.5)

    segs_r       = max(3,   int(segs_r))
    segs_h       = max(1,   int(segs_h))
    bevel_subdiv = max(0,   int(bevel_subdiv))
    bevel_size   = max(0.0, float(bevel_size))

    # Фаска не может превышать половину длины трубки
    actual_bevel = min(bevel_size, length * 0.45)
    inner_half   = length * 0.5 - actual_bevel

    # ── Основной цилиндр ────────────────────────────────────────────────────
    tube_pts   = []
    tube_cpols = []

    for row in range(segs_h + 1):
        t = row / segs_h
        y = -inner_half + t * (inner_half * 2.0)
        for col in range(segs_r):
            a = col / segs_r * 2.0 * math.pi
            tube_pts.append(c4d.Vector(
                tube_radius * math.cos(a),
                y,
                tube_radius * math.sin(a)
            ))

    for row in range(segs_h):
        for col in range(segs_r):
            bl = row * segs_r + col
            br = row * segs_r + (col + 1) % segs_r
            tl = (row + 1) * segs_r + col
            tr = (row + 1) * segs_r + (col + 1) % segs_r
            tube_cpols.append(c4d.CPolygon(bl, tl, tr, br))

    tube_obj = _make_poly_object(tube_pts, tube_cpols, "MHL_Tube")
    _add_phong_tag(tube_obj, 45.0)

    mg = _matrix_y_to_dir(direction)
    mg.off = midpoint
    tube_obj.SetMg(mg)

    # ── Фаски ───────────────────────────────────────────────────────────────
    bevel_list = []

    if actual_bevel > 1e-4:
        n_bev = max(1, bevel_subdiv + 1)

        for end_sign in (-1.0, 1.0):
            bev_pts   = []
            bev_cpols = []

            # Профиль фаски (от стыка с трубкой к поверхности шара):
            #   Секция A (кольца 0..n_bev): четверть дуги — радиус растёт
            #     от tube_radius до tube_radius+actual_bevel,
            #     Y идёт от ±inner_half до ±(inner_half + actual_bevel*(1-cos))
            #     → максимальный Y дуги = ±(inner_half + actual_bevel)
            #     (т.е. ровно ±half_length = поверхность шара)
            #   Секция B (кольца n_bev..n_bev+1): прямой цилиндрический выступ
            #     r = tube_radius+actual_bevel, Y идёт ещё на actual_bevel внутрь шара
            #     Это «шип», утопленный в шар — закрывает зазор.
            #
            # Итого n_bev+2 кольца точек, n_bev+1 полос полигонов.

            n_rings = n_bev + 2  # 0..n_bev — дуга, n_bev+1 — конец шипа

            for ring in range(n_rings):
                if ring <= n_bev:
                    # Секция A: четверть окружности (скругление-фаска)
                    t     = ring / n_bev
                    angle = t * math.pi * 0.5   # 0..90°
                    r_ring = tube_radius + actual_bevel * math.sin(angle)
                    y_ring = end_sign * (inner_half + actual_bevel * (1.0 - math.cos(angle)))
                else:
                    # Секция B: прямой цилиндрический выступ в тело шара
                    # r фиксирован = tube_radius+actual_bevel
                    # Y сдвигается ещё на actual_bevel в сторону шара
                    r_ring = tube_radius + actual_bevel
                    y_ring = end_sign * (inner_half + actual_bevel + actual_bevel)

                for col in range(segs_r):
                    a = col / segs_r * 2.0 * math.pi
                    bev_pts.append(c4d.Vector(
                        r_ring * math.cos(a),
                        y_ring,
                        r_ring * math.sin(a)
                    ))

            for ring in range(n_rings - 1):
                for col in range(segs_r):
                    bl = ring * segs_r + col
                    br = ring * segs_r + (col + 1) % segs_r
                    tl = (ring + 1) * segs_r + col
                    tr = (ring + 1) * segs_r + (col + 1) % segs_r
                    # Нижний конец: нормаль смотрит вниз → переставляем порядок
                    if end_sign < 0:
                        bev_cpols.append(c4d.CPolygon(bl, br, tr, tl))
                    else:
                        bev_cpols.append(c4d.CPolygon(bl, tl, tr, br))

            bev_obj = _make_poly_object(bev_pts, bev_cpols, "MHL_Bevel")
            _add_phong_tag(bev_obj, 45.0)
            bev_obj.SetMg(mg)
            bevel_list.append(bev_obj)

    return tube_obj, bevel_list


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор позиций и связей
# ══════════════════════════════════════════════════════════════════════════════

def _generate_positions(size_x, size_y, size_z, density, seed, jitter):
    """Генерирует позиции узлов на решётке + случайный джиттер."""
    rng     = random.Random(int(seed))
    density = max(1.0, float(density))
    nx = max(1, int(math.ceil(size_x / density)))
    ny = max(1, int(math.ceil(size_y / density)))
    nz = max(1, int(math.ceil(size_z / density)))

    positions = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                x = ix * density - size_x * 0.5
                y = iy * density - size_y * 0.5
                z = iz * density - size_z * 0.5
                if jitter > 1e-4:
                    x += rng.uniform(-jitter, jitter)
                    y += rng.uniform(-jitter, jitter)
                    z += rng.uniform(-jitter, jitter)
                positions.append(c4d.Vector(x, y, z))
    return positions


def _apply_strip(positions, amplitude, frequency, phase, axis):
    """
    Плавно смещает позиции синусоидой вдоль перпендикулярного направления.
    Трубки не рвутся, так как пересчитываются при каждом изменении phase.
    """
    if amplitude < 1e-6:
        return positions
    result = []
    for p in positions:
        if axis == 0:        # синусоида вдоль X, смещение по Y
            val = math.sin(p.x * frequency + phase)
            result.append(c4d.Vector(p.x, p.y + amplitude * val, p.z))
        elif axis == 1:      # синусоида вдоль Y, смещение по X
            val = math.sin(p.y * frequency + phase)
            result.append(c4d.Vector(p.x + amplitude * val, p.y, p.z))
        else:                # синусоида вдоль Z, смещение по Y
            val = math.sin(p.z * frequency + phase)
            result.append(c4d.Vector(p.x, p.y + amplitude * val, p.z))
    return result


def _find_bonds(positions, max_dist):
    """Находит все пары узлов на расстоянии ≤ max_dist."""
    bonds  = []
    max_sq = max_dist * max_dist
    n = len(positions)
    for i in range(n):
        for j in range(i + 1, n):
            d  = positions[i] - positions[j]
            sq = d.x**2 + d.y**2 + d.z**2
            if sq <= max_sq:
                bonds.append((i, j))
    return bonds


def _find_best_face(face_normals, direction):
    """
    Возвращает индекс грани dual_sphere, нормаль которой ближе всего
    к direction (unit vector). Используется для выбора места подключения трубки.
    """
    best_idx = 0
    best_dot = -2.0
    dx, dy, dz = direction.x, direction.y, direction.z
    for fi, (nx, ny, nz) in enumerate(face_normals):
        dot = nx*dx + ny*dy + nz*dz
        if dot > best_dot:
            best_dot = dot
            best_idx = fi
    return best_idx


# ══════════════════════════════════════════════════════════════════════════════
#  Теги выделения полигонов (F, T, M)
# ══════════════════════════════════════════════════════════════════════════════

def _apply_selection_tag(obj, selection_name):
    """
    Вешает тег выделения полигонов (Tpolygonselection) с именем selection_name
    (F, T или M) на все полигоны объекта.

    Материал пользователь назначает сам — drag-and-drop на примитив с
    ограничением выделения F, T или M, либо без ограничения (на весь объект).
    """
    n_polys = obj.GetPolygonCount()
    if n_polys == 0:
        return

    tag = obj.MakeTag(c4d.Tpolygonselection)
    if tag is None:
        return

    tag.SetName(selection_name)

    sel = tag.GetBaseSelect()
    # Выделяем все полигоны объекта под данное имя выделения
    for pi in range(n_polys):
        sel.Select(pi)


# ══════════════════════════════════════════════════════════════════════════════
#  Главный генератор
# ══════════════════════════════════════════════════════════════════════════════

def _build_lattice(op):
    """Строит всю молекулярную систему и возвращает нулевой объект-контейнер."""

    # ── Параметры ────────────────────────────────────────────────────────────
    size_x      = max(1.0,  float(_ud_get(op, ML_SIZE_X,       DEFAULT_SIZE_X)))
    size_y      = max(1.0,  float(_ud_get(op, ML_SIZE_Y,       DEFAULT_SIZE_Y)))
    size_z      = max(1.0,  float(_ud_get(op, ML_SIZE_Z,       DEFAULT_SIZE_Z)))
    density     = max(10.0, float(_ud_get(op, ML_DENSITY,      DEFAULT_DENSITY)))
    bond_dens   = max(1.0,  float(_ud_get(op, ML_BOND_DENS,    DEFAULT_BOND_DENS)))
    seed        = int(_ud_get(op, ML_SEED,    DEFAULT_SEED))
    jitter      = max(0.0,  float(_ud_get(op, ML_JITTER,       DEFAULT_JITTER)))

    strip_amp   = max(0.0,   float(_ud_get(op, ML_STRIP_AMP,   DEFAULT_STRIP_AMP)))
    strip_freq  = max(0.0001,float(_ud_get(op, ML_STRIP_FREQ,  DEFAULT_STRIP_FREQ)))
    strip_phase = float(_ud_get(op, ML_STRIP_PHASE, DEFAULT_STRIP_PHASE))
    strip_axis  = int(_ud_get(op, ML_STRIP_AXIS,   DEFAULT_STRIP_AXIS))

    sphere_r    = max(1.0,  float(_ud_get(op, ML_SPHERE_RADIUS, DEFAULT_SPHERE_RADIUS)))
    sphere_sub  = max(1,    min(4, int(_ud_get(op, ML_SPHERE_SUBDIV, DEFAULT_SPHERE_SUBDIV))))

    tube_r      = max(0.5,  float(_ud_get(op, ML_TUBE_RADIUS,   DEFAULT_TUBE_RADIUS)))
    tube_sr     = max(3,    int(_ud_get(op, ML_TUBE_SEGS_R,    DEFAULT_TUBE_SEGS_R)))
    tube_sh     = max(1,    int(_ud_get(op, ML_TUBE_SEGS_H,    DEFAULT_TUBE_SEGS_H)))

    bevel_size  = max(0.0,  float(_ud_get(op, ML_BEVEL_SIZE,    DEFAULT_BEVEL_SIZE)))
    bevel_sub   = max(0,    int(_ud_get(op, ML_BEVEL_SUBDIV,    DEFAULT_BEVEL_SUBDIV)))

    sphere_phong = math.degrees(max(0.0, min(math.radians(180.0), float(_ud_get(op, ML_SPHERE_PHONG, DEFAULT_SPHERE_PHONG)))))

    hide_isolated = bool(_ud_get(op, ML_HIDE_ISOLATED, DEFAULT_HIDE_ISOLATED))

    # ── Позиции узлов ────────────────────────────────────────────────────────
    positions_raw = _generate_positions(size_x, size_y, size_z, density, seed, jitter)

    # Жёсткое ограничение (производительность)
    MAX_NODES = 150
    if len(positions_raw) > MAX_NODES:
        positions_raw = positions_raw[:MAX_NODES]

    positions = _apply_strip(positions_raw, strip_amp, strip_freq, strip_phase, strip_axis)

    if not positions:
        null = c4d.BaseObject(c4d.Onull)
        null.SetName("MolecularHexLattice [пусто]")
        return null

    # ── Связи ────────────────────────────────────────────────────────────────
    bonds = _find_bonds(positions, bond_dens)

    MAX_BONDS = 500
    if len(bonds) > MAX_BONDS:
        bonds = bonds[:MAX_BONDS]

    # ── Данные dual icosphere для определения лучшей грани ───────────────────
    _, _, face_normals, _ = _build_hex_sphere_data(1.0, sphere_sub)
    n_faces = len(face_normals)

    # Для каждого узла: список индексов граней, куда подключены трубки
    node_holes = [[] for _ in range(len(positions))]

    for i, j in bonds:
        dir_ij = _v3_normalize(positions[j] - positions[i])
        dir_ji = _v3_normalize(positions[i] - positions[j])

        fi_ij = _find_best_face(face_normals, dir_ij)
        fi_ji = _find_best_face(face_normals, dir_ji)

        if fi_ij not in node_holes[i]:
            node_holes[i].append(fi_ij)
        if fi_ji not in node_holes[j]:
            node_holes[j].append(fi_ji)

    # ── Фильтр одиночных шаров ───────────────────────────────────────────────
    # Если галочка включена — узлы без единой связи полностью исключаются из генерации.
    # bonds при этом не меняются (они ссылаются на оригинальные индексы через remap).
    if hide_isolated:
        # Множество узлов, участвующих хотя бы в одной связи
        connected = set()
        for i, j in bonds:
            connected.add(i)
            connected.add(j)

        # Таблица переиндексации: старый индекс → новый
        remap = {}
        new_positions  = []
        new_node_holes = []
        for old_idx, pos in enumerate(positions):
            if old_idx in connected:
                remap[old_idx] = len(new_positions)
                new_positions.append(pos)
                new_node_holes.append(node_holes[old_idx])

        positions  = new_positions
        node_holes = new_node_holes
        # Переиндексируем bonds под новые индексы узлов
        bonds = [(remap[i], remap[j]) for i, j in bonds]

    # ── Строим иерархию ──────────────────────────────────────────────────────
    root = c4d.BaseObject(c4d.Onull)
    root.SetName("MolecularHexLattice")

    g_spheres = c4d.BaseObject(c4d.Onull)
    g_spheres.SetName("Spheres")
    g_spheres.InsertUnder(root)

    g_tubes = c4d.BaseObject(c4d.Onull)
    g_tubes.SetName("Tubes")
    g_tubes.InsertUnder(root)

    g_bevels = c4d.BaseObject(c4d.Onull)
    g_bevels.SetName("Bevels")
    g_bevels.InsertUnder(root)

    # ── Шары ─────────────────────────────────────────────────────────────────
    for node_idx, pos in enumerate(positions):
        hole_faces = [f for f in node_holes[node_idx] if f < n_faces]

        sphere_obj, hole_centers, hole_normals = \
            _build_sphere_with_holes(sphere_r, sphere_sub, hole_faces, sphere_phong)

        sphere_obj.SetAbsPos(pos)
        sphere_obj.SetName("Sphere_%03d" % node_idx)
        _apply_selection_tag(sphere_obj, "M")
        sphere_obj.InsertUnder(g_spheres)

    # ── Трубки и фаски ────────────────────────────────────────────────────────
    for bond_idx, (i, j) in enumerate(bonds):
        pi = positions[i]
        pj = positions[j]
        diff   = pj - pi
        length = _v3_len(diff)
        if length < 1e-6:
            continue

        dir_n = _v3_normalize(diff)

        # Точки старта/конца трубки у поверхности шаров
        pt_a = pi + dir_n * sphere_r
        pt_b = pj - dir_n * sphere_r

        tube_len = _v3_len(pt_b - pt_a)
        if tube_len < tube_r * 0.1:
            # Узлы слишком близко — трубка не вмещается
            continue

        tube_obj, bevel_list = _build_tube_between(
            pt_a, pt_b,
            tube_r, tube_sr, tube_sh,
            bevel_size, bevel_sub
        )

        if tube_obj is not None:
            tube_obj.SetName("Tube_%03d" % bond_idx)
            _apply_selection_tag(tube_obj, "T")
            tube_obj.InsertUnder(g_tubes)

        for bv_idx, bev_obj in enumerate(bevel_list):
            bev_obj.SetName("Bevel_%03d_%d" % (bond_idx, bv_idx))
            _apply_selection_tag(bev_obj, "F")
            bev_obj.InsertUnder(g_bevels)

    return root


# ══════════════════════════════════════════════════════════════════════════════
#  UserData: создание интерфейса
# ══════════════════════════════════════════════════════════════════════════════

def _create_userdata(op):
    """
    Создаёт все группы и поля UserData В СТРОГО ФИКСИРОВАННОМ ПОРЯДКЕ.
    SubID назначается автоматически C4D: каждый вызов AddUserData
    даёт следующий свободный SubID (начиная с 1).
    """
    # SubID=1 → g_lat
    g_lat = _add_group(op, "Каркас (Lattice)")
    # SubID=2..8 → поля
    _add_in_group(op, g_lat, _float_bc("Размер X",           DEFAULT_SIZE_X,    10.0, 100000.0))
    _add_in_group(op, g_lat, _float_bc("Размер Y",           DEFAULT_SIZE_Y,    10.0, 100000.0))
    _add_in_group(op, g_lat, _float_bc("Размер Z",           DEFAULT_SIZE_Z,    10.0, 100000.0))
    _add_in_group(op, g_lat, _float_bc("Плотность (шаг сетки)", DEFAULT_DENSITY, 10.0, 10000.0))
    _add_in_group(op, g_lat, _float_bc("Макс. длина связи",  DEFAULT_BOND_DENS, 10.0, 10000.0))
    _add_in_group(op, g_lat, _int_bc  ("Seed",               DEFAULT_SEED,      0,    99999))
    _add_in_group(op, g_lat, _float_bc("Джиттер (шум позиций)", DEFAULT_JITTER, 0.0, 5000.0))

    # SubID=9 → g_strip
    g_strip = _add_group(op, "Strip — волновое смещение")
    # SubID=10..13 → поля
    _add_in_group(op, g_strip, _float_bc("Амплитуда",          DEFAULT_STRIP_AMP,   0.0,    10000.0))
    _add_in_group(op, g_strip, _float_bc("Частота",            DEFAULT_STRIP_FREQ,  0.0001, 10.0,
                                          unit=c4d.DESC_UNIT_FLOAT, step=0.001))
    _add_in_group(op, g_strip, _float_bc("Фаза (анимировать)", DEFAULT_STRIP_PHASE, -1000.0, 1000.0,
                                          unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_strip, _cycle_bc("Ось волны",          DEFAULT_STRIP_AXIS,
                                          ["X (смещение Y)", "Y (смещение X)", "Z (смещение Y)"]))

    # SubID=14 → g_sph
    g_sph = _add_group(op, "Шары  [M]")
    # SubID=15..16, 24
    _add_in_group(op, g_sph, _float_bc("Радиус шара",   DEFAULT_SPHERE_RADIUS, 1.0, 100000.0))
    _add_in_group(op, g_sph, _int_bc  ("Подразделение", DEFAULT_SPHERE_SUBDIV, 1,   4))

    # SubID=17 → g_tub
    g_tub = _add_group(op, "Трубки  [T]")
    # SubID=18..20
    _add_in_group(op, g_tub, _float_bc("Радиус трубки",          DEFAULT_TUBE_RADIUS,  0.5,  100000.0))
    _add_in_group(op, g_tub, _int_bc  ("Сегменты окружности",    DEFAULT_TUBE_SEGS_R,  3,    64))
    _add_in_group(op, g_tub, _int_bc  ("Сегменты длины",         DEFAULT_TUBE_SEGS_H,  1,    64))

    # SubID=21 → g_bev
    g_bev = _add_group(op, "Фаска  [F]")
    # SubID=22..23
    _add_in_group(op, g_bev, _float_bc("Размер фаски",           DEFAULT_BEVEL_SIZE,   0.0,  100000.0))
    _add_in_group(op, g_bev, _int_bc  ("Подразделение фаски",    DEFAULT_BEVEL_SUBDIV, 0,    8))

    # SubID=24 → угол фонг-сглаживания шаров
    _add_in_group(op, g_sph, _float_bc("Фонг шаров (°)",        DEFAULT_SPHERE_PHONG,  0.0,  math.radians(180.0),
                                        unit=c4d.DESC_UNIT_DEGREE, step=math.radians(1.0)))

    # SubID=25 → галочка скрытия одиночных шаров (без связей)
    _add_in_group(op, g_lat, _bool_bc("Скрывать одиночные шары", DEFAULT_HIDE_ISOLATED))


def _set_defaults(op):
    _ud_set(op, ML_SIZE_X,       DEFAULT_SIZE_X)
    _ud_set(op, ML_SIZE_Y,       DEFAULT_SIZE_Y)
    _ud_set(op, ML_SIZE_Z,       DEFAULT_SIZE_Z)
    _ud_set(op, ML_DENSITY,      DEFAULT_DENSITY)
    _ud_set(op, ML_BOND_DENS,    DEFAULT_BOND_DENS)
    _ud_set(op, ML_SEED,         DEFAULT_SEED)
    _ud_set(op, ML_JITTER,       DEFAULT_JITTER)

    _ud_set(op, ML_STRIP_AMP,    DEFAULT_STRIP_AMP)
    _ud_set(op, ML_STRIP_FREQ,   DEFAULT_STRIP_FREQ)
    _ud_set(op, ML_STRIP_PHASE,  DEFAULT_STRIP_PHASE)
    _ud_set(op, ML_STRIP_AXIS,   DEFAULT_STRIP_AXIS)

    _ud_set(op, ML_SPHERE_RADIUS, DEFAULT_SPHERE_RADIUS)
    _ud_set(op, ML_SPHERE_SUBDIV, DEFAULT_SPHERE_SUBDIV)
    _ud_set(op, ML_SPHERE_PHONG,  DEFAULT_SPHERE_PHONG)

    _ud_set(op, ML_TUBE_RADIUS,  DEFAULT_TUBE_RADIUS)
    _ud_set(op, ML_TUBE_SEGS_R,  DEFAULT_TUBE_SEGS_R)
    _ud_set(op, ML_TUBE_SEGS_H,  DEFAULT_TUBE_SEGS_H)

    _ud_set(op, ML_BEVEL_SIZE,   DEFAULT_BEVEL_SIZE)
    _ud_set(op, ML_BEVEL_SUBDIV, DEFAULT_BEVEL_SUBDIV)

    _ud_set(op, ML_HIDE_ISOLATED, DEFAULT_HIDE_ISOLATED)


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin class
# ══════════════════════════════════════════════════════════════════════════════

class MolecularHexLatticeObject(c4d.plugins.ObjectData):
    """Генератор молекулярной гексагональной решётки."""

    OBJECT_NAME = "MolecularHexLattice"

    def _ensure_ud(self, op):
        """Инициализирует UserData один раз (проверяет по первому параметру)."""
        if not _ud_exists(op, ML_FIRST_PARAM):
            _create_userdata(op)
            _set_defaults(op)

    # ── ObjectData interface ──────────────────────────────────────────────────

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
        self._ensure_ud(op)
        return True

    def GetVirtualObjects(self, op, hh):
        self._ensure_ud(op)
        return _build_lattice(op)

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
#  Иконка (32×32, молекула из гексагональных шаров)
# ══════════════════════════════════════════════════════════════════════════════

_ICON_ML = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAC8ElEQVR4nL2X"
    "TUhUURTHf+/NeKOjo6OOOuqoo4466qijjjrqqKOOOuqoo4466qijjjrq"
    "qKOOOuqoo4466qijFhERERERERERERERERERERERERERERERERERERERERER"
    "ERERERERERERERERERERERERQ6urq6urq6urq6urq6urq6urq6urq6urq6urq6"
    "urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6ur"
    "q6urq6uo7d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3"
    "d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3"
    "d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d"
    "3d3d3d3d3d3d3d3AAAAAAAA"
)

# Генерируем настоящую иконку программно — 32×32 PNG молекулы
def _generate_icon_png():
    """Генерирует PNG-иконку 32×32 в виде молекулярной сетки."""
    # Используем встроенный модуль для создания простого PNG
    import struct
    import zlib

    width, height = 32, 32

    def put_pixel(pixels, x, y, r, g, b, a=255):
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 4
            pixels[idx]   = r
            pixels[idx+1] = g
            pixels[idx+2] = b
            pixels[idx+3] = a

    def draw_circle(pixels, cx, cy, radius, r, g, b, fill=True):
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                dist = math.sqrt(dx*dx + dy*dy)
                if fill:
                    if dist <= radius:
                        put_pixel(pixels, int(cx+dx), int(cy+dy), r, g, b)
                else:
                    if radius-1 <= dist <= radius:
                        put_pixel(pixels, int(cx+dx), int(cy+dy), r, g, b)

    def draw_line(pixels, x0, y0, x1, y1, r, g, b, thick=1):
        dx = x1 - x0
        dy = y1 - y0
        length = math.sqrt(dx*dx + dy*dy)
        if length < 0.001:
            return
        steps = int(length * 2) + 1
        for i in range(steps):
            t = i / steps
            px = int(x0 + dx * t)
            py = int(y0 + dy * t)
            for tx in range(-thick+1, thick):
                for ty in range(-thick+1, thick):
                    put_pixel(pixels, px+tx, py+ty, r, g, b)

    # Прозрачный фон
    pixels = bytearray([0] * (width * height * 4))

    # Тёмный фон
    for i in range(width * height):
        pixels[i*4]   = 18
        pixels[i*4+1] = 20
        pixels[i*4+2] = 35
        pixels[i*4+3] = 255

    # Молекулярные узлы (позиции)
    nodes = [
        (8, 8), (24, 8),
        (16, 16),
        (4, 22), (28, 22),
        (10, 28), (22, 28),
    ]

    # Связи между узлами
    bonds = [
        (0,1), (0,2), (1,2),
        (0,3), (1,4),
        (2,5), (2,6),
        (3,5), (4,6),
        (5,6),
    ]

    # Рисуем трубки (связи) — сначала, чтобы шары перекрывали их
    for a_idx, b_idx in bonds:
        ax, ay = nodes[a_idx]
        bx, by = nodes[b_idx]
        draw_line(pixels, ax, ay, bx, by, 80, 160, 220, thick=1)

    # Рисуем шары поверх трубок
    for i, (nx, ny) in enumerate(nodes):
        # Градиентный шар — внешний обод
        draw_circle(pixels, nx, ny, 4, 30, 100, 200)
        # Светлый верх (имитация объёма)
        draw_circle(pixels, nx-1, ny-1, 2, 120, 200, 255)
        # Гексагональная решётка на шаре (маленькая)
        put_pixel(pixels, nx, ny, 200, 240, 255)

    # PNG encode
    def make_png(pixels, w, h):
        raw_rows = []
        for y in range(h):
            row = bytearray([0])  # filter type None
            for x in range(w):
                idx = (y * w + x) * 4
                row += pixels[idx:idx+4]
            raw_rows.append(bytes(row))
        raw_data = b''.join(raw_rows)
        compressed = zlib.compress(raw_data, 9)

        def chunk(name, data):
            length = struct.pack('>I', len(data))
            crc    = struct.pack('>I', zlib.crc32(name + data) & 0xFFFFFFFF)
            return length + name + data + crc

        ihdr_data = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
        png = (b'\x89PNG\r\n\x1a\n'
               + chunk(b'IHDR', ihdr_data)
               + chunk(b'IDAT', compressed)
               + chunk(b'IEND', b''))
        return png

    return make_png(pixels, width, height)


def _make_icon_ml():
    png_data = _generate_icon_png()
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
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
    return bmp

# ══════════════════════════════════════════════════════════════════════════════
#  Точка входа — регистрация плагина
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ICO_ML = _make_icon_ml()

    c4d.plugins.RegisterObjectPlugin(
        id          = ID_MOLHEXLATTICE,
        str         = NAME_MOLHEXLATTICE,
        g           = MolecularHexLatticeObject,
        description = "",
        icon        = ICO_ML,
        info        = c4d.OBJECT_GENERATOR,
    )
