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

import c4d # type: ignore
from c4d import gui # type: ignore
import os
import base64
import tempfile


# Уникальный ID плагина (получен из диапазона для частных плагинов)
PLUGIN_ID = 1068937
PLUGIN_NAME = "Shift Animation2Zero"
PLUGIN_VER  = "v1.2.2"

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
    "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"
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
