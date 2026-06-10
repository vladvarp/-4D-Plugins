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
  • Уникальная иконка в base64
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

ID_MOLHEXLATTICE  = 1068899
NAME_MOLHEXLATTICE = "MolecularHexLattice v1.0"

# ══════════════════════════════════════════════════════════════════════════════
#  UserData SubID — строго зафиксированные номера
# ══════════════════════════════════════════════════════════════════════════════

UD_GROUP_LATTICE  = 1   # Группа «Каркас»

# Каркас
ML_SIZE_X   = 2
ML_SIZE_Y   = 3
ML_SIZE_Z   = 4
ML_DENSITY  = 5   # плотность узлов (расстояние между ними)
ML_BOND_DENS= 6   # плотность связей (макс. дистанция для создания трубки)
ML_SEED     = 7   # Seed для случайного размещения
ML_JITTER   = 8   # Дрожание (случайное смещение позиций)

# Strip
ML_STRIP_AMP   = 9    # Амплитуда полоски
ML_STRIP_FREQ  = 10   # Частота синусоиды
ML_STRIP_PHASE = 11   # Фаза (анимируемый параметр смещения)
ML_STRIP_AXIS  = 12   # Ось синусоиды (X/Y/Z)

# Шары
ML_SPHERE_RADIUS = 13
ML_SPHERE_SUBDIV = 14

# Трубки
ML_TUBE_RADIUS   = 15
ML_TUBE_SEGS_R   = 16
ML_TUBE_SEGS_H   = 17

# Фаска
ML_BEVEL_SIZE    = 18
ML_BEVEL_SUBDIV  = 19

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


def _add_group(op, name, parent_subid=0):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_TITLEBAR]   = 1
    bc[c4d.DESC_DEFAULT]    = 1
    if parent_subid:
        bc[c4d.DESC_PARENTGROUP] = c4d.DescID(
            c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
            c4d.DescLevel(parent_subid, c4d.DTYPE_GROUP, 0)
        )
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
#  Математика: общие утилиты
# ══════════════════════════════════════════════════════════════════════════════

def _v3(x, y, z):
    return c4d.Vector(x, y, z)


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


def _normalize_tuple(v):
    d = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if d < 1e-12:
        return v
    return (v[0]/d, v[1]/d, v[2]/d)


