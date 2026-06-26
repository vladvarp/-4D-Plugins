# -*- coding: utf-8 -*-
"""
CleanSelectTags — Cinema 4D Command Plugin
Удаляет все теги того же типа, что и выделенный тег.
Поиск ведётся по всей сцене (по всем объектам).
Кнопка активна только если выделен ровно 1 тег.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068911
PLUGIN_NAME = "Clean Select Tags v1.0.2"
PLUGIN_HELP = "Удалить все теги того же типа, что и выделенный тег"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAADfElEQVR4nO3Yz2ucRRjA8e/zzrtJ192thdRW9FJvASnSWAOlYLwKBb3s4kUxHsyxIKLQg3HpzaN/QYke7O7Bi4V60hxsgyUVDxFFqR4EsVUwiV3Nvu/M08Nmk91mk+xull2DzweGd9mXmXln3nne+QHGGGOMMcYYY4wxxhjzPyI951DtPc8giejoKld1o6t8U0XdIF9C7wXd0Cx5juBR/u4jfz/yNN66Rzkrq4MsursGNHpc+JpLZHiTlBweGVLzt56CGA98xjrv8AJ/AgcOiXj/atUh4rmpl3icy/wBRIADhh2NATjOLAlPAi82n/AgRe79Dpux9hV5Yn4iwwR1wKcROoJvkXMgUUqWDHWmmZZbVNRREr9bFp0nApAyodP9/UeAiHJDM8AYAUeaKN+uCEkKMqQYECANcHoSjhUaY085ul82rRSdlKr+4d+t9u8AaHx8HGFrvCQpJMkQO0Ag9bSMOiGirTFaKW7PUI/dFe6dUDbunNArU5epJ+9LqfqrVoqOYjWIbIdNdx0AoC3hIrKdhqFTXb49fDu9XZ3nd05NvUFu/IJ+fOailKpXG//PxFJeTKGXDvivWkH1i5mYn9fPMSYxKRCpEEQhFIC/gJNk4k/0o2dfpsZbMrf4WzP7oe4AAbTsAkcnjzFx5HPiKAvaGC0OwEESoB6UuiqPxK8g+rwuTJXxhQV+WaxHI27DIDki2JGAzRVLYCPAePQE6Fly92KeLsqhHgEAqBc+mExQrvNvKOCD0pzehRhkGhgjl4lJ/R3up2/L69982sj83eEOAQWoEsm7P6wDL+24Pz8T89TaGtlY2PAfUuM9mbu92jol9hcCQvtMMKy0V2fME6kSbV6dKhGnasdR+Z5auCCvLl+UueVVrdC2Hui+A1rmTtIAadqYm4eW0u11gKI7psEyQYSwefUiBHJuldzYeZldvqaVolNFpNS+fuguBFKUGEeEx7mI05MQtJ+9ZP9UIZ+DQMARk2HHvP8wKS39A7uvAqGbJlTUUSSwxBVO8hp3SYn6DJ2DEMATeJSYNX5knDM8Q61xb/cdoSrSuvLrVOzemhuiL5mgwALx1i5s+CIgsMJ9Zjkvt1CNEOm4yelW74P4tj6HkGfjINX2KYtniZvMSYKqDPd4TFVGfh7YpDqwEOy9QZURnwsWCaM9GDXGGGOMMcYYY4wxxphD7AE4+3dMUCqIwQAAAABJRU5ErkJggg=="
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
