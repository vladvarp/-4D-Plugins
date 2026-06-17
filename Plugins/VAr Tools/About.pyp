# -*- coding: utf-8 -*-
"""
AboutVArTools - Cinema 4D Command Plugin
Отображает окно «О плагине» с описанием набора VAr Tools
и кнопкой-ссылкой на сайт автора.
"""
import c4d
from c4d import gui
import webbrowser
import os
import base64
import tempfile

PLUGIN_ID   = 1068833
VERS = 'v2.32.2'
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

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEuklEQVR4nMWXX4hUdRTHP+femV11V3Ptj7qmIYKKaf7BCGQhth6MKCQogx4iMowefOtZX6IiCCwS8iGSoCVmQSLIp+IGSqDN6sydcWfdmdk/s62rrtbKro7OzL2nhzv37szOzM6uIh0YmPu7v98533PO93fOufA/izzwSdXqsyL6sGCay7FjBpYVIqJmHUAGloZQNRajcmER8Lw1EHGCNcsKsW5LBwAFM8/21TNz9gsi7sMDUDUDw7GBjYRb38Mw9+E4axCW4boCFBC5hWFGMeVHtmy4UHO2gYTmNW5ZIURK9KU6WbHia0R2UigkMY0eigUbd2YMd5nSIo9hhnfhOK9gtnxP+uo094sfI3IOVaPMj0VyRMt5vjx0gFRuguy1r+gfWdv0XDLZQnr8CFfGJujPHS3rMmpIuyDjdvoIA7kJEunuqndal4TV6319naRG+7CzPYAXzUUZT2RfJ56eIhp9orweCrxQNTgz2Eoi8yX9Iz8TyzyFqgTkU501Fs/8iZ09vjAQfqj6R9ZiZ/4hlu0CIBoN1wBMZl7ixowy7SrxzKcByOqIGFwaXomdvUEi+1rV+bLMvbOCiFIsnQT5iV2bzhGNhtm7t1ixx0VVaHET3Jg8y9XxMYTTwbtAkziAsHvjFOp+gOq3DA8vCc7X8d5bTGY3YGfGuTj4ZEPy+GuRiIlltdeN5tyI2Zko8ew7c6NQmRMTKOFwCLjAns2T5XtcW0xEFFUpezlTvmqNio7HjcTQKdDDQE/ly8oUePdU3C7E/SUgVCPxa//Jk+EmFc9BRHHNX4GniU20IeL4UfQAeA8usVgbKmuR0MWygfqK/bpvZ3rp2m9jZ1dX3IJaoKrC3avXEO5h3NkaRKYqAiIK7W0IS5HQWFVUqo17Nf7x3HLgVVat2orq9jLgRo1I2Lcvj8g0wjMA9M4FMGsA7sw0r1qOqyh3yOddxC013e+D12qnqgHodAGRAstCKxek0OuQBiLNACvRaBilFdF/awF4eTLYvXsKuAnmLrwcLaq31zetXm1p6ViFsAJtiQPwlsevSgP+/xiq+/Hy/+ATU6VeVQH3RWCKHRtuV3TIKgAe40VOAS8zONhKw6oViKLq/eYTEUWMd8HtLV/ZwG7lLXBRNdix6S9Up7knh8ubazsfgGkISBjTFNBw3T2epw7JwW0oXZT4ruxQMKTUy7EgfATyCXZ2NeDWzICqwnI3D/o39/IObigXRKRyjw/eMXrA+Zw9myfxiDtPxPw6HRs8ip1O1KzPKoe+VCfnLz9bteZ77ndGO3OCeMaq0TGvWP7hdA8Do39w1u4IFFtWqKbq+c+qZlXPvzz8DXYmiT3asbipyFPmpad/+DipXI7M+Bu1QK1Q1Qzgy5WhnQyMnic1+huXhlcG4OtIY0SVo3V86ABtS79AdZJCsZdW4wy/Xx/hw4o5ITXaSbHUzZLWNzHM53FKJ9iy/rPAeIOG1TwklhWiu7uEdSzEmkNvo/o+hqyjVCqi3EVdEAljGMsxjJsYcpr7xR94btP1stc6H+kWlpNIxOTgwdn5Pplsx2jfjBFeDyUoure5m0/wwrZbwZ4FfBMsTnySRSKNmVxJ0kcqPkn9UTwSMR+90Uck/wGFl23zKpoE/wAAAABJRU5ErkJggg=="
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
