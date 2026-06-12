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

NAME_TRITORUS = "Tri Torus v1.1"

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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABwUlEQVR4nMVXMY6EMAw0p+vzg1VOome/QMVLqNLcvYRtqHgJFV+465E24ge84LYhyATbOOhudxogCvZkHNtJBgjfn/YXnoDrzWfhPXumY4rI2yscY2RnVm9zCwAAxg313JZdGPejTybwnupUO0dLRhUCjfOz/7AEiuZe29yyhowbKgCYlidLwuYWiuZeJxOY27Izbtj9aNxQGTdUc1v2AHCZ27IPYwzRzT6JIe6BQGJ5VstYT8zrA7noW3TOEsCyB+eUYy2RYJPamLsQCDFn40hgDc2R7cM0xKvHkvrRA3x9rPJyteEISZVwbsvOj56UMoxj55QKIoFYIm3sUxD7SFJAU93iOUcqsAT+Y/UUNs0oqlgTAFzw5B+06STY3MZZw9raEMDxoRTQNpgUO1IpVuWx5FyDDYEz/VyCRkUxC2IVjBvYDhnGEyum/kASVzhOatRFJ00W7RQQ8njiiFEkqLlUiEkF/Ojj2s52OYLQOmfXOwiIIYhll4hQY/g8wflgT8VFcz/saniDHqhSc0VMdSyXcltaoSatVc3oTH3Q/qNOQ2yQU+TUxeR688m3I+yoOOkY4I/uhtoOySHDH6+4nj8AZLs/JIvrX8wAAAAASUVORK5CYII="
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
