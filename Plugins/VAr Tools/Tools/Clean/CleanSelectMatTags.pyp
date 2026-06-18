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
PLUGIN_NAME = "Clean Select Mat-Tags v1.0.1"
PLUGIN_HELP = "Удалить все теги материалов с тем же материалом, что и выделенный тег"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAADmklEQVRYhe2XzU9cZRTGf+edO+NAZYQ07dBCpB3kU1udQN0RbZPaiokmfiy7cSGJxoU6aGuitW0qTZhE04S48g8w0WpMTDTWgqbapiotIDDAFGilHRAJWPrBZO69xwUfnSmgLmaiiTy797wn53nec56cmwv/d0iuCmu0pgz0WZDahUgfyMcS6b+UUwGqCNGqQ4gcACZRvTrPIpuBDai2EBk4KIICWNkWQLTmCKKvYvQFVCx8zmckVTDep3DVRqSNaBUw8DaAySa3vlcZQvR1kCaS0o7qNAB3iYLOIOYUSBMi+7W1aitkuwOueRplAuNMYclLYCZJGmfhNoS4OxDtwDUTGHkGiGZ7BJUYfkO9o4hzEohJ87zptKV6Cx6pxFhjGGcSpQKyPAIUxQWMCjaQ0tsm9wMugq3z9tPcmHAQtBHXvheP7EI0rK01AwDYTjWWFIHdjpiNwBBkvQN6ApEgYoLY0oYjcVKp06RSp1GJg2lDTBBlIx4+gbQOaGvNGwh1qxfnB2nuf19ba57AuA2r5rnyEegHeOVlwJAHJFUQKUL1MeA4wlF5JTYKaYtIo9WfA3Ug36/AHgD2AAeBAL/7G7nmG6T8j1hmmvGTyGvCuN8RnHsUmEa5ggGUEqAIOMprsSOLi+jOEfyML7UP0V5QD6K9+FL7JBLbu0B+CKWelOliMBDmZOnjXCxMINYJvtn8KV+V7uCXwlm82gD6PCrHEO1EtROVYzh2uURihxfJM0awhDnPTgz1C22vZ86zE/hSIrHDGq1+BJEyNt38CZ+zm4uBNxkqeJfhu69hyz2gx0m6e1ifbEElLM39kVVHtYDlJjSif3G+sbyECqqQ9iqU5N8Rry7AZ3egcg4lico5fHbHspxEfgk/bviaWV+YiusH2D32JF5nFyINWFYvifySfyogw4SO8Tx8YV1oas7j9a+UXHvjUnFKvHZqOs+9osUzI/cVzGR8TxW2xmcLS2S88Eyo/PJzD+4/e0eJX7GsD6ndklgMLHlg1F/c1xkI7S1wbkm+k7y+koC+dWXjt8RnT60P3FztOSMVBTMjFMx8W/jA+AoZjdj2i/QMh9kWmsi86hp6h674qRULZwuqQnf8DN3xtxZDtz0gsgmZX485g4gC3UDpcgH/EtYErAlIFzAGbEc1Z/8K85BqRK4unZbiPcNB1D0PjAI9OWKvArbjkYe4v/wypHdgW2gCy6pD+SJH5CDSnk6+hv8E/gRqEFagL1yaWwAAAABJRU5ErkJggg=="
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
