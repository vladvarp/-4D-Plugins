# -*- coding: utf-8 -*-
"""
HierarchyFilter — Cinema 4D ObjectData Plugin
ID: 1068852

Объект-Ноль с расширенными UserData для фильтрации и обхода иерархии.
Используется совместно с Xpresso для динамической выборки дочерних объектов.

UserData:
  - Dropdown "Тип объекта"    : динамически собирает типы из дочерних объектов
  - Dropdown "Режим обхода"   : Все / Текущий уровень / Рекурсивно
  - Integer  "Глубина"        : видим только при режиме "Рекурсивно"
  - Dropdown "Родит. объект"  : дочерние у которых есть свои дети
                                (видим только при "Текущий уровень" / "Рекурсивно")
  - InExclude "Результат"     : заполняется автоматически, только для чтения
"""

import c4d
import os
import base64
import tempfile

__res__ = c4d.plugins.GeResource()
__res__.Init(os.path.dirname(__file__))

# ─── Константы ───────────────────────────────────────────────────────────────
PLUGIN_ID   = 1068852
PLUGIN_NAME = "HierarchyFilter v1.0"
PLUGIN_HELP = "Объект-фильтр иерархии для использования в Xpresso"

# SubID наших UserData-параметров (1-based, порядок создания)
UD_OBJECT_TYPE   = 1
UD_TRAVERSE_MODE = 2
UD_DEPTH         = 3
UD_PARENT_OBJ    = 4
UD_INEXCLUDE     = 5

# Значения Dropdown "Режим обхода"
MODE_ALL       = 0
MODE_LEVEL     = 1
MODE_RECURSIVE = 2


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _get_type_name(obj):
    """Возвращает человекочитаемое имя типа объекта через C4D API."""
    try:
        name = obj.GetTypeName()
        if name:
            return name
    except Exception:
        pass
    return "Type_%d" % obj.GetType()


def _collect_direct_children(obj):
    """Прямые дочерние объекты (один уровень)."""
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


def _collect_recursive(obj, depth=0, max_depth=-1):
    """
    Рекурсивно собирает всех потомков obj.
    max_depth=-1 — без ограничения глубины.
    Возвращает список (object, depth_level).
    """
    result = []
    child = obj.GetDown()
    while child:
        result.append((child, depth))
        if max_depth < 0 or depth < max_depth - 1:
            result.extend(_collect_recursive(child, depth + 1, max_depth))
        child = child.GetNext()
    return result


def _has_children(obj):
    return obj.GetDown() is not None


def _ud_descid(op, uid):
    """Возвращает (DescID, BaseContainer) UserData по нашему SubID или (None, None)."""
    for descid, bc in op.GetUserDataContainer():
        if descid[1].id == uid:
            return descid, bc
    return None, None


def _ud_get(op, uid):
    """Значение UserData-параметра по SubID."""
    did, _ = _ud_descid(op, uid)
    if did is not None:
        return op[did]
    return None


# ─── Менеджер UserData ────────────────────────────────────────────────────────

