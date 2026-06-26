# -*- coding: utf-8 -*-
"""
AxisToBottomCenter — Cinema 4D Command Plugin
Смещает ось (pivot) выделенных объектов в нижнюю центральную точку их bounding box.
По X и Z — центр, по Y — нижняя грань.
Сами объекты визуально не двигаются.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068829
PLUGIN_NAME = "Axis2Bottom v1.1.2"
PLUGIN_HELP = "Переместить ось объекта в нижний центр его bounding box"

_ICON_B64 = (
    "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"
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
    Смещает pivot объекта на local_offset (в локальных координатах obj).
    Геометрия объекта и его дочерние объекты визуально не двигаются.

    Стратегия:
      1. Сдвигаем точки меша (если есть) в обратную сторону.
      2. Обновляем мировую матрицу объекта (смещаем origin).
      3. Компенсируем прямых потомков, пересчитывая их RelPos.
    """
    mg = obj.GetMg()

    # Новая мировая матрица — origin сдвинут на local_offset в локальном пространстве
    new_mg = c4d.Matrix(mg * local_offset, mg.v1, mg.v2, mg.v3)

    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

    # ── 1. Компенсируем геометрию (точки) самого объекта ─────────────────────
    # Если объект имеет редактируемые точки — сдвигаем их в обратную сторону,
    # чтобы меш не смещался вместе с осью.
    point_offset = -local_offset
    point_count = obj.GetPointCount() if hasattr(obj, "GetPointCount") else 0
    if point_count > 0:
        pts = obj.GetAllPoints()
        pts = [p + point_offset for p in pts]
        obj.SetAllPoints(pts)
        obj.Message(c4d.MSG_UPDATE)

    # ── 2. Обновляем матрицу объекта ─────────────────────────────────────────
    obj.SetMg(new_mg)

    # ── 3. Компенсируем прямых потомков ──────────────────────────────────────
    child = obj.GetDown()
    while child:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, child)
        child_world_pos = mg * child.GetRelPos()
        child.SetRelPos(~new_mg * child_world_pos)
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
