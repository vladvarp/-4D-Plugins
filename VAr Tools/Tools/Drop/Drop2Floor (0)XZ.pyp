# -*- coding: utf-8 -*-
"""
Drop2Floor 0(XZ) — Cinema 4D Command Plugin
Опускает выделенные объекты на уровень пола (Y = 0)
и центрирует их по X и Z (в центр сцены).
"""
import c4d
import base64

PLUGIN_ID   = 1068827
PLUGIN_NAME = "Drop2Floor 0(XZ) v1.0"
PLUGIN_HELP = "Опустить выделенные объекты на пол (Y=0) и центрировать по X, Z"


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA6ElEQVR4nO2WsQ2D"
    "MBBFP1EK6qxA5c5QR5kCUTKca6bIAE6RwhUrpKZLigQEls/BGHSNfwM6bP0nnf2P"
    "TEr5BqNOnOYAcHYVX7fuELPLvV4HAABVVexqrnXvrLO3IAEkgATADkAGERUceyuL"
    "GUYPNQAAyjbfDMDeggSQABIAOwCZhHupGwZnvc6/4RWUhGPy+TRPRcp8DhEcxT4I"
    "yrwwZrGuF2J6D25B2eZOCGoeFMYsDO3apkNom7EMo9E0xhywWqCUCtr8BEBuaZpw"
    "AK11EIBP19+zF8J7CKN+SP5pzTU8NAnHsPF9+wABYUBjjukSiAAAAABJRU5ErkJg"
    "gg=="
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

def _get_world_bounds(obj):
    """
    Рекурсивно обходит obj и всех его потомков.
    Возвращает (min_y, center_x, center_z) в мировых координатах,
    где center_x/center_z — центр bounding box по горизонтали.
    """
    min_y   = [float("inf")]
    min_x   = [float("inf")]
    max_x   = [float("-inf")]
    min_z   = [float("inf")]
    max_z   = [float("-inf")]

    def _traverse(o):
        mg  = o.GetMg()
        rad = o.GetRad()
        mp  = o.GetMp()

        if rad.x + rad.y + rad.z > 0.0:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        local_pt = mp + c4d.Vector(sx * rad.x, sy * rad.y, sz * rad.z)
                        world_pt = mg * local_pt
                        if world_pt.y < min_y[0]: min_y[0] = world_pt.y
                        if world_pt.x < min_x[0]: min_x[0] = world_pt.x
                        if world_pt.x > max_x[0]: max_x[0] = world_pt.x
                        if world_pt.z < min_z[0]: min_z[0] = world_pt.z
                        if world_pt.z > max_z[0]: max_z[0] = world_pt.z

        child = o.GetDown()
        while child:
            _traverse(child)
            child = child.GetNext()

    _traverse(obj)

    center_x = (min_x[0] + max_x[0]) / 2.0 if min_x[0] != float("inf") else 0.0
    center_z = (min_z[0] + max_z[0]) / 2.0 if min_z[0] != float("inf") else 0.0

    return min_y[0], center_x, center_z


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

            pos = obj.GetAbsPos()
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

            # Новая позиция: X и Z — смещаем так, чтобы центр BBox оказался в 0,
            # Y — опускаем нижнюю грань на пол (Y = 0)
            new_x = pos.x - center_x
            new_z = pos.z - center_z
            new_y = pos.y - min_y

            obj.SetAbsPos(c4d.Vector(new_x, new_y, new_z))

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
