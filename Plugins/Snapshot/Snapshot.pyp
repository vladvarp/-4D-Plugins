from typing import Optional
import c4d # type: ignore
from c4d import plugins # type: ignore
import os
import base64
import tempfile

PLUGIN_ID   = 1068924
PLUGIN_NAME = "Snapshot"
PLUGIN_VER  = "v1.7.1"
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
    "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"
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