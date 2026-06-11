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

import c4d
import base64

# ── ID плагинов ───────────────────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068900   # CommandData — кнопка в меню
PLUGIN_ID_TAG = 1068901   # TagData     — тег

# ── ID пользовательских данных (UserData) ─────────────────────────────────────
# Индексы фиксированы: создаём данные в строго определённом порядке.
UD_DROPDOWN = 1   # выпадающий список дочерних объектов
UD_NAME     = 2   # имя выбранного объекта
UD_LINK     = 3   # ссылка на выбранный объект

# ── Иконки (b64, 32×32 PNG) ───────────────────────────────────────────────────
# Иконка кнопки — синий квадрат с буквой C
_ICON_CMD_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAyklEQVRYw+2WwQ2D"
    "MBAE1xEFpAN6oAF6oAF6SAdQAutBCaQDSiAd0AEd0AEdQAkpgfUiRUJC4mzn6"
    "Yt0u5b3xvYBAAAAAAAAAAAAAAAAAACg0jRNOefceymlNAzDGcdxrLWuta611tre"
    "WmulSimllHPOOeecUkoppZRSSil1OI6jc84ppZRSSimllFJKKaWUUkqp0+M4Dq"
    "WUUkoppZRSSql/3vf9TimllFJKKaWUUkop5b7v+1JKKaWUUkoppZRS6t/3fU8p"
    "pZRSSimllFJKKeW+7/tSSimllFJKKaWUUuoBkXMnJAAAAABJRU5ErkJggg=="
)

# Иконка тега — оранжевый квадрат с буквой T
_ICON_TAG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAy0lEQVRYw+2WwQ2D"
    "MBAE1xEFpAN6oAF6oAF6SAeuB+ugA9IBJbgO6IAO6IAOKCEloF4kJCQkzna+vki"
    "3a3lvbB8AAAAAAAAAAAAAAAAAAACA0jRNOefce+mcc/M8r2Mcx7bWuta211prpZ"
    "RSSimllHPOOeecUkoppZRSSil1OI6jc84ppZRSSimllFJKKaWUUkqp0+M4DqWU"
    "UkoppZRSSql/3vf9TimllFJKKaWUUkop5b7v+1JKKaWUUkoppZRS6t/3fU8ppZ"
    "RSSimllFJKKeW+7/tSSimllFJKKaWUUuoBJa8nJQAAAABJRU5ErkJggg=="
)


def _make_icon(b64_str):
    """Декодирует b64 PNG и возвращает BaseBitmap для иконки плагина."""
    import tempfile, os
    data = base64.b64decode(b64_str)
    # В R26 BaseBitmap находится в c4d.bitmaps
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.Init(32, 32, 32)
    # Записываем через временный файл — единственный надёжный способ в C4D Python API
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(data)
    tmp.close()
    bmp.InitWith(tmp.name)
    os.unlink(tmp.name)
    return bmp


def _get_direct_children(obj):
    """Возвращает список прямых дочерних объектов (depth=1)."""
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


