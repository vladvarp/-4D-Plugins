# -*- coding: utf-8 -*-
"""
MeshPrimitives — Cinema 4D ObjectData Plugin
Набор примитивов с нестандартной топологией полигонов.

Примитивы:
  1. TriCube   — Куб с треугольной сеткой
  2. HexSphere — Сфера с гексагональной/пятиугольной сеткой (dual icosphere)
  3. DiamondCylinder — Цилиндр с ромбической сеткой (смещённые ряды)
  4. TriTorus  — Тор с треугольной сеткой
  5. BrickPlane — Плоскость с кирпичной сеткой (running bond)

IDs:  1068860 – 1068864  (5 уникальных ID)
"""

import c4d
import math
import os
import base64
import tempfile

# ─── Plugin IDs ───────────────────────────────────────────────────────────────

ID_TRICUBE          = 1068862
ID_HEXSPHERE        = 1068863
ID_DIAMONDCYLINDER  = 1068864
ID_TRITORUS         = 1068865
ID_BRICKPLANE       = 1068866

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# TriCube
TC_SIZE    = 2
TC_SUBDIVS = 3

# HexSphere
HS_RADIUS  = 2
HS_SUBDIV  = 3

# DiamondCylinder
DC_RADIUS  = 2
DC_HEIGHT  = 3
DC_SEGS_R  = 4
DC_SEGS_H  = 5
DC_CAPS    = 6

# TriTorus
TT_RADIUS_MAJOR = 2
TT_RADIUS_MINOR = 3
TT_SEGS_MAJOR   = 4
TT_SEGS_MINOR   = 5

# BrickPlane
BP_WIDTH  = 2
BP_HEIGHT = 3
BP_SEGS_W = 4
BP_SEGS_H = 5


# ─── Вспомогательные функции UserData ────────────────────────────────────────

def _ud_descid(op, uid):
    """Ищет UserData по SubID. Возвращает (DescID, BaseContainer) или (None, None)."""
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


def _add_group(op, name):
    """Добавляет корневую группу UserData. Возвращает SubID группы."""
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_TITLEBAR]   = 1
    did = op.AddUserData(bc)
    return did[1].id   # [1] — SubID, [0] — ID_USERDATA(700)


def _add_in_group(op, grp_subid, bc):
    """Добавляет элемент UserData внутрь группы с данным SubID."""
    bc[c4d.DESC_PARENTGROUP] = c4d.DescID(
        c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
        c4d.DescLevel(grp_subid, c4d.DTYPE_GROUP, 0)
    )
    return op.AddUserData(bc)


def _make_float_bc(name, default, minval, maxval, unit=c4d.DESC_UNIT_METER):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_REAL)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_MIN]        = minval
    bc[c4d.DESC_MAX]        = maxval
    bc[c4d.DESC_UNIT]       = unit
    bc[c4d.DESC_STEP]       = 1.0
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


def _make_int_bc(name, default, minval, maxval):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_MIN]        = minval
    bc[c4d.DESC_MAX]        = maxval
    bc[c4d.DESC_STEP]       = 1
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


def _make_bool_bc(name, default):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BOOL)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    return bc


def _ud_already_created(op, first_field_uid):
    """Проверяет, созданы ли уже UserData по наличию поля с данным SubID."""
    did, _ = _ud_descid(op, first_field_uid)
    return did is not None


def _ud_set_default(op, uid, value):
    """Устанавливает значение поля UserData по SubID."""
    did, _ = _ud_descid(op, uid)
    if did is not None:
        op[did] = value


# ─── Математика: общие утилиты ────────────────────────────────────────────────

def _normalize(v):
    d = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if d < 1e-12:
        return v
    return (v[0]/d, v[1]/d, v[2]/d)


