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

import c4d # type: ignore
import base64
import os
import tempfile

# ── ID плагинов ───────────────────────────────────────────────────────────────
PLUGIN_ID_CMD = 1068903   # CommandData — кнопка в меню
PLUGIN_ID_TAG = 1068904   # TagData     — тег

PLUGIN_NAME_V = "Camera Visibility Tag v1.4.1"
TAG_NAME      = "Camera Visibility Tag"
PLUGIN_HELP   = "Управление видимостью объекта по активной камере сцены"

# ── ID пользовательских данных ────────────────────────────────────────────────
UD_HIDE = 1
UD_SHOW = 2
UD_WARN = 3

# Description-based parameter IDs
CV_GRP_PARAMS = 2000
CV_HIDE       = 2001
CV_SHOW       = 2002
CV_WARN       = 2003


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _get_stage_camera(doc):
    """
    Возвращает активную камеру сцены через активный BaseDraw вьюпорта.
    BaseDraw.GetSceneCamera(doc) возвращает камеру, назначенную в данном
    вьюпорте (в т.ч. через Stage), либо None если активна редакторная камера.
    Это единственный надёжный способ получить «текущую» камеру в C4D Python SDK.
    Старый подход (поиск Ostage по сцене) не работал, потому что Stage может
    отсутствовать, а GetFirstObject() обходит только первый уровень иерархии.
    """
    bd = doc.GetActiveBaseDraw()
    if bd is None:
        return None
    return bd.GetSceneCamera(doc)


def _set_visibility(obj, mode):
    obj[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = mode
    obj[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = mode


def _get_cameras_from_list(tag, doc, desc_id):
    cams = []
    inexclude = tag[desc_id]
    if not isinstance(inexclude, c4d.InExcludeData):
        return cams
    count = inexclude.GetObjectCount()
    for i in range(count):
        obj = inexclude.ObjectFromIndex(doc, i)
        if obj is not None:
            cams.append(obj)
    return cams


def _validate_no_overlap(tag, doc):
    hide_cams = _get_cameras_from_list(tag, doc, CV_HIDE)
    show_cams = _get_cameras_from_list(tag, doc, CV_SHOW)

    overlap = [h for h in hide_cams if any(h == s for s in show_cams)]
    if overlap:
        names = ", ".join(o.GetName() for o in overlap)
        tag[CV_WARN] = (
            "⚠ Конфликт! Камер{} в обоих списках: {}".format(
                "а" if len(overlap) == 1 else "ы", names
            )
        )
        return False

    tag[CV_WARN] = ""
    return True


# ── TagData ───────────────────────────────────────────────────────────────────

class CameraVisibilityTag(c4d.plugins.TagData):

    def Init(self, node, isload=False):
        if not isload:
            node[CV_HIDE] = c4d.InExcludeData()
            node[CV_SHOW] = c4d.InExcludeData()
            node[CV_WARN] = ""
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CV_GRP_PARAMS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD)
        gid = c4d.DescID(c4d.DescLevel(CV_GRP_PARAMS, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]    = "Скрыть при камере"
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_OFF
        bc[c4d.DESC_EDITABLE] = True
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CV_HIDE, c4d.CUSTOMDATATYPE_INEXCLUDE_LIST, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]    = "Показать при камере"
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_OFF
        bc[c4d.DESC_EDITABLE] = True
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CV_SHOW, c4d.CUSTOMDATATYPE_INEXCLUDE_LIST, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_STRING)
        bc[c4d.DESC_NAME]    = "⚠ Конфликт камер"
        bc[c4d.DESC_EDITABLE] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CV_WARN, c4d.DTYPE_STRING, 0)),
            bc, gid)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def GetDirty(self, tag, doc):
        cam = _get_stage_camera(doc)
        if cam is not None:
            return cam.GetDirty(c4d.DIRTYFLAGS_ALL) + id(cam)
        return 0

    def Execute(self, tag, doc, op, bt, priority, flags):
        obj = tag.GetObject()
        if obj is None:
            return c4d.EXECUTIONRESULT_OK

        active_cam = _get_stage_camera(doc)

        if active_cam is None:
            _set_visibility(obj, c4d.OBJECT_UNDEF)
            return c4d.EXECUTIONRESULT_OK

        hide_cams = _get_cameras_from_list(tag, doc, CV_HIDE)
        show_cams = _get_cameras_from_list(tag, doc, CV_SHOW)

        if active_cam in hide_cams:
            _set_visibility(obj, c4d.OBJECT_OFF)
        elif active_cam in show_cams:
            _set_visibility(obj, c4d.OBJECT_ON)
        else:
            _set_visibility(obj, c4d.OBJECT_UNDEF)

        return c4d.EXECUTIONRESULT_OK

    def Message(self, node, msg_type, data):
        if msg_type == c4d.MSG_DESCRIPTION_POSTSETPARAMETER:
            _validate_no_overlap(node, c4d.documents.GetActiveDocument())
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

# Иконка кнопки — камера + знак «+» (добавить тег на объект)
_ICON_TAG = (
    "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"
)

def _make_icon():
    """Декодирует встроенный base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(_ICON_TAG.replace(" ", ""))
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


ICON_PLG = _make_icon()


# ── Регистрация ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Регистрация тега
    c4d.plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str=TAG_NAME,
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=CameraVisibilityTag,
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
        dat=CameraVisibilityCmd()
    )
