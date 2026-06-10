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

NAME_TRICUBE = "TriCube v1.3"

# ─── UserData SubID (общая схема: SubID=1 — группа, поля с 2) ────────────────

UD_GROUP = 1   # Группа "Параметры"

# TriCube — размеры по осям
TC_SIZE_X  = 2
TC_SIZE_Y  = 3
TC_SIZE_Z  = 4
# TriCube — подразделения по осям
TC_SUB_X   = 5
TC_SUB_Y   = 6
TC_SUB_Z   = 7
# TriCube — тип поверхности и смещение
TC_SURFACE    = 8   # 0=Треугольники, 1=Квады, 2=Ёлочка, 3=Смещённые ряды
TC_STAR_EN    = 9   # Галочка "Смещение (звезда)"
TC_STAR_OFFSET = 10  # Величина смещения по нормали грани

# Значения для TC_SURFACE
SURF_TRI    = 0   # Треугольная сетка (диагональ единообразная)
SURF_QUAD   = 1   # Квадратная сетка
SURF_HBONE  = 2   # Ёлочка (чередование диагоналей)
SURF_SHIFT  = 3   # Смещённые ряды (кирпичная раскладка)
SURF_HEX    = 4   # Гексагональная сетка

# Галочка "Закрыть швы смещения"
TC_STAR_CAP = 11  # Закрывает разрывы по рёбрам грани при star_offset != 0


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