def _midpoint_sphere(a, b):
    return _normalize_tuple(((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2))


# ══════════════════════════════════════════════════════════════════════════════
#  Dual Icosphere (гексагональная сфера) — ядро из HexSphere
# ══════════════════════════════════════════════════════════════════════════════

def _icosphere_tris(subdivisions):
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

        def get_mid(a, b, _verts=verts, _ec=edge_cache):
            key = (min(a, b), max(a, b))
            if key not in _ec:
                _ec[key] = len(_verts)
                _verts.append(list(_midpoint_sphere(_verts[a], _verts[b])))
            return _ec[key]

        for f in faces:
            a, b, c = f[0], f[1], f[2]
            ab = get_mid(a, b)
            bc = get_mid(b, c)
            ca = get_mid(c, a)
            new_faces += [[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]]
        faces = new_faces

    return verts, faces


def _dual_mesh(verts, faces):
    """Строит dual mesh: центры треугольников → вершины гексагонов."""
    n_verts = len(verts)
    dual_verts = []
    for f in faces:
        cx = (verts[f[0]][0] + verts[f[1]][0] + verts[f[2]][0]) / 3.0
        cy = (verts[f[0]][1] + verts[f[1]][1] + verts[f[2]][1]) / 3.0
        cz = (verts[f[0]][2] + verts[f[1]][2] + verts[f[2]][2]) / 3.0
        dual_verts.append(list(_normalize_tuple((cx, cy, cz))))

    vert_to_faces = [[] for _ in range(n_verts)]
    for fi, f in enumerate(faces):
        for vi in f:
            vert_to_faces[vi].append(fi)

    dual_polys = []
    for vi in range(n_verts):
        adj = vert_to_faces[vi]
        if len(adj) < 3:
            continue
        nx, ny, nz = verts[vi]
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

        def angle(fi, _nx=nx,_ny=ny,_nz=nz,_tx=tx,_ty=ty,_tz=tz,_bx=bx,_by=by,_bz=bz):
            dvx = dual_verts[fi][0] - _nx
            dvy = dual_verts[fi][1] - _ny
            dvz = dual_verts[fi][2] - _nz
            u = dvx*_tx + dvy*_ty + dvz*_tz
            v = dvx*_bx + dvy*_by + dvz*_bz
            return math.atan2(v, u)

        ordered = sorted(adj, key=angle)
        # Проверяем ориентацию нормали
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

    return dual_verts, dual_polys


def _build_hex_sphere_data(radius, subdivisions):
    """
    Возвращает (sphere_pts, dual_polys, face_centers_unit, ico_verts_unit):
      sphere_pts       — c4d.Vector на поверхности сферы (уже масштабированы)
      dual_polys       — индексные списки гексагонов/пятиугольников
      face_normals     — единичные нормали каждого dual_poly (направление «наружу»)
      ico_verts_unit   — unit-вектора исходных вершин икосаэдра (для оси трубки)
    """
    subdivisions = max(1, min(5, int(subdivisions)))
    ico_verts, ico_faces = _icosphere_tris(subdivisions)
    dual_verts, dual_polys = _dual_mesh(ico_verts, ico_faces)
    sphere_pts = [c4d.Vector(v[0]*radius, v[1]*radius, v[2]*radius) for v in dual_verts]
    # Нормаль каждого полигона = среднее направление его вершин (они на сфере)
    face_normals = []
    for poly in dual_polys:
        nx = ny = nz = 0.0
        for idx in poly:
            nx += dual_verts[idx][0]
            ny += dual_verts[idx][1]
            nz += dual_verts[idx][2]
        l = math.sqrt(nx**2 + ny**2 + nz**2)
        face_normals.append((nx/l, ny/l, nz/l) if l > 1e-12 else (0,1,0))
    return sphere_pts, dual_polys, face_normals, ico_verts


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор гексагональной сферы С отверстием
# ══════════════════════════════════════════════════════════════════════════════

def _fan_polys(indices, pts):
    """N-гон → список c4d.CPolygon (веер от первой вершины)."""
    hub = indices[0]
    result = []
    n = len(indices)
    if n == 3:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[2])]
    if n == 4:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[3])]
    for k in range(1, n - 1):
        result.append(c4d.CPolygon(hub, indices[k], indices[k+1], indices[k+1]))
    return result


def _add_phong_tag(obj, angle_deg=45.0):
    """Добавляет Phong-тег к объекту."""
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
        tag[c4d.PHONGTAG_PHONG_ANGLE]      = math.radians(angle_deg)
        tag[c4d.PHONGTAG_PHONG_USEEDGES]   = True
    return tag


def _make_poly_object_raw(pts, cpolys, name):
    """Создаёт c4d.PolygonObject из готовых списков точек и CPolygon."""
    obj = c4d.PolygonObject(len(pts), len(cpolys))
    obj.SetName(name)
    for i, p in enumerate(pts):
        obj.SetPoint(i, p)
    for i, cp in enumerate(cpolys):
        obj.SetPolygon(i, cp)
    obj.Message(c4d.MSG_UPDATE)
    return obj


