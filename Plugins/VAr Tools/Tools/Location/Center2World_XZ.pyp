# -*- coding: utf-8 -*-
"""
Center2World XZ — Cinema 4D Command Plugin
Центрирует выделенные объекты по мировым осям X и Z (без изменения Y).
Центр bounding box объекта помещается в точку X=0, Z=0 мирового пространства.
"""
import c4d
import base64

PLUGIN_ID   = 1068839
PLUGIN_NAME = "Center2World XZ v1.1.1"
PLUGIN_HELP = "Центрировать выделенные объекты по X и Z в мировом пространстве (Y не меняется)"


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABAElEQVR4nGNgGAWjgFJw6Y4NJdqZqOUOcgEjxSZcurOFaLV6Kj7oQiwUOwACIohQswKbIE2i4L+uMjEOop0DSAHUigIGBgZUn8PYjJfvYg16mjiA8fLdFf93+XxmKL6eSshiGKA4Cv7v8vFGYn9mdNvCS4p+qqUBZMuJ9T0DA4XlwP8ejf9YDXXbshWrBizlAMWW/+/R+A/DeDVcumODrdjGTITElu27fCBqd/kwMLptsf2/y+cwUXov3bFh0FM5QpQd+ADcx1BLyQ0BqqUBxpIbuM2ilq9xGk4BGPCieNQBow4g3wHoqZ/M3EBZmxDZUjLz+YBHAeWAwoJoFAw4AADhhWKXKyybDQAAAABJRU5ErkJggg=="
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
    в мировых координатах XZ. Учитывает кеш генераторов и деформеров.
    Возвращает (None, None) если геометрии нет.
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

class Center2WorldXZCommand(c4d.plugins.CommandData):

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
            center_x, center_z = _get_world_center_xz(obj)
            world_pos = obj.GetMg().off
            parent = obj.GetUp()

            if center_x is None:
                # Нет геометрии — перемещаем pivot в X=0, Z=0 мирового пространства
                target_world = c4d.Vector(0.0, world_pos.y, 0.0)
            else:
                # Смещаем так, чтобы центр BBox оказался в X=0, Z=0
                target_world = c4d.Vector(world_pos.x - center_x, world_pos.y, world_pos.z - center_z)

            # Конвертируем в локальное пространство родителя
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
        return c4d.CMD_ENABLED if doc.GetActiveObjects(0) else 0


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = Center2WorldXZCommand(),
    )
