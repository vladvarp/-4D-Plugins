# -*- coding: utf-8 -*-
"""
DiamondCylinder — Cinema 4D ObjectData Plugin
Цилиндр с ромбической сеткой (смещённые ряды).
"""

import c4d # type: ignore
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_DIAMONDCYLINDER = 1068873

NAME_DIAMONDCYLINDER = "Diamond Cylinder v1.6.1"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# DiamondCylinder
DC_RADIUS  = 2
DC_HEIGHT  = 3
DC_SEGS_R  = 4
DC_SEGS_H  = 5
DC_CAPS    = 6
DC_SURFACE = 7   # Тип поверхности (enum)
DC_TWIST        = 8   # Скрутка по оси Y (градусы)
DC_STAR_ENABLED = 9   # Галочка "Смещение (звезда)"
DC_STAR_OFFSET  = 10  # Величина радиального смещения чётных точек

# Значения для DC_SURFACE
SURF_ZIGZAG  = 0   # Зигзаг (ромбы) — исходный режим
SURF_SPIRAL  = 1   # Спираль
SURF_HEX     = 2   # Гексагональная сетка
SURF_DIAMOND = 3   # Прямые ромбы (без смещения рядов)


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


def _make_float_bc(name, default, minval, maxval, unit=c4d.DESC_UNIT_METER, step=1.0):
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


def _make_cycle_bc(name, default, items):
    """Создаёт поле-выпадающий список (CUSTOMDATATYPE_CYCLE / DTYPE_LONG).
    items — список строк в нужном порядке (индекс = значение).
    """
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME]       = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_DEFAULT]    = default
    bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
    bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
    cycle_bc = c4d.BaseContainer()
    for i, label in enumerate(items):
        cycle_bc[i] = label
    bc[c4d.DESC_CYCLE] = cycle_bc
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

def build_diamond_cylinder(radius, height, segs_r, segs_h, add_caps, twist=0.0, star_offset=0.0):
    """
    Цилиндр с ромбической сеткой.
    Нечётные ряды вершин смещены на полшага по углу — ячейки становятся ромбами.
    twist — угол скрутки по оси Y в радианах (0 = без скрутки).
    star_offset — величина радиального смещения чётных точек окружности наружу
                  (вид сверху: круг превращается в звезду/шестерёнку).
    Возвращает (points, polys).
    """
    verts = []

    # Боковая поверхность: segs_h+1 рядов, segs_r вершин на ряд
    for row in range(segs_h + 1):
        t = row / segs_h                      # [0, 1]
        y = t * height - height / 2.0
        # Нечётные ряды сдвигаем на полшага по углу
        offset_angle = (math.pi / segs_r) if (row % 2 == 1) else 0.0
        # Скрутка: линейно от 0 до twist по высоте цилиндра
        twist_angle = twist * t
        for col in range(segs_r):
            angle = col / segs_r * 2.0 * math.pi + offset_angle + twist_angle
            # Чётные точки (col % 2 == 0) смещаем наружу на star_offset — эффект звезды
            r = radius + (star_offset if col % 2 == 0 else 0.0)
            x = r * math.cos(angle)
            z = r * math.sin(angle)
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
                polys.append(c4d.CPolygon(curr, up_col, up_next, next_col))
            else:
                # Нечётный ряд → чётный: ромб вытянут влево-вверх
                polys.append(c4d.CPolygon(curr, up_col, up_next, next_col))

    if add_caps:
        # Нижняя крышка
        bottom_center_idx = len(verts)
        verts.append(c4d.Vector(0, -height/2.0, 0))
        for col in range(segs_r):
            a = col
            b = (col + 1) % segs_r
            # Нормаль вниз: CPolygon(center, a, b, b) — CCW вид снизу
            polys.append(c4d.CPolygon(bottom_center_idx, a, b, b))

        # Верхняя крышка (последний ряд вершин — индекс segs_h)
        top_center_idx = len(verts)
        verts.append(c4d.Vector(0, height/2.0, 0))
        top_row_start = segs_h * segs_r
        # У верхнего ряда может быть смещение, если segs_h нечётное
        for col in range(segs_r):
            a = top_row_start + col
            b = top_row_start + (col + 1) % segs_r
            # Нормаль вверх: CPolygon(center, b, a, a)
            polys.append(c4d.CPolygon(top_center_idx, b, a, a))

    return verts, polys