def _build_hex_sphere_with_holes(radius, subdivisions, connection_face_indices):
    """
    Строит dual icosphere с удалёнными гексагонами на позициях connection_face_indices.
    Возвращает (PolygonObject, hole_centers, hole_normals, hole_radii).
      hole_centers — c4d.Vector центра каждого отверстия (на поверхности сферы)
      hole_normals — направление «наружу» для каждого отверстия
      hole_radii   — усреднённый радиус отверстия (для стыковки трубки)
    """
    sphere_pts_raw, dual_polys, face_normals, _ = _build_hex_sphere_data(radius, subdivisions)

    pts = list(sphere_pts_raw)
    cpolys = []
    hidden = []

    hole_centers = []
    hole_normals = []
    hole_radii   = []

    conn_set = set(connection_face_indices)

    for fi, poly_idx_list in enumerate(dual_polys):
        if fi in conn_set:
            # Запоминаем данные отверстия
            cx = cy = cz = 0.0
            for idx in poly_idx_list:
                cx += pts[idx].x
                cy += pts[idx].y
                cz += pts[idx].z
            n_pts = len(poly_idx_list)
            cx /= n_pts; cy /= n_pts; cz /= n_pts
            hole_centers.append(c4d.Vector(cx, cy, cz))
            hole_normals.append(c4d.Vector(*face_normals[fi]))
            # Среднее расстояние от центра до края — радиус отверстия
            r_avg = 0.0
            for idx in poly_idx_list:
                p = pts[idx]
                r_avg += math.sqrt((p.x-cx)**2 + (p.y-cy)**2 + (p.z-cz)**2)
            hole_radii.append(r_avg / n_pts)
            # Этот полигон пропускаем (не добавляем)
            continue

        start = len(cpolys)
        new_cps = _fan_polys(poly_idx_list, pts)
        cpolys.extend(new_cps)
        n = len(poly_idx_list)
        if n > 4:
            for t in range(n - 2):
                pi = start + t
                if t > 0:
                    hidden.append(4 * pi + 0)
                if t < n - 3:
                    hidden.append(4 * pi + 2)

    obj = _make_poly_object_raw(pts, cpolys, "MHL_Sphere")
    if hidden:
        eh = obj.GetEdgeH()
        for eid in hidden:
            eh.Select(eid)
    _add_phong_tag(obj, 45.0)
    return obj, hole_centers, hole_normals, hole_radii


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор трубки между двумя точками (с фаской)
# ══════════════════════════════════════════════════════════════════════════════

def _make_rotation_matrix_from_z_to_dir(direction):
    """Матрица поворота, которая направляет ось Z вдоль direction."""
    d = _v3_normalize(direction)
    # Стандартная ось Z
    z = c4d.Vector(0, 1, 0)  # Cinema 4D: Y — ось цилиндра
    # Если direction почти параллелен Y
    if abs(_v3_dot(d, c4d.Vector(0, 1, 0))) > 0.9999:
        # Деградированный случай — поворот на 180° вокруг X
        if d.y > 0:
            return c4d.Matrix(
                c4d.Vector(0,0,0),
                c4d.Vector(1,0,0),
                c4d.Vector(0,1,0),
                c4d.Vector(0,0,1)
            )
        else:
            return c4d.Matrix(
                c4d.Vector(0,0,0),
                c4d.Vector(1,0,0),
                c4d.Vector(0,-1,0),
                c4d.Vector(0,0,-1)
            )
    right = _v3_normalize(_v3_cross(c4d.Vector(0, 1, 0), d))
    up    = _v3_normalize(_v3_cross(d, right))
    return c4d.Matrix(c4d.Vector(0,0,0), right, d, up)


