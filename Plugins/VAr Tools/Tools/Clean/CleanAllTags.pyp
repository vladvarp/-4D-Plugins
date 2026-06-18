# -*- coding: utf-8 -*-
"""
CleanAllTags — Cinema 4D Command Plugin
Удаляет все теги с выделенных объектов.
Кнопка активна только если выделен(ы) объект(ы).
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068910
PLUGIN_NAME = "Clean All Tags v1.0.1"
PLUGIN_HELP = "Удалить все теги с выделенных объектов"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAAEoklEQVRYhe1WfUxVZRx+fi/cvCAqXmCN3RIVHFpDCOwKKuNy73vVJDTnF5Kmmaz+cbXZdLq1aP2hm7LVWP2RqYixuDQ2wCUf93AhR44MSdAMIiI/lo4FsQSucO85v/4Q5F64fmZbWzzb2c45z/P+nuf9ve95d4BJTGIS/3fQ6A1LuQtEkejtfZ/On3f/G2aclKSDwfABmG+QouQDgBhjOQjM+2Aw1LPFYnzi5haLEQZDPZj3gTlo9D35iKRco1FgkQadaArJOdUWlNl1V0hwbi+iGj60IANCS53goJKT9rTV4GJnBtiX3/Hd2VmflhavnOJxB4I5h2pr7aOc8BaSopRXzzhkHwgwYPGt/I3Wvtw0Io0A6MEoLdjCq0GcDiaL7/SEHgKlnBe7GhqnA3d4AeBYcWHyEfvJrCszDTPeXJe939t8QgcAoGAzH9Zpg6FLBvJenn37zNMe0jsDhXvDiYiqZdBQlDl/bbUhuK0HoOfuVAjIpt2XrnFe7GowFSWk5Fe3TJvTEzbYv9B+4sg8a0d7GICiufs/rOgKjzgKjdcjYV613w6Mwi2CZ30z/b2TrcHZlYLdqVDVC9tu2roBFAwMG6MAzAFz453L8xIA0O72ChAKZru6o8wd7fFtB3IXpHV2hBYnvFhCirKly5JSAqAARDZvL78BQOgCYPoh5PWp13SL1wBwA6hP7s9/fkTRBYIJBBNUz+mxpcBQRvNPYTWf5SepRPpVObsubt66Y7c3P94q0G8Axq3tX1La3UcpE8F8PHawYq2rPaQHieIs7buc5jPEbNbje215Tk/jnJZIY1d8981Fjg2ZvX7r+8x1HAo28+EhnbaiNdrlGtbxtDEhY2tr2aylPYXBnqlQqy1RV3vD9UMAENo39JS59nfj9L+Gp3xlir+dtfGtQY1Et1e8PhAugJEExhnEx7x7zw60Rvd3Xo/wzNcPiz+muEXfWFMIhQvXXr3quRG07pzTuLLyetS5xeE3VZ3QUr7tjtQIqJfGa58kp97SSPguLXM0QAkgOg5C3X07gJZfDoOQhrhoE4jYX9vYYjGCqARES0ZeNUHT1pPTecWfHnV1gQh7thlAJRbG7PWmJm5C4kiAf76XuV/QxHn4ID3dA/BFgJ8ZT/n/Cu4DltIMIZpAFAfmLACvgDkGQjSxzbb8Ues9dAAGiG22vQAUAH1Q1RSqrbWTopSDyATgBpirWMqDnJv70HUfSshSzoDVWgrmgwCKIcQiqqv7cZQnh6MDHo8JRMcA7EVDwylescLwRAKwxZIIoBlEq0D0DinKFqqpGRivo/r62+Rw7ASwDUA6VPUCS5n8jwKwlK9BiAYAOgBmcjg+flBBUpRCaNoyjJyebLO9/cgBQoaGA9hm+xzACQB1CAhIIEVpfJD53RBOZzOARDCfBvNHLOUXM10u/6fueKSWVR1pz37VxVJqj7qhxmN047KUnl83ZblsJRXHJ4T1GSDlGk2Iwj/1QdN2btr6W1ncC02Pa+6NjMutCUftJ2MiBvoHhaq+4feHhK3WPQDKBPOlvFTz0rK4eLvfao+BrxfElR+wLjcL5hYQFY94AfgP/JRO4m/EBO51+ENKIQAAAABJRU5ErkJggg=="
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
