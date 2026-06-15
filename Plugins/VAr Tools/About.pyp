# -*- coding: utf-8 -*-
"""
AboutVArTools - Cinema 4D Command Plugin
Отображает окно «О плагине» с описанием набора VAr Tools
и кнопкой-ссылкой на сайт автора.
"""
import c4d
from c4d import gui
import webbrowser

PLUGIN_ID   = 1068833
VERS = 'v2.29.1'
LABLE =  'VAr Tools'
PLUGIN_NAME = "About"
PLUGIN_HELP = "Информация о наборе плагинов VAr Tools"

AUTHOR_URL  = "https://vladvarp.github.io/-4D-Plugins/web/plugin.html?md=plugins%2FVAr_Tools.md"

# --- ID элементов диалога -----------------------------------------------------
ID_BTN_WEBSITE = 1001
ID_BTN_CLOSE   = 1002

# --- Текст о плагинах ---------------------------------------------------------
ABOUT_TEXT = """\
VAr Tools — набор практичных утилит для Cinema 4D, заточенных 
под реальный рабочий процесс. Вместо того чтобы делать одно
большое всё-в-одном, каждый инструмент решает конкретную задачу:
переименовать объекты пачкой, сбросить ось на пол, почистить
сцену от мусорных нуллов, сгенерировать нестандартную геометрию.

Особенно полезен на стадии подготовки сцены и финального клинапа,
рутинные операции, которые обычно съедают по несколько минут,
делаются в один клик.

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
            initw=260,
            inith=120,
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
            defaultw=500,
            defaulth=260,
        )
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED

# --- Иконка: рисуем программно 32x32 -----------------------------------------

def _make_icon():
    """
    Рисует иконку 'i' (информация) на синем круге.
    Без внешних файлов - совместимо с R26+.
    """
    SIZE = 32
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()

    bmp.Init(SIZE, SIZE, 32)

    BG     = (40,  40,  40)
    CIRCLE = (60, 130, 220)
    TEXT   = (255, 255, 255)

    cx, cy, r = SIZE // 2, SIZE // 2, SIZE // 2 - 1

    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= r * r:
                bmp.SetPixel(x, y, CIRCLE[0], CIRCLE[1], CIRCLE[2])
            else:
                bmp.SetPixel(x, y, BG[0], BG[1], BG[2])

    # Точка над буквой 'i'
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            bmp.SetPixel(cx + dx, cy - 7 + dy, TEXT[0], TEXT[1], TEXT[2])

    # Палочка буквы 'i'
    for dy in range(0, 9):
        for dx in range(-1, 1):
            bmp.SetPixel(cx + dx, cy - 2 + dy, TEXT[0], TEXT[1], TEXT[2])

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