def build_spiral_cylinder(radius, height, segs_r, segs_h, add_caps, twist=0.0, star_offset=0.0):
    """
    Цилиндр со спиральной сеткой.
    Каждый ряд вершин повёрнут на фиксированный шаг — рёбра уходят по спирали.
    twist — угол скрутки по оси Y в радианах (0 = без скрутки).
    star_offset — величина радиального смещения чётных точек окружности наружу.
    Возвращает (points, polys).
    """
    verts = []

    # Угол поворота каждого ряда относительно предыдущего (один полный оборот за всю высоту)
    spiral_step = 2.0 * math.pi / segs_r / 2.0  # полшага на ряд → заметная спираль

    for row in range(segs_h + 1):
        t = row / segs_h
        y = t * height - height / 2.0
        base_angle = row * spiral_step
        # Скрутка: линейно от 0 до twist по высоте цилиндра
        twist_angle = twist * t
        for col in range(segs_r):
            angle = col / segs_r * 2.0 * math.pi + base_angle + twist_angle
            # Чётные точки (col % 2 == 0) смещаем наружу на star_offset — эффект звезды
            r = radius + (star_offset if col % 2 == 0 else 0.0)
            x = r * math.cos(angle)
            z = r * math.sin(angle)
            verts.append(c4d.Vector(x, y, z))

    polys = []

    for row in range(segs_h):
        for col in range(segs_r):
            curr     = row * segs_r + col
            next_col = row * segs_r + (col + 1) % segs_r
            up_col   = (row + 1) * segs_r + col
            up_next  = (row + 1) * segs_r + (col + 1) % segs_r
            polys.append(c4d.CPolygon(curr, up_col, up_next, next_col))

    if add_caps:
        bottom_center_idx = len(verts)
        verts.append(c4d.Vector(0, -height / 2.0, 0))
        for col in range(segs_r):
            a = col
            b = (col + 1) % segs_r
            polys.append(c4d.CPolygon(bottom_center_idx, a, b, b))

        top_center_idx = len(verts)
        verts.append(c4d.Vector(0, height / 2.0, 0))
        top_row_start = segs_h * segs_r
        for col in range(segs_r):
            a = top_row_start + col
            b = top_row_start + (col + 1) % segs_r
            polys.append(c4d.CPolygon(top_center_idx, b, a, a))

    return verts, polys


def build_hex_cylinder(radius, height, segs_r, segs_h, add_caps, twist=0.0, star_offset=0.0):
    """
    Цилиндр с гексагональной (шестиугольной) сеткой.
    Чётные ряды смещаются на полшага — образуются правильные шестиугольники.
    Каждая ячейка разбивается на два треугольника/четырёхугольника так, чтобы
    получалась классическая «кирпичная» укладка гексагонов.
    twist — угол скрутки по оси Y в радианах (0 = без скрутки).
    star_offset — величина радиального смещения чётных точек окружности наружу.
    Возвращает (points, polys).
    """
    # Гексагональная сетка на цилиндре: нечётные ряды сдвинуты на полшага,
    # каждый «гексагон» описывается двумя квадами (верхний и нижний треугольники).
    # Для segs_r кратного 2 результат наиболее правильный.
    verts = []

    for row in range(segs_h + 1):
        t = row / segs_h
        y = t * height - height / 2.0
        # Чётные ряды — сдвиг на полшага (противоположно zigzag)
        offset_angle = (math.pi / segs_r) if (row % 2 == 0) else 0.0
        # Скрутка: линейно от 0 до twist по высоте цилиндра
        twist_angle = twist * t
        for col in range(segs_r):
            angle = col / segs_r * 2.0 * math.pi + offset_angle + twist_angle
            # Чётные точки (col % 2 == 0) смещаем наружу на star_offset — эффект звезды
            r = radius + (star_offset if col % 2 == 0 else 0.0)
            x = r * math.cos(angle)
            z = r * math.sin(angle)
            verts.append(c4d.Vector(x, y, z))

    polys = []

    for row in range(segs_h):
        for col in range(segs_r):
            curr     = row * segs_r + col
            next_col = row * segs_r + (col + 1) % segs_r
            up_col   = (row + 1) * segs_r + col
            up_next  = (row + 1) * segs_r + (col + 1) % segs_r

            if row % 2 == 0:
                # Нижний ряд смещён → верхний нет:
                # левый треугольник + правый треугольник (имитация гексагона)
                polys.append(c4d.CPolygon(curr, up_col, next_col, next_col))
                polys.append(c4d.CPolygon(next_col, up_col, up_next, up_next))
            else:
                # Нижний ряд не смещён → верхний смещён:
                polys.append(c4d.CPolygon(curr, up_next, next_col, next_col))
                polys.append(c4d.CPolygon(curr, up_col, up_next, up_next))

    if add_caps:
        bottom_center_idx = len(verts)
        verts.append(c4d.Vector(0, -height / 2.0, 0))
        for col in range(segs_r):
            a = col
            b = (col + 1) % segs_r
            polys.append(c4d.CPolygon(bottom_center_idx, a, b, b))

        top_center_idx = len(verts)
        verts.append(c4d.Vector(0, height / 2.0, 0))
        top_row_start = segs_h * segs_r
        for col in range(segs_r):
            a = top_row_start + col
            b = top_row_start + (col + 1) % segs_r
            polys.append(c4d.CPolygon(top_center_idx, b, a, a))

    return verts, polys


