# -*- coding: utf-8 -*-
"""
CleanSelectMatTags — Cinema 4D Command Plugin
Удаляет все теги материалов с объектов, у которых назначен тот же материал,
что и у выделенного тега материала.
Кнопка активна только если выделен тег материала (TextureTag).
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068913
PLUGIN_NAME = "Clean Select Mat-Tags v1.0.2"
PLUGIN_HELP = "Удалить все теги материалов с тем же материалом, что и выделенный тег"

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


def _collect_mat_tags_by_material(root, target_mat):
    """
    Собирает все теги материалов (TextureTag), у которых назначен
    тот же материал, что и target_mat.
    """
    result = []

    def _traverse(obj):
        while obj:
            tag = obj.GetFirstTag()
            while tag:
                if tag.GetType() == c4d.Ttexture:
                    mat = tag[c4d.TEXTURETAG_MATERIAL]
                    if mat is not None and mat == target_mat:
                        result.append(tag)
                tag = tag.GetNext()
            _traverse(obj.GetDown())
            obj = obj.GetNext()

    _traverse(root)
    return result


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanSelectMatTagsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        active_tag = _get_active_tag(doc)

        # Дополнительная проверка: должен быть именно TextureTag
        if active_tag is None or active_tag.GetType() != c4d.Ttexture:
            c4d.gui.MessageDialog("Выберите тег материала для определения материала.")
            return True

        target_mat = active_tag[c4d.TEXTURETAG_MATERIAL]

        if target_mat is None:
            c4d.gui.MessageDialog(
                "У выделенного тега не назначен материал.\n"
                "Используйте «Clean Empty Mat-Tags» для удаления таких тегов."
            )
            return True

        mat_name = target_mat.GetName()

        root = doc.GetFirstObject()
        if root is None:
            return True

        candidates = _collect_mat_tags_by_material(root, target_mat)

        if not candidates:
            c4d.gui.MessageDialog(
                "Тегов с материалом «{}» не найдено.".format(mat_name)
            )
            return True

        msg = (
            "Найдено тегов с материалом «{}»: {}\n\n"
            "Удалить все?"
        ).format(mat_name, len(candidates))

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
        # Активна только если выделен тег материала (TextureTag)
        active_tag = _get_active_tag(doc)
        if active_tag is not None and active_tag.GetType() == c4d.Ttexture:
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
        dat  = CleanSelectMatTagsCommand(),
    )
