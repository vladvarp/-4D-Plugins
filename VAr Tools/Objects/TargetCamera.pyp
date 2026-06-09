"""
TargetCamera.pyp — Cinema 4D R26

Создаёт камеру с целевой точкой (Null-объектом), на которую камера всегда смотрит. Таргет следует за камерой при переименовании.
"""

import c4d
import os
import base64
import tempfile

# ── ID плагина (оригинальные) ─────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068859   # CommandData — кнопка меню
PLUGIN_ID_TAG = 1068860   # TagData     — Expression-тег

PLUGIN_NAME_CMD   = "Target Camera"
PLUGIN_NAME_CMD_V = "Target Camera v1.4"
PLUGIN_NAME_TAG   = "TargetCam Controller"

# Ключ ссылки на таргет в BaseContainer тега
TAG_LINK_TARGET = 1000


def look_at_matrix(cam_mg, target_pos):
    """
    Cinema 4D: камера смотрит вдоль своей локальной оси +Z.
    Значит v3 = forward (направление НА таргет).
    """
    cam_pos = cam_mg.off
    delta   = target_pos - cam_pos

    if delta.GetLength() < 0.001:
        return cam_mg

    forward = delta.GetNormalized()

    # Опорный вектор «вверх»
    world_up = c4d.Vector(0, 1, 0)
    if abs(forward.Dot(world_up)) > 0.999:
        world_up = c4d.Vector(0, 0, 1)

    # right = world_up x forward  (правосторонняя система C4D)
    right  = world_up.Cross(forward).GetNormalized()
    up_vec = forward.Cross(right).GetNormalized()

    mg     = c4d.Matrix()
    mg.off = cam_pos
    mg.v1  = right      # +X = вправо
    mg.v2  = up_vec     # +Y = вверх
    mg.v3  = forward    # +Z = вперёд (камера смотрит на таргет)
    return mg


# ══════════════════════════════════════════════════════════════════════════════
#  TagData — Expression-тег
# ══════════════════════════════════════════════════════════════════════════════

class TargetCamTag(c4d.plugins.TagData):

    def Init(self, node):
        node[TAG_LINK_TARGET] = None
        self._prev_dist = None   # предыдущее расстояние для детектирования ручного изменения
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription("tbaselist2d"):
            return False

        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc[c4d.DESC_NAME]       = "Target"
        bc[c4d.DESC_SHORT_NAME] = "Target"
        bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_LINKBOX

        pid = c4d.DescID(c4d.DescLevel(TAG_LINK_TARGET, c4d.DTYPE_BASELISTLINK, 0))
        description.SetParameter(pid, bc, c4d.ID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Execute(self, tag, doc, op, bt, priority, flags):
        cam = op
        if cam is None:
            return c4d.EXECUTIONRESULT_OK

        target = tag[TAG_LINK_TARGET]
        if target is None or not target.IsAlive():
            return c4d.EXECUTIONRESULT_OK

        # Синхронизация имени
        expected = cam.GetName() + ".target"
        if target.GetName() != expected:
            target.SetName(expected)
            c4d.EventAdd()

        # ── LookAt ────────────────────────────────────────────────────────────
        new_mg = look_at_matrix(cam.GetMg(), target.GetMg().off)
        cam.SetMg(new_mg)

        # ── Расстояние до цели ────────────────────────────────────────────────
        real_dist  = (target.GetMg().off - new_mg.off).GetLength()
        param_dist = cam[c4d.CAMERAOBJECT_TARGETDISTANCE]

        # Если пользователь изменил параметр вручную — двигаем таргет вперёд по оси камеры
        if self._prev_dist is not None and abs(param_dist - self._prev_dist) > 0.001:
            new_target_pos = new_mg.off + new_mg.v3.GetNormalized() * param_dist
            target.SetAbsPos(new_target_pos)
            c4d.EventAdd()
        else:
            # Таргет двигали мышью — обновляем параметр по реальному расстоянию
            cam[c4d.CAMERAOBJECT_TARGETDISTANCE] = real_dist
            param_dist = real_dist

        self._prev_dist = param_dist

        return c4d.EXECUTIONRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  CommandData — кнопка в меню Extensions
# ══════════════════════════════════════════════════════════════════════════════

class TargetCameraCmd(c4d.plugins.CommandData):

    def Execute(self, doc):
        doc.StartUndo()

        # ── 1. Камера ──────────────────────────────────────────────────────────
        cam = c4d.BaseObject(c4d.Ocamera)
        cam.SetName("Camera")
        cam[c4d.CAMERAOBJECT_FOCUS] = 36.0
        cam.SetAbsPos(c4d.Vector(0, 0, -500))
        _set_object_icon(cam, _ICON_B64_1)   # иконка камеры
        doc.InsertObject(cam)
        doc.AddUndo(c4d.UNDOTYPE_NEW, cam)

        # ── 2. Таргет (Null) ──────────────────────────────────────────────────
        # Имя сразу по правилу: "<имя камеры>.target"
        target = c4d.BaseObject(c4d.Onull)
        target.SetName(cam.GetName() + ".target")
        target[c4d.NULLOBJECT_DISPLAY] = 11
        target[c4d.NULLOBJECT_RADIUS]  = 5.0
        target.SetAbsPos(c4d.Vector(0, 0, 0))
        _set_object_icon(target, _ICON_B64_2)  # иконка таргета
        doc.InsertObject(target)
        doc.AddUndo(c4d.UNDOTYPE_NEW, target)

        # ── 3. Expression-тег на камере ───────────────────────────────────────
        tag = cam.MakeTag(PLUGIN_ID_TAG)
        tag.SetName("TargetCam Controller")
        tag[TAG_LINK_TARGET] = target
        doc.AddUndo(c4d.UNDOTYPE_NEW, tag)

        doc.EndUndo()
        doc.SetActiveObject(cam)
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED


_ICON_B64_1 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAoUlEQVR42mOQUdCi"
    "KWIYtWDUAlpY4NZzB4JoYgHcdGrZQV8L0EzHhci0AL+hKas+QBBBO/7v0yDNAoi5"
    "IiJyEATh4jEdgoi1AM10PHbAzYWTEAZhC5DNRWbjChk0Bj4L0Ezccuc/LjuQwwSN"
    "TZQFENMhCC5YseAEUBeQhIc7VjSgPqB5HNAjFVEzH+DPzMg5GX/ZgDMnj9ZooxaM"
    "WjB0LQAA/SmnUKnI7oUAAAAASUVORK5CYII="
)

