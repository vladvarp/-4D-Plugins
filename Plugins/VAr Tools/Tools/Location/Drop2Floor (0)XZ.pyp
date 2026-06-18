# -*- coding: utf-8 -*-
"""
Drop2Floor 0(XZ) — Cinema 4D Command Plugin
Опускает выделенные объекты на уровень пола (Y = 0)
и центрирует их по X и Z (в центр сцены).
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068827
PLUGIN_NAME = "Drop2Floor 0(XZ) v1.3.1"
PLUGIN_HELP = "Опустить выделенные объекты на пол (Y=0) и центрировать по X, Z"


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA+0lEQVR4nGNgGAUjHTASrfLSnQqKbdNT6UAXYiHRiCkUWJ+DTZCJAgOpAkYdMOqAUQeQWg5gzcsDCv73aPwfWAf8/29EiX6S08CCqP94fUxInioA2RLkEKCL5eiWwRxAruUY1TGpBsUvZTBeGM1wlhQ9CcsYiW8G4ALUCgGKLEd2AN0cgW4JejakiyOQCx9kB9C1UIJZhk6TCihKjciWMpbcoDxlk2M5pSGAWhteumPDwMCggSRyAyd/lw8Dw6U7NowMDKkMlxhSYHyi9eupzEF1CkQz0Xx0H2OEACHzoIDU9gAcMLptsf3f4/Mfmc/AoEKmaST6nmL+YAIAHH2SJUncDyUAAAAASUVORK5CYII="
)


def _make_icon():
    """Загружает иконку из встроенного base64 PNG и возвращает BaseBitmap."""
    png_data = base64.b64decode(_ICON_B64)

    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()

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

def _collect_bounds(o, mn_y, mn_x, mx_x, mn_z, mx_z):
    """
    Рекурсивно обходит объект o внутри кешированного мира C4D.

    Логика на каждом узле:
      1. Деформ-кеш есть → идём только в него.
      2. Кеш генератора есть → идём только в него (SDS, Extrude, Cloner),
         реальные дети сцены игнорируются.
      3. PointObject без кеша → читаем вершины.
      4. Прочее → ничего не берём.

    После обработки текущего узла ВСЕГДА спускаемся в GetDown(),
    потому что кеш может быть иерархичным (SDS с Null внутри
    порождает дерево сглаженных мешей, а не плоский список).
    """
    dc = o.GetDeformCache()
    if dc:
        _collect_bounds(dc, mn_y, mn_x, mx_x, mn_z, mx_z)
        return

    cache = o.GetCache()
    if cache:
        c = cache
        while c:
            _collect_bounds(c, mn_y, mn_x, mx_x, mn_z, mx_z)
            c = c.GetNext()
        return

    if o.IsInstanceOf(c4d.Opoint):
        mg  = o.GetMg()
        pts = o.GetAllPoints()
        for p in pts:
            wp = mg * p
            if wp.y < mn_y[0]: mn_y[0] = wp.y
            if wp.x < mn_x[0]: mn_x[0] = wp.x
            if wp.x > mx_x[0]: mx_x[0] = wp.x
            if wp.z < mn_z[0]: mn_z[0] = wp.z
            if wp.z > mx_z[0]: mx_z[0] = wp.z

    # Всегда спускаемся в дочерние узлы кеша
    child = o.GetDown()
    while child:
        _collect_bounds(child, mn_y, mn_x, mx_x, mn_z, mx_z)
        child = child.GetNext()


def _get_world_bounds(obj):
    """
    Возвращает (min_y, center_x, center_z) в мировых координатах.

    Обход ведётся по КЕШУ, поэтому учитываются генераторы (SDS, Extrude,
    Cloner) и деформеры (Bend, Twist, FFD) — берётся финальная геометрия,
    а не исходный меш.

    Реальная иерархия сцены обходится только для контейнеров без кеша (Null).
    """
    mn_y = [float("inf")]
    mn_x = [float("inf")]
    mx_x = [float("-inf")]
    mn_z = [float("inf")]
    mx_z = [float("-inf")]

    def _scene_traverse(o):
        dc    = o.GetDeformCache()
        cache = o.GetCache()

        if dc:
            _collect_bounds(dc, mn_y, mn_x, mx_x, mn_z, mx_z)
        elif cache:
            c = cache
            while c:
                _collect_bounds(c, mn_y, mn_x, mx_x, mn_z, mx_z)
                c = c.GetNext()
        elif o.IsInstanceOf(c4d.Opoint):
            mg  = o.GetMg()
            pts = o.GetAllPoints()
            for p in pts:
                wp = mg * p
                if wp.y < mn_y[0]: mn_y[0] = wp.y
                if wp.x < mn_x[0]: mn_x[0] = wp.x
                if wp.x > mx_x[0]: mx_x[0] = wp.x
                if wp.z < mn_z[0]: mn_z[0] = wp.z
                if wp.z > mx_z[0]: mx_z[0] = wp.z
        else:
            child = o.GetDown()
            while child:
                _scene_traverse(child)
                child = child.GetNext()
            return

    _scene_traverse(obj)

    center_x = (mn_x[0] + mx_x[0]) / 2.0 if mn_x[0] != float("inf") else 0.0
    center_z = (mn_z[0] + mx_z[0]) / 2.0 if mn_z[0] != float("inf") else 0.0

    return mn_y[0], center_x, center_z


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class Drop2FloorXZCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        try:
            flags = c4d.GETACTIVEOBJECTFLAGS_CHILDREN
        except AttributeError:
            flags = 1

        objects = doc.GetActiveObjects(flags)
        if not objects:
            c4d.gui.MessageDialog("Нет выделенных объектов.")
            return True

        doc.StartUndo()

        for obj in objects:
            min_y, center_x, center_z = _get_world_bounds(obj)

            if min_y == float("inf"):
                continue   # нет геометрии — пропускаем

            # Целевая позиция в мировых координатах:
            # X и Z — смещаем pivot так, чтобы центр BBox оказался в (0, 0),
            # Y — опускаем нижнюю грань на пол (Y = 0)
            world_pos = obj.GetMg().off
            target_world = c4d.Vector(
                world_pos.x - center_x,
                world_pos.y - min_y,
                world_pos.z - center_z
            )
            # Конвертируем в локальное пространство родителя
            parent = obj.GetUp()
            if parent:
                target_local = ~parent.GetMg() * target_world
            else:
                target_local = target_world
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.SetRelPos(target_local)

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
        dat  = Drop2FloorXZCommand(),
    )