def build_straight_cylinder(radius, height, segs_r, segs_h, add_caps, twist=0.0, star_offset=0.0):
    """
    Цилиндр с прямой сеткой (без смещения рядов).
    Классические прямоугольники / ровные колонки.
    twist — угол скрутки по оси Y в радианах (0 = без скрутки).
    star_offset — величина радиального смещения чётных точек окружности наружу.
    Возвращает (points, polys).
    """
    verts = []

    for row in range(segs_h + 1):
        t = row / segs_h
        y = t * height - height / 2.0
        # Скрутка: линейно от 0 до twist по высоте цилиндра
        twist_angle = twist * t
        for col in range(segs_r):
            angle = col / segs_r * 2.0 * math.pi + twist_angle
            # Чётные точки (col % 2 == 0) смещаем наружу на star_offset — эффект звезды
            r = radius + (star_offset if col % 2 == 0 else 0.0)
            x = r * math.cos(angle)
            z = r * math.sin(angle)
            verts.append(c4d.Vector(x, y, z))

    polys = []

    for row in range(segs_h):
        for col in range(segs_r):
            curr     = row * segs_r + col
            next_col = row * segs_r + (col + 1) % segs_r
            up_col   = (row + 1) * segs_r + col
            up_next  = (row + 1) * segs_r + (col + 1) % segs_r
            polys.append(c4d.CPolygon(curr, up_col, up_next, next_col))

    if add_caps:
        bottom_center_idx = len(verts)
        verts.append(c4d.Vector(0, -height / 2.0, 0))
        for col in range(segs_r):
            a = col
            b = (col + 1) % segs_r
            polys.append(c4d.CPolygon(bottom_center_idx, a, b, b))

        top_center_idx = len(verts)
        verts.append(c4d.Vector(0, height / 2.0, 0))
        top_row_start = segs_h * segs_r
        for col in range(segs_r):
            a = top_row_start + col
            b = top_row_start + (col + 1) % segs_r
            polys.append(c4d.CPolygon(top_center_idx, b, a, a))

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

    OBJECT_NAME  = "Diamond Cylinder"
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
        _add_in_group(op, grp_subid, _make_cycle_bc(
            "Тип поверхности", SURF_ZIGZAG,
            ["Зигзаг (ромбы)", "Спираль", "Гармошка", "Прямая сетка"]))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Скрутка (°)", 0.0, math.radians(-3600.0), math.radians(3600.0), unit=c4d.DESC_UNIT_DEGREE, step=math.radians(0.1)))
        _add_in_group(op, grp_subid, _make_bool_bc(
            "Смещение (звезда)", False))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Величина смещения", 20.0, 0.0, 100000.0, unit=c4d.DESC_UNIT_METER, step=1.0))

    def _set_defaults(self, op):
        _ud_set_default(op, DC_RADIUS, 100.0)
        _ud_set_default(op, DC_HEIGHT, 200.0)
        _ud_set_default(op, DC_SEGS_R, 12)
        _ud_set_default(op, DC_SEGS_H, 6)
        _ud_set_default(op, DC_CAPS,    True)
        _ud_set_default(op, DC_SURFACE, SURF_ZIGZAG)
        _ud_set_default(op, DC_TWIST,   0.0)
        _ud_set_default(op, DC_STAR_ENABLED, False)
        _ud_set_default(op, DC_STAR_OFFSET,  20.0)

    def _build_mesh(self, op):
        radius       = _ud_get(op, DC_RADIUS, 100.0)
        height       = _ud_get(op, DC_HEIGHT, 200.0)
        segs_r       = max(3,  int(_ud_get(op, DC_SEGS_R, 12)))
        segs_h       = max(1,  int(_ud_get(op, DC_SEGS_H, 6)))
        caps         = bool(_ud_get(op, DC_CAPS, True))
        surf         = int(_ud_get(op, DC_SURFACE, SURF_ZIGZAG))
        twist        = _ud_get(op, DC_TWIST, 0.0)  # скрутка по Y, хранится в радианах (C4D конвертирует из °)
        star_enabled = bool(_ud_get(op, DC_STAR_ENABLED, False))
        star_offset  = float(_ud_get(op, DC_STAR_OFFSET, 20.0))

        # Если смещение включено — segs_r должен быть чётным (звезда требует пар точек)
        if star_enabled and segs_r % 2 != 0:
            segs_r += 1

        # Если смещение выключено — передаём 0.0 чтобы не влияло на форму
        effective_star_offset = star_offset if star_enabled else 0.0

        if surf == SURF_SPIRAL:
            return build_spiral_cylinder(radius, height, segs_r, segs_h, caps, twist, effective_star_offset)
        elif surf == SURF_HEX:
            return build_hex_cylinder(radius, height, segs_r, segs_h, caps, twist, effective_star_offset)
        elif surf == SURF_DIAMOND:
            return build_straight_cylinder(radius, height, segs_r, segs_h, caps, twist, effective_star_offset)
        else:  # SURF_ZIGZAG (default)
            return build_diamond_cylinder(radius, height, segs_r, segs_h, caps, twist, effective_star_offset)