class UserDataManager:

    TRAVERSE_LABELS = [
        "Все объекты",
        "Только текущая иерархия",
        "Рекурсивно",
    ]

    def __init__(self, op):
        self.op = op

    # ── Фабрики BaseContainer ─────────────────────────────────────────────────

    def _cycle_bc(self, name, items):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_CUSTOMGUI]  = c4d.CUSTOMGUI_CYCLE
        cycle_bc = c4d.BaseContainer()
        for i, label in enumerate(items):
            cycle_bc[i] = label
        bc[c4d.DESC_CYCLE]   = cycle_bc
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        return bc

    def _int_bc(self, name, default=3, minval=1, maxval=99):
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_MIN]        = minval
        bc[c4d.DESC_MAX]        = maxval
        bc[c4d.DESC_DEFAULT]    = default
        bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_ON
        return bc

    def _inexclude_bc(self, name):
        bc = c4d.GetCustomDatatypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_OFF
        # Пометим как только для чтения через DESC_EDITABLE
        # (будем дополнительно защищать через Message)
        bc[c4d.DESC_EDITABLE]   = False
        return bc

    # ── Создание (первый запуск) ──────────────────────────────────────────────

    def ensure_created(self):
        """Создаёт все UserData если их ещё нет. Безопасно вызывать многократно."""
        did, _ = _ud_descid(self.op, UD_OBJECT_TYPE)
        if did is not None:
            return  # уже создано

        self.op.AddUserData(self._cycle_bc("Тип объекта", ["Все типы"]))
        self.op.AddUserData(self._cycle_bc("Режим обхода", self.TRAVERSE_LABELS))
        self.op.AddUserData(self._int_bc("Глубина", default=3))
        self.op.AddUserData(self._cycle_bc("Родительский объект", ["(нет)"]))
        self.op.AddUserData(self._inexclude_bc("Результат фильтрации"))

        # Значения по умолчанию
        did, _ = _ud_descid(self.op, UD_TRAVERSE_MODE)
        if did:
            self.op[did] = MODE_ALL

        did, _ = _ud_descid(self.op, UD_DEPTH)
        if did:
            self.op[did] = 3

    # ── Обновление Dropdown-ов ────────────────────────────────────────────────

    def _update_cycle(self, uid, items):
        """Меняет пункты Dropdown не трогая текущее значение."""
        did, bc = _ud_descid(self.op, uid)
        if did is None:
            return
        cycle_bc = c4d.BaseContainer()
        for i, label in enumerate(items):
            cycle_bc[i] = label
        bc[c4d.DESC_CYCLE] = cycle_bc
        self.op.SetUserDataContainer(did, bc)

    def refresh_dropdowns(self):
        """Обновляет динамические Dropdown-ы под текущую иерархию."""
        children = _collect_direct_children(self.op)

        # Dropdown 1 — типы объектов (из всей вложенной иерархии)
        seen = {}  # type_id → label
        for obj in children:
            tid = obj.GetType()
            if tid not in seen:
                seen[tid] = _get_type_name(obj)
            for sub, _ in _collect_recursive(obj):
                stid = sub.GetType()
                if stid not in seen:
                    seen[stid] = _get_type_name(sub)

        type_labels = ["Все типы"] + sorted(seen.values())
        self._update_cycle(UD_OBJECT_TYPE, type_labels)

        # Dropdown 4 — родительские объекты (у которых есть хотя бы один ребёнок)
        parents = [c for c in children if _has_children(c)]
        parent_labels = ["(нет)"] + [obj.GetName() for obj in parents]
        self._update_cycle(UD_PARENT_OBJ, parent_labels)

    # ── Заполнение InExclude ──────────────────────────────────────────────────

    def apply_filter(self):
        """
        Вычисляет список объектов по настройкам фильтра
        и записывает результат в InExclude-поле.
        Пользователь не имеет доступа к этому полю — только для чтения.
        """
        did_ie, _ = _ud_descid(self.op, UD_INEXCLUDE)
        if did_ie is None:
            return

        traverse_mode = _ud_get(self.op, UD_TRAVERSE_MODE) or MODE_ALL
        depth_val     = _ud_get(self.op, UD_DEPTH) or 3
        type_idx      = _ud_get(self.op, UD_OBJECT_TYPE) or 0
        parent_idx    = _ud_get(self.op, UD_PARENT_OBJ) or 0

        children = _collect_direct_children(self.op)

        # Строим карту индекс→type_id для Dropdown 1
        seen = {}
        for obj in children:
            tid = obj.GetType()
            if tid not in seen:
                seen[tid] = _get_type_name(obj)
            for sub, _ in _collect_recursive(obj):
                stid = sub.GetType()
                if stid not in seen:
                    seen[stid] = _get_type_name(sub)

        sorted_types = sorted(seen.items(), key=lambda x: x[1])  # сортируем по имени
        # type_idx=0 → "Все типы" → нет фильтра
        filter_type_id = None
        if type_idx > 0 and (type_idx - 1) < len(sorted_types):
            filter_type_id = sorted_types[type_idx - 1][0]

        # Определяем стартовый объект для обхода (Dropdown 4)
        parents = [c for c in children if _has_children(c)]
        if parent_idx > 0 and (parent_idx - 1) < len(parents):
            start_obj = parents[parent_idx - 1]
        else:
            start_obj = self.op

        # Собираем объекты согласно режиму обхода
        candidates = []
        if traverse_mode == MODE_ALL:
            for obj, _ in _collect_recursive(self.op):
                candidates.append(obj)
        elif traverse_mode == MODE_LEVEL:
            candidates = _collect_direct_children(start_obj)
        elif traverse_mode == MODE_RECURSIVE:
            for obj, _ in _collect_recursive(start_obj, max_depth=depth_val):
                candidates.append(obj)

        # Фильтр по типу
        if filter_type_id is not None:
            candidates = [o for o in candidates if o.GetType() == filter_type_id]

        # Записываем в InExclude
        ie_data = c4d.InExcludeData()
        for obj in candidates:
            ie_data.InsertObject(obj, 1)  # 1 = включён

        self.op[did_ie] = ie_data


