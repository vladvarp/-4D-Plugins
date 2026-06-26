"""
scale_anim_timeline.pyp
Cinema 4D R26 Plugin — Scale Animation Timeline
=====================================================

Установка:
  Поместите этот файл в папку:
    Windows: C:/Users/<user>/AppData/Roaming/MAXON/Cinema 4D R26/plugins/scale_anim_timeline/
    macOS:   ~/Library/Preferences/MAXON/Cinema 4D R26/plugins/scale_anim_timeline/

  Имя папки и файла должны совпадать (без расширения).
  Перезапустите Cinema 4D. Плагин появится в меню Plugins.

Идея:
  Берём текущую длину таймлайна (0..N) как базу масштабирования.
  Пользователь вводит новую длину таймлайна (M).
  Все ключевые кадры сцены (и сама длина таймлайна) масштабируются
  с коэффициентом k = M / N относительно нуля:
      new_frame = old_frame * k

  Пример: таймлайн 100 кадров, анимация 20..80.
    Ввод 50  -> k = 0.5  -> анимация 10..40,  таймлайн 0..50
    Ввод 200 -> k = 2.0  -> анимация 40..160, таймлайн 0..200
"""

import c4d # type: ignore
from c4d import gui # type: ignore
import os
import base64
import tempfile


# Уникальный ID плагина (получен из диапазона для частных плагинов)
PLUGIN_ID = 1068954
PLUGIN_NAME = "Scale Animation Timeline"
PLUGIN_VER  = "v1.1.1"

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def get_all_tracks(op, tracks):
    """Рекурсивно собирает все анимационные треки сцены."""
    if op is None:
        return
    track = op.GetFirstCTrack()
    while track:
        tracks.append((op, track))
        track = track.GetNext()
    tag = op.GetFirstTag()
    while tag:
        t = tag.GetFirstCTrack()
        while t:
            tracks.append((tag, t))
            t = t.GetNext()
        tag = tag.GetNext()
    child = op.GetDown()
    while child:
        get_all_tracks(child, tracks)
        child = child.GetNext()


def collect_all_tracks(doc):
    """Возвращает список всех (owner, track) во всей сцене (объекты + материалы)."""
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
    return tracks


def find_earliest_latest_keyframe(doc):
    """
    Возвращает (earliest, latest) — номера самого раннего и самого позднего
    ключевого кадра во всей сцене (в единицах FPS-фреймов), либо (None, None).
    """
    fps = doc.GetFps()
    tracks = collect_all_tracks(doc)

    earliest = None
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
            if earliest is None or frame < earliest:
                earliest = frame
            if latest is None or frame > latest:
                latest = frame

    return earliest, latest


def scale_all_keyframes(doc, factor):
    """
    Масштабирует время всех ключевых кадров сцены относительно нуля:
        new_frame = round(old_frame * factor)
    Также масштабирует тангенсы (длину касательных по времени), чтобы
    форма кривой не искажалась.
    """
    fps = doc.GetFps()
    tracks = collect_all_tracks(doc)

    for owner, track in tracks:
        curve = track.GetCurve()
        if curve is None:
            continue
        key_count = curve.GetKeyCount()
        # При масштабировании > 1 двигаем с конца к началу, при < 1 — с начала,
        # чтобы не возникало коллизий порядка ключей при перезаписи.
        order = range(key_count - 1, -1, -1) if factor > 1.0 else range(key_count)
        for i in order:
            key = curve.GetKey(i)
            if key is None:
                continue
            old_frame = key.GetTime().GetFrame(fps)
            new_frame = int(round(old_frame * factor))
            new_time = c4d.BaseTime(new_frame, fps)
            curve.MoveKey(new_time, i)

        # Масштабируем длину тангенсов (по времени), чтобы кривая сохраняла форму
        for i in range(curve.GetKeyCount()):
            key = curve.GetKey(i)
            if key is None:
                continue
            try:
                lt = key.GetTimeLeft()
                rt = key.GetTimeRight()
                key.SetTimeLeft(curve, c4d.BaseTime(lt.Get() * factor))
                key.SetTimeRight(curve, c4d.BaseTime(rt.Get() * factor))
            except AttributeError:
                # Некоторые версии API не поддерживают эти методы — пропускаем безопасно
                pass


