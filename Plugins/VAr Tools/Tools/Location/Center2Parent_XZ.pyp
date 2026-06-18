# -*- coding: utf-8 -*-
"""
Center2Parent XZ — Cinema 4D Command Plugin
Центрирует выделенные объекты по осям X и Z относительно центра родителя
(Null или любого другого объекта), без изменения Y.

Ключевой момент: родитель может быть повёрнут. Центрирование происходит
в МИРОВОМ пространстве XZ — т.е. центр BBox объекта совмещается с мировой
проекцией позиции родителя на плоскость XZ. Угол поворота родителя не влияет
на результат: объект всегда выравнивается по мировой горизонтали.

Если у объекта нет родителя — поведение идентично Center2World XZ (X=0, Z=0).
"""
import c4d # type: ignore
import base64

PLUGIN_ID     = 1068838
PLUGIN_NAME = "Center2Parent XZ v1.1.1"
PLUGIN_HELP   = "Центрировать по X и Z в позицию родителя (мировое пространство, Y не меняется)"


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA9UlEQVR4nGNgGAUDDBgxRC7daYKz9VTqaMLXU6nD7SRkDbQAaOYzUWre////Kyg1AxWQEAL/ezT+wzB1HUGk5QwMiBAg2hEEo4CIEIBb+v9/BUOvZjsKn0RAVhpgZGTswEdTBoZKGoA74v//CpIcQI00gAwoDXaKywFKAQtOGVKK2F0+pKmnNhjQREipIwZxGsAFLt3B7lNIOsAfCnoqGNU/6Q6AAAEsYh9wiCPLY4ABjwKqOYDRbYvA/10+HwbMAeSC4eUARrctAgPqAHLAqAPwOmBB1P8tOKQ+kIFJA3gspyrA7JoRYXnCMkYf2jiHBEdQCwAAlxCX1RyWIy4AAAAASUVORK5CYII="
)


def _make_icon():
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

def _collect_bounds(o, mn_x, mx_x, mn_z, mx_z):
    """
    Рекурсивно обходит объект o внутри кешированного мира C4D.
    Приоритет: деформ-кеш → кеш генератора → прямые вершины PointObject.
    Всегда спускается в GetDown() внутри кеша (иерархичные кеши SDS и т.п.).
    """
    dc = o.GetDeformCache()
    if dc:
        _collect_bounds(dc, mn_x, mx_x, mn_z, mx_z)
        return

    cache = o.GetCache()
    if cache:
        c = cache
        while c:
            _collect_bounds(c, mn_x, mx_x, mn_z, mx_z)
            c = c.GetNext()
        return

    if o.IsInstanceOf(c4d.Opoint):
        mg  = o.GetMg()
        pts = o.GetAllPoints()
        for p in pts:
            wp = mg * p
            if wp.x < mn_x[0]: mn_x[0] = wp.x
            if wp.x > mx_x[0]: mx_x[0] = wp.x
            if wp.z < mn_z[0]: mn_z[0] = wp.z
            if wp.z > mx_z[0]: mx_z[0] = wp.z

    child = o.GetDown()
    while child:
        _collect_bounds(child, mn_x, mx_x, mn_z, mx_z)
        child = child.GetNext()


def _get_world_center_xz(obj):
    """
    Возвращает (center_x, center_z) — центр bounding box объекта
    в мировых координатах XZ. Возвращает (None, None) если геометрии нет.
    """
    mn_x = [float("inf")]
    mx_x = [float("-inf")]
    mn_z = [float("inf")]
    mx_z = [float("-inf")]

    def _scene_traverse(o):
        dc    = o.GetDeformCache()
        cache = o.GetCache()

        if dc:
            _collect_bounds(dc, mn_x, mx_x, mn_z, mx_z)
        elif cache:
            c = cache
            while c:
                _collect_bounds(c, mn_x, mx_x, mn_z, mx_z)
                c = c.GetNext()
        elif o.IsInstanceOf(c4d.Opoint):
            mg  = o.GetMg()
            pts = o.GetAllPoints()
            for p in pts:
                wp = mg * p
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

    if mn_x[0] == float("inf"):
        return None, None

    return (mn_x[0] + mx_x[0]) / 2.0, (mn_z[0] + mx_z[0]) / 2.0


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class Center2ParentXZCommand(c4d.plugins.CommandData):

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
            # Мировая позиция родителя (только X и Z).
            # GetMg().off — это мировая позиция объекта независимо от поворота.
            # Если родителя нет — целевая точка (0, 0).
            parent_obj = obj.GetUp()
            if parent_obj:
                parent_world_pos = parent_obj.GetMg().off   # мировые координаты
                target_x = parent_world_pos.x
                target_z = parent_world_pos.z
            else:
                target_x = 0.0
                target_z = 0.0

            center_x, center_z = _get_world_center_xz(obj)
            world_pos = obj.GetMg().off

            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

            if center_x is None:
                # Нет геометрии — перемещаем pivot к мировой XZ-позиции родителя
                target_world = c4d.Vector(target_x, world_pos.y, target_z)
            else:
                # Смещаем так, чтобы центр BBox совпал с мировой XZ-позицией родителя
                target_world = c4d.Vector(
                    world_pos.x - (center_x - target_x),
                    world_pos.y,
                    world_pos.z - (center_z - target_z)
                )

            # Конвертируем в локальное пространство родителя
            if parent_obj:
                target_local = ~parent_obj.GetMg() * target_world
            else:
                target_local = target_world

            obj.SetRelPos(target_local)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED if doc.GetActiveObjects(0) else 0


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = Center2ParentXZCommand(),
    )
