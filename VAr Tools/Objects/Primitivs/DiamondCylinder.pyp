# -*- coding: utf-8 -*-
"""
DiamondCylinder — Cinema 4D ObjectData Plugin
Цилиндр с ромбической сеткой (смещённые ряды).
"""

import c4d
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_DIAMONDCYLINDER = 1068873

NAME_DIAMONDCYLINDER = "DiamondCylinder v1.1"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# DiamondCylinder
DC_RADIUS  = 2
DC_HEIGHT  = 3
DC_SEGS_R  = 4
DC_SEGS_H  = 5
DC_CAPS    = 6


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
    _first_ud_id = DC_RADIUS   # переопределяется в подклассах

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


_ICON_DC = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVElEQVR4nGNkQAIb/A79Z6ADCNhkxwhjM9LTYmwOYRoIi5EB40D5HgYGPARGHcBCqgYFJTW88g/u3aKNAwhZjK6OWIcQdACxFpPrEIJpQL9f3F2/X9wdiV+JJo+Vj64PFyAYAhcLX+6EGYjsKJg4shg+eVyAYEF05/k9BgYGBgYXaw+Y4ZUXC1+2o/sOyaGVFwtftu85uoOBgYGBQUVSCa8DiE6EuHyIzUH6/eLue8wYqBMC/httYQYbEetYKDjHwMDAsNH/MF6HEB0FxafiUYK812zhTqh4Za/ZwnZc8oSigGgHwAAhC2HyMHGqOWDAQmA0DQzaNFCt37+TgYGBofViYWW1fn9768XCoZkGCJaEMJ/CAMzHxPLNFEzwmj/gLSKCUXDqwRmKLCAUAgSjAGYAqQ4hZDHRDiDVIcRaTLIDyLWAEGBC7ijSGwyOviEyZyC65wCo9fAZJ/PIvAAAAABJRU5ErkJggg=="
)

def _make_icon_dc():
    png_data = base64.b64decode(_ICON_DC)
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


ICO_DC = _make_icon_dc()

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_DIAMONDCYLINDER,
        str         = NAME_DIAMONDCYLINDER,
        g           = DiamondCylinderObject,
        description = "",
        icon        = ICO_DC,
        info        = c4d.OBJECT_GENERATOR,
    )
