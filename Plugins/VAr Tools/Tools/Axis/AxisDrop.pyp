# -*- coding: utf-8 -*-
"""
AxisDrop — Cinema 4D Command Plugin
Опускает ось (pivot) выделенных объектов на нижнюю грань их bounding box,
сохраняя X и Z позицию оси нетронутыми.
Сами объекты визуально не двигаются.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068830
PLUGIN_NAME = "Axis Drop v1.1.2"
PLUGIN_HELP = "Опустить ось объекта на нижнюю грань его bounding box"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAFYUlEQVR4nO2bX4hc1R3HP79z7p3dmTibbCQYhUIRig9LMUmDCG7QtlYptpQ+zCIUSrFiaR80ffCplHXRB8Enn4Sg8aFo7U5RRAultC5VSygYXE2F+lJfog0msu7OZnd2557z9WEmMQrZnTuzmdua+4XDeTm/3/nO9/zOn3vOb+AqhxXZuSS7UhzMTICuhO+vFAqJAElmZpp/dWG/kR4z72qh05E5N7TvKKlWrVm73X545gfTi7Ozs25ubi5ern0ydI+DwQBF+af37t17TwiBJPE74jjGyK5d13DmzIfXAUxNTW05yIML0J2/A6EJhmT2pzd2STG0Wq2jGKeyTscnaRoGcpplOOeVkdHZ2MC3N98FmJmZuezowzACdBeZgXAvBAB75fVN573frfjm3fdMLw7MZWtsyXMwASTjJBOs47gGsZpvLblhEju9hLLlf1SIgX+76teuX1g5va9i7uymthyxL8Nqdcm37OaP6637VpsZNIAmjUYjWh+DlC+MJcNMLGgPVd7Gs5uQf6txihad0+zSqfp055P017sPtP41tqfjYrRoLo8/Q4gqRpsfcau9wbw8M9b3NBosAhIMuBZPfTAvDgyi97ARiJXxOmOAcu4CoVdSoE2alwUMtwt0yBCBSGCFPIcORcM5uRDqOJ+6zXYLG+8Qo9FPBAjrjX0dw9HB5er/Egy3DaYYkRXEITKW2Q0sb292w6Sz00vopmzlRfbuu+P+8x/ce9QOnthfWXUfbU5svwZMYiwhEl5mnCPDnPd24hwgAp9wxFr9GnzUq9NXXu9gjm+sry5zly2dydvzCXW6J4q8hp9j+KNX10uKZEiuV29ZXpA8ksnMAM6nSYJkv11YSPqxp2fPDpxkd0aAgLjw8WG2bWlwsX2XRJQw09TZs33Z8yX7YbAzAvwfoxSgyM67E1i4GAq7lyhUgCAvWcJ6UhvsA2gHUJgAWrg9qerTNA0t9mcf1IriMfL7AM03vJkFHT902/fHHpu29QRbWz8K/KXRmBn5FVZRFyKQkKbWTggCKCwCilsDoklyYAkYV98aAJ/vAqi42+nyHFA0gaJRClA0gaJRClA0gaJRClA0gaJRClA0gaJRClA0gaJRClA0gaJRCrAjXio4JAe9eoty7MY7HZJrq3Kx7ygzJPcIs9vaf7Gf/4WXISF20cIsYhZ69WXLrw7/ooNZHO+8f/4iCcsyzOKjNpdtZ98r3XaObFj6w9wJXrjImqDFXzmhvsgYAZznx63X9rz04VGQeKt64Fv8853XiAHIlSx1gA0ilcEHcogkKSKRCHiqHOk3GIUHB8vZPogRFGklE5PU+DYxZ6ZYGwi9KPCjzA/wGFCn1gvCHDmZF550LV6aBiAsguXKDoJuVgkJNeDcYL8ln9GFF9kNVqhyJ22SvLMwMwIe/XDpbwdJx57ExNTa+2+rw0MhYEQclnNxS4DAIgAN8so4OjhAD1ATOD197Xf13GHp94el499cEDg9ydjYiDkNvo3Mq/8J24AHTh5z1/9n0n6z9sQfqLrvubUselMdIGKdmPo1gs6dDvumf/b1h88B/P3sHf1NrAY9N/lzBkZ2H6/ZWWdzc1G/O3wTpkXEOJnUC/dIPXEsh5/YfSef13zD20yzsMeSKwbNNzyAnjnwS/3xFunZg5mOH8zUvEV69tALl7YZFUZ6FLaZZtB8w9vPF59iNfsz497jzbEe/ovPHpQw3muO9IG0uG+B4B4nEqk4kcVT9tN3PwbM5ka7ihf6OsyYczhgI0yooPfB0QvQaHZHONk4SbvyHRLAwqdmSOUfXEaPwp6lBcZ8o7sGvdfUqOd+iRIlSpQoUaLEVY/PAFYAfjaa1DEnAAAAAElFTkSuQmCC"
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


# ─── ВЫЧИСЛЕНИЕ СМЕЩЕНИЯ ПО Y ДО НИЖНЕЙ ГРАНИ ────────────────────────────────

def _get_bbox_min_y_local(obj):
    """
    Возвращает минимальную Y-координату bounding box (включая потомков)
    в ЛОКАЛЬНЫХ координатах obj.
    X и Z не трогаем — ось остаётся на своём горизонтальном месте.
    """
    mg_inv = ~obj.GetMg()

    min_y = [float("inf")]

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
                        if lp.y < min_y[0]:
                            min_y[0] = lp.y

        child = o.GetDown()
        while child:
            _traverse(child)
            child = child.GetNext()

    _traverse(obj)
    return min_y[0]  # float("inf") если геометрии нет


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

class AxisDropCommand(c4d.plugins.CommandData):

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
            min_y_local = _get_bbox_min_y_local(obj)
            if min_y_local == float("inf"):
                continue  # нет геометрии

            # Смещаем только по Y, X и Z остаются нулевыми (ось не уходит в сторону)
            local_offset = c4d.Vector(0.0, min_y_local, 0.0)
            _move_axis(doc, obj, local_offset)

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
        dat  = AxisDropCommand(),
    )
