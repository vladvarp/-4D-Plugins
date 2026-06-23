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
PLUGIN_NAME = "Hierarchy Filter v1.5"
OBJECT_NAME = "Hierarchy Filter"
PLUGIN_HELP = "Объект-фильтр иерархии для использования в Xpresso"

# SubID UserData (legacy, kept for reference)
UD_OBJECT_TYPE    = 1
UD_TRAVERSE_MODE  = 2
UD_DEPTH          = 4
UD_PARENT_OBJ     = 3
UD_INEXCLUDE      = 5
UD_IE2_INEX_MODE  = 6
UD_IE2_OBJ_MODE   = 7
UD_INEXCLUDE2     = 8

# Description-based parameter IDs
HF_GRP_PARAMS  = 2000
HF_OBJECT_TYPE = 2001
HF_TRAVERSE_MODE = 2002
HF_DEPTH       = 2003
HF_PARENT_OBJ  = 2004
HF_INEXCLUDE   = 2005
HF_IE2_INEX_MODE = 2006
HF_IE2_OBJ_MODE  = 2007
HF_INEXCLUDE2  = 2008

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
    result = []
    child = obj.GetDown()
    while child:
        result.append((child, depth))
        if max_depth < 0 or depth < max_depth - 1:
            result.extend(_collect_recursive(child, depth + 1, max_depth))
        child = child.GetNext()
    return result


def _collect_parents_recursive(obj, depth=0, max_depth=-1):
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


def _get_type_items(op):
    children = _collect_direct_children(op)
    seen = {}
    for obj in children:
        tid = obj.GetType()
        if tid not in seen:
            seen[tid] = _get_type_name(obj)
        for sub, _ in _collect_recursive(obj):
            stid = sub.GetType()
            if stid not in seen:
                seen[stid] = _get_type_name(sub)
    return ["Все типы"] + sorted(seen.values())


def _get_parent_items(op):
    all_parents = _collect_parents_recursive(op)
    labels = [op.GetName()]
    for obj, depth in all_parents:
        prefix = "-" * (depth + 1)
        labels.append(prefix + " " + obj.GetName())
    return labels


def _apply_filter(op):
    traverse_mode = op[HF_TRAVERSE_MODE] if op[HF_TRAVERSE_MODE] is not None else MODE_ALL
    depth_val     = op[HF_DEPTH] if op[HF_DEPTH] is not None else 3
    type_idx      = op[HF_OBJECT_TYPE] if op[HF_OBJECT_TYPE] is not None else 0
    parent_idx    = op[HF_PARENT_OBJ] if op[HF_PARENT_OBJ] is not None else 0
    ie2_inex_mode = op[HF_IE2_INEX_MODE] if op[HF_IE2_INEX_MODE] is not None else IE2_EXCLUDE
    ie2_obj_mode  = op[HF_IE2_OBJ_MODE] if op[HF_IE2_OBJ_MODE] is not None else IE2_OBJECT
    ie2_data      = op[HF_INEXCLUDE2]

    children = _collect_direct_children(op)

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

    all_parents = _collect_parents_recursive(op)
    if parent_idx > 0 and (parent_idx - 1) < len(all_parents):
        start_obj = all_parents[parent_idx - 1][0]
    else:
        start_obj = op

    candidates = []
    if traverse_mode == MODE_ALL:
        for obj, _ in _collect_recursive(op):
            candidates.append(obj)
    elif traverse_mode == MODE_RECURSIVE:
        for obj, _ in _collect_recursive(start_obj, max_depth=depth_val):
            candidates.append(obj)

    if filter_type_id is not None:
        candidates = [o for o in candidates if o.GetType() == filter_type_id]

    if ie2_data is not None:
        count = ie2_data.GetObjectCount()
        ie2_objects = []
        ie2_types   = set()
        for i in range(count):
            obj = ie2_data.ObjectFromIndex(op.GetDocument(), i)
            if obj:
                ie2_objects.append(obj)
                ie2_types.add(obj.GetType())

        if ie2_inex_mode == IE2_INCLUDE:
            if ie2_obj_mode == IE2_OBJECT:
                candidates = [o for o in candidates if any(o.IsInstanceOf(e.GetType()) and o == e for e in ie2_objects)]
            else:
                candidates = [o for o in candidates if o.GetType() in ie2_types]
        else:
            if ie2_obj_mode == IE2_OBJECT:
                candidates = [o for o in candidates if not any(o == e for e in ie2_objects)]
            else:
                candidates = [o for o in candidates if o.GetType() not in ie2_types]

    ie_data = c4d.InExcludeData()
    for obj in candidates:
        ie_data.InsertObject(obj, 1)
    op[HF_INEXCLUDE] = ie_data


