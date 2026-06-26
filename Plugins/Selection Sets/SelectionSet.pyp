# coding: utf-8
"""
Selection Sets — Cinema 4D R26+

Сохранение и восстановление наборов выделения объектов.
Каждый набор — это тег (Selection Set Tag) на нулевом объекте внутри
контейнера "Selection Sets". Тег хранит имя набора и ссылки на объекты
в пользовательских данных (UserData).

Возможности:
  - Сохранить текущее выделение как именованный набор
  - Восстановить выделение по набору
  - Добавить / убрать объекты из набора
  - Очистить / удалить / переименовать набор
"""

import c4d # type: ignore
import os
import base64
import tempfile

# ── ID ────────────────────────────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068965
PLUGIN_ID_TAG = 1068966

PLUGIN_NAME   = "Selection Sets"
PLUGIN_NAME_V = "v1.4.1"
TAG_NAME      = "Selection Set Tag"
PLUGIN_HELP   = "Управление наборами выделения объектов"

UD_SET_NAME = 1
OBJ_PREFIX  = "Obj_"
MAX_OBJECTS = 256

# Description-based parameter IDs
SS_GRP_PARAMS = 2000
SS_SET_NAME   = 2001

# ── UI IDs ────────────────────────────────────────────────────────────────────
ID_COMBO   = 1000
ID_BTN_NEW = 1001
ID_BTN_SEL = 1002
ID_BTN_ADD = 1003
ID_BTN_REM = 1004
ID_BTN_DEL = 1005
ID_BTN_RNM = 1006
ID_BTN_CLR = 1007
ID_LBL_INF = 1008
ID_LBL_OBJ = 1009


def _set_object_icon(obj, icon_b64):
    """Назначает иконку объекту через временный PNG-файл."""
    try:
        data = base64.b64decode(icon_b64)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            tmp.write(data)
            tmp.close()
            obj[c4d.ID_BASELIST_ICON_FILE] = tmp.name
        finally:
            pass
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
#  TAG HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _tag_objects(tag):
    """Возвращает список живых объектов из UserData тега."""
    result = []
    for descid, bc in tag.GetUserDataContainer():
        if bc.GetString(c4d.DESC_NAME).startswith(OBJ_PREFIX):
            try:
                obj = tag[descid]
                if obj is not None:
                    result.append(obj)
            except Exception:
                pass
    return result


def _tag_add(tag, obj):
    """Добавляет объект в набор. True если добавлен."""
    if obj in _tag_objects(tag):
        return False

    used = set()
    for descid, bc in tag.GetUserDataContainer():
        name = bc.GetString(c4d.DESC_NAME)
        if name.startswith(OBJ_PREFIX):
            used.add(name)

    idx = 1
    while OBJ_PREFIX + str(idx) in used:
        idx += 1
    if idx > MAX_OBJECTS:
        return False

    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
    bc.SetString(c4d.DESC_NAME, OBJ_PREFIX + str(idx))
    bc.SetString(c4d.DESC_SHORT_NAME, "")
    bc.SetBool(c4d.DESC_HIDE, True)
    did = tag.AddUserData(bc)
    tag[did] = obj
    tag.Message(c4d.MSG_UPDATE)
    return True


def _tag_remove(tag, obj):
    """Удаляет объект из набора. True если найден."""
    for descid, bc in tag.GetUserDataContainer():
        name = bc.GetString(c4d.DESC_NAME)
        if name.startswith(OBJ_PREFIX):
            try:
                if tag[descid] == obj:
                    tag[descid] = None
                    tag.Message(c4d.MSG_UPDATE)
                    return True
            except Exception:
                pass
    return False


def _tag_clear(tag):
    """Очищает все ссылки на объекты."""
    for descid, bc in tag.GetUserDataContainer():
        if bc.GetString(c4d.DESC_NAME).startswith(OBJ_PREFIX):
            try:
                tag[descid] = None
            except Exception:
                pass
    tag.Message(c4d.MSG_UPDATE)


def _find_all_sets(doc):
    """Находит все теги наборов выделения в сцене."""
    result = []
    def walk(obj):
        while obj:
            t = obj.GetFirstTag()
            while t:
                if t.GetType() == PLUGIN_ID_TAG:
                    result.append(t)
                t = t.GetNext()
            walk(obj.GetDown())
            obj = obj.GetNext()
    walk(doc.GetFirstObject())
    return result


def _ensure_container(doc):
    """Находит или создаёт корневой объект-контейнер."""
    obj = doc.GetFirstObject()
    while obj:
        if obj.GetName() == "Selection Sets" and obj.GetType() == c4d.Onull:
            return obj
        obj = obj.GetNext()
    null = c4d.BaseObject(c4d.Onull)
    null.SetName("Selection Sets")
    _set_object_icon(null, _ICON_CMD_B64)
    doc.InsertObject(null)
    return null


