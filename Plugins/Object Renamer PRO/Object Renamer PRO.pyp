# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║       OBJECT RENAMER PRO  —  Cinema 4D Utility Script            ║
║       Требуется Cinema 4D R20+                                   ║
║                                                                  ║
║  Плавающая немодальная панель с операциями переименования,       ║
║  выделения и сортировки объектов. Каждое нажатие кнопки          ║
║  создаёт ОДИН шаг отмены → Ctrl+Z откатывает ВСЕ изменения.      ║
╚══════════════════════════════════════════════════════════════════╝

РАЗДЕЛЫ
───────
  ВЫДЕЛЕНИЕ         – выделение по имени (поиск), тегу, типу, материалу
  МАТЕРИАЛ          – переименование по материалу; копирование имени обратно
  НАЙТИ И ЗАМЕНИТЬ  – замена подстрок в именах объектов
  ПРЕФИКС/СУФФИКС   – добавление и удаление префикса или суффикса
  АВТОНУМЕРАЦИЯ     – добавление порядковых номеров в конец или начало
  РЕГИСТР И ОЧИСТКА – смена регистра, замена пробелов/подчёркиваний,
                      удаление лишних пробелов, суффикс/префикс типа,
                      первый заглавный
  СОРТИРОВКА        – сортировка объектов в иерархии по разным критериям,
                      сортировка тегов на объектах

ОБЛАСТЬ ВЫДЕЛЕНИЯ (выпадающий список)
──────────────────────────────────────
  Глобально    – действует на все объекты сцены
  Локально     – только объекты на том же уровне иерархии
  Рекурсивно   – текущий уровень иерархии и все дочерние
