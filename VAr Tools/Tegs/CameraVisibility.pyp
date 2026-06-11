# coding: utf-8
"""
CameraVisibility.pyp
--------------------
Кнопка плагина: вешает тег CameraVisibilityTag на выбранный объект.
Тег управляет видимостью объекта (вьюпорт + рендер) в зависимости от
активной камеры сцены (Stage-объект).

Пользовательские данные:
  - Список скрытия  — камеры, при которых объект скрыт (OFF)
  - Список показа   — камеры, при которых объект виден (ON)

Поведение:
  - Активная камера есть в списке скрытия  → видимость OFF
  - Активная камера есть в списке показа   → видимость ON
  - Активной камеры нет ни в одном списке  → видимость «не определено» (-1)
  - Одна и та же камера в обоих списках    → запрещено (валидация при добавлении)
"""

import c4d
import base64
import os
import tempfile

# ── ID плагинов ───────────────────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068903   # CommandData — кнопка в меню
PLUGIN_ID_TAG = 1068904   # TagData     — тег

PLUGIN_NAME_V = "Camera Visibility Tag v1.0"
TAG_NAME      = "Camera Visibility Tag"
PLUGIN_HELP   = "Управление видимостью объекта по активной камере сцены"

# ── ID пользовательских данных ────────────────────────────────────────────────
# Группа-заголовок «Скрыть при камере»
UD_GROUP_HIDE   = 1
# Слоты для камер скрытия (до 16 камер)
UD_HIDE_START   = 2
UD_HIDE_END     = 17   # включительно, слоты 2..17

# Группа-заголовок «Показать при камере»
UD_GROUP_SHOW   = 18
# Слоты для камер показа (до 16 камер)
UD_SHOW_START   = 19
UD_SHOW_END     = 34   # включительно, слоты 19..34

MAX_SLOTS = 16   # максимум камер в каждом списке


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _get_stage_camera(doc):
    """
    Возвращает активную камеру сцены через Stage-объект.
    Stage хранит камеру в параметре STAGE_CAMERA.
    Возвращает объект камеры или None.
    """
    stage = doc.GetFirstObject()
    while stage:
        if stage.GetType() == c4d.Ostage:
            cam = stage[c4d.STAGE_CAMERA]
            return cam
        stage = stage.GetNext()
    return None


def _build_userdata(tag):
    """
    Создаёт структуру пользовательских данных на теге:
      - Группа «Скрыть при камере» с MAX_SLOTS слотами LinkBox
      - Группа «Показать при камере» с MAX_SLOTS слотами LinkBox

    Структура создаётся один раз при Init; если данные уже есть — пропускаем.
    Возвращает True при успехе.
    """
    ud = tag.GetUserDataContainer()
    # Ожидаем 2 группы + MAX_SLOTS*2 слотов = 2 + 32 = 34 записи
    if ud and len(ud) >= (2 + MAX_SLOTS * 2):
        return True

    # ── Группа «Скрыть при камере» ────────────────────────────────────────────
    bc_grp_hide = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc_grp_hide[c4d.DESC_NAME]      = "Скрыть при камере"
    bc_grp_hide[c4d.DESC_SHORT_NAME]= "Скрыть"
    bc_grp_hide[c4d.DESC_COLUMNS]   = 1
    bc_grp_hide[c4d.DESC_DEFAULT]   = 1
    tag.AddUserData(bc_grp_hide)   # → UD_GROUP_HIDE = 1

    # Слоты скрытия
    for i in range(MAX_SLOTS):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc[c4d.DESC_NAME]       = "Камера {:02d}".format(i + 1)
        bc[c4d.DESC_SHORT_NAME] = "Кам {:02d}".format(i + 1)
        bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_LINKBOX
        bc[c4d.DESC_PARENTGROUP]= c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA),
                                              c4d.DescLevel(UD_GROUP_HIDE))
        tag.AddUserData(bc)   # → UD_HIDE_START + i

    # ── Группа «Показать при камере» ──────────────────────────────────────────
    bc_grp_show = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc_grp_show[c4d.DESC_NAME]      = "Показать при камере"
    bc_grp_show[c4d.DESC_SHORT_NAME]= "Показать"
    bc_grp_show[c4d.DESC_COLUMNS]   = 1
    bc_grp_show[c4d.DESC_DEFAULT]   = 1
    tag.AddUserData(bc_grp_show)   # → UD_GROUP_SHOW = 18

    # Слоты показа
    for i in range(MAX_SLOTS):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc[c4d.DESC_NAME]       = "Камера {:02d}".format(i + 1)
        bc[c4d.DESC_SHORT_NAME] = "Кам {:02d}".format(i + 1)
        bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_LINKBOX
        bc[c4d.DESC_PARENTGROUP]= c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA),
                                              c4d.DescLevel(UD_GROUP_SHOW))
        tag.AddUserData(bc)   # → UD_SHOW_START + i

    return True


