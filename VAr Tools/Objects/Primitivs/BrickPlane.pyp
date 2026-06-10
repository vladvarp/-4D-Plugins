# -*- coding: utf-8 -*-
"""
BrickPlane — Cinema 4D ObjectData Plugin
Плоскость с кирпичной сеткой (running bond).
"""

import c4d
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_BRICKPLANE = 1068875

NAME_BRICKPLANE = "BrickPlane v1.0"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

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


# ─── Генераторы мешей ─────────────────────────────────────────────────────────

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
    _first_ud_id = BP_WIDTH   # переопределяется в подклассах

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


_ICON_BP = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAApElEQVR4nO1XQQ6AIAzbCP8SH+ZFHwa+DE9LkCwyTKQe6AlIgcK6LGMqkELINAAhJZYxj7xYE+IQF5dg1OsF8B/w9cIS42HZeK7r1sM1C2htILqL7OFqgIcALkANgTW2vVwN8DTknPP+ROh1e4tbm9Zri4K3brecJ4CbEC7AE9mc/FVmwLNg1gK4CeECZi2YtQBuQriAWQtc2SiOxj96w3KCaM8vfQqEBgGNXZYAAAAASUVORK5CYII="
)

def _make_icon_bp():
    png_data = base64.b64decode(_ICON_BP)
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


ICO_BP = _make_icon_bp()

# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_BRICKPLANE,
        str         = NAME_BRICKPLANE,
        g           = BrickPlaneObject,
        description = "",
        icon        = ICO_BP,
        info        = c4d.OBJECT_GENERATOR,
    )
