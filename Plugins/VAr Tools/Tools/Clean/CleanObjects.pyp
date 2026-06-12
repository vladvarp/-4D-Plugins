# -*- coding: utf-8 -*-
"""
CleanObjects — Cinema 4D Command Plugin
Удаляет все объекты того же типа, что и выделенный объект,
сохраняя дочерние объекты (перемещая их на место удалённого).
Кнопка активна только если выделен ровно 1 объект.
"""
import c4d
import base64

PLUGIN_ID   = 1068908
PLUGIN_NAME = "Clean Objects v1.0"
PLUGIN_HELP = "Удалить все объекты того же типа, что и выделенный, сохранив дочерние"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABC0lEQVR4nGNgGOqgRkamf4OGxhkQTQ11JFt+x8joPwxPVVRci00dSBxZHVZHGBpZCLh6hUV5+EalEIv3mVudQTYYhNdY2a2FyYPMW2pkvBZdDSgkMCyPTatYn5LXdIIUvNwn5AS64SC81dUbLA+iscljhADIpaRaDsO4LMGFsUYTKLjIdQApjsCVRih2ADGOwGk5tRwAwvgcgNPyYRECA5oGBjQXUK0cINcBR+ycMEpCmOX4QgijJKRWCKBbDsOg4pkmIQBzBCgkQDQuNSDz8daG1CoH8DkAZxYcdcCoA0YdMOoAEKCkTUgMBpmP1wHktoqJwSBzQebjdQDMEaT2CwhhkHlEWT4KRjQAANYWScibwGJbAAAAAElFTkSuQmCC"
)


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

def _collect_children(obj):
    """Возвращает список прямых дочерних объектов."""
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


def _dissolve_object(doc, target_obj):
    """
    Переносит всех детей target_obj на его место в иерархии,
    сохраняя мировые координаты, затем удаляет target_obj.
    """
    parent = target_obj.GetUp()
    pred   = target_obj.GetPred()
    children = _collect_children(target_obj)

    insert_pred = pred
    for child in children:
        world_mg = child.GetMg()
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, child)
        child.Remove()

        if insert_pred is not None:
            child.InsertAfter(insert_pred)
        elif parent is not None:
            child.InsertUnderLast(parent)
        else:
            last_root = doc.GetFirstObject()
            if last_root is None:
                doc.InsertObject(child, None, None)
            else:
                while last_root.GetNext():
                    last_root = last_root.GetNext()
                child.InsertAfter(last_root)

        child.SetMg(world_mg)
        insert_pred = child

    doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, target_obj)
    target_obj.Remove()


def _collect_by_type(root, obj_type):
    """Обходит иерархию снизу вверх, собирая объекты заданного типа."""
    result = []

    def _traverse(obj):
        while obj:
            _traverse(obj.GetDown())
            if obj.GetType() == obj_type:
                result.append(obj)
            obj = obj.GetNext()

    _traverse(root)
    return result


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanObjectsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        # Определяем тип по выделенному объекту
        sel = doc.GetActiveObject()
        if sel is None:
            c4d.gui.MessageDialog("Выберите один объект для определения типа.")
            return True

        obj_type = sel.GetType()
        type_name = sel.GetTypeName()

        root = doc.GetFirstObject()
        if root is None:
            return True

        candidates = _collect_by_type(root, obj_type)

        if not candidates:
            c4d.gui.MessageDialog(
                "Объектов типа «{}» не найдено.".format(type_name)
            )
            return True

        msg = (
            "Найдено объектов типа «{}»: {}\n"
            "Дочерние объекты будут сохранены.\n\n"
            "Продолжить?"
        ).format(type_name, len(candidates))

        if not c4d.gui.QuestionDialog(msg):
            return True

        doc.StartUndo()

        for obj in candidates:
            if obj.GetDocument() is None:
                continue
            _dissolve_object(doc, obj)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        # Активна только при выделении ровно 1 объекта
        sel_list = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if sel_list and len(sel_list) == 1:
            return c4d.CMD_ENABLED
        return 0


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = CleanObjectsCommand(),
    )