def _build_tube(pt_a, pt_b, tube_radius, segs_r, segs_h,
                bevel_size, bevel_subdiv):
    """
    Строит трубку от pt_a до pt_b.
    Возвращает (tube_obj, bevel_objs).
    tube_obj   — основной цилиндр (PolygonObject)
    bevel_objs — список фасочных кольцевых объектов (по 2 штуки: у каждого конца)
    """
    diff = pt_b - pt_a
    length = _v3_len(diff)
    if length < 1e-6:
        return None, []

    direction = _v3_normalize(diff)
    midpoint  = _v3_lerp(pt_a, pt_b, 0.5)

    segs_r = max(3, int(segs_r))
    segs_h = max(1, int(segs_h))
    bevel_subdiv = max(0, int(bevel_subdiv))
    bevel_size   = max(0.0, float(bevel_size))

    # ── Основной цилиндр ────────────────────────────────────────────────────
    pts      = []
    cpolys   = []

    half_len = length / 2.0
    # Если есть фаска — укорачиваем трубку на bevel_size с каждого конца
    actual_bevel = min(bevel_size, half_len * 0.45)
    inner_half   = half_len - actual_bevel

    # Ряды вершин: segs_h+1 рядов вдоль оси
    for row in range(segs_h + 1):
        t = row / segs_h
        y = -inner_half + t * inner_half * 2.0
        for col in range(segs_r):
            angle = col / segs_r * 2.0 * math.pi
            x = tube_radius * math.cos(angle)
            z = tube_radius * math.sin(angle)
            pts.append(c4d.Vector(x, y, z))

    for row in range(segs_h):
        for col in range(segs_r):
            bl = row * segs_r + col
            br = row * segs_r + (col+1) % segs_r
            tl = (row+1) * segs_r + col
            tr = (row+1) * segs_r + (col+1) % segs_r
            cpolys.append(c4d.CPolygon(bl, tl, tr, br))

    # Крышки трубки (кольцо без дна — трубка открытая у шаров)
    # Ничего не добавляем — шары закрывают отверстия

    tube_obj = _make_poly_object_raw(pts, cpolys, "MHL_Tube")
    _add_phong_tag(tube_obj, 45.0)

    # Позиционируем и ориентируем
    mg = _make_rotation_matrix_from_z_to_dir(direction)
    mg.off = midpoint
    tube_obj.SetMg(mg)

    # ── Фаски ───────────────────────────────────────────────────────────────
    bevel_objs = []
    if actual_bevel > 1e-4 and bevel_subdiv >= 0:
        for end_sign in (-1.0, 1.0):  # -1 = нижний конец, +1 = верхний
            bev_pts   = []
            bev_polys = []

            # Фаска — тор-секция: переход от inner_half до half_len по радиусу
            # Число кольцевых рядов фаски
            n_bev = max(1, bevel_subdiv + 1)

            for ring in range(n_bev + 1):
                t = ring / n_bev  # 0..1
                # Радиус и Y меняются по четверти окружности (скруглённая фаска)
                ang = t * math.pi * 0.5
                ring_radius = tube_radius + actual_bevel * math.sin(ang)
                ring_y      = end_sign * (inner_half + actual_bevel * (1.0 - math.cos(ang)))
                for col in range(segs_r):
                    a = col / segs_r * 2.0 * math.pi
                    x = ring_radius * math.cos(a)
                    z = ring_radius * math.sin(a)
                    bev_pts.append(c4d.Vector(x, ring_y, z))

            for ring in range(n_bev):
                for col in range(segs_r):
                    bl = ring * segs_r + col
                    br = ring * segs_r + (col+1) % segs_r
                    tl = (ring+1) * segs_r + col
                    tr = (ring+1) * segs_r + (col+1) % segs_r
                    if end_sign < 0:
                        # Нижний конец — порядок CCW
                        bev_polys.append(c4d.CPolygon(bl, br, tr, tl))
                    else:
                        # Верхний конец
                        bev_polys.append(c4d.CPolygon(bl, tl, tr, br))

            bev_obj = _make_poly_object_raw(bev_pts, bev_polys, "MHL_Bevel")
            _add_phong_tag(bev_obj, 45.0)
            bev_obj.SetMg(mg)
            bevel_objs.append(bev_obj)

    return tube_obj, bevel_objs


# ══════════════════════════════════════════════════════════════════════════════
#  Генератор каркаса
# ══════════════════════════════════════════════════════════════════════════════

