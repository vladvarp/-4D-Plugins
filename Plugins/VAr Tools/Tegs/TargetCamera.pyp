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
PLUGIN_NAME_CMD_V = "Target Camera v2.0"
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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEO0lEQVR4nO2WXYiUZRTHf+d5Z9753HV3Z1fFSBE2S0gqLwxU+oIUkzAQVy+UoOyquz7Ai0JLkzAIArtSC2+6WC9CCUyJIKxcVGJ3TVczCD+JZm1mnN1x9v14Thcz6267766zFt3kH56LOe+cc37Pec9znhfu6/8uuScv1Wg/Ef0nMI1mnwZ6umfRutcKtFKaYJsFiBT+XYDxpT6EYQOGvl8PYswqbldCwNSfWlJpB2uP81jnyxzCsgE7lmXqVxObJrlBxI6zhKimqVbXsWvnZW7evE08XgPwfUsul+Kdd9cBSbqk/LdY3d0OXV1hVBoTZURVELFs325QbaOobRSLbZSqHcScCkhQW9RX/XfMqVCqdlAs1nxU27h+PU1XVzhV4042ju784pVlWD1ApdJOEJp6gwnQjOdZUEAEAZRaiV3XALcARUQRsWSyHiLvsXj+ZxFVnQAwSnn1apJCtZfPD0LPyd9oanKxYS1JaANc1xD4lvJQgFpIZxySSQfPszim9lrFgO8rLa0J3nzjSToXPc685vMTISb3gIhSKqW5UczRc/IMxWKV4WEPrfdRLCYMDnq0tydYsSKH6wp9vSX6ekvMnZvA2hFGWy4WE3659CfFQkDMLADOT9x0dBOqKiIhTU0uw8MeiYRBLRhHKBR8Nm9ZyItrF3GrHMP3LevXO/T3X2bvpxdIJhykjmAcIZuNY4xg1Y9KNfUpAMGGiip3kufzHps2LuCldUvYf+AH8n+cIB4fwdqlbH1tFW+/5bJ9x0/MmZ0gCBSxoFbvxJshwDgUEXzf0tHh8sLaR9i3/yTNmf3s+2KQAOGrYz+z58Nh3t+5iadWXuHU6QLZbEOxo4/hJAADpVLA8uXtDJUdBvPf8fHuPD/2ZznTl2bNap9FD5/gwoWbPP3sA1QqAY7TUOjGAABUIR43eL4lHh9hBAMhuK5SrhiaMj6eFxBrMPOMANRCNutwtr9ALuegdilHjyVY9kSF+Qt8jAb0nF7CQ53tnD2bx603bQNqrAdUlVTK4dz5Mv39l3l162r2fDTE0a+/J5PxOXV6CVs2byTUYY4cuU5bi0toFcfc9bKbGkBEkXEFCgJlzuwEe/cOsG1bjF07uxgYeB7PC1izJoe1FXZ/cIZUykF17PIxd2JEXkjRACKCtULgWxwjiAgitYOUSTvs2NHLipXXeO6ZeWSzhuPHz3H48A0yKUMyaQhDEKkd3TBUVC1WInNNNtbGsUc8Ds0taS5eKtDcFCcMx3aQcIVvv/mdw19eAyCZcmhpjTNctWilPoQAqxCLOaTSaYwUI/caAVCb1QNXXqFU/IR8HiSqUkZwpAas6LiBMyZLSEurobXlII8ufL1e3Wkuo/FVEFFuDC6mNfcgpSE75X+nVAiZWTBSKdOe6ZmZbw2i8Rlx91j39umHqkHVoVsddIZr1Ke7e0aD6b7u6z/XX0ef4KRcbPHGAAAAAElFTkSuQmCC"
)

