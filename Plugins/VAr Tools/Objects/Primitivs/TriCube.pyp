# -*- coding: utf-8 -*-
"""
TriCube — Cinema 4D ObjectData Plugin
 Генератор куба с 5 типами сетки (треугольники, квады, ёлочка, кирпич, гексагоны), раздельными размерами и подразделениями по XYZ, смещением вершин по нормали и зашивкой швов.
"""

import c4d # type: ignore
import math
import os
import base64
import tempfile

# ─── Plugin ID & Name ───────────────────────────────────────────────────────────────

ID_TRICUBE = 1068871

NAME_TRICUBE = "Tri Cube v1.6"

# ─── Description-based parameter IDs ──────────────────────────────────────────────────

TC_GRP          = 2000
TC_D_SIZE_X     = 2001
TC_D_SIZE_Y     = 2002
TC_D_SIZE_Z     = 2003
TC_D_SUB_X      = 2004
TC_D_SUB_Y      = 2005
TC_D_SUB_Z      = 2006
TC_D_SURFACE    = 2007
TC_D_STAR_EN    = 2008
TC_D_STAR_OFFSET = 2009
TC_D_STAR_CAP   = 2010

# Значения для TC_SURFACE
SURF_TRI    = 0   # Треугольная сетка (диагональ единообразная)
SURF_QUAD   = 1   # Квадратная сетка
SURF_HBONE  = 2   # Ёлочка (чередование диагоналей)
SURF_SHIFT  = 3   # Смещённые ряды (кирпичная раскладка)
SURF_HEX    = 4   # Гексагональная сетка


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

    # face_bases[i] = (base, nu, su, sv) для i-й грани (заполняется в цикле ниже)
    # Используется для закрытия швов (star_cap) после генерации всех граней.
    face_bases = []

    for (ux, uy, uz), (vx, vy, vz), w_sign, (wx, wy, wz), hu, hv, hw, su, sv in face_defs:

        # Гексагональная сетка — отдельный путь генерации
        if surface == SURF_HEX:
            _build_hex_face(ux, uy, uz, vx, vy, vz, w_sign, wx, wy, wz,
                            hu, hv, hw, su, sv, star_offset, all_points, all_polys)
            face_bases.append(None)  # для HEX star_cap не применяется
            continue

        base = len(all_points)
        nu = su + 1  # вершин по u
        nv = sv + 1  # вершин по v
        face_bases.append((base, nu, su, sv))

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

    # ─── Закрытие швов (star_cap) ────────────────────────────────────────────────
    # Все 6 граней уже сгенерированы. Для каждого из 12 рёбер куба берём
    # последовательности вершин с обеих смежных граней и соединяем их двумя треугольниками.
    # flip_seam в таблице cube_edges определяет порядок обхода (нормаль наружу).
    # Для рёбер с rev_B=True последовательность грани B реверсируется перед соединением.
    if star_offset != 0.0 and star_cap and surface != SURF_HEX:
        # 12 рёбер куба: (face_A, тип_ребра_A, знач_A, face_B, тип_ребра_B, знач_B, rev_B, flip_seam)
        # тип: "col" — фиксированный столбец (ребро по v), "row" — фиксированная строка (ребро по u)
        # знач: число или "su"/"sv" — последний индекс по соответствующей оси
        # flip_seam: инвертирует порядок вершин в треугольниках заплатки (нормаль наружу)
        cube_edges = [
            (0, "col", "su", 2, "col", 0,    False, False),  # передняя+правая
            (0, "col", 0,    3, "col", "su", False, True),   # передняя+левая
            (0, "row", "sv", 4, "row", 0,    False, True),   # передняя+верхняя
            (0, "row", 0,    5, "row", "sv", False, False),  # передняя+нижняя
            (1, "col", 0,    2, "col", "su", False, True),   # задняя+правая
            (1, "col", "su", 3, "col", 0,    False, False),  # задняя+левая
            (1, "row", "sv", 4, "row", "sv", True,  True),   # задняя+верхняя
            (1, "row", 0,    5, "row", 0,    True,  False),  # задняя+нижняя
            (2, "row", "sv", 4, "col", "su", False, True),   # правая+верхняя
            (2, "row", 0,    5, "col", "su", True,  False),  # правая+нижняя
            (3, "row", "sv", 4, "col", 0,    True,  True),   # левая+верхняя
            (3, "row", 0,    5, "col", 0,    False, False),  # левая+нижняя
        ]

        def edge_seq(fi, etype, eval_):
            """Возвращает список (row, col) вершин вдоль ребра грани fi."""
            fb = face_bases[fi]
            if fb is None:
                return []
            _, _, su_f, sv_f = fb
            v = su_f if eval_ == "su" else (sv_f if eval_ == "sv" else eval_)
            if etype == "col":
                return [(r, v) for r in range(sv_f + 1)]
            else:
                return [(v, c) for c in range(su_f + 1)]

        def vert_idx(fi, row, col):
            """Глобальный индекс вершины грани fi в позиции (row, col)."""
            base_f, nu_f, _, _ = face_bases[fi]
            return base_f + row * nu_f + col

        for fi_a, ta, va, fi_b, tb, vb, rev_b, flip_seam in cube_edges:
            if face_bases[fi_a] is None or face_bases[fi_b] is None:
                continue
            seq_a = edge_seq(fi_a, ta, va)
            seq_b = edge_seq(fi_b, tb, vb)
            if rev_b:
                seq_b = seq_b[::-1]

            n = min(len(seq_a), len(seq_b))
            for i in range(n - 1):
                ra0, ca0 = seq_a[i];     ra1, ca1 = seq_a[i + 1]
                rb0, cb0 = seq_b[i];     rb1, cb1 = seq_b[i + 1]
                ia0 = vert_idx(fi_a, ra0, ca0)
                ia1 = vert_idx(fi_a, ra1, ca1)
                ib0 = vert_idx(fi_b, rb0, cb0)
                ib1 = vert_idx(fi_b, rb1, cb1)
                sh_a0 = (ra0 + ca0) % 2 == 0
                sh_a1 = (ra1 + ca1) % 2 == 0
                sh_b0 = (rb0 + cb0) % 2 == 0
                sh_b1 = (rb1 + cb1) % 2 == 0
                # Добавляем заплатку только если хотя бы одна вершина смещена
                # (иначе грани уже совпадают в пространстве и заплатка не нужна)
                if sh_a0 or sh_a1 or sh_b0 or sh_b1:
                    # Диагональ выбирается через смещённую вершину, чтобы треугольники
                    # огибали выступ, а не проваливались вовнутрь.
                    # Диагональ ia1–ib0 используется если смещена ia1 или ib0,
                    # иначе диагональ ia0–ib1 (смещена ia0 или ib1, или ни одна).
                    use_alt_diag = (sh_a1 or sh_b0) and not (sh_a0 or sh_b1)
                    if flip_seam:
                        if use_alt_diag:
                            all_polys.append(c4d.CPolygon(ib0, ia0, ia1, ia1))
                            all_polys.append(c4d.CPolygon(ib0, ia1, ib1, ib1))
                        else:
                            all_polys.append(c4d.CPolygon(ib0, ia0, ib1, ib1))
                            all_polys.append(c4d.CPolygon(ia0, ia1, ib1, ib1))
                    else:
                        if use_alt_diag:
                            all_polys.append(c4d.CPolygon(ib0, ia1, ia0, ia0))
                            all_polys.append(c4d.CPolygon(ib0, ib1, ia1, ia1))
                        else:
                            all_polys.append(c4d.CPolygon(ib0, ib1, ia0, ia0))
                            all_polys.append(c4d.CPolygon(ia0, ib1, ia1, ia1))

        # ─── Угловые заплатки ────────────────────────────────────────────────────────
        # В каждом из 8 углов куба сходятся 3 грани. Рёберные заплатки не закрывают
        # угловой треугольник между тремя гранями — добавляем его явно.
        # Для каждого угла: (fi_a, row_a, col_a, fi_b, row_b, col_b, fi_c, row_c, col_c, flip)
        # flip=True инвертирует порядок вершин (нормаль наружу зависит от знака угла).
        # "su"/"sv" в row/col заменяются на реальные значения через face_bases.
        cube_corners = [
            #  fa   ra    ca    fb   rb    cb    fc   rc    cc    flip
            (0, "sv","su", 2,"sv",  0,   4,  0, "su", False),  # +X+Y+Z
            (0, "sv",  0,  3,"sv","su",  4,  0,   0,  True),   # -X+Y+Z
            (0,   0, "su", 2,  0,   0,  5,"sv","su", True),    # +X-Y+Z
            (0,   0,   0,  3,  0, "su", 5,"sv",  0,  False),   # -X-Y+Z
            (1, "sv",  0,  2,"sv","su",  4,"sv","su", True),    # +X+Y-Z
            (1, "sv","su", 3,"sv",  0,  4,"sv",  0,  False),   # -X+Y-Z
            (1,   0,   0,  2,  0, "su", 5,  0, "su", False),   # +X-Y-Z
            (1,   0, "su", 3,  0,   0,  5,  0,   0,  True),    # -X-Y-Z
        ]

        def _resolve(fb, val):
            """Заменяет 'su'/'sv' на реальное значение из face_bases."""
            _, _, su_f, sv_f = fb
            if val == "su": return su_f
            if val == "sv": return sv_f
            return val

        for fa, ra, ca, fb_, rb, cb, fc, rc, cc, flip in cube_corners:
            if face_bases[fa] is None or face_bases[fb_] is None or face_bases[fc] is None:
                continue
            ra_ = _resolve(face_bases[fa], ra)
            ca_ = _resolve(face_bases[fa], ca)
            rb_ = _resolve(face_bases[fb_], rb)
            cb_ = _resolve(face_bases[fb_], cb)
            rc_ = _resolve(face_bases[fc], rc)
            cc_ = _resolve(face_bases[fc], cc)
            # Добавляем заплатку только если хотя бы одна угловая вершина смещена
            sh_a = (ra_ + ca_) % 2 == 0
            sh_b = (rb_ + cb_) % 2 == 0
            sh_c = (rc_ + cc_) % 2 == 0
            if sh_a or sh_b or sh_c:
                ia = vert_idx(fa, ra_, ca_)
                ib = vert_idx(fb_, rb_, cb_)
                ic = vert_idx(fc, rc_, cc_)
                if flip:
                    all_polys.append(c4d.CPolygon(ia, ic, ib, ib))
                else:
                    all_polys.append(c4d.CPolygon(ia, ib, ic, ic))

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


