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
PLUGIN_NAME = "Clean Empty Polys v1.2.1"
PLUGIN_HELP = "Удалить все пустые полигональные объекты без полигонов"

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