_ICON_B64_2 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAx0lEQVR42r2WwQ2D"
    "MAxFMwiHHhGD9NzBmKmTsAutFLBSYn87qP7SF4fI/s8RTuIyPZZUlaHo57r9GfB1"
    "FO3vuapdvA/oXQRgBQwA1MwLAEQ6ACtBBeAUBQBCAQAklqC7MNyOMAGR2lsFGQ7A"
    "srPWTQBwB6YRhgNwqx4A4PIBQGWEANeV7VXlRiqAvkPke+h0PwQif/dUKtBqxCCg"
    "l2yCsgPGP2B0Ufo5yD3J6XcR4zZNfw8YLxrjTWZMFYy5iDHZkWZT9nR9Qx/pzjY7"
    "O/Zd6AAAAABJRU5ErkJggg=="
)



def _set_object_icon(obj, icon_b64):
    """Назначает иконку объекту сцены через временный PNG-файл (ID_BASELIST_ICON_FILE)."""
    png_data = base64.b64decode(icon_b64)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        obj[c4d.ID_BASELIST_ICON_FILE] = tmp.name
    finally:
        pass  # файл нужен, пока C4D не загрузил иконку; удалять сразу нельзя


def _make_icon_plug():
    png_data = base64.b64decode(_ICON_B64_1)
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        bmp.InitWith(tmp.name)
    finally:
        os.unlink(tmp.name)
    return bmp

def _make_icon_teg():
    png_data = base64.b64decode(_ICON_B64_2)
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        bmp.InitWith(tmp.name)
    finally:
        os.unlink(tmp.name)
    return bmp

# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    ok_tag = c4d.plugins.RegisterTagPlugin(
        id          = PLUGIN_ID_TAG,
        str         = PLUGIN_NAME_TAG,
        info        = c4d.TAG_EXPRESSION,
        g           = TargetCamTag,
        description = "",
        icon        = _make_icon_teg(),
    )

    ok_cmd = c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID_CMD,
        str  = PLUGIN_NAME_CMD_V,
        info = 0,
        icon = _make_icon_plug(),
        help = "Создать Target Camera",
        dat  = TargetCameraCmd(),
    )

    if ok_tag and ok_cmd:
        print("[TargetCamera] Плагин загружен успешно.")
    else:
        print("[TargetCamera] ОШИБКА регистрации! tag=%s cmd=%s" % (ok_tag, ok_cmd))
