"""
TargetCamera.pyp — Cinema 4D R26
══════════════════════════════════════════════════════
Target Camera — аналог 3ds Max.

При нажатии на кнопку в меню Extensions создаётся:
  • Camera         — обычная камера C4D
  • Camera Target  — Null-объект (цель)
  • Тег Expression — живёт на камере, каждый кадр
                     поворачивает камеру точно на таргет
                     и синхронизирует имя таргета

Таргет можно двигать/анимировать — камера всегда
смотрит на него. При переименовании камеры таргет
автоматически получает имя "<камера>.target".

Установка:
  Plugins/TargetCamera/TargetCamera.pyp
"""

import c4d

# ── ID плагина (оригинальные) ─────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068859   # CommandData — кнопка меню
PLUGIN_ID_TAG = 1068860   # TagData     — Expression-тег

# Ключ ссылки на таргет в BaseContainer тега
TAG_LINK_TARGET = 1000


# ══════════════════════════════════════════════════════════════════════════════
#  LookAt-матрица: камера → точка
# ══════════════════════════════════════════════════════════════════════════════

def look_at_matrix(cam_mg, target_pos):
    """
    Строит матрицу для камеры так, чтобы её ось -Z смотрела на target_pos.

    Cinema 4D — правосторонняя система:
      v1 = right   (local +X)
      v2 = up      (local +Y)
      v3 = back    (local +Z)  =>  камера смотрит в -Z, т.е. v3 = -forward
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

    # Правая система: right = world_up x forward
    right  = world_up.Cross(forward).GetNormalized()
    up_vec = forward.Cross(right).GetNormalized()

    mg     = c4d.Matrix()
    mg.off = cam_pos
    mg.v1  = right       # +X = вправо
    mg.v2  = up_vec      # +Y = вверх
    mg.v3  = -forward    # +Z = назад (камера смотрит в -Z)
    return mg


# ══════════════════════════════════════════════════════════════════════════════
#  TagData — Expression-тег
# ══════════════════════════════════════════════════════════════════════════════

class TargetCamTag(c4d.plugins.TagData):

    def Init(self, node):
        node[TAG_LINK_TARGET] = None
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

        # ── Синхронизация имени таргета ───────────────────────────────────────
        # Таргет всегда называется "<имя камеры>.target"
        expected = cam.GetName() + ".target"
        if target.GetName() != expected:
            target.SetName(expected)
            c4d.EventAdd()

        # ── LookAt ────────────────────────────────────────────────────────────
        new_mg = look_at_matrix(cam.GetMg(), target.GetMg().off)
        cam.SetMg(new_mg)

        return c4d.EXECUTIONRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  CommandData — кнопка в меню Extensions
# ══════════════════════════════════════════════════════════════════════════════

class TargetCameraCmd(c4d.plugins.CommandData):

    def Execute(self, doc):
        doc.StartUndo()

        # ── 1. Камера ──────────────────────────────────────────────────────────
        cam = c4d.BaseObject(c4d.Ocamera)
        cam.SetName("Target Camera")
        cam[c4d.CAMERAOBJECT_FOCUS] = 36.0
        cam.SetAbsPos(c4d.Vector(0, 0, -500))
        doc.InsertObject(cam)
        doc.AddUndo(c4d.UNDOTYPE_NEW, cam)

        # ── 2. Таргет (Null) ──────────────────────────────────────────────────
        # Имя сразу по правилу: "<имя камеры>.target"
        target = c4d.BaseObject(c4d.Onull)
        target.SetName(cam.GetName() + ".target")
        target[c4d.NULLOBJECT_DISPLAY] = 2      # 2 = Cross
        target[c4d.NULLOBJECT_RADIUS]  = 30.0
        target.SetAbsPos(c4d.Vector(0, 0, 0))
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


# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    icon = c4d.bitmaps.BaseBitmap()
    icon.Init(32, 32, 32)
    for x in range(32):
        for y in range(32):
            if x == 16 or y == 16 or (14 <= x <= 18 and 14 <= y <= 18):
                icon.SetPixel(x, y, 255, 200, 50)
            else:
                icon.SetPixel(x, y, 40, 90, 160)

    ok_tag = c4d.plugins.RegisterTagPlugin(
        id          = PLUGIN_ID_TAG,
        str         = "TargetCam Controller",
        info        = c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g           = TargetCamTag,
        description = "",
        icon        = None,
    )

    ok_cmd = c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID_CMD,
        str  = "Target Camera",
        info = 0,
        icon = icon,
        help = "Создать Target Camera (аналог 3ds Max)",
        dat  = TargetCameraCmd(),
    )

    if ok_tag and ok_cmd:
        print("[TargetCamera] Плагин загружен успешно.")
    else:
        print("[TargetCamera] ОШИБКА регистрации! tag=%s cmd=%s" % (ok_tag, ok_cmd))
