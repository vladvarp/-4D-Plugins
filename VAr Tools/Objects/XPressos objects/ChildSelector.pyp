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
import os
import tempfile

# ── ID плагинов ───────────────────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068900   # CommandData — кнопка в меню
PLUGIN_ID_TAG = 1068901   # TagData     — тег

PLUGIN_NAME_V = "Child Selector Tag v1.1"
TEG_NAME      = "Child Selector Tag"
PLUGIN_HELP   = "Добавить тег выбора дочернего объекта"

# ── ID пользовательских данных (UserData) ─────────────────────────────────────
# Индексы фиксированы: создаём данные в строго определённом порядке.
UD_DROPDOWN = 1   # выпадающий список дочерних объектов
UD_NAME     = 2   # имя выбранного объекта
UD_LINK     = 3   # ссылка на выбранный объект

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

    def __init__(self):
        self._cached_names = None  # кеш имён детей для избежания лишних пересозданий

    def Init(self, node):
        # При инициализации создаём пользовательские данные
        _build_userdata(node)
        self._cached_names = None
        return True

    def _rebuild_cycle(self, tag, children):
        """
        Пересоздаёт DESC_CYCLE в UserData поле UD_DROPDOWN через SetUserDataContainer.
        Это единственный рабочий способ обновить CYCLE динамически в R26.
        Сохраняет текущий индекс выбора.
        """
        # Сохраняем текущий выбор перед пересозданием
        current_idx = tag[c4d.ID_USERDATA, UD_DROPDOWN] or 0

        cycle_bc = c4d.BaseContainer()
        if children:
            for i, child in enumerate(children):
                cycle_bc.SetString(i, child.GetName())
        else:
            cycle_bc.SetString(0, "— нет дочерних —")

        # Обновляем DESC_CYCLE через SetUserDataContainer
        for ud_id, ud_bc in tag.GetUserDataContainer():
            if ud_id[1].id == UD_DROPDOWN:
                ud_bc[c4d.DESC_CYCLE] = cycle_bc
                tag.SetUserDataContainer(ud_id, ud_bc)
                break

        # Восстанавливаем индекс (зажимаем в допустимые пределы)
        max_idx = max(0, len(children) - 1) if children else 0
        tag[c4d.ID_USERDATA, UD_DROPDOWN] = min(current_idx, max_idx)

    def Execute(self, tag, doc, op, bt, priority, flags):
        """
        Обновляем CYCLE и поля Имя/Связь при каждом тике.
        CYCLE пересоздаётся только при изменении состава дочерних объектов.
        """
        obj = tag.GetObject()
        if obj is None:
            return c4d.EXECUTIONRESULT_OK

        children = _get_direct_children(obj)
        names = [c.GetName() for c in children]

        # Пересоздаём CYCLE только если состав детей изменился
        if names != self._cached_names:
            self._cached_names = names
            self._rebuild_cycle(tag, children)
            c4d.EventAdd()

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

# ── Иконки (b64, 32×32 PNG) ───────────────────────────────────────────────────
# Иконка кнопки — синий квадрат с буквой C
_ICON_PLG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAABoElEQVR4nGPU0NBgoCVgoqnpDAwMLJhC"
    "169fp8RETU1NZC66Dyg0HdMERuQ4gMgxVt6gxIL/7RoMSP5A+IAqpsNNgPuDibqmY9oxEKkICjo0cUpB"
    "QAUsMjFVViDiGbcFDAz////HJcXIyIii8kQKQspiDrIUFYLoxAmc7mDA7wPCRgcQLmbI9MGJE/8hplts"
    "uGFhwYhHJUU+gAO0cKeCBRYWjIigr8BXupAfyRYbbjAQEQ34fICWFskDuC3A63EIsNhw40SAxokADfR4"
    "JjKjEQ9omNEgMXGSYTYuBVTIyRYWjOYMqTS0AD8YrBkNBdAooxEJhr4FiGYLvN4X5mKudxbxUueR4Wd5"
    "/fXvrFMfmve9YWBgyLEULLYVkuZj+fb7/+03v0ynPsBlKHLLBRHJmpqa169f/9+ucevNLwVB1rhVz7fd"
    "/KInwe6sws3AwKAmwjbZT3zemY+5m16qirDWOokQYzoDWsOLgRotOwbU1iN6HEyYMIGKpjNg5oNnz54x"
    "MDCsXbu2pqYGUzM7O7uOjk5OTo6FhUVtbe2aNWsI2gcAbDeLOb51KUEAAAAASUVORK5CYII="
)

# Иконка тега — оранжевый квадрат с буквой T
_ICON_TAG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAABh0lEQVR4nNVWv0uFUBg99xFIUFBEUy0t"
    "8R48gqDwBkLQ2F9Qe9HiZltKQ2uBUDRUY0ugY2uThG9tcXhTDS4t0fCWhtvgS++74lX0SnU2/a7neL4f"
    "+pFut4s20WmVHcBU/lYURU0Ye70efyk6aMieZyB8DcaxC9JIwWLgfGQO1LD/MKQ+OorZcxq/0UUJyHHJ"
    "k+y88GQakgkAYIwVypOJZLLwIAvROz6kIEVhWPgekDsoxcCQUSeo6SAMWcKuB4RSWe81cpBCyLsCAUpJ"
    "mnq+Z/KoX2Q9IKhQBpkDoRfroVBAbjyBHpCBwQYGE+pcddCqo8VBG1cCt0UHFEwypUTHYYsCcvzVQePR"
    "1qBVxP8XyNaW7L8/vYCtU6zsYnYZo3e83CA8A4B1ExsWZpbwNcLHEPebhazc5pI5GG8yFsP+M9aOEJzg"
    "ehGPe0i+SPOr2LnE2xOu5vCwjc/XKuwQFi+o2OwwuT2KNXBdVyE78nMQxzEA3/dt284/rGlav983TZNS"
    "6jiO53mlet/UC3rDfQqS2gAAAABJRU5ErkJggg=="
)

def _make_icon_teg():
    """Декодирует встроенный base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(_ICON_TAG_B64.replace(" ", ""))
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

ICON_TEG = _make_icon_teg()
ICON_PLG = _make_icon_plg()

# ── Регистрация ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Регистрация тега
    c4d.plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str=TEG_NAME,
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=ChildSelectorTag,
        description="",
        icon=ICON_TEG
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
