"""
shift_anim_to_zero.pyp
Cinema 4D R26 Plugin — Shift Animation Start to Zero
=====================================================

Установка:
  Поместите этот файл в папку:
    Windows: C:/Users/<user>/AppData/Roaming/MAXON/Cinema 4D R26/plugins/shift_anim_to_zero/
    macOS:   ~/Library/Preferences/MAXON/Cinema 4D R26/plugins/shift_anim_to_zero/

  Имя папки и файла должны совпадать (без расширения).
  Перезапустите Cinema 4D. Плагин появится в меню Plugins.
"""

import c4d
from c4d import gui
import os
import base64
import tempfile


# Уникальный ID плагина (получен из диапазона для частных плагинов)
PLUGIN_ID = 1068937
PLUGIN_NAME = "Shift Animation2Zero"
PLUGIN_VER  = "v1.1"

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def get_all_tracks(op, tracks):
    """Рекурсивно собирает все анимационные треки сцены."""
    if op is None:
        return
    # Треки на самом объекте
    track = op.GetFirstCTrack()
    while track:
        tracks.append((op, track))
        track = track.GetNext()
    # Теги объекта
    tag = op.GetFirstTag()
    while tag:
        t = tag.GetFirstCTrack()
        while t:
            tracks.append((tag, t))
            t = t.GetNext()
        tag = tag.GetNext()
    # Дочерние объекты
    child = op.GetDown()
    while child:
        get_all_tracks(child, tracks)
        child = child.GetNext()


def find_earliest_keyframe(doc):
    """
    Возвращает номер самого раннего ключевого кадра во всей сцене
    (в единицах FPS-фреймов) или None, если ключей нет.
    """
    fps = doc.GetFps()
    tracks = []

    # Объекты сцены
    op = doc.GetFirstObject()
    while op:
        get_all_tracks(op, tracks)
        op = op.GetNext()

    # Материалы
    mat = doc.GetFirstMaterial()
    while mat:
        t = mat.GetFirstCTrack()
        while t:
            tracks.append((mat, t))
            t = t.GetNext()
        mat = mat.GetNext()

    earliest = None
    for owner, track in tracks:
        curve = track.GetCurve()
        if curve is None:
            continue
        key_count = curve.GetKeyCount()
        for i in range(key_count):
            key = curve.GetKey(i)
            if key is None:
                continue
            frame = key.GetTime().GetFrame(fps)
            if earliest is None or frame < earliest:
                earliest = frame

    return earliest


def shift_all_keyframes(doc, delta_frames):
    """
    Сдвигает все ключевые кадры сцены на delta_frames.
    delta_frames > 0 — сдвиг вправо (в сторону увеличения кадра).
    """
    fps = doc.GetFps()
    tracks = []

    op = doc.GetFirstObject()
    while op:
        get_all_tracks(op, tracks)
        op = op.GetNext()

    mat = doc.GetFirstMaterial()
    while mat:
        t = mat.GetFirstCTrack()
        while t:
            tracks.append((mat, t))
            t = t.GetNext()
        mat = mat.GetNext()

    for owner, track in tracks:
        curve = track.GetCurve()
        if curve is None:
            continue
        key_count = curve.GetKeyCount()
        # Двигаем в правильном порядке, чтобы не перезаписать ключи
        order = range(key_count - 1, -1, -1) if delta_frames > 0 else range(key_count)
        for i in order:
            key = curve.GetKey(i)
            if key is None:
                continue
            old_frame = key.GetTime().GetFrame(fps)
            new_time = c4d.BaseTime(old_frame + delta_frames, fps)
            curve.MoveKey(new_time, i)


# ---------------------------------------------------------------------------
# Диалог запроса количества статичных кадров
# ---------------------------------------------------------------------------