def _get_cameras_from_slots(tag, start_ud, count):
    """
    Читает camera-ссылки из слотов UserData начиная с индекса start_ud.
    Возвращает set уникальных объектов (None-значения пропускаются).
    """
    cams = set()
    for i in range(count):
        cam = tag[c4d.ID_USERDATA, start_ud + i]
        if cam is not None:
            cams.add(cam)
    return cams


def _validate_no_overlap(tag):
    """
    Проверяет, что одна и та же камера не находится одновременно
    в списке скрытия и в списке показа.
    Если пересечение есть — очищает конфликтный слот в списке показа
    и выводит предупреждение.
    Возвращает True если всё чисто, False если было исправление.
    """
    hide_cams = _get_cameras_from_slots(tag, UD_HIDE_START, MAX_SLOTS)
    conflict_found = False

    for i in range(MAX_SLOTS):
        cam = tag[c4d.ID_USERDATA, UD_SHOW_START + i]
        if cam is not None and cam in hide_cams:
            # Очищаем конфликтный слот в списке показа
            tag[c4d.ID_USERDATA, UD_SHOW_START + i] = None
            conflict_found = True

    if conflict_found:
        c4d.gui.MessageDialog(
            "Одна или несколько камер одновременно находились в списке\n"
            "«Скрыть» и «Показать». Конфликтные записи удалены из списка «Показать».\n\n"
            "Одна камера может быть только в одном списке."
        )
        c4d.EventAdd()
        return False

    return True


