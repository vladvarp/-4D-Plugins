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
PLUGIN_NAME = "Clean Select Tags v1.0.1"
PLUGIN_HELP = "Удалить все теги того же типа, что и выделенный тег"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAADZElEQVRYhe2XUWhbZRTHf+c2V9KNlWDBtMOuM0PXTVecxTIYQwSF4ZQ5cbolbG2HT4IO24gPQ1EfpGBlnehDH2aTovGhwphUEB8qQ5hF1NBEu+K6rrMjbTpFZ1vW9jb3+NAmS29SqnCDA/eH+3DP9//O/3/Oud8HF/7vkFIk7Tmid9kZnlbYviwyZFucOdYr15xcw23x6GFttTOMAW0iVIpQKdBqmFyJHtZWt/VWIBLUcCSo16MhPVBgLKQHIkG9HglpW37ctRF0H9QqMRnF4FDzx/J5MU40qPsVPlWLQEuvTIKLIzA87AcuryYO0BSTswhjy1xcNaDCViC+Fk+UuC3c574BUPkHI1VBBGzXDRjKLwoPrUlUdgIXXTdgL3IW2FTsBGTRHdQjwCa1yH0nrhlo6ZVJFU6oEo2G9FlFc+NQVLpDekygR+HL7AmAvJnpu9teQ2goml05L69e6Mzj7sOw9xSj/jAervhp6oWjwITAd0vbaQSqFfoEDgKvNMfkfcjvgOhu0N1F1CsQPakddW/kcR/lT++TXN1Qu5JqeBvKP2x+vnLvO0C7KlOqTAHtdyibW2JySOA40BkJ6lEAj7MARDtROY5wUtouDAAsi7+lHXWzEh5+D4A5iZP07SHpm8Y0wwBYVgdlOu1tnDjRVLvtGQkPn3aW0xSTDyJB/UuE6ZUdyFXBS6DPofpyruDw8NtAP/BIjuefS2Oa9YCysDCKZY0APjzeOnwLHwGPF3ZzCc0x6Wn6RM4U6wCInEJVUeOUY2V2tYSILD2q2SLmV+U6UGBgue0Da+5Me/1YVgL4CtMMAEsjmJ+Pk/Z+g38u/a8NZIyyxu+7nvp5rsz0Ool/zF6purRu4zUSfV2fDbbv2rVwqebyY9W/p2rKHwbOZXkbx29Y99iZfQP+LeMk+rocacbxeE6zffNEgYExb9XQjxWBvRsyN2RdZn7GaWBofe1kcn3tbwD9d9anMoZhOzkAqZrymRT3zpzzPTBZZPkJFhdfJDm6kx0BR4cGL77J4Eh/saSuQVVIjHxLYuT1bCjvHpBq5OYdXRKIKJAA7i408B/htoFbysBVoB7Vkvwr3ITUIZLKveXiyVE/aseBMSBZIvWtQD1l8iD3b/kV8juwI5DG42lA+aJE4iDydb74bdwS+BvclT/dZrdVTwAAAABJRU5ErkJggg=="
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
