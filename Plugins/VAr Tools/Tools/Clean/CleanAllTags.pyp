# -*- coding: utf-8 -*-
"""
CleanAllTags — Cinema 4D Command Plugin
Удаляет все теги с выделенных объектов.
Кнопка активна только если выделен(ы) объект(ы).
"""
import c4d
import base64

PLUGIN_ID   = 1068910
PLUGIN_NAME = "Clean All Tags v1.0"
PLUGIN_HELP = "Удалить все теги с выделенных объектов"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABfklEQVR4nGNgGAVQoMrBob1CTe3QHSOj/yAaxKer+TBJGD6orf2AWo4AmQMyD9l8kH0oipAlqekIbJbDMIpC9BCA4WMm5g/cnMLzNNziScYgfSD92MzFCAF8LiXHEfgsxxmyIEFcmkhxBMmWy5m6B3s2rDsV0LPvTkbN0junbZywagaJg+RB6nBhfPqPGBpj9znMcmIMwecIfPpgISikoG2E4QBSDcPmCGIsh0URl7CUHEEHkOIIQuqwpR1mNg4ugg4gxvCG3F6CjvRp23oJW2IlygGEHIELo0eTbc7kVUQ7wCCkqAWmCMQm1RG4Eqp+UEETQQfY5kzCcClIjFhHEMqqBNMAsu/RQwGEQXGOzwEgeXzRSTAX0DoEiCoHaJUGFCz9ojAsp1cuMEtomsbIxMRMsgOoVQ5w8ImIY7WcHiWhnYlzME7LcTmAmnUBwZYVPWpDvI6gV3uAYEjga5aR0kAlyxxqWU62ebhaxZQ0zfE5YvD3C+jeMxrwvuFAAQC1fGxsSc/K/gAAAABJRU5ErkJggg=="
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

def _remove_all_tags(doc, obj):
    """Удаляет все теги с объекта."""
    tag = obj.GetFirstTag()
    while tag:
        next_tag = tag.GetNext()
        doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, tag)
        tag.Remove()
        tag = next_tag


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class CleanAllTagsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        sel_list = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if not sel_list:
            c4d.gui.MessageDialog("Выберите объект(ы) для удаления тегов.")
            return True

        # Считаем общее количество тегов
        total_tags = 0
        for obj in sel_list:
            tag = obj.GetFirstTag()
            while tag:
                total_tags += 1
                tag = tag.GetNext()

        if total_tags == 0:
            c4d.gui.MessageDialog(
                "У выделенных объектов ({}) нет тегов.".format(len(sel_list))
            )
            return True

        msg = (
            "Объектов выделено: {}\n"
            "Тегов будет удалено: {}\n\n"
            "Продолжить?"
        ).format(len(sel_list), total_tags)

        if not c4d.gui.QuestionDialog(msg):
            return True

        doc.StartUndo()

        for obj in sel_list:
            _remove_all_tags(doc, obj)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        sel_list = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if sel_list:
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
        dat  = CleanAllTagsCommand(),
    )