# ══════════════════════════════════════════════════════════════════════════════
#  DIALOG
# ══════════════════════════════════════════════════════════════════════════════

class SelSetDialog(c4d.gui.GeDialog):

    def CreateLayout(self):
        self.SetTitle("Selection Sets")
        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupBorderSpace(8, 8, 8, 8)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Набор:")
        self.AddComboBox(ID_COMBO, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.AddStaticText(ID_LBL_INF, c4d.BFH_SCALEFIT, name="")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(ID_BTN_NEW, c4d.BFH_SCALEFIT, name="Новый набор")
        self.AddButton(ID_BTN_RNM, c4d.BFH_SCALEFIT, name="Переименовать")
        self.GroupEnd()

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 0)
        self.AddButton(ID_BTN_DEL, c4d.BFH_SCALEFIT, name="Удалить набор")
        self.GroupEnd()

        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(ID_BTN_ADD, c4d.BFH_SCALEFIT, name="+ Добавить")
        self.AddButton(ID_BTN_REM, c4d.BFH_SCALEFIT, name="- Убрать")
        self.AddButton(ID_BTN_SEL, c4d.BFH_SCALEFIT, name="Выделить")
        self.AddButton(ID_BTN_CLR, c4d.BFH_SCALEFIT, name="Очистить")
        self.GroupEnd()

        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Объекты в наборе:")

        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddMultiLineEditText(
            ID_LBL_OBJ,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=280, inith=120,
            style=c4d.DR_MULTILINE_READONLY | c4d.DR_MULTILINE_MONOSPACED,
        )
        self.GroupEnd()

        self.GroupEnd()
        return True

    def InitValues(self):
        self._sets = []
        self._rebuild()
        return True

    def _rebuild(self):
        prev_name = None
        if self._sets:
            idx = self.GetInt32(ID_COMBO)
            if 0 <= idx < len(self._sets):
                prev_name = self._sets[idx][SS_SET_NAME]

        self.FreeChildren(ID_COMBO)
        self._sets = _find_all_sets(c4d.documents.GetActiveDocument())

        if not self._sets:
            self.AddChild(ID_COMBO, 0, "— нет наборов —")
            self.SetString(ID_LBL_INF, "Создайте набор из текущего выделения")
            self.SetString(ID_LBL_OBJ, "")
            return

        new_idx = 0
        for i, t in enumerate(self._sets):
            name = t[SS_SET_NAME] or "Без имени"
            cnt = len(_tag_objects(t))
            self.AddChild(ID_COMBO, i, "{} ({} объектов)".format(name, cnt))
            if name == prev_name:
                new_idx = i

        self.SetInt32(ID_COMBO, new_idx)
        self._update_info()

    def _cur(self):
        idx = self.GetInt32(ID_COMBO)
        if self._sets and 0 <= idx < len(self._sets):
            return self._sets[idx]
        return None

    def _update_info(self):
        t = self._cur()
        if t is None:
            self.SetString(ID_LBL_INF, "")
            self.SetString(ID_LBL_OBJ, "")
            return
        name = t[SS_SET_NAME] or "Без имени"
        objs = _tag_objects(t)
        self.SetString(ID_LBL_INF,
            "Набор: {}  |  Объектов: {}".format(name, len(objs)))
        if objs:
            lines = []
            for o in objs:
                try:
                    lines.append("  • {} [{}]".format(
                        o.GetName(), o.GetTypeName()))
                except Exception:
                    lines.append("  • (удалён)")
            self.SetString(ID_LBL_OBJ, "\n".join(lines))
        else:
            self.SetString(ID_LBL_OBJ, "  (пусто)")

    def CoreMessage(self, kind, msg):
        if kind == c4d.EVMSG_CHANGE:
            self._rebuild()
        return True

    def Command(self, cid, msg):
        if cid == ID_COMBO:
            self._update_info()
            return True

        doc = c4d.documents.GetActiveDocument()

        if cid == ID_BTN_NEW:
            name = c4d.gui.InputDialog("Имя нового набора:", "Пользовательский набор")
            if not name:
                return True
            sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
            if not sel:
                c4d.gui.MessageDialog("Сначала выделите объекты.")
                return True
            doc.StartUndo()
            container = _ensure_container(doc)
            null = c4d.BaseObject(c4d.Onull)
            null.SetName(name)
            _set_object_icon(null, _ICON_TAG_B64)
            doc.AddUndo(c4d.UNDOTYPE_NEW, null)
            t = null.MakeTag(PLUGIN_ID_TAG)
            doc.AddUndo(c4d.UNDOTYPE_NEW, t)
            t[SS_SET_NAME] = name
            null.InsertUnder(container)
            for o in sel:
                _tag_add(t, o)
            doc.EndUndo()
            c4d.EventAdd()
            self._rebuild()
            return True

        if cid == ID_BTN_SEL:
            t = self._cur()
            if not t:
                return True
            doc.StartUndo()
            for o in doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN):
                doc.AddUndo(c4d.UNDOTYPE_BITS, o)
                o.DelBit(c4d.BIT_ACTIVE)
            for o in _tag_objects(t):
                doc.AddUndo(c4d.UNDOTYPE_BITS, o)
                o.SetBit(c4d.BIT_ACTIVE)
            doc.EndUndo()
            c4d.EventAdd()
            return True

        if cid == ID_BTN_ADD:
            t = self._cur()
            if not t:
                return True
            sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
            if not sel:
                return True
            doc.StartUndo()
            for o in sel:
                _tag_add(t, o)
            doc.EndUndo()
            c4d.EventAdd()
            self._rebuild()
            return True

        if cid == ID_BTN_REM:
            t = self._cur()
            if not t:
                return True
            sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
            if not sel:
                return True
            doc.StartUndo()
            for o in sel:
                _tag_remove(t, o)
            doc.EndUndo()
            c4d.EventAdd()
            self._rebuild()
            return True

        if cid == ID_BTN_DEL:
            t = self._cur()
            if not t:
                return True
            doc.StartUndo()
            parent = t.GetObject()
            doc.AddUndo(c4d.UNDOTYPE_DELETE, t)
            t.Remove()
            if parent:
                grandparent = parent.GetUp()
                is_auto = (grandparent is not None
                           and grandparent.GetName() == "Selection Sets"
                           and grandparent.GetType() == c4d.Onull)
                if is_auto:
                    doc.AddUndo(c4d.UNDOTYPE_DELETE, parent)
                    parent.Remove()
            doc.EndUndo()
            c4d.EventAdd()
            self._rebuild()
            return True

        if cid == ID_BTN_RNM:
            t = self._cur()
            if not t:
                return True
            old = t[SS_SET_NAME] or ""
            new = c4d.gui.InputDialog("Новое имя:", old)
            if not new or new == old:
                return True
            doc.StartUndo()
            t[SS_SET_NAME] = new
            parent = t.GetObject()
            if parent:
                grandparent = parent.GetUp()
                is_auto = (grandparent is not None
                           and grandparent.GetName() == "Selection Sets"
                           and grandparent.GetType() == c4d.Onull)
                if is_auto:
                    parent.SetName(new)
            doc.EndUndo()
            c4d.EventAdd()
            self._rebuild()
            return True

        if cid == ID_BTN_CLR:
            t = self._cur()
            if not t:
                return True
            doc.StartUndo()
            _tag_clear(t)
            doc.EndUndo()
            c4d.EventAdd()
            self._rebuild()
            return True

        return True


# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND
# ══════════════════════════════════════════════════════════════════════════════

class SelSetCmd(c4d.plugins.CommandData):

    def __init__(self):
        self._dlg = None

    def Execute(self, doc):
        if self._dlg is None:
            self._dlg = SelSetDialog()
        if self._dlg.IsOpen():
            self._dlg.Close()
        else:
            self._dlg.Open(
                dlgtype=c4d.DLG_TYPE_ASYNC,
                pluginid=PLUGIN_ID_CMD,
                defaultw=340,
                defaulth=420,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dlg is None:
            self._dlg = SelSetDialog()
        return self._dlg.Restore(PLUGIN_ID_CMD, secret)

    def GetState(self, doc):
        return c4d.CMD_ENABLED


# ══════════════════════════════════════════════════════════════════════════════
#  TAG DATA
# ══════════════════════════════════════════════════════════════════════════════

class SelSetTag(c4d.plugins.TagData):

    def Init(self, node, isload=False):
        if not isload:
            node[SS_SET_NAME] = ""
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Имя набора"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(SS_GRP_PARAMS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD)
        gid = c4d.DescID(c4d.DescLevel(SS_GRP_PARAMS, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_STRING)
        bc[c4d.DESC_NAME]    = "Имя набора"
        bc[c4d.DESC_DEFAULT] = ""
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(SS_SET_NAME, c4d.DTYPE_STRING, 0)),
            bc, gid)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED


# ══════════════════════════════════════════════════════════════════════════════
#  ICONS
# ══════════════════════════════════════════════════════════════════════════════

_ICON_CMD_B64 = (
    "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"
)

