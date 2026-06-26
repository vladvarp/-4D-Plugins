# -*- coding: utf-8 -*-
"""
FlattenNulls — Cinema 4D Command Plugin
Удаляет все Null-объекты в сцене, кроме тех у которых есть теги.
Дочерние объекты удаляемого Null-а перемещаются на его место в иерархии
(к его родителю), сохраняя мировые координаты.
"""
import c4d # type: ignore
import base64

PLUGIN_ID   = 1068831
PLUGIN_NAME = "Clean Nulls v1.0.2"
PLUGIN_HELP = "Удалить все Null-объекты (кроме тегованных), сохранив содержимое"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAGjklEQVR4nO2aTWxcVxXHf+d9eDz1R1OKglQBEigbqETxTGMgRQop0IpdN/ayyqJ2aCTUIiG6HHvJgrSV2NiG2MZsYjcbVrAAJyokTosb6tC0CFJ2qBJSSWLF4/Gb9/4sZsbxjGfseWO/sS3mJ1nyfJxzzzn33HPPeTZ06NChQ4cOHTp06NDh/xHbV22SPdRq2lfd7dDfEpKxKG/TuIfvu0jOode/J+blVr1e0WP8S8fQlvdrv3OY9LOXIyA5mEX8Xsf5LOcxfkDACQxw+QRxjQJv8oz9DcmwmCmbtP4yrQWgYtyf9TwpLtLDExSAoPy5C6SAAgFFfspJ3mQBh2ELD4X+LcQ/Q/NyMYt4W9+nn99hPMFdiuSJKCKKiA0iVimygcvjvM41cgxb2FS6Jq2/hngZUClE7/AZjA9wOE5AhFF/YSEciqTwWOMMp+wq83Ib7lTS+usQNwMczETEj+jncwSEDY0DMIwIBxcDxsjJYYidzmrS+ussGI+IRXnAC6wjrKkMclhDeHyT7/F5zCJyDa+vpPXXEW6WSqX16MP4IgGGmpAv7ZJIkcLnBABP1nEsaf0NiF8E3SYNq6WSrgetv4bmBcxULlJ5jP/gIqzJ82YYAQEO/waoe06T1t+A+EXwlOWBK3RjQLSrhIjKd/Y/8fhHOdUbySWtv86C8ShFNuTn5AlxKF1FO1MkjQE/42kLdlkzaf3biBcAs4h5uTxjH1HgJzyOVy5B4abxJYSIEBscp4u7XOZbzJWbnMZ3dNL66y0ZKwCby5db1SXl6GYMF1gDonLKGg4pIA08YJ41fsi3uVt2cvfzmbT+LexlGCpdWzf0Xbp4jZBT+PQAEFDE+JCQNxi0i1Xfr9WxaUWdz/aqvwn29kBEW1Lulr5AgRO4gMcnvMXfGbfooZNl4yTjCi7fIawyuDTiqqqAtaK/7czL3fawooJqhpNW5vs4+ltg/x6J5eRsdmBDlTu8aof3Nt/vpr9F9veZYCPaON/HJflnam2e7+OSbAYcwHwfl6QzoO3zfXwDk6Xt831ckgvAAc33cUm+CLZ5vo9Lcgsc0Hwfl+SLYJvn+/gGJsu+zffK4SgX395W5faPSjNzTa9yR2JJRa6ryJIilqTyT8R1hVxXofydt5CciuxWByRMTfYvrcrtP5W/4i4px18lbknckMpOhyxJ3JT4SGJZl3hbjyEZklWc0HTmVc1mp8vOONLOzmjxtFcrV5atkvP22dX6WHlsNRvnhv5EF6/hcoruLfN9xIfcr57vhRmAZgZ+jG8XSLtoNrNh9t45zQ+50kJkdQqrFk97duZqUdOZEbqd1/ENzWYcrHiesZW8ACsfz/adjdKt4PIN+wMD9hwpvkLAs0Q8S4qv8Vu+zqBdrOz85jT45JAhniLtwr1gjV5vVDMDkza8ELIwtC0Tqpx/xJ2kEBUoNdJZCsUUY01UoUSJMd8LHh6BmYFJXR6UpgfWdHlQmhmYBChlQikImsj6AJrOjOjSSWk2s65LJ6XfZN/RRPbR0hLVATugokDT833ZYDMj0szAJH3+CPeDPP1+mtVgys7eHNX8kAsfuDZ8e2Nz59fDAt1uiiB6l/sbz9v5W/9VDsfGq6/igwtADCSMhSHHhhfCbUF4EEzZizdHATSTGSXtTtR1XjnHbHxbP3EkAgA7BOGYn+Ze8Aay9+lxp8k37zwcoQBAnSA82jXC3Y0iXa6HAYUwpNd3WQ//wurGc7s5D0csAFAThNnMBXznFQphycEu10X6I/n8sI3c/lTCMdu5/T7gfzOLjxniyx+X7A6j97HNAhrhmVHUHRu5/Wm5Edr1wjtyAdBE1renlwP9KjNKrz9DIRK+65N2u1grBvR5o5rNTtmZq8V6fUItRyoAWjzt2bnlQNOZEXrdCfJhgR7PI4iusB5O0u/7rBbX6XVf2qlZ2sqRCcC2Dq9y1RXCdynYC3b2vXM8CH9Jn9fN/SBPnz/STBCORAAaOl+56s4t39NE1rcXl0dYDabo99PNBuHQ3wKVSr5jh6ecA+NqqlkStnWAOtQBkHAYA7408Aop9wKFqEC6cZNTt1laDfL0eGkehHM4xZe5s5JnHLV/GmyVyjToG3Q7O3Z4ZoihhUjzQ66dvTnKajBFj5cmFBgDFB45BNNgDKqnwcyvNZdd0fRTxwBKad9ATlhpQALNZuY0l13R3GB/5bM2mL5/bI66ORz94qu9ld+bkasEMI7coafVHTxyO1+LwFpxYje5/wGJbd/rw3OwcwAAAABJRU5ErkJggg=="
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