_ICON_DC = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzU6NTQrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzU6NTQrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjY5MWZjOWQ5LTU5ZTAtZmM0MC1iN2I1LTFiMDRkY2Y2YTJkMSIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDo2OTFmYzlkOS01OWUwLWZjNDAtYjdiNS0xYjA0ZGNmNmEyZDEiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDo2OTFmYzlkOS01OWUwLWZjNDAtYjdiNS0xYjA0ZGNmNmEyZDEiPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjY5MWZjOWQ5LTU5ZTAtZmM0MC1iN2I1LTFiMDRkY2Y2YTJkMSIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/Pu4pleQAAAOoSURBVFiF7ZdvSF1lHMc/v+cer1dnZBPNP5myuYET5l60loMgoy2abaNggVobFexN7UV/GBENDNaIYBuzXm9uZcFeJCYFe5PBtLGKcsp15b0uRznFdZeQ5tV7z/n14qrk8dx21JFv9oVzXjzP8zvfL7/n+3vO7xFVZTVhVpUdsNwDIuI/+rxmAfCcTPkNcWdcFg24BXR25pBXchQJ7EW1EJUgqMGtUwHEQXQGkVHUbic2/A61tRPLE/DDjVKCkxdByuYplEmEMdBxMDFUR2aDisDJA8lFKUBYA7MSVa+TWPMoDxX/5iUAVV3wAOzoat8Z6rnq0BtVegd/5kqkjqXiSqSO3sFf6I1q6Kd+Z0dX+05PPveANlfkx05t1ZEPt+tc0Erw+LcdT400P6J/nNqq2lyR7+ZbZEKAhLFIijAxbQIrFeCYGWObAKhALNN2z3t6IKunf8rGhGYCFjgaxTJvUrW+fUnM4cG9JPU4wvqgkySAE5/asinLnwl7IxOoCMIosC41owr8DWbWhBKDWRMiRaApE+IUgGTDfJ1cQylEVNm8IcfN57kFj/Xcm7nrcq5VMJ4R//Oe+L7XXh3ehiPPIlqEahlQnsrpHHT2pYowjfIrhs9PflRy+b6/Qu+O5Sayv9o2nvzGgyttBkrHMq2jp0uHVNiI4giEJcAr+z+WrvnFHgdRa4NuScBJoAYIKoy8t384L1o8lfTKQPotANi8IQegpV4PqfCGwINAEui2Qxx8+bREAM7v0+JJixNG2KMQAmJGOffCZxwWxP7395YlYA5NTRosi3LC2DSqkLu78hkAOq62Icq4E6D1egWvNzXJzIKP/ocATw/4xxL+G2ng62/YUq+HzjToUPkAcXE4qEKPHWJj3pE2yTvSJtkJShy4YBxeKh8g3tKgN8/V63FFb3uOrMyEHrgjJqw9O5Y4cCHfAlSF919slbf9ZMqNM416TJS3ADn75M1k54GCDN8mXNUM3C1D/7hbhotxR0xY8+mos/vSWim+ldFvweHnW+VLP5ly45NGrUvCBzfWJjZ11NzSSw2Fxp8J+wbjqJNJRvJhKiu/Xw75PH6MbMcy3ahOU10RcvN5e8CYXSBKIuO7ZTelfdE99EUGsKQbHAWe8FqWvi0Ph9dhB79e1JajoyC/Y2QUJVVeQg6OFgKlwP0L2nKRIZyJWqqrh2DZF5MHjoF5GrQIyCR9/SnKNCIjYH+xsouJH4TDqX6xquqa35DbCvi/seq3438AAm+eL8II8dsAAAAASUVORK5CYII="
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
