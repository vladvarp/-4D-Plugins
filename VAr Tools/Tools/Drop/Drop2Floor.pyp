# -*- coding: utf-8 -*-
"""
Drop2Floor — Cinema 4D Command Plugin
Опускает выделенные объекты (и их иерархии) на уровень пола (Y = 0).
"""
import c4d
import base64

PLUGIN_ID   = 1068826
PLUGIN_NAME = "Drop2Floor v1.0"
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

def _min_world_y(obj):
    """
    Рекурсивно обходит obj и всех его потомков.
    Возвращает минимальную Y-координату bounding box в мировых координатах.
    Учитывает вращение и масштаб через трансформацию всех 8 углов AABB.
    """
    result = [float("inf")]

    def _traverse(o):
        mg  = o.GetMg()    # матрица объекта в мировых координатах
        rad = o.GetRad()   # полуразмеры AABB в локальных координатах
        mp  = o.GetMp()    # центр AABB в локальных координатах

        if rad.x + rad.y + rad.z > 0.0:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        local_pt = mp + c4d.Vector(sx * rad.x, sy * rad.y, sz * rad.z)
                        world_y  = (mg * local_pt).y
                        if world_y < result[0]:
                            result[0] = world_y

        child = o.GetDown()
        while child:
            _traverse(child)
            child = child.GetNext()

    _traverse(obj)
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