def _build_userdata(tag):
    """
    Создаёт три поля пользовательских данных на теге если их ещё нет.
    Порядок важен: UD_DROPDOWN=1, UD_NAME=2, UD_LINK=3.
    Возвращает True если данные созданы или уже существуют.
    """
    ud = tag.GetUserDataContainer()
    if ud and len(ud) >= 3:
        return True  # данные уже созданы

    # ── 1. Выпадающий список ──────────────────────────────────────────────────
    bc_drop = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc_drop[c4d.DESC_NAME]      = "Объект"
    bc_drop[c4d.DESC_SHORT_NAME]= "Объект"
    bc_drop[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
    bc_drop[c4d.DESC_DEFAULT]   = 0
    cycle_bc = c4d.BaseContainer()
    cycle_bc.SetString(0, "— нет дочерних —")
    bc_drop[c4d.DESC_CYCLE] = cycle_bc
    tag.AddUserData(bc_drop)

    # ── 2. Имя ────────────────────────────────────────────────────────────────
    bc_name = c4d.GetCustomDatatypeDefault(c4d.DTYPE_STRING)
    bc_name[c4d.DESC_NAME]      = "Имя"
    bc_name[c4d.DESC_SHORT_NAME]= "Имя"
    bc_name[c4d.DESC_DEFAULT]   = ""
    bc_name[c4d.DESC_EDITABLE]  = False   # только для чтения
    tag.AddUserData(bc_name)

    # ── 3. Связь ──────────────────────────────────────────────────────────────
    bc_link = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
    bc_link[c4d.DESC_NAME]      = "Связь"
    bc_link[c4d.DESC_SHORT_NAME]= "Связь"
    bc_link[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_LINKBOX
    tag.AddUserData(bc_link)

    return True


# ── TagData ───────────────────────────────────────────────────────────────────

class ChildSelectorTag(c4d.plugins.TagData):

    def Init(self, node):
        # При инициализации создаём пользовательские данные
        _build_userdata(node)
        return True

    def GetDDescription(self, node, description, flags):
        """
        Динамически перестраиваем список дочерних объектов в выпадающем меню
        каждый раз когда C4D запрашивает описание тега (открытие AM, смена выделения).
        """
        # Для тегов с UserData грузим базовое описание через "tbaselist2d"
        if not description.LoadDescription("tbaselist2d"):
            return False

        obj = node.GetObject()
        if obj is None:
            return True, flags | c4d.DESCFLAGS_DESC_LOADED

        children = _get_direct_children(obj)

        # Формируем BaseContainer для CYCLE с актуальным списком детей
        cycle_bc = c4d.BaseContainer()
        if children:
            for i, child in enumerate(children):
                cycle_bc.SetString(i, child.GetName())
        else:
            cycle_bc.SetString(0, "— нет дочерних —")

        # DescID для UserData поля UD_DROPDOWN
        ud_id = c4d.DescID(
            c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
            c4d.DescLevel(UD_DROPDOWN, c4d.DTYPE_LONG, 0)
        )

        # Получаем текущий BaseContainer параметра, обновляем CYCLE, записываем обратно
        bc = description.GetParameterI(ud_id, None)
        if bc is not None:
            bc[c4d.DESC_CYCLE] = cycle_bc
            description.SetParameter(ud_id, bc, c4d.DESCFLAGS_DESC_SET)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Execute(self, tag, doc, op, bt, priority, flags):
        """
        Обновляем поля Имя и Связь при каждом тике —
        синхронизируем с текущим выбором в выпадающем списке.
        """
        obj = tag.GetObject()
        if obj is None:
            return c4d.EXECUTIONRESULT_OK

        children = _get_direct_children(obj)
        idx = tag[c4d.ID_USERDATA, UD_DROPDOWN]

        if children and idx is not None and 0 <= idx < len(children):
            selected = children[idx]
            # Авто-обновление имени и ссылки
            tag[c4d.ID_USERDATA, UD_NAME] = selected.GetName()
            tag[c4d.ID_USERDATA, UD_LINK] = selected
        else:
            tag[c4d.ID_USERDATA, UD_NAME] = ""
            tag[c4d.ID_USERDATA, UD_LINK] = None

        return c4d.EXECUTIONRESULT_OK

    def Message(self, node, type, data):
        """Реагируем на изменение пользовательских данных — обновляем AM."""
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


# ── Регистрация ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Иконка кнопки
    cmd_icon = _make_icon(_ICON_CMD_B64)

    # Иконка тега
    tag_icon = _make_icon(_ICON_TAG_B64)

    # Регистрация тега
    c4d.plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str="Child Selector Tag",
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=ChildSelectorTag,
        description="",
        icon=tag_icon
    )

    # Регистрация кнопки
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD,
        str="Child Selector",
        info=0,
        icon=cmd_icon,
        help="Добавить тег выбора дочернего объекта",
        dat=ChildSelectorCmd()
    )
