# ============================================================
#  PolySubdivider — плагин для Cinema 4D R26
#  Расширенный аналог Divider: несколько алгоритмов разбиения
#  полигонов с возможностью лёгкого добавления новых типов.
#
#  Установка:
#    Положить файл PolySubdivider.pyp в папку:
#    ..\AppData\Roaming\Maxon\Cinema 4D R26_xxx\plugins\VAr Tools\
#
#  ID плагина: 1068837
# ============================================================

import c4d
from c4d import plugins, utils
import math
import random

# ── ID плагина (зарегистрирован на plugincafe.maxon.net) ──
PLUGIN_ID = 1068837

# ============================================================
#  ID параметров панели Атрибуты
#  Значения > 1000 чтобы не конфликтовать с базовыми ID C4D
# ============================================================
PAR_ALGORITHM   = 1100   # Тип алгоритма (cycle/dropdown)
PAR_ITERATIONS  = 1101   # Количество итераций
PAR_SLIDER_X    = 1102   # Смещение / параметр X (0..100 %)
PAR_SLIDER_Y    = 1103   # Смещение / параметр Y (0..100 %)
PAR_SLIDER_Z    = 1104   # Смещение / параметр Z (0..100 %)
PAR_RANDOM_SEED = 1105   # Зерно генератора случайных чисел
PAR_NOISE_AMT   = 1106   # Величина шума
PAR_NOISE_FREQ  = 1107   # Частота шума
PAR_NOISE_LOOP  = 1108   # Петля шума (%)
PAR_PATTERN_ROT = 1109   # Угол паттерна (градусы)
PAR_GRID_SCALE  = 1110   # Масштаб сетки

# ── ID групп в описании ──
GRP_SETTINGS    = 1200
GRP_NOISE       = 1201

# ============================================================
#  Индексы алгоритмов
#  Чтобы добавить новый: ALG_MYALG = 6, имя в ALG_NAMES,
#  функция subdivide_myalg, запись в ALGORITHM_REGISTRY
# ============================================================
ALG_UNIFORM     = 0   # Равномерная UV-сетка (аналог Dmitris)
ALG_RANDOM      = 1   # Случайные прямолинейные разрезы
ALG_DIAGONAL    = 2   # Диагональное деление (fan из центра)
ALG_HERRINGBONE = 3   # Паттерн «Ёлочка»
ALG_RADIAL      = 4   # Радиальное деление (секторы)
ALG_VORONOI     = 5   # Вороной-подобная сетка

# Названия для выпадающего списка (порядок = индекс)
ALG_NAMES = [
    "Равномерное",
    "Случайное",
    "Диагональ",
    "Ёлочка",
    "Радиальное",
    "Вороной",
]

# ============================================================
#  Вспомогательные функции
# ============================================================

def lerp(a, b, t):
    """Линейная интерполяция двух векторов c4d.Vector."""
    return a + (b - a) * t


def mid_pt(a, b):
    """Средняя точка отрезка."""
    return (a + b) * 0.5


def simple_noise(x, y, z, freq=1.0):
    """
    Детерминированный псевдошум через синус.
    Не требует внешних библиотек (perlin и т.п.).
    Возвращает значение в диапазоне [-1 .. 1].
    """
    x, y, z = x * freq, y * freq, z * freq
    return math.sin(x * 127.1 + y * 311.7 + z * 74.9)

# ============================================================
#  Строитель полигонального меша
# ============================================================

class MeshBuilder:
    """
    Накапливает вершины и полигоны, затем создаёт
    готовый c4d.PolygonObject одним вызовом build().
    """

    def __init__(self):
        self.verts = []   # список c4d.Vector
        self.polys = []   # список кортежей (a, b, c, d)

    def add_vert(self, v):
        """Добавляет вершину и возвращает её индекс."""
        idx = len(self.verts)
        self.verts.append(c4d.Vector(v.x, v.y, v.z))
        return idx

    def add_quad(self, a, b, c, d):
        """Добавляет четырёхугольник."""
        self.polys.append((a, b, c, d))

    def add_tri(self, a, b, c):
        """Добавляет треугольник (вырожденный quad: c==d)."""
        self.polys.append((a, b, c, c))

    def build(self):
        """Создаёт и возвращает c4d.PolygonObject."""
        if not self.verts or not self.polys:
            return None
        obj = c4d.PolygonObject(len(self.verts), len(self.polys))
        for i, v in enumerate(self.verts):
            obj.SetPoint(i, v)
        for i, p in enumerate(self.polys):
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[3]))
        obj.Message(c4d.MSG_UPDATE)
        return obj

