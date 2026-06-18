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
PLUGIN_NAME = "Clean Empty Objects v1.0.1"
PLUGIN_HELP = "Удалить все пустые объекты того же типа, что и выделенный"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAACyElEQVRYhe2WTUhUYRSGn3PHPyyocdEiauHPKkolqdAyYXImSwoJbRe6rE1RUeKunZpkEEVUBOUuHTKRrGSUhGggMXB0ldrPrpUjYaZjc08LUWfujOOMXGnju7o/33Pe9577fd+9sKUt/WdJ1NnYVDXKKdD0BMwCKj0U5Q/YwRrRBdQLun2dzE5E+xiddNnBpq3cU61C6ORAQUPiIkBgQhCpAQYjWb168TAiz5mebpeRkcWV0iUl6eTkXEO1XtofdkWyRkTZDJT5dc2XnuQ3kBnDGkY1UIHTOaIuVxmAejwlOJ1+VE+iWmNl07BR0t//DTitHs8ZVF+o2z2Lae4EGsXn64jHGPEu2pUHVVBNOMjWDqjHk4vqA0xzD1AnPp9fXa6DiDzWysoGwuFLYmEiO7AAkp2Uk5AFhGJY03wNDBEMlsjAgB9ABgc/EwyWIvIOh6PbykasAulBtI/AFKBzCc2V88A5KyvtjzpB84D70cjKwbCVje7I6KQLoYboGb6qHT92o8YCv/Y+pbDgTUrskkJAXwyblLStEG2ZQZurUoeTNmkpQ29XxDHfhTZ/R5sb7ba0LkMnmN1oW+6q+b1MMF+CDCFNrXYHsK4K0Ja7wFGYP4bcCqGtT0D3QbYLubyQqFhtbe11ABH52NXV5a+rqytV1TIAr9d7Z3nM8jHE3QecN2FmCLJa0eafYLrBPLKe+UYV2wFg6RWERwAHOMqRG4HNMF87ALA0GcOCNL1PtphNrwAY/VrOuOlGNY1AbcSyk0VMo5fivE/JhlpPsR0IfDkORi/KM0T/WIZvA+ox5AT784ftCBDbAXVUIdpBUcGVuMTYhAOlBtikAGgGytoz3pQ5Em+3KWkz/wc2GkBCGLr2Z1kkCyS05v0UFWcOyCtUfASmTDBnLe7ZoBdQqbYrQPx9YHzqEKaejfnHF/lLWN5SnP/BrgBb+geovSjI11ucBwAAAABJRU5ErkJggg=="
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