def _is_removable_null(obj):
    """Null без тегов — кандидат на удаление."""
    return obj.GetType() == c4d.Onull and obj.GetFirstTag() is None


def _collect_children(obj):
    """Возвращает список прямых дочерних объектов."""
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


def _insert_after(doc, obj, pred, parent):
    """
    Вставляет obj после pred внутри parent.
    Аналог InsertObjectLast / InsertObject с правильной позицией.
    """
    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
    obj.Remove()
    if pred is not None:
        obj.InsertAfter(pred)
    elif parent is not None:
        obj.InsertUnder(parent)
    else:
        # Вставляем в корень сцены после всех объектов верхнего уровня
        last = doc.GetFirstObject()
        if last is None:
            doc.InsertObject(obj, None, None)
        else:
            while last.GetNext():
                last = last.GetNext()
            obj.InsertAfter(last)


def _dissolve_null(doc, null_obj):
    """
    Основная операция:
    1. Запоминаем место Null-а в иерархии (родитель, предшественник)
    2. Переносим всех детей на место Null-а, сохраняя мировые координаты
    3. Удаляем сам Null
    """
    parent = null_obj.GetUp()
    pred   = null_obj.GetPred()   # объект перед Null-ом (на том же уровне)

    children = _collect_children(null_obj)

    # Переносим детей в обратном порядке, чтобы InsertAfter сохранял порядок
    # (каждый следующий вставляем после pred, pred обновляем)
    insert_pred = pred
    for child in children:
        # Сохраняем мировую матрицу до переноса
        world_mg = child.GetMg()

        doc.AddUndo(c4d.UNDOTYPE_CHANGE, child)
        child.Remove()

        if insert_pred is not None:
            child.InsertAfter(insert_pred)
        elif parent is not None:
            child.InsertUnderLast(parent)
        else:
            # Корень сцены
            last_root = doc.GetFirstObject()
            if last_root is None:
                doc.InsertObject(child, None, None)
            else:
                while last_root.GetNext():
                    last_root = last_root.GetNext()
                child.InsertAfter(last_root)

        # Восстанавливаем мировые координаты
        child.SetMg(world_mg)

        insert_pred = child  # следующий встанет после этого

    # Удаляем пустой Null
    doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, null_obj)
    null_obj.Remove()


# ─── СБОР КАНДИДАТОВ ─────────────────────────────────────────────────────────

def _collect_nulls(root):
    """
    Собирает все удаляемые Null-ы обходом снизу вверх (листья первыми).
    Это важно: если внутри Null есть Null — внутренний обрабатывается раньше.
    """
    result = []

    def _traverse(obj):
        while obj:
            _traverse(obj.GetDown())
            if _is_removable_null(obj):
                result.append(obj)
            obj = obj.GetNext()

    _traverse(root)
    return result


# ─── КОМАНДА ─────────────────────────────────────────────────────────────────

class FlattenNullsCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        root = doc.GetFirstObject()
        if root is None:
            c4d.gui.MessageDialog("Сцена пуста.")
            return True

        candidates = _collect_nulls(root)

        if not candidates:
            c4d.gui.MessageDialog("Null-объектов без тегов не найдено.")
            return True

        msg = (
            "Найдено Null-объектов для удаления: {}\n"
            "Их содержимое будет сохранено.\n\n"
            "Продолжить?"
        ).format(len(candidates))

        if not c4d.gui.QuestionDialog(msg):
            return True

        doc.StartUndo()

        for null_obj in candidates:
            # Объект мог уже попасть в иерархию другого удалённого Null-а —
            # проверяем что он ещё жив (GetDocument вернёт None у удалённых)
            if null_obj.GetDocument() is None:
                continue
            _dissolve_null(doc, null_obj)

        doc.EndUndo()
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED if doc.GetFirstObject() else 0


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = FlattenNullsCommand(),
    )