# ============================================================
#  Утилита: извлечь полигоны исходного объекта
# ============================================================

def get_source_polys(src_obj):
    """
    Возвращает список полигонов как список списков c4d.Vector.
    Треугольники возвращаются как список из 3 элементов,
    квады — из 4.
    """
    pts = [src_obj.GetPoint(i) for i in range(src_obj.GetPointCount())]
    result = []
    for i in range(src_obj.GetPolygonCount()):
        p = src_obj.GetPolygon(i)
        if p.c == p.d:
            result.append([pts[p.a], pts[p.b], pts[p.c]])
        else:
            result.append([pts[p.a], pts[p.b], pts[p.c], pts[p.d]])
    return result


def ensure_quad(poly):
    """Дополняет треугольник до вырожденного quad."""
    if len(poly) == 3:
        return [poly[0], poly[1], poly[2], poly[2]]
    return poly

# ============================================================
#  Алгоритмы подразделения
#  Сигнатура каждой функции: subdivide_*(src_obj, p) -> MeshBuilder
#  p — словарь параметров (iterations, slider_x, ... noise_amt, ...)
# ============================================================

def subdivide_uniform(src_obj, p):
    """
    Равномерная UV-сетка.
    Каждый полигон делится на (iter+1)^2 ячеек.
    slider_x / slider_y смещают внутренние рёбра сетки.
    """
    div   = max(1, p["iterations"])       # делений по каждой оси
    sx    = p["slider_x"] / 100.0 - 0.5  # [-0.5 .. 0.5]
    sy    = p["slider_y"] / 100.0 - 0.5
    noise = p["noise_amt"]
    freq  = max(0.01, p["noise_freq"])
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly

        # Строим сетку (div+1) x (div+1) вершин
        grid = []
        for row in range(div + 1):
            tv = row / div
            if 0 < row < div:
                tv = max(0.0, min(1.0, tv + sy / div))
            grid_row = []
            for col in range(div + 1):
                tu = col / div
                if 0 < col < div:
                    tu = max(0.0, min(1.0, tu + sx / div))
                # Билинейная интерполяция
                bot = lerp(p0, p1, tu)
                top = lerp(p3, p2, tu)
                pt  = lerp(bot, top, tv)
                # Добавляем шум
                if noise > 0:
                    n = simple_noise(pt.x, pt.y, pt.z, freq)
                    jitter = noise * rng.uniform(0.8, 1.2)
                    pt = pt + c4d.Vector(n * jitter, n * jitter * 0.5, n * jitter)
                grid_row.append(mb.add_vert(pt))
            grid.append(grid_row)

        # Создаём квады по сетке
        for row in range(div):
            for col in range(div):
                a = grid[row][col]
                b = grid[row][col + 1]
                c = grid[row + 1][col + 1]
                d = grid[row + 1][col]
                mb.add_quad(a, b, c, d)

    return mb


def subdivide_random(src_obj, p):
    """
    Случайное подразделение.
    Каждый полигон режется iter случайными горизонтальными
    или вертикальными разрезами.
    slider_x управляет смещением точки разреза.
    """
    iters = max(1, p["iterations"])
    bias  = p["slider_x"] / 100.0        # смещение от центра [0..1]
    noise = p["noise_amt"]
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    def split_h(quad, t):
        """Горизонтальный разрез quad по параметру t."""
        a, b, c, d = quad
        ab = lerp(a, d, t)
        bc = lerp(b, c, t)
        return [a, b, bc, ab], [ab, bc, c, d]

    def split_v(quad, t):
        """Вертикальный разрез quad по параметру t."""
        a, b, c, d = quad
        ad = lerp(a, b, t)
        dc = lerp(d, c, t)
        return [a, ad, dc, d], [ad, b, c, dc]

    for poly in get_source_polys(src_obj):
        pieces = [ensure_quad(poly)]
        for _ in range(iters):
            next_pieces = []
            for piece in pieces:
                # Точка разреза: смещаем в сторону slider_x
                t = rng.uniform(0.15, 0.85)
                t = t * (1.0 - bias) + bias * rng.uniform(0.4, 0.6)
                t = max(0.1, min(0.9, t))
                if noise > 0:
                    t += simple_noise(
                        piece[0].x, piece[0].y, piece[0].z
                    ) * noise * 0.15
                    t = max(0.1, min(0.9, t))
                if rng.random() < 0.5:
                    next_pieces.extend(split_h(piece, t))
                else:
                    next_pieces.extend(split_v(piece, t))
            pieces = next_pieces

        for piece in pieces:
            idxs = [mb.add_vert(v) for v in piece]
            mb.add_quad(*idxs)

    return mb


