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
PLUGIN_NAME = "Clean Empty Nulls v1.0.1"
PLUGIN_HELP = "Удалить все пустые Null-объекты без тегов (включая вложенные)"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAADOklEQVRYhe2WT2xUVRjFf999b2qLiQnjn9QSNQat0xmpxkJIEWKgKZUNQU1UUEnTNC7cmOikurGhceEAtUsWFhYQDCnERFxpW2JMyhBCQ2DqDAN9DhUNtmgoaUhMO2/e52LqU1unvNYaYzJn9+5573zn3nu+ex+U8R9D/tHX57M1GBEmr0+webO7FAmzpKLH1QLAts9grB+596EbZHKP/PsGRpwN2HaKSO6V4oDVgsg6ROLUPXqNixfvJuU0LMXInXHh8ipSzi+knL7GZLJqLq179hhGnDgjzs9kxh4MKht8BVz7Nsj+xts3WpOdnd9rc/N2v3hz83aGhq43TN86AEySdzuDyi4phLplyzaM6UN1N6rTGNMHvCGDgydJOTuA+6l/rHf5DKSvVlMoHAevlfranG9C5DNEAHbK4OBJAD+gL0shiHSwLcjPWMAmxAr/1f6sf9U/JhLNPUPkO5fz2ZrlM3CldhyYBNbCn7YAduJ5LyFyRJuadgDg6XrQmzhPTASRDp6B1OhzWDNn9MQJl6GhcUTaZWDgC5gNoeonbNxYIy++1oswzZrH3wqsHRiqhpTT2jA8vGIu1ZhMVvlbMTp6V1DJxXXByJU61HyDcAuVLupXf8qFy6sw1gvA2yAHqV+9dzGSizsJ19RewrafwuMUaKSoYG8F7UJ0ANs6sii9ZUE6XeG3Xhn/RyzYBdpduw1MG4iCHpJ49iuf21/3JOizCIprTsv7mbTP9cTCzGjxRqyQn+Sd9M1SNUp2wWzxowhnUe8ccEy7Iy1+cdE2lKsYxrAK7ZqIxvzi4tYRMlOEzBRePqo9sXCpOnbp+ZvdIHvl3UvdAL9+tKkyNfFm4vCu15/+euzUurXV+47e80F/P8DUh1tXDI93dB3e1XTu829zD6y/7+ODNfsO/ACgiZhgUw387SosdA7o3AHXq7I9WOl6lRXzucoKD1Z6as37WcGamaf1O0pmYHa5j6FSPNlE38PjVenI9msiGsMqtCPyZfFlfR6xeyWezmhPLIyXj+KGrgFg5x/GhDKlcnCHEEZaQNoA8PSQdGT7fS4RjRHyNhQfrNMST2d8ricWxqMaAMP4QiEso4wyfgMsiTY4LnTERgAAAABJRU5ErkJggg=="
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