_ICON_TAG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAFOElEQVR4nO2ZTWwUZRjHf8/M7Oz2g25bEFGgIIkon9LwIYiSyAGjUS+cxIPRg0TjiYvegASvfhwMJFVumCheuXnwAFQFBCRgRYOASoi0pduW/ei88z4eZlvASHcKnW3R+W0m2cnO+84z/333eZ//PpCSkpKSkpKSkvL/RCZ2uQqaTCCTikgCUao6dzNMmLDK986X6sa9NF5sqhKpqg6XyHMBxSvUHJsHCoV89D5/mQL5uHFNHJNXZhaE4XyZp6R0M+bxqS2AqoOI5XtdS4bPCJlLWHusCGgIjzQcZ0Qb+LO0DJxYd7x7HCw+RYbZxUbZPxb7eHGOO6Fq9Pk3ZGngNHkW06/gjjNMo5+ghkJb7iqbZ3WBVc6UXuDCcCcmdJMTwQI5wKJUWMpG6WGnOuy+swhezUlFlKMDjUh+DgNYfjgJgRFEbrkEVAEEEYsGGVraCjz9zBFMRclkQhZWvuZit0GshyaRSUXAhLD88ZB5eY+A+UAPy8aXu7YAACGKi0FwCIxiwpsCqKChA45FvBBCF98rsnb1CXw/IAxdKiNZur97kpGih2QC0ASWgAgYA6hTVTiIM2wimV3GbiSCuMBIjnkdV9mw6QQZ36IjORCHDZtO0N4+iDEerms5fHgNQ9dbEN+gOGNzJHJEkUavGMRbAf9UQhQ1Hq0P9LJq1TmamorMaBni+LedzFv4Bw/O7qVUyuL7AcePr+T6XzORbIDaum+INYkvgFQXlkQnqMus2ddpai5RLmdpbiqxafNRRKBcydLUVObU6aVcOr8IaSij1kl2B7h1BQC48RJNPAFcBK1KEFrUhOCU+fXsAoqDPqvX/IiXNWAziBiyXsDP5xbQc3oRkimiAUQpOkFGc0CUjS2WWMVQbQFUhSO9AQ6WLMKyJQair1NEuVJZRuHaWtbNOUSLXKXPzIdAOWm2QqeDyuiySbqGFlBVZjQJgoMwGHNUDUaLiW59nUb24eLfNoEDasBVaM300R/MxBUwo0VPvb2DAAX2soF3ovN7KYRGGS0rD+tjNJu5lDw7lmUNuJ4hxAPDXabVScCYahHkDbNOjk3+DWKYoWmT4zV+oTExh1dj4n9b7W71qCsH4z9Xom6wgwKXOzoAWHHmDGfyHXHjmjjTzQ16WIzj8HbvV/S5LXzRtiXxnXB6uEHAJSTEZX3lJ7ovvQJqeffh9/ikZSslm0Uloc1hKtxg9I+PVuskiR5eG1mRucih5j2M4OBLwPbfuvj0xkJK+CTy+FPhBqMHd1HNgBg8yliytDPAgZa9tDtFAvXpZwYv39hBf9CII8XIEE029XaDrqOotrItd4yDrR/S5lQw5BERDrV9xIrMJYzmyEjAiwM7OGsW4jpFrHj3vxt0UKxm6cz08HHz58xyr/GEd4XXBt/i1dwR1vtnKYd5ck6RN4feoDtYgidDGFzqXxqOz125QRGweDzr9zDLu0Zo8zzq9nK09X0QZcTmyXn97B7eRlfxeTLudQJcEi2V6ukGQ2NxnGE+GHqO30fa2DdjP+1ugEoDElbwpUjX4BZ2Db2EJ30YI1DdOxOj3m7QIjhYDtrlnMps5kDfTjpLv3CyYSUKbH9oD4JDiK0mvf+oG/SIPFBjAGvK5zncuJhGC8M+iE7BL77ubhDIYqh4XlT0VwAP3LIh9OpoDafaDQqMpbkpd4VT4QaVKM0pty/7KRFkurjBtDeY9gbT3mDaG0x7g2lvMO0Npr3BtDeY9gbrSNobTHuDE3KDE9gFxFZFEA7e4b6xJ0sYkYT/f0tJSUlJSUlJSbn/+RvB84q4tZaoNQAAAABJRU5ErkJggg=="
)


def _decode_icon(b64_str):
    """Декодирует base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(b64_str)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            tmp.write(data)
            tmp.close()
            bmp.InitWith(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    except Exception:
        return None
    return bmp


ICON_CMD = _decode_icon(_ICON_CMD_B64)
ICON_TAG = _decode_icon(_ICON_TAG_B64)


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str=TAG_NAME,
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=SelSetTag,
        description="Obase",
        icon=ICON_TAG,
    )
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD,
        str=PLUGIN_NAME + " " + PLUGIN_NAME_V,
        info=0,
        icon=ICON_CMD,
        help=PLUGIN_HELP,
        dat=SelSetCmd(),
    )
