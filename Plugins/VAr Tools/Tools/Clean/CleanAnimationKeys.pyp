# -*- coding: utf-8 -*-
"""
CleanAnimationKeys — Cinema 4D Command Plugin
Удаляет ключевые кадры анимации сцены.
Предлагает выбор: все ключевые кадры сцены, только выделенного объекта,
или выделенного объекта и всех его дочерних объектов рекурсивно.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1069091
PLUGIN_NAME = "Clean Animation Keys v1.1"
PLUGIN_HELP = "Удалить ключевые кадры анимации сцены"

_ICON_B64 = "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"

ID_RADIO_GROUP = 2000
ID_BTN_OK      = 2001
ID_BTN_CANCEL  = 2002

MODE_SCENE       = 1
MODE_OBJECT      = 2
MODE_OBJECT_TREE = 3


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


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────────────────

def _count_keys_in_track(track):
    curve = track.GetCurve()
    if curve is None:
        return 0
    return curve.GetKeyCount()


def _count_keys_in_object(obj):
    count = 0
    track = obj.GetFirstCTrack()
    while track:
        count += _count_keys_in_track(track)
        track = track.GetNext()
    return count


def _remove_keys_from_track(track):
    curve = track.GetCurve()
    if curve is None:
        return
    key_count = curve.GetKeyCount()
    for i in range(key_count - 1, -1, -1):
        curve.DelKey(i)


def _remove_keys_from_object(obj):
    track = obj.GetFirstCTrack()
    while track:
        next_track = track.GetNext()
        _remove_keys_from_track(track)
        track = next_track


def _collect_children_recursive(obj):
    result = [obj]

    def _traverse(current):
        child = current.GetDown()
        while child:
            result.append(child)
            _traverse(child)
            child = child.GetNext()

    _traverse(obj)
    return result


def _collect_scene_objects(doc):
    result = []
    root = doc.GetFirstObject()
    if root is None:
        return result

    def _traverse(obj):
        while obj:
            result.append(obj)
            _traverse(obj.GetDown())
            obj = obj.GetNext()

    _traverse(root)
    return result


# ─── ДИАЛОГ ВЫБОРА ──────────────────────────────────────────────────────────

ID_INFO_TEXT = 2003  # многострочное поле с описанием


def _get_objects_for_mode(doc, sel, mode):
    """Возвращает список объектов для заданного режима."""
    if mode == MODE_SCENE:
        return _collect_scene_objects(doc)
    elif mode == MODE_OBJECT:
        return [sel] if sel is not None else []
    elif mode == MODE_OBJECT_TREE:
        return _collect_children_recursive(sel) if sel is not None else []
    return []


def _build_info_text(doc, sel, mode):
    """Формирует динамический текст с реальной статистикой для режима."""
    objects    = _get_objects_for_mode(doc, sel, mode)
    animated   = [o for o in objects if _count_keys_in_object(o) > 0]
    total_keys = sum(_count_keys_in_object(o) for o in animated)

    if mode == MODE_SCENE:
        scope = "Вся сцена"
    elif mode == MODE_OBJECT:
        scope = "Только: «{}»".format(sel.GetName() if sel else "—")
    else:
        scope = "«{}» и все дочерние".format(sel.GetName() if sel else "—")

    lines = [
        "Область:                  {}".format(scope),
        "Объектов / с анимацией:   {} / {}".format(len(objects), len(animated)),
        "Ключей к удалению:        {}".format(total_keys),
    ]
    return "\n".join(lines)


class CleanAnimationKeysDialog(c4d.gui.GeDialog):

    def __init__(self, doc, sel=None):
        super().__init__()
        self.result   = None
        self._doc     = doc
        self._sel     = sel
        self._has_sel = sel is not None

    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME)

        self.GroupBegin(1000, c4d.BFH_SCALEFIT, 1, 1)
        self.GroupBorderSpace(12, 10, 12, 10)

        # ── Многострочное поле с описанием ──
        self.GroupBegin(1001, c4d.BFH_SCALEFIT, 1, 1)
        self.GroupBorderSpace(0, 0, 0, 10)
        self.AddMultiLineEditText(
            ID_INFO_TEXT,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=380, inith=52,
            style=c4d.DR_MULTILINE_READONLY | c4d.DR_MULTILINE_WORDWRAP,
        )
        self.GroupEnd()

        # ── Радиокнопки — только если есть выделенный объект ──
        if self._has_sel:
            self.GroupBegin(1003, c4d.BFH_SCALEFIT, 1, 1)
            self.GroupBorderSpace(8, 0, 8, 0)
            self.AddRadioGroup(ID_RADIO_GROUP, c4d.BFH_SCALEFIT, 1, 1)
            self.AddChild(ID_RADIO_GROUP, MODE_SCENE,       "Все ключевые кадры сцены")
            self.AddChild(ID_RADIO_GROUP, MODE_OBJECT,      "Ключевые кадры выделенного объекта")
            self.AddChild(ID_RADIO_GROUP, MODE_OBJECT_TREE, "Выделенный объект и все дочерние")
            self.GroupEnd()

        self.GroupEnd()

        self.GroupBegin(0, c4d.BFH_CENTER, 2, 1)
        self.AddButton(ID_BTN_OK,     c4d.BFH_SCALE, name="Удалить")
        self.AddButton(ID_BTN_CANCEL, c4d.BFH_SCALE, name="Отмена")
        self.GroupEnd()

        return True

    def InitValues(self):
        if self._has_sel:
            self.SetInt32(ID_RADIO_GROUP, MODE_OBJECT)
            self.SetString(ID_INFO_TEXT, _build_info_text(self._doc, self._sel, MODE_OBJECT))
        else:
            self.SetString(ID_INFO_TEXT, _build_info_text(self._doc, self._sel, MODE_SCENE))
        return True

    def Command(self, id, msg):
        # Обновляем описание при смене радиокнопки
        if id == ID_RADIO_GROUP and self._has_sel:
            mode = self.GetInt32(ID_RADIO_GROUP)
            self.SetString(ID_INFO_TEXT, _build_info_text(self._doc, self._sel, mode))

        if id == ID_BTN_OK:
            if self._has_sel:
                self.result = self.GetInt32(ID_RADIO_GROUP)
            else:
                self.result = MODE_SCENE
            self.Close()
        elif id == ID_BTN_CANCEL:
            self.result = None
            self.Close()
        return True


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanAnimationKeysCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        sel = doc.GetActiveObject()

        # Всегда открываем модалку; sel=None — режим "только сцена"
        dialog = CleanAnimationKeysDialog(doc=doc, sel=sel)
        dialog.Open(c4d.DLG_TYPE_MODAL, defaultw=420, defaulth=160)

        if dialog.result is None:
            return True

        mode = dialog.result

        objects = _get_objects_for_mode(doc, sel, mode)

        doc.StartUndo()

        for obj in objects:
            if obj.GetDocument() is None:
                continue
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            _remove_keys_from_object(obj)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = CleanAnimationKeysCommand(),
    )
