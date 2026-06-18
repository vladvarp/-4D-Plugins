# -*- coding: utf-8 -*-
"""
CleanEmptyPolys — Cinema 4D Command Plugin
Удаляет все полигональные объекты (Opolygon), которые не содержат полигонов.
Если у пустого объекта есть дочерние элементы — пользователь выбирает:
  • удалить объект, сохранив детей (переместить на место удалённого)
  • не трогать такие объекты
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068961
PLUGIN_NAME = "Clean Empty Polys v1.2"
PLUGIN_HELP = "Удалить все пустые полигональные объекты без полигонов"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA90lEQVR4nO2WuxXDIAxFISejUKTyBGSrjJGtkgmoUrALKXI4ASQ+QsIVr/GX9y4ylq3U1hYm561y3p7hd0FvxvY54Q2/64BBYCLcWxd1JTSSvtRh8Hsoin6HeVMHBnYFWB5x4KyBxASmIbjwwIhiJhY+AzEDTAJoGS8Jb0GkHW4UshDshOP6NxjnbdYvnA+j/WMc4DBavqxUwTLDj8xyyN6zJgJw1gAU4dnPAwivBbkKFLMPz1sGWR7zADpViGG1LR+gVDF7/figlUjP8wF+VbCq8sdThmHhPID8/QcQa9dAR7Wyy66B9P8u2cfCexDiqoWcEr5F1RdgR8gkUwL0kQAAAABJRU5ErkJggg=="
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

def _collect_empty_polys(root):
    """
    Обходит иерархию снизу вверх, собирая полигональные объекты,
    у которых нет полигонов (GetPolygonCount() == 0).
    Возвращает два списка: (без_детей, с_детьми).
    """
    without_children = []
    with_children = []

    def _traverse(obj):
        while obj:
            _traverse(obj.GetDown())
            if obj.GetType() == c4d.Opolygon and obj.GetPolygonCount() == 0:
                if obj.GetDown() is None:
                    without_children.append(obj)
                else:
                    with_children.append(obj)
            obj = obj.GetNext()

    _traverse(root)
    return without_children, with_children


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


def _ask_keep_children(count_with_children):
    """
    Диалог выбора: что делать с пустыми полигонами, имеющими детей.
    Возвращает True — сохранить детей, False — не трогать.
    """
    msg = (
        "Найдено {} пустых полигональных объектов с дочерними элементами.\n\n"
        "Сохранить дочерние элементы (переместить на место удалённого)?\n"
        "Нет — пропустить такие объекты."
    ).format(count_with_children)
    return c4d.gui.QuestionDialog(msg)


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanEmptyPolysCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        root = doc.GetFirstObject()
        if root is None:
            c4d.gui.MessageDialog("Сцена пуста.")
            return True

        without_children, with_children = _collect_empty_polys(root)
        total = len(without_children) + len(with_children)

        if total == 0:
            c4d.gui.MessageDialog("Пустых полигональных объектов не найдено.")
            return True

        # Если есть объекты с детьми — спрашиваем пользователя
        keep_children = False
        if with_children:
            keep_children = _ask_keep_children(len(with_children))

        if not keep_children:
            total -= len(with_children)

        msg = "Удалить пустых полигональных объектов: {}?".format(total)
        if not c4d.gui.QuestionDialog(msg):
            return True

        doc.StartUndo()
        deleted_total = 0

        # Удаляем те, у которых нет детей — просто убираем
        for obj in without_children:
            if obj.GetDocument() is None:
                continue
            doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, obj)
            obj.Remove()
            deleted_total += 1

        # Если пользователь выбрал сохранение детей — растворяем
        if keep_children:
            for obj in with_children:
                if obj.GetDocument() is None:
                    continue
                _dissolve_object(doc, obj)
                deleted_total += 1

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED if doc.GetFirstObject() else 0


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = CleanEmptyPolysCommand(),
    )