# ─── ObjectData Plugin ───────────────────────────────────────────────────────

class HierarchyFilterObject(c4d.plugins.ObjectData):

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(OBJECT_NAME)
            op[HF_OBJECT_TYPE]  = 0
            op[HF_TRAVERSE_MODE] = MODE_ALL
            op[HF_DEPTH]        = 3
            op[HF_PARENT_OBJ]   = 0
            op[HF_IE2_INEX_MODE] = IE2_EXCLUDE
            op[HF_IE2_OBJ_MODE]  = IE2_OBJECT
        return True

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Параметры"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_GRP_PARAMS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD)
        gid = c4d.DescID(c4d.DescLevel(HF_GRP_PARAMS, c4d.DTYPE_GROUP, 0))

        type_items = _get_type_items(op)
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Тип объекта"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = 0
        cyc = c4d.BaseContainer()
        for i, label in enumerate(type_items):
            cyc[i] = label
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_OBJECT_TYPE, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Режим обхода"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = MODE_ALL
        cyc = c4d.BaseContainer()
        cyc[0] = "Все объекты"
        cyc[1] = "Рекурсивно"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_TRAVERSE_MODE, c4d.DTYPE_LONG, 0)),
            bc, gid)

        traverse_mode = op[HF_TRAVERSE_MODE] if op[HF_TRAVERSE_MODE] is not None else MODE_ALL
        is_all_mode = (traverse_mode == MODE_ALL)

        parent_items = _get_parent_items(op)
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Рекурсивно начиная с"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = 0
        bc[c4d.DESC_EDITABLE]  = not is_all_mode
        cyc = c4d.BaseContainer()
        for i, label in enumerate(parent_items):
            cyc[i] = label
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_PARENT_OBJ, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Рекурсивная глубина"
        bc[c4d.DESC_DEFAULT] = 3
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 99
        bc[c4d.DESC_EDITABLE] = not is_all_mode
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_DEPTH, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]    = " "
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_OFF
        bc[c4d.DESC_EDITABLE] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_INEXCLUDE, c4d.CUSTOMDATATYPE_INEXCLUDE_LIST, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Метод"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = IE2_EXCLUDE
        cyc = c4d.BaseContainer()
        cyc[0] = "Учета"
        cyc[1] = "Исключения"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_IE2_INEX_MODE, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Режим фильтра"
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        bc[c4d.DESC_DEFAULT]   = IE2_OBJECT
        cyc = c4d.BaseContainer()
        cyc[0] = "Объект"
        cyc[1] = "Тип"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_IE2_OBJ_MODE, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
        bc[c4d.DESC_NAME]    = " "
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_OFF
        bc[c4d.DESC_EDITABLE] = True
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(HF_INEXCLUDE2, c4d.CUSTOMDATATYPE_INEXCLUDE_LIST, 0)),
            bc, gid)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Message(self, op, type_, data):
        if type_ == c4d.MSG_MENUPREPARE:
            if op.GetName() == PLUGIN_NAME:
                op.SetName(OBJECT_NAME)

        if type_ == c4d.MSG_DESCRIPTION_POSTSETPARAMETER:
            _apply_filter(op)
            return True

        elif type_ in (c4d.MSG_UPDATE, c4d.MSG_DOCUMENTINFO):
            _apply_filter(op)

        return True

    def GetVirtualObjects(self, op, hh):
        _apply_filter(op)
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
        description = "Obase",
        icon        = _make_icon(),
        info        = c4d.OBJECT_GENERATOR | c4d.OBJECT_INPUT,
    )