def _generate_node_positions(size_x, size_y, size_z, density, seed, jitter):
    """
    Генерирует позиции узлов на регулярной решётке с добавлением случайного
    джиттера. density — расстояние между узлами.
    """
    rng = random.Random(seed)
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
    Плавно смещает позиции вдоль перпендикулярной оси по синусоиде.
    axis: 0=X (смещение по Y+Z), 1=Y (смещение по X+Z), 2=Z (смещение по X+Y)
    Параметр phase анимируется — смещение «плывёт» не разрывая связей,
    потому что трубки пересчитываются по новым позициям.
    """
    if amplitude < 1e-6:
        return positions
    result = []
    for p in positions:
        if axis == 0:
            val = math.sin(p.x * frequency + phase)
            result.append(c4d.Vector(p.x, p.y + amplitude * val, p.z + amplitude * val * 0.5))
        elif axis == 1:
            val = math.sin(p.y * frequency + phase)
            result.append(c4d.Vector(p.x + amplitude * val, p.y, p.z + amplitude * val * 0.5))
        else:
            val = math.sin(p.z * frequency + phase)
            result.append(c4d.Vector(p.x + amplitude * val, p.y + amplitude * val * 0.5, p.z))
    return result


def _find_bonds(positions, bond_max_dist):
    """
    Находит пары узлов для создания связей.
    Только пары, расстояние между которыми < bond_max_dist.
    """
    bonds = []
    n = len(positions)
    bond_sq = bond_max_dist * bond_max_dist
    for i in range(n):
        for j in range(i+1, n):
            d = positions[i] - positions[j]
            dsq = d.x**2 + d.y**2 + d.z**2
            if dsq < bond_sq:
                bonds.append((i, j))
    return bonds


def _find_closest_face(node_pos, face_normals_unit, direction):
    """
    Находит индекс грани dual_sphere, нормаль которой ближе всего к direction.
    direction — единичный вектор от центра шара к соседнему узлу.
    """
    best_idx = 0
    best_dot = -2.0
    dx, dy, dz = direction.x, direction.y, direction.z
    for fi, (nx, ny, nz) in enumerate(face_normals_unit):
        dot = nx*dx + ny*dy + nz*dz
        if dot > best_dot:
            best_dot = dot
            best_idx = fi
    return best_idx


# ══════════════════════════════════════════════════════════════════════════════
#  Материальные теги (ограничение выделения)
# ══════════════════════════════════════════════════════════════════════════════

def _find_material(doc, restriction):
    """Ищет в документе материал по ограничению выделения (имя материала)."""
    mat = doc.GetFirstMaterial()
    while mat:
        if mat.GetName() == restriction:
            return mat
        mat = mat.GetNext()
    return None


def _apply_material_tag(obj, doc, restriction):
    """
    Назначает материал с ограничением выделения obj.
    restriction — 'M', 'T' или 'F'.
    Ищет материал с именем restriction. Если не найден — создаёт новый.
    """
    mat = _find_material(doc, restriction)
    if mat is None:
        mat = c4d.BaseMaterial(c4d.Mmaterial)
        mat.SetName(restriction)
        # Базовый цвет по типу
        if restriction == "M":
            mat[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(0.2, 0.5, 1.0)
        elif restriction == "T":
            mat[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(0.8, 0.8, 0.9)
        elif restriction == "F":
            mat[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(1.0, 0.7, 0.2)
        doc.InsertMaterial(mat)

    tag = obj.MakeTag(c4d.Ttexture)
    if tag:
        tag[c4d.TEXTURETAG_MATERIAL]    = mat
        tag[c4d.TEXTURETAG_RESTRICTION] = restriction
    return tag


# ══════════════════════════════════════════════════════════════════════════════
#  Главный генератор: собираем всё вместе
# ══════════════════════════════════════════════════════════════════════════════

def _build_molecular_lattice(op, doc):
    """
    Строит всю молекулярную систему.
    Возвращает BaseObject (нулевой объект-контейнер) со всеми дочерними объектами.
    """
    # ── Читаем параметры ────────────────────────────────────────────────────
    size_x      = max(1.0,   float(_ud_get(op, ML_SIZE_X,      500.0)))
    size_y      = max(1.0,   float(_ud_get(op, ML_SIZE_Y,      500.0)))
    size_z      = max(1.0,   float(_ud_get(op, ML_SIZE_Z,      500.0)))
    density     = max(10.0,  float(_ud_get(op, ML_DENSITY,     200.0)))
    bond_dens   = max(1.0,   float(_ud_get(op, ML_BOND_DENS,   250.0)))
    seed        = int(_ud_get(op, ML_SEED,        42))
    jitter      = max(0.0,   float(_ud_get(op, ML_JITTER,      20.0)))

    strip_amp   = max(0.0,   float(_ud_get(op, ML_STRIP_AMP,   0.0)))
    strip_freq  = max(0.001, float(_ud_get(op, ML_STRIP_FREQ,  0.01)))
    strip_phase = float(_ud_get(op, ML_STRIP_PHASE, 0.0))
    strip_axis  = int(_ud_get(op, ML_STRIP_AXIS,  1))

    sphere_r    = max(1.0,   float(_ud_get(op, ML_SPHERE_RADIUS, 40.0)))
    sphere_sub  = max(1,     min(4, int(_ud_get(op, ML_SPHERE_SUBDIV, 2))))

    tube_r      = max(0.5,   float(_ud_get(op, ML_TUBE_RADIUS,  8.0)))
    tube_sr     = max(3,     int(_ud_get(op, ML_TUBE_SEGS_R,   8)))
    tube_sh     = max(1,     int(_ud_get(op, ML_TUBE_SEGS_H,   2)))

    bevel_size  = max(0.0,   float(_ud_get(op, ML_BEVEL_SIZE,  5.0)))
    bevel_sub   = max(0,     int(_ud_get(op, ML_BEVEL_SUBDIV,  2)))

    # ── Генерируем позиции узлов ────────────────────────────────────────────
    positions_raw = _generate_node_positions(size_x, size_y, size_z, density, seed, jitter)

    # Ограничиваем количество узлов (безопасность производительности)
    max_nodes = 200
    if len(positions_raw) > max_nodes:
        positions_raw = positions_raw[:max_nodes]

    # Применяем Strip
    positions = _apply_strip(positions_raw, strip_amp, strip_freq, strip_phase, strip_axis)

    if not positions:
        null = c4d.BaseObject(c4d.Onull)
        null.SetName("MolecularHexLattice")
        return null

    # ── Находим связи ────────────────────────────────────────────────────────
    bonds = _find_bonds(positions, bond_dens)

    # Ограничиваем количество связей
    max_bonds = 600
    if len(bonds) > max_bonds:
        bonds = bonds[:max_bonds]

    # ── Вычисляем какие грани шара используются для связей ──────────────────
    # Получаем нормали граней dual icosphere
    _, _, face_normals_unit, _ = _build_hex_sphere_data(1.0, sphere_sub)
    n_faces = len(face_normals_unit)

    # Для каждого узла — список граней, куда подключаются трубки
    node_connection_faces = [[] for _ in range(len(positions))]

    for bond_idx, (i, j) in enumerate(bonds):
        pi = positions[i]
        pj = positions[j]
        # Направление от i к j
        diff_ij = pj - pi
        diff_ji = pi - pj
        dir_ij = _v3_normalize(diff_ij)
        dir_ji = _v3_normalize(diff_ji)

        fi_ij = _find_closest_face(pi, face_normals_unit, dir_ij)
        fi_ji = _find_closest_face(pj, face_normals_unit, dir_ji)

        # Избегаем дублирования грани на одном шаре
        if fi_ij not in node_connection_faces[i]:
            node_connection_faces[i].append(fi_ij)
        if fi_ji not in node_connection_faces[j]:
            node_connection_faces[j].append(fi_ji)

    # ── Создаём контейнер ────────────────────────────────────────────────────
    root = c4d.BaseObject(c4d.Onull)
    root.SetName("MolecularHexLattice")

    # Группы для организации
    grp_spheres = c4d.BaseObject(c4d.Onull)
    grp_spheres.SetName("Spheres")
    grp_spheres.InsertUnder(root)

    grp_tubes = c4d.BaseObject(c4d.Onull)
    grp_tubes.SetName("Tubes")
    grp_tubes.InsertUnder(root)

    grp_bevels = c4d.BaseObject(c4d.Onull)
    grp_bevels.SetName("Bevels")
    grp_bevels.InsertUnder(root)

    # ── Строим шары ──────────────────────────────────────────────────────────
    sphere_objects = []
    for node_idx, pos in enumerate(positions):
        conn_faces = node_connection_faces[node_idx]
        # Клэмп: не более чем граней существует
        conn_faces = [f for f in conn_faces if f < n_faces]

        sphere_obj, hole_centers, hole_normals, hole_radii = \
            _build_hex_sphere_with_holes(sphere_r, sphere_sub, conn_faces)

        sphere_obj.SetAbsPos(pos)
        sphere_obj.SetName("Sphere_%03d" % node_idx)
        sphere_objects.append(sphere_obj)

        # Материальный тег "M"
        if doc:
            _apply_material_tag(sphere_obj, doc, "M")

        sphere_obj.InsertUnder(grp_spheres)

    # ── Строим трубки ────────────────────────────────────────────────────────
    for bond_idx, (i, j) in enumerate(bonds):
        pi = positions[i]
        pj = positions[j]

        # Точки стыковки трубки у поверхности шаров
        diff = pj - pi
        length = _v3_len(diff)
        if length < 1e-6:
            continue

        dir_n = _v3_normalize(diff)

        # Трубка начинается/заканчивается у поверхности шаров
        pt_a = pi + dir_n * sphere_r
        pt_b = pj - dir_n * sphere_r

        # Убеждаемся что длина трубки положительная
        tube_len = _v3_len(pt_b - pt_a)
        if tube_len < tube_r * 0.5:
            continue

        tube_obj, bevel_objs = _build_tube(
            pt_a, pt_b,
            tube_r, tube_sr, tube_sh,
            bevel_size, bevel_sub
        )

        if tube_obj is not None:
            tube_obj.SetName("Tube_%03d" % bond_idx)
            if doc:
                _apply_material_tag(tube_obj, doc, "T")
            tube_obj.InsertUnder(grp_tubes)

            for bv_idx, bev_obj in enumerate(bevel_objs):
                bev_obj.SetName("Bevel_%03d_%d" % (bond_idx, bv_idx))
                if doc:
                    _apply_material_tag(bev_obj, doc, "F")
                bev_obj.InsertUnder(grp_bevels)

    return root


# ══════════════════════════════════════════════════════════════════════════════
#  UserData: создание и инициализация
# ══════════════════════════════════════════════════════════════════════════════

def _create_all_userdata(op):
    """Создаёт все UserData-поля плагина."""

    # ── Группа: Каркас ───────────────────────────────────────────────────────
    g_lat = _add_group(op, "Каркас")

    _add_in_group(op, g_lat, _float_bc("Размер X",      500.0,  10.0, 100000.0))
    _add_in_group(op, g_lat, _float_bc("Размер Y",      500.0,  10.0, 100000.0))
    _add_in_group(op, g_lat, _float_bc("Размер Z",      500.0,  10.0, 100000.0))
    _add_in_group(op, g_lat, _float_bc("Плотность узлов", 200.0, 10.0, 10000.0))
    _add_in_group(op, g_lat, _float_bc("Макс. длина связи", 250.0, 10.0, 10000.0))
    _add_in_group(op, g_lat, _int_bc("Seed", 42, 0, 99999))
    _add_in_group(op, g_lat, _float_bc("Джиттер", 20.0, 0.0, 5000.0))

    # ── Группа: Strip ────────────────────────────────────────────────────────
    g_strip = _add_group(op, "Strip (смещение)")

    _add_in_group(op, g_strip, _float_bc("Амплитуда", 0.0, 0.0, 10000.0))
    _add_in_group(op, g_strip, _float_bc("Частота",   0.01, 0.0001, 10.0,
                                          unit=c4d.DESC_UNIT_FLOAT, step=0.001))
    _add_in_group(op, g_strip, _float_bc("Фаза (анимировать)", 0.0, -1000.0, 1000.0,
                                          unit=c4d.DESC_UNIT_FLOAT, step=0.01))
    _add_in_group(op, g_strip, _cycle_bc("Ось синусоиды", 1, ["X", "Y", "Z"]))

    # ── Группа: Шары ─────────────────────────────────────────────────────────
    g_sph = _add_group(op, "Шары (M)")

    _add_in_group(op, g_sph, _float_bc("Радиус шара", 40.0, 1.0, 100000.0))
    _add_in_group(op, g_sph, _int_bc("Подразделение", 2, 1, 4))

    # ── Группа: Трубки ────────────────────────────────────────────────────────
    g_tub = _add_group(op, "Трубки (T)")

    _add_in_group(op, g_tub, _float_bc("Радиус трубки", 8.0, 0.5, 100000.0))
    _add_in_group(op, g_tub, _int_bc("Сегменты окружности", 8, 3, 64))
    _add_in_group(op, g_tub, _int_bc("Сегменты длины",      2, 1, 64))

    # ── Группа: Фаска ─────────────────────────────────────────────────────────
    g_bev = _add_group(op, "Фаска (F)")

    _add_in_group(op, g_bev, _float_bc("Размер фаски", 5.0, 0.0, 100000.0))
    _add_in_group(op, g_bev, _int_bc("Подразделение фаски", 2, 0, 8))


def _set_all_defaults(op):
    """Устанавливает значения по умолчанию."""
    _ud_set(op, ML_SIZE_X,      500.0)
    _ud_set(op, ML_SIZE_Y,      500.0)
    _ud_set(op, ML_SIZE_Z,      500.0)
    _ud_set(op, ML_DENSITY,     200.0)
    _ud_set(op, ML_BOND_DENS,   250.0)
    _ud_set(op, ML_SEED,        42)
    _ud_set(op, ML_JITTER,      20.0)

    _ud_set(op, ML_STRIP_AMP,   0.0)
    _ud_set(op, ML_STRIP_FREQ,  0.01)
    _ud_set(op, ML_STRIP_PHASE, 0.0)
    _ud_set(op, ML_STRIP_AXIS,  1)

    _ud_set(op, ML_SPHERE_RADIUS, 40.0)
    _ud_set(op, ML_SPHERE_SUBDIV, 2)

    _ud_set(op, ML_TUBE_RADIUS,  8.0)
    _ud_set(op, ML_TUBE_SEGS_R,  8)
    _ud_set(op, ML_TUBE_SEGS_H,  2)

    _ud_set(op, ML_BEVEL_SIZE,   5.0)
    _ud_set(op, ML_BEVEL_SUBDIV, 2)


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin class
# ══════════════════════════════════════════════════════════════════════════════

class MolecularHexLatticeObject(c4d.plugins.ObjectData):
    """Генератор молекулярной гексагональной решётки."""

    OBJECT_NAME  = "MolecularHexLattice"
    _first_ud_id = ML_SIZE_X

    # ── Служебные ────────────────────────────────────────────────────────────

    def _ensure_ud(self, op):
        if not _ud_exists(op, self._first_ud_id):
            _create_all_userdata(op)
            _set_all_defaults(op)

    # ── ObjectData interface ──────────────────────────────────────────────────

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
        self._ensure_ud(op)
        return True

    def GetVirtualObjects(self, op, hh):
        self._ensure_ud(op)
        doc = op.GetDocument()
        result = _build_molecular_lattice(op, doc)
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
#  Регистрация плагина
# ══════════════════════════════════════════════════════════════════════════════

ICO_ML = None

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
