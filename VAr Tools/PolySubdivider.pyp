# ============================================================
#  PolySubdivider — плагин для Cinema 4D R26
#  Расширенный аналог Divider: несколько алгоритмов разбиения
#  полигонов с возможностью лёгкого добавления новых типов.
#
#  Установка:
#    Скопировать файл в папку:
#    .../Cinema 4D R26/plugins/PolySubdivider/PolySubdivider.py
#
#  ID плагина: задать в переменной PLUGIN_ID ниже
# ============================================================

import c4d
from c4d import plugins, utils, gui
import math
import random

# ── Замените на свой ID с https://plugincafe.maxon.net/forum/ ──
PLUGIN_ID = 1068837   # <-- ВРЕМЕННЫЙ ID, заменить!

# ============================================================
#  Константы параметров (уникальные ID для каждого атрибута)
# ============================================================
# Тип алгоритма
PAR_ALGORITHM    = 1000
# Количество итераций
PAR_ITERATIONS   = 1001
# Смещение X (0..100 %)
PAR_SLIDER_X     = 1002
# Смещение Y (0..100 %)
PAR_SLIDER_Y     = 1003
# Случайное зерно
PAR_RANDOM_SEED  = 1004
# Шум
PAR_NOISE_AMT    = 1005
PAR_NOISE_FREQ   = 1006
PAR_NOISE_LOOP   = 1007
# Смещение Z (для 3‑D разбиений)
PAR_SLIDER_Z     = 1008
# Угол поворота паттерна (градусы)
PAR_PATTERN_ROT  = 1009
# Масштаб сетки
PAR_GRID_SCALE   = 1010

# ============================================================
#  Индексы алгоритмов — добавляйте сюда новые значения
# ============================================================
ALG_UNIFORM      = 0   # Равномерное деление (аналог Dmitris)
ALG_RANDOM       = 1   # Случайное деление
ALG_DIAGONAL     = 2   # Диагональный паттерн
ALG_HERRINGBONE  = 3   # «Ёлочка»
ALG_RADIAL       = 4   # Радиальное деление
ALG_VORONOI      = 5   # Воронои‑подобная сетка
# ── Добавьте новый алгоритм: ALG_MYALG = 6  ──

# Имена алгоритмов для выпадающего списка (на русском)
ALG_NAMES = [
    "Равномерное",      # 0
    "Случайное",        # 1
    "Диагональ",        # 2
    "Ёлочка",           # 3
    "Радиальное",       # 4
    "Вороной",          # 5
    # "Моё новое",      # 6  ← пример расширения
]

# ============================================================
#  Вспомогательные геометрические функции
# ============================================================

def lerp(a, b, t):
    """Линейная интерполяция двух точек c4d.Vector."""
    return a + (b - a) * t


def mid(a, b):
    """Средняя точка отрезка."""
    return (a + b) * 0.5


def noise3(x, y, z, freq=1.0):
    """
    Простой детерминированный шум на основе синуса.
    Заменяет внешние библиотеки (perlin и т.п.).
    """
    x *= freq
    y *= freq
    z *= freq
    return (math.sin(x * 127.1 + y * 311.7 + z * 74.9) * 0.5 + 0.5)


