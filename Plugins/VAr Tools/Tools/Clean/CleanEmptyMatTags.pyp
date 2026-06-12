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
PLUGIN_NAME = "Clean Empty Mat-Tags v1.0"
PLUGIN_HELP = "Удалить все теги материалов без назначенного материала"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAACA0lEQVR4nO2WMUvDQBTHu7t1EAoVKRQMCIJZKugkpYJTCy7FQRAHp1LI4JAOfgMnUYqKQx2F4OSqUwcL7dahe0eh4CKUeL9oIMRLvEujg/TB43J3773/u3fvvUsm8x+olc+fOYbxwpiGnDb4yDRdn88LhXuZHOtBudSc4ERBwzInwuAweqk4EI5A2AkZeKoRiAOJ4qhriqTiomnWS7Z9WnWcy4PB4PZoNGJkzjr7qk5ogS9lDaNZabcfrel0cuG67oPgZ8Hdr1HMWWcfuZuVtVgntMA3i7UaJ32/EkA9wW+ue7Lb6dQ3bLtqNhqMzFlnHznk4xzQAncak4l34lfXBSy7kMsBEGbW2UduvG/NHn7CjmHArw+Hw/XlclkGHOa71VI6OcBdemEXJ1IF724fx4Ze2QmymYTiTgmrCvjTTksK3q9Y07jqkPYBSsrLdpFYUXce5v7W3jcHxk3Lqw7sYVe5E1LX3D3ZrQIuiwDX4VWHsIM937bSW0Bzob5Vwx90gkgwMveqQtjBXtD+j6+hl/2iyVDnOg6EGX3s8B2b8WlFIMxREfiRkuSAjGU5oERJqkDWGdEPVoEyJekD0vD3Ph8o7Gk5ACXphD4jjx762NEGh5K+Bcghjx5z7CRyAEr6GiKPHvqJwYNOAKD7P5AKuE+6f0QzhT2OVP4JfwV4TnP6C/oAu0qnwyk2lQsAAAAASUVORK5C"
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