def subdivide_diagonal(src_obj, p):
    """
    Диагональное (fan) деление.
    Каждый полигон рекурсивно делится на 4 части
    через смещённый центр. Создаёт органичный паттерн.
    """
    iters = max(1, p["iterations"])
    sx    = p["slider_x"] / 100.0
    sy    = p["slider_y"] / 100.0
    noise = p["noise_amt"]
    freq  = max(0.01, p["noise_freq"])
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    def diag_split(quad, depth):
        p0, p1, p2, p3 = quad
        # Центр со смещением от слайдеров
        center = lerp(
            lerp(p0, p1, sx),
            lerp(p3, p2, sx),
            sy
        )
        if noise > 0:
            n = simple_noise(center.x, center.y, center.z, freq)
            jitter = noise * rng.uniform(0.5, 1.5)
            center = center + c4d.Vector(
                n * jitter, n * jitter * 0.3, n * jitter
            )
        if depth <= 1:
            # Конечный уровень: добавляем 4 треугольника
            ci = mb.add_vert(center)
            i0 = mb.add_vert(p0)
            i1 = mb.add_vert(p1)
            i2 = mb.add_vert(p2)
            i3 = mb.add_vert(p3)
            mb.add_tri(i0, i1, ci)
            mb.add_tri(i1, i2, ci)
            mb.add_tri(i2, i3, ci)
            mb.add_tri(i3, i0, ci)
        else:
            # Делим на 4 подквада и уходим рекурсивно
            m01 = mid_pt(p0, p1)
            m12 = mid_pt(p1, p2)
            m23 = mid_pt(p2, p3)
            m30 = mid_pt(p3, p0)
            diag_split([p0,  m01, center, m30], depth - 1)
            diag_split([m01, p1,  m12, center], depth - 1)
            diag_split([center, m12, p2,  m23], depth - 1)
            diag_split([m30, center, m23, p3 ], depth - 1)

    for poly in get_source_polys(src_obj):
        diag_split(ensure_quad(poly), iters)

    return mb


def subdivide_herringbone(src_obj, p):
    """
    Паттерн «Ёлочка» (Herringbone).
    Чётные и нечётные строки смещаются на slider_x,
    создавая паркетный эффект.
    """
    div   = max(1, p["iterations"])
    sx    = p["slider_x"] / 100.0   # смещение чётных строк
    sy    = p["slider_y"] / 100.0   # степень сжатия по V
    noise = p["noise_amt"]
    freq  = max(0.01, p["noise_freq"])
    rng   = random.Random(p["random_seed"])
    mb    = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly
        grid = []
        for row in range(div + 1):
            tv = row / div
            # Сжатие строк регулируется slider_y
            tv_adj = min(tv * (0.5 + sy * 0.5) * 2.0, 1.0)
            # Чётные строки смещаются вправо на sx/div
            shift = sx * 0.5 if (row % 2 == 1) else 0.0
            grid_row = []
            for col in range(div + 1):
                tu = (col / div + shift) % 1.0
                bot = lerp(p0, p1, tu)
                top = lerp(p3, p2, tu)
                pt  = lerp(bot, top, tv_adj)
                if noise > 0:
                    n = simple_noise(pt.x, pt.y, pt.z, freq)
                    jitter = noise * rng.uniform(0.7, 1.3)
                    pt = pt + c4d.Vector(
                        n * jitter, n * jitter * 0.4, n * jitter
                    )
                grid_row.append(mb.add_vert(pt))
            grid.append(grid_row)

        for row in range(div):
            for col in range(div):
                a = grid[row][col]
                b = grid[row][col + 1]
                c = grid[row + 1][col + 1]
                d = grid[row + 1][col]
                mb.add_quad(a, b, c, d)

    return mb


