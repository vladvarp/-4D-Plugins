# -*- coding: utf-8 -*-
"""
CleanAllTags — Cinema 4D Command Plugin
Удаляет все теги с выделенных объектов.
Кнопка активна только если выделен(ы) объект(ы).
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068910
PLUGIN_NAME = "Clean All Tags v1.0.2"
PLUGIN_HELP = "Удалить все теги с выделенных объектов"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAFj0lEQVR4nO2ay28bVRSHv3PvjB0nTlLEQxWFBQgBpZVKE2BBkaougC2bZIVQi3CilgUgsU+yYFuQqBBJKE2bXYKExB9AU4mHBKShDyo2IBAIIQFN86pjz9w5LGyHtCSpPQ52LeazLFny3Dvn/HzuPb+ZMSQkJCQkJCQkJCQkJCT8/5B4w1TQ7Q0kFiJNiELVNP6kmzCltt4paqsAVSmproaf6eZHFG8hZhXFJOxW7lwQlrtXeVry/8QUj+qDVzWIRHylT+JzEscuXI1zbBeGiBTXWWaYA/LhWmwxqC541dJxM6TJcIFuHuaqgm187gBEQBsQoRR4jAPyPUNqGKldBK/qI0WUL661I907uUbE+TkIQkEaLIIIhA72Puq4r9sj4H7ge/bEq8TqBQBwKJYQwRCESuiaJEAIqEFRIKhnutoEKIewFkjl3UjWn1PKrzq4fVpak6i9AqRceELzKwDA1mfJahPAImhZAheV1qI0uIgqe4AqQEREXWaoegFUhc//DDBABmHv7gitdwXGJFLo6jBYQFisZ6rqBBBRVA3P3L3E5/oqcIK7unbgmiSBEOETMM+7/Mr5shFycaaKswdcJmKZiDtwNMMHKgL4BERcoF9cPdcncZzgJbI8xHwQIcbQ8MtCAY2UtC9YYJXdjXaC97CI8u1lIXRN6AJA6IS9jzh2dVuKzXCCBiEItDkCrHUBSZxg4gTrJ3GCNR2dOMHECSZOMHGCiRNMnGDiBNcCaYIPMFKKICpFUrUT1KGS6ZMRblgmcQRoGgYl0jSoofIsqJodSIcwlcS13LekPLRFnKCWknd38Hr2Y/bxE0fMCQyKocBW/U/PHvTk0LlQT/W8jpF9IrNHoCSECLoNTvC/F8CgoGneaP+I49kpcMsEK28xwBAdts27zsaVsC75HG3mbXxBT/cYJDzG8MW8Es8JRqQR9uwOIWqMD1ZFrPD4yifw1wKrdqfm5idEfulwuXvf/F1B+plmev2Q9cm32zHyroCxaaCXQphmmOsMx3k4+qUeoZ33saS2O8/NKO97RApjv71N7q9TFIttYcpfMQR2TA5fOqpTWPqIRFAd7fVlcDZYS37VFWizaYLoa1Z4VgZnFypLIN7j8c/0EbLhLvJe1CgrbMMQz6zaQirripefeNHPmpfDZS16nTbFUnFcDs8N6FSfhe+s9F8pbpj8YvF5OXZpfv2mWHvwdTyKrhehdAPDAXqmd4wOm2MxyNPlZ1gJxuWluQEAnegZIGNHN0xeh4zISLR+ztopeW+5YdE1iIN3z8jMH++p9E87ndg/RqdfEmGHn2EheAeVC3TYU+RvnTw041JmG1BFmO4zayJ0p3JcK4akrIcABefI+pZV9w1Lxec2Sx5aVAC4SYTTPcfxzWsUXCnBlLWofko+3y+5K1dVMSJsuGxb9p6gCMqDP5bid9GFNYeCRHgihPqD5K5c1bMHPbYwjC0rgI72+vLEbKAnewbI+hMUIsW3Phmb4noY0OkN6OnecTl0LmS6z6huXO0tKYCePeit9fmsHSXvCnR4HkE0w6obo8v3WQpXydpXdGL/mPRPu81EaDkB/uXwKq2u4L6mIC/I4fODrLgP6PTaWAzydPq5rURoKQE2Tb7S6gZnF3S015eXZnMsBeN0+ZlbidAyXaCyk2/p8HTIwIje0CIrPuFmsxTLCjcJVQzDwAP7XyNtj1OICmQ2Nzn/8gmdfo6lIE+Hl2HFTWLCo/xwMc8It9H/fm/Fnj5B2Ycv0Ga2treC0jcd6VSflcNzAywF43R4GZyCsJ9Ce5rh8n2NVkBBKre0dKLnjE72XtRT+3YAlMp+k3GKlC6QQE/3TOpk70WdfKqr8l0DQt8+KgHrEEZPPJatfK5mXEXAWsbd9sT9BVvul78ZBYmTxGbj/ga222D2T6JFzwAAAABJRU5ErkJggg=="
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