def _set_visibility(obj, mode):
    """
    Устанавливает видимость объекта для вьюпорта и рендера.
    mode:
      c4d.MODE_ON   (1)  → видим
      c4d.MODE_OFF  (2)  → скрыт
      c4d.MODE_UNDEF(0)  → не определено (наследует от родителя)
    """
    obj[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = mode
    obj[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = mode


# ── TagData ───────────────────────────────────────────────────────────────────

class CameraVisibilityTag(c4d.plugins.TagData):

    def __init__(self):
        self._last_cam_ptr = -1   # кеш указателя на последнюю активную камеру

    def Init(self, node):
        _build_userdata(node)
        self._last_cam_ptr = -1
        return True

    def Execute(self, tag, doc, op, bt, priority, flags):
        obj = tag.GetObject()
        if obj is None:
            return c4d.EXECUTIONRESULT_OK

        active_cam = _get_stage_camera(doc)

        # Кеш: избегаем лишней работы если камера не изменилась
        cam_ptr = id(active_cam) if active_cam is not None else 0
        if cam_ptr == self._last_cam_ptr:
            return c4d.EXECUTIONRESULT_OK
        self._last_cam_ptr = cam_ptr

        if active_cam is None:
            # Нет активной камеры — не определено
            _set_visibility(obj, c4d.MODE_UNDEF)
            return c4d.EXECUTIONRESULT_OK

        # Читаем оба списка
        hide_cams = _get_cameras_from_slots(tag, UD_HIDE_START, MAX_SLOTS)
        show_cams = _get_cameras_from_slots(tag, UD_SHOW_START, MAX_SLOTS)

        if active_cam in hide_cams:
            _set_visibility(obj, c4d.MODE_OFF)
        elif active_cam in show_cams:
            _set_visibility(obj, c4d.MODE_ON)
        else:
            # Активная камера не в списках — не определено
            _set_visibility(obj, c4d.MODE_UNDEF)

        return c4d.EXECUTIONRESULT_OK

    def Message(self, node, msg_type, data):
        """
        Отслеживаем изменение UserData для валидации пересечений.
        MSG_DESCRIPTION_POSTSETVALUE срабатывает после того как пользователь
        изменил значение поля — это лучший момент для проверки.
        """
        if msg_type == c4d.MSG_DESCRIPTION_POSTSETVALUE:
            _validate_no_overlap(node)
            # Сбрасываем кеш чтобы Execute пересчитал видимость
            self._last_cam_ptr = -1

        return True


# ── CommandData ───────────────────────────────────────────────────────────────

class CameraVisibilityCmd(c4d.plugins.CommandData):

    def Execute(self, doc):
        obj = doc.GetActiveObject()
        if obj is None:
            c4d.gui.MessageDialog("Выберите объект для добавления тега.")
            return False

        doc.StartUndo()

        tag = obj.MakeTag(PLUGIN_ID_TAG)
        tag.SetName("Camera Visibility")
        doc.AddUndo(c4d.UNDOTYPE_NEW, tag)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        if doc.GetActiveObject():
            return c4d.CMD_ENABLED
        return 0


# ── Иконки (b64, 32×32 PNG) ───────────────────────────────────────────────────

# Иконка кнопки — синий квадрат с буквой C (переиспользуем стиль ChildSelector)
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

# Иконка тега — зелёный квадрат с буквой V (visibility)
_ICON_TAG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAABh0lEQVR4nNVWv0uFUBg995FAUFBEUy0t"
    "8R48gqDwBkLQ2F9Qe9HiZltKQ2uBUDRUY0ugY2uThG9tcXhTDS4t0fCWhtvgS++74lX0SnU2/a7neL4f"
    "+pFut4s20WmVHcBU/lYURU0Ye70efyk6aMieZyB8DcaxC9JIwWLgfGQO1LD/MKQ+OorZcxq/0UUJyHHJ"
    "k+y88GQakgkAYIwVypOJZLLwIAvROz6kIEVhWPgekDsoxcCQUSeo6SAMWcKuB4RSWe81cpBCyLsCAUpJ"
    "mnq+Z/KoX2Q9IKhQBpkDoRfroVBAbjyBHpCBwQYGE+pcddCqo8VBG1cCt0UHFEwypUTHYYsCcvzVQePR"
    "1qBVxP8XyNaW7L8/vYCtU6zsYnYZo3e83CA8A4B1ExsWZpbwNcLHEPebhazc5pI5GG8yFsP+M9aOEJzg"
    "ehGPe0i+SPOr2LnE2xOu5vCwjc/XKuwQFi+o2OwwuT2KNXBdVyE78nMQxzEA3/dt284/rGlav983TZNS"
    "6jiO53mlet/UC3rDfQqS2gAAAABJRU5ErkJggg=="
)


def _make_icon_tag():
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


ICON_TAG = _make_icon_tag()
ICON_PLG = _make_icon_plg()


# ── Регистрация ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Регистрация тега
    c4d.plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str=TAG_NAME,
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=CameraVisibilityTag,
        description="",
        icon=ICON_TAG
    )

    # Регистрация кнопки
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD,
        str=PLUGIN_NAME_V,
        info=0,
        icon=ICON_PLG,
        help=PLUGIN_HELP,
        dat=CameraVisibilityCmd()
    )