def subdivide_radial(src_obj, p):
    """
    Радиальное деление.
    Из смещённого центра полигона расходятся лучи.
    Количество секторов = iterations * 2 + 4.
    slider_x / slider_y задают положение центра.
    """
    iters   = max(1, p["iterations"])
    cx_bias = p["slider_x"] / 100.0   # X-позиция центра [0..1]
    cy_bias = p["slider_y"] / 100.0   # Y-позиция центра [0..1]
    sectors = iters * 2 + 4            # минимум 6 секторов
    noise   = p["noise_amt"]
    freq    = max(0.01, p["noise_freq"])
    rng     = random.Random(p["random_seed"])
    mb      = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly

        # Центр со смещением
        center = lerp(
            lerp(p0, p1, cx_bias),
            lerp(p3, p2, cx_bias),
            cy_bias
        )
        if noise > 0:
            n = simple_noise(center.x, center.y, center.z, freq)
            jitter = noise * rng.uniform(0.4, 1.2)
            center = center + c4d.Vector(
                n * jitter, n * jitter * 0.3, n * jitter
            )
        ci = mb.add_vert(center)

        # Периметр: обходим 4 ребра, равномерно набирая точки
        seg = sectors // 4  # точек на каждое ребро
        rim_pts = []
        edges = [(p0, p1), (p1, p2), (p2, p3), (p3, p0)]
        for ea, eb in edges:
            for k in range(seg):
                t = k / seg
                rim_pts.append(lerp(ea, eb, t))

        rim_ids = [mb.add_vert(v) for v in rim_pts]
        n_rim   = len(rim_ids)
        for k in range(n_rim):
            a = rim_ids[k]
            b = rim_ids[(k + 1) % n_rim]
            mb.add_tri(ci, a, b)

    return mb


def subdivide_voronoi(src_obj, p):
    """
    Вороной-подобное деление.
    Случайные точки-сайты размещаются внутри полигона,
    затем каждый сайт соединяется с ближайшими соседями
    через средние точки, аппроксимируя ячейки Вороного.
    """
    iters    = max(1, p["iterations"])
    num_sites = min(iters * iters + 2, 30)  # ограничиваем сложность
    noise    = p["noise_amt"]
    freq     = max(0.01, p["noise_freq"])
    rng      = random.Random(p["random_seed"])
    mb       = MeshBuilder()

    for poly in get_source_polys(src_obj):
        poly = ensure_quad(poly)
        p0, p1, p2, p3 = poly

        # Генерируем сайты внутри полигона
        sites = []
        for _ in range(num_sites):
            u = rng.uniform(0.05, 0.95)
            v = rng.uniform(0.05, 0.95)
            bot = lerp(p0, p1, u)
            top = lerp(p3, p2, u)
            pt  = lerp(bot, top, v)
            if noise > 0:
                n = simple_noise(pt.x, pt.y, pt.z, freq)
                pt = pt + c4d.Vector(
                    n * noise * rng.uniform(0.2, 0.8),
                    n * noise * rng.uniform(0.2, 0.8),
                    n * noise * rng.uniform(0.2, 0.8)
                )
            sites.append(pt)

        site_ids = [mb.add_vert(s) for s in sites]

        # Упрощённая связность: каждый сайт соединяем
        # с 2 ближайшими через среднюю точку → треугольники
        for i, si in enumerate(sites):
            dists = sorted(
                [(((si - sites[j]).GetLength()), j)
                 for j in range(len(sites)) if j != i]
            )
            # Берём 2-3 ближайших соседа
            k_neighbors = min(3, len(dists))
            for k in range(k_neighbors):
                j = dists[k][1]
                m = mid_pt(si, sites[j])
                mi = mb.add_vert(m)
                mb.add_tri(site_ids[i], site_ids[j], mi)

    return mb


# ============================================================
#  Реестр алгоритмов
#  Ключ = целочисленный индекс из ALG_* констант
#  Значение = функция subdivide_*
# ============================================================
ALGORITHM_REGISTRY = {
    ALG_UNIFORM:     subdivide_uniform,
    ALG_RANDOM:      subdivide_random,
    ALG_DIAGONAL:    subdivide_diagonal,
    ALG_HERRINGBONE: subdivide_herringbone,
    ALG_RADIAL:      subdivide_radial,
    ALG_VORONOI:     subdivide_voronoi,
    # ── Пример добавления нового алгоритма ──
    # ALG_MYALG:    subdivide_myalg,
}

