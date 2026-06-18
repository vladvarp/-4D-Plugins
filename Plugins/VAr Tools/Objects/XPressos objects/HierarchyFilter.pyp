# -*- coding: utf-8 -*-
"""
HierarchyFilter — Cinema 4D ObjectData Plugin
ID: 1068852
"""

import c4d # type: ignore
import os
import base64
import tempfile

__res__ = c4d.plugins.GeResource()
__res__.Init(os.path.dirname(__file__))

PLUGIN_ID   = 1068852
PLUGIN_NAME = "Hierarchy Filter v1.4.1"
OBJECT_NAME = "Hierarchy Filter"
PLUGIN_HELP = "Объект-фильтр иерархии для использования в Xpresso"

# SubID UserData
UD_OBJECT_TYPE    = 1
UD_TRAVERSE_MODE  = 2
UD_DEPTH          = 4
UD_PARENT_OBJ     = 3
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

    IE2_INEX_LABELS = ["Учета", "Исключения"]
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
        # 4. Родительский объект
        self.op.AddUserData(self._cycle_bc("Рекурсивно начиная с", [self.op.GetName()]))

        # 3. Глубина
        self.op.AddUserData(self._int_bc("Рекурсивная глубина", default=3))

        # 5. Результат фильтрации — только чтение
        self.op.AddUserData(self._inexclude_bc(" ", editable=False))
        # 6. Включить / Исключить
        self.op.AddUserData(self._cycle_bc("Метод", self.IE2_INEX_LABELS))
        # 7. Объект / Тип
        self.op.AddUserData(self._cycle_bc("Режим фильтра", self.IE2_OBJ_LABELS))
        # 8. Второй InExclude — пользователь заполняет сам
        self.op.AddUserData(self._inexclude_bc(" ", editable=True))

        # Значения по умолчанию
        did, _ = _ud_descid(self.op, UD_TRAVERSE_MODE)
        if did:
            self.op[did] = MODE_ALL
        did, _ = _ud_descid(self.op, UD_DEPTH)
        if did:
            self.op[did] = 3
        did, _ = _ud_descid(self.op, UD_IE2_INEX_MODE)
        if did:
            self.op[did] = IE2_EXCLUDE

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
        parent_labels = [self.op.GetName()]
        for obj, depth in all_parents:
            prefix = "-" * (depth + 1)
            label = prefix + " " + obj.GetName()
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
                    candidates = [o for o in candidates if any(o.IsInstanceOf(e.GetType()) and o == e for e in ie2_objects)]
                else:  # IE2_TYPE
                    candidates = [o for o in candidates if o.GetType() in ie2_types]
            else:  # IE2_EXCLUDE
                # Убираем те что в списке
                if ie2_obj_mode == IE2_OBJECT:
                    candidates = [o for o in candidates if not any(o == e for e in ie2_objects)]
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

        traverse_mode = _ud_get(op, UD_TRAVERSE_MODE)
        if traverse_mode is None:
            traverse_mode = MODE_ALL

        is_all_mode = (traverse_mode == MODE_ALL)

        for descid, bc in op.GetUserDataContainer():
            uid = descid[1].id

            if uid == UD_DEPTH:
                # Неактивны при "Все объекты", активны при "Рекурсивно"
                bc[c4d.DESC_EDITABLE] = not is_all_mode
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

            elif uid == UD_PARENT_OBJ:
                # Неактивны при "Все объекты", активны при "Рекурсивно"
                bc[c4d.DESC_EDITABLE] = not is_all_mode
                description.SetParameter(descid, bc, c4d.DESCID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Message(self, op, type_, data):

        if type_ == c4d.MSG_MENUPREPARE:
            if op.GetName() == PLUGIN_NAME:
                op.SetName(OBJECT_NAME)

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
                    c4d.MSG_DOCUMENTINFO):
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
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzU6MzUrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzU6MzUrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjA1NGEwYTUwLTVlOWItODA0Zi04NmI5LWRkNjlkZWQ3MjE1YiIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDowNTRhMGE1MC01ZTliLTgwNGYtODZiOS1kZDY5ZGVkNzIxNWIiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDowNTRhMGE1MC01ZTliLTgwNGYtODZiOS1kZDY5ZGVkNzIxNWIiPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjA1NGEwYTUwLTVlOWItODA0Zi04NmI5LWRkNjlkZWQ3MjE1YiIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/Por6WdYAAAP2SURBVFiFxZZbbFRVFIa/dc50TpkOFA21rYQgtkwrRNoHlAimjSGGKDH40gRa05YYjAR98ckbYUj0QdTExIREidJqL15jiPJASIw1UWNoUqpOU9taoYhUCr3Ydi6dOWf50FZnmCmdU0y6ns7a+1///s9ee629RVVZTjOWdXXAk+yISPaR3YMfI/oQAA5fU1myN9vQ5F2XFCcbAZ1/BvCGewCTefgshc2UFWD7ukE3AtynwBvpml1c3sEhjEMYQ04AJnmxn93SLeEMqA8YQT1tqBioGDieFpARBJ9bNncpCIWKsK0rN8WYsWI2bx6+GWTpKfiPeARyqnEkiiPRue9rN2CyMs/ikBtMCSMU4Nj16//yGgAXiyL7MYw1CNNu6dwLmLbuJS/Wh+E8+WDID8DF4lgjiI3f2OSWzv0h3L5ukIpSDwbtxdctLb5mKeiHbCnxsGHDkFs6930gyZr26TRAY7vkuYm7tT7wP5v7M5BkCj6Xm5ZmS0pB2z7dFRNOC5hzQmxL2V3bLmeyib+lu6C5TjtUqRKwURIqKLOp9IrQ2dAq97kRkPUZaK3VqqZajalSJUJnQ5t4dFaE09gmlgjfqrK1uVYT79foo9nyZiWguU474tAhYDpxdmf6y4ZWqc6BagXbyOF0c52ey4Y7JQW8uzXAtXDlvHth9PHy86MHDsdtn2eVNTS4666GF5KDT/V/+QHAno2P1SePn/n9vaN/x+8uz5GYU7aq5dg9hS1d/06u8Z3nqc6+eTe1ChJRL1aihoRZ+Ovo3tJLkzuLb8vt0YqiEz+u9vVeBZ5Ihhf4u2bjvU7K+K6y/f3j4fKJ7uED91+OVj1vTMSvlN3+0QAm10lEexbcARFBX9+yqc9beOzgxpcfcWwfb/1x9GTFVP942t45ntWT8bWNDpCfc7kJI5GGGbFWWsfl1f2WOeI8HX3z7Gpr5ogcCv2yaBX4zofGw4aVD7BpcigS+v7g8TQBIoeA3Dkvgmoa5tnygzt7/Ws32mLopRVFXwxs21EPWVRBWCx7/js/MWVmwpBcsQs8rAsSoytnjBw9l182NuC/cywTJnMVxH0PoHo9NxEfO/nT25+TIJCGSZitQASIIE5LBpbAM1e++m7QW/jZlFinuHrhSMb/WKwRaXBzEZa+hMdeD/SlATJbAI8xxITxigRDaQ8UV41IgqFhYnccBvpwtBxbF46x1ZjFeAbw+YKZFk/jz7YV6yf4GSx9EdOoxKAXR5wUgKEGDuVgdjNd+JoEvxlfkGupd4HW4Gdb4DkcZwdixlInbQuVH+jsf0M+ZeqmPLdyGWmQXPJKHmbGuyJlwjsTYfq3sxIkuijHQgKWw5b9RbTsAv4BywKwx8ZUCScAAAAASUVORK5CYII="
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