# ─── TriCube ──────────────────────────────────────────────────────────────────

class TriCubeObject(_MeshPrimitiveBase):
    """Куб с треугольной сеткой."""

    OBJECT_NAME = "Tri Cube"

    def _set_defaults(self, op):
        op[TC_D_SIZE_X]      = 200.0
        op[TC_D_SIZE_Y]      = 200.0
        op[TC_D_SIZE_Z]      = 200.0
        op[TC_D_SUB_X]       = 3
        op[TC_D_SUB_Y]       = 3
        op[TC_D_SUB_Z]       = 3
        op[TC_D_SURFACE]     = SURF_TRI
        op[TC_D_STAR_EN]     = False
        op[TC_D_STAR_OFFSET] = 0.0
        op[TC_D_STAR_CAP]    = False

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_GRP, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid = c4d.DescID(c4d.DescLevel(TC_GRP, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Размер X"
        bc[c4d.DESC_DEFAULT] = 200.0
        bc[c4d.DESC_MIN]     = 1.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SIZE_X, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Размер Y"
        bc[c4d.DESC_DEFAULT] = 200.0
        bc[c4d.DESC_MIN]     = 1.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SIZE_Y, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Размер Z"
        bc[c4d.DESC_DEFAULT] = 200.0
        bc[c4d.DESC_MIN]     = 1.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SIZE_Z, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Подразделения X"
        bc[c4d.DESC_DEFAULT] = 3
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 500
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 20
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SUB_X, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Подразделения Y"
        bc[c4d.DESC_DEFAULT] = 3
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 50
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 20
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SUB_Y, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Подразделения Z"
        bc[c4d.DESC_DEFAULT] = 3
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 50
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 20
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SUB_Z, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Поверхность"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = SURF_TRI
        cyc = c4d.BaseContainer()
        cyc[0] = "Треугольники"
        cyc[1] = "Квады"
        cyc[2] = "Ёлочка"
        cyc[3] = "Смещённые ряды"
        cyc[4] = "Гексагоны"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_SURFACE, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Смещение (звезда)"
        bc[c4d.DESC_DEFAULT] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_STAR_EN, c4d.DTYPE_BOOL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Величина смещения"
        bc[c4d.DESC_DEFAULT] = 0.0
        bc[c4d.DESC_MIN]     = -10000.0
        bc[c4d.DESC_MAX]     = 10000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 50.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_STAR_OFFSET, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Закрыть швы"
        bc[c4d.DESC_DEFAULT] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TC_D_STAR_CAP, c4d.DTYPE_BOOL, 0)),
            bc, gid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def _build_mesh(self, op):
        size_x      = op[TC_D_SIZE_X]
        size_y      = op[TC_D_SIZE_Y]
        size_z      = op[TC_D_SIZE_Z]
        sub_x       = max(1, int(op[TC_D_SUB_X]))
        sub_y       = max(1, int(op[TC_D_SUB_Y]))
        sub_z       = max(1, int(op[TC_D_SUB_Z]))
        surface     = int(op[TC_D_SURFACE])
        star_en     = bool(op[TC_D_STAR_EN])
        star_offset = float(op[TC_D_STAR_OFFSET]) if star_en else 0.0
        star_cap    = bool(op[TC_D_STAR_CAP])
        return build_tricube(size_x, size_y, size_z, sub_x, sub_y, sub_z, surface, star_offset, star_cap)


_ICON_TC = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzQ6MjIrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzQ6MjIrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjYzYjBiNWI2LTNiMTktOGI0OS04MjVlLTVjNmQ1MWY2ZDIzZiIgeG1wTU06RG9jdW1lbnRJRD0i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"
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
        description = "Obase",
        icon        = ICO_TC,
        info        = c4d.OBJECT_GENERATOR,
    )
