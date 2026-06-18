# -*- coding: utf-8 -*-
"""
AxisToCenter — Cinema 4D Command Plugin
Смещает ось (pivot) выделенных объектов в геометрический центр их bounding box.
Сами объекты визуально не двигаются.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068828
PLUGIN_NAME = "Axis2Center v1.1.1"
PLUGIN_HELP = "Переместить ось объекта в центр его bounding box"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA6ElEQVR4nO1WsRHDIAyUchnFhStPkOyQYTyGh8kO2YDKBbsoFXdEhiCEcFLwjV08r0eSLQH8GChmOn/r6EMQvIcBkWYgWRuoCm5toDq4pQGmk25C58kkWArLJGj8lAGLDCR0L82ijSgbcP6hVlefHSXIIZFS2mYqcewMLNPThKM2wBBuf8jCGQZomwnXHQEAcN1Ra+KqCczf+TMY00PwGeaC1+qqSxCnPS5HLZqaMO4BrUbzf0DFiZAfx3xs2uwDLwC4l2m8WeyWEaFuTLSchp+6Xy4ViPaLqFDXeeq0hh90/3QnHBg4EW919Z5Vpf/EdAAAAABJRU5ErkJggg=="
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
