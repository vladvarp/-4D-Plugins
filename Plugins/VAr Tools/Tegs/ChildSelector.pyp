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

PLUGIN_NAME_V = "Child Selector Tag v1.1.1"
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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzY6MDMrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzY6MDMrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjk0YWMwMDAxLTkwMjUtMDQ0MC04YjFjLWU5ODg2YWIxZTRmNiIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDo5NGFjMDAwMS05MDI1LTA0NDAtOGIxYy1lOTg4NmFiMWU0ZjYiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDo5NGFjMDAwMS05MDI1LTA0NDAtOGIxYy1lOTg4NmFiMWU0ZjYiPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjk0YWMwMDAxLTkwMjUtMDQ0MC04YjFjLWU5ODg2YWIxZTRmNiIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/PvE1qIYAAAKlSURBVFiF7ZfPS1RRFMc/5840OqRBRNRC+jUaScyIrbRNrTL6AyJbRD9AoTZaRi3FhRCWuWnRIpU2RS1cSAot27YYeEpkMyolSqShixl19L13WsxM+XPU8YlBfVfv3vPO+36457z73hVVZTdldtX9bwBAVVm3DIMjTVjxSaz4JIMjTTvhK1lzEVlt7rptgJOZ8eFzH3L65COvACBXCRy3CXA6W0Ptna2hdsDBNo1emC+VP3dYMMK17DV4/8asD2BMG+o+vn/726H0hKbnvFbOJrSGGyt7JpzKngkHa9jT5d+4CTPqrtXvANdfyWGvAWDDHgCFg+uweaKcG1FXrdYZwQiYrlqt2wmAdUvw4qaW+eYZQnFJh4wGqLjRLQNeGOfcBxT1+eexgAWFKaNMAfOywMfmZg14AZDVmgAvrzKiUJBa5IwALuAUUgEEjsX4snMA0dFwee/4zLvq6SPR0GxL/Vv5lA3d6pRYNDTb0lc1fbS8d3yG6GjYC4DlPWDFF/fO+YwAiaDj6vtLd1wNPgcwMlcvF/qeFc35jALJoOMSKd2Tr/HqHnijQcCfLJaaRLHUAH5bAw1GUhhJkdLCBsCfKJaaZCaeydmW/gBcljnAxrb7se1+wPbLQgfpD4AWyHzHyngmZ1taXoLoaBi/8xoA23eFyuPLX7nfcQ2gphjYt3VL9weJwrNaXTKxGmCzGoiPoZRAPiugQVQsjZyogE1sxWs/Q/cDSSKlRVvOtWIJREPZYX4Am5S2n2rElScAGL0ndz8/XXlPfiWwYgkAImVFWHEXWJn8gUjpOQBtK/+JuEjT0IGluRpOr972VyBSmvvP2nWrcoV3tAQA8mAo5j2AmhFEw1jDs3kkB4Gx7Ci/g0kycBHVr3nlwhi+1PnsQP6fDf95gF/eBy9OJpogYgAAAABJRU5ErkJggg=="
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
        description="",
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