# ─── ObjectData Plugin ───────────────────────────────────────────────────────

class HierarchyFilterObject(c4d.plugins.ObjectData):

    def Init(self, op, isload=False):
        udm = UserDataManager(op)
        udm.ensure_created()
        return True

    # ── Скрытие/показ полей ───────────────────────────────────────────────────

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription(op.GetType()):
            return False, flags

        udm = UserDataManager(op)
        udm.ensure_created()
        udm.refresh_dropdowns()

        traverse_mode = _ud_get(op, UD_TRAVERSE_MODE) or MODE_ALL

        # Итерируемся по UserData и управляем видимостью
        for descid, bc in op.GetUserDataContainer():
            uid = descid[1].id

            if uid == UD_DEPTH:
                # "Глубина" — только при рекурсивном режиме
                bc[c4d.DESC_HIDE] = (traverse_mode != MODE_RECURSIVE)
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

            elif uid == UD_PARENT_OBJ:
                # "Родительский объект" — только при MODE_LEVEL или MODE_RECURSIVE
                bc[c4d.DESC_HIDE] = (traverse_mode == MODE_ALL)
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    # ── Реакция на изменения ──────────────────────────────────────────────────

    def Message(self, op, type_, data):
        if type_ == c4d.MSG_DESCRIPTION_POSTSETPARAMETER:
            # Перехватываем любые изменения InExclude-поля и откатываем их.
            # Пользователь не должен редактировать это поле вручную.
            if data and "descid" in data:
                changed_id = data["descid"]
                if changed_id and changed_id[1].id == UD_INEXCLUDE:
                    # Перезаписываем вычисленным значением
                    udm = UserDataManager(op)
                    udm.apply_filter()
                    return True

            # При любом другом изменении параметра — обновляем всё
            udm = UserDataManager(op)
            udm.ensure_created()
            udm.refresh_dropdowns()
            udm.apply_filter()

        elif type_ in (c4d.MSG_UPDATE,
                       c4d.MSG_DOCUMENTINFO,
                       c4d.MSG_MENUPREPARE):
            udm = UserDataManager(op)
            udm.ensure_created()
            udm.refresh_dropdowns()
            udm.apply_filter()

        return True

    # ── Виртуальный объект ────────────────────────────────────────────────────

    def GetVirtualObjects(self, op, hh):
        udm = UserDataManager(op)
        udm.ensure_created()
        udm.refresh_dropdowns()
        udm.apply_filter()
        return c4d.BaseObject(c4d.Onull)

    def CheckDirty(self, op, doc):
        # Помечаем объект грязным каждый кадр — чтобы динамические списки
        # всегда отражали актуальную иерархию
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABSUlEQVR4nNVXIRaC"
    "QBBd9nkTi0WDBgtWs5lkMBnsnsBuMBm8hMUqhSBBioWzaNoVlhl2ZkB4/jS7Dvu/"
    "w8wHAlXAeBq+VQfI0jgwsQ245M/H3caT2UIsQjclh9YUGM6gKXkRkkpo9hUt4/8E"
    "YGWWlF8kACKTkosFGNJrkjciV0qpAfbDPFzaOIlvosOHu+/E5EdYKFiBIjm05pJD"
    "a1QARsYRgZFB++gtgHA4XUh75xf9TJaA/XZNysMqAKFyC7CG4zQi1nDQPtiELplk"
    "Clwy1hQY0lUUiUfQkG5GOUpeK6Ar2Cb0GQ/FmHw5kDFp90LJmpKDGZP2GQ/FmHw5"
    "dcbUew/UCqAaT5MztM94KMbky6kzJg0dwF1TcjBjYr8Vt43Kw4jzIJHArUSpCX9N"
    "DnH0P4bFD8WukaVxoE2gFD4ubcJwGM7Sv+/j8/wDsOykd7X786wAAAAASUVORK5C"
    "YII="
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


# ─── Регистрация ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = PLUGIN_ID,
        str         = PLUGIN_NAME,
        g           = HierarchyFilterObject,
        description = "",
        icon        = _make_icon(),
        info        = c4d.OBJECT_GENERATOR | c4d.OBJECT_INPUT,
    )
