# -*- coding: utf-8 -*-
"""
CleanObjects — Cinema 4D Command Plugin
Удаляет все объекты того же типа, что и выделенный объект,
сохраняя дочерние объекты (перемещая их на место удалённого).
Кнопка активна только если выделен ровно 1 объект.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068908
PLUGIN_NAME = "Clean Objects v1.0.2"
PLUGIN_HELP = "Удалить все объекты того же типа, что и выделенный, сохранив дочерние"

_ICON_B64 = (
    "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"
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
