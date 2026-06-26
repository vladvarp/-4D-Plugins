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
PLUGIN_NAME = "Hierarchy Filter v1.5.1"
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