# ---------------------------------------------------------------------------
# Диалог запроса новой длины таймлайна
# ---------------------------------------------------------------------------

class ScaleTimelineDialog(gui.GeDialog):
    ID_NEW_LENGTH_INPUT = 1000
    ID_OK               = 1001
    ID_CANCEL           = 1002
    ID_PREVIEW_TSTART   = 1005  # Превью: начало таймлайна
    ID_PREVIEW_ASTART   = 1006  # Превью: кадр начала анимации
    ID_PREVIEW_AEND     = 1007  # Превью: кадр конца анимации
    ID_PREVIEW_TEND      = 1008  # Превью: конец таймлайна
    ID_PREVIEW_FACTOR   = 1009  # Превью: коэффициент масштабирования
    ID_QUICK_HALF       = 1010  # Быстрая кнопка x0.5
    ID_QUICK_DOUBLE     = 1011  # Быстрая кнопка x2

    def __init__(self, old_length, earliest_frame, latest_frame):
        super().__init__()
        self.old_length     = old_length      # текущая длина таймлайна (кадров)
        self.earliest_frame = earliest_frame  # первый ключ в исходной сцене (может быть None)
        self.latest_frame   = latest_frame    # последний ключ в исходной сцене (может быть None)
        self.result = None   # None = отмена, new_length иначе

    def _calc_preview(self):
        """Вычисляет итоговые значения на основе текущего поля диалога."""
        new_length = int(self.GetFloat(self.ID_NEW_LENGTH_INPUT))
        old_length = self.old_length if self.old_length > 0 else 1
        factor = new_length / float(old_length)

        timeline_start = 0
        timeline_end = new_length

        if self.earliest_frame is not None:
            anim_start = int(round(self.earliest_frame * factor))
            anim_end   = int(round(self.latest_frame * factor))
        else:
            anim_start = None
            anim_end = None

        return timeline_start, timeline_end, anim_start, anim_end, factor

    def _update_preview(self):
        """Обновляет текстовые метки превью."""
        ts, te, af, ae, factor = self._calc_preview()
        self.SetString(self.ID_PREVIEW_TSTART, f"Таймлайн начало:       {ts}")
        if af is not None:
            self.SetString(self.ID_PREVIEW_ASTART, f"Анимация начало:       {af}")
            self.SetString(self.ID_PREVIEW_AEND,   f"Анимация конец:         {ae}")
        else:
            self.SetString(self.ID_PREVIEW_ASTART, "Анимация начало:       —")
            self.SetString(self.ID_PREVIEW_AEND,   "Анимация конец:         —")
        self.SetString(self.ID_PREVIEW_TEND,   f"Таймлайн конец:         {te}")
        self.SetString(self.ID_PREVIEW_FACTOR, f"Коэффициент:            x{factor:.4g}")

    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME + " " + PLUGIN_VER)

        if self.earliest_frame is not None:
            info = (
                f"Текущий таймлайн: 0–{self.old_length}   "
                f"Анимация: {self.earliest_frame}–{self.latest_frame}"
            )
        else:
            info = f"Текущий таймлайн: 0–{self.old_length}   (ключевых кадров не найдено)"
        self.AddStaticText(0, c4d.BFH_LEFT, name=info)
        self.AddSeparatorH(200)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Новая длина таймлайна (кадров):")
        self.AddEditNumberArrows(self.ID_NEW_LENGTH_INPUT, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        # Быстрые кнопки-фишки: x0.5 / x2 от текущей длины
        self.GroupBegin(0, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.ID_QUICK_HALF,   c4d.BFH_SCALE, name="x0.5")
        self.AddButton(self.ID_QUICK_DOUBLE, c4d.BFH_SCALE, name="x2")
        self.GroupEnd()

        self.AddSeparatorH(200)

        # Блок превью (динамические метки — EditText readonly, как в референсе)
        self.AddEditText(self.ID_PREVIEW_TSTART, c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_ASTART, c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_AEND,   c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_TEND,   c4d.BFH_SCALEFIT, initw=300, inith=0)
        self.AddEditText(self.ID_PREVIEW_FACTOR, c4d.BFH_SCALEFIT, initw=300, inith=0)

        self.AddSeparatorH(200)

        self.GroupBegin(0, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.ID_OK,     c4d.BFH_SCALE, name="OK")
        self.AddButton(self.ID_CANCEL, c4d.BFH_SCALE, name="Отмена")
        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetFloat(self.ID_NEW_LENGTH_INPUT, self.old_length, min=1, max=1000000, step=1,
                      tristate=False)
        self.Enable(self.ID_PREVIEW_TSTART, False)
        self.Enable(self.ID_PREVIEW_ASTART, False)
        self.Enable(self.ID_PREVIEW_AEND,   False)
        self.Enable(self.ID_PREVIEW_TEND,   False)
        self.Enable(self.ID_PREVIEW_FACTOR, False)
        self._update_preview()
        return True

    def Command(self, id, msg):
        if id == self.ID_NEW_LENGTH_INPUT:
            self._update_preview()
        elif id == self.ID_QUICK_HALF:
            new_val = max(1, int(round(self.old_length * 0.5)))
            self.SetFloat(self.ID_NEW_LENGTH_INPUT, new_val)
            self._update_preview()
        elif id == self.ID_QUICK_DOUBLE:
            new_val = max(1, int(round(self.old_length * 2.0)))
            self.SetFloat(self.ID_NEW_LENGTH_INPUT, new_val)
            self._update_preview()
        elif id == self.ID_OK:
            new_length = int(self.GetFloat(self.ID_NEW_LENGTH_INPUT))
            if new_length <= 0:
                gui.MessageDialog("Длина таймлайна должна быть больше нуля.")
                return True
            self.result = new_length
            self.Close()
        elif id == self.ID_CANCEL:
            self.result = None
            self.Close()
        return True


# ---------------------------------------------------------------------------
# Команда плагина
# ---------------------------------------------------------------------------

class ScaleAnimTimelineCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        fps = doc.GetFps()

        # 1. Текущая длина таймлайна (берём за базу масштабирования отрезок 0..MaxTime)
        old_min = doc.GetMinTime().GetFrame(fps)
        old_max = doc.GetMaxTime().GetFrame(fps)
        old_length = old_max - old_min
        if old_length <= 0:
            old_length = old_max  # на случай нулевой/отрицательной длины — fallback

        # 2. Найти границы анимации (для информации и превью)
        earliest, latest = find_earliest_latest_keyframe(doc)

        # 3. Показать диалог
        dlg = ScaleTimelineDialog(
            old_length=old_length,
            earliest_frame=earliest,
            latest_frame=latest,
        )
        dlg.Open(
            dlgtype=c4d.DLG_TYPE_MODAL,
            pluginid=PLUGIN_ID,
            defaultw=360,
            defaulth=220,
        )

        if dlg.result is None:
            return True  # Пользователь нажал «Отмена»

        new_length = dlg.result

        # 4. Вычислить коэффициент масштабирования относительно нуля
        factor = new_length / float(old_length)

        # 5. Открыть Undo-группу
        doc.StartUndo()
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, doc)

        # Масштабируем все ключевые кадры сцены
        scale_all_keyframes(doc, factor)

        # Новые границы временной шкалы документа
        new_min = 0
        new_max = new_length
        doc.SetMinTime(c4d.BaseTime(new_min, fps))
        doc.SetMaxTime(c4d.BaseTime(new_max, fps))

        # Текущий кадр тоже масштабируем, чтобы плейхед остался в "том же" месте анимации
        cur_frame = doc.GetTime().GetFrame(fps)
        new_cur_frame = int(round(cur_frame * factor))
        new_cur_frame = max(new_min, min(new_max, new_cur_frame))
        doc.SetTime(c4d.BaseTime(new_cur_frame, fps))

        doc.EndUndo()

        # 6. Обновить UI Cinema 4D
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
        help      = "Масштабирует таймлайн и все ключевые кадры сцены относительно нуля",
        dat       = ScaleAnimTimelineCommand(),
    )