def _midpoint_sphere(a, b):
    """Средняя точка двух вершин, спроецированная на единичную сферу."""
    return _normalize(((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2))


# ─── Генераторы мешей ─────────────────────────────────────────────────────────

def build_tricube(size, subdivs):
    """
    Куб с треугольной сеткой.
    Каждая из 6 граней делится на subdivs×subdivs ячеек,
    каждая ячейка — 2 треугольника (CPolygon с равными c и d = вырожденный квад).
    Возвращает (points, polys) для c4d.PolygonObject.
    """
    half = size / 2.0

    # 6 граней куба: (ось_u, ось_v, нормаль_знак * нормаль_ось)
    # Каждая грань задаётся тремя осями: u, v, w (нормаль)
    # Ориентация такова, что нормаль смотрит наружу
    face_axes = [
        # (u_axis,      v_axis,      w_sign, w_axis)  — w = нормаль * w_sign
        (( 1, 0, 0), ( 0, 1, 0), +1, (0, 0, 1)),  # передняя  +Z
        ((-1, 0, 0), ( 0, 1, 0), -1, (0, 0, 1)),  # задняя    -Z
        (( 0, 0,-1), ( 0, 1, 0), +1, (1, 0, 0)),  # правая    +X
        (( 0, 0, 1), ( 0, 1, 0), -1, (1, 0, 0)),  # левая     -X
        (( 1, 0, 0), ( 0, 0,-1), +1, (0, 1, 0)),  # верхняя   +Y
        (( 1, 0, 0), ( 0, 0, 1), -1, (0, 1, 0)),  # нижняя    -Y
    ]

    all_points = []
    all_polys  = []

    for (ux, uy, uz), (vx, vy, vz), w_sign, (wx, wy, wz) in face_axes:
        base = len(all_points)
        n = subdivs + 1  # вершин на сторону

        # Генерируем вершины грани в локальной (u,v)-системе
        for row in range(n):
            v_t = (row / subdivs) * 2.0 - 1.0  # [-1, +1]
            for col in range(n):
                u_t = (col / subdivs) * 2.0 - 1.0  # [-1, +1]
                x = (ux*u_t + vx*v_t + wx*w_sign) * half
                y = (uy*u_t + vy*v_t + wy*w_sign) * half
                z = (uz*u_t + vz*v_t + wz*w_sign) * half
                all_points.append(c4d.Vector(x, y, z))

        # Генерируем треугольники (через вырожденный CPolygon: d == c)
        for row in range(subdivs):
            for col in range(subdivs):
                bl = base + row*n + col
                br = base + row*n + (col+1)
                tl = base + (row+1)*n + col
                tr = base + (row+1)*n + (col+1)
                # Треугольник 1: bl, br, tl  (d=tl — вырожденный)
                all_polys.append(c4d.CPolygon(bl, br, tl, tl))
                # Треугольник 2: br, tr, tl  (d=tl — вырожденный)
                all_polys.append(c4d.CPolygon(br, tr, tl, tl))

    return all_points, all_polys


def build_hexsphere(radius, subdivisions):
    """
    Сфера с гексагональной/пятиугольной сеткой.
    Метод: dual mesh икосферы.
      - Строим икосаэдр, subdivide его до нужного уровня
      - Берём dual mesh: каждый треугольник → вершина, каждая вершина → полигон
      - 12 пятиугольников (бывшие вершины икосаэдра) + остальные шестиугольники
    Возвращает (points, polys).
    """
    PHI = (1.0 + math.sqrt(5.0)) / 2.0

    # ── Икосаэдр (12 вершин, 20 граней) ──
    raw_verts = [
        ( 0,  1,  PHI), ( 0, -1,  PHI), ( 0,  1, -PHI), ( 0, -1, -PHI),
        ( 1,  PHI, 0),  (-1,  PHI, 0),  ( 1, -PHI, 0),  (-1, -PHI, 0),
        ( PHI, 0,  1),  (-PHI, 0,  1),  ( PHI, 0, -1),  (-PHI, 0, -1),
    ]
    ico_verts = [list(_normalize(v)) for v in raw_verts]

    # Фиксированная таблица 20 граней икосаэдра (CCW, нормали наружу)
    ico_faces = [
        [0,1,8],  [0,8,4],  [0,4,5],  [0,5,9],  [0,9,1],
        [1,6,8],  [8,6,10], [8,10,4], [4,10,2],  [4,2,5],
        [5,2,11], [5,11,9], [9,11,7], [9,7,1],   [1,7,6],
        [3,6,7],  [3,7,11], [3,11,2], [3,2,10],  [3,10,6],
    ]

    # ── Подразделение (subdivisions итераций) ──
    verts = ico_verts
    faces = ico_faces
    for _ in range(subdivisions):
        new_faces  = []
        edge_cache = {}   # (min_i, max_i) → новый индекс

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
            new_faces.append([a, ab, ca])
            new_faces.append([ab, b, bc])
            new_faces.append([ca, bc, c])
            new_faces.append([ab, bc, ca])
        faces = new_faces

    n_verts = len(verts)
    n_faces = len(faces)

    # ── Dual mesh ──
    # Dual-вершины = центроиды граней икосферы, спроецированные на сферу
    dual_verts = []
    for f in faces:
        cx = (verts[f[0]][0] + verts[f[1]][0] + verts[f[2]][0]) / 3.0
        cy = (verts[f[0]][1] + verts[f[1]][1] + verts[f[2]][1]) / 3.0
        cz = (verts[f[0]][2] + verts[f[1]][2] + verts[f[2]][2]) / 3.0
        dual_verts.append(list(_normalize((cx, cy, cz))))

    # Для каждой вершины икосферы — список смежных граней
    vert_to_faces = [[] for _ in range(n_verts)]
    for fi, f in enumerate(faces):
        for vi in f:
            vert_to_faces[vi].append(fi)

    # Упорядочиваем смежные грани вокруг вершины по углу в касательной плоскости
    dual_polys = []
    for vi in range(n_verts):
        adj = vert_to_faces[vi]
        if len(adj) < 3:
            continue

        nx, ny, nz = verts[vi][0], verts[vi][1], verts[vi][2]

        # Касательный вектор (Gram-Schmidt)
        if abs(nx) < 0.9:
            tx, ty, tz = 1.0, 0.0, 0.0
        else:
            tx, ty, tz = 0.0, 1.0, 0.0
        dot = tx*nx + ty*ny + tz*nz
        tx -= dot*nx;  ty -= dot*ny;  tz -= dot*nz
        td = math.sqrt(tx**2 + ty**2 + tz**2)
        tx /= td;  ty /= td;  tz /= td

        # Бинормаль (правая система: n = t × b → b = n × t)
        bx = ny*tz - nz*ty
        by = nz*tx - nx*tz
        bz = nx*ty - ny*tx

        def _face_angle(fi):
            dvx = dual_verts[fi][0] - nx
            dvy = dual_verts[fi][1] - ny
            dvz = dual_verts[fi][2] - nz
            u = dvx*tx + dvy*ty + dvz*tz
            v = dvx*bx + dvy*by + dvz*bz
            return math.atan2(v, u)

        adj_sorted = sorted(adj, key=_face_angle)
        dual_polys.append(adj_sorted)

    # ── Конвертация в c4d ──
    # Масштабируем под нужный радиус
    c4d_points = [c4d.Vector(v[0]*radius, v[1]*radius, v[2]*radius)
                  for v in dual_verts]

    c4d_polys = []
    for poly_indices in dual_polys:
        n = len(poly_indices)
        if n == 5:
            # Пятиугольник — раскладываем в три треугольника (fan triangulation)
            a = poly_indices[0]
            for k in range(1, n - 1):
                b = poly_indices[k]
                c_i = poly_indices[k+1]
                c4d_polys.append(c4d.CPolygon(a, b, c_i, c_i))
        elif n == 6:
            # Шестиугольник — раскладываем в четыре треугольника (fan)
            a = poly_indices[0]
            for k in range(1, n - 1):
                b = poly_indices[k]
                c_i = poly_indices[k+1]
                c4d_polys.append(c4d.CPolygon(a, b, c_i, c_i))
        else:
            # Любые другие полигоны (не ожидаются, но на всякий случай)
            a = poly_indices[0]
            for k in range(1, n - 1):
                b = poly_indices[k]
                c_i = poly_indices[k+1]
                c4d_polys.append(c4d.CPolygon(a, b, c_i, c_i))

    return c4d_points, c4d_polys


def build_diamond_cylinder(radius, height, segs_r, segs_h, add_caps):
    """
    Цилиндр с ромбической сеткой.
    Нечётные ряды вершин смещены на полшага по углу — ячейки становятся ромбами.
    Возвращает (points, polys).
    """
    verts = []

    # Боковая поверхность: segs_h+1 рядов, segs_r вершин на ряд
    for row in range(segs_h + 1):
        t = row / segs_h                      # [0, 1]
        y = t * height - height / 2.0
        # Нечётные ряды сдвигаем на полшага по углу
        offset_angle = (math.pi / segs_r) if (row % 2 == 1) else 0.0
        for col in range(segs_r):
            angle = col / segs_r * 2.0 * math.pi + offset_angle
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            verts.append(c4d.Vector(x, y, z))

    polys = []

    # Ромбы на боковой поверхности
    for row in range(segs_h):
        for col in range(segs_r):
            curr = row * segs_r + col
            next_col = row * segs_r + (col + 1) % segs_r
            up_col   = (row + 1) * segs_r + col
            up_next  = (row + 1) * segs_r + (col + 1) % segs_r

            if row % 2 == 0:
                # Чётный ряд → нечётный (сдвинутый): ромб вытянут вправо-вверх
                polys.append(c4d.CPolygon(curr, next_col, up_next, up_col))
            else:
                # Нечётный ряд → чётный: ромб вытянут влево-вверх
                polys.append(c4d.CPolygon(curr, next_col, up_next, up_col))

    if add_caps:
        # Нижняя крышка
        bottom_center_idx = len(verts)
        verts.append(c4d.Vector(0, -height/2.0, 0))
        for col in range(segs_r):
            a = col
            b = (col + 1) % segs_r
            # Нормаль вниз: CPolygon(center, b, a, a) — CCW вид снизу
            polys.append(c4d.CPolygon(bottom_center_idx, b, a, a))

        # Верхняя крышка (последний ряд вершин — индекс segs_h)
        top_center_idx = len(verts)
        verts.append(c4d.Vector(0, height/2.0, 0))
        top_row_start = segs_h * segs_r
        # У верхнего ряда может быть смещение, если segs_h нечётное
        for col in range(segs_r):
            a = top_row_start + col
            b = top_row_start + (col + 1) % segs_r
            # Нормаль вверх: CPolygon(center, a, b, b)
            polys.append(c4d.CPolygon(top_center_idx, a, b, b))

    return verts, polys


def build_tritorus(radius_major, radius_minor, segs_major, segs_minor):
    """
    Тор с треугольной сеткой.
    Каждый quad разбивается на 2 треугольника.
    Возвращает (points, polys).
    """
    verts = []
    for j in range(segs_major):
        phi = j / segs_major * 2.0 * math.pi
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        for i in range(segs_minor):
            theta = i / segs_minor * 2.0 * math.pi
            cos_theta = math.cos(theta)
            sin_theta = math.sin(theta)
            x = (radius_major + radius_minor * cos_theta) * cos_phi
            y = radius_minor * sin_theta
            z = (radius_major + radius_minor * cos_theta) * sin_phi
            verts.append(c4d.Vector(x, y, z))

    polys = []
    for j in range(segs_major):
        for i in range(segs_minor):
            v0 = j * segs_minor + i
            v1 = j * segs_minor + (i + 1) % segs_minor
            v2 = ((j + 1) % segs_major) * segs_minor + (i + 1) % segs_minor
            v3 = ((j + 1) % segs_major) * segs_minor + i
            # Треугольник 1: v0, v1, v2 (d=v2 — вырожденный quad)
            polys.append(c4d.CPolygon(v0, v1, v2, v2))
            # Треугольник 2: v0, v2, v3 (d=v3 — вырожденный quad)
            polys.append(c4d.CPolygon(v0, v2, v3, v3))

    return verts, polys


def build_brickplane(width, height, segs_w, segs_h):
    """
    Плоскость с кирпичной сеткой (running bond / половинное смещение).
    Нечётные ряды смещены на полшага по X.
    Рёбра на границах нечётных рядов разрезаются дополнительными вершинами.
    Возвращает (points, polys).
    """
    # Стратегия: для корректной топологии без T-стыков используем
    # сетку с двойным количеством вершин по X и треугольниками на стыках

    step_x = width  / segs_w
    step_y = height / segs_h

    # Строим полную сетку вершин: (segs_w*2 + 1) × (segs_h + 1)
    # Это даёт нам все нужные точки для смещённых рядов
    nx = segs_w * 2 + 1   # вершин по X
    ny = segs_h + 1        # вершин по Y (ряды)

    verts = []
    # Все вершины: каждый ряд чередует обычные и смещённые позиции
    for row in range(ny):
        y_pos = row / segs_h * height - height / 2.0
        for col in range(nx):
            # col идёт с шагом step_x/2
            x_pos = col * (step_x / 2.0) - width / 2.0
            verts.append(c4d.Vector(x_pos, 0.0, y_pos))

    polys = []
    for row in range(segs_h):
        if row % 2 == 0:
            # Чётный ряд: кирпичи начинаются с 0, каждый кирпич = 2 шага по X
            for brick in range(segs_w):
                # Нижние вершины кирпича (в глобальной сетке col*2 и col*2+2)
                bl = row * nx + brick * 2
                br = row * nx + brick * 2 + 2
                tl = (row + 1) * nx + brick * 2
                tr = (row + 1) * nx + brick * 2 + 2
                # Средние вершины на верхнем и нижнем ребре
                bm = row * nx + brick * 2 + 1
                tm = (row + 1) * nx + brick * 2 + 1

                # Полный кирпич = quad (bl, br, tr, tl)
                # Но нам нужны средние точки для стыковки с нечётным рядом
                # Нижняя половина кирпича
                polys.append(c4d.CPolygon(bl, bm, tm, tl))
                polys.append(c4d.CPolygon(bm, br, tr, tm))
        else:
            # Нечётный ряд: смещение на полкирпича
            # Первый полукирпич у левого края
            bl = row * nx + 0
            br = row * nx + 1
            tl = (row + 1) * nx + 0
            tr = (row + 1) * nx + 1
            polys.append(c4d.CPolygon(bl, br, tr, tl))

            # Полные кирпичи в середине
            for brick in range(segs_w - 1):
                col_start = brick * 2 + 1
                bl = row * nx + col_start
                br = row * nx + col_start + 2
                tl = (row + 1) * nx + col_start
                tr = (row + 1) * nx + col_start + 2
                bm = row * nx + col_start + 1
                tm = (row + 1) * nx + col_start + 1
                polys.append(c4d.CPolygon(bl, bm, tm, tl))
                polys.append(c4d.CPolygon(bm, br, tr, tm))

            # Последний полукирпич у правого края
            col_start = (segs_w - 1) * 2 + 1
            bl = row * nx + col_start
            br = row * nx + col_start + 1
            tl = (row + 1) * nx + col_start
            tr = (row + 1) * nx + col_start + 1
            polys.append(c4d.CPolygon(bl, br, tr, tl))

    return verts, polys


# ─── Создание PolygonObject из вершин и полигонов ─────────────────────────────

def _make_poly_object(points, polys, name):
    """Создаёт c4d.PolygonObject, заполняет вершины и полигоны."""
    obj = c4d.PolygonObject(len(points), len(polys))
    obj.SetName(name)
    for i, pt in enumerate(points):
        obj.SetPoint(i, pt)
    for i, poly in enumerate(polys):
        obj.SetPolygon(i, poly)
    obj.Message(c4d.MSG_UPDATE)
    return obj


# ─── Базовый класс плагина ───────────────────────────────────────────────────

class _MeshPrimitiveBase(c4d.plugins.ObjectData):
    """
    Базовый класс для всех mesh-примитивов.
    Подклассы определяют:
      OBJECT_NAME   — имя объекта по умолчанию
      _first_ud_id  — SubID первого поля UserData (для проверки инициализации)
      _create_ud()  — создание UserData-полей
      _set_defaults() — установка значений по умолчанию
      _build_mesh() — генерация (points, polys)
    """

    OBJECT_NAME  = "MeshPrimitive"
    _first_ud_id = TC_SIZE   # переопределяется в подклассах

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
        if not _ud_already_created(op, self._first_ud_id):
            grp_subid = _add_group(op, "Параметры")
            self._create_ud(op, grp_subid)
            self._set_defaults(op)
        return True

    def GetVirtualObjects(self, op, hh):
        if not _ud_already_created(op, self._first_ud_id):
            grp_subid = _add_group(op, "Параметры")
            self._create_ud(op, grp_subid)
            self._set_defaults(op)

        points, polys = self._build_mesh(op)
        return _make_poly_object(points, polys, self.OBJECT_NAME)

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription(op.GetType()):
            return False, flags
        if not _ud_already_created(op, self._first_ud_id):
            grp_subid = _add_group(op, "Параметры")
            self._create_ud(op, grp_subid)
            self._set_defaults(op)
        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK

    # Переопределить в подклассах:
    def _create_ud(self, op, grp_subid):
        pass

    def _set_defaults(self, op):
        pass

    def _build_mesh(self, op):
        return [], []


# ─── TriCube ──────────────────────────────────────────────────────────────────

class TriCubeObject(_MeshPrimitiveBase):
    """Куб с треугольной сеткой."""

    OBJECT_NAME  = "TriCube"
    _first_ud_id = TC_SIZE

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Размер", 200.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Подразделения", 3, 1, 50))

    def _set_defaults(self, op):
        _ud_set_default(op, TC_SIZE,    200.0)
        _ud_set_default(op, TC_SUBDIVS, 3)

    def _build_mesh(self, op):
        size    = _ud_get(op, TC_SIZE,    200.0)
        subdivs = _ud_get(op, TC_SUBDIVS, 3)
        subdivs = max(1, int(subdivs))
        return build_tricube(size, subdivs)


