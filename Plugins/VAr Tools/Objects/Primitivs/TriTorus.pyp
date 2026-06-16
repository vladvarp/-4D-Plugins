# -*- coding: utf-8 -*-
"""
TriTorus — Cinema 4D ObjectData Plugin
Тор с треугольной сеткой.
"""

import c4d
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_TRITORUS = 1068874

NAME_TRITORUS = "Tri Torus v1.1.1"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# TriTorus
TT_RADIUS_MAJOR = 2
TT_RADIUS_MINOR = 3
TT_SEGS_MAJOR   = 4
TT_SEGS_MINOR   = 5
TT_NOTRI        = 6   # Галочка "Квады" (выключить триангуляцию)


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

def build_tritorus(radius_major, radius_minor, segs_major, segs_minor, triangulate=True):
    """
    Тор с треугольной сеткой.
    Каждый quad разбивается на 2 треугольника.
    При triangulate=False ячейки остаются квадами.
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
            if triangulate:
                # Треугольник 1: v0, v1, v2 (d=v2 — вырожденный quad)
                polys.append(c4d.CPolygon(v0, v1, v2, v2))
                # Треугольник 2: v0, v2, v3 (d=v3 — вырожденный quad)
                polys.append(c4d.CPolygon(v0, v2, v3, v3))
            else:
                # Квад: v0, v1, v2, v3
                polys.append(c4d.CPolygon(v0, v1, v2, v3))

    return verts, polys


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
    _first_ud_id = TT_RADIUS_MAJOR   # переопределяется в подклассах

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


# ─── TriTorus ─────────────────────────────────────────────────────────────────

class TriTorusObject(_MeshPrimitiveBase):
    """Тор с треугольной сеткой."""

    OBJECT_NAME  = "Tri Torus"
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
        _add_in_group(op, grp_subid, _make_bool_bc(
            "Триангуляция", True))

    def _set_defaults(self, op):
        _ud_set_default(op, TT_RADIUS_MAJOR, 150.0)
        _ud_set_default(op, TT_RADIUS_MINOR,  50.0)
        _ud_set_default(op, TT_SEGS_MAJOR,    24)
        _ud_set_default(op, TT_SEGS_MINOR,    12)
        _ud_set_default(op, TT_NOTRI,         True)

    def _build_mesh(self, op):
        r_major     = _ud_get(op, TT_RADIUS_MAJOR, 150.0)
        r_minor     = _ud_get(op, TT_RADIUS_MINOR,  50.0)
        segs_major  = max(3, int(_ud_get(op, TT_SEGS_MAJOR, 24)))
        segs_minor  = max(3, int(_ud_get(op, TT_SEGS_MINOR, 12)))
        triangulate = bool(_ud_get(op, TT_NOTRI, True))
        return build_tritorus(r_major, r_minor, segs_major, segs_minor, triangulate)


_ICON_TT = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzM6NTMrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzM6NTMrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjI5YjMxZWUxLWYxODItMDQ0OS04OTkwLTNjNWUwNzJiNDg2NSIgeG1wTU06RG9jdW1lbnRJRD0i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"
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

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_TRITORUS,
        str         = NAME_TRITORUS,
        g           = TriTorusObject,
        description = "",
        icon        = ICO_TT,
        info        = c4d.OBJECT_GENERATOR,
    )
