# -*- coding: utf-8 -*-
"""
HierarchyFilter — Cinema 4D ObjectData Plugin
ID: 1068840

Объект-Ноль с расширенными UserData для фильтрации и обхода иерархии.
Используется совместно с Xpresso для динамической выборки дочерних объектов.

UserData:
  - Dropdown "Тип объекта"   : динамически собирает типы из дочерних объектов
  - Dropdown "Режим обхода"  : Все / Текущий уровень / Рекурсивно
  - Integer  "Глубина"       : видим только при режиме "Рекурсивно"
  - Dropdown "Родит. объект" : дочерние Нуля у которых есть свои дети
                               (видим только при "Текущий уровень" / "Рекурсивно")
  - InExclude "Вкл./Искл."  : стандартное поле выбора объектов
"""

import c4d
from c4d import plugins
import os
import base64
import tempfile

# Обязательно для RegisterObjectPlugin
__res__ = c4d.plugins.GeResource()
__res__.Init(os.path.dirname(__file__))

# ─── Константы ───────────────────────────────────────────────────────────────
PLUGIN_ID   = 1068852
PLUGIN_NAME = "HierarchyFilter v1.0"
PLUGIN_HELP = "Объект-фильтр иерархии для использования в Xpresso"

# ID групп UserData
GRP_FILTER  = 1000
GRP_TRAVERSE = 1001

# ID параметров UserData (смещение от базы UD)
UD_OBJECT_TYPE   = 1   # Dropdown — тип объекта
UD_TRAVERSE_MODE = 2   # Dropdown — режим обхода
UD_DEPTH         = 3   # Integer  — глубина рекурсии
UD_PARENT_OBJ    = 4   # Dropdown — родительский объект
UD_INEXCLUDE     = 5   # InExclude

# Значения Dropdown "Режим обхода"
MODE_ALL       = 0
MODE_LEVEL     = 1
MODE_RECURSIVE = 2

# ─── Иконка (base64 PNG 32×32, нарисована программно через PIL-совместимый raw)
# Простая иконка: синий фон, белая решётка иерархии
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAB2UlEQVR4nO2Wv0oDQRDGf5de"
    "YmFhYSoLC0E8gZWIhYiksLGwsLCwsLCwsLDQJiBiYWFhYSoLC0E8gbWIhYWFhYWFhYWFhY"
    "WFrYFkl2Rnd29v75IJDCz77e7MN99mdi8hIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi"
    "IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiLSBv4AGQD"
    "XZVtptwAAAABJRU5ErkJggg=="
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


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _get_type_name(obj):
    """Возвращает человекочитаемое имя типа объекта."""
    type_id = obj.GetType()
    # Пробуем получить имя типа из самого объекта
    try:
        name = obj.GetTypeName()
        if name:
            return name
    except Exception:
        pass
    return "Type_%d" % type_id


def _collect_direct_children(null_obj):
    """Возвращает список прямых дочерних объектов нуля."""
    children = []
    child = null_obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


def _collect_all_recursive(obj, depth=0, max_depth=-1):
    """Рекурсивно собирает все объекты начиная с прямых детей obj."""
    result = []
    child = obj.GetDown()
    while child:
        result.append((child, depth))
        if max_depth < 0 or depth < max_depth - 1:
            result.extend(_collect_all_recursive(child, depth + 1, max_depth))
        child = child.GetNext()
    return result


def _has_children(obj):
    return obj.GetDown() is not None


# ─── Менеджер UserData ────────────────────────────────────────────────────────

