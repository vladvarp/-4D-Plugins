# -*- coding: utf-8 -*-
"""
AboutVArTools - Cinema 4D Command Plugin
Отображает окно «О плагине»
и кнопкой-ссылкой на сайт автора.
"""
import c4d # type: ignore
from c4d import gui # type: ignore
import webbrowser
import os
import base64
import tempfile

PLUGIN_ID   = 1069098
VERS = 'v1.14'
LABLE =  'Action Recorder'
PLUGIN_NAME = "About"
PLUGIN_HELP = "Информация о плагине Action Recorder"

AUTHOR_URL  = "https://vladvarp.github.io/-4D-Plugins/web/plugins/action-recorder.md"

# --- ID элементов диалога -----------------------------------------------------
ID_BTN_WEBSITE = 1001
ID_BTN_CLOSE   = 1002

# --- Текст о плагинах ---------------------------------------------------------
ABOUT_TEXT = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTION RECORDER  —  Cinema 4D                                       ║
║          Аналог операций Photoshop для Cinema 4D                             ║
║                                                                              ║
║  3 кнопки в меню плагинов:                                                   ║
║   1. «Лог событий»  — плавающее окно с записью всех команд в виде кода       ║
║   2. «Менеджер операций» — создание, удаление, запуск, коллекции             ║
║   3. «Воспроизвести последний» — быстрый запуск последней операции           ║
║                                                                              ║
║  Операции хранятся в:                                                        ║
║    ~/Documents/ActionRecorder/<Коллекция>/<action>.py                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Автор:  V.Ar Production
"""


# --- Диалог -------------------------------------------------------------------

class AboutDialog(gui.GeDialog):

    def CreateLayout(self):
        self.SetTitle("O плагине - " + LABLE + " " + VERS)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 0)
        self.GroupBorderSpace(12, 12, 12, 4)
        self.AddStaticText(0, c4d.BFH_CENTER, name=LABLE)
        self.GroupEnd()

        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupBorderSpace(12, 8, 12, 8)
        self.AddMultiLineEditText(
            1000,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=950,
            inith=150,
            style=c4d.DR_MULTILINE_READONLY | c4d.DR_MULTILINE_MONOSPACED,
        )
        self.GroupEnd()

        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.GroupBorderSpace(12, 8, 12, 12)
        self.AddButton(ID_BTN_WEBSITE, c4d.BFH_SCALEFIT, name="Открыть сайт")
        self.AddButton(ID_BTN_CLOSE, c4d.BFH_RIGHT, initw=90, name="Закрыть")
        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetString(1000, ABOUT_TEXT)
        return True

    def Command(self, id, msg):
        if id == ID_BTN_WEBSITE:
            try:
                webbrowser.open(AUTHOR_URL)
            except Exception:
                c4d.gui.MessageDialog(
                    "Не удалось открыть браузер.\nСкопируйте адрес вручную:\n\n" + AUTHOR_URL
                )
        elif id == ID_BTN_CLOSE:
            self.Close()
        return True

# --- Команда ------------------------------------------------------------------

class AboutCommand(c4d.plugins.CommandData):

    def Execute(self, doc):
        dlg = AboutDialog()
        dlg.Open(
            dlgtype=c4d.DLG_TYPE_MODAL_RESIZEABLE,
            pluginid=PLUGIN_ID,
        )
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED

# --- Иконка: рисуем программно 32x32 -----------------------------------------

_ICON_B64 = (
    "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"
)

def _make_icon():
    png_data = base64.b64decode(_ICON_B64)
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        bmp.InitWith(tmp.name)
    finally:
        os.unlink(tmp.name)
    return bmp


# --- Регистрация --------------------------------------------------------------

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME,
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = AboutCommand(),
    )