# ─── HexSphere ────────────────────────────────────────────────────────────────

class HexSphereObject(_MeshPrimitiveBase):
    """Сфера с гексагональной/пятиугольной сеткой (dual icosphere)."""

    OBJECT_NAME  = "HexSphere"
    _first_ud_id = HS_RADIUS

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Радиус", 100.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Подразделения", 2, 1, 5))

    def _set_defaults(self, op):
        _ud_set_default(op, HS_RADIUS, 100.0)
        _ud_set_default(op, HS_SUBDIV, 2)

    def _build_mesh(self, op):
        radius = _ud_get(op, HS_RADIUS, 100.0)
        subdiv = _ud_get(op, HS_SUBDIV, 2)
        subdiv = max(1, min(5, int(subdiv)))  # ограничиваем: при 5 уже 20480 граней
        return build_hexsphere(radius, subdiv)


# ─── DiamondCylinder ─────────────────────────────────────────────────────────

class DiamondCylinderObject(_MeshPrimitiveBase):
    """Цилиндр с ромбической сеткой."""

    OBJECT_NAME  = "DiamondCylinder"
    _first_ud_id = DC_RADIUS

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Радиус", 100.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Высота", 200.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Сегменты (окружность)", 12, 3, 200))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Сегменты (высота)", 6, 1, 200))
        _add_in_group(op, grp_subid, _make_bool_bc(
            "Крышки", True))

    def _set_defaults(self, op):
        _ud_set_default(op, DC_RADIUS, 100.0)
        _ud_set_default(op, DC_HEIGHT, 200.0)
        _ud_set_default(op, DC_SEGS_R, 12)
        _ud_set_default(op, DC_SEGS_H, 6)
        _ud_set_default(op, DC_CAPS,   True)

    def _build_mesh(self, op):
        radius = _ud_get(op, DC_RADIUS, 100.0)
        height = _ud_get(op, DC_HEIGHT, 200.0)
        segs_r = max(3,  int(_ud_get(op, DC_SEGS_R, 12)))
        segs_h = max(1,  int(_ud_get(op, DC_SEGS_H, 6)))
        caps   = bool(_ud_get(op, DC_CAPS, True))
        return build_diamond_cylinder(radius, height, segs_r, segs_h, caps)