def _make_cycle_bc(name, default, items):
    """Создаёт поле-выпадающий список (CUSTOMGUI_CYCLE / DTYPE_LONG).
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

def _build_hex_face(ux, uy, uz, vx, vy, vz, w_sign, wx, wy, wz,
                    hu, hv, hw, su, sv, star_offset, all_points, all_polys):
    """
    Гексагональная сетка на одной грани куба.
    Каждая ячейка (row, col) — правильный шестиугольник с центром и 6 вершинами.
    Центры шестиугольников укладываются в смещённую сетку (offset-grid):
      нечётные строки сдвинуты на полшага по u.
    Шестиугольники ориентированы вершинами вверх-вниз (flat-top).
    star_offset — смещение центра шестиугольника вдоль нормали грани.
    """
    # Шаги между центрами гексагонов
    step_u = (2.0 * hu) / su          # шаг по u
    step_v = (2.0 * hv) / sv          # шаг по v
    # Радиус вписанной окружности (апофема) и описанной для flat-top гексагона
    r_out = min(step_u, step_v) * 0.5  # описанная (вершины)
    r_in  = r_out * math.sqrt(3) * 0.5 # вписанная (середины рёбер)

    # Углы 6 вершин flat-top гексагона (0°=правый, затем против часовой стрелки)
    hex_angles = [math.radians(a) for a in (0, 60, 120, 180, 240, 300)]

    for row in range(sv):
        v_center = -hv + step_v * (row + 0.5)          # центр строки по v
        u_off = step_u * 0.5 if row % 2 == 1 else 0.0  # сдвиг нечётных строк

        for col in range(su):
            u_center = -hu + step_u * (col + 0.5) + u_off  # центр по u

            # Смещение центра вдоль нормали (звезда)
            nrm_shift = star_offset if star_offset != 0.0 else 0.0

            # Базовая позиция центра (для расчёта координат вершин, сама точка не добавляется)
            cx = ux*u_center*1.0 + vx*v_center*1.0 + wx*w_sign*hw + wx*w_sign*nrm_shift
            cy = uy*u_center*1.0 + vy*v_center*1.0 + wy*w_sign*hw + wy*w_sign*nrm_shift
            cz = uz*u_center*1.0 + vz*v_center*1.0 + wz*w_sign*hw + wz*w_sign*nrm_shift

            # 6 вершин гексагона в плоскости грани (u-v), без центральной точки
            # Индексы: 0=правый, 1=верх-правый, 2=верх-левый, 3=левый, 4=низ-левый, 5=низ-правый
            vert_start = len(all_points)
            for ang in hex_angles:
                du = r_out * math.cos(ang)
                dv = r_out * math.sin(ang)
                x = cx + ux*du + vx*dv
                y = cy + uy*du + vy*dv
                z = cz + uz*du + vz*dv
                all_points.append(c4d.Vector(x, y, z))

            # 2 четырёхугольных полигона вместо 6 треугольников (без центральной точки):
            # Quad 0: вершины 0, 1, 2, 3  (верхняя половина гексагона)
            # Quad 1: вершины 0, 3, 4, 5  (нижняя половина гексагона)
            v0 = vert_start + 0
            v1 = vert_start + 1
            v2 = vert_start + 2
            v3 = vert_start + 3
            v4 = vert_start + 4
            v5 = vert_start + 5
            all_polys.append(c4d.CPolygon(v0, v1, v2, v3))
            all_polys.append(c4d.CPolygon(v0, v3, v4, v5))


def build_tricube(size_x, size_y, size_z, sub_x, sub_y, sub_z,
                  surface=SURF_TRI, star_offset=0.0, star_cap=False):
    """
    Куб с настраиваемой сеткой.
    size_x/y/z   — размеры по осям.
    sub_x/y/z    — подразделения по каждой оси (применяются к соответствующим граням).
    surface      — тип сетки: SURF_TRI / SURF_QUAD / SURF_HBONE / SURF_SHIFT / SURF_HEX.
    star_offset  — смещение чередующихся вершин вдоль нормали грани (эффект рельефа).
    star_cap     — закрыть разрывы по краям грани заплаточными полигонами.
    Возвращает (points, polys) для c4d.PolygonObject.
    """
    hx = size_x / 2.0
    hy = size_y / 2.0
    hz = size_z / 2.0

    # 6 граней куба: (u_axis, v_axis, w_sign, w_axis, half_u, half_v, half_w, subdivs_u, subdivs_v)
    # half_u/v/w — половины размеров по соответствующим осям
    # subdivs_u/v — подразделения вдоль u и v на данной грани
    face_defs = [
        # (u_axis,      v_axis,      w_sign, w_axis,       hu,  hv,  hw,  su,    sv   )
        (( 1, 0, 0), ( 0, 1, 0), +1, (0, 0, 1),   hx,  hy,  hz,  sub_x, sub_y),  # передняя  +Z
        ((-1, 0, 0), ( 0, 1, 0), -1, (0, 0, 1),   hx,  hy,  hz,  sub_x, sub_y),  # задняя    -Z
        (( 0, 0,-1), ( 0, 1, 0), +1, (1, 0, 0),   hz,  hy,  hx,  sub_z, sub_y),  # правая    +X
        (( 0, 0, 1), ( 0, 1, 0), -1, (1, 0, 0),   hz,  hy,  hx,  sub_z, sub_y),  # левая     -X
        (( 1, 0, 0), ( 0, 0,-1), +1, (0, 1, 0),   hx,  hz,  hy,  sub_x, sub_z),  # верхняя   +Y
        (( 1, 0, 0), ( 0, 0, 1), -1, (0, 1, 0),   hx,  hz,  hy,  sub_x, sub_z),  # нижняя    -Y
    ]

    all_points = []
    all_polys  = []

    for (ux, uy, uz), (vx, vy, vz), w_sign, (wx, wy, wz), hu, hv, hw, su, sv in face_defs:

        # Гексагональная сетка — отдельный путь генерации
        if surface == SURF_HEX:
            _build_hex_face(ux, uy, uz, vx, vy, vz, w_sign, wx, wy, wz,
                            hu, hv, hw, su, sv, star_offset, all_points, all_polys)
            continue

        base = len(all_points)
        nu = su + 1  # вершин по u
        nv = sv + 1  # вершин по v

        # Генерируем вершины грани в локальной (u,v)-системе
        for row in range(nv):
            v_t = (row / sv) * 2.0 - 1.0   # [-1, +1]
            for col in range(nu):
                # Тип SURF_SHIFT: нечётные строки сдвигаются на полшага по u
                if surface == SURF_SHIFT and row % 2 == 1:
                    u_t = ((col + 0.5) / su) * 2.0 - 1.0
                else:
                    u_t = (col / su) * 2.0 - 1.0   # [-1, +1]

                x = (ux*u_t*hu + vx*v_t*hv + wx*w_sign*hw)
                y = (uy*u_t*hu + vy*v_t*hv + wy*w_sign*hw)
                z = (uz*u_t*hu + vz*v_t*hv + wz*w_sign*hw)

                # Смещение чередующихся вершин вдоль нормали грани
                if star_offset != 0.0 and (row + col) % 2 == 0:
                    x += wx * w_sign * star_offset
                    y += wy * w_sign * star_offset
                    z += wz * w_sign * star_offset

                all_points.append(c4d.Vector(x, y, z))

        # Генерируем полигоны в зависимости от типа поверхности
        for row in range(sv):
            for col in range(su):
                bl = base + row*nu + col
                br = base + row*nu + (col+1)
                tl = base + (row+1)*nu + col
                tr = base + (row+1)*nu + (col+1)

                if surface == SURF_QUAD or surface == SURF_SHIFT:
                    # Квадратная / смещённая — квады
                    all_polys.append(c4d.CPolygon(bl, br, tr, tl))
                elif surface == SURF_HBONE:
                    # Ёлочка — чередование диагоналей по (row+col) чётности
                    if (row + col) % 2 == 0:
                        all_polys.append(c4d.CPolygon(bl, br, tl, tl))  # диагональ bl-tl
                        all_polys.append(c4d.CPolygon(br, tr, tl, tl))
                    else:
                        all_polys.append(c4d.CPolygon(bl, br, tr, tr))  # диагональ br-tr
                        all_polys.append(c4d.CPolygon(bl, tr, tl, tl))
                else:
                    # SURF_TRI — единообразные треугольники (диагональ bl-tr)
                    all_polys.append(c4d.CPolygon(bl, br, tl, tl))
                    all_polys.append(c4d.CPolygon(br, tr, tl, tl))

        # Закрытие швов (star_cap): смещённые вершины на краях грани образуют разрыв
        # с соседними гранями. Вдоль каждого ребра грани проходим последовательными
        # парами соседних вершин. Если одна из пары смещена — добавляем треугольник,
        # закрывающий щель между смещённой вершиной и её двумя соседями вдоль ребра.
        # Ориентация: w_sign определяет направление нормали (наружу куба).
        if star_offset != 0.0 and star_cap:
            # Четыре ребра грани как последовательности (row, col):
            # нижнее (row=0), верхнее (row=sv), левое (col=0), правое (col=su)
            edge_sequences = [
                [(0,  c) for c in range(su + 1)],   # нижнее ребро
                [(sv, c) for c in range(su + 1)],   # верхнее ребро
                [(r,  0) for r in range(sv + 1)],   # левое ребро
                [(r, su) for r in range(sv + 1)],   # правое ребро
            ]

            for seq in edge_sequences:
                for i in range(len(seq) - 1):
                    r0, c0 = seq[i]
                    r1, c1 = seq[i + 1]
                    shifted0 = (r0 + c0) % 2 == 0
                    shifted1 = (r1 + c1) % 2 == 0
                    idx0 = base + r0 * nu + c0
                    idx1 = base + r1 * nu + c1

                    if shifted0 and not shifted1:
                        # idx0 смещена, idx1 на поверхности грани.
                        # Нужен треугольник: смещённая → левый сосед → правый сосед.
                        # Предыдущая вершина вдоль ребра (если есть) — ещё один не-смещённый сосед.
                        if i > 0:
                            r_prev, c_prev = seq[i - 1]
                            idx_prev = base + r_prev * nu + c_prev
                            # Ориентация по w_sign: наружу куба
                            if w_sign > 0:
                                all_polys.append(c4d.CPolygon(idx0, idx_prev, idx1, idx1))
                            else:
                                all_polys.append(c4d.CPolygon(idx0, idx1, idx_prev, idx_prev))
                        else:
                            # Начало ребра — треугольник с одним соседом впереди
                            if i + 2 < len(seq):
                                r_next, c_next = seq[i + 2]
                                idx_next = base + r_next * nu + c_next
                                if w_sign > 0:
                                    all_polys.append(c4d.CPolygon(idx0, idx1, idx_next, idx_next))
                                else:
                                    all_polys.append(c4d.CPolygon(idx0, idx_next, idx1, idx1))

                    elif shifted1 and not shifted0:
                        # idx1 смещена, idx0 на поверхности грани.
                        if i + 2 < len(seq):
                            r_next, c_next = seq[i + 2]
                            idx_next = base + r_next * nu + c_next
                            if w_sign > 0:
                                all_polys.append(c4d.CPolygon(idx1, idx_next, idx0, idx0))
                            else:
                                all_polys.append(c4d.CPolygon(idx1, idx0, idx_next, idx_next))

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
    _first_ud_id = TC_SIZE_X   # переопределяется в подклассах

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
    _first_ud_id = TC_SIZE_X

    def _create_ud(self, op, grp_subid):
        # Размеры по осям
        _add_in_group(op, grp_subid, _make_float_bc(
            "Размер X", 200.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Размер Y", 200.0, 1.0, 100000.0))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Размер Z", 200.0, 1.0, 100000.0))
        # Подразделения по осям
        _add_in_group(op, grp_subid, _make_int_bc(
            "Подразделения X", 3, 1, 50))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Подразделения Y", 3, 1, 50))
        _add_in_group(op, grp_subid, _make_int_bc(
            "Подразделения Z", 3, 1, 50))
        # Тип поверхности
        _add_in_group(op, grp_subid, _make_cycle_bc(
            "Поверхность", SURF_TRI,
            ["Треугольники", "Квады", "Ёлочка", "Смещённые ряды", "Гексагоны"]))
        # Смещение (звезда)
        _add_in_group(op, grp_subid, _make_bool_bc(
            "Смещение (звезда)", False))
        _add_in_group(op, grp_subid, _make_float_bc(
            "Величина смещения", 0.0, -10000.0, 10000.0))
        # Закрыть швы смещения
        _add_in_group(op, grp_subid, _make_bool_bc(
            "Закрыть швы", False))

    def _set_defaults(self, op):
        _ud_set_default(op, TC_SIZE_X,     200.0)
        _ud_set_default(op, TC_SIZE_Y,     200.0)
        _ud_set_default(op, TC_SIZE_Z,     200.0)
        _ud_set_default(op, TC_SUB_X,      3)
        _ud_set_default(op, TC_SUB_Y,      3)
        _ud_set_default(op, TC_SUB_Z,      3)
        _ud_set_default(op, TC_SURFACE,    SURF_TRI)
        _ud_set_default(op, TC_STAR_EN,    False)
        _ud_set_default(op, TC_STAR_OFFSET, 0.0)

    def _build_mesh(self, op):
        size_x  = _ud_get(op, TC_SIZE_X,  200.0)
        size_y  = _ud_get(op, TC_SIZE_Y,  200.0)
        size_z  = _ud_get(op, TC_SIZE_Z,  200.0)
        sub_x   = max(1, int(_ud_get(op, TC_SUB_X,  3)))
        sub_y   = max(1, int(_ud_get(op, TC_SUB_Y,  3)))
        sub_z   = max(1, int(_ud_get(op, TC_SUB_Z,  3)))
        surface = int(_ud_get(op, TC_SURFACE, SURF_TRI))
        star_en = bool(_ud_get(op, TC_STAR_EN, False))
        star_offset = float(_ud_get(op, TC_STAR_OFFSET, 0.0)) if star_en else 0.0
        star_cap = bool(_ud_get(op, TC_STAR_CAP, False))
        return build_tricube(size_x, size_y, size_z, sub_x, sub_y, sub_z, surface, star_offset, star_cap)


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
