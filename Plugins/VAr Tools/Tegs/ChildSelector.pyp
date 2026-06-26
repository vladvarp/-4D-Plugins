# coding: utf-8
"""
ChildSelector.pyp
-----------------
Кнопка плагина: вешает тег ChildSelectorTag на выбранный объект.
Тег добавляет пользовательские данные:
  - Выпадающий список  — прямые дети объекта (обновляется динамически)
  - Имя               — имя выбранного дочернего объекта (авто)
  - Связь             — ссылка на выбранный дочерний объект (авто)
"""

import c4d # type: ignore
import base64
import os
import tempfile

# ── ID плагинов ───────────────────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068900   # CommandData — кнопка в меню
PLUGIN_ID_TAG = 1068901   # TagData     — тег

PLUGIN_NAME_V = "Child Selector Tag v1.2.1"
TEG_NAME      = "Child Selector Tag"
PLUGIN_HELP   = "Добавить тег выбора дочернего объекта"

# ── ID пользовательских данных (UserData) ─────────────────────────────────────
UD_DROPDOWN = 1
UD_NAME     = 2
UD_LINK     = 3

# Description-based parameter IDs
CS_GRP_PARAMS = 2000
CS_DROPDOWN   = 2001
CS_NAME       = 2002
CS_LINK       = 2003

def _get_direct_children(obj):
    """Возвращает список прямых дочерних объектов (depth=1)."""
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


class ChildSelectorTag(c4d.plugins.TagData):

    def __init__(self):
        self._cached_names = None

    def Init(self, node, isload=False):
        if not isload:
            node[CS_DROPDOWN] = 0
            node[CS_NAME] = ""
            node[CS_LINK] = None
        self._cached_names = None
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CS_GRP_PARAMS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD)
        gid = c4d.DescID(c4d.DescLevel(CS_GRP_PARAMS, c4d.DTYPE_GROUP, 0))

        children = _get_direct_children(node.GetObject()) if node.GetObject() else []
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Объект"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = 0
        cyc = c4d.BaseContainer()
        if children:
            for i, child in enumerate(children):
                cyc[i] = child.GetName()
        else:
            cyc[0] = "— нет дочерних —"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CS_DROPDOWN, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_STRING)
        bc[c4d.DESC_NAME]    = "Имя"
        bc[c4d.DESC_EDITABLE] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CS_NAME, c4d.DTYPE_STRING, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BASELISTLINK)
        bc[c4d.DESC_NAME]      = "Связь"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_LINKBOX
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CS_LINK, c4d.DTYPE_BASELISTLINK, 0)),
            bc, gid)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Execute(self, tag, doc, op, bt, priority, flags):
        obj = tag.GetObject()
        if obj is None:
            return c4d.EXECUTIONRESULT_OK

        children = _get_direct_children(obj)
        names = [c.GetName() for c in children]

        if names != self._cached_names:
            self._cached_names = names
            c4d.EventAdd()

        idx = tag[CS_DROPDOWN]

        if children and idx is not None and 0 <= idx < len(children):
            selected = children[idx]
            tag[CS_NAME] = selected.GetName()
            tag[CS_LINK] = selected
        else:
            tag[CS_NAME] = ""
            tag[CS_LINK] = None

        return c4d.EXECUTIONRESULT_OK

    def Message(self, node, type, data):
        if type == c4d.MSG_DESCRIPTION_COMMAND:
            c4d.EventAdd()
        return True


# ── CommandData ───────────────────────────────────────────────────────────────

class ChildSelectorCmd(c4d.plugins.CommandData):

    def Execute(self, doc):
        obj = doc.GetActiveObject()
        if obj is None:
            c4d.gui.MessageDialog("Выберите объект для добавления тега.")
            return False

        doc.StartUndo()

        # Создаём тег — Init внутри создаст пользовательские данные
        tag = obj.MakeTag(PLUGIN_ID_TAG)
        tag.SetName("Child Selector")
        doc.AddUndo(c4d.UNDOTYPE_NEW, tag)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        # Кнопка активна только если есть выбранный объект
        if doc.GetActiveObject():
            return c4d.CMD_ENABLED
        return 0

# ── Иконки (b64, 32×32 PNG) ───────────────────────────────────────────────────
# Иконка кнопки — синий квадрат с буквой C
_ICON_PLG_B64 = (
    "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"
)

def _make_icon_plg():
    """Декодирует встроенный base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(_ICON_PLG_B64.replace(" ", ""))
        fd, tmp = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, data)
            os.close(fd)
            bmp.InitWith(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return None
    return bmp    

ICON_PLG = _make_icon_plg()

# ── Регистрация ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Регистрация тега
    c4d.plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str=TEG_NAME,
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=ChildSelectorTag,
        description="Obase",
        icon=ICON_PLG
    )

    # Регистрация кнопки
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD,
        str=PLUGIN_NAME_V,
        info=0,
        icon=ICON_PLG,
        help=PLUGIN_HELP,
        dat=ChildSelectorCmd()
    )
