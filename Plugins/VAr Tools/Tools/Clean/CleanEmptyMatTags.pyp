# -*- coding: utf-8 -*-
"""
CleanEmptyMatTags — Cinema 4D Command Plugin
Удаляет все теги материалов у которых не назначен материал.
Поиск ведётся по всей сцене (по всем объектам).
Кнопка всегда активна (нет ограничений по выделению).
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068912
PLUGIN_NAME = "Clean Empty Mat-Tags v1.0.2"
PLUGIN_HELP = "Удалить все теги материалов без назначенного материала"

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

def _collect_empty_mat_tags(root):
    """
    Собирает все теги материалов (TextureTag, тип c4d.Ttexture),
    у которых не назначен материал (параметр TEXTURETAG_MATERIAL == None).
    """
    result = []

    def _traverse(obj):
        while obj:
            tag = obj.GetFirstTag()
            while tag:
                if tag.GetType() == c4d.Ttexture:
                    mat = tag[c4d.TEXTURETAG_MATERIAL]
                    if mat is None:
                        result.append(tag)
                tag = tag.GetNext()
            _traverse(obj.GetDown())
            obj = obj.GetNext()

    _traverse(root)
    return result


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanEmptyMatTagsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        root = doc.GetFirstObject()
        if root is None:
            c4d.gui.MessageDialog("Сцена пуста.")
            return True

        candidates = _collect_empty_mat_tags(root)

        if not candidates:
            c4d.gui.MessageDialog(
                "Тегов материалов без назначенного материала не найдено."
            )
            return True

        msg = (
            "Найдено тегов материалов без материала: {}\n\n"
            "Удалить все?"
        ).format(len(candidates))

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
        # Кнопка всегда активна — не требует выделения
        return c4d.CMD_ENABLED


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = CleanEmptyMatTagsCommand(),
    )
