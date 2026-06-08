# -*- coding: utf-8 -*-
"""
HierarchyFilter — Cinema 4D ObjectData Plugin
ID: 1068852
"""

import c4d
import os
import base64
import tempfile

__res__ = c4d.plugins.GeResource()
__res__.Init(os.path.dirname(__file__))

PLUGIN_ID   = 1068852
PLUGIN_NAME = "HierarchyFilter v1.0"
PLUGIN_HELP = "Объект-фильтр иерархии для использования в Xpresso"

# SubID UserData
UD_OBJECT_TYPE    = 1
UD_TRAVERSE_MODE  = 2
UD_DEPTH          = 3
UD_PARENT_OBJ     = 4
UD_INEXCLUDE      = 5   # Результат фильтрации (только чтение)
UD_IE2_INEX_MODE  = 6   # Включить / Исключить
UD_IE2_OBJ_MODE   = 7   # Объект / Тип
UD_INEXCLUDE2     = 8   # Второй InExclude (пользовательский)

MODE_ALL       = 0
MODE_RECURSIVE = 1

IE2_INCLUDE = 0
IE2_EXCLUDE = 1

IE2_OBJECT = 0
IE2_TYPE   = 1


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _get_type_name(obj):
    try:
        name = obj.GetTypeName()
        if name:
            return name
    except Exception:
        pass
    return "Type_%d" % obj.GetType()


def _collect_direct_children(obj):
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children


def _collect_recursive(obj, depth=0, max_depth=-1):
    """Возвращает список (object, depth_level)."""
    result = []
    child = obj.GetDown()
    while child:
        result.append((child, depth))
        if max_depth < 0 or depth < max_depth - 1:
            result.extend(_collect_recursive(child, depth + 1, max_depth))
        child = child.GetNext()
    return result


def _collect_parents_recursive(obj, depth=0, max_depth=-1):
    """
    Собирает все объекты у которых есть хоть один ребёнок, рекурсивно по всей иерархии.
    Возвращает список (object, depth_level).
    """
    result = []
    child = obj.GetDown()
    while child:
        if child.GetDown() is not None:
            result.append((child, depth))
            if max_depth < 0 or depth < max_depth - 1:
                result.extend(_collect_parents_recursive(child, depth + 1, max_depth))
        child = child.GetNext()
    return result


def _has_children(obj):
    return obj.GetDown() is not None


def _ud_descid(op, uid):
    for descid, bc in op.GetUserDataContainer():
        if descid[1].id == uid:
            return descid, bc
    return None, None


def _ud_get(op, uid):
    did, _ = _ud_descid(op, uid)
    if did is not None:
        return op[did]
    return None


# ─── Менеджер UserData ────────────────────────────────────────────────────────

