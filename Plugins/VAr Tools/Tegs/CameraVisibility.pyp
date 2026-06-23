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

PLUGIN_NAME_V = "Camera Visibility Tag v1.4"
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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6Mzc6NDArMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6Mzc6NDArMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjU4YzYzM2U3LWVmMmEtMGM0MC05NzM4LTBhZmNiZGI4ZjNiYSIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDo1OGM2MzNlNy1lZjJhLTBjNDAtOTczOC0wYWZjYmRiOGYzYmEiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDo1OGM2MzNlNy1lZjJhLTBjNDAtOTczOC0wYWZjYmRiOGYzYmEiPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjU4YzYzM2U3LWVmMmEtMGM0MC05NzM4LTBhZmNiZGI4ZjNiYSIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/Pg8qzoEAAAMjSURBVFiF7ZdLaFRnFMd/585MEqPR0VqLYmNJJhpFr4sxxoQuXLqwCF2MVBBduKigOLQ+UapRio+AzKIFwVrEiouJi6CImxKC4qO+0EkaJiYZNYqPbJzERzIZ5x4XITCTySR3Mkq09Ozux/f/n9+95zvf/T5RVcYzjHHN/j/AJw0gdUyQfyP7BPLGBYDytoNYupd7kYPZmko4XGF7bnIbSmtrGXFnAypfoIDgBN5llltdvC6o1qrZTwEk9OAoktgE4kJ1pZqeC6MBOFOe4s4GlNlALwIjJweQOUzsvyihjqsIGwaAjQQoqPHVaMnTAVSnAm90UekkO2Jp6oiBmggmEEPkAAmeYHDCjh5y7gJxIYDD2qmLSgt0Ycn+bB1yBFAA1QVlh5NHyzsnUHvs6yMn1/LbRwbIPXItAYBIS9uO5NFwcS/bfny8ff1fbPrIABpHgYRxSJo6+qQ58ku2DqldgPQDRdLU9oM9uSEIPShnEDagWoMhibEDiARQasA4Y9tBOaFm6UZgY9JG5ECsF3bkMvRAIi0tJSRclbaS51m3dN68tjTTcLhCy8tvZg0Q8EUdwG7guD/ofmYLIscYCuACQkAJsMcfdNdKKPQNWvgdAO8m1qt35mPb5ja0aSUI+KKFwCmF7yPFcT2+5pWBox+AmOECiGFpjS72ZPxLyr32XRiyF8jPt+IjatMABsjbb1WECry+C5PIp0/Xm2ukKO8Z16bM7aquPFoATEb1tpqeJcNpEfECPddvbI1VRsNfAhm1afuANEfqEfHeNPvqVs3dNafQ0S1/3j3L5c7NVHXfn6GNKzygZxHxSnOkfjgtqnXauMIzmBzIqB2yD6RG2fS/e0uLLnOpcwt3nq+ms7uC4mn/TGf5SKrsImMJBj/j1es/91X1tM54GK3mXPuvGjPy+X1tjzyaFR+1BINagCvu+V3fLq1NK8GwAJC6kPKsgXOJpS5++mOyzuxyApwG1vmD7jSD4bT9hhPsLsLUN0pqJXl7Xk3zYcAX3QnsBx4Ay/xB90u72rQ5Y72aBXzRpcARwO8Puu+OySQXgA8Vn/uB5D8A8B6b13QqFLKRmAAAAABJRU5ErkJggg=="
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