"""

import c4d
from c4d import gui
import re
import os
import base64
import tempfile

# ─── Идентификатор плагина ────────────────────────────────────────────────────
PLUGIN_ID = 1068825
PLUGIN_NAME = "Object Renamer PRO"
PLUGIN_NAME_V = "Object Renamer PRO v2.6"

# ─── Размеры окна ─────────────────────────────────────────────────────────────
DIALOG_DEFAULT_W = 100   # ширина окна по умолчанию (px)
DIALOG_DEFAULT_H = 100   # высота окна по умолчанию (px)
PREVIEW_H        = 80    # высота панели предпросмотра (px)
PREVIEW_MAX_ROWS = 6     # максимальное число строк имён в превью

# ─── ID элементов интерфейса ─────────────────────────────────────────────────
# Выделение
BTN_SEL_SAME_NAME   = 1100
BTN_SEL_SAME_TAG    = 1101
BTN_SEL_SAME_TYPE   = 1102
BTN_SEL_SAME_MAT    = 1103   # "Выделить все с тем же материалом" (перенесена сюда)
ID_SEL_SCOPE        = 1104   # Combobox: 0=Глобально, 1=Локально, 2=Выделенные, 3=Рекурсивно
ID_SEL_NAME_TEXT    = 1105   # Поле поиска по имени
BTN_SEL_NAME_EXACT  = 1106   # Кнопка: точное совпадение
BTN_SEL_NAME_PART   = 1107   # Кнопка: фрагмент
BTN_SEL_NAME_CASE   = 1108   # Чекбокс: учитывать регистр

# Материал
BTN_MAT_RENAME   = 1001
BTN_NAME_TO_MAT  = 1003

# Найти и заменить
BTN_FIND_REPLACE = 1010
ID_FIND          = 1011
ID_REPLACE_STR   = 1012

# Префикс / Суффикс
BTN_ADD_PREFIX   = 1020
BTN_ADD_SUFFIX   = 1021
BTN_STRIP_PREFIX = 1022
BTN_STRIP_SUFFIX = 1023
ID_PREFIX        = 1024
ID_SUFFIX        = 1025

# Автонумерация
BTN_NUM_APPEND        = 1030
BTN_NUM_PREPEND       = 1031
BTN_REMOVE_NUMS       = 1032
BTN_REMOVE_NUM_PREFIX = 1036
ID_NUM_START     = 1033
ID_NUM_DIGITS    = 1034
ID_NUM_SEP       = 1035

# Регистр и очистка
BTN_CASE_UPPER   = 1040
BTN_CASE_LOWER   = 1041
BTN_CASE_TITLE   = 1042
BTN_SP_TO_UNDER  = 1043
BTN_UNDER_TO_SP  = 1044
BTN_CLEAN_WS     = 1045
BTN_TYPE_SUFFIX  = 1046
BTN_RU_TO_EN     = 1047   # транслитерация RU → EN
BTN_TYPE_PREFIX  = 1048   # Префикс типа
BTN_FIRST_CAP    = 1049   # Первый заглавный

# Строка состояния
ID_STATUS        = 1090

# Сортировка
BTN_SORT_AZ       = 1200   # А→Я по имени
BTN_SORT_ZA       = 1201   # Я→А по имени
BTN_SORT_TYPE     = 1202   # по типу объекта
BTN_SORT_TYPE_REV = 1203   # по типу (обратно)
BTN_SORT_TAGS          = 1204   # сортировка тегов по имени А→Я
BTN_SORT_TAGS_REV      = 1205   # сортировка тегов по имени Я→А
BTN_SORT_TAGS_TYPE     = 1211   # сортировка тегов по типу А→Я
BTN_SORT_TAGS_TYPE_REV = 1212   # сортировка тегов по типу Я→А
BTN_TOGGLE_PREVIEW     = 1213   # скрыть/показать предпросмотр
BTN_SORT_POLY_CNT     = 1206   # по числу полигонов (убывание)
BTN_SORT_POLY_CNT_REV = 1209   # по числу полигонов (возрастание)
BTN_SORT_CHILDREN     = 1207   # по числу дочерних (убывание)
BTN_SORT_CHILDREN_REV = 1210   # по числу дочерних (возрастание)
BTN_SORT_REVERSE      = 1208   # обратить порядок
BTN_SORT_TAG_CNT      = 1214   # по числу тегов (toggle ↓/↑)

# Группы вкладок — каждая вкладка требует уникального ненулевого ID
GRP_TABS         = 5000
GRP_TAB_SEL      = 5010   # вкладка Выделение
GRP_TAB_MAT      = 5011   # вкладка Материал
GRP_TAB_FIND     = 5012   # вкладка Найти/Замена
GRP_TAB_PREFIX   = 5013   # вкладка Преф/Суфф
GRP_TAB_NUM      = 5014   # вкладка Нумерация
GRP_TAB_CASE     = 5015   # вкладка Регистр
GRP_TAB_SORT     = 5016   # вкладка Сортировка
GRP_SCROLL       = 5001   # оставлен для совместимости (не используется)

# Предпросмотр
GRP_PREVIEW      = 5020   # группа-рамка панели предпросмотра
ID_PREVIEW       = 5021   # StaticText с текстом предпросмотра
GRP_ROOT         = 5022   # внешняя корневая группа (для LayoutChanged)

# Таймер обновления превью (мс)
PREVIEW_TIMER_MS = 400

# Значения выпадающего списка области
SCOPE_GLOBAL     = 0
SCOPE_LOCAL      = 1
SCOPE_SELECTED   = 2
SCOPE_RECURSIVE  = 3


class RenamerDialog(gui.GeDialog):

    # ══════════════════════════════════════════════════════════════════════════
    #  РАЗМЕТКА ИНТЕРФЕЙСА
    # ══════════════════════════════════════════════════════════════════════════
    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME)

        # ── Внешняя рамка с отступами ─────────────────────────────────────────
        self.GroupBegin(GRP_ROOT, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupBorderSpace(6, 6, 6, 6)

        # ══════════════════════════════════════════════════════════════════════
        #  ВКЛАДКИ
        # ══════════════════════════════════════════════════════════════════════
        self.TabGroupBegin(GRP_TABS, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, c4d.TAB_TABS)

        # ── Вкладка: ВЫДЕЛЕНИЕ ──────────────────────────────────────────────
        self.GroupBegin(GRP_TAB_SEL, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0, "Выделение")
        self.GroupBorderSpace(8, 10, 8, 8)

        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0,
            "Выделение по имени, типу, тегу или материалу.")
        # ── ОБЛАСТЬ ДЕЙСТВИЯ ──────────────────────────────────────────────────
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.GroupBorderSpace(0, 0, 0, 4)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Область:")
        self.AddComboBox(ID_SEL_SCOPE, c4d.BFH_SCALEFIT, 0, 10)
        self.AddChild(ID_SEL_SCOPE, SCOPE_GLOBAL,    "Глобально")
        self.AddChild(ID_SEL_SCOPE, SCOPE_LOCAL,     "Локально")
        self.AddChild(ID_SEL_SCOPE, SCOPE_RECURSIVE, "Рекурсивно")
        self.GroupEnd()

        # ── ПОИСК ПО ИМЕНИ ────────────────────────────────────────────────────
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 3, 0)
        self.GroupBorderSpace(0, 0, 0, 2)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поиск по имени:")
        self.AddEditText(ID_SEL_NAME_TEXT, c4d.BFH_SCALEFIT)
        self.AddCheckbox(BTN_SEL_NAME_CASE, c4d.BFH_LEFT, 0, 0, "Учитывать регистр")
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_SEL_NAME_EXACT, c4d.BFH_SCALEFIT, 0, 0, "Точное совпадение")
        self.AddButton(BTN_SEL_NAME_PART,  c4d.BFH_SCALEFIT, 0, 0, "Фрагмент")
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 0)
        self.GroupBorderSpace(0, 0, 0, 2)

        self.GroupEnd()

        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        # ── КНОПКИ ВЫДЕЛЕНИЯ ──────────────────────────────────────────────────
        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0, "Выделить по совпадению с первым объектом:")
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_SEL_SAME_NAME, c4d.BFH_SCALEFIT, 0, 0, "По имени")
        self.AddButton(BTN_SEL_SAME_TYPE, c4d.BFH_SCALEFIT, 0, 0, "По типу")
        self.AddButton(BTN_SEL_SAME_TAG,  c4d.BFH_SCALEFIT, 0, 0, "По первому тегу")
        self.AddButton(BTN_SEL_SAME_MAT,  c4d.BFH_SCALEFIT, 0, 0, "По материалу")
        self.GroupEnd()

        self.GroupEnd()

        # ── Вкладка: СОРТИРОВКА ─────────────────────────────────────────────
        self.GroupBegin(GRP_TAB_SORT, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0, "Сортировка")
        self.GroupBorderSpace(8, 10, 8, 8)

        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0, "Сортирует объекты внутри уровня иерархии выделенного объекта.")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 4, 0)
        self.AddButton(BTN_SORT_AZ,       c4d.BFH_SCALEFIT, 0, 0, "Имя А→Я")
        self.AddButton(BTN_SORT_TYPE,     c4d.BFH_SCALEFIT, 0, 0, "Тип А→Я")
        self.AddButton(BTN_SORT_CHILDREN, c4d.BFH_SCALEFIT, 0, 0, "Дочерних ↓")
        self.AddButton(BTN_SORT_TAG_CNT,  c4d.BFH_SCALEFIT, 0, 0, "Число тегов ↓")
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 1, 0)
        self.AddButton(BTN_SORT_REVERSE,  c4d.BFH_SCALEFIT, 0, 0, "⇅ Обратить порядок")
        self.GroupEnd()

        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0, "Сортировка тегов выделеных объектов:")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_SORT_TAGS,      c4d.BFH_SCALEFIT, 0, 0, "Имя  А→Я")
        self.AddButton(BTN_SORT_TAGS_TYPE, c4d.BFH_SCALEFIT, 0, 0, "Тип  А→Я")
        self.GroupEnd()

        self.GroupEnd()

        # ── Вкладка: Имена ─────────────────────────────────────────
        self.GroupBegin(GRP_TAB_FIND, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0, "Имена")
        self.GroupBorderSpace(8, 10, 8, 8)

        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0,
            "Заменяет подстроку в именах выделенных объектов. Регистр учитывается.")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 4, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Найти:")
        self.AddEditText(ID_FIND, c4d.BFH_SCALEFIT)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Заменить:")
        self.AddEditText(ID_REPLACE_STR, c4d.BFH_SCALEFIT)
        self.GroupEnd()
        self.AddButton(BTN_FIND_REPLACE, c4d.BFH_SCALEFIT, 0, 0, "Применить замену")

        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0,
            "Добавляет или удаляет префикс и суффикс у имён выделенных объектов.")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 4, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Префикс:")
        self.AddEditText(ID_PREFIX, c4d.BFH_SCALEFIT)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Суффикс:")
        self.AddEditText(ID_SUFFIX, c4d.BFH_SCALEFIT)
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 3, 0)
        self.AddButton(BTN_ADD_PREFIX,   c4d.BFH_SCALEFIT, 0, 0, "+ Префикс")
        self.AddButton(BTN_ADD_SUFFIX,   c4d.BFH_SCALEFIT, 0, 0, "+ Суффикс") 
        self.AddButton(BTN_TYPE_PREFIX,  c4d.BFH_SCALEFIT, 0, 0, "+ Преф. типа")                
        self.AddButton(BTN_STRIP_PREFIX, c4d.BFH_SCALEFIT, 0, 0, "- Префикс")
        self.AddButton(BTN_STRIP_SUFFIX, c4d.BFH_SCALEFIT, 0, 0, "- Суффикс")
        self.AddButton(BTN_TYPE_SUFFIX,  c4d.BFH_SCALEFIT, 0, 0, "+ Суфф. типа")
        self.GroupEnd()

        self.GroupEnd()

        # ── Вкладка: НУМЕРАЦИЯ ──────────────────────────────────────────────
        self.GroupBegin(GRP_TAB_NUM, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0, "Нумерация")
        self.GroupBorderSpace(8, 10, 8, 8)
        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0,
            "Добавляет порядковый номер. Порядок — по выделению.")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 6, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Разд-ль:")
        self.AddEditText(ID_NUM_SEP, c4d.BFH_SCALEFIT)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "С:")
        self.AddEditNumberArrows(ID_NUM_START,  c4d.BFH_LEFT, 46, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Знаков:")
        self.AddEditNumberArrows(ID_NUM_DIGITS, c4d.BFH_LEFT, 46, 0)
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_NUM_PREPEND, c4d.BFH_SCALEFIT, 0, 0, "+ Число в начало")
        self.AddButton(BTN_NUM_APPEND,  c4d.BFH_SCALEFIT, 0, 0, "+ Число в конец")
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_REMOVE_NUM_PREFIX, c4d.BFH_SCALEFIT, 0, 0, "- Числ. префикс")        
        self.AddButton(BTN_REMOVE_NUMS,       c4d.BFH_SCALEFIT, 0, 0, "- Числ. суффикс")
        self.GroupEnd()

        self.GroupEnd()

        # ── Вкладка: РЕГИСТР ────────────────────────────────────────────────
        self.GroupBegin(GRP_TAB_CASE, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0, "Регистр")
        self.GroupBorderSpace(8, 10, 8, 8)
        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0,
            "Меняет регистр, заменяет пробелы/подчёркивания, транслитерирует.")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 4, 0)
        self.AddButton(BTN_CASE_UPPER,   c4d.BFH_SCALEFIT, 0, 0, "ВЕРХНИЙ")
        self.AddButton(BTN_CASE_LOWER,   c4d.BFH_SCALEFIT, 0, 0, "нижний")
        self.AddButton(BTN_CASE_TITLE,   c4d.BFH_SCALEFIT, 0, 0, "Заглавные")
        self.AddButton(BTN_FIRST_CAP,    c4d.BFH_SCALEFIT, 0, 0, "Первый заглавный")
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_SP_TO_UNDER,  c4d.BFH_SCALEFIT, 0, 0, "Пробелы \u2192 _")
        self.AddButton(BTN_UNDER_TO_SP,  c4d.BFH_SCALEFIT, 0, 0, "_ \u2192 Пробелы")
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_CLEAN_WS,     c4d.BFH_SCALEFIT, 0, 0, "Убрать пробелы")
        self.AddButton(BTN_RU_TO_EN,     c4d.BFH_SCALEFIT, 0, 0, "RU \u2192 EN  (транслит)")
        self.GroupEnd()

        self.AddStaticText(0, c4d.BFH_SCALEFIT, 0, 0,
            "Синхронизирует имена объектов и материалов между собой.")
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddButton(BTN_NAME_TO_MAT, c4d.BFH_SCALEFIT, 0, 0, "Объект  ->  Материал")
        self.AddButton(BTN_MAT_RENAME,  c4d.BFH_SCALEFIT, 0, 0, "Объект  <-  Материал")
        self.GroupEnd()

        self.GroupEnd()

        self.GroupEnd()  # /TabGroupEnd

        # ── ПАНЕЛЬ ПРЕДПРОСМОТРА (вне вкладок, над строкой состояния) ─────────
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)

        self.GroupBegin(GRP_PREVIEW, c4d.BFH_SCALEFIT, 1, 0, "")
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFV_CENTER, 0, 0, "Предпросмотр:")
        self.GroupEnd()
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(6, 4, 6, 4)
        self.AddMultiLineEditText(
            ID_PREVIEW,
            c4d.BFH_SCALEFIT | c4d.BFV_TOP,
            0, PREVIEW_H,
            c4d.DR_MULTILINE_READONLY | c4d.DR_MULTILINE_MONOSPACED
        )
        self.GroupEnd()  # /GRP_PREVIEW
        self.AddSeparatorH(0, c4d.BFH_SCALEFIT)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0)
        self.AddStaticText(ID_STATUS, c4d.BFH_SCALEFIT, 0, 16, "")
        self.AddButton(BTN_TOGGLE_PREVIEW, c4d.BFH_RIGHT, 18, 18, "⊙")
        self.HideElement(GRP_PREVIEW, True)
        self.GroupEnd()
        self.GroupEnd()  # /внешняя рамка
        return True

    """
    Немодальный асинхронный диалог для пакетного переименования и выделения объектов.

    Принцип работы
    ──────────────
    Каждая публичная операция либо вызывает `_batch_rename()`, либо
    самостоятельно оборачивает логику в блок doc.StartUndo() / doc.EndUndo().
    """

    # ── Таблица транслитерации RU → EN ───────────────────────────────────────
    _RU_TO_EN_MAP = {
        'а': 'a',  'б': 'b',  'в': 'v',  'г': 'g',  'д': 'd',
        'е': 'e',  'ё': 'yo', 'ж': 'zh', 'з': 'z',  'и': 'i',
        'й': 'y',  'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',
        'о': 'o',  'п': 'p',  'р': 'r',  'с': 's',  'т': 't',
        'у': 'u',  'ф': 'f',  'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'sch','ъ': '',   'ы': 'y',  'ь': '',
        'э': 'e',  'ю': 'yu', 'я': 'ya',
        'А': 'A',  'Б': 'B',  'В': 'V',  'Г': 'G',  'Д': 'D',
        'Е': 'E',  'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z',  'И': 'I',
        'Й': 'Y',  'К': 'K',  'Л': 'L',  'М': 'M',  'Н': 'N',
        'О': 'O',  'П': 'P',  'Р': 'R',  'С': 'S',  'Т': 'T',
        'У': 'U',  'Ф': 'F',  'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch',
        'Ш': 'Sh', 'Щ': 'Sch','Ъ': '',   'Ы': 'Y',  'Ь': '',
        'Э': 'E',  'Ю': 'Yu', 'Я': 'Ya',
    }

    # ── Таблица суффиксов типов объектов ─────────────────────────────────────
    _TYPE_MAP = {
        # ── ПРИМИТИВЫ ────────────────────────────────────────────────────────────────
        c4d.Onull:           "NULL",
        c4d.Ocube:           "CUBE",
        c4d.Osphere:         "SPHERE",
        c4d.Ocylinder:       "CYL",
        c4d.Oplane:          "PLANE",
        c4d.Ocone:           "CONE",
        c4d.Otorus:          "TORUS",
        c4d.Opyramid:        "PYR",
        c4d.Oplatonic:       "PLAT",
        c4d.Otube:           "TUBE",
        c4d.Odisc:           "DISC",
        c4d.Ooiltank:        "TANK",
        c4d.Ocapsule:        "CAPS",
        c4d.Ofigure:         "FIG",
        c4d.Orelief:         "RELF",
        c4d.Osinglepoly:     "POLY",
        c4d.Ofractal:        "FRAC",

        # ── ПОЛИГОНАЛЬНЫЙ ────────────────────────────────────────────────────────────
        c4d.Opolygon:        "MESH",

        # ── СПЛАЙНЫ ──────────────────────────────────────────────────────────────────
        c4d.Ospline:         "SPLN",
        c4d.Osplinearc:      "ARC",
        c4d.Osplinecircle:   "CIRC",
        c4d.Osplinerectangle:"RECT",
        c4d.Osplinestar:     "STAR",
        c4d.Osplinetext:     "STXT",
        c4d.Osplineflower:   "FLWR",
        c4d.Osplineformula:  "SFRM",
        c4d.Osplinecogwheel: "COG",
        c4d.Osplinecycloid:  "CYCL",
        c4d.Osplinehelix:    "HELIX",
        c4d.Osplineprofile:  "PROF",
        c4d.Osplinecontour:  "CONT",
        c4d.Ospline4side:    "4SID",

        # ── NURBS / ГЕНЕРАТОРЫ ───────────────────────────────────────────────────────
        c4d.Oextrude:        "EXT",
        c4d.Olathe:          "LATH",
        c4d.Oloft:           "LOFT",
        c4d.Osweep:          "SWP",
        c4d.Obezier:         "BEZ",
        c4d.Oboole:          "BOOL",
        c4d.Osds:            "SDS",
        c4d.Oarray:          "ARR",
        c4d.Oatomarray:      "ATOM",
        c4d.Osymmetry:       "SYM",
        c4d.Oinstance:       "INST",

        # ── ДЕФОРМЕРЫ ────────────────────────────────────────────────────────────────
        c4d.Obend:                "BEND",
        c4d.Obulge:               "BULGE",
        c4d.Oshear:               "SHEAR",
        c4d.Otaper:               "TAPER",
        c4d.Otwist:               "TWIST",
        c4d.Owave:                "WAVE",
        c4d.Owinddeform:          "WDEF",
        c4d.Owrap:                "WRAP",
        c4d.Opolyreduction:       "PRED",
        c4d.Ospherify:            "SPHR",
        c4d.Omelt:                "MELT",
        c4d.Oshatter:             "SHAT",
        c4d.Oexplosion:           "EXPL",
        c4d.Oformula:             "FRML",
        c4d.Oskin:                "SKIN",

        # ── СВЕТ ─────────────────────────────────────────────────────────────────────
        c4d.Olight:          "LIGHT",

        # ── КАМЕРА ───────────────────────────────────────────────────────────────────
        c4d.Ocamera:         "CAM",

        # ── СРЕДА / СЦЕНА ────────────────────────────────────────────────────────────
        c4d.Osky:            "SKY",
        c4d.Oenvironment:    "ENV",
        c4d.Oforeground:     "FG",
        c4d.Obackground:     "BG",
        c4d.Ostage:          "STAGE",
        c4d.Ofloor:          "FLOOR",

        # ── ПЕРСОНАЖ / РИГ ───────────────────────────────────────────────────────────
        c4d.Ojoint:          "JNT",
        c4d.Ocharacter:      "CHAR",

        # ── ЧАСТИЦЫ / СИЛЫ (TP & классика) ───────────────────────────────────────────
        c4d.Oparticle:       "PART",
        c4d.Oattractor:      "ATTR",
        c4d.Odeflector:      "DEFL",
        c4d.Orotation:       "RFOR",
        c4d.Oturbulence:     "TURB",
        c4d.Owind:           "WIND",
        c4d.Ofriction:       "FRIC",
        c4d.Ometaball:       "META",

        # ── VOLUME (R21+) ─────────────────────────────────────────────────────────────
        c4d.Ovolumebuilder:  "VOLB",
        c4d.Ovolumeloader:   "VOLL",

        # ── HAIR ─────────────────────────────────────────────────────────────────────
        c4d.Ohair:           "HAIR",
    }

    # ══════════════════════════════════════════════════════════════════════════
    #  ИНИЦИАЛИЗАЦИЯ
    # ══════════════════════════════════════════════════════════════════════════
    def InitValues(self):
        self._preview_visible = False
        self._sort_states = {
            BTN_SORT_AZ:        False,
            BTN_SORT_TYPE:      False,
            BTN_SORT_CHILDREN:  False,
            BTN_SORT_POLY_CNT:  False,
            BTN_SORT_TAGS:      False,
            BTN_SORT_TAGS_TYPE: False,
            BTN_SORT_TAG_CNT:   False,
        }
        self.SetInt32(ID_NUM_START,  1)
        self.SetInt32(ID_NUM_DIGITS, 2)
        self.SetString(ID_NUM_SEP,   "_")
        self.SetInt32(ID_SEL_SCOPE,  SCOPE_LOCAL)
        self.SetString(ID_SEL_NAME_TEXT, "")
        self.SetBool(BTN_SEL_NAME_CASE, False)
        self.SetString(ID_PREVIEW,   "Выберите объекты для предпросмотра")
        self._status("Готово  —  выберите объекты и нажмите кнопку выше")
        self.SetTimer(PREVIEW_TIMER_MS)
        return True

    # ══════════════════════════════════════════════════════════════════════════
    #  ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ══════════════════════════════════════════════════════════════════════════
    def _status(self, msg):
        self.SetString(ID_STATUS, msg)

    # ══════════════════════════════════════════════════════════════════════════
    #  ДИНАМИЧЕСКИЙ ПРЕДПРОСМОТР
    # ══════════════════════════════════════════════════════════════════════════
    def _current_tab(self):
        """Возвращает ID активной вкладки через GetInt32 на GRP_TABS."""
        return self.GetInt32(GRP_TABS)

    def _preview_objects(self):
        """
        Для вкладки «Выделение» — текущие выделенные объекты.
        Для остальных вкладок — объекты, которые будут затронуты операцией
        (т.е. текущие выделенные объекты, как это делают _get_selected).
        """
        doc  = c4d.documents.GetActiveDocument()
        objs = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        return objs

    def _build_preview_text(self):
        """Формирует строку предпросмотра в зависимости от активной вкладки."""
        try:
            tab = self._current_tab()
            doc = c4d.documents.GetActiveDocument()

            # ── Вкладка ВЫДЕЛЕНИЕ ────────────────────────────────────────────
            if tab == GRP_TAB_SEL:
                sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                scope = self.GetInt32(ID_SEL_SCOPE)
                scope_label = {
                    SCOPE_GLOBAL:    "Глобально",
                    SCOPE_LOCAL:     "Локально",
                    SCOPE_SELECTED:  "Выделенные",
                    SCOPE_RECURSIVE: "Рекурсивно",
                }.get(scope, "?")
                query = self.GetString(ID_SEL_NAME_TEXT).strip()
                if not sel:
                    return "Нет выделенных объектов\nОбласть: {}".format(scope_label)
                ref = sel[0]
                pool = self._get_scope_pool(ref)
                lines = [
                    "Выделено: {}  |  Область: {} ({} объектов)".format(
                        len(sel), scope_label, len(pool)
                    ),
                    "Эталон: «{}»{}".format(
                        ref.GetName(),
                        "  |  Поиск: «{}»".format(query) if query else ""
                    ),
                    "─" * 36,
                ]
                for obj in pool[:PREVIEW_MAX_ROWS]:
                    lines.append("  • {}".format(obj.GetName()))
                if len(pool) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(pool) - PREVIEW_MAX_ROWS))
                return "\n".join(lines)

            # ── Вкладка МАТЕРИАЛ ─────────────────────────────────────────────
            if tab == GRP_TAB_MAT:
                sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                if not sel:
                    return "Нет выделенных объектов"
                lines = ["Будет затронуто: {} объектов".format(len(sel)), "─" * 36]
                for obj in sel[:PREVIEW_MAX_ROWS]:
                    mat = self._first_material(obj)
                    mat_name = mat.GetName() if mat else "—"
                    lines.append("  {} → {}".format(obj.GetName(), mat_name))
                if len(sel) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(sel) - PREVIEW_MAX_ROWS))
                return "\n".join(lines)

            # ── Вкладка НАЙТИ / ЗАМЕНА ───────────────────────────────────────
            if tab == GRP_TAB_FIND:
                sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                find_str = self.GetString(ID_FIND)
                repl_str = self.GetString(ID_REPLACE_STR)
                if not sel:
                    return "Нет выделенных объектов"
                if not find_str:
                    lines = ["Введите строку поиска", "─" * 36]
                    for obj in sel[:PREVIEW_MAX_ROWS]:
                        lines.append("  {}".format(obj.GetName()))
                    if len(sel) > PREVIEW_MAX_ROWS:
                        lines.append("  … ещё {} объектов".format(len(sel) - PREVIEW_MAX_ROWS))
                    return "\n".join(lines)
                affected = [o for o in sel if find_str in o.GetName()]
                lines = [
                    "Найдено: {} из {} объектов  «{}» → «{}»".format(
                        len(affected), len(sel), find_str, repl_str
                    ),
                    "─" * 36,
                ]
                for obj in affected[:PREVIEW_MAX_ROWS]:
                    new_name = obj.GetName().replace(find_str, repl_str)
                    lines.append("  {} → {}".format(obj.GetName(), new_name))
                if len(affected) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(affected) - PREVIEW_MAX_ROWS))
                if not affected:
                    lines.append("  (совпадений не найдено)")
                return "\n".join(lines)

            # ── Вкладка ПРЕФИКС / СУФФИКС ────────────────────────────────────
            if tab == GRP_TAB_PREFIX:
                sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                prefix = self.GetString(ID_PREFIX)
                suffix = self.GetString(ID_SUFFIX)
                if not sel:
                    return "Нет выделенных объектов"
                lines = [
                    "Префикс: «{}»   Суффикс: «{}»   Объектов: {}".format(
                        prefix or "—", suffix or "—", len(sel)
                    ),
                    "─" * 36,
                ]
                for obj in sel[:PREVIEW_MAX_ROWS]:
                    name = obj.GetName()
                    preview = (prefix or "") + name + (suffix or "")
                    if prefix or suffix:
                        lines.append("  {} → {}".format(name, preview))
                    else:
                        lines.append("  {}".format(name))
                if len(sel) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(sel) - PREVIEW_MAX_ROWS))
                return "\n".join(lines)

            # ── Вкладка НУМЕРАЦИЯ ─────────────────────────────────────────────
            if tab == GRP_TAB_NUM:
                sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                if not sel:
                    return "Нет выделенных объектов"
                start  = self.GetInt32(ID_NUM_START)
                digits = self.GetInt32(ID_NUM_DIGITS)
                sep    = self.GetString(ID_NUM_SEP)
                lines  = [
                    "Нумерация: с {}, {} знаков, разд. «{}»   Объектов: {}".format(
                        start, digits, sep, len(sel)
                    ),
                    "─" * 36,
                ]
                for i, obj in enumerate(sel[:PREVIEW_MAX_ROWS]):
                    num = str(start + i).zfill(digits)
                    lines.append("  {} → {}{}{} / {}{}{}".format(
                        obj.GetName(),
                        obj.GetName(), sep, num,
                        num, sep, obj.GetName(),
                    ))
                if len(sel) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(sel) - PREVIEW_MAX_ROWS))
                return "\n".join(lines)

            # ── Вкладка РЕГИСТР ───────────────────────────────────────────────
            if tab == GRP_TAB_CASE:
                sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                if not sel:
                    return "Нет выделенных объектов"
                lines = ["Объектов для обработки: {}".format(len(sel)), "─" * 36]
                for obj in sel[:PREVIEW_MAX_ROWS]:
                    name = obj.GetName()
                    lines.append("  UPPER: {}  |  lower: {}  |  Title: {}".format(
                        name.upper(), name.lower(), name.title()
                    ))
                if len(sel) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(sel) - PREVIEW_MAX_ROWS))
                return "\n".join(lines)

            # ── Вкладка СОРТИРОВКА ───────────────────────────────────────────
            if tab == GRP_TAB_SORT:
                doc2, parent, siblings = self._sorted_siblings_pool()
                if not siblings:
                    return "Нет объектов для сортировки"
                parent_name = parent.GetName() if parent else "(корень сцены)"
                lines = [
                    "Уровень: «{}»  |  {} объектов".format(parent_name, len(siblings)),
                    "─" * 36,
                ]
                for obj in siblings[:PREVIEW_MAX_ROWS]:
                    n_tags = 0
                    tag = obj.GetFirstTag()
                    while tag:
                        n_tags += 1
                        tag = tag.GetNext()
                    lines.append("  {} [{}  тегов: {}]".format(
                        obj.GetName(), self._type_suffix(obj), n_tags
                    ))
                if len(siblings) > PREVIEW_MAX_ROWS:
                    lines.append("  … ещё {} объектов".format(len(siblings) - PREVIEW_MAX_ROWS))
                return "\n".join(lines)

        except Exception as e:
            return "(ошибка предпросмотра: {})".format(e)

        return ""

    def Timer(self, msg):
        """Вызывается C4D каждые PREVIEW_TIMER_MS мс — обновляет панель предпросмотра."""
        try:
            text = self._build_preview_text()
            self.SetString(ID_PREVIEW, text)
        except Exception:
            pass

    def _get_selected(self):
        doc  = c4d.documents.GetActiveDocument()
        objs = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if not objs:
            self._status("Объекты не выбраны  —  сначала выберите объекты")
        return objs

    def _first_material(self, obj):
        tag = obj.GetFirstTag()
        while tag:
            if tag.GetType() == c4d.Ttexture:
                mat = tag[c4d.TEXTURETAG_MATERIAL]
                if mat:
                    return mat
            tag = tag.GetNext()
        return None

    def _material_name(self, obj):
        mat = self._first_material(obj)
        return mat.GetName() if mat else None

    def _texture_filename(self, obj):
        mat = self._first_material(obj)
        if not mat:
            return None
        shader = mat[c4d.MATERIAL_COLOR_SHADER]
        if shader and shader.GetType() == c4d.Xbitmap:
            filepath = shader[c4d.BITMAPSHADER_FILENAME]
            if filepath:
                return os.path.splitext(os.path.basename(filepath))[0]
        return None

    def _type_suffix(self, obj):
        return self._TYPE_MAP.get(obj.GetType(), "OBJ")

    def _all_scene_objects(self):
        result = []
        def _walk(obj):
            while obj:
                result.append(obj)
                _walk(obj.GetDown())
                obj = obj.GetNext()
        _walk(c4d.documents.GetActiveDocument().GetFirstObject())
        return result

    def _get_scope_pool(self, ref_obj):
        """
        Возвращает пул объектов в зависимости от выбранной области:
          SCOPE_GLOBAL    — все объекты сцены
          SCOPE_LOCAL     — объекты на том же уровне иерархии (дочерние того же родителя)
          SCOPE_SELECTED  — только текущие выделенные объекты
          SCOPE_RECURSIVE — текущий уровень + все вложенные (рекурсивно)
        """
        scope = self.GetInt32(ID_SEL_SCOPE)
        if scope == SCOPE_SELECTED:
            return self._get_selected()
        elif scope == SCOPE_LOCAL:
            parent = ref_obj.GetUp()
            if parent:
                siblings = []
                child = parent.GetDown()
                while child:
                    siblings.append(child)
                    child = child.GetNext()
                return siblings
            else:
                # корневой уровень — все корневые объекты
                doc = c4d.documents.GetActiveDocument()
                siblings = []
                child = doc.GetFirstObject()
                while child:
                    siblings.append(child)
                    child = child.GetNext()
                return siblings
        elif scope == SCOPE_RECURSIVE:
            # Берём стартовый уровень: родитель ref_obj или корень
            result = []
            parent = ref_obj.GetUp()
            if parent:
                start = parent.GetDown()
            else:
                start = c4d.documents.GetActiveDocument().GetFirstObject()
            def _walk_rec(obj):
                while obj:
                    result.append(obj)
                    _walk_rec(obj.GetDown())
                    obj = obj.GetNext()
            _walk_rec(start)
            return result
        else:  # SCOPE_GLOBAL
            return self._all_scene_objects()

    def _get_selected_tag(self, ref_obj):
        """
        Возвращает выделенный тег у ref_obj, или None.
        Используется при SCOPE_SELECTED, чтобы учитывать выделенный тег
        вместо перебора всех тегов.
        """
        tag = ref_obj.GetFirstTag()
        while tag:
            if tag.GetBit(c4d.BIT_ACTIVE):
                return tag
            tag = tag.GetNext()
        return None

    def _batch_rename(self, objects, name_fn):
        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        renamed = 0
        for obj in objects:
            try:
                new_name = name_fn(obj)
            except Exception:
                continue
            if new_name and new_name != obj.GetName():
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
                obj.SetName(new_name)
                renamed += 1
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Готово  —  переименовано {}/{} объектов".format(renamed, len(objects)))

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ВЫДЕЛЕНИЯ
    # ══════════════════════════════════════════════════════════════════════════

    def _do_select_same_name(self):
        """Выделить все объекты с таким же именем, как у первого выделенного."""
        sel = self._get_selected()
        if not sel:
            return
        ref_name = sel[0].GetName()
        scope = self.GetInt32(ID_SEL_SCOPE)
        pool = self._get_scope_pool(sel[0])
        if scope == SCOPE_SELECTED:
            # при "Выделенные" — ищем совпадения по имени внутри выделенных
            pool = sel
        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        found = 0
        for obj in pool:
            if obj.GetName() == ref_name:
                doc.AddUndo(c4d.UNDOTYPE_BITS, obj)
                obj.SetBit(c4d.BIT_ACTIVE)
                found += 1
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Выделено {} объектов с именем '{}'".format(found, ref_name))

    def _do_select_same_tag(self):
        """
        Выделить все объекты, у которых есть тег того же типа.
        При SCOPE_SELECTED — учитывает конкретный выделенный тег у ref_obj.
        """
        sel = self._get_selected()
        if not sel:
            return
        ref_obj = sel[0]
        scope = self.GetInt32(ID_SEL_SCOPE)

        # Определяем эталонный тип тега
        if scope == SCOPE_SELECTED:
            # пробуем взять выделенный тег
            active_tag = self._get_selected_tag(ref_obj)
            if active_tag:
                ref_tag_type = active_tag.GetType()
            else:
                # fallback — первый тег
                first = ref_obj.GetFirstTag()
                if not first:
                    self._status("У объекта нет тегов")
                    return
                ref_tag_type = first.GetType()
            pool = sel
        else:
            first = ref_obj.GetFirstTag()
            if not first:
                self._status("У первого объекта нет тегов")
                return
            ref_tag_type = first.GetType()
            pool = self._get_scope_pool(ref_obj)

        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        found = 0
        for obj in pool:
            tag = obj.GetFirstTag()
            while tag:
                if tag.GetType() == ref_tag_type:
                    doc.AddUndo(c4d.UNDOTYPE_BITS, obj)
                    obj.SetBit(c4d.BIT_ACTIVE)
                    found += 1
                    break
                tag = tag.GetNext()
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Выделено {} объектов с тегом типа {}".format(found, ref_tag_type))

    def _do_select_same_type(self):
        """Выделить все объекты того же типа (камера, примитив и т.д.)."""
        sel = self._get_selected()
        if not sel:
            return
        ref_obj = sel[0]
        ref_type = ref_obj.GetType()
        scope = self.GetInt32(ID_SEL_SCOPE)
        pool = sel if scope == SCOPE_SELECTED else self._get_scope_pool(ref_obj)

        type_label = self._TYPE_MAP.get(ref_type, "тип {}".format(ref_type))
        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        found = 0
        for obj in pool:
            if obj.GetType() == ref_type:
                doc.AddUndo(c4d.UNDOTYPE_BITS, obj)
                obj.SetBit(c4d.BIT_ACTIVE)
                found += 1
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Выделено {} объектов типа {}".format(found, type_label))

    def _do_select_by_mat(self):
        """
        Выделить объекты с тем же материалом.

        Логика выбора эталонного материала:
          1. Если у первого выделенного объекта есть ВЫДЕЛЕННЫЙ тег-текстуры
             → берётся материал именно из него.
          2. Иначе → первый тег-текстуры объекта.

        При SCOPE_SELECTED поиск ведётся только среди уже выделенных объектов.
        """
        sel = self._get_selected()
        if not sel:
            return
        ref_obj = sel[0]
        scope = self.GetInt32(ID_SEL_SCOPE)

        # Определяем эталонный материал
        ref_mat = None
        # Сначала проверяем, есть ли выделенный тег текстуры
        tag = ref_obj.GetFirstTag()
        while tag:
            if tag.GetType() == c4d.Ttexture and tag.GetBit(c4d.BIT_ACTIVE):
                ref_mat = tag[c4d.TEXTURETAG_MATERIAL]
                break
            tag = tag.GetNext()
        # Если нет — берём первый материал
        if not ref_mat:
            ref_mat = self._first_material(ref_obj)

        if not ref_mat:
            self._status("У первого выделенного объекта нет материала")
            return
        ref_name = ref_mat.GetName()

        pool = sel if scope == SCOPE_SELECTED else self._get_scope_pool(ref_obj)

        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        found = 0
        for obj in pool:
            tag = obj.GetFirstTag()
            while tag:
                if tag.GetType() == c4d.Ttexture:
                    mat = tag[c4d.TEXTURETAG_MATERIAL]
                    if mat and mat.GetName() == ref_name:
                        doc.AddUndo(c4d.UNDOTYPE_BITS, obj)
                        obj.SetBit(c4d.BIT_ACTIVE)
                        found += 1
                        break
                tag = tag.GetNext()
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Выделено {} объектов с материалом '{}'".format(found, ref_name))

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ПЕРЕИМЕНОВАНИЯ — МАТЕРИАЛ
    # ══════════════════════════════════════════════════════════════════════════

    def _do_mat_rename(self):
        objs = self._get_selected()
        if objs:
            self._batch_rename(objs, self._material_name)

    def _do_name_to_mat(self):
        objs = self._get_selected()
        if not objs:
            return
        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        n = 0
        for obj in objs:
            mat = self._first_material(obj)
            if mat:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, mat)
                mat.SetName(obj.GetName())
                n += 1
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Готово  —  {} материал(ов) переименовано".format(n))

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ПЕРЕИМЕНОВАНИЯ — НАЙТИ И ЗАМЕНИТЬ
    # ══════════════════════════════════════════════════════════════════════════

    def _do_find_replace(self):
        objs = self._get_selected()
        if not objs:
            return
        find_str = self.GetString(ID_FIND)
        repl_str = self.GetString(ID_REPLACE_STR)
        if not find_str:
            self._status("Введите строку поиска")
            return

        def fn(obj):
            name = obj.GetName()
            return name.replace(find_str, repl_str) if find_str in name else None

        self._batch_rename(objs, fn)

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ПЕРЕИМЕНОВАНИЯ — ПРЕФИКС / СУФФИКС
    # ══════════════════════════════════════════════════════════════════════════

    def _do_add_prefix(self):
        objs = self._get_selected()
        if not objs:
            return
        prefix = self.GetString(ID_PREFIX)
        if not prefix:
            self._status("Введите префикс")
            return
        self._batch_rename(objs, lambda obj: prefix + obj.GetName())

    def _do_add_suffix(self):
        objs = self._get_selected()
        if not objs:
            return
        suffix = self.GetString(ID_SUFFIX)
        if not suffix:
            self._status("Введите суффикс")
            return
        self._batch_rename(objs, lambda obj: obj.GetName() + suffix)

    def _do_strip_prefix(self):
        objs = self._get_selected()
        if not objs:
            return
        prefix = self.GetString(ID_PREFIX)
        if not prefix:
            self._status("Введите удаляемый префикс")
            return

        def fn(obj):
            name = obj.GetName()
            return name[len(prefix):] if name.startswith(prefix) else None

        self._batch_rename(objs, fn)

    def _do_strip_suffix(self):
        objs = self._get_selected()
        if not objs:
            return
        suffix = self.GetString(ID_SUFFIX)
        if not suffix:
            self._status("Введите удаляемый суффикс")
            return

        def fn(obj):
            name = obj.GetName()
            return name[:-len(suffix)] if name.endswith(suffix) else None

        self._batch_rename(objs, fn)

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ПЕРЕИМЕНОВАНИЯ — АВТОНУМЕРАЦИЯ
    # ══════════════════════════════════════════════════════════════════════════

    def _do_numbering(self, prepend=False):
        objs = self._get_selected()
        if not objs:
            return
        start  = self.GetInt32(ID_NUM_START)
        digits = self.GetInt32(ID_NUM_DIGITS)
        sep    = self.GetString(ID_NUM_SEP)
        doc    = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        for i, obj in enumerate(objs):
            num = str(start + i).zfill(digits)
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            if prepend:
                obj.SetName(num + sep + obj.GetName())
            else:
                obj.SetName(obj.GetName() + sep + num)
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Готово  —  {} объектов пронумеровано".format(len(objs)))

    def _do_remove_nums(self):
        objs = self._get_selected()
        if not objs:
            return
        pat = re.compile(r'[\._\-\s]+\d+$')

        def fn(obj):
            cleaned = pat.sub('', obj.GetName())
            return cleaned if cleaned else None

        self._batch_rename(objs, fn)

    def _do_remove_num_prefix(self):
        objs = self._get_selected()
        if not objs:
            return
        pat = re.compile(r'^\d+[\._\-\s]+')

        def fn(obj):
            cleaned = pat.sub('', obj.GetName())
            return cleaned if cleaned else None

        self._batch_rename(objs, fn)

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ПЕРЕИМЕНОВАНИЯ — РЕГИСТР И ОЧИСТКА
    # ══════════════════════════════════════════════════════════════════════════

    def _do_case(self, mode):
        objs = self._get_selected()
        if not objs:
            return
        converters = {
            'upper': str.upper,
            'lower': str.lower,
            'title': str.title,
        }
        convert = converters[mode]
        self._batch_rename(objs, lambda obj: convert(obj.GetName()))

    def _do_spaces_to_underscore(self):
        objs = self._get_selected()
        if objs:
            self._batch_rename(objs, lambda obj: obj.GetName().replace(' ', '_'))

    def _do_underscore_to_spaces(self):
        objs = self._get_selected()
        if objs:
            self._batch_rename(objs, lambda obj: obj.GetName().replace('_', ' '))

    def _do_clean_whitespace(self):
        objs = self._get_selected()
        if objs:
            self._batch_rename(objs, lambda obj: obj.GetName().replace(' ', '') or None)

    def _do_add_type_suffix(self):
        objs = self._get_selected()
        if objs:
            self._batch_rename(
                objs,
                lambda obj: obj.GetName() + '_' + self._type_suffix(obj)
            )

    def _do_ru_to_en(self):
        objs = self._get_selected()
        if objs:
            def transliterate(obj):
                return ''.join(self._RU_TO_EN_MAP.get(ch, ch) for ch in obj.GetName())
            self._batch_rename(objs, transliterate)

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ВЫДЕЛЕНИЯ — ПО ИМЕНИ ИЗ ПОЛЯ ПОИСКА
    # ══════════════════════════════════════════════════════════════════════════

    def _do_select_by_name_search(self, exact=True):
        """
        Выделяет объекты по строке из поля поиска.
        exact=True  → полное совпадение имени
        exact=False → наличие фрагмента в имени
        Учёт регистра определяется чекбоксом BTN_SEL_NAME_CASE.
        """
        query = self.GetString(ID_SEL_NAME_TEXT).strip()
        if not query:
            self._status("Введите строку поиска")
            return
        case_sens = self.GetBool(BTN_SEL_NAME_CASE)
        doc = c4d.documents.GetActiveDocument()
        sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)

        # Определяем пул: если нет выделения — глобальный
        if sel:
            pool = self._get_scope_pool(sel[0])
        else:
            pool = self._all_scene_objects()

        def matches(name):
            a, b = (name, query) if case_sens else (name.lower(), query.lower())
            return (a == b) if exact else (b in a)

        doc.StartUndo()
        found = 0
        for obj in pool:
            if matches(obj.GetName()):
                doc.AddUndo(c4d.UNDOTYPE_BITS, obj)
                obj.SetBit(c4d.BIT_ACTIVE)
                found += 1
        doc.EndUndo()
        c4d.EventAdd()
        mode = "точное" if exact else "фрагмент"
        reg  = "с рег." if case_sens else "без рег."
        self._status("Выделено {} объектов по «{}» ({}, {})".format(found, query, mode, reg))

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ ПЕРЕИМЕНОВАНИЯ — РЕГИСТР (НОВЫЕ)
    # ══════════════════════════════════════════════════════════════════════════

    def _do_add_type_prefix(self):
        """Добавляет префикс типа объекта: CUBE_Имя, CAM_Имя и т.д."""
        objs = self._get_selected()
        if objs:
            self._batch_rename(
                objs,
                lambda obj: self._type_suffix(obj) + '_' + obj.GetName()
            )

    def _do_first_cap(self):
        """Делает только первую букву заглавной, остальные не меняет."""
        objs = self._get_selected()
        if objs:
            def first_cap(obj):
                name = obj.GetName()
                return name[0].upper() + name[1:] if name else name
            self._batch_rename(objs, first_cap)

    # ══════════════════════════════════════════════════════════════════════════
    #  ОПЕРАЦИИ СОРТИРОВКИ
    # ══════════════════════════════════════════════════════════════════════════

    def _sorted_siblings_pool(self):
        """
        Определяет список объектов для сортировки и их общего родителя.
        Если есть выделение — берём уровень первого выделенного объекта.
        Иначе — корневой уровень сцены.
        Возвращает (doc, parent_or_None, [объекты на одном уровне]).
        """
        doc = c4d.documents.GetActiveDocument()
        sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if sel:
            ref = sel[0]
            parent = ref.GetUp()
        else:
            parent = None

        siblings = []
        if parent:
            child = parent.GetDown()
        else:
            child = doc.GetFirstObject()
        while child:
            siblings.append(child)
            child = child.GetNext()
        return doc, parent, siblings

    def _apply_sort_order(self, doc, parent, ordered):
        """
        Переставляет объекты в ordered в сцене через InsertObject/InsertUnder.
        Создаёт один шаг отмены.
        """
        doc.StartUndo()
        # Удаляем все объекты из текущей позиции (Remove не удаляет из памяти)
        for obj in ordered:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.Remove()

        # Вставляем в новом порядке
        prev = None
        for obj in ordered:
            if parent:
                if prev is None:
                    obj.InsertUnder(parent)
                else:
                    obj.InsertAfter(prev)
            else:
                if prev is None:
                    doc.InsertObject(obj, None, None)
                else:
                    obj.InsertAfter(prev)
            prev = obj
        doc.EndUndo()
        c4d.EventAdd()

    def _do_sort_by_name(self, reverse=False):
        doc, parent, siblings = self._sorted_siblings_pool()
        if not siblings:
            self._status("Нет объектов для сортировки")
            return
        ordered = sorted(siblings, key=lambda o: o.GetName().lower(), reverse=reverse)
        self._apply_sort_order(doc, parent, ordered)
        self._status("Сортировка по имени ({}) — {} объектов".format(
            "Я→А" if reverse else "А→Я", len(ordered)))

    def _do_sort_by_type(self, reverse=False):
        doc, parent, siblings = self._sorted_siblings_pool()
        if not siblings:
            self._status("Нет объектов для сортировки")
            return
        ordered = sorted(siblings, key=lambda o: self._type_suffix(o), reverse=reverse)
        self._apply_sort_order(doc, parent, ordered)
        self._status("Сортировка по типу ({}) — {} объектов".format(
            "Я→А" if reverse else "А→Я", len(ordered)))

    def _do_sort_by_poly_count(self, reverse=False):
        doc, parent, siblings = self._sorted_siblings_pool()
        if not siblings:
            self._status("Нет объектов для сортировки")
            return
        def poly_count(obj):
            try:
                return obj.GetPolygonCount()
            except Exception:
                return 0
        ordered = sorted(siblings, key=poly_count, reverse=not reverse)
        self._apply_sort_order(doc, parent, ordered)
        self._status("Сортировка по числу полигонов ({}) — {} объектов".format(
            "↓" if not reverse else "↑", len(ordered)))

    def _do_sort_by_children(self, reverse=False):
        doc, parent, siblings = self._sorted_siblings_pool()
        if not siblings:
            self._status("Нет объектов для сортировки")
            return
        def child_count(obj):
            n, child = 0, obj.GetDown()
            while child:
                n += 1
                child = child.GetNext()
            return n
        ordered = sorted(siblings, key=child_count, reverse=not reverse)
        self._apply_sort_order(doc, parent, ordered)
        self._status("Сортировка по числу дочерних ({}) — {} объектов".format(
            "↓" if not reverse else "↑", len(ordered)))

    def _do_sort_by_tag_count(self, reverse=False):
        doc, parent, siblings = self._sorted_siblings_pool()
        if not siblings:
            self._status("Нет объектов для сортировки")
            return
        def tag_count(obj):
            n, tag = 0, obj.GetFirstTag()
            while tag:
                n += 1
                tag = tag.GetNext()
            return n
        ordered = sorted(siblings, key=tag_count, reverse=not reverse)
        self._apply_sort_order(doc, parent, ordered)
        self._status("Сортировка по числу тегов ({}) — {} объектов".format(
            "↓" if not reverse else "↑", len(ordered)))

    def _do_reverse_order(self):
        doc, parent, siblings = self._sorted_siblings_pool()
        if not siblings:
            self._status("Нет объектов для сортировки")
            return
        ordered = list(reversed(siblings))
        self._apply_sort_order(doc, parent, ordered)
        self._status("Порядок обращён — {} объектов".format(len(ordered)))

    def _do_sort_tags_by_type(self, reverse=False):
        """
        Сортирует теги на каждом из выделенных объектов по числовому ID типа тега.
        Использует c4d.BaseTag.GetType() как первичный ключ, имя тега — как вторичный.
        """
        doc = c4d.documents.GetActiveDocument()
        sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if not sel:
            self._status("Выделите объекты для сортировки тегов")
            return
        doc.StartUndo()
        total_tags = 0
        for obj in sel:
            tags = []
            tag = obj.GetFirstTag()
            while tag:
                tags.append(tag)
                tag = tag.GetNext()
            if len(tags) < 2:
                continue
            def tag_type_key(t):
                return (t.GetType(), t.GetName().lower())
            sorted_tags = sorted(tags, key=tag_type_key, reverse=reverse)
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            for t in tags:
                t.Remove()
            prev = None
            for t in sorted_tags:
                if prev is None:
                    obj.InsertTag(t)
                else:
                    t.InsertAfter(prev)
                prev = t
                total_tags += 1
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Теги отсортированы по типу ({}) на {} объектах ({} тегов)".format(
            "Я→А" if reverse else "А→Я", len(sel), total_tags))

    def _do_sort_tags(self, reverse=False):
        """
        Сортирует теги на каждом из выделенных объектов по имени типа тега.
        Использует c4d.BaseTag.GetType() как ключ сортировки.
        """
        doc = c4d.documents.GetActiveDocument()
        sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if not sel:
            self._status("Выделите объекты для сортировки тегов")
            return
        doc.StartUndo()
        total_tags = 0
        for obj in sel:
            tags = []
            tag = obj.GetFirstTag()
            while tag:
                tags.append(tag)
                tag = tag.GetNext()
            if len(tags) < 2:
                continue
            # Сортируем по строковому имени типа (через GetTypeName если доступно,
            # иначе по числовому ID типа)
            def tag_key(t):
                try:
                    return t.GetName() or str(t.GetType())
                except Exception:
                    return str(t.GetType())
            sorted_tags = sorted(tags, key=tag_key, reverse=reverse)
            # Удаляем все теги
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            for t in tags:
                t.Remove()
            # Вставляем в новом порядке
            prev = None
            for t in sorted_tags:
                if prev is None:
                    obj.InsertTag(t)
                else:
                    t.InsertAfter(prev)
                prev = t
                total_tags += 1
        doc.EndUndo()
        c4d.EventAdd()
        self._status("Теги отсортированы ({}) на {} объектах ({} тегов)".format(
            "Я→А" if reverse else "А→Я", len(sel), total_tags))

    # ══════════════════════════════════════════════════════════════════════════
    #  МАРШРУТИЗАТОР КОМАНД
    # ══════════════════════════════════════════════════════════════════════════
    def Command(self, id, msg):
        DISPATCH = {
            # Выделение — поиск по имени
            BTN_SEL_NAME_EXACT:    lambda: self._do_select_by_name_search(exact=True),
            BTN_SEL_NAME_PART:     lambda: self._do_select_by_name_search(exact=False),
            # Выделение — по эталону
            BTN_SEL_SAME_NAME:     self._do_select_same_name,
            BTN_SEL_SAME_TAG:      self._do_select_same_tag,
            BTN_SEL_SAME_TYPE:     self._do_select_same_type,
            BTN_SEL_SAME_MAT:      self._do_select_by_mat,
            # Материал
            BTN_MAT_RENAME:        self._do_mat_rename,
            BTN_NAME_TO_MAT:       self._do_name_to_mat,
            # Найти и заменить
            BTN_FIND_REPLACE:      self._do_find_replace,
            # Префикс / Суффикс
            BTN_ADD_PREFIX:        self._do_add_prefix,
            BTN_ADD_SUFFIX:        self._do_add_suffix,
            BTN_STRIP_PREFIX:      self._do_strip_prefix,
            BTN_STRIP_SUFFIX:      self._do_strip_suffix,
            # Автонумерация
            BTN_NUM_APPEND:        lambda: self._do_numbering(False),
            BTN_NUM_PREPEND:       lambda: self._do_numbering(True),
            BTN_REMOVE_NUMS:       self._do_remove_nums,
            BTN_REMOVE_NUM_PREFIX: self._do_remove_num_prefix,
            # Регистр и очистка
            BTN_CASE_UPPER:        lambda: self._do_case('upper'),
            BTN_CASE_LOWER:        lambda: self._do_case('lower'),
            BTN_CASE_TITLE:        lambda: self._do_case('title'),
            BTN_FIRST_CAP:         self._do_first_cap,
            BTN_SP_TO_UNDER:       self._do_spaces_to_underscore,
            BTN_UNDER_TO_SP:       self._do_underscore_to_spaces,
            BTN_CLEAN_WS:          self._do_clean_whitespace,
            BTN_TYPE_SUFFIX:       self._do_add_type_suffix,
            BTN_TYPE_PREFIX:       self._do_add_type_prefix,
            BTN_RU_TO_EN:          self._do_ru_to_en,
            # Сортировка (однократные действия)
            BTN_SORT_REVERSE:      self._do_reverse_order,
        }
        if id == BTN_TOGGLE_PREVIEW:
            self._preview_visible = not self._preview_visible
            self.HideElement(GRP_PREVIEW, not self._preview_visible)
            self.SetString(BTN_TOGGLE_PREVIEW, "⊙" if not self._preview_visible else "◉")
            self.LayoutChanged(GRP_ROOT)
            return True
        # ── Toggle-кнопки сортировки: каждое нажатие меняет направление ─────
        _TOGGLE_SORT = {
            BTN_SORT_AZ:        (self._do_sort_by_name,
                                 "Имя А→Я", "Имя Я→А"),
            BTN_SORT_TYPE:      (self._do_sort_by_type,
                                 "Тип А→Я", "Тип Я→А"),
            BTN_SORT_CHILDREN:  (self._do_sort_by_children,
                                 "Дочерних ↓", "Дочерних ↑"),
            BTN_SORT_POLY_CNT:  (self._do_sort_by_poly_count,
                                 "Полигонов ↓", "Полигонов ↑"),
            BTN_SORT_TAGS:      (self._do_sort_tags,
                                 "Имя А→Я", "Имя Я→А"),
            BTN_SORT_TAGS_TYPE: (self._do_sort_tags_by_type,
                                 "Тип А→Я", "Тип Я→А"),
            BTN_SORT_TAG_CNT:   (self._do_sort_by_tag_count,
                                 "Число тегов ↓", "Число тегов ↑"),
        }
        if id in _TOGGLE_SORT:
            fn, lbl_fwd, lbl_rev = _TOGGLE_SORT[id]
            rev = self._sort_states.get(id, False)
            fn(reverse=rev)
            new_rev = not rev
            self._sort_states[id] = new_rev
            self.SetString(id, lbl_rev if new_rev else lbl_fwd)
            return True
        handler = DISPATCH.get(id)
        if handler:
            handler()
        return True


# ─── Плагин CommandData ──────────────────────────────────────────────────────
class RenamerPlugin(c4d.plugins.CommandData):
    """Обёртка CommandData: открывает/восстанавливает диалог как плагин меню."""

    _dialog = None  # единственный экземпляр диалога на сессию

    def Execute(self, doc):
        if self._dialog is None:
            self._dialog = RenamerDialog()
        return self._dialog.Open(
            dlgtype  = c4d.DLG_TYPE_ASYNC,
            pluginid = PLUGIN_ID,
            xpos     = -1,
            ypos     = -1,
            defaultw = DIALOG_DEFAULT_W,
            defaulth = DIALOG_DEFAULT_H,
        )

    def RestoreLayout(self, sec_ref):
        """Вызывается C4D при восстановлении layout — обязательно для плагинов с диалогом."""
        if self._dialog is None:
            self._dialog = RenamerDialog()
        return self._dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAAEmElEQVRYhe1WfUzUZRz/fJ/j/SUPodQCi9c7aAKBzLWBpsyV1tpiBaQrrVzOeNPx4kooyuELHGGOlq5yqdHSpsAfTdYkmgttMwRP4CAOyVAiAlHh1sHd/b79Ece9cHcc/zY+f/1+37fP5/k9v+/zfIFF/J/A5cl+XJMoX0gOzT51DS6FUZ8PohXuJsfp/vDPHfw+at34jbCIyT+X+rDBZ8Y1BaAbjGYI8Q0VdrfPL+B6XzkIWQBdmo84TD/mfay7NmXj3XbF9YAn7jQFr/69cdmasFFP+dmBH98+DJ+pIBhlCSBpM0CZAK5AZtpDe/o0zgWotccBAPFRO12Rc5XyaRC+A/gqJFMRlWj7XeVzTaIcpn/eBegdEBdQYe8Ja7+HI5KvtnI6GLvt7Y/Lfwg28d6UzuG3NB3DubXb66jflVgAoD0d9/iAshJeFALGEVbFhlORpsylgO111Ayg2XYlMREwiV8BejOxOu80kDcftz2mwXQbxKWsUj5PRT1JtgKIhsBS9uyntIIQErpbc1/o9X3sTkbivlSokTq3Pq8F44wjZnqvZwzALgBgleIsWHiZfRYBRvEJZCwBCLUvsPNW08oV+jF5Wkplk9P1kfgW8Djq1G8JTIZMypl9mz8B4CrlBRC1UJGm0p14p3VUMSGA6IKXcSXla6fmCujpCcS0eNja9OLIlYCGjkNtZVFb11VEZA47re4l/Q2lcsKG8HiyJyZ0pWCvSipW6wCAyyGoHJI5xrIFHX3PYlqcA9jfusiERyBu+i1HRUR2q8vlTYsJqPszEB950c7zEsgQy4wsIrA1OWBzEGk/g4AcLO2zDlBfznslXD+yOXDDmTdcCiBRAQn3uH5HHpYMrbTYORQGWQOIPrVuPzOsugACjAeIj7l56jUONxqQDADyqMho9pW8TxyITrJJ9ETb66dpwKJU+wAEgYDhMpjE+7biAIBLuTb2C8rV3HIswA4yGfwBwMCBECT5md/nxeTy/VgydNJCPvMFQLX25LPaADjdggvXPlqzYazjsPfG88+4JJ7ZAiRE7TKbZn7CNoB6UKjJIgLbp1kfROfAfB4Q2dYBWfElGG15FWH6u/2DPiHOBTDpIKQMB556sGelI3LAjTYEgAfNmV+Oei+5GpH6+TGnAhy0oTtw7yBSxWwCxAn4yqIpp2tyoSSuYNkCFwMJAVBfzjUN+C77BepGZ+fBbUzTUayOvO+KkKsV68FsoKLffgYAMesx6vP/G0gcY9uq3ZfSx9WRH2rrFE5Kb4H33CvcljzuKTDVg2QPzfWqtccd3YQ2BSrj0lilvM9VivyF5nO1Yj2rlGOsUhRY2xc0kJzsAB4NbFWvDS8+pDuYtsVPjGyjvb29LkV//ORSsLEMTDtAlEOFPafmFeBoILEpWpMoh6TfD6Z2rlK0ANTw3Oi14F7/UN3AwVVBENOPQCABRJsgmV4G6CdIlEQlmj77WpYuuNH/AVjKdmcoNSNGN+RXMNgYlTreFRamH1seZJiQzbh0AHWBpBZI4msq1nQ6q2ER0D4gh8yUBwcDiVsgGkr/q/PYxfaySfPVu4hFuIN/AW9lzrMffdlRAAAAAElFTkSuQmCC"
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
            fd = -1
            bmp.InitWith(tmp)
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return None
    return bmp


# ─── Регистрация ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME_V,
        info = 0,
        icon = _make_icon(),
        help = "Пакетное переименование объектов сцены",
        dat  = RenamerPlugin(),
    )