def rotate2d(px, py, angle_deg):
    """Поворот 2‑D точки вокруг начала координат."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    return px * ca - py * sa, px * sa + py * ca

# ============================================================
#  Строитель полигональной сетки
# ============================================================

class MeshBuilder:
    """
    Накапливает вершины и полигоны, затем записывает их
    в объект PolygonObject.
    """

    def __init__(self):
        self.verts = []    # список c4d.Vector
        self.polys = []    # список кортежей (a, b, c[, d])

    def add_vert(self, v):
        idx = len(self.verts)
        self.verts.append(v)
        return idx

    def add_quad(self, a, b, c, d):
        self.polys.append((a, b, c, d))

    def add_tri(self, a, b, c):
        self.polys.append((a, b, c, c))   # треугольник как вырожденный quad

    def build(self):
        """Создаёт и возвращает c4d.PolygonObject."""
        obj = c4d.PolygonObject(len(self.verts), len(self.polys))
        for i, v in enumerate(self.verts):
            obj.SetPoint(i, v)
        for i, p in enumerate(self.polys):
            obj.SetPolygon(i, c4d.CPolygon(*p))
        obj.Message(c4d.MSG_UPDATE)
        return obj

# ============================================================
#  Алгоритмы подразделения
#  Каждый алгоритм — функция:
#    subdivide_*(src_obj, params) -> MeshBuilder
#  params — словарь с параметрами (итерации, слайдеры и т.д.)
# ============================================================

def _get_source_polys(src_obj):
    """
    Возвращает список полигонов исходного объекта в виде
    списка списков вершин [[v0, v1, v2, v3], ...].
    """
    pc = src_obj.GetPointCount()
    pts = [src_obj.GetPoint(i) for i in range(pc)]
    polys_out = []
    for i in range(src_obj.GetPolygonCount()):
        p = src_obj.GetPolygon(i)
        quad = [pts[p.a], pts[p.b], pts[p.c], pts[p.d]]
        # Если треугольник (c == d) — оставляем 3 вершины
        if p.c == p.d:
            polys_out.append(quad[:3])
        else:
            polys_out.append(quad)
    return polys_out


def subdivide_uniform(src_obj, params):
    """
    Равномерное подразделение: каждый полигон делится на
    (iter+1)^2 равных частей по UV‑сетке.
    Slider X / Y задают смещение внутренних рёбер (0..1).
    """
    iters  = max(1, params["iterations"])
    sx     = params["slider_x"] / 100.0
    sy     = params["slider_y"] / 100.0
    noise  = params["noise_amt"]
    freq   = params["noise_freq"]
    seed   = params["random_seed"]
    rng    = random.Random(seed)

    polys_src = _get_source_polys(src_obj)
    mb = MeshBuilder()

    div = iters + 1   # кол‑во делений по каждой оси

    for poly in polys_src:
        is_quad = len(poly) == 4
        if not is_quad:
            # Треугольники подразделяем как вырожденный quad
            poly = [poly[0], poly[1], poly[2], poly[2]]

        # Сетка (div+1) × (div+1) вершин
        grid = []
        for j in range(div + 1):
            row = []
            v = j / div
            # Применяем смещение слайдера к внутренним рядам
            if 0 < j < div:
                v = v + (sy - 0.5) * (1.0 / div)
                v = max(0.0, min(1.0, v))
            for i in range(div + 1):
                u = i / div
                if 0 < i < div:
                    u = u + (sx - 0.5) * (1.0 / div)
                    u = max(0.0, min(1.0, u))

                # Билинейная интерполяция по quad
                p0 = lerp(poly[0], poly[1], u)
                p1 = lerp(poly[3], poly[2], u)
                pt = lerp(p0, p1, v)

                # Добавляем шум
                if noise > 0:
                    n = noise3(pt.x, pt.y, pt.z, freq) * 2 - 1
                    pt += c4d.Vector(
                        n * noise * rng.uniform(0.8, 1.2),
                        n * noise * rng.uniform(0.8, 1.2),
                        n * noise * rng.uniform(0.8, 1.2)
                    )
                row.append(mb.add_vert(pt))
            grid.append(row)

        # Создаём quad‑полигоны по сетке
        for j in range(div):
            for i in range(div):
                a = grid[j][i]
                b = grid[j][i + 1]
                c = grid[j + 1][i + 1]
                d = grid[j + 1][i]
                mb.add_quad(a, b, c, d)

    return mb


def subdivide_random(src_obj, params):
    """
    Случайное подразделение: каждый полигон делится
    произвольным горизонтальным или вертикальным разрезом
    (количество разрезов = iterations).
    """
    iters = max(1, params["iterations"])
    seed  = params["random_seed"]
    noise = params["noise_amt"]
    rng   = random.Random(seed)

    polys_src = _get_source_polys(src_obj)
    mb = MeshBuilder()

    def split_poly_h(quad, t):
        """Горизонтальный разрез квада на двух уровне t."""
        p0, p1, p2, p3 = quad
        m01 = lerp(p0, p3, t)
        m12 = lerp(p1, p2, t)
        return [p0, p1, m12, m01], [m01, m12, p2, p3]

    def split_poly_v(quad, t):
        """Вертикальный разрез квада."""
        p0, p1, p2, p3 = quad
        m03 = lerp(p0, p1, t)
        m32 = lerp(p3, p2, t)
        return [p0, m03, m32, p3], [m03, p1, p2, m32]

    for poly in polys_src:
        if len(poly) == 3:
            poly = [poly[0], poly[1], poly[2], poly[2]]
        pieces = [poly]

        for _ in range(iters):
            new_pieces = []
            for piece in pieces:
                t = rng.uniform(0.2, 0.8)
                # Шум смещает точку разреза
                if noise > 0:
                    t += (rng.random() - 0.5) * noise * 0.3
                    t = max(0.1, min(0.9, t))
                if rng.random() < 0.5:
                    a, b = split_poly_h(piece, t)
                else:
                    a, b = split_poly_v(piece, t)
                new_pieces.extend([a, b])
            pieces = new_pieces

        # Добавляем итоговые куски в меш
        for piece in pieces:
            idxs = [mb.add_vert(v) for v in piece]
            mb.add_quad(*idxs)

    return mb


def subdivide_diagonal(src_obj, params):
    """
    Диагональный паттерн: полигон делится по двум диагоналям
    на 4 треугольника, затем каждый итерируется повторно.
    """
    iters  = max(1, params["iterations"])
    sx     = params["slider_x"] / 100.0
    noise  = params["noise_amt"]
    rng    = random.Random(params["random_seed"])

    polys_src = _get_source_polys(src_obj)
    mb = MeshBuilder()

    def diag_split(quad, depth):
        """Рекурсивное диагональное деление."""
        p0, p1, p2, p3 = quad
        center = (p0 + p1 + p2 + p3) * 0.25
        # Смещение центра по слайдеру
        edge_mid = lerp(mid(p0, p1), mid(p2, p3), sx)
        center = lerp(center, edge_mid, 0.3)

        if noise > 0:
            n = noise3(center.x, center.y, center.z) * 2 - 1
            center += c4d.Vector(
                n * noise * rng.uniform(0.5, 1.5),
                n * noise * rng.uniform(0.5, 1.5),
                n * noise * rng.uniform(0.5, 1.5)
            )

        if depth <= 1:
            ci = mb.add_vert(center)
            idxs = [mb.add_vert(v) for v in quad]
            mb.add_tri(idxs[0], idxs[1], ci)
            mb.add_tri(idxs[1], idxs[2], ci)
            mb.add_tri(idxs[2], idxs[3], ci)
            mb.add_tri(idxs[3], idxs[0], ci)
        else:
            sub_quads = [
                [p0, mid(p0, p1), center, mid(p0, p3)],
                [mid(p0, p1), p1, mid(p1, p2), center],
                [center, mid(p1, p2), p2, mid(p2, p3)],
                [mid(p0, p3), center, mid(p2, p3), p3],
            ]
            for sq in sub_quads:
                diag_split(sq, depth - 1)

    for poly in polys_src:
        if len(poly) == 3:
            poly = [poly[0], poly[1], poly[2], poly[2]]
        diag_split(poly, iters)

    return mb


def subdivide_herringbone(src_obj, params):
    """
    Паттерн «Ёлочка» (Herringbone): смещённая сетка прямоугольников,
    как в паркетной укладке.
    """
    iters   = max(1, params["iterations"])
    sx      = params["slider_x"] / 100.0
    sy      = params["slider_y"] / 100.0
    rot_deg = params.get("pattern_rot", 0.0)
    noise   = params["noise_amt"]
    rng     = random.Random(params["random_seed"])

    polys_src = _get_source_polys(src_obj)
    mb = MeshBuilder()

    div = iters + 1

    for poly in polys_src:
        if len(poly) == 3:
            poly = [poly[0], poly[1], poly[2], poly[2]]

        p0, p1, p2, p3 = poly

        # Строим сетку с чередованием смещения через строку
        grid = []
        for row in range(div + 1):
            v_row = []
            t_v = row / div
            offset_u = (sx * 0.5) if (row % 2 == 1) else 0.0  # смещение «ёлочки»
            for col in range(div + 1):
                t_u = col / div + offset_u
                t_u = t_u - math.floor(t_u)  # wrap [0..1]

                # Используем sy для сжатия/растяжения ячеек по Y
                t_v_adj = t_v * (0.5 + sy)
                t_v_adj = min(t_v_adj, 1.0)

                pt_bot = lerp(p0, p1, t_u)
                pt_top = lerp(p3, p2, t_u)
                pt = lerp(pt_bot, pt_top, t_v_adj)

                # Шум
                if noise > 0:
                    n = noise3(pt.x, pt.y, pt.z) * 2 - 1
                    pt += c4d.Vector(
                        n * noise * rng.uniform(0.7, 1.3),
                        n * noise * rng.uniform(0.7, 1.3),
                        n * noise * rng.uniform(0.7, 1.3)
                    )
                v_row.append(mb.add_vert(pt))
            grid.append(v_row)

        for j in range(div):
            for i in range(div):
                a = grid[j][i]
                b = grid[j][i + 1]
                c = grid[j + 1][i + 1]
                d = grid[j + 1][i]
                mb.add_quad(a, b, c, d)

    return mb


def subdivide_radial(src_obj, params):
    """
    Радиальное деление: из центра каждого полигона расходятся
    лучи, создавая «пирожковую» нарезку.
    """
    iters  = max(1, params["iterations"])
    sx     = params["slider_x"] / 100.0  # смещение центра по X
    sy     = params["slider_y"] / 100.0  # смещение центра по Y
    noise  = params["noise_amt"]
    rng    = random.Random(params["random_seed"])

    # Количество секторов = iters * 2 (минимум 3)
    sectors = max(3, iters * 2)

    polys_src = _get_source_polys(src_obj)
    mb = MeshBuilder()

    for poly in polys_src:
        if len(poly) == 3:
            poly = [poly[0], poly[1], poly[2], poly[2]]

        p0, p1, p2, p3 = poly

        # Центр полигона со смещением слайдера
        center_u = 0.5 + (sx - 0.5) * 0.8
        center_v = 0.5 + (sy - 0.5) * 0.8
        pt_bot = lerp(p0, p1, center_u)
        pt_top = lerp(p3, p2, center_u)
        center = lerp(pt_bot, pt_top, center_v)

        if noise > 0:
            n = noise3(center.x, center.y, center.z) * 2 - 1
            center += c4d.Vector(
                n * noise * rng.uniform(0.5, 1.5),
                n * noise * rng.uniform(0.5, 1.5),
                n * noise * rng.uniform(0.5, 1.5)
            )

        ci = mb.add_vert(center)

        # Собираем периметр полигона
        rim = []
        # Нижнее ребро
        for k in range(sectors // 4):
            t = k / (sectors // 4)
            rim.append(lerp(p0, p1, t))
        # Правое ребро
        for k in range(sectors // 4):
            t = k / (sectors // 4)
            rim.append(lerp(p1, p2, t))
        # Верхнее ребро (обратно)
        for k in range(sectors // 4):
            t = k / (sectors // 4)
            rim.append(lerp(p2, p3, t))
        # Левое ребро (обратно)
        for k in range(sectors // 4):
            t = k / (sectors // 4)
            rim.append(lerp(p3, p0, t))

        rim_ids = [mb.add_vert(v) for v in rim]
        n_rim = len(rim_ids)

        for k in range(n_rim):
            a = rim_ids[k]
            b = rim_ids[(k + 1) % n_rim]
            mb.add_tri(ci, a, b)

    return mb


def subdivide_voronoi(src_obj, params):
    """
    Вороной‑подобное деление: случайно расставляются точки
    внутри полигона, затем делается упрощённая аппроксимация
    ячеек через триангуляцию от ближайших соседей.
    """
    iters  = max(1, params["iterations"])
    noise  = params["noise_amt"]
    seed   = params["random_seed"]
    rng    = random.Random(seed)

    # Количество точек = iters^2 (ограничиваем разумным числом)
    num_sites = min(iters * iters, 25)

    polys_src = _get_source_polys(src_obj)
    mb = MeshBuilder()

    for poly in polys_src:
        if len(poly) == 3:
            poly = [poly[0], poly[1], poly[2], poly[2]]
        p0, p1, p2, p3 = poly

        # Случайные точки‑сайты внутри полигона
        sites = []
        for _ in range(num_sites):
            u = rng.uniform(0.1, 0.9)
            v = rng.uniform(0.1, 0.9)
            pt_bot = lerp(p0, p1, u)
            pt_top = lerp(p3, p2, u)
            pt = lerp(pt_bot, pt_top, v)
            if noise > 0:
                n = noise3(pt.x, pt.y, pt.z) * 2 - 1
                pt += c4d.Vector(
                    n * noise * rng.uniform(0.3, 1.0),
                    n * noise * rng.uniform(0.3, 1.0),
                    n * noise * rng.uniform(0.3, 1.0)
                )
            sites.append(pt)

        # Упрощённая схема: для каждой пары соседних сайтов
        # строим quad через середины рёбер периметра
        site_ids = [mb.add_vert(s) for s in sites]

        # Соединяем каждый сайт с его двумя ближайшими соседями
        for i, si in enumerate(sites):
            # Находим ближайший сайт
            dists = []
            for j, sj in enumerate(sites):
                if i != j:
                    d = (si - sj).GetLength()
                    dists.append((d, j))
            dists.sort()
            # Берём 2 ближайших
            neighbors = [dists[k][1] for k in range(min(2, len(dists)))]
            mid_center = mb.add_vert(si)
            for nb in neighbors:
                m = mid(si, sites[nb])
                mi = mb.add_vert(m)
                mb.add_tri(site_ids[i], mi, site_ids[nb])

    return mb

# ============================================================
#  Реестр алгоритмов
#  Добавьте свою функцию сюда, чтобы она стала доступна в UI
# ============================================================
ALGORITHM_REGISTRY = {
    ALG_UNIFORM:     subdivide_uniform,
    ALG_RANDOM:      subdivide_random,
    ALG_DIAGONAL:    subdivide_diagonal,
    ALG_HERRINGBONE: subdivide_herringbone,
    ALG_RADIAL:      subdivide_radial,
    ALG_VORONOI:     subdivide_voronoi,
    # ALG_MYALG:    subdivide_myalg,  ← добавить здесь
}

# ============================================================
#  Класс плагина — ObjectData
# ============================================================

class PolySubdividerObject(plugins.ObjectData):
    """
    Генераторный объект Cinema 4D.
    Берёт первого дочернего ребёнка (PolygonObject) и
    применяет выбранный алгоритм подразделения.
    """

    @classmethod
    def Register(cls):
        """Регистрация плагина в Cinema 4D."""
        return plugins.RegisterObjectPlugin(
            id          = PLUGIN_ID,
            str         = "PolySubdivider",
            g           = cls,
            description = "Opobjpoly",   # используем базовый ресурс
            icon        = None,
            info        = c4d.OBJECT_GENERATOR | c4d.OBJECT_INPUT,
        )

    def Init(self, op):
        """Инициализация значений по умолчанию."""
        self.InitAttr(op, int,   PAR_ALGORITHM)
        self.InitAttr(op, int,   PAR_ITERATIONS)
        self.InitAttr(op, float, PAR_SLIDER_X)
        self.InitAttr(op, float, PAR_SLIDER_Y)
        self.InitAttr(op, float, PAR_SLIDER_Z)
        self.InitAttr(op, int,   PAR_RANDOM_SEED)
        self.InitAttr(op, float, PAR_NOISE_AMT)
        self.InitAttr(op, float, PAR_NOISE_FREQ)
        self.InitAttr(op, float, PAR_NOISE_LOOP)
        self.InitAttr(op, float, PAR_PATTERN_ROT)
        self.InitAttr(op, float, PAR_GRID_SCALE)

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
        Основной метод генерации геометрии.
        Вызывается Cinema 4D при каждом обновлении сцены.
        """
        # Получаем первого дочернего объекта
        child = op.GetDown()
        if child is None:
            return None   # нет потомка — пустой результат

        # Преобразуем потомка в полигональный объект
        src = child.GetCache(hh)
        if src is None:
            src = child
        if not src.CheckType(c4d.Opolygon):
            # Попытка конвертировать (например, Куб → полигоны)
            src = utils.SendModelingCommand(
                command   = c4d.MCOMMAND_CURRENTSTATETOOBJECT,
                list      = [src],
                mode      = c4d.MODELINGCOMMANDMODE_ALL,
                doc       = op.GetDocument()
            )
            if not src:
                return None
            src = src[0]

        # Собираем параметры из атрибутов плагина
        alg     = op[PAR_ALGORITHM]
        params  = {
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

        # Вызываем нужный алгоритм из реестра
        func = ALGORITHM_REGISTRY.get(alg)
        if func is None:
            return None

        try:
            mb  = func(src, params)
            res = mb.build()
        except Exception as e:
            # Показываем ошибку в консоли, не крашим Cinema 4D
            print(f"[PolySubdivider] Ошибка генерации: {e}")
            return None

        # Называем результат по типу алгоритма
        res.SetName(f"PolySubdivider [{ALG_NAMES[alg]}]")
        return res

    def GetDDescription(self, op, description, flags):
        """
        Динамическое описание параметров (панель Атрибуты).
        Позволяет строить UI программно без .res / .sdr файлов.
        """
        if not description.LoadDescription(op.GetType()):
            return False

        # ── Группа «Настройки» ──────────────────────────────
        grp_settings = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        grp_settings[c4d.DESC_NAME]    = "Настройки"
        grp_settings[c4d.DESC_SHORT_NAME] = "Настройки"
        grp_settings[c4d.DESC_COLUMNS] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0)),
            grp_settings, c4d.ID_ROOT_CLASSID
        )

        # Алгоритм — выпадающий список
        bc_alg = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc_alg[c4d.DESC_NAME]       = "Алгоритм"
        bc_alg[c4d.DESC_SHORT_NAME] = "Алг"
        bc_alg[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
        bc_alg[c4d.DESC_DEFAULT]    = ALG_UNIFORM
        cycle = c4d.BaseContainer()
        for i, name in enumerate(ALG_NAMES):
            cycle[i] = name
        bc_alg[c4d.DESC_CYCLE] = cycle
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_ALGORITHM, c4d.DTYPE_LONG, 0)),
            bc_alg,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # Итерации
        bc_iter = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc_iter[c4d.DESC_NAME]    = "Итерации"
        bc_iter[c4d.DESC_MIN]     = 1
        bc_iter[c4d.DESC_MAX]     = 8
        bc_iter[c4d.DESC_STEP]    = 1
        bc_iter[c4d.DESC_DEFAULT] = 3
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_ITERATIONS, c4d.DTYPE_LONG, 0)),
            bc_iter,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # Слайдер X
        bc_sx = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_sx[c4d.DESC_NAME]    = "Смещение X"
        bc_sx[c4d.DESC_MIN]     = 0.0
        bc_sx[c4d.DESC_MAX]     = 100.0
        bc_sx[c4d.DESC_STEP]    = 1.0
        bc_sx[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc_sx[c4d.DESC_DEFAULT] = 18.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_X, c4d.DTYPE_REAL, 0)),
            bc_sx,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # Слайдер Y
        bc_sy = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_sy[c4d.DESC_NAME]    = "Смещение Y"
        bc_sy[c4d.DESC_MIN]     = 0.0
        bc_sy[c4d.DESC_MAX]     = 100.0
        bc_sy[c4d.DESC_STEP]    = 1.0
        bc_sy[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc_sy[c4d.DESC_DEFAULT] = 35.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_Y, c4d.DTYPE_REAL, 0)),
            bc_sy,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # Слайдер Z
        bc_sz = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_sz[c4d.DESC_NAME]    = "Смещение Z"
        bc_sz[c4d.DESC_MIN]     = 0.0
        bc_sz[c4d.DESC_MAX]     = 100.0
        bc_sz[c4d.DESC_STEP]    = 1.0
        bc_sz[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc_sz[c4d.DESC_DEFAULT] = 50.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_SLIDER_Z, c4d.DTYPE_REAL, 0)),
            bc_sz,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # Угол паттерна
        bc_rot = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_rot[c4d.DESC_NAME]    = "Угол паттерна"
        bc_rot[c4d.DESC_MIN]     = -180.0
        bc_rot[c4d.DESC_MAX]     = 180.0
        bc_rot[c4d.DESC_STEP]    = 1.0
        bc_rot[c4d.DESC_UNIT]    = c4d.DESC_UNIT_DEGREE
        bc_rot[c4d.DESC_DEFAULT] = 0.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_PATTERN_ROT, c4d.DTYPE_REAL, 0)),
            bc_rot,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # Случайное зерно
        bc_seed = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc_seed[c4d.DESC_NAME]    = "Зерно случ."
        bc_seed[c4d.DESC_MIN]     = 0
        bc_seed[c4d.DESC_MAX]     = 99999
        bc_seed[c4d.DESC_STEP]    = 1
        bc_seed[c4d.DESC_DEFAULT] = 1235
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_RANDOM_SEED, c4d.DTYPE_LONG, 0)),
            bc_seed,
            c4d.DescID(c4d.DescLevel(10001, c4d.DTYPE_GROUP, 0))
        )

        # ── Группа «Шум» ────────────────────────────────────
        grp_noise = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        grp_noise[c4d.DESC_NAME]    = "Шум"
        grp_noise[c4d.DESC_SHORT_NAME] = "Шум"
        grp_noise[c4d.DESC_COLUMNS] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(10002, c4d.DTYPE_GROUP, 0)),
            grp_noise, c4d.ID_ROOT_CLASSID
        )

        # Величина шума
        bc_namt = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_namt[c4d.DESC_NAME]    = "Величина шума"
        bc_namt[c4d.DESC_MIN]     = 0.0
        bc_namt[c4d.DESC_MAX]     = 10.0
        bc_namt[c4d.DESC_STEP]    = 0.1
        bc_namt[c4d.DESC_DEFAULT] = 0.5
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_AMT, c4d.DTYPE_REAL, 0)),
            bc_namt,
            c4d.DescID(c4d.DescLevel(10002, c4d.DTYPE_GROUP, 0))
        )

        # Частота шума
        bc_nfrq = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_nfrq[c4d.DESC_NAME]    = "Частота шума"
        bc_nfrq[c4d.DESC_MIN]     = 0.1
        bc_nfrq[c4d.DESC_MAX]     = 20.0
        bc_nfrq[c4d.DESC_STEP]    = 0.1
        bc_nfrq[c4d.DESC_DEFAULT] = 3.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_FREQ, c4d.DTYPE_REAL, 0)),
            bc_nfrq,
            c4d.DescID(c4d.DescLevel(10002, c4d.DTYPE_GROUP, 0))
        )

        # Петля шума
        bc_nlp = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc_nlp[c4d.DESC_NAME]    = "Петля шума %"
        bc_nlp[c4d.DESC_MIN]     = 0.0
        bc_nlp[c4d.DESC_MAX]     = 100.0
        bc_nlp[c4d.DESC_STEP]    = 1.0
        bc_nlp[c4d.DESC_UNIT]    = c4d.DESC_UNIT_PERCENT
        bc_nlp[c4d.DESC_DEFAULT] = 0.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(PAR_NOISE_LOOP, c4d.DTYPE_REAL, 0)),
            bc_nlp,
            c4d.DescID(c4d.DescLevel(10002, c4d.DTYPE_GROUP, 0))
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED


# ============================================================
#  Точка входа
# ============================================================

if __name__ == "__main__":
    PolySubdividerObject.Register()