class UserDataManager:

    TRAVERSE_LABELS = [
        "Все объекты",
        "Рекурсивно",
    ]

    IE2_INEX_LABELS = ["Включить", "Исключить"]
    IE2_OBJ_LABELS  = ["Объект", "Тип"]

    def __init__(self, op):
        self.op = op

    # ── Фабрики ───────────────────────────────────────────────────────────────

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

    def _inexclude_bc(self, name, editable=False):
        bc = c4d.GetCustomDatatypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]       = name
        bc[c4d.DESC_SHORT_NAME] = name
        bc[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_OFF
        bc[c4d.DESC_EDITABLE]   = editable
        return bc

    # ── Создание ──────────────────────────────────────────────────────────────

    def ensure_created(self):
        did, _ = _ud_descid(self.op, UD_OBJECT_TYPE)
        if did is not None:
            return

        # 1. Тип объекта
        self.op.AddUserData(self._cycle_bc("Тип объекта", ["Все типы"]))
        # 2. Режим обхода
        self.op.AddUserData(self._cycle_bc("Режим обхода", self.TRAVERSE_LABELS))
        # 3. Глубина
        self.op.AddUserData(self._int_bc("Глубина", default=3))
        # 4. Родительский объект
        self.op.AddUserData(self._cycle_bc("Родительский объект", ["(нет)"]))
        # 5. Результат фильтрации — только чтение
        self.op.AddUserData(self._inexclude_bc("Результат фильтрации", editable=False))
        # 6. Включить / Исключить
        self.op.AddUserData(self._cycle_bc("Действие", self.IE2_INEX_LABELS))
        # 7. Объект / Тип
        self.op.AddUserData(self._cycle_bc("Режим фильтра", self.IE2_OBJ_LABELS))
        # 8. Второй InExclude — пользователь заполняет сам
        self.op.AddUserData(self._inexclude_bc("Включить / Исключить", editable=True))

        # Значения по умолчанию
        did, _ = _ud_descid(self.op, UD_TRAVERSE_MODE)
        if did:
            self.op[did] = MODE_ALL
        did, _ = _ud_descid(self.op, UD_DEPTH)
        if did:
            self.op[did] = 3

    # ── Обновление дропдаунов ─────────────────────────────────────────────────

    def _update_cycle(self, uid, items):
        did, bc = _ud_descid(self.op, uid)
        if did is None:
            return
        cycle_bc = c4d.BaseContainer()
        for i, label in enumerate(items):
            cycle_bc[i] = label
        bc[c4d.DESC_CYCLE] = cycle_bc
        self.op.SetUserDataContainer(did, bc)

    def refresh_dropdowns(self):
        children = _collect_direct_children(self.op)

        # Dropdown 1 — типы из всей иерархии
        seen = {}
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

        # Dropdown 4 — все родители по всей глубине иерархии
        # Глубина показывается через префикс "-", "--", "---" и т.д.
        all_parents = _collect_parents_recursive(self.op)
        parent_labels = ["(нет)"]
        for obj, depth in all_parents:
            prefix = "-" * depth if depth > 0 else ""
            label = (prefix + " " + obj.GetName()) if prefix else obj.GetName()
            parent_labels.append(label)
        self._update_cycle(UD_PARENT_OBJ, parent_labels)

    # ── Применение фильтра → InExclude 1 (только чтение) ─────────────────────

    def apply_filter(self):
        did_ie, _ = _ud_descid(self.op, UD_INEXCLUDE)
        if did_ie is None:
            return

        traverse_mode = _ud_get(self.op, UD_TRAVERSE_MODE) or MODE_ALL
        depth_val     = _ud_get(self.op, UD_DEPTH) or 3
        type_idx      = _ud_get(self.op, UD_OBJECT_TYPE) or 0
        parent_idx    = _ud_get(self.op, UD_PARENT_OBJ) or 0

        # Второй InExclude — фильтр включения/исключения
        ie2_inex_mode = _ud_get(self.op, UD_IE2_INEX_MODE) or IE2_INCLUDE
        ie2_obj_mode  = _ud_get(self.op, UD_IE2_OBJ_MODE)  or IE2_OBJECT
        did_ie2, _    = _ud_descid(self.op, UD_INEXCLUDE2)
        ie2_data      = self.op[did_ie2] if did_ie2 else None

        children = _collect_direct_children(self.op)

        # Карта тип → имя для фильтра
        seen = {}
        for obj in children:
            tid = obj.GetType()
            if tid not in seen:
                seen[tid] = _get_type_name(obj)
            for sub, _ in _collect_recursive(obj):
                stid = sub.GetType()
                if stid not in seen:
                    seen[stid] = _get_type_name(sub)

        sorted_types = sorted(seen.items(), key=lambda x: x[1])
        filter_type_id = None
        if type_idx > 0 and (type_idx - 1) < len(sorted_types):
            filter_type_id = sorted_types[type_idx - 1][0]

        # Стартовый объект из Dropdown 4 (с учётом всей иерархии родителей)
        all_parents = _collect_parents_recursive(self.op)
        if parent_idx > 0 and (parent_idx - 1) < len(all_parents):
            start_obj = all_parents[parent_idx - 1][0]
        else:
            start_obj = self.op

        # Сбор кандидатов
        candidates = []
        if traverse_mode == MODE_ALL:
            for obj, _ in _collect_recursive(self.op):
                candidates.append(obj)
        elif traverse_mode == MODE_RECURSIVE:
            for obj, _ in _collect_recursive(start_obj, max_depth=depth_val):
                candidates.append(obj)

        # Фильтр по типу (Dropdown 1)
        if filter_type_id is not None:
            candidates = [o for o in candidates if o.GetType() == filter_type_id]

        # Применяем второй InExclude
        if ie2_data is not None:
            count = ie2_data.GetObjectCount()
            ie2_objects = []
            ie2_types   = set()
            for i in range(count):
                obj = ie2_data.ObjectFromIndex(self.op.GetDocument(), i)
                if obj:
                    ie2_objects.append(obj)
                    ie2_types.add(obj.GetType())

            if ie2_inex_mode == IE2_INCLUDE:
                # Оставляем только те что в списке
                if ie2_obj_mode == IE2_OBJECT:
                    ie2_set = set(id(o) for o in ie2_objects)
                    candidates = [o for o in candidates if id(o) in ie2_set]
                else:  # IE2_TYPE
                    candidates = [o for o in candidates if o.GetType() in ie2_types]
            else:  # IE2_EXCLUDE
                # Убираем те что в списке
                if ie2_obj_mode == IE2_OBJECT:
                    ie2_set = set(id(o) for o in ie2_objects)
                    candidates = [o for o in candidates if id(o) not in ie2_set]
                else:  # IE2_TYPE
                    candidates = [o for o in candidates if o.GetType() not in ie2_types]

        # Записываем в InExclude 1
        ie_data = c4d.InExcludeData()
        for obj in candidates:
            ie_data.InsertObject(obj, 1)
        self.op[did_ie] = ie_data


# ─── ObjectData Plugin ───────────────────────────────────────────────────────

class HierarchyFilterObject(c4d.plugins.ObjectData):

    def Init(self, op, isload=False):
        udm = UserDataManager(op)
        udm.ensure_created()
        return True

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription(op.GetType()):
            return False, flags

        udm = UserDataManager(op)
        udm.ensure_created()
        udm.refresh_dropdowns()

        traverse_mode = _ud_get(op, UD_TRAVERSE_MODE) or MODE_ALL

        for descid, bc in op.GetUserDataContainer():
            uid = descid[1].id

            if uid == UD_DEPTH:
                # Показываем только при рекурсивном режиме
                bc[c4d.DESC_HIDE] = (traverse_mode != MODE_RECURSIVE)
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

            elif uid == UD_PARENT_OBJ:
                # Показываем только при рекурсивном режиме
                bc[c4d.DESC_HIDE] = (traverse_mode != MODE_RECURSIVE)
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Message(self, op, type_, data):
        if type_ == c4d.MSG_DESCRIPTION_POSTSETPARAMETER:
            # Откатываем ручное редактирование первого InExclude
            if data and "descid" in data:
                changed_id = data["descid"]
                if changed_id and changed_id[1].id == UD_INEXCLUDE:
                    udm = UserDataManager(op)
                    udm.apply_filter()
                    return True
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

    def GetVirtualObjects(self, op, hh):
        udm = UserDataManager(op)
        udm.ensure_created()
        udm.refresh_dropdowns()
        udm.apply_filter()
        return c4d.BaseObject(c4d.Onull)

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK


# ─── Иконка ──────────────────────────────────────────────────────────────────
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