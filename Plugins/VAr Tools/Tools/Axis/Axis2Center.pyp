# -*- coding: utf-8 -*-
"""
AxisToCenter — Cinema 4D Command Plugin
Смещает ось (pivot) выделенных объектов в геометрический центр их bounding box.
Сами объекты визуально не двигаются.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068828
PLUGIN_NAME = "Axis2Center v1.1.2"
PLUGIN_HELP = "Переместить ось объекта в центр его bounding box"

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


# ─── ВЫЧИСЛЕНИЕ ЦЕНТРА BOUNDING BOX В ЛОКАЛЬНЫХ КООРДИНАТАХ ──────────────────

def _get_bbox_center_local(obj):
    """
    Возвращает центр bounding box объекта (включая всех потомков)
    в ЛОКАЛЬНЫХ координатах самого obj.
    Это нужно, чтобы потом задать новый pivot без смещения геометрии.
    """
    mg_inv = ~obj.GetMg()   # инвертированная мировая матрица obj

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
                        # переводим в локальное пространство obj
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
    cy = (min_pt[1] + max_pt[1]) / 2.0
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

class AxisToCenterCommand(c4d.plugins.CommandData):

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
            center_local = _get_bbox_center_local(obj)
            if center_local is None:
                continue  # нет геометрии

            _move_axis(doc, obj, center_local)

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
        dat  = AxisToCenterCommand(),
    )
