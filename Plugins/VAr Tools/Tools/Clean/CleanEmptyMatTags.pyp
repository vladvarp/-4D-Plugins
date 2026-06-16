# -*- coding: utf-8 -*-
"""
CleanEmptyMatTags — Cinema 4D Command Plugin
Удаляет все теги материалов у которых не назначен материал.
Поиск ведётся по всей сцене (по всем объектам).
Кнопка всегда активна (нет ограничений по выделению).
"""
import c4d
import base64

PLUGIN_ID   = 1068912
PLUGIN_NAME = "Clean Empty Mat-Tags v1.0.1"
PLUGIN_HELP = "Удалить все теги материалов без назначенного материала"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAADUUlEQVRYhe2VbWiVZRjHf9fzPJvnbCOnx2aTg1tH2QLdSa1YsqRYEczIQEYGwVakfSv2YbHnGLHzpXZOncD6UEkR7hjYCwYRBovVBFE76ZJtH2ruxenmmtQcez8v2333QZ7DsVlIuAw6v0/3/Vz/+/7/ue4LHsiSJUuWLLcZcRahUOgJEdkBoJRqDwQC7eFwOJS5/ydagGBQG+t7eQTgUjnHg0FRSwKEw+EGrfWOglTqsmdqquKix7MZyAN+BpoXFxcvmqZZYtv2MUcrIn2bR0fdvUVFD6Usq0JrPa61jiil2hwtwKFn9KMYNACgOPDcp/LdkgAORxsbj+zq7q6dyM/fe2j79jat9bta6zHDML5VSh0Bam3bbgOIRCIlT3V2/lI8Odl7xut9LObzPQB8bBjGq0qpdxztTQUIhUJ1zrLu1KlXiufm3kfrujeqq2OmaXbatr2upaVlr4gknTNaa1eeUpUvd3SUALksLOx8s6bmbaVUJ6BEJGnbdvTvnsBIJxHxi4gf4HBVVQdK7UEkuu/s2RpAAwQCgY9s245mauOWtYDbvQtIYlnfuJLJnEwtQHMQbSpGTMVIc/DaXTecAQCl1N0i4hWRl56PxR5fNTPz4Vd+/+e1kcizjiajA18CMcMw9j04PBzbNjDQ/mthYdlRv79cRHYDNDU1HWjdo8u0ea0Dssjx+s/k/A1noOG9gw2TLtfThbOzpYWJ+UJDK3PlfHz2zHrfwOFtlT+98OOJhxM5uYlPtlb+UD3Qu/GumcnVViqVs3Z2+s5V83MerUmIZmz/zt3tmdqNI66VWwby1rmT5tX8RM5bH+zPO+l4Wmn3cxdKT4wNvl46Mf7b7+6Coa833dvjmExbK1IAFzxFl+dyrGRm6Al3wVT0/qqTGdr5P2sHvfFJgGQuZcNr4l/w5OBWKnxXuI6uviBd/d+zLGhprdOegy/qNXT1n6a7/zWnkh5CRIoR+pbDvrWO1XqB0hUzlHimzfOAd2mA28S/EqA+ylWxGBKLofE7FuOZNeuvDt1aRNdHGQegsf+6yv/jCW42wAjgR+slP6hbi9yDyGh6l/7eM7gWrc4BQ0DPMrmXA35M2cKmDZcgswMVvitY1n1oji2TOYh0ZJpn+U/wB4WoiIUM3CfMAAAAAElFTkSuQmCC"
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