# ============================================================
#  Класс генераторного объекта Cinema 4D
# ============================================================

class PolySubdividerObject(plugins.ObjectData):
    """
    Генераторный ObjectData-плагин.
    Берёт первого дочернего потомка (PolygonObject или
    примитив) и применяет выбранный алгоритм подразделения.
    """

    def Init(self, op):
        """Устанавливает значения атрибутов по умолчанию."""
        self.InitAttr(op, int,   [PAR_ALGORITHM])
        self.InitAttr(op, int,   [PAR_ITERATIONS])
        self.InitAttr(op, float, [PAR_SLIDER_X])
        self.InitAttr(op, float, [PAR_SLIDER_Y])
        self.InitAttr(op, float, [PAR_SLIDER_Z])
        self.InitAttr(op, int,   [PAR_RANDOM_SEED])
        self.InitAttr(op, float, [PAR_NOISE_AMT])
        self.InitAttr(op, float, [PAR_NOISE_FREQ])
        self.InitAttr(op, float, [PAR_NOISE_LOOP])
        self.InitAttr(op, float, [PAR_PATTERN_ROT])
        self.InitAttr(op, float, [PAR_GRID_SCALE])

        op[PAR_ALGORITHM]   = ALG_UNIFORM
        op[PAR_ITERATIONS]  = 3
        op[PAR_SLIDER_X]    = 18.0
        op[PAR_SLIDER_Y]    = 35.0
        op[PAR_SLIDER_Z]    = 50.0
        op[PAR_RANDOM_SEED] = 1235
        op[PAR_NOISE_AMT]   = 0.5
        op[PAR_NOISE_FREQ]  = 3.0
        op[PAR_NOISE_LOOP]  = 0.0
        op[PAR_PATTERN_ROT] = 0.0
        op[PAR_GRID_SCALE]  = 1.0
        return True

    def GetVirtualObjects(self, op, hh):
        """
        Главный метод генерации: вызывается при каждом
        обновлении сцены. Возвращает c4d.PolygonObject
        или None если источника нет.
        """
        # Берём первого дочернего потомка
        child = op.GetDown()
        if child is None:
            return None

        # Помечаем зависимость от потомка (для кэша)
        hh.AddDependenceList(op)

        # Получаем полигональный кэш потомка
        src = child.GetDeformCache()
        if src is None:
            src = child.GetCache(hh)
        if src is None:
            src = child

        # Если не полигональный — пытаемся конвертировать
        if not src.CheckType(c4d.Opolygon):
            result_list = utils.SendModelingCommand(
                command = c4d.MCOMMAND_CURRENTSTATETOOBJECT,
                list    = [src.GetClone()],
                mode    = c4d.MODELINGCOMMANDMODE_ALL,
                doc     = op.GetDocument()
            )
            if not result_list:
                return None
            src = result_list[0]

        # Собираем словарь параметров
        params = {
            "iterations":  op[PAR_ITERATIONS],
            "slider_x":    op[PAR_SLIDER_X],
            "slider_y":    op[PAR_SLIDER_Y],
            "slider_z":    op[PAR_SLIDER_Z],
            "random_seed": op[PAR_RANDOM_SEED],
            "noise_amt":   op[PAR_NOISE_AMT],
            "noise_freq":  op[PAR_NOISE_FREQ],
            "noise_loop":  op[PAR_NOISE_LOOP],
            "pattern_rot": op[PAR_PATTERN_ROT],
            "grid_scale":  op[PAR_GRID_SCALE],
        }

        # Вызываем нужный алгоритм
        alg  = op[PAR_ALGORITHM]
        func = ALGORITHM_REGISTRY.get(alg)
        if func is None:
            return None

        try:
            mb  = func(src, params)
            res = mb.build()
        except Exception as e:
            print("[PolySubdivider] Ошибка генерации: {}".format(e))
            return None

        if res is None:
            return None

        res.SetName("PolySubdivider [{}]".format(ALG_NAMES[alg]))
        return res

    def GetDDescription(self, op, description, flags):
        """
        Программное описание параметров.
        Строит панель Атрибуты без .res / .sdr файлов.
        """
        # Загружаем базовое описание (без него не работает)
        if not description.LoadDescription(op.GetType()):
            return False

        # ── Группа «Настройки подразделения» ────────────────
        grp_bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        grp_bc[c4d.DESC_NAME]       = "Настройки подразделения"
        grp_bc[c4d.DESC_SHORT_NAME] = "Настройки"
        grp_bc[c4d.DESC_COLUMNS]    = 1
        grp_bc[c4d.DESC_DEFAULT]    = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GRP_SETTINGS, c4d.DTYPE_GROUP, 0)),
            grp_bc,
            c4d.ID_ROOT_CLASSID
        )
        gid = c4d.DescID(c4d.DescLevel(GRP_SETTINGS, c4d.DTYPE_GROUP, 0))

        # Алгоритм — выпадающий список (cycle)
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Алгоритм"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = ALG_UNIFORM
        cyc = c4d.BaseContainer()
        for i, name in enumerate(ALG_NAMES):
            cyc[i] = name
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_ALGORITHM, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # Итерации
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Итерации"
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 8
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_DEFAULT] = 3
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_ITERATIONS, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # Смещение X
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Смещение X"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 100.0
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 18.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_X, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Смещение Y
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Смещение Y"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 100.0
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 35.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_Y, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Смещение Z
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Смещение Z"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 100.0
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 50.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_Z, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Угол паттерна
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Угол паттерна"
        bc[c4d.DESC_MIN]     = -180.0
        bc[c4d.DESC_MAX]     = 180.0
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_DEFAULT] = 0.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_PATTERN_ROT, c4d.DTYPE_REAL, 0)),
            bc, gid
        )

        # Зерно случайных чисел
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Зерно случайности"
        bc[c4d.DESC_MIN]     = 0
        bc[c4d.DESC_MAX]     = 99999
        bc[c4d.DESC_STEP]    = 1
        bc[c4d.DESC_DEFAULT] = 1235
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_RANDOM_SEED, c4d.DTYPE_LONG, 0)),
            bc, gid
        )

        # ── Группа «Шум» ─────────────────────────────────────
        grp_n = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        grp_n[c4d.DESC_NAME]       = "Шум"
        grp_n[c4d.DESC_SHORT_NAME] = "Шум"
        grp_n[c4d.DESC_COLUMNS]    = 1
        grp_n[c4d.DESC_DEFAULT]    = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(GRP_NOISE, c4d.DTYPE_GROUP, 0)),
            grp_n,
            c4d.ID_ROOT_CLASSID
        )
        nid = c4d.DescID(c4d.DescLevel(GRP_NOISE, c4d.DTYPE_GROUP, 0))

        # Величина шума
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Величина шума"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 50.0
        bc[c4d.DESC_STEP]    = 0.1
        bc[c4d.DESC_DEFAULT] = 0.5
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_AMT, c4d.DTYPE_REAL, 0)),
            bc, nid
        )

        # Частота шума
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Частота шума"
        bc[c4d.DESC_MIN]     = 0.1
        bc[c4d.DESC_MAX]     = 20.0
        bc[c4d.DESC_STEP]    = 0.1
        bc[c4d.DESC_DEFAULT] = 3.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_FREQ, c4d.DTYPE_REAL, 0)),
            bc, nid
        )

        # Петля шума
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Петля шума"
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 100.0
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc[c4d.DESC_DEFAULT] = 0.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_LOOP, c4d.DTYPE_REAL, 0)),
            bc, nid
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED


# ============================================================
#  Точка входа — PluginMessage (стандарт для .pyp плагинов)
# ============================================================

def PluginMessage(id, data):
    """
    Вызывается Cinema 4D при старте и других событиях.
    Регистрация плагина происходит здесь, а не в __main__.
    """
    if id == c4d.C4DPL_BUILDMENU:
        pass
    return False


# Регистрируем плагин при загрузке модуля
if __name__ == "__main__":
    plugins.RegisterObjectPlugin(
        id          = PLUGIN_ID,
        str         = "PolySubdivider",
        g           = PolySubdividerObject,
        description = "",          # пустая строка = без .res файла
        icon        = None,
        info        = c4d.OBJECT_GENERATOR | c4d.OBJECT_INPUT,
    )