# -*- coding: utf-8 -*-
"""
CleanEmptyObjects — Cinema 4D Command Plugin
Удаляет все объекты того же типа, что и выделенный объект,
НО только если у них нет дочерних объектов.
Кнопка активна только если выделен ровно 1 объект.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068909
PLUGIN_NAME = "Clean Empty Objects v1.0.2"
PLUGIN_HELP = "Удалить все пустые объекты того же типа, что и выделенный"

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

def _collect_empty_by_type(root, obj_type):
    """
    Обходит иерархию снизу вверх, собирая объекты заданного типа
    у которых НЕТ дочерних объектов.
    """
    result = []

    def _traverse(obj):
        while obj:
            _traverse(obj.GetDown())
            if obj.GetType() == obj_type and obj.GetDown() is None:
                result.append(obj)
            obj = obj.GetNext()

    _traverse(root)
    return result


def _count_total_empty(doc, obj_type):
    """
    Имитирует многопроходное удаление и считает итоговое количество.
    Нужно для случаев, когда после удаления пустых объектов
    их родители тоже становятся пустыми.
    """
    nodes = {}

    def _build(obj, parent_id):
        while obj:
            oid = id(obj)
            nodes[oid] = {
                "type":      obj.GetType(),
                "parent_id": parent_id,
                "children":  [],
            }
            if parent_id is not None and parent_id in nodes:
                nodes[parent_id]["children"].append(oid)
            _build(obj.GetDown(), oid)
            obj = obj.GetNext()

    root = doc.GetFirstObject()
    if root is None:
        return 0
    _build(root, None)

    total = 0
    while True:
        to_remove = [
            oid for oid, n in nodes.items()
            if n["type"] == obj_type and len(n["children"]) == 0
        ]
        if not to_remove:
            break
        for oid in to_remove:
            parent_id = nodes[oid]["parent_id"]
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].remove(oid)
            del nodes[oid]
        total += len(to_remove)

    return total


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanEmptyObjectsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        sel = doc.GetActiveObject()
        if sel is None:
            c4d.gui.MessageDialog("Выберите один объект для определения типа.")
            return True

        obj_type  = sel.GetType()
        type_name = sel.GetTypeName()

        total = _count_total_empty(doc, obj_type)

        if total == 0:
            c4d.gui.MessageDialog(
                "Пустых объектов типа «{}» не найдено.".format(type_name)
            )
            return True

        msg = "Найдено пустых объектов «{}»: {}\n\nУдалить?".format(type_name, total)
        if not c4d.gui.QuestionDialog(msg):
            return True

        doc.StartUndo()
        deleted_total = 0

        while True:
            root = doc.GetFirstObject()
            if root is None:
                break
            batch = _collect_empty_by_type(root, obj_type)
            if not batch:
                break
            for obj in batch:
                doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, obj)
                obj.Remove()
            deleted_total += len(batch)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
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
        dat  = CleanEmptyObjectsCommand(),
    )
