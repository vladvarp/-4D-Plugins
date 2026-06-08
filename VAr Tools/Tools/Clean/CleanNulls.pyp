# -*- coding: utf-8 -*-
"""
FlattenNulls — Cinema 4D Command Plugin
Удаляет все Null-объекты в сцене, кроме тех у которых есть теги.
Дочерние объекты удаляемого Null-а перемещаются на его место в иерархии
(к его родителю), сохраняя мировые координаты.
"""
import c4d
import base64

PLUGIN_ID   = 1068831
PLUGIN_NAME = "Clean Nulls v1.0"
PLUGIN_HELP = "Удалить все Null-объекты (кроме тегованных), сохранив содержимое"

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA60lEQVR4nGPU0NBgGEjA"
    "NKC2j1gHbBER+U9zByBbgk0cRtPEAeiWYHOUz5s3jEQ54PoWrhOkysEMx+UYZHkWZI09"
    "PT1YDKxDES8pKbEg5GiYJYQsx3AANgu8t3CdgIlhdyBxjsBmOQMDjXMBvjQAA4zIJSE2"
    "H3pr1DFsvdGE1QJ8chodHeYwNr6QwHAAsXGMD+CyjKxcQA6AGY4e59gcQ7M0cKOi4iQx"
    "jsPIBTBg02NzB13sSMkRFUJyxADkkBiZldGoA0YdgAxwZkN82YqULEcIDHgIDLgDMKKA"
    "1DqfUsA42jEZdcCoAwbaAQCvlnojUpHkNgAAAABJRU5ErkJggg=="
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