class UserDataManager:
    """
    Строит и обновляет UserData на объекте-ноле.
    Все параметры хранятся с фиксированными ID чтобы Xpresso ссылки не рвались.
    """

    # Метки режимов обхода
    TRAVERSE_LABELS = ["Все объекты",
                       "Только текущая иерархия",
                       "Рекурсивно"]

    def __init__(self, op):
        self.op = op

    # ── Утилиты ──────────────────────────────────────────────────────────────

    def _find_ud_by_id(self, uid):
        """Ищет UserData по SubID (нашему UD_* константу)."""
        ud = self.op.GetUserDataContainer()
        for descid, bc in ud:
            sub = descid[1]
            if sub.id == uid:
                return descid, bc
        return None, None

    def _ud_exists(self, uid):
        did, _ = self._find_ud_by_id(uid)
        return did is not None

    # ── Создание параметров ───────────────────────────────────────────────────

    def _add_group(self, uid, name, parent_id=c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA))):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]      = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_TITLEBAR]  = True
        did = self.op.AddUserData(bc)
        return did

    def _make_cycle_bc(self, name, items_list):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
        cycle_bc = c4d.BaseContainer()
        for i, label in enumerate(items_list):
            cycle_bc[i] = label
        bc[c4d.DESC_CYCLE] = cycle_bc
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        return bc

    def _make_int_bc(self, name, default=0, minval=1, maxval=99):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_MIN]        = minval
        bc[c4d.DESC_MAX]        = maxval
        bc[c4d.DESC_DEFAULT]    = default
        bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
        return bc

    def _make_inexclude_bc(self, name):
        bc = c4d.GetCustomDatatypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_OFF
        return bc

    # ── Инициализация (первый запуск) ─────────────────────────────────────────

    def ensure_created(self):
        """Создаёт все UserData если их ещё нет."""
        if self._ud_exists(UD_OBJECT_TYPE):
            return  # уже инициализировано

        # 1. Тип объекта — изначально только "Все типы"
        bc = self._make_cycle_bc("Тип объекта", ["Все типы"])
        self.op.AddUserData(bc)

        # 2. Режим обхода
        bc = self._make_cycle_bc("Режим обхода", self.TRAVERSE_LABELS)
        self.op.AddUserData(bc)

        # 3. Глубина рекурсии
        bc = self._make_int_bc("Глубина", default=3, minval=1, maxval=99)
        self.op.AddUserData(bc)

        # 4. Родительский объект — заполняется динамически
        bc = self._make_cycle_bc("Родит. объект", ["(нет)"])
        self.op.AddUserData(bc)

        # 5. InExclude
        bc = self._make_inexclude_bc("Включить / Исключить")
        self.op.AddUserData(bc)

    # ── Динамическое обновление ───────────────────────────────────────────────

    def _get_ud_value(self, uid):
        ud = self.op.GetUserDataContainer()
        for descid, bc in ud:
            sub = descid[1]
            if sub.id == uid:
                return self.op[descid]
        return None

    def _set_cycle_items(self, uid, items_list):
        """Обновляет список пунктов в Dropdown не меняя текущего значения."""
        ud = self.op.GetUserDataContainer()
        for descid, bc in ud:
            sub = descid[1]
            if sub.id == uid:
                cycle_bc = c4d.BaseContainer()
                for i, label in enumerate(items_list):
                    cycle_bc[i] = label
                bc[c4d.DESC_CYCLE] = cycle_bc
                self.op.SetUserDataContainer(descid, bc)
                return

    def refresh(self):
        """
        Обновляет динамические Dropdown-ы на основе текущих дочерних объектов.
        Вызывается каждый раз из GetDDescription / Execute.
        """
        children = _collect_direct_children(self.op)

        # ── Dropdown 1: типы объектов ─────────────────────────────────────────
        seen_types  = {}   # type_id → label
        for obj in children:
            tid   = obj.GetType()
            if tid not in seen_types:
                seen_types[tid] = _get_type_name(obj)
            # Рекурсивно обходим всех потомков тоже
            for (sub_obj, _) in _collect_all_recursive(obj):
                stid = sub_obj.GetType()
                if stid not in seen_types:
                    seen_types[stid] = _get_type_name(sub_obj)

        type_labels = ["Все типы"] + sorted(seen_types.values())
        self._set_cycle_items(UD_OBJECT_TYPE, type_labels)

        # ── Dropdown 4: родительские объекты (у которых есть дети) ───────────
        parent_candidates = [c for c in children if _has_children(c)]
        parent_labels = ["(нет)"] + [obj.GetName() for obj in parent_candidates]
        self._set_cycle_items(UD_PARENT_OBJ, parent_labels)


# ─── ObjectData Plugin ───────────────────────────────────────────────────────

class HierarchyFilterObject(c4d.plugins.ObjectData):

    def __init__(self):
        self._udm = None

    # Вызывается при добавлении объекта в сцену
    def Init(self, op, isload=False):
        self._udm = UserDataManager(op)
        self._udm.ensure_created()
        # Установить значения по умолчанию
        self._set_defaults(op)
        return True

    def _set_defaults(self, op):
        ud = op.GetUserDataContainer()
        for descid, bc in ud:
            sub = descid[1]
            uid = sub.id
            if uid == UD_TRAVERSE_MODE:
                if op[descid] is None:
                    op[descid] = MODE_ALL
            elif uid == UD_DEPTH:
                if op[descid] is None:
                    op[descid] = 3

    # Вызывается при каждом обновлении параметров (скрыть/показать поля)
    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription(op.GetType()):
            return False, flags

        # Инициализируем/обновляем UserData
        udm = UserDataManager(op)
        udm.ensure_created()
        udm.refresh()

        # Читаем текущий режим обхода
        traverse_mode = MODE_ALL
        ud = op.GetUserDataContainer()
        for descid, bc in ud:
            sub = descid[1]
            if sub.id == UD_TRAVERSE_MODE:
                val = op[descid]
                if val is not None:
                    traverse_mode = val
                break

        # Скрываем/показываем "Глубина" и "Родит. объект"
        for descid, bc in op.GetUserDataContainer():
            sub = descid[1]
            uid = sub.id

            if uid == UD_DEPTH:
                # Показываем только при рекурсивном режиме
                visible = (traverse_mode == MODE_RECURSIVE)
                bc[c4d.DESC_HIDE] = not visible
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

            elif uid == UD_PARENT_OBJ:
                # Показываем только при "Текущий уровень" или "Рекурсивно"
                visible = (traverse_mode in (MODE_LEVEL, MODE_RECURSIVE))
                bc[c4d.DESC_HIDE] = not visible
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    # Вызывается при изменении любого параметра
    def Message(self, op, type_, data):
        if type_ in (c4d.MSG_UPDATE, c4d.MSG_DOCUMENTINFO,
                     c4d.MSG_MENUPREPARE, c4d.MSG_DESCRIPTION_COMMAND):
            udm = UserDataManager(op)
            udm.ensure_created()
            udm.refresh()
        return True

    # ObjectData должен возвращать виртуальный объект (Null просто возвращает None)
    def GetVirtualObjects(self, op, hh):
        # Обновляем данные при каждом пересчёте
        udm = UserDataManager(op)
        udm.ensure_created()
        udm.refresh()
        # Возвращаем None — объект не генерирует полигонов
        return c4d.BaseObject(c4d.Onull)

    def CheckDirty(self, op, doc):
        # Пересчитываем каждый кадр чтобы динамические списки были актуальны
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ok = plugins.RegisterObjectPlugin(
        id          = PLUGIN_ID,
        str         = PLUGIN_NAME,
        g           = HierarchyFilterObject,
        description = "",
        icon        = _make_icon(),
        info        = 0,
    )
    if not ok:
        raise RuntimeError("HierarchyFilter: регистрация не удалась")
    print("HierarchyFilter: плагин зарегистрирован (ID={})".format(PLUGIN_ID))