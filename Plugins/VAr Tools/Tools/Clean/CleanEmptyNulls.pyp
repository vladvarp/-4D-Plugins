# -*- coding: utf-8 -*-
"""
RemoveEmptyNulls — Cinema 4D Command Plugin
Удаляет все Null-объекты в сцене, у которых нет тегов.
Работает в несколько проходов — пока есть что удалять, чтобы корректно
обрабатывать цепочки вложенных пустых Null-ов любой глубины.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068832
PLUGIN_NAME = "Clean Empty Nulls v1.0.2"
PLUGIN_HELP = "Удалить все пустые Null-объекты без тегов (включая вложенные)"

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


# ─── ОДИН ПРОХОД: собрать и удалить текущие пустые Null-ы ────────────────────

def _collect_empty_nulls(root):
    """
    Обходит иерархию снизу вверх (листья первыми).
    Возвращает список Null-ов без тегов и без дочерних объектов
    на момент вызова.
    """
    candidates = []

    def _traverse(obj):
        while obj:
            _traverse(obj.GetDown())  # сначала вглубь

            if obj.GetType() == c4d.Onull:
                if obj.GetDown() is None and obj.GetFirstTag() is None:
                    candidates.append(obj)

            obj = obj.GetNext()

    _traverse(root)
    return candidates


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class RemoveEmptyNullsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        root = doc.GetFirstObject()
        if root is None:
            c4d.gui.MessageDialog("Сцена пуста.")
            return True

        # Считаем сколько всего будет удалено (для диалога подтверждения)
        # Симулируем проходы на копии — просто считаем, не удаляем
        total = self._count_total(doc)

        if total == 0:
            c4d.gui.MessageDialog("Пустых Null-объектов без тегов не найдено.")
            return True

        msg = "Найдено пустых Null-объектов: {}\n\nУдалить?".format(total)
        if not c4d.gui.QuestionDialog(msg):
            return True

        # Удаляем в несколько проходов пока есть что удалять
        doc.StartUndo()
        deleted_total = 0

        while True:
            root = doc.GetFirstObject()
            if root is None:
                break

            batch = _collect_empty_nulls(root)
            if not batch:
                break  # больше нечего удалять — выходим

            for obj in batch:
                doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, obj)
                obj.Remove()

            deleted_total += len(batch)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def _count_total(self, doc):
        """
        Считает итоговое количество удаляемых объектов через
        имитацию проходов (без реального удаления).
        Работает на именах объектов через временный список.
        """
        # Собираем все Null-ы сцены в плоский список с инфой о связях
        # Имитация: считаем «живые» объекты итерационно

        # Строим словарь: id(obj) -> {'obj', 'parent_id', 'children_ids', 'has_tags'}
        nodes = {}

        def _build(obj, parent_id):
            while obj:
                oid = id(obj)
                nodes[oid] = {
                    "type":        obj.GetType(),
                    "has_tags":    obj.GetFirstTag() is not None,
                    "parent_id":   parent_id,
                    "children":    [],
                }
                if parent_id is not None and parent_id in nodes:
                    nodes[parent_id]["children"].append(oid)
                _build(obj.GetDown(), oid)
                obj = obj.GetNext()

        root = doc.GetFirstObject()
        if root is None:
            return 0
        _build(root, None)

        # Итерационно удаляем пустые Null-ы из словаря
        total = 0
        while True:
            to_remove = [
                oid for oid, n in nodes.items()
                if n["type"] == c4d.Onull
                and not n["has_tags"]
                and len(n["children"]) == 0
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
        dat  = RemoveEmptyNullsCommand(),
    )