class StaticFramesDialog(gui.GeDialog):
    ID_STATIC_INPUT    = 1000
    ID_OK              = 1001
    ID_CANCEL          = 1002
    ID_ANIM_START      = 1003  # Новое поле: желаемый кадр начала анимации

    def __init__(self, earliest_frame):
        super().__init__()
        self.earliest_frame = earliest_frame
        self.result = None          # None = отмена, (static_frames, anim_start) иначе

    def CreateLayout(self):
        self.SetTitle("Shift Animation to Zero")

        self.AddStaticText(0, c4d.BFH_LEFT, name=(
            f"Первый ключевой кадр: {self.earliest_frame}"
        ))
        self.AddSeparatorH(200)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Статичных кадров в начале:")
        self.AddEditNumberArrows(self.ID_STATIC_INPUT, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Начало анимации (кадр):")
        self.AddEditNumberArrows(self.ID_ANIM_START, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.AddSeparatorH(200)

        self.GroupBegin(0, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.ID_OK,     c4d.BFH_SCALE, name="OK")
        self.AddButton(self.ID_CANCEL, c4d.BFH_SCALE, name="Отмена")
        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetFloat(self.ID_STATIC_INPUT, 0, min=0, max=10000, step=1,
                      tristate=False)
        # Начало анимации: допускает отрицательные значения
        self.SetFloat(self.ID_ANIM_START, 0, min=-10000, max=10000, step=1,
                      tristate=False)
        return True

    def Command(self, id, msg):
        if id == self.ID_OK:
            static_frames = int(self.GetFloat(self.ID_STATIC_INPUT))
            anim_start    = int(self.GetFloat(self.ID_ANIM_START))
            self.result   = (static_frames, anim_start)
            self.Close()
        elif id == self.ID_CANCEL:
            self.result = None
            self.Close()
        return True


# ---------------------------------------------------------------------------
# Команда плагина
# ---------------------------------------------------------------------------

class ShiftAnimToZeroCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        # 1. Найти самый ранний ключевой кадр
        earliest = find_earliest_keyframe(doc)

        if earliest is None:
            gui.MessageDialog("В сцене не найдено ни одного ключевого кадра.")
            return True

        # 2. Показать диалог
        dlg = StaticFramesDialog(earliest_frame=earliest)
        dlg.Open(
            dlgtype=c4d.DLG_TYPE_MODAL,
            pluginid=PLUGIN_ID,
            defaultw=320,
            defaulth=140,
        )

        if dlg.result is None:
            return True  # Пользователь нажал «Отмена»

        static_frames, anim_start = dlg.result

        # 3. Вычислить сдвиг
        # Хотим, чтобы earliest оказался на кадре (anim_start + static_frames).
        # delta — на сколько кадров сдвинуть все ключи вправо (может быть отрицательным).
        target_first_key = anim_start + static_frames
        delta = target_first_key - earliest

        fps          = doc.GetFps()
        old_min_time = doc.GetMinTime().GetFrame(fps)
        old_max_time = doc.GetMaxTime().GetFrame(fps)

        # Новые границы временной шкалы
        new_min = 0
        new_max = old_max_time + delta  # расширяем/сжимаем на величину сдвига

        # 4. Открыть Undo-группу
        doc.StartUndo()

        # Undo для временной шкалы
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, doc)

        # Сдвиг ключей
        shift_all_keyframes(doc, delta)

        # Обновить временную шкалу документа
        doc.SetMinTime(c4d.BaseTime(new_min, fps))
        doc.SetMaxTime(c4d.BaseTime(new_max, fps))

        # Закрыть Undo-группу
        doc.EndUndo()

        # 5. Обновить UI Cinema 4D
        # FORCEREDRAW необходим для корректной работы Ctrl+Z сразу после операции
        c4d.EventAdd(c4d.EVENT_FORCEREDRAW)

        sign = "+" if delta >= 0 else ""
        gui.MessageDialog(
            f"Готово!\n\n"
            f"Первый ключ был: {earliest}\n"
            f"Статичных кадров: {static_frames}\n"
            f"Начало анимации: {anim_start}\n"
            f"Сдвиг: {sign}{delta} кадров\n\n"
            f"Временная шкала: 0 → {new_max}"
        )

        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED


_ICON_BP = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAABwUlEQVRYhe2VPUhbYRSGn+/Gn6JJ/EkTcbFSHErFTS1OdeqooFsXB38gFktB0FE7xk4dJCAasKVTwUWoEB0lLm4idCgdFMR/rwlaEvUeNzGpV2+uV+5y3/E7533P+51z73fAgweHkEn4w5l4XaRYnuaYA6MsTunFZiZR/dYVA1fa1Riwj6El07O1A1Z5qvAgMxcawZAuOyZESQmoFgUhEVkMDp48qOPcCGzivw7YhZ6oeukzfItAk8CH4MDxrBWe5Q6IyIiIHJjFfYZvCoigGe+sFgcosZoIhIDnplEtFyVbqQLRvf0iNK1DRCZFRJzWzfsGJps7/eFgdqVBztsC6jJvPI39w7zoH+b15+S9gjXJebPQFqjpVOrHF+DmInlFwoHccjPpN4XF0aCifoF/fz6iKdtNaACJdXS8Hy2Qvp1x1n4ns/eE8qp1Lva+Mf5qxq4BAJSST6YGxOR6zk/exMBf8S/dlbS9UENWb6Wsro/Y76FHFVRK+25qQF9b7d5Qtb/SlF7msQw43+3hWdNXDLH9du0AMV3PTdhiP9Vv6PouKMbAIXDkpgHFrQfEDQP37wKbKGYZ/QROnTbgwYMH13ENsuSJ2NS0zugAAAAASUVORK5CYII="
)

def _make_icon_bp():
    png_data = base64.b64decode(_ICON_BP)
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


ICO_BP = _make_icon_bp()

# ---------------------------------------------------------------------------
# Регистрация плагина
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id        = PLUGIN_ID,
        str       = PLUGIN_NAME + " " + PLUGIN_VER,
        info      = 0,
        icon      = ICO_BP,
        help      = "Смещает все ключевые кадры так, чтобы анимация начиналась с нуля",
        dat       = ShiftAnimToZeroCommand(),
    )
