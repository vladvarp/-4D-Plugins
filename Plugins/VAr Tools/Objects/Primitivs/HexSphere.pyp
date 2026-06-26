# -*- coding: utf-8 -*-
"""
HexSphere — Cinema 4D ObjectData Plugin
Сфера с настраиваемым числом углов (3–16).
"""

import c4d # type: ignore
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_HEXSPHERE = 1068872

NAME_HEXSPHERE = "Hex Sphere v1.4.1"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# HexSphere
HS_RADIUS  = 2
HS_SUBDIV  = 3
HS_SIDES   = 4

# ─── Description-based parameter IDs ──────────────────────────────────
HS_GRP        = 2000
HS_D_RADIUS   = 2001
HS_D_SUBDIV   = 2002
HS_D_SIDES    = 2003

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
    Использует Description-систему для UI (вкладки в Attributes Manager).
    Подклассы определяют:
      OBJECT_NAME     — имя объекта по умолчанию
      GetDDescription() — описание UI (вкладки и параметры)
      _set_defaults() — установка значений по умолчанию
      _build_mesh()   — генерация (points, polys)
    """

    OBJECT_NAME = "MeshPrimitive"

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
            self._set_defaults(op)
        return True

    def GetVirtualObjects(self, op, hh):
        points, polys = self._build_mesh(op)
        return _make_poly_object(points, polys, self.OBJECT_NAME)

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags
        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK

    def _set_defaults(self, op):
        pass

    def _build_mesh(self, op):
        return [], []


# ─── HexSphere ────────────────────────────────────────────────────────────────

class HexSphereObject(_MeshPrimitiveBase):
    """Сфера с гексагональной/пятиугольной сеткой (dual icosphere)."""

    OBJECT_NAME = "Hex Sphere"

    def _set_defaults(self, op):
        op[HS_D_RADIUS] = 100.0
        op[HS_D_SUBDIV] = 2
        op[HS_D_SIDES]  = 6

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HS_GRP, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid = c4d.DescID(c4d.DescLevel(HS_GRP, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Радиус"
        bc[c4d.DESC_DEFAULT]   = 100.0
        bc[c4d.DESC_MIN]       = 1.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HS_D_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Подразделения"
        bc[c4d.DESC_DEFAULT]   = 2
        bc[c4d.DESC_MIN]       = 1
        bc[c4d.DESC_MAX]       = 5
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 5
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HS_D_SUBDIV, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Углов"
        bc[c4d.DESC_DEFAULT]   = 6
        bc[c4d.DESC_MIN]       = 3
        bc[c4d.DESC_MAX]       = 16
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 16
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HS_D_SIDES, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def _build_mesh(self, op):
        radius = float(op[HS_D_RADIUS])
        subdiv = max(1, min(5, int(op[HS_D_SUBDIV])))
        sides  = max(3, min(16, int(op[HS_D_SIDES])))
        return build_hexsphere(radius, subdiv, sides)


_ICON_HS = (
    "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"
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
        description = "Obase",
        icon        = ICO_HS,
        info        = c4d.OBJECT_GENERATOR,
    )
