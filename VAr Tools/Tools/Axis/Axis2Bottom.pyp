# -*- coding: utf-8 -*-
"""
AxisToBottomCenter — Cinema 4D Command Plugin
Смещает ось (pivot) выделенных объектов в нижнюю центральную точку их bounding box.
По X и Z — центр, по Y — нижняя грань.
Сами объекты визуально не двигаются.
"""
import c4d
import base64

PLUGIN_ID   = 1068829
PLUGIN_NAME = "Axis2Bottom v1.0"
PLUGIN_HELP = "Переместить ось объекта в нижний центр его bounding box"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAsUlEQVR4nGPU0NBgGEjA"
    "NKC2jzpg1AEMDAws6AI9PT3/aWlhSUkJI14HYFNELYDNcwMeBaMOGHXAqANGHTDqgKHt"
    "gOsaGv+va2hQVHsO7RCgBsDaHiAGXN/C9Z+B4RGE40O+A8gKAYjluPmkAKwhgK3l4j1n"
    "DhLvEaajkBLj1pQUoh3ASGzPCCW192A6gKFEDs7UvHGD6CYd0Q7AcBBSsGv6fCO7DUm2"
    "A6gFBjwbjjoAAFWdKgY/9jEgAAAAAElFTkSuQmCC"
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


# ─── ВЫЧИСЛЕНИЕ НИЖНЕГО ЦЕНТРА BOUNDING BOX В ЛОКАЛЬНЫХ КООРДИНАТАХ ──────────

def _get_bbox_bottom_center_local(obj):
    """
    Возвращает нижнюю центральную точку bounding box (включая потомков)
    в ЛОКАЛЬНЫХ координатах obj:
      X, Z — центр bbox
      Y    — минимальная Y (нижняя грань)
    """
    mg_inv = ~obj.GetMg()

    min_pt = [float("inf")]  * 3
    max_pt = [float("-inf")] * 3

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
                        lp = mg_inv * world_pt
                        if lp.x < min_pt[0]: min_pt[0] = lp.x
                        if lp.x > max_pt[0]: max_pt[0] = lp.x
                        if lp.y < min_pt[1]: min_pt[1] = lp.y
                        if lp.y > max_pt[1]: max_pt[1] = lp.y
                        if lp.z < min_pt[2]: min_pt[2] = lp.z
                        if lp.z > max_pt[2]: max_pt[2] = lp.z

        child = o.GetDown()
        while child:
            _traverse(child)
            child = child.GetNext()

    _traverse(obj)

    if min_pt[0] == float("inf"):
        return None  # нет геометрии

    cx = (min_pt[0] + max_pt[0]) / 2.0
    cy = min_pt[1]                       # нижняя грань по Y
    cz = (min_pt[2] + max_pt[2]) / 2.0
    return c4d.Vector(cx, cy, cz)


def _move_axis(doc, obj, local_offset):
    """
    Смещает pivot объекта на local_offset (в локальных координатах obj),
    компенсируя смещение прямых потомков, чтобы геометрия не двигалась.
    """
    mg = obj.GetMg()

    new_mg = c4d.Matrix(mg * local_offset, mg.v1, mg.v2, mg.v3)

    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
    obj.SetMg(new_mg)

    child = obj.GetDown()
    while child:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, child)
        child_world = mg * child.GetRelPos()
        new_local   = ~new_mg * child_world
        child.SetRelPos(new_local)
        child = child.GetNext()


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class AxisToBottomCenterCommand(c4d.plugins.CommandData):

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
            bottom_center_local = _get_bbox_bottom_center_local(obj)
            if bottom_center_local is None:
                continue  # нет геометрии

            _move_axis(doc, obj, bottom_center_local)

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
        dat  = AxisToBottomCenterCommand(),
    )
