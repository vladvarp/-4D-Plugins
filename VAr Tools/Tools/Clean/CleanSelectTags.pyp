# -*- coding: utf-8 -*-
"""
CleanSelectTags — Cinema 4D Command Plugin
Удаляет все теги того же типа, что и выделенный тег.
Поиск ведётся по всей сцене (по всем объектам).
Кнопка активна только если выделен ровно 1 тег.
"""
import c4d
import base64

PLUGIN_ID   = 1068911
PLUGIN_NAME = "Clean Select Tags v1.0"
PLUGIN_HELP = "Удалить все теги того же типа, что и выделенный тег"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABd0lEQVR4nGNgGOqgRkamf4OGxhkQTU21RFt+x8joPwxPVVRci0stSA5ZLVUcAfINsqG4HIFuOQiD9FLsAPQQwOYIbJZTLQTwWQASxyeH00Blt/AEjYCUPFLwImsnrBaRbLl5fvfMgAUn7pCD14cm3aHIchAg13JiHEHQ8iHvgAGNAmIsJ8oR1LQcJI5LDqcj0A137Vq7Xy+2tBGEQWx0+XmJxTgtJ+RArAURsuFWpZMWsPMLi8LkQGyQGLKaAx4BGIYjW+4///htXI7AWhQjGy6qbWaDLg8SwxcCyJaDMKiQsijomYXNEQRDANn3yKGALRpAIQGi0eVADuCXV9fGppZgGiAmBAhh5BBAxlohmSUEHUBMGiCEYWkAGdtWzViB1XJ0BxCTC0jFoNDAaTk2B1ATu/dvPootXdHNARIGNk54LaelA9T9k3MJWk4rBxCMd1o7gGC8IwNKWkTYsG5UQQ3RlsMAOW1CZAzK5yDLcRY2o2AUDDYAAAFm+aRevyxKAAAAAElFTkSuQmCC"
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

def _get_active_tag(doc):
    """
    Возвращает активный (выделенный) тег или None.
    Перебирает все объекты сцены в поисках активного тега.
    """
    def _find_tag(obj):
        while obj:
            tag = obj.GetFirstTag()
            while tag:
                if tag.GetBit(c4d.BIT_ACTIVE):
                    return tag
                tag = tag.GetNext()
            found = _find_tag(obj.GetDown())
            if found:
                return found
            obj = obj.GetNext()
        return None

    return _find_tag(doc.GetFirstObject())


def _collect_tags_by_type(root, tag_type):
    """Собирает все теги заданного типа во всей иерархии."""
    result = []

    def _traverse(obj):
        while obj:
            tag = obj.GetFirstTag()
            while tag:
                if tag.GetType() == tag_type:
                    result.append(tag)
                tag = tag.GetNext()
            _traverse(obj.GetDown())
            obj = obj.GetNext()

    _traverse(root)
    return result


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanSelectTagsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        active_tag = _get_active_tag(doc)
        if active_tag is None:
            c4d.gui.MessageDialog("Выберите один тег для определения типа.")
            return True

        tag_type  = active_tag.GetType()
        tag_name  = active_tag.GetTypeName()

        root = doc.GetFirstObject()
        if root is None:
            return True

        candidates = _collect_tags_by_type(root, tag_type)

        if not candidates:
            c4d.gui.MessageDialog(
                "Тегов типа «{}» не найдено.".format(tag_name)
            )
            return True

        msg = (
            "Найдено тегов «{}»: {}\n\n"
            "Удалить все?"
        ).format(tag_name, len(candidates))

        if not c4d.gui.QuestionDialog(msg):
            return True

        doc.StartUndo()

        for tag in candidates:
            doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, tag)
            tag.Remove()

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        # Активна только если выделен ровно 1 тег
        active_tag = _get_active_tag(doc)
        if active_tag is not None:
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
        dat  = CleanSelectTagsCommand(),
    )
