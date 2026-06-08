# -*- coding: utf-8 -*-
"""
RemoveEmptyNulls — Cinema 4D Command Plugin
Удаляет все Null-объекты в сцене, у которых нет тегов.
Работает в несколько проходов — пока есть что удалять, чтобы корректно
обрабатывать цепочки вложенных пустых Null-ов любой глубины.
"""
import c4d
import base64

PLUGIN_ID   = 1068832
PLUGIN_NAME = "Clean Empty Nulls v1.0"
PLUGIN_HELP = "Удалить все пустые Null-объекты без тегов (включая вложенные)"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA00lEQVR4nGPU0NBgGEjA"
    "NKC2j1gHbBER+U9zByBbgk0cRtPEAeiWYHOUz5s3jDRzAMxwXI5BlmdEzoY9PT0nCBle"
    "UlJiQaxDsEUDsuUMDAwMLKRYQIwD0S3D5XMYoGkuwJcGYIDkKCAWaHR0mMPY+EKCpCgg"
    "FmCzDNkRW0RE/tMlF6DHObbcQbM0cKOi4iQxjsOIAhiwsbFZAGMfOXIkgVQ+Pschh8TI"
    "rIyQAc4oQA9GUvnEggEPgVEHjDpgwB2AkQ2pWSMSAxhHOyajDhh1wEA7AADiD3UeY7G0"
    "tgAAAABJRU5ErkJggg=="
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
