from typing import Optional
import c4d
from c4d import plugins
import os
import base64
import tempfile

PLUGIN_ID   = 1068924
PLUGIN_NAME = "Snapshot"
PLUGIN_VER  = "v1.7"
PLUGIN_HELP = "Создаёт снепшоты анимации по кадрам"

class SnapshotPlugin(c4d.plugins.CommandData):

    def Execute(self, doc: c4d.documents.BaseDocument) -> bool:
        self.main(doc)
        return True

    def GetState(self, doc: c4d.documents.BaseDocument) -> int:
        # Плагин активен только если выбран объект
        if doc.GetActiveObject():
            return c4d.CMD_ENABLED
        return 0

    def main(self, doc: c4d.documents.BaseDocument) -> None:
        
        # ========Задаем количество копий========
        # Запрашиваем новое количество кадров
        user_input = c4d.gui.InputDialog("Введите новое количество кадров:")
    
        if not user_input:
            #c4d.gui.MessageDialog("Вы ничего не ввели.")
            return
    
        try:
            new_frame_count = int(user_input)
        except ValueError:
            c4d.gui.MessageDialog("Введите корректное целое число.")
            return
    
        if new_frame_count <= 0:
            c4d.gui.MessageDialog("Количество кадров должно быть больше 0.")
            return
    
        # Получаем текущее количество кадров
        fps = doc.GetFps()
        old_frame_count = doc.GetMaxTime().GetFrame(fps)
        if old_frame_count == 0:
            c4d.gui.MessageDialog("Сцена не содержит анимации.")
            return
    
        # Открываем блок отмены (один Ctrl+Z отменит всё)
        doc.StartUndo()

        # Коэффициент масштабирования
        scale_factor = new_frame_count / old_frame_count
    
        def scale_all_keys(obj):
            """Масштабирование всех треков (ключей) объекта и его тегов."""
            while obj:
                # Масштабируем все треки объекта
                track = obj.GetFirstCTrack()
                while track:
                    scale_track_keys(track)
                    track = track.GetNext()
    
                # Масштабируем все треки тегов объекта
                tag = obj.GetFirstTag()
                while tag:
                    track = tag.GetFirstCTrack()
                    while track:
                        scale_track_keys(track)
                        track = track.GetNext()
                    tag = tag.GetNext()
    
                # Рекурсивно обрабатываем дочерние объекты
                scale_all_keys(obj.GetDown())
                obj = obj.GetNext()
    
        def scale_track_keys(track):
            """Масштабирование всех ключей в заданном треке."""
            curve = track.GetCurve()
            if curve:
                for i in range(curve.GetKeyCount()):
                    key = curve.GetKey(i)
                    old_time = key.GetTime()
                    scaled_time = c4d.BaseTime(old_time.GetFrame(fps) * scale_factor, fps)
                    key.SetTime(curve, scaled_time)
    
        # Масштабируем все ключи в проекте
        first_object = doc.GetFirstObject()
        scale_all_keys(first_object)
    
        # Устанавливаем новое количество кадров
        new_time = c4d.BaseTime(new_frame_count, fps)
        doc.SetMaxTime(new_time)
    
        # Обновляем сцену
        #c4d.gui.MessageDialog(f"Ключи анимации масштабированы. Новое количество копии: {new_frame_count}.")
    
    
        # ========Задаем количество копий========
        c4d.CallCommand(12501) # Установить на первый фрейм
    
        fps = doc.GetFps()
        total_frames = doc.GetMaxTime().GetFrame(fps) # Расчет кол-во кадров проекта
    
        # Проверка
        active_obj = doc.GetActiveObject()
        if not active_obj:
            c4d.gui.MessageDialog("Пожалуйста, выберите активный объект!")
            return
    
        # Создаём нулевой объект
        null_obj = c4d.BaseObject(c4d.Onull)
        null_obj.SetName("Снепшот")
        doc.InsertObject(null_obj)
        #doc.SetActiveObject(active_obj)# Возвращаем выделение на исходный объект
    
        # Скрипт
        for frame in range(total_frames + 1): # Количество копии = количеству кадров проекта
            doc.SetTime(c4d.BaseTime(frame, fps)) # Текущий кадр
            doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE) # Принудительно обновляем сцену с указанием всех флагов
            #c4d.CallCommand(12233) # Текущее состояние в объект
            c4d.CallCommand(12144) # Объединить объекты
    
            # Получаем созданный объединенный объект
            merged_obj = doc.GetActiveObject()
            if merged_obj:
                merged_obj.InsertUnder(null_obj)  # Помещаем в папку "Снепшоты"
                merged_obj.SetName(f"Снепшот_{frame}")  # Переименовываем объект под текущий кадр
    
            doc.SetActiveObject(active_obj)# Возвращаем выделение на исходный объект
            print(f"Объект создан на кадре {frame}.") # Лог
    
        c4d.CallCommand(12501) # Установить на первый фрейм
        doc.SetActiveObject(null_obj) # Выделить папку "Снепшот""
        doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE) # Принудительно обновляем сцену с указанием всех флагов
        c4d.CallCommand(16768) # Объединить объекты и удалить
        #c4d.gui.MessageDialog("Выполнено!") # Сообщение

        # Восстанавливаем исходное количество кадров
        doc.SetMaxTime(c4d.BaseTime(old_frame_count, fps))

        # Закрываем блок отмены — весь плагин отменяется одним Ctrl+Z
        doc.EndUndo()
        c4d.EventAdd()

# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAADGUlEQVRYhe2WS2hTURCGv7mJphVFa3DT4DuxtrEFH6gVRETqSnChgqgbuyi48EkV6krcqNhWUKS0i2p9g4IbwYWLYhdufMdHlVwRtRVELQWr8ZGccWESm+SmSWOz84dLbnLm/PPf+edMLvxHEaDNlXXaXFmXT6y7SBI2xm9u5Yq0iiMgf6RUoHO7TnP9YHa24JiH1/Vn5GMhibSlYhNqDUpjb0pVUisQIWBgjrHwZFwwhwiBUSdWRI9XHEblPKol6esZPaCGt/WX5E76752bdUX+aeUagB4Kjqcl1oVQB7JW9vf25BSQkThhi1AO0LVFlw5fd7IlUWY9XlEDMgsjtXKgN+zEn/sURAgYixlo/LuFJ7lm8BHBDTj2hex/GQJqR6LP6xiq4W3ifrg9+djyZx4kj2VC2rVElQqaA4XYkg0ZAlwuylMI40kAYjHeA6OyJf6kWQdSqoBSwuYXLiSF0B1P0k8pyUb6F1uGQ3IFJAjrrzgnadvwYdXdeV/XIAwATBlyeQEGJ8Y+J0mUqVh6mmr/9XT+vHpgJFteTI+sR3QZ8BDEztytfoSFGKJAAQJy2PJzvOlDVFBZgujZ1pMz70G8YiG7AdiAcA/0sxN9TguckGJLKHwxTnUbaPP3lZw8eM53tf7gqwVAG8IeVJcDUBPYms5V8L9hwpayIbe3bMjt7To699G8dyXHbN/33ft2vjmcTF7tPzUST2ECSgkb4YOx8IgRlxhxGQtP02XfTe+XcbcGJ0XXIHo9V/KxQSh8MWlDyG4gZMd4Yl+Of+7KiEnD2L0R/Wm4v2UP2d0obTyxQTXrtrF5IxL8pHte4+8AdqCcAKnItvXfK6DiBZYCD1FZSejVyrSAx8BiVD4VR4BFO0bciUmImlJE1qF6A7EiIDbKAJa2O213nAPaWhXEiErjs+ejFvTgRTludz/RqI9F89/n4ssQoM3BKiX2VLFYvezI1Z7JwcHRKZAJoNtALoB+WzXwtKz7ftNGFBVXdIHsDfcOj85igaiTuPyg34AO+Nv5qoKQ/SRkUjQHq/REoLIwAcXn+48xxW+nclN7D4gRBgAAAABJRU5ErkJggg=="
)


def _make_icon():
    """Декодирует встроенный base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(_ICON_B64.replace(" ", ""))
        fd, tmp = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, data)
            os.close(fd)
            bmp.InitWith(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return None
    return bmp

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str=PLUGIN_NAME + " " + PLUGIN_VER,
        info=0,
        icon=_make_icon(),
        help=PLUGIN_HELP,
        dat=SnapshotPlugin()
    )