# ─── TriTorus ─────────────────────────────────────────────────────────────────

class TriTorusObject(_MeshPrimitiveBase):
    """Тор с треугольной сеткой."""

    OBJECT_NAME  = "TriTorus"
    _first_ud_id = TT_RADIUS_MAJOR

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Радиус (большой)", 150.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Радиус (малый)", 50.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Сегменты (кольцо)", 24, 3, 500))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Сегменты (труба)", 12, 3, 500))

    def _set_defaults(self, op):
        _ud_set_default(op, TT_RADIUS_MAJOR, 150.0)
        _ud_set_default(op, TT_RADIUS_MINOR,  50.0)
        _ud_set_default(op, TT_SEGS_MAJOR,    24)
        _ud_set_default(op, TT_SEGS_MINOR,    12)

    def _build_mesh(self, op):
        r_major    = _ud_get(op, TT_RADIUS_MAJOR, 150.0)
        r_minor    = _ud_get(op, TT_RADIUS_MINOR,  50.0)
        segs_major = max(3, int(_ud_get(op, TT_SEGS_MAJOR, 24)))
        segs_minor = max(3, int(_ud_get(op, TT_SEGS_MINOR, 12)))
        return build_tritorus(r_major, r_minor, segs_major, segs_minor)


# ─── BrickPlane ───────────────────────────────────────────────────────────────

