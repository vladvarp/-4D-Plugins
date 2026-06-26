"""
TargetCamera.pyp — Cinema 4D R26

Создаёт камеру с целевой точкой (Null-объектом), на которую камера всегда смотрит. Таргет следует за камерой при переименовании.
"""

import c4d # type: ignore
import os
import base64
import tempfile

# ── ID плагина (оригинальные) ─────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068859   # CommandData — кнопка меню
PLUGIN_ID_TAG = 1068860   # TagData     — Expression-тег

PLUGIN_NAME_CMD   = "Target Camera"
PLUGIN_NAME_CMD_V = "Target Camera v2.0.1"
PLUGIN_NAME_TAG   = "TargetCam Controller"

# Ключ ссылки на таргет в BaseContainer тега
TAG_LINK_TARGET = 1000


def _has_lock_tag(obj):
    """True если на объекте есть тег блокировки (Protection)."""
    if obj is None or not obj.IsAlive():
        return False
    tag = obj.GetFirstTag()
    while tag:
        if tag.GetType() == c4d.Tprotection:
            return True
        tag = tag.GetNext()
    return False


def _set_lock_tag(obj, locked):
    """Добавляет или снимает тег блокировки (Protection) с объекта."""
    if obj is None or not obj.IsAlive():
        return
    doc = obj.GetDocument()
    if locked:
        if not _has_lock_tag(obj):
            obj.MakeTag(c4d.Tprotection)
    else:
        tag = obj.GetFirstTag()
        while tag:
            nxt = tag.GetNext()
            if tag.GetType() == c4d.Tprotection:
                tag.Remove()
            tag = nxt
    if doc:
        doc.SetChanged()


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

    def Free(self, node):
        # Вызывается при удалении тега — удаляем связанный таргет вместе с ним
        target = node[TAG_LINK_TARGET]
        if target is not None and target.IsAlive():
            doc = target.GetDocument()
            if doc is not None:
                target.Remove()
                c4d.EventAdd()

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
            # Таргет удалён или не создан — пересоздаём.
            # Это покрывает: ручное удаление таргета, ручное добавление тега на камеру.
            new_target = c4d.BaseObject(c4d.Onull)
            new_target.SetName(cam.GetName() + ".target")
            new_target[c4d.NULLOBJECT_DISPLAY] = 11
            new_target[c4d.NULLOBJECT_RADIUS]  = 5.0
            _set_object_icon(new_target, _ICON_B64_T)  # иконка таргета
            # Сначала вставляем в иерархию — только после этого SetMg работает в мировых координатах
            doc.InsertObject(new_target, cam.GetUp(), cam.GetPred())
            world_pos = cam.GetMg().off + cam.GetMg().v3.GetNormalized() * cam[c4d.CAMERAOBJECT_TARGETDISTANCE]
            mg = c4d.Matrix()
            mg.off = world_pos
            new_target.SetMg(mg)
            tag[TAG_LINK_TARGET] = new_target
            self._prev_dist = None
            _set_lock_tag(new_target, _has_lock_tag(cam))
            c4d.EventAdd()
            return c4d.EXECUTIONRESULT_OK

        # Синхронизация имени
        expected = cam.GetName() + ".target"
        if target.GetName() != expected:
            target.SetName(expected)
            c4d.EventAdd()

        # ── Синхронизация блокировки: камера → таргет ─────────────────────────
        cam_locked = _has_lock_tag(cam)
        if cam_locked != _has_lock_tag(target):
            _set_lock_tag(target, cam_locked)

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
        _set_object_icon(cam, _ICON_B64_P)   # иконка камеры
        doc.InsertObject(cam)
        doc.AddUndo(c4d.UNDOTYPE_NEW, cam)

        # ── 2. Expression-тег на камере ───────────────────────────────────────
        tag = cam.MakeTag(PLUGIN_ID_TAG)
        tag.SetName("TargetCam Controller")
        doc.AddUndo(c4d.UNDOTYPE_NEW, tag)

        # ── 3. Таргет (Null) — создаётся после появления тега ────────────────
        # Тег уже существует (MakeTag выше) — это и есть триггер.
        # Имя по правилу: "<имя камеры>.target"
        target = c4d.BaseObject(c4d.Onull)
        target.SetName(cam.GetName() + ".target")
        target[c4d.NULLOBJECT_DISPLAY] = 11
        target[c4d.NULLOBJECT_RADIUS]  = 5.0
        _set_object_icon(target, _ICON_B64_T)  # иконка таргета
        # Сначала вставляем в иерархию — только после этого SetMg работает в мировых координатах
        doc.InsertObject(target, cam.GetUp(), cam.GetPred())
        world_pos = cam.GetMg().off + cam.GetMg().v3.GetNormalized() * cam[c4d.CAMERAOBJECT_TARGETDISTANCE]
        mg = c4d.Matrix()
        mg.off = world_pos
        target.SetMg(mg)
        doc.AddUndo(c4d.UNDOTYPE_NEW, target)
        tag[TAG_LINK_TARGET] = target

        doc.EndUndo()
        doc.SetActiveObject(cam)
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED


_ICON_B64_P = (
    "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"
)

_ICON_B64_T = (
    "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"
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
    png_data = base64.b64decode(_ICON_B64_P)
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
    png_data = base64.b64decode(_ICON_B64_T)
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
        info        = c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
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
