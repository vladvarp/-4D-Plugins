from typing import Optional
import c4d
from c4d import plugins
import os
import base64
import tempfile

PLUGIN_ID   = 1068924
PLUGIN_NAME = "Snapshot"
PLUGIN_VER  = "v1.6"
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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAHzWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIgeG1sbnM6ZGM9Imh0dHA6Ly9wdXJsLm9yZy9kYy9lbGVtZW50cy8xLjEvIiB4bWxuczpwaG90b3Nob3A9Imh0dHA6Ly9ucy5hZG9iZS5jb20vcGhvdG9zaG9wLzEuMC8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIiB4bXA6Q3JlYXRvclRvb2w9IkFkb2JlIFBob3Rvc2hvcCAyNi41IChXaW5kb3dzKSIgeG1wOkNyZWF0ZURhdGU9IjIwMjQtMTItMjJUMDE6NDU6MTQrMDM6MDAiIHhtcDpNb2RpZnlEYXRlPSIyMDI2LTA2LTEyVDE3OjUwOjU5KzAzOjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDI2LTA2LTEyVDE3OjUwOjU5KzAzOjAwIiB0aWZmOkltYWdlV2lkdGg9IjMyIiB0aWZmOkltYWdlTGVuZ3RoPSIzMiIgdGlmZjpDb21wcmVzc2lvbj0iMzI3NzMiIHRpZmY6UGhvdG9tZXRyaWNJbnRlcnByZXRhdGlvbj0iMiIgdGlmZjpPcmllbnRhdGlvbj0iMSIgdGlmZjpTYW1wbGVzUGVyUGl4ZWw9IjQiIHRpZmY6UGxhbmFyQ29uZmlndXJhdGlvbj0iMSIgdGlmZjpYUmVzb2x1dGlvbj0iNzIvMSIgdGlmZjpZUmVzb2x1dGlvbj0iNzIvMSIgdGlmZjpSZXNvbHV0aW9uVW5pdD0iMiIgZGM6Zm9ybWF0PSJpbWFnZS9wbmciIHBob3Rvc2hvcDpDb2xvck1vZGU9IjMiIHhtcE1NOkluc3RhbmNlSUQ9InhtcC5paWQ6N2Y5NGNkNWYtZGZkYy02ODRkLWE0ZTUtOTA4Y2UzNTM3NjYwIiB4bXBNTTpEb2N1bWVudElEPSJhZG9iZTpkb2NpZDpwaG90b3Nob3A6NTI3Zjg0OGItOWI5OC0wMjRkLWFiOWItNzU5MDBmN2JiZjUwIiB4bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ9InhtcC5kaWQ6YWNhMzhmYTctYjVhYy02OTRhLTgxOGUtY2JlNDE5YmI5NWNjIj4gPHRpZmY6Qml0c1BlclNhbXBsZT4gPHJkZjpTZXE+IDxyZGY6bGk+ODwvcmRmOmxpPiA8cmRmOmxpPjg8L3JkZjpsaT4gPHJkZjpsaT44PC9yZGY6bGk+IDxyZGY6bGk+ODwvcmRmOmxpPiA8L3JkZjpTZXE+IDwvdGlmZjpCaXRzUGVyU2FtcGxlPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOmFjYTM4ZmE3LWI1YWMtNjk0YS04MThlLWNiZTQxOWJiOTVjYyIgc3RFdnQ6d2hlbj0iMjAyNC0xMi0yMlQwMTo0NToxNCswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjb252ZXJ0ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImZyb20gaW1hZ2UvdGlmZiB0byBpbWFnZS9wbmciLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249InNhdmVkIiBzdEV2dDpp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"
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