class BrickPlaneObject(_MeshPrimitiveBase):
    """Плоскость с кирпичной сеткой (running bond)."""

    OBJECT_NAME  = "BrickPlane"
    _first_ud_id = BP_WIDTH

    def _create_ud(self, op, grp_subid):
        _add_in_group(op, grp_subid, _make_float_bc(
            "Ширина", 400.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Высота", 400.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Кирпичей (X)", 4, 1, 200))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Рядов (Y)", 4, 1, 200))

    def _set_defaults(self, op):
        _ud_set_default(op, BP_WIDTH,  400.0)
        _ud_set_default(op, BP_HEIGHT, 400.0)
        _ud_set_default(op, BP_SEGS_W, 4)
        _ud_set_default(op, BP_SEGS_H, 4)

    def _build_mesh(self, op):
        w      = _ud_get(op, BP_WIDTH,  400.0)
        h      = _ud_get(op, BP_HEIGHT, 400.0)
        segs_w = max(1, int(_ud_get(op, BP_SEGS_W, 4)))
        segs_h = max(1, int(_ud_get(op, BP_SEGS_H, 4)))
        return build_brickplane(w, h, segs_w, segs_h)


_ICON_B64_1 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAoUlEQVR42mOQUdCi"
    "KWIYtWDUAlpY4NZzB4JoYgHcdGrZQV8L0EzHhci0AL+hKas+QBBBO/7v0yDNAoi5"
    "IiJyEATh4jEdgoi1AM10PHbAzYWTEAZhC5DNRWbjChk0Bj4L0Ezccuc/LjuQwwSN"
    "TZQFENMhCC5YseAEUBeQhIc7VjSgPqB5HNAjFVEzH+DPzMg5GX/ZgDMnj9ZooxaM"
    "WjB0LQAA/SmnUKnI7oUAAAAASUVORK5CYII="
)

def _make_icon_1():
    png_data = base64.b64decode(_ICON_B64_1)
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

ICO_P_1 = _make_icon_1()

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    primitives = [
        (ID_TRICUBE,
         "TriCube",
         TriCubeObject,
         "Куб с треугольной сеткой"),
         ICO_P_1,

        (ID_HEXSPHERE,
         "HexSphere",
         HexSphereObject,
         "Сфера с гексагональной сеткой (dual icosphere)"),
         ICO_P_1,

        (ID_DIAMONDCYLINDER,
         "DiamondCylinder",
         DiamondCylinderObject,
         "Цилиндр с ромбической сеткой"),
         ICO_P_1,

        (ID_TRITORUS,
         "TriTorus",
         TriTorusObject,
         "Тор с треугольной сеткой"),
         ICO_P_1,

        (ID_BRICKPLANE,
         "BrickPlane",
         BrickPlaneObject,
         "Плоскость с кирпичной сеткой"),
         ICO_P_1,
    ]

    for plugin_id, name, cls, help_text, ico in primitives:
        c4d.plugins.RegisterObjectPlugin(
            id          = plugin_id,
            str         = name,
            g           = cls,
            description = "",
            icon        = ico,
            info        = c4d.OBJECT_GENERATOR,
        )
