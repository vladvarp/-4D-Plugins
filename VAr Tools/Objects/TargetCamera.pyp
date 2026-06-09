"""
TargetCamera.pyp — Cinema 4D R26
══════════════════════════════════════════════════════
Target Camera — аналог 3ds Max.

При нажатии на кнопку в меню Extensions создаётся:
  • Camera         — обычная камера C4D
  • Camera Target  — Null-объект (цель)
  • Тег Expression — живёт на камере, каждый кадр
                     поворачивает камеру точно на таргет

Таргет можно двигать/анимировать — камера всегда
смотрит на него. Камеру тоже можно двигать.

Установка:
  Plugins/TargetCamera/TargetCamera.pyp
"""

import c4d

# ── ID плагина (оригинальные, из старого плагина) ─────────────────────────────
PLUGIN_ID_CMD = 1068859   # CommandData — кнопка меню
PLUGIN_ID_TAG = 1068860   # TagData     — Expression-тег

# Имя параметра в теге — ссылка на таргет (храним в BaseContainer тега)
TAG_LINK_TARGET = 1000


# ══════════════════════════════════════════════════════════════════════════════
#  Вспомогательная: LookAt-матрица (камера → точка)
# ══════════════════════════════════════════════════════════════════════════════

def look_at_matrix(cam_mg, target_pos):
    """
    Возвращает новую матрицу cam_mg, у которой ось -Z направлена
    точно на target_pos.  Позиция камеры (off) не меняется.

    В Cinema 4D камера смотрит вдоль своей локальной оси -Z:
      v1 = правый вектор  (local X)
      v2 = верхний вектор (local Y)
      v3 = задний вектор  (local Z) = -forward

    Алгоритм: строим ортонормальный базис из направления вперёд.
    """
    cam_pos = cam_mg.off
    forward = (target_pos - cam_pos).GetNormalized()

    # Если расстояние слишком мало — не меняем матрицу
    if (target_pos - cam_pos).GetLength() < 0.001:
        return cam_mg

    # Опорный «верх» мира
    world_up = c4d.Vector(0, 1, 0)

    # Если forward почти параллелен world_up — используем другую опору
    if abs(forward.Dot(world_up)) > 0.999:
        world_up = c4d.Vector(0, 0, 1)

    right  = forward.Cross(world_up).GetNormalized()
    up_vec = right.Cross(forward).GetNormalized()

    new_mg      = c4d.Matrix()
    new_mg.off  = cam_pos
    new_mg.v1   = right        # X = вправо
    new_mg.v2   = up_vec       # Y = вверх
    new_mg.v3   = -forward     # Z = назад (камера смотрит в -Z)
    return new_mg


# ══════════════════════════════════════════════════════════════════════════════
#  TagData — Expression-тег на камере
# ══════════════════════════════════════════════════════════════════════════════

class TargetCamTag(c4d.plugins.TagData):
    """
    Тег, который живёт на камере.
    В его BaseContainer под ключом TAG_LINK_TARGET хранится ссылка
    на Null-объект (таргет).

    Execute() вызывается каждый кадр и направляет камеру на таргет.
    """

    def Init(self, node):
        # Инициализируем слот таргета пустым значением
        node[TAG_LINK_TARGET] = None
        return True

    def GetDDescription(self, node, description, flags):
        """Добавляем поле 'Таргет' в панель атрибутов тега."""
        if not description.LoadDescription("tbaselist2d"):
            return False

        # Параметр: ссылка на объект-таргет
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc[c4d.DESC_NAME]       = "Таргет"
        bc[c4d.DESC_SHORT_NAME] = "Таргет"
        bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_LINKBOX

        pid = c4d.DescID(c4d.DescLevel(TAG_LINK_TARGET, c4d.DTYPE_BASELISTLINK, 0))
        description.SetParameter(pid, bc, c4d.ID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Execute(self, tag, doc, op, bt, priority, flags):
        """
        op  = объект, на котором висит тег (камера).
        Читаем таргет из параметра тега, строим LookAt и применяем.
        """
        cam = op
        if cam is None:
            return c4d.EXECUTIONRESULT_OK

        target = tag[TAG_LINK_TARGET]
        if target is None or not target.IsAlive():
            return c4d.EXECUTIONRESULT_OK

        target_pos = target.GetMg().off
        new_mg     = look_at_matrix(cam.GetMg(), target_pos)
        cam.SetMg(new_mg)

        return c4d.EXECUTIONRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  CommandData — кнопка «Target Camera» в меню Extensions
# ══════════════════════════════════════════════════════════════════════════════

class TargetCameraCmd(c4d.plugins.CommandData):

    def Execute(self, doc):
        doc.StartUndo()

        # ── 1. Камера ──────────────────────────────────────────────────────────
        cam = c4d.BaseObject(c4d.Ocamera)
        cam.SetName("Target Camera")
        # Стандартные настройки фокуса
        cam[c4d.CAMERAOBJECT_FOCUS] = 36.0
        # Ставим камеру чуть назад по Z, чтобы она сразу смотрела на таргет
        cam.SetAbsPos(c4d.Vector(0, 0, -500))

        doc.InsertObject(cam)
        doc.AddUndo(c4d.UNDOTYPE_NEW, cam)

        # ── 2. Таргет (Null) ──────────────────────────────────────────────────
        target = c4d.BaseObject(c4d.Onull)
        target.SetName("Camera Target")
        # Крест — наглядный маркер в вьюпорте
        target[c4d.NULLOBJECT_DISPLAY] = c4d.NULLOBJECT_DISPLAY_CROSS
        target[c4d.NULLOBJECT_RADIUS]  = 30.0
        # Таргет — в начале координат
        target.SetAbsPos(c4d.Vector(0, 0, 0))

        doc.InsertObject(target)
        doc.AddUndo(c4d.UNDOTYPE_NEW, target)

        # ── 3. Expression-тег на камере ───────────────────────────────────────
        tag = cam.MakeTag(PLUGIN_ID_TAG)
        tag.SetName("TargetCam Controller")
        tag[TAG_LINK_TARGET] = target
        doc.AddUndo(c4d.UNDOTYPE_NEW, tag)

        doc.EndUndo()

        # Делаем камеру активной
        doc.SetActiveObject(cam)
        c4d.EventAdd()

        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED


# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Простая иконка 32×32 — голубой квадрат
    icon = c4d.bitmaps.BaseBitmap()
    icon.Init(32, 32, 32)
    for x in range(32):
        for y in range(32):
            # Рисуем перекрестие (символ камеры + таргет)
            if x == 16 or y == 16 or (14 <= x <= 18 and 14 <= y <= 18):
                icon.SetPixel(x, y, 255, 200, 50)
            else:
                icon.SetPixel(x, y, 40, 90, 160)

    # Сначала регистрируем тег (CommandData использует его при создании)
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
