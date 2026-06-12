# -*- coding: utf-8 -*-
"""
CleanSelectMatTags — Cinema 4D Command Plugin
Удаляет все теги материалов с объектов, у которых назначен тот же материал,
что и у выделенного тега материала.
Кнопка активна только если выделен тег материала (TextureTag).
"""
import c4d
import base64

PLUGIN_ID   = 1068913
PLUGIN_NAME = "Clean Select Mat-Tags v1.0"
PLUGIN_HELP = "Удалить все теги материалов с тем же материалом, что и выделенный тег"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADTUlEQVR4nO2V2UvUURTH/UN88W2e5x8oKgiCoMnQdqKycoOoKHKMrERaCHvIpSm1RStFcyzDVqOitFxwKurluDvuW6ZIC9j9XGdimGZ+8/uN8xDhgR+Hc+/93e8537PcuLj/QbLj4/PdNlsrOhbnLIOL3b7g/woSEmpCnWM98FzMnCCiwItDOREMzsd/MXEgmIFgJ0KBx5QBI5BwX7g0hZVHpybsj09POJV2N5wc9zw8MSYPskY97qMj7ppDQ86qzEG7WScsgT/JnbQ9y5tyPT87JY3npgWtbFHr0pAzLvXZY1J3bESUE1KVMeh6vyrN0AlL4E/zJh2N56fl5cWv8ip/Rl5fmtEam3W1L4oR7YRiQqoPDsndNK8YOWAJ/MWFaQ365vI3aSqcleaiOa2xWWcfJ2BCpUNqjwxLy5p0QwdMMQDtRAjI24JZeeeak9aSeWkrndcam3X2OUc6qIn2tRmG4KadIOfQTKSAtZXNS0f5d/lQ8UNrbNbZ5xw10bEu0xR4RCeodgqNXEM3EQP6qfKnfKn+pTU26+xzrj05NyR484pUcSV1he2OkHOAVqPaoZecQzuRAy71C1pjs84+5z6vTv7LAdUNcn1nr1xN7nJyr+lJSJ8vlQEKsTylX8p29MCA23+3qbeAIUNOrdZAS+IZ+bgySZrW50hlulfK9/5xwBN4f8TXkGqmqqPpgjrfLLiTOiA3d/dJ6bYeubKpUwwrPlgYr/Q1/R3NHFAjWW7vH5Abu3rl2pZuKdoonsioAcJsZ7Ix4bg8mknop18VoBRuEHdk1ADhYWG2cymRQS85NvkWSMW+fh19ydZuKVb0KweclhzgVeMyIoJWcqsKU0eqWlRrbN9rqM9pcKg/4Mv9dl18gPPZLTmgnVCvGnSSUwrr/vFRDVaftQiKzTr7nCNywG/t6VukfnMXuQfcZRkcUTTayCVRAUCE9w4PS6360NgaWO1zDtqJHHAKrzix0x+9LSoHEFVIDqqZlqKvKzO8OlI0NuvsU3DkHNqJPADcETW4X9TFDiIDhMlWkbKosVkHmKgpOHLuoz024H5Rw8SmQFwAMdvRfAwZ6KbVfNWuc74k2o2EV42HhdnOeGXCMWToc1otqmpflmX5V+Q3HlsWaeFLAjcAAAAASUVORK5CYII="
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
