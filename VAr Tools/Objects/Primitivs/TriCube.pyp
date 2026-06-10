# -*- coding: utf-8 -*-
"""
TriCube — Cinema 4D ObjectData Plugin
Куб с треугольной сеткой.
"""

import c4d
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_TRICUBE = 1068871

NAME_TRICUBE = "TriCube v1.1"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# TriCube
TC_SIZE    = 2
TC_SUBDIVS = 3
TC_NOTRI   = 4   # Галочка "Квады" (выключить триангуляцию)


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


# ─── Генераторы мешей ─────────────────────────────────────────────────────────

def build_tricube(size, subdivs, triangulate=True):
    """
    Куб с треугольной сеткой.
    Каждая из 6 граней делится на subdivs×subdivs ячеек,
    каждая ячейка — 2 треугольника (CPolygon с равными c и d = вырожденный квад).
    При triangulate=False ячейки остаются квадами.
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
                if triangulate:
                    # Треугольник 1: bl, br, tl  (d=tl — вырожденный)
                    all_polys.append(c4d.CPolygon(bl, br, tl, tl))
                    # Треугольник 2: br, tr, tl  (d=tl — вырожденный)
                    all_polys.append(c4d.CPolygon(br, tr, tl, tl))
                else:
                    # Квад: bl, br, tr, tl
                    all_polys.append(c4d.CPolygon(bl, br, tr, tl))

    return all_points, all_polys


# ─── Создание PolygonObject из вершин и полигонов ─────────────────────────────

def _make_poly_object(points, polys, name):
    """
    Создаёт c4d.PolygonObject.
    polys — список c4d.CPolygon или списков индексов вершин (n-гоны).
    """
    cpoly_list = []

    for item in polys:
        if isinstance(item, c4d.CPolygon):
            cpoly_list.append(item)
            continue
        cpoly_list.append(item)

    obj = c4d.PolygonObject(len(points), len(cpoly_list))
    obj.SetName(name)
    for i, pt in enumerate(points):
        obj.SetPoint(i, pt)
    for i, poly in enumerate(cpoly_list):
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
        _add_in_group(op, grp_subid, _make_bool_bc(
            "Триангуляция", True))

    def _set_defaults(self, op):
        _ud_set_default(op, TC_SIZE,    200.0)
        _ud_set_default(op, TC_SUBDIVS, 3)
        _ud_set_default(op, TC_NOTRI,   True)

    def _build_mesh(self, op):
        size       = _ud_get(op, TC_SIZE,    200.0)
        subdivs    = _ud_get(op, TC_SUBDIVS, 3)
        triangulate = bool(_ud_get(op, TC_NOTRI, True))
        subdivs = max(1, int(subdivs))
        return build_tricube(size, subdivs, triangulate)


_ICON_TC = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABaUlEQVR4nGNkQALW+Q/+M9ABHJ2owAhjM9LTYmwOYRoIi5EB40D5HgYoDoEjE+QDKdHPQq7GQFd5DPb63Q9p7wBki3HJkeIQohyAz1JC6gk5Bq8DSLUYnxm4HII1FxyZIG+MxJWj2BUMDI9gDJuCh2eRJbCGgF78KbiiSwvNkB3D0LuVAcWAYm+GwN6tDOvRxFD0SPvthOtRVNJAsQtrCHx6/xLDUfFhZlgNZ4CE0CNkAZgj+2buxDAH3QFE54KFq05BHWCGLvUIXQCbxbgAQQegRwFy9MSHmcGjANnSp5vccUYBOiCYCJEtxOVAfBagO4jiREjIQdgAvkRIMArQLUR3EKWA6FyAC2BzEL4oITsX4APoFpKSCKniAFIcRFQi5BMUZ2BgIC0qCDkIPejxOoCaDsFlMVEOQHcIsY4hZCnJDsDmGGwOIcVish2A7hByLYaBod8qHnUAxQ5A7ijSGwyOviEyZyC65wBPfJoHhPNNrQAAAABJRU5ErkJggg=="
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


ICO_TC = _make_icon_tc()

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_TRICUBE,
        str         = NAME_TRICUBE,
        g           = TriCubeObject,
        description = "",
        icon        = ICO_TC,
        info        = c4d.OBJECT_GENERATOR,
    )
