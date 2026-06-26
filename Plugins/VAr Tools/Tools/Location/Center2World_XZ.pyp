# -*- coding: utf-8 -*-
"""
Center2World XZ — Cinema 4D Command Plugin
Центрирует выделенные объекты по мировым осям X и Z (без изменения Y).
Центр bounding box объекта помещается в точку X=0, Z=0 мирового пространства.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068839
PLUGIN_NAME = "Center2World XZ v1.1.2"
PLUGIN_HELP = "Центрировать выделенные объекты по X и Z в мировом пространстве (Y не меняется)"


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAIwklEQVR4nO2bf4xcVRXHP+e+HzO7M9P90RbaRqJpBOKuUWw1sWDZLSnRkBobk9kYCcgfBhIJETASjT+mg8QQjYBKhGrAEAjRmWpCkBjLj93YSGvcZQvaRbCpROjadmm3+4vdefPePf4xs7DLbtvdaXeelP0mN5l5c989537vveeec88dWEasEFWVWBU41Q+azTqnfbNYtAJ6zjWqM+YnQKhL13K5+9PJpPGmpo6O5fP5cOklzoU730NHIbz2hs0kfHdOjTCERAJgvzzwwLCCLHYm5HI5k8/n7ZQJH3WTTR2TYes24PlsoeAUu7qi2rpSG2Z1T0E6Nefc/Oj4RWN/G38243gek+V3veGC40AQbAWeJZs1FIu1KS00OcZpUYNXo/5nDTP9IasFR0BXvWo2/e6qVS9cd8ta7v5cBiLASGWcp4sxcA6MlyBhFIVqrI3NlsxZAtYxnrqmearR1WOZcJhyuD8yghNVdRSxBIFB9U0A2tpqV15VRCTWXWAOAaJWoyDUFa4rBy/0++SRh64+XQOSz9ulU2/pMa8RREQUcKy6msuZnk5MZw+zO5rP6/mwDc5PQBVqRCWft7kdObZseW+P9Klgzlzl/MZcG4BRVSwKqpyXoz4Tc2aAmtD1Ur7xUr4RNBWHUvXE2zOgSNYClCZKffj+Va7roionAfLk3/PG7lR4ZwlUDD9PfezuYaB7Vi05C2s/j8M0UCwKqsKdPwXAGiOoyrGeHjlrB6vaj4Vi7i6gSJaCAWjjgOblLK3/PArtqviXsONeBUhOlUJE9M9Q94BoLgGCFjlHAYmq0McKJjGkUcYr0WfGGZHRqEmj7p97qGVw5YVN7NGWtD9qxoIVtRGeRnEQjjPGFlkwkaf1A2qGqiCi9NBEA/0kaaKEToc8YzYjJNE3WtZlmo4e5OnLv/wbGiiPB2nBq2m5CVMoDQgNfAHYQ0EduuSMA7k0BLzTugArccjMkqYGXFDXBRuhfkOGBJUgqxYLEFWLB0wtLrJcWgIqKBOiRFgiRgHFWsEzKmGYwTieBJNjlCgTWMGYhc8ARRAUJYNgKGNYpHteDwLAQ7CMomwgZCQVHnHGo3XRB4YHf0/r6s6rX+3+0kOZ6/em/fHF2YAWhGEUlydIsrmWxVMfAipQIo6zWcYmqg+cHfeWEcO640dH2CzD47W2vFfLtR7j1TcWMHioyoadO72qoRSAqWTCRVWu7O52UZVFFKfqN9TsO9SXgAhFRNODgzrTPzDWKiJ6wdBQ5flCC+hiHZ93430fDcZOQKznYcRIgBayjlWRSAXfBI5qPFzERoB0FaMGE4SNbsA/Jj44IoJ+beIpT7s7XO3ucOtFyBwhuVzurEkZaG+XtgMH9J7P3N4ynk6/SkJaKemJNUNHLh3s++WJYvuAZN86+O2S+Ldbx2u21u5KOWM3ybV/H16MLj2dnaazp8fe+dnvP0ujdGLBTEZbv7v7ru4/rPu8s23wyTmucD6frxjPKpaWZVWfPgZJsJISx9nIRYhM6iMbv0OrdxcnSmCtpck3jIT9iDyBqpA04PznQekaOrIgOb36NA1sxQIOm2iTfQtVUSp6qoiI5nL3p6fc6FFHTDqyVqXW2FwEVAmN4x1uXnu5OsYzkS2vHT72/AozUb5jXXFT0i0nrRUxiMHaCN84eAZUwI14/LWOF3vHPzzUaEoS6fxbXUVr1cGmNRuDhN+CwuqRN19IBW+dmP5tRl31/YREk5Pf/GH+tv3T6blZnmCpNJpwE03bU6kMURRy1jkLVZqPHgRrEWO8qHlNR6Pn4nk+hKVIxDGVhBxCpJVgRgAb4TS2fjwlTTSaEvYME/WSk4chKFW+NK/cwIqmeVRR/EQDI6XyhVBZplB1hatpABKJ0shkFF4xMTrqhpTnNLJQWGPEWKtDqVWZZzZd+7gmZIWUdPSal/90XWo0ODmZtrelVya263BoFTBp1zARvs5k9BCighH8qcH+ydFVw2ImJDhFgBTiGpfQ7tqw/b4gnfgEFi5+49+3fur13v7A+o5vglk2IFkK8Gz4EkCxq8vC0tsAlz6OzLABaxEp66/aWkk2PIaUt4I4kfivOJPh9fLV/t6a5PTpbpJcjQV8Ps2l8teFvjonGMpmCw7ZmtR4G8dWr5YLhob0j0+ONU+sTglGoKySenKi6eFCYVi6ssMg1zz8ozt6/Exzx7+OmBvz+W/1dv/6K8nOD70WAhSHbtbiGeQcWr/erD90yO4qRR6OAQtmNEp/sVBwDtDmtDMwZxeojvwSH/JOG8892sI+PU6/Kvv0OHu0BeDGnTd6qsjXc7/Y/b2fPKbf+MH9V2oOky0UTn8rZa6cyja5V5/jRdWqnC0AFHRBbcXiCL0yuFZF0JQpSdIEJCkj+XiSMLHGAhZBkfofBc9A7MFQ3FgmoK7SfAyqZqi93aBqtOpphbgGVXNo/XqD6sILVD/Xvp3X70xQUdKMIWJfhgDA7LgnRIQ1E8cmELEvsGhDWKm/T2s2I/UgQKqJsBWM8Qx7NcRGgufo4ed/e9klJ99g5xU3PEjvnSMEFqSmSXkZJSz+4mf00hOgWGw1Tmtgc+X01gEXgkQDBCVKqeYNNABujYmRKSCqbibO/1NewEGADI0YQir+13Sx8LZDZqPKd0ttBCQAxaUReHNxfVoaAqZPakuM0sBWpnBnbvYmCk2UcO0FI0d/TPOqjRf/d+DW15s7XjJB6ETGrT0x6wIR+wHILsyeLO0MqGRp97z78bRm6R33DNHcyraXdv/lues6e8+pK7jA4/KltwHz+OQbhvtMX8tGG/3zZx6qHG5dm6agzkc44AzQXvsMqARxdjG5gqUnYJ4U9bZcTvtu+qSV/H0K4IahpUui9kKBga6P1vWy9LInGLcCcWOZgLgViBvLBMStQNxYJiBuBeJGrARoNQQyxontLnKsBAjS6PsJE4Zaz8tasxCL4GqKGmPtLeUwaAms7QcoZrPn/f8TljETuVzOFCrZoLivCr1/8T/ayd8GEVRQDwAAAABJRU5ErkJggg=="
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
