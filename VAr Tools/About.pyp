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
PLUGIN_NAME = "About"
PLUGIN_HELP = "Информация о наборе плагинов VAr Tools"

AUTHOR_URL  = "https://github.com/vladvarp/-4D-Plugins"

# --- ID элементов диалога -----------------------------------------------------
ID_BTN_WEBSITE = 1001
ID_BTN_CLOSE   = 1002

# --- Текст о плагинах ---------------------------------------------------------
ABOUT_TEXT = """\
VAr Tools - набор инструментов для Cinema 4D,
созданных для ускорения повседневной работы.

------------------------------------------

  * Object Renamer PRO v2.4
    Плавающая немодальная панель с операциями
    переименования, выделения и сортировки объектов.
    Каждое нажатие кнопки создаёт ОДИН шаг
    отмены → Ctrl+Z откатывает ВСЕ изменения.

  * Camera Resolution Manager v1.3
    Управление разрешением рендера для каждой камеры

------------------------------------------

  Axis

  * Axis2Bottom v1.1
    Смещает ось (pivot) выделенных объектов
    в нижнюю центральную точку их bounding box.
    По X и Z — центр, по Y — нижняя грань.

  * Axis2Center v1.1
    Смещает ось (pivot) выделенных объектов
    в геометрический центр их bounding box.
  
  * AxisDrop v1.1
    Опускает ось (pivot) выделенных объектов
    на нижнюю грань их bounding box,
    сохраняя X и Z позицию оси нетронутыми.
    
------------------------------------------

  Location

  * Drop2Floor v1.3
    Опускает выделенные объекты (и их иерархии)
    на уровень пола (Y = 0).

  * Drop2Floor 0(XZ) v1.3
    Опускает выделенные объекты на уровень пола
    и дополнительно центрирует их по осям X и Z.

  * Center2Parent XZ v1.1
    Центрировать по X и Z в позицию родителя
    (мировое пространство, Y не меняется)

  * Center2World XZ v1.1
    Центрировать выделенные объекты по X и Z в
    мировом пространстве (Y не меняется)

------------------------------------------

  Clean

  * Clean Nulls v1.0
    Удаляет все Null-объекты без тегов из сцены.
    Дочерние объекты перемещаются на место
    Null-а, сохраняя мировые координаты.

  * Clean Empty Nulls v1.0
    Удаляет пустые Null-объекты без тегов
    и без дочерних объектов. Работает
    в несколько проходов для вложенных цепочек.

------------------------------------------

  Objects

  * HierarchyFilter v1.4
    Объект-Ноль с расширенными UserData для
    фильтрации и обхода иерархии. Используется
    совместно с Xpresso для динамической выборки
    дочерних объектов.

  * TargetCamera v1.4
    Создаёт камеру с целевой точкой (Null-объектом),
    на которую камера всегда смотрит. Таргет следует
    за камерой при переименовании.

    Primitivs

    * TriCube v1.1         
      Куб с треугольной сеткой.

    * HexSphere v1.2       
      Сфера с настраиваемым числом углов (3–16).

    * DiamondCylinder v1.1 
      Цилиндр с ромбической сеткой (смещённые ряды).

    * TriTorus v1.1       
      Тор с треугольной сеткой.

    * BrickPlane v1.0
      Плоскость с кирпичной сеткой (running bond).

------------------------------------------

  Deformers

  * PolySubdivider v1.0 (Experimental)
    Эксперементальный аналог Divider: несколько
    алгоритмов разбиения полигонов с возможностью
    лёгкого добавления новых типов.

------------------------------------------

Версия: 2.6
Автор:  V.Ar Production
"""


# --- Диалог -------------------------------------------------------------------

class AboutDialog(gui.GeDialog):

    def CreateLayout(self):
        self.SetTitle("O плагине - VAr Tools")

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 0)
        self.GroupBorderSpace(12, 12, 12, 4)
        self.AddStaticText(0, c4d.BFH_CENTER, name="VAr Tools")
        self.GroupEnd()

        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupBorderSpace(12, 8, 12, 8)
        self.AddMultiLineEditText(
            1000,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=460,
            inith=300,
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
            defaulth=460,
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
