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
PLUGIN_NAME_V = "v1.3"
TAG_NAME      = "Selection Set Tag"
PLUGIN_HELP   = "Управление наборами выделения объектов"

UD_SET_NAME = 1
OBJ_PREFIX  = "Obj_"
MAX_OBJECTS = 256

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
                prev_name = self._sets[idx][c4d.ID_USERDATA, UD_SET_NAME]

        self.FreeChildren(ID_COMBO)
        self._sets = _find_all_sets(c4d.documents.GetActiveDocument())

        if not self._sets:
            self.AddChild(ID_COMBO, 0, "— нет наборов —")
            self.SetString(ID_LBL_INF, "Создайте набор из текущего выделения")
            self.SetString(ID_LBL_OBJ, "")
            return

        new_idx = 0
        for i, t in enumerate(self._sets):
            name = t[c4d.ID_USERDATA, UD_SET_NAME] or "Без имени"
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
        name = t[c4d.ID_USERDATA, UD_SET_NAME] or "Без имени"
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
            t[c4d.ID_USERDATA, UD_SET_NAME] = name
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
            old = t[c4d.ID_USERDATA, UD_SET_NAME] or ""
            new = c4d.gui.InputDialog("Новое имя:", old)
            if not new or new == old:
                return True
            doc.StartUndo()
            t[c4d.ID_USERDATA, UD_SET_NAME] = new
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

    def Init(self, node):
        for _, bc in node.GetUserDataContainer():
            if bc.GetString(c4d.DESC_NAME) == "Set Name":
                return True
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_STRING)
        bc.SetString(c4d.DESC_NAME, "Set Name")
        bc.SetString(c4d.DESC_SHORT_NAME, "Name")
        bc.SetString(c4d.DESC_DEFAULT, "")
        node.AddUserData(bc)
        return True


# ══════════════════════════════════════════════════════════════════════════════
#  ICONS
# ══════════════════════════════════════════════════════════════════════════════

_ICON_CMD_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAcklEQVR42mNgGAUD"
    "DBhxyly685+qNumpMBKvGM3y/z0a/2GYbAfg8BATIX3ollLkCCyAhSLdl+5UEB"
    "H0HbRzAAHDiQEEo4Cx5AYjPj5dooDalg6BbDhaEI0WRKMF0WhBNFoQjRZEowXR"
    "aEE0WhCNAjoCAFg9Yf8XukC4AAAAAElFTkSuQmCC"
)

_ICON_TAG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAn0lEQVR42mNgGAWj"
    "YIABI4bIpTv/qWa6ngojaRqoaTlZZlHTAUSaxzS4UgS1Q4AIM0dACBAwl4VMA3"
    "sIZL+SwRUCeMzGGwL/ezTgmhhLbjDSwl1MxFiOjU9WqYglFMhNAyk4LJlDqlEs"
    "ZPpmDs2jAD3OKU4Dl+78x1Y54Q0BWiU8aqSBCjzR00Gs7wdFSThaGY02SAa8TT"
    "jIWsWjYCQCAFZNVo0tVE1yAAAAAElFTkSuQmCC"
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
        description="",
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
