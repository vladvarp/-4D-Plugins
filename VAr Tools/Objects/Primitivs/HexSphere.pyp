# -*- coding: utf-8 -*-
"""
HexSphere — Cinema 4D ObjectData Plugin
Сфера с настраиваемым числом углов (3–16).
"""

import c4d
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_HEXSPHERE = 1068872

NAME_HEXSPHERE = "HexSphere v1.2"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# HexSphere
HS_RADIUS  = 2
HS_SUBDIV  = 3
HS_SIDES   = 4


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
    bc[c4d.DESC_DEFAULT]    = 1  # развёрнута по умолчанию
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

def _icosphere_tri_mesh(subdivisions):
    """
    Икосаэдр с midpoint-подразделением.
    Возвращает (verts, faces) — списки 3D-точек и треугольных граней.
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

    return verts, faces


def _dual_mesh_from_tris(verts, faces):
    """
    Dual mesh треугольной сетки на сфере.
    Возвращает (dual_verts, dual_polys) — списки точек и индексов n-гранных полигонов.
    """
    n_verts = len(verts)

    dual_verts = []
    for f in faces:
        cx = (verts[f[0]][0] + verts[f[1]][0] + verts[f[2]][0]) / 3.0
        cy = (verts[f[0]][1] + verts[f[1]][1] + verts[f[2]][1]) / 3.0
        cz = (verts[f[0]][2] + verts[f[1]][2] + verts[f[2]][2]) / 3.0
        dual_verts.append(list(_normalize((cx, cy, cz))))

    vert_to_faces = [[] for _ in range(n_verts)]
    for fi, f in enumerate(faces):
        for vi in f:
            vert_to_faces[vi].append(fi)

    dual_polys = []
    for vi in range(n_verts):
        adj = vert_to_faces[vi]
        if len(adj) < 3:
            continue

        nx, ny, nz = verts[vi][0], verts[vi][1], verts[vi][2]

        if abs(nx) < 0.9:
            tx, ty, tz = 1.0, 0.0, 0.0
        else:
            tx, ty, tz = 0.0, 1.0, 0.0
        dot = tx*nx + ty*ny + tz*nz
        tx -= dot*nx;  ty -= dot*ny;  tz -= dot*nz
        td = math.sqrt(tx**2 + ty**2 + tz**2)
        tx /= td;  ty /= td;  tz /= td

        bx = ny*tz - nz*ty
        by = nz*tx - nx*tz
        bz = nx*ty - ny*tx

        def _face_angle(fi, _nx=nx, _ny=ny, _nz=nz,
                         _tx=tx, _ty=ty, _tz=tz,
                         _bx=bx, _by=by, _bz=bz):
            dvx = dual_verts[fi][0] - _nx
            dvy = dual_verts[fi][1] - _ny
            dvz = dual_verts[fi][2] - _nz
            u = dvx*_tx + dvy*_ty + dvz*_tz
            v = dvx*_bx + dvy*_by + dvz*_bz
            return math.atan2(v, u)

        ordered = sorted(adj, key=_face_angle)
        dual_polys.append(_ensure_outward_winding(ordered, dual_verts))

    return dual_verts, dual_polys


def _scale_verts_to_radius(verts, radius):
    return [c4d.Vector(v[0]*radius, v[1]*radius, v[2]*radius) for v in verts]


def _as_vector(p):
    if isinstance(p, c4d.Vector):
        return p
    return c4d.Vector(p[0], p[1], p[2])


def _ensure_outward_winding(indices, points):
    """Разворачивает полигон, если нормаль смотрит к центру сферы (origin)."""
    if len(indices) < 3:
        return list(indices)
    p0 = _as_vector(points[indices[0]])
    p1 = _as_vector(points[indices[1]])
    p2 = _as_vector(points[indices[2]])
    normal = (p1 - p0).Cross(p2 - p0)
    centroid = c4d.Vector()
    for idx in indices:
        centroid += _as_vector(points[idx])
    centroid /= float(len(indices))
    if normal.Dot(centroid) < 0.0:
        return list(reversed(indices))
    return list(indices)


def _build_tri_sphere(radius, subdivisions):
    """Геодезическая сфера из треугольников (икосаэдр + подразделение)."""
    verts, faces = _icosphere_tri_mesh(subdivisions)
    return _scale_verts_to_radius(verts, radius), faces


def _build_dual_icosphere(radius, subdivisions):
    """
    Сфера с гексагональной/пятиугольной сеткой (dual icosphere).
    12 пятиугольников + шестиугольники.
    """
    verts, faces = _icosphere_tri_mesh(subdivisions)
    dual_verts, dual_polys = _dual_mesh_from_tris(verts, faces)
    return _scale_verts_to_radius(dual_verts, radius), dual_polys


def _build_quad_sphere(radius, subdivisions):
    """Сфера из четырёхугольников (куб + сетка на гранях, проекция на сферу)."""
    face_axes = [
        (( 1, 0, 0), ( 0, 1, 0), +1, (0, 0, 1)),
        ((-1, 0, 0), ( 0, 1, 0), -1, (0, 0, 1)),
        (( 0, 0,-1), ( 0, 1, 0), +1, (1, 0, 0)),
        (( 0, 0, 1), ( 0, 1, 0), -1, (1, 0, 0)),
        (( 1, 0, 0), ( 0, 0,-1), +1, (0, 1, 0)),
        (( 1, 0, 0), ( 0, 0, 1), -1, (0, 1, 0)),
    ]

    all_points = []
    all_polys  = []

    for (ux, uy, uz), (vx, vy, vz), w_sign, (wx, wy, wz) in face_axes:
        base = len(all_points)
        n = subdivisions + 1

        for row in range(n):
            v_t = (row / subdivisions) * 2.0 - 1.0
            for col in range(n):
                u_t = (col / subdivisions) * 2.0 - 1.0
                x = ux*u_t + vx*v_t + wx*w_sign
                y = uy*u_t + vy*v_t + wy*w_sign
                z = uz*u_t + vz*v_t + wz*w_sign
                nx, ny, nz = _normalize((x, y, z))
                all_points.append(c4d.Vector(nx*radius, ny*radius, nz*radius))

        for row in range(subdivisions):
            for col in range(subdivisions):
                bl = base + row*n + col
                br = base + row*n + (col+1)
                tl = base + (row+1)*n + col
                tr = base + (row+1)*n + (col+1)
                all_polys.append([bl, br, tr, tl])

    return all_points, all_polys


def _build_penta_sphere(radius, subdivisions):
    """Сфера из пятиугольников (додекаэдр; при subdiv>1 — кольцевая сетка)."""
    if subdivisions > 1:
        return _build_banded_ngon_sphere(radius, 5, subdivisions)
    verts, faces = _icosphere_tri_mesh(0)
    dual_verts, dual_polys = _dual_mesh_from_tris(verts, faces)
    return _scale_verts_to_radius(dual_verts, radius), dual_polys


def _build_banded_ngon_sphere(radius, sides, subdivisions):
    """
    Сфера по меридианам (sides=7..16 и pentagon при subdiv>1).
    Квады между широтными кольцами, треугольники у полюсов.
    Плоские кольцевые n-гоны не строятся — они давали «внутренние» полигоны.
    """
    sides = max(3, int(sides))
    rings = max(1, int(subdivisions))

    points = []
    polys  = []

    south = len(points)
    points.append(c4d.Vector(0.0, -radius, 0.0))

    ring_starts = []
    for ring in range(1, rings + 1):
        t = ring / (rings + 1)
        lat = -math.pi * 0.5 + t * math.pi
        y = math.sin(lat)
        r = math.cos(lat)
        ring_starts.append(len(points))
        for seg in range(sides):
            ang = seg / sides * 2.0 * math.pi
            x = r * math.cos(ang)
            z = r * math.sin(ang)
            points.append(c4d.Vector(x*radius, y*radius, z*radius))

    north = len(points)
    points.append(c4d.Vector(0.0, radius, 0.0))

    first_ring = ring_starts[0]
    for seg in range(sides):
        a = first_ring + seg
        b = first_ring + (seg + 1) % sides
        polys.append(_ensure_outward_winding([south, a, b], points))

    for ring in range(len(ring_starts) - 1):
        start = ring_starts[ring]
        next_start = ring_starts[ring + 1]
        for seg in range(sides):
            bl = start + seg
            br = start + (seg + 1) % sides
            tl = next_start + seg
            tr = next_start + (seg + 1) % sides
            polys.append(_ensure_outward_winding([bl, br, tr, tl], points))

    last_ring = ring_starts[-1]
    for seg in range(sides):
        a = last_ring + seg
        b = last_ring + (seg + 1) % sides
        polys.append(_ensure_outward_winding([north, a, b], points))

    return points, polys


def build_hexsphere(radius, subdivisions, sides=6):
    """
    Сфера с управляемым числом углов полигона (3–16).
      3 — треугольники (геодезическая икосфера)
      4 — четырёхугольники (кубическая проекция)
      5 — пятиугольники (додекаэдр / кольцевая сетка)
      6 — гексагоны + 12 пятиугольников (dual icosphere)
      7–16 — сфера по меридианам (квады + полюса)
    Возвращает (points, poly_indices) — списки индексов вершин для каждого полигона.
    """
    sides = max(3, min(16, int(sides)))
    subdivisions = max(1, int(subdivisions))

    if sides == 3:
        return _build_tri_sphere(radius, subdivisions)
    if sides == 4:
        return _build_quad_sphere(radius, subdivisions)
    if sides == 5:
        return _build_penta_sphere(radius, subdivisions)
    if sides == 6:
        return _build_dual_icosphere(radius, subdivisions)
    return _build_banded_ngon_sphere(radius, sides, subdivisions)


# ─── Создание PolygonObject из вершин и полигонов ─────────────────────────────

def _rotate_ngon_for_fan(indices, points):
    """Ставит в начало вершину, ближайшую к центру n-гона (стабильный веер на сфере)."""
    if len(indices) <= 4:
        return indices
    cx = cy = cz = 0.0
    for idx in indices:
        p = _as_vector(points[idx])
        cx += p.x
        cy += p.y
        cz += p.z
    inv = 1.0 / len(indices)
    cx *= inv
    cy *= inv
    cz *= inv
    best_pos = 0
    best_d = 1e30
    for pos, idx in enumerate(indices):
        p = _as_vector(points[idx])
        d = (p.x - cx) ** 2 + (p.y - cy) ** 2 + (p.z - cz) ** 2
        if d < best_d:
            best_d = d
            best_pos = pos
    if best_pos == 0:
        return indices
    return indices[best_pos:] + indices[:best_pos]


def _indices_to_cpolygons(indices, points=None):
    """Конвертирует список индексов n-гона в CPolygon(ы) без лишней триангуляции."""
    if points is not None:
        indices = _rotate_ngon_for_fan(indices, points)
    n = len(indices)
    if n == 3:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[2])]
    if n == 4:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[3])]
    hub = indices[0]
    return [
        c4d.CPolygon(hub, indices[k], indices[k + 1], indices[k + 1])
        for k in range(1, n - 1)
    ]


def _fan_hidden_edge_indices(poly_start, n):
    """Индексы внутренних рёбер веерной триангуляции n-гона (для N-gon в C4D)."""
    hidden = []
    for t in range(n - 2):
        pi = poly_start + t
        if t > 0:
            hidden.append(4 * pi + 0)
        if t < n - 3:
            hidden.append(4 * pi + 2)
    return hidden


def _make_poly_object(points, polys, name):
    """
    Создаёт c4d.PolygonObject.
    polys — список c4d.CPolygon или списков индексов вершин (n-гоны).
    """
    cpoly_list = []
    hidden_edges = []

    for item in polys:
        if isinstance(item, c4d.CPolygon):
            cpoly_list.append(item)
            continue
        start = len(cpoly_list)
        indices = _ensure_outward_winding(list(item), points)
        new_polys = _indices_to_cpolygons(indices, points)
        if len(indices) > 4:
            hidden_edges.extend(_fan_hidden_edge_indices(start, len(indices)))
        cpoly_list.extend(new_polys)

    obj = c4d.PolygonObject(len(points), len(cpoly_list))
    obj.SetName(name)
    for i, pt in enumerate(points):
        obj.SetPoint(i, pt)
    for i, poly in enumerate(cpoly_list):
        obj.SetPolygon(i, poly)

    if hidden_edges:
        edge_h = obj.GetEdgeH()
        for eid in hidden_edges:
            edge_h.Select(eid)

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
    _first_ud_id = HS_RADIUS   # переопределяется в подклассах

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
        _add_in_group(op, grp_subid, _make_int_bc(
            "Углов", 6, 3, 16))

    def _set_defaults(self, op):
        _ud_set_default(op, HS_RADIUS, 100.0)
        _ud_set_default(op, HS_SUBDIV, 2)
        _ud_set_default(op, HS_SIDES, 6)

    def _build_mesh(self, op):
        radius = _ud_get(op, HS_RADIUS, 100.0)
        subdiv = _ud_get(op, HS_SUBDIV, 2)
        sides  = _ud_get(op, HS_SIDES, 6)
        subdiv = max(1, min(5, int(subdiv)))  # ограничиваем: при 5 уже 20480 граней
        sides  = max(3, min(16, int(sides)))
        return build_hexsphere(radius, subdiv, sides)


_ICON_HS = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABOklEQVR4nNVXMRKDIBBEJ72ljeML4nvMA+wt7GJtOgt7HxDfY17g2Fj6gqRy5gbugMNEzFbiAbvK3gGBALg+729xAF63R7A9B0cSY0JCH8QQga+v33BxGbTOC/o+SuLfCaBIqT62Yqw8YEPuOsYowIWcM5YUMOZNuYccihjzpqTiZBZ8gxyC8gT6B3TkU9WTX6OLUXOyCpGOgNPHScBU9WXaFp2JJG2LjiNCqQPYr9omxERAQhP5Oi+KFxQTmswHRWCiYAyDLGD3ZmQiNMH7bvjfAqaqL2XTcdNQyYIoibWZILtejm1tzBtYNURLMZUJMhE3jglgLYGN47lZcc7NSAi+mXTQzUUKyIaaVdN15NlQk8tidSp2XQ4TubUAFxG2h1LrUzGc0MuxfC8RhRBeFI/GOe6GsOHjev4BeqjHFj+lkcgAAAAASUVORK5CYII="
)

def _make_icon_hs():
    png_data = base64.b64decode(_ICON_HS)
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


ICO_HS = _make_icon_hs()

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_HEXSPHERE,
        str         = NAME_HEXSPHERE,
        g           = HexSphereObject,
        description = "",
        icon        = ICO_HS,
        info        = c4d.OBJECT_GENERATOR,
    )