_ICON_B64_T = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAHKElEQVR4nNWXbYxcZRXHf+feO7Olpe0WKLEvSpTtzp0hWMoCQkGXl6CEYLDKLKCmETQQg6XbMtumRHo7UQLszL5ZiPaDQTA0zW6Crw1o+GBNpVJBabpMd7cLFj+IpK92S7q7c+/9+2Fnpt2+yLaf9PlyZ545c87/Oed/zv0/8P+4FOAITMVGX4X0twUmYefjyznnwEGzxxV4BiJWGtRmIB7GU9DsKTg3n1MLLEy9uJPBNHvqaPymiv5OPZu58DT7KQL52LSpF9daiABUaPw0rvstHC0l5lJkc5HmIPbhcAjjTeS8ZI+Vdp763/MCoADP8oR6JjWfC5wfAYsJ1U/SfsNY+BaRXYnjtFKOWrgg0UQcfwnPbgAbYTzMWW5ouwIc8shAU8nIpJMDqLPxbnX5H2hjpked/rxJNu2Nd6iQ3jFpb0VDnXoyK9Ttf6Auf33lII6mkO3TgxdTE446Urec0a7DX64O/6/a1JSo7VW6QZ3+PHWn31IhtbkCwjuTj9NQVeumztSXieznlLncHh84qN5M0lpK4+rKXIWrRwhZQhwvwGwWZsO4vEvEC7Z6z68U4FieuHKI15HttLaBVgXNnuW3hSfHm8RUBThkidXpzyPmBSy+yx4fOKigErwj3YnHb8E+Io5akdYQ089YuBxjBwkrqNt/hfrFsyb8NXu4o3difF1F/y7LbwtP7abJrXIFZoaI2YTZFssNbVdPQ53lS+MqpLbgcDVE19mjpVbLDW1HOgbMsHV7d9mjewr8sZQGe5do7E/a6F8MYKvePwL6DuInCi6bRpb45KFV+yBNBNfTn/kUXnIHY+FVLBo+ZC1EKqY6gestN7gUQD0NdRxKihlxE3Afs2fkmHPcyJbKZkgF/0ngi9Y2cG017Sr6bxKr09YMbj5jeypo9io1y6vg/6IKSu2Nn1XRP6qehrmnDiQFmaR6GupOLmGVkCqm3lExtQJAYOrwv6dC6g8Ayp7w4VQDwX5n4mk3YfHWKiBcZxXSi7ZyeD8bMgmyxApw1JH+PvV6l9D7lzr9n6rYeInlifnncVNv1gXWgT2sh5oS9GYdwvHfgX1Sz6Rmkj3RaQ6AGbJ8adwMgV2Ka69ZfltY4cNVROGPAWo2M1LrqPd+gFiIqGeW9yCyl9SbdS1fGreWvshyg78GjMuPzbWWvsjWvrcXGCHUAmshqpZgomeLjT4z3BQj4WwctwBaTaxjmFMPegYpx3R3hNF4Pzbnb+jwPlznYkJNHMIISToJRstLIDnCLBZztBxh1o7Dy0T6M44JWTvSL5nu7GA0Omi5oe0TaTb3RuQ8hOM6oHqwVZhFmJLI6jFbMVFke4PEgbcYd6cT14IbwnABx3WJw8+B24pjIdg8RAtmtyIBWoCxDLgFbCewfdIgUhaX6/x+EmM3W+vfPwRQwe8n1F22bnBfjS/F1M+Yk1jO4XIIiAu9BB+Fexlxr7Z86VjNX8HfRTK831YOlyYy7b+Jokesbe8bp5FQAR69xMAhouQXamw33sOzexXgaEVDHQaYHuNo+Ap1rsd0N0E57kf6huVLxxRkkurNuir6TRgzOFR+TwGONqbmA3Mou8MKcKSJ2DUSQnPlqV2I262FSGAo2gRaCcBFCyICzHJDB2z1wJ1ELGEsbuLgniXWNvSX6oCxlr4IlCdmq+XfH2UDYlQ3ITvC2MDhSsy4BgCADdviSuKeR3abehrqCDBr27sV6GdW6tmJOd7sKMgkFeAwNn6Asi2yPKE2NSXYkElYvjSuYuNXwK4lHl+v3qxrhjBbjqmv8o44s1ipqhgV/LdrQ2RTU0IdmYtU9N9Rp//DSfZF/34V/OFJe52pe1RMfah2/waoDKFCQ0ZF/4iebJh7qn6cTELhYIh2/3qMV0l4jcxPH7CWvkhdi+vR2KskzBBPcfDI75k5+0bEExwbuJmLM9cgrQVdwxj32ZqBHXr+smn2wPujKvhvY2yx3MDTp47hs7+OC/56TFnLDV5ZJaoZUlf6UVyWU9Y0hIfxCYx9eI6H4tcY1RO2dnBEPQ11tnJ4TMXUc2AZyw3cot6sO8GPE+uMKqUmxQqpzSSc+Rz3ltm63Ycn6cPu9CLC+AHM7sHjfg45uy1fGq8CBVBX+lmi+GbKyc8zuvvfbEDV3/7rEidUrTr8bnWl/6Fuf9lpdsWG21VIvX7afscVi9Xtv6FO/zV1La6vHOqMxDurThMYAWZ5YrWn72aatWPaT5k+pnmvcsnuYfb5t2HaYG2DS9Vz5ULK480k7B7MuRbFz9nKgaeqwasKacoAakCq7/MAj4sy9xLHD+LYAsoaxUgiFgJDOMzG7ADwMua+aK39HyrA+bi0T0mpKotrfSeYq56GWeAtIuSriK9h+i7SbssNHajZTOFOcE5LYOrNupMESXvjHSr4u2rfK1e3c7knnteFUr24vIOY2bgUufexc89KMuhsdf6fXv8BGZeVqWODm9MAAAAASUVORK5CYII="
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
