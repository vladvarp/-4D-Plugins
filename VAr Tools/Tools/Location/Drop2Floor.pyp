# -*- coding: utf-8 -*-
"""
Drop2Floor — Cinema 4D Command Plugin
Опускает выделенные объекты (и их иерархии) на уровень пола (Y = 0).
"""
import c4d
import base64

PLUGIN_ID   = 1068826
PLUGIN_NAME = "Drop2Floor v1.2"
PLUGIN_HELP = "Опустить выделенные объекты на уровень пола (Y = 0)"


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAtUlEQVR4nGM0MDD4"
    "zzCAgGkgLWdgYGBgwSb4zm4NTSwTOhRCnAMYGBgYjIyUqWr5uXN3sYoPeBSMOmDU"
    "AaMOGHAH4CyIcBUc1AaMlFRG5xf9YGBgYGAwjOMg2wEDHgWjDhh1wKgDRh1AUkkI"
    "K/nwAVJLRZJCgJDh5BTJJEcBLkvIrQ/ISgPolg1IZQSzlBLLGRjQEuGiRYsoMoxY"
    "EBcXB2ejNEjOnTtHFwcgA4oaJNQAA14QAQB7SyCqtzUESwAAAABJRU5ErkJggg=="
)


def _make_icon():
    """Загружает иконку из встроенного base64 PNG и возвращает BaseBitmap."""
    png_data = base64.b64decode(_ICON_B64)

    # Совместимость: c4d.bitmaps.BaseBitmap (2024+) или c4d.BaseBitmap (старые)
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()

    # Записываем PNG во временный файл и загружаем через штатный метод C4D
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        bmp.InitWith(tmp.name)
    finally:
        os.unlink(tmp.name)

    return bmp


# ─── ВЫЧИСЛЕНИЕ BOUNDING BOX ─────────────────────────────────────────────────

def _collect_min_y(o, result):
    """
    Рекурсивно обходит объект o внутри кешированного мира C4D.

    Логика на каждом узле:
      1. Деформ-кеш есть → идём только в него (финальная деформированная геометрия).
      2. Кеш генератора есть → идём только в него (SDS, Extrude, Cloner и т.п.),
         реальные дети сцены игнорируются.
      3. PointObject без кеша → читаем вершины.
      4. Прочее → ничего не берём.

    После обработки текущего узла ВСЕГДА спускаемся в GetDown(),
    потому что кеш может быть иерархичным (например SDS с Null внутри
    порождает дерево сглаженных мешей, а не плоский список).
    """
    # Деформированный кеш — наивысший приоритет
    dc = o.GetDeformCache()
    if dc:
        _collect_min_y(dc, result)
        # После деформ-кеша дочерние объекты не нужны
        return

    # Кеш генератора (SDS, Extrude, Cloner, ...)
    cache = o.GetCache()
    if cache:
        c = cache
        while c:
            _collect_min_y(c, result)
            c = c.GetNext()
        # Кеш генератора заменяет реальных детей сцены — не идём в GetDown()
        return

    # Нет кеша — если PointObject, берём вершины
    if o.IsInstanceOf(c4d.Opoint):
        mg  = o.GetMg()
        pts = o.GetAllPoints()
        for p in pts:
            wy = (mg * p).y
            if wy < result[0]:
                result[0] = wy
        # Продолжаем вниз: у PointObject в кеше могут быть дочерние объекты

    # Спускаемся в дочерние объекты текущего кеш-узла (обязательно для
    # иерархичных кешей: SDS(Null(Куб, Куб.1, ...)) → дерево сглаженных мешей)
    child = o.GetDown()
    while child:
        _collect_min_y(child, result)
        child = child.GetNext()


def _min_world_y(obj):
    """
    Возвращает минимальную мировую Y-координату для obj и всей его иерархии.

    Ключевое отличие от наивного подхода: обход ведётся по КЕШУ, а не по
    реальной иерархии сцены. Это означает, что:
    - Subdivision Surface → берётся сглаженный меш (кеш SDS), а не куб внутри.
    - Bend/Twist/FFD → берётся деформированная геометрия (деформ-кеш).
    - Cloner → берётся кеш всех клонов.
    - Обычный меш без генераторов → вершины напрямую.

    Реальная иерархия сцены обходится только для объектов, у которых нет
    собственного кеша (например, Null с несколькими дочерними мешами).
    """
    result = [float("inf")]

    def _scene_traverse(o):
        """Обход по реальной иерархии сцены (верхний уровень)."""
        dc    = o.GetDeformCache()
        cache = o.GetCache()

        if dc:
            _collect_min_y(dc, result)
        elif cache:
            c = cache
            while c:
                _collect_min_y(c, result)
                c = c.GetNext()
        elif o.IsInstanceOf(c4d.Opoint):
            mg  = o.GetMg()
            pts = o.GetAllPoints()
            for p in pts:
                wy = (mg * p).y
                if wy < result[0]:
                    result[0] = wy
        else:
            # Null или подобный контейнер — спускаемся по реальным детям
            child = o.GetDown()
            while child:
                _scene_traverse(child)
                child = child.GetNext()
            return  # дети уже обойдены выше

        # Если объект имеет кеш/геометрию, его реальные дети — это входные
        # данные генератора, а не самостоятельные объекты; их не обходим.

    _scene_traverse(obj)
    return result[0]


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class Drop2FloorCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        # GETACTIVEOBJECTFLAGS_CHILDREN исключает объекты, чей родитель
        # уже есть в списке — иначе дочерние объекты сдвинутся дважды
        # (сами и вместе с родителем).
        try:
            flags = c4d.GETACTIVEOBJECTFLAGS_CHILDREN
        except AttributeError:
            flags = 1  # числовое значение флага для старых версий C4D

        objects = doc.GetActiveObjects(flags)
        if not objects:
            c4d.gui.MessageDialog("Нет выделенных объектов.")
            return True

        doc.StartUndo()

        for obj in objects:
            min_y = _min_world_y(obj)

            if min_y == float("inf"):
                continue   # нет геометрии — пропускаем (пустой Null и т.п.)

            pos = obj.GetAbsPos()
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.SetAbsPos(c4d.Vector(pos.x, pos.y - min_y, pos.z))

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        """Кнопка активна при наличии одного или нескольких выделенных объектов."""
        return c4d.CMD_ENABLED if doc.GetActiveObjects(0) else 0


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = Drop2FloorCommand(),
    )
