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
PLUGIN_VER  = "v1.2"

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


def find_latest_keyframe(doc):
    """
    Возвращает номер самого позднего ключевого кадра во всей сцене
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

    latest = None
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
            if latest is None or frame > latest:
                latest = frame

    return latest


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
    ID_ANIM_START      = 1003  # Желаемый кадр начала анимации
    ID_STATIC_END      = 1004  # Статичных кадров в конце
    ID_PREVIEW_TSTART  = 1005  # Превью: начало таймлайна
    ID_PREVIEW_ASTART  = 1006  # Превью: кадр начала анимации
    ID_PREVIEW_AEND    = 1007  # Превью: кадр конца анимации
    ID_PREVIEW_TEND    = 1008  # Превью: конец таймлайна

    def __init__(self, earliest_frame, latest_frame, default_static_start, default_static_end):
        super().__init__()
        self.earliest_frame       = earliest_frame        # первый ключ в исходной сцене
        self.latest_frame         = latest_frame          # последний ключ в исходной сцене
        self.default_static_start = default_static_start  # вычисленное начальное значение поля
        self.default_static_end   = default_static_end    # вычисленное начальное значение поля
        self.result = None   # None = отмена, (static_start, anim_start, static_end) иначе

    def _calc_preview(self):
        """Вычисляет итоговые значения на основе текущих полей диалога."""
        static_start = int(self.GetFloat(self.ID_STATIC_INPUT))
        anim_start   = int(self.GetFloat(self.ID_ANIM_START))
        static_end   = int(self.GetFloat(self.ID_STATIC_END))

        # delta — сдвиг всех ключей
        target_first_key = anim_start + static_start
        delta = target_first_key - self.earliest_frame

        # Кадр последнего ключа после сдвига
        anim_end_frame = self.latest_frame + delta

        # Границы таймлайна
        timeline_start = 0
        timeline_end   = anim_end_frame + static_end

        return timeline_start, timeline_end, target_first_key, anim_end_frame

    def _update_preview(self):
        """Обновляет текстовые метки превью."""
        ts, te, af, ae = self._calc_preview()
        self.SetString(self.ID_PREVIEW_TSTART, f"Таймлайн начало:       {ts}")
        self.SetString(self.ID_PREVIEW_ASTART, f"Анимация начало:       {af}")
        self.SetString(self.ID_PREVIEW_AEND,   f"Анимация конец:         {ae}")
        self.SetString(self.ID_PREVIEW_TEND,   f"Таймлайн конец:         {te}")

    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME + " " + PLUGIN_VER)

        self.AddStaticText(0, c4d.BFH_LEFT, name=(
            f"Первый ключевой кадр: {self.earliest_frame}   "
            f"Последний ключевой кадр: {self.latest_frame}"
        ))
        self.AddSeparatorH(200)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Начало анимации (кадр):")
        self.AddEditNumberArrows(self.ID_ANIM_START, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Статичных кадров в начале:")
        self.AddEditNumberArrows(self.ID_STATIC_INPUT, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Статичных кадров в конце:")
        self.AddEditNumberArrows(self.ID_STATIC_END, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.AddSeparatorH(200)

        # Блок превью (динамические метки — EditText readonly, т.к. SetString на StaticText не работает в R26)
        self.AddEditText(self.ID_PREVIEW_TSTART, c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_ASTART, c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_AEND,   c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_TEND,   c4d.BFH_SCALEFIT, initw=300, inith=0)

        self.AddSeparatorH(200)

        self.GroupBegin(0, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.ID_OK,     c4d.BFH_SCALE, name="OK")
        self.AddButton(self.ID_CANCEL, c4d.BFH_SCALE, name="Отмена")
        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetFloat(self.ID_ANIM_START,   0, min=-10000, max=10000, step=1,
                      tristate=False)
        self.SetFloat(self.ID_STATIC_INPUT, self.default_static_start, min=0, max=10000, step=1,
                      tristate=False)
        self.SetFloat(self.ID_STATIC_END,   self.default_static_end,   min=0, max=10000, step=1,
                      tristate=False)
        # Поля превью — только чтение
        self.Enable(self.ID_PREVIEW_TSTART, False)
        self.Enable(self.ID_PREVIEW_ASTART, False)
        self.Enable(self.ID_PREVIEW_AEND,   False)
        self.Enable(self.ID_PREVIEW_TEND,   False)
        self._update_preview()
        return True

    def Command(self, id, msg):
        # Обновляем превью при изменении любого поля ввода
        if id in (self.ID_STATIC_INPUT, self.ID_ANIM_START, self.ID_STATIC_END):
            self._update_preview()
        elif id == self.ID_OK:
            static_start = int(self.GetFloat(self.ID_STATIC_INPUT))
            anim_start   = int(self.GetFloat(self.ID_ANIM_START))
            static_end   = int(self.GetFloat(self.ID_STATIC_END))
            self.result  = (static_start, anim_start, static_end)
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
        # 1. Найти самый ранний и самый поздний ключевые кадры
        earliest = find_earliest_keyframe(doc)
        latest   = find_latest_keyframe(doc)

        if earliest is None:
            gui.MessageDialog("В сцене не найдено ни одного ключевого кадра.")
            return True

        # 2. Показать диалог
        fps            = doc.GetFps()
        timeline_end   = doc.GetMaxTime().GetFrame(fps)

        # Статичных кадров в начале = сколько кадров от 0 до первого ключа (минимум 0)
        default_static_start = max(0, earliest)
        # Статичных кадров в конце = сколько кадров от последнего ключа до конца таймлайна (минимум 0)
        default_static_end   = max(0, timeline_end - latest)

        dlg = StaticFramesDialog(
            earliest_frame=earliest,
            latest_frame=latest,
            default_static_start=default_static_start,
            default_static_end=default_static_end,
        )
        dlg.Open(
            dlgtype=c4d.DLG_TYPE_MODAL,
            pluginid=PLUGIN_ID,
            defaultw=360,
            defaulth=200,
        )

        if dlg.result is None:
            return True  # Пользователь нажал «Отмена»

        static_start, anim_start, static_end = dlg.result

        # 3. Вычислить сдвиг
        # Хотим, чтобы earliest оказался на кадре (anim_start + static_start).
        # delta — на сколько кадров сдвинуть все ключи вправо (может быть отрицательным).
        target_first_key = anim_start + static_start
        delta = target_first_key - earliest

        fps = doc.GetFps()

        # Новые границы временной шкалы
        new_min    = 0
        anim_end   = latest + delta          # последний ключ после сдвига
        new_max    = anim_end + static_end   # + статичные кадры в конце

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
