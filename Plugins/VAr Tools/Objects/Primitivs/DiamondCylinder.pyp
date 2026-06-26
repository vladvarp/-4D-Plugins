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

NAME_DIAMONDCYLINDER = "Diamond Cylinder v1.8.1"

# ─── Description-based parameter IDs ──────────────────────────────────────────────────

DC_GRP           = 2000
DC_D_RADIUS      = 2001
DC_D_HEIGHT      = 2002
DC_D_SEGS_R      = 2003
DC_D_SEGS_H      = 2004
DC_D_CAPS        = 2005
DC_D_SURFACE     = 2006
DC_D_TWIST       = 2007
DC_D_STAR_ENABLED = 2008
DC_D_STAR_OFFSET = 2009

# Значения для DC_SURFACE
SURF_ZIGZAG  = 0   # Зигзаг (ромбы) — исходный режим
SURF_SPIRAL  = 1   # Спираль
SURF_HEX     = 2   # Гексагональная сетка
SURF_DIAMOND = 3   # Прямые ромбы (без смещения рядов)


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


# ─── DiamondCylinder ─────────────────────────────────────────────────────────

class DiamondCylinderObject(_MeshPrimitiveBase):
    """Цилиндр с ромбической сеткой."""

    OBJECT_NAME = "Diamond Cylinder"

    def _set_defaults(self, op):
        op[DC_D_RADIUS]       = 100.0
        op[DC_D_HEIGHT]       = 200.0
        op[DC_D_SEGS_R]       = 12
        op[DC_D_SEGS_H]       = 6
        op[DC_D_CAPS]         = True
        op[DC_D_SURFACE]      = SURF_ZIGZAG
        op[DC_D_TWIST]        = 0.0
        op[DC_D_STAR_ENABLED] = False
        op[DC_D_STAR_OFFSET]  = 20.0

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_GRP, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid = c4d.DescID(c4d.DescLevel(DC_GRP, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Радиус"
        bc[c4d.DESC_DEFAULT] = 100.0
        bc[c4d.DESC_MIN]     = 1.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Высота"
        bc[c4d.DESC_DEFAULT] = 200.0
        bc[c4d.DESC_MIN]     = 1.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_HEIGHT, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Сегменты (окружность)"
        bc[c4d.DESC_DEFAULT] = 12
        bc[c4d.DESC_MIN]     = 3
        bc[c4d.DESC_MAX]     = 500
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 50
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_SEGS_R, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Сегменты (высота)"
        bc[c4d.DESC_DEFAULT] = 6
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 500
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 50
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_SEGS_H, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Крышки"
        bc[c4d.DESC_DEFAULT] = True
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_CAPS, c4d.DTYPE_BOOL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Тип поверхности"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = SURF_ZIGZAG
        cyc = c4d.BaseContainer()
        cyc[0] = "Зигзаг (ромбы)"
        cyc[1] = "Спираль"
        cyc[2] = "Гармошка"
        cyc[3] = "Прямая сетка"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_SURFACE, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Скрутка"
        bc[c4d.DESC_DEFAULT] = 0.0
        bc[c4d.DESC_MIN]     = math.radians(-3600.0)
        bc[c4d.DESC_MAX]     = math.radians(3600.0)
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_STEP]    = math.radians(0.1)
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = math.radians(-180.0)
        bc[c4d.DESC_MAXSLIDER] = math.radians(180.0)
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_TWIST, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Смещение (звезда)"
        bc[c4d.DESC_DEFAULT] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_STAR_ENABLED, c4d.DTYPE_BOOL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Величина смещения"
        bc[c4d.DESC_DEFAULT] = 20.0
        bc[c4d.DESC_MIN]     = -100000.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = -50
        bc[c4d.DESC_MAXSLIDER] = 150
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(DC_D_STAR_OFFSET, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def _build_mesh(self, op):
        radius        = op[DC_D_RADIUS]
        height        = op[DC_D_HEIGHT]
        segs_r        = max(3,  int(op[DC_D_SEGS_R]))
        segs_h        = max(1,  int(op[DC_D_SEGS_H]))
        caps          = bool(op[DC_D_CAPS])
        surf          = int(op[DC_D_SURFACE])
        twist         = op[DC_D_TWIST]  # скрутка по Y, хранится в радианах (C4D конвертирует из °)
        star_enabled  = bool(op[DC_D_STAR_ENABLED])
        star_offset   = float(op[DC_D_STAR_OFFSET])

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
    "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"
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
        description = "Obase",
        icon        = ICO_DC,
        info        = c4d.OBJECT_GENERATOR,
    )
