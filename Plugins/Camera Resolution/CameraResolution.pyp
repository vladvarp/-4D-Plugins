# coding: utf-8
"""
Camera Resolution Manager — Cinema 4D R26+
Plugin ID : 1068834
Файл: plugins/VAr Tools/CameraResolution.pyp
"""

import c4d # type: ignore
import os
import base64
import tempfile

# ─── ID ───────────────────────────────────────────────────────────────────────
PLUGIN_ID_CMD   = 1068834
PLUGIN_ID_TAG   = 1068836

PLUGIN_NAME = "Resolution Manager"
PLUGIN_NAME_V = "Resolution Manager v1.7.1"
PLUGIN_HELP = "Управление разрешением рендера для каждой камеры"

ID_BASE           = 10000
ID_LBL_STATUS     = ID_BASE + 4
ID_LBL_RESOLUTION = ID_BASE + 7
ID_SCROLL         = ID_BASE + 5
ID_CAM_LIST_GROUP = ID_BASE + 6

OFFSET_LBL      = 0
OFFSET_PRESET   = 1
OFFSET_W        = 2
OFFSET_RATIO    = 3
OFFSET_SWAP     = 4
OFFSET_H        = 5
OFFSET_ACTIVATE = 6
OFFSET_LOCK     = 7
ROW_STRIDE      = 10
ID_CAM_ROWS_START = ID_BASE + 100

# ─── Пресеты ──────────────────────────────────────────────────────────────────
_RAW_PRESETS = [
    ("Custom",                              0,    0),
    ("HD 720p - 1280 x 720",             1280,  720),
    ("FHD 1080p - 1920 x 1080",          1920, 1080),
    ("2K DCI - 2048 x 1080",             2048, 1080),
    ("4K UHD - 3840 x 2160",             3840, 2160),
    ("4K DCI - 4096 x 2160",             4096, 2160),
    ("1:1 Square - 1080 x 1080",         1080, 1080),
    ("Instagram 4:5 - 1080 x 1350",      1080, 1350),
    ("9:16 Vertical - 1080 x 1920",      1080, 1920),
    ("16:9 Link Preview - 1200 x 675",   1200,  675),
    ("1.91:1 Link Preview - 1200 x 630", 1200,  630),
    ("A4 Portrait - 2480 x 3508",        2480, 3508),
    ("A4 Landscape - 3508 x 2480",       3508, 2480),
    ("Cinemascope - 2390 x 1000",        2390, 1000),
]

PRESETS = []
_seen_res = set()
for _pname, _pw, _ph in _RAW_PRESETS:
    _key = (_pw, _ph)
    if _key in _seen_res:
        continue
    _seen_res.add(_key)
    PRESETS.append((_pname, _pw, _ph))


# ─── Работа с данными камеры через TagData ───────────────────────────────────

UD_NAME_W     = "CamRes_W"
UD_NAME_H     = "CamRes_H"
UD_NAME_RATIO = "CamRes_Ratio"

# Description-based parameter IDs
CR_GRP_PARAMS = 2000
CR_W          = 2001
CR_H          = 2002
CR_RATIO      = 2003


def _find_tag(obj):
    """Находит Camera Resolution Tag на объекте."""
    tag = obj.GetFirstTag()
    while tag:
        if tag.GetType() == PLUGIN_ID_TAG:
            return tag
        tag = tag.GetNext()
    return None


def _ensure_tag(obj):
    """Гарантирует наличие тега на камере. Возвращает тег."""
    tag = _find_tag(obj)
    if tag is not None:
        return tag
    tag = obj.MakeTag(PLUGIN_ID_TAG)
    if tag is not None:
        tag.SetName("Camera Resolution")
    return tag


def _remove_old_ud(obj):
    """Удаляет старые UserData поля CamRes_* с объекта."""
    to_remove = []
    for descid, bc in obj.GetUserDataContainer():
        name = bc.GetString(c4d.DESC_NAME)
        if name in (UD_NAME_W, UD_NAME_H, UD_NAME_RATIO, "Camera Resolution Data"):
            to_remove.append(descid)
    for descid in reversed(to_remove):
        obj.RemoveUserData(descid)


def _cam_read(obj):
    """Читает w, h, ratio. Сначала ищет тег, потом старые UserData."""
    _rw, _rh = _get_render_resolution()
    w     = _rw if _rw >= 1 else 1920
    h     = _rh if _rh >= 1 else 1080
    ratio = False

    tag = _find_tag(obj)
    if tag is not None:
        try:
            val = tag[CR_W]
            if isinstance(val, (int, float)) and val >= 1:
                w = int(val)
        except Exception:
            pass
        try:
            val = tag[CR_H]
            if isinstance(val, (int, float)) and val >= 1:
                h = int(val)
        except Exception:
            pass
        try:
            ratio = bool(tag[CR_RATIO])
        except Exception:
            pass
        return w, h, ratio

    # Fallback: старые UserData
    ud = obj.GetUserDataContainer()
    if ud:
        for descid, bc in ud:
            name = bc.GetString(c4d.DESC_NAME)
            try:
                if name == UD_NAME_W:
                    val = obj[descid]
                    if isinstance(val, (int, float)) and val >= 1:
                        w = int(val)
                elif name == UD_NAME_H:
                    val = obj[descid]
                    if isinstance(val, (int, float)) and val >= 1:
                        h = int(val)
                elif name == UD_NAME_RATIO:
                    ratio = bool(obj[descid])
            except Exception:
                pass

    return w, h, ratio


def _cam_write(obj, w, h, ratio):
    """Записывает w, h, ratio в тег на камере. Удаляет старые UserData."""
    try:
        tag = _ensure_tag(obj)
        if tag is not None:
            tag[CR_W]     = int(w)
            tag[CR_H]     = int(h)
            tag[CR_RATIO] = bool(ratio)
            tag.Message(c4d.MSG_UPDATE)

        _remove_old_ud(obj)

        obj.Message(c4d.MSG_UPDATE)
        doc = c4d.documents.GetActiveDocument()
        if doc:
            doc.SetChanged()
    except Exception:
        pass


# ─── Вспомогательные ──────────────────────────────────────────────────────────

def _doc_key(doc):
    if doc is None:
        return ""
    path = doc.GetDocumentPath()
    name = doc.GetDocumentName()
    return os.path.join(path, name) if path else name


def _collect_cameras():
    """Возвращает список [(name, obj), ...]"""
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return []
    result = []

    def _walk(obj):
        while obj:
            if obj.GetType() == c4d.Ocamera:
                result.append((obj.GetName(), obj))
            child = obj.GetDown()
            if child:
                _walk(child)
            obj = obj.GetNext()

    _walk(doc.GetFirstObject())
    return result


def _get_render_resolution():
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return (0, 0)
    rd = doc.GetActiveRenderData()
    if rd is None:
        return (0, 0)
    return (int(rd[c4d.RDATA_XRES]), int(rd[c4d.RDATA_YRES]))


def _apply_to_render(w, h):
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return
    rd = doc.GetActiveRenderData()
    if rd is None:
        return
    rd[c4d.RDATA_XRES] = float(w)
    rd[c4d.RDATA_YRES] = float(h)
    c4d.EventAdd()


def _find_preset_index(w, h):
    for i, (_, pw, ph) in enumerate(PRESETS):
        if i == 0:
            continue
        if pw == w and ph == h:
            return i
    return 0


def _obj_key(obj):
    """Хешируемый ключ для отслеживания состояния C4D-объекта."""
    return id(obj)


def _has_lock_tag(obj):
    """True если на объекте есть тег блокировки (Protection)."""
    tag = obj.GetFirstTag()
    while tag:
        if tag.GetType() == c4d.Tprotection:
            return True
        tag = tag.GetNext()
    return False


def _set_lock_tag(obj, locked):
    """Добавляет или снимает тег блокировки с объекта камеры."""
    doc = obj.GetDocument()
    if locked:
        if not _has_lock_tag(obj):
            obj.MakeTag(c4d.Tprotection)
    else:
        tag = obj.GetFirstTag()
        while tag:
            nxt = tag.GetNext()
            if tag.GetType() == c4d.Tprotection:
                tag.Remove()
            tag = nxt
    if doc:
        doc.SetChanged()


def _diff_cameras(old_list, new_list):
    """Возвращает True если состав/порядок камер изменился."""
    if len(old_list) != len(new_list):
        return True
    for (old_name, old_obj), (new_name, new_obj) in zip(old_list, new_list):
        # Сравниваем по указателю объекта — переименование не считается изменением состава
        if old_obj != new_obj:
            return True
    return False


def _names_changed(old_list, new_list):
    """Возвращает True если у какой-либо камеры изменилось имя (переименование)."""
    if len(old_list) != len(new_list):
        return False
    for (old_name, old_obj), (new_name, new_obj) in zip(old_list, new_list):
        if old_obj == new_obj and old_name != new_name:
            return True
    return False


# ─── TagData ──────────────────────────────────────────────────────────────────

class CameraResolutionTag(c4d.plugins.TagData):

    def Init(self, node, isload=False):
        if not isload:
            node[CR_W]     = 1920
            node[CR_H]     = 1080
            node[CR_RATIO] = False
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription(c4d.Tbase):
            return False, flags

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Camera Resolution Data"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CR_GRP_PARAMS, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD)
        gid = c4d.DescID(c4d.DescLevel(CR_GRP_PARAMS, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Ширина"
        bc[c4d.DESC_DEFAULT] = 1920
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 99999
        bc[c4d.DESC_STEP]    = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CR_W, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]    = "Высота"
        bc[c4d.DESC_DEFAULT] = 1080
        bc[c4d.DESC_MIN]     = 1
        bc[c4d.DESC_MAX]     = 99999
        bc[c4d.DESC_STEP]    = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CR_H, c4d.DTYPE_LONG, 0)),
            bc, gid)

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Сохранять пропорции"
        bc[c4d.DESC_DEFAULT] = False
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(CR_RATIO, c4d.DTYPE_BOOL, 0)),
            bc, gid)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Message(self, node, msg_type, data):
        if msg_type == c4d.MSG_DESCRIPTION_POSTSETPARAMETER:
            doc = c4d.documents.GetActiveDocument()
            if doc:
                doc.SetChanged()
            c4d.EventAdd()
        return True


# ─── Диалог ───────────────────────────────────────────────────────────────────

class CamResDialog(c4d.gui.GeDialog):

    def __init__(self, command):
        super(CamResDialog, self).__init__()
        self._command           = command
        self._cam_list          = []   # [(name, obj), ...]
        self._last_active_cam     = None
        self._last_active_cam_obj = None
        self._plugin_active_obj = None  # объект камеры, активированной через плагин
        self._last_lock_states  = {}    # id(obj) -> bool
        self._initialized       = False

    # ── CreateLayout ─────────────────────────────────────────────────────────

    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME)
        self.AddSeparatorH(0)
        self.ScrollGroupBegin(
            ID_SCROLL,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            c4d.SCROLLGROUP_VERT | c4d.SCROLLGROUP_AUTOVERT,
            initw=0, inith=60,
        )
        self.GroupBegin(ID_CAM_LIST_GROUP,
                        c4d.BFH_SCALEFIT | c4d.BFV_TOP,
                        cols=1, rows=0)
        self.GroupBorderSpace(0, 0, 0, 0)
        self.GroupEnd()
        self.GroupEnd()
        self.AddSeparatorH(0)
        self.GroupBegin(ID_BASE+12, c4d.BFH_SCALEFIT, cols=1, rows=2)
        self.GroupBorderSpace(4, 2, 4, 2)
        self.AddStaticText(ID_LBL_STATUS,     c4d.BFH_SCALEFIT, name="Загрузка...")
        self.AddStaticText(ID_LBL_RESOLUTION, c4d.BFH_SCALEFIT, name="")
        self.GroupEnd()
        return True

    # ── InitValues ───────────────────────────────────────────────────────────

    def InitValues(self):
        doc = c4d.documents.GetActiveDocument()
        self._last_doc          = _doc_key(doc)
        self._cam_list          = _collect_cameras()
        self._last_active_cam     = self._get_active_camera_name()
        self._last_active_cam_obj = self._get_active_camera_obj()
        self._last_render_res   = _get_render_resolution()
        self._initialized       = True
        self._last_lock_states  = {}
        self._rebuild_list()
        return True

    # ── Перестройка списка ────────────────────────────────────────────────────

    def _rebuild_list(self):
        self.LayoutFlushGroup(ID_CAM_LIST_GROUP)

        active_obj  = self._get_active_camera_obj()
        active_name = active_obj.GetName() if active_obj else None
        render_w, render_h = _get_render_resolution()
        self._last_render_res = (render_w, render_h)

        if not self._cam_list:
            self.AddStaticText(ID_BASE+31, c4d.BFH_CENTER,
                               name="-- Камеры в сцене не найдены --")
        else:
            for idx, (name, obj) in enumerate(self._cam_list):
                self._add_camera_row(idx, name, obj,
                                     obj == active_obj,
                                     render_w, render_h)

        self.LayoutChanged(ID_CAM_LIST_GROUP)

        count = len(self._cam_list)
        if active_name:
            self.SetString(ID_LBL_STATUS,
                           "Активная камера: {}  |  Камер в сцене: {}".format(active_name, count))
        else:
            self.SetString(ID_LBL_STATUS,
                           "Активная камера не задана  |  Камер в сцене: {}".format(count))

        self._update_resolution_label(render_w, render_h)
        self._update_lock_states()

    def _update_lock_states(self):
        for _, obj in self._cam_list:
            self._last_lock_states[_obj_key(obj)] = _has_lock_tag(obj)

    def _lock_states_changed(self):
        for _, obj in self._cam_list:
            if self._last_lock_states.get(_obj_key(obj)) != _has_lock_tag(obj):
                return True
        return False

    def _get_active_camera_name(self):
        try:
            doc = c4d.documents.GetActiveDocument()
            if doc is None:
                return None
            bd = doc.GetActiveBaseDraw()
            if bd is None:
                return None
            active = bd.GetSceneCamera(doc)
            if active is None:
                return None
            return active.GetName()
        except Exception:
            return None

    def _get_active_camera_obj(self):
        try:
            doc = c4d.documents.GetActiveDocument()
            if doc is None:
                return None
            bd = doc.GetActiveBaseDraw()
            if bd is None:
                return None
            return bd.GetSceneCamera(doc)
        except Exception:
            return None

    def _update_resolution_label(self, render_w=None, render_h=None):
        try:
            if render_w is None or render_h is None:
                render_w, render_h = _get_render_resolution()
            if render_w == 0 and render_h == 0:
                self.SetString(ID_LBL_RESOLUTION, "")
                return
            self.SetString(ID_LBL_RESOLUTION,
                           "Разрешение рендера: {}x{}".format(render_w, render_h))
        except Exception:
            self.SetString(ID_LBL_RESOLUTION, "")

    # ── Строка одной камеры ───────────────────────────────────────────────────

    def _add_camera_row(self, idx, name, obj, is_active=False,
                        render_w=0, render_h=0):
        base = ID_CAM_ROWS_START + idx * ROW_STRIDE

        saved_w, saved_h, saved_ratio = _cam_read(obj)
        preset_idx = _find_preset_index(saved_w, saved_h)

        # "✓ Активна" — только если эта камера активирована через плагин
        # И её w/h совпадают с текущим разрешением рендера
        cam_matches = (
            obj is self._plugin_active_obj
            and render_w == saved_w
            and render_h == saved_h
            and render_w > 0
        )

        self.GroupBegin(base+9, c4d.BFH_SCALEFIT, cols=8, rows=1)
        self.GroupBorderSpace(6, 1, 6, 1)

        btn_label = "✓ Активна" if cam_matches else "Активировать"
        self.AddButton(base+OFFSET_ACTIVATE, c4d.BFH_RIGHT,
                       initw=100, name=btn_label)

        label = ("▶ " if is_active else "    ") + name
        self.AddStaticText(base+OFFSET_LBL,
                           c4d.BFH_SCALEFIT | c4d.BFV_CENTER,
                           initw=110, name=label)

        self.AddEditNumberArrows(base+OFFSET_W, c4d.BFH_LEFT, initw=60)
        self.SetInt32(base+OFFSET_W, saved_w, min=1, max=99999)

        self.AddCheckbox(base+OFFSET_RATIO, c4d.BFH_CENTER, initw=0, inith=0, name="∝")
        self.SetBool(base+OFFSET_RATIO, saved_ratio)

        self.AddButton(base+OFFSET_SWAP, c4d.BFH_CENTER, initw=24, name="⇄")

        self.AddEditNumberArrows(base+OFFSET_H, c4d.BFH_LEFT, initw=60)
        self.SetInt32(base+OFFSET_H, saved_h, min=1, max=99999)

        self.AddComboBox(base+OFFSET_PRESET, c4d.BFH_LEFT, initw=250)
        for pi, (pname, _, _) in enumerate(PRESETS):
            self.AddChild(base+OFFSET_PRESET, pi, pname)
        self.SetInt32(base+OFFSET_PRESET, preset_idx)

        self.AddCheckbox(base+OFFSET_LOCK, c4d.BFH_CENTER, initw=0, inith=0, name=f"⊘")
        self.SetBool(base+OFFSET_LOCK, _has_lock_tag(obj))

        self.GroupEnd()

    # ── Команды ──────────────────────────────────────────────────────────────

    def Command(self, widget_id, msg):

        for idx, (name, obj) in enumerate(self._cam_list):
            base = ID_CAM_ROWS_START + idx * ROW_STRIDE

            # ── Пресет ──
            if widget_id == base + OFFSET_PRESET:
                pi = self.GetInt32(base+OFFSET_PRESET)
                if pi > 0:
                    _, pw, ph = PRESETS[pi]
                    self.SetInt32(base+OFFSET_W, pw)
                    self.SetInt32(base+OFFSET_H, ph)
                    ratio = self.GetBool(base+OFFSET_RATIO)
                    _cam_write(obj, pw, ph, ratio)
                    if obj is self._plugin_active_obj:
                        _apply_to_render(pw, ph)
                        self._rebuild_list()
                return True

            # ── Галочка пропорций ──
            if widget_id == base + OFFSET_RATIO:
                w = self.GetInt32(base+OFFSET_W)
                h = self.GetInt32(base+OFFSET_H)
                ratio = self.GetBool(base+OFFSET_RATIO)
                _cam_write(obj, w, h, ratio)
                return True

            # ── Ширина ──
            if widget_id == base + OFFSET_W:
                w = self.GetInt32(base+OFFSET_W)
                h = self.GetInt32(base+OFFSET_H)
                ratio = self.GetBool(base+OFFSET_RATIO)
                if ratio and w > 0:
                    old_w, old_h, _ = _cam_read(obj)
                    if old_w > 0:
                        h = max(1, int(round(w * old_h / float(old_w))))
                        self.SetInt32(base+OFFSET_H, h)
                _cam_write(obj, w, h, ratio)
                self.SetInt32(base+OFFSET_PRESET, _find_preset_index(w, h))
                if obj is self._plugin_active_obj:
                    _apply_to_render(w, h)
                    self._rebuild_list()
                return True

            # ── Высота ──
            if widget_id == base + OFFSET_H:
                w = self.GetInt32(base+OFFSET_W)
                h = self.GetInt32(base+OFFSET_H)
                ratio = self.GetBool(base+OFFSET_RATIO)
                if ratio and h > 0:
                    old_w, old_h, _ = _cam_read(obj)
                    if old_h > 0:
                        w = max(1, int(round(h * old_w / float(old_h))))
                        self.SetInt32(base+OFFSET_W, w)
                _cam_write(obj, w, h, ratio)
                self.SetInt32(base+OFFSET_PRESET, _find_preset_index(w, h))
                if obj is self._plugin_active_obj:
                    _apply_to_render(w, h)
                    self._rebuild_list()
                return True

            # ── Инверт ──
            if widget_id == base + OFFSET_SWAP:
                w = self.GetInt32(base+OFFSET_W)
                h = self.GetInt32(base+OFFSET_H)
                ratio = self.GetBool(base+OFFSET_RATIO)
                self.SetInt32(base+OFFSET_W, h)
                self.SetInt32(base+OFFSET_H, w)
                _cam_write(obj, h, w, ratio)
                self.SetInt32(base+OFFSET_PRESET, _find_preset_index(h, w))
                if obj is self._plugin_active_obj:
                    _apply_to_render(h, w)
                    self._rebuild_list()
                return True

            # ── Активировать / Деактивировать ──
            if widget_id == base + OFFSET_ACTIVATE:
                if obj is self._plugin_active_obj:
                    self._deactivate_camera()
                else:
                    self._activate_camera(idx, name, obj)
                return True

            # ── Блокировка камеры ──
            if widget_id == base + OFFSET_LOCK:
                locked = self.GetBool(base+OFFSET_LOCK)
                _set_lock_tag(obj, locked)
                self._last_lock_states[_obj_key(obj)] = locked
                c4d.EventAdd()
                return True

        return True

    # ── Логика ───────────────────────────────────────────────────────────────

    def _deactivate_camera(self):
        try:
            doc = c4d.documents.GetActiveDocument()
            if doc:
                bd = doc.GetActiveBaseDraw()
                if bd:
                    bd.SetSceneCamera(None)
                    c4d.EventAdd()
        except Exception:
            pass
        self._plugin_active_obj = None
        self._rebuild_list()

    def _activate_camera(self, idx, name, obj):
        doc = c4d.documents.GetActiveDocument()
        if doc is None:
            return
        bd = doc.GetActiveBaseDraw()
        if bd is not None:
            bd.SetSceneCamera(obj)
        w = self.GetInt32(ID_CAM_ROWS_START + idx*ROW_STRIDE + OFFSET_W)
        h = self.GetInt32(ID_CAM_ROWS_START + idx*ROW_STRIDE + OFFSET_H)
        ratio = self.GetBool(ID_CAM_ROWS_START + idx*ROW_STRIDE + OFFSET_RATIO)
        _apply_to_render(w, h)
        _cam_write(obj, w, h, ratio)
        self._plugin_active_obj   = obj
        self._last_active_cam     = name
        self._last_active_cam_obj = obj
        self._last_render_res     = (w, h)
        self._rebuild_list()
        c4d.EventAdd()

    def _do_full_refresh(self):
        doc = c4d.documents.GetActiveDocument()
        self._last_doc = _doc_key(doc)
        self._cam_list = _collect_cameras()
        self._rebuild_list()

    # ── CoreMessage ───────────────────────────────────────────────────────────

    def CoreMessage(self, kind, msg):
        if kind != c4d.EVMSG_CHANGE:
            return True
        if not self._initialized:
            return True

        try:
            doc = c4d.documents.GetActiveDocument()
            if doc is None:
                return True

            current_doc = _doc_key(doc)

            # ── Сменился проект ──
            if current_doc != self._last_doc:
                self._last_doc          = current_doc
                self._last_active_cam   = None
                self._plugin_active_obj = None
                self._last_lock_states  = {}
                self._cam_list          = _collect_cameras()
                self._rebuild_list()
                return True

            # ── Изменилось разрешение рендера извне ──
            current_render_res = _get_render_resolution()
            if current_render_res != self._last_render_res:
                self._last_render_res   = current_render_res
                self._plugin_active_obj = None  # сброс кнопки
                self._rebuild_list()
                return True

            # ── Изменился состав камер ──
            new_list = _collect_cameras()
            if _diff_cameras(self._cam_list, new_list):
                self._cam_list = new_list
                self._rebuild_list()
                return True

            # ── Переименование камеры ──
            if _names_changed(self._cam_list, new_list):
                self._cam_list = new_list
                self._rebuild_list()
                return True

            # ── Тег блокировки добавлен или снят вручную ──
            if self._lock_states_changed():
                self._update_lock_states()
                self._rebuild_list()
                return True

            # ── Сменилась активная камера в редакторе ──
            current_active_obj = self._get_active_camera_obj()
            if current_active_obj != self._last_active_cam_obj:
                self._last_active_cam_obj = current_active_obj
                current_active            = current_active_obj.GetName() if current_active_obj else None
                self._last_active_cam     = current_active
                self._plugin_active_obj   = None  # сброс кнопки
                self._command._last_active_cam = current_active
                self._rebuild_list()

        except Exception:
            pass

        return True


# ─── CommandData ──────────────────────────────────────────────────────────────

class CamResCommand(c4d.plugins.CommandData):

    def __init__(self):
        super(CamResCommand, self).__init__()
        self._dialog          = None
        self._enabled         = False
        self._last_active_cam = None

    def Execute(self, doc):
        if self._dialog is None:
            self._dialog = CamResDialog(self)
        if self._dialog.IsOpen():
            self._dialog.Close()
        else:
            self._dialog.Open(
                dlgtype=c4d.DLG_TYPE_ASYNC,
                pluginid=PLUGIN_ID_CMD,
                defaultw=710,
                defaulth=280,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dialog is None:
            self._dialog = CamResDialog(self)
        return self._dialog.Restore(PLUGIN_ID_CMD, secret)

    def GetState(self, doc):
        return c4d.CMD_ENABLED

    def CoreMessage(self, kind, msg):
        """Работает всегда — даже когда диалог закрыт."""
        if kind != c4d.EVMSG_CHANGE:
            return True
        if not self._enabled:
            return True

        try:
            doc = c4d.documents.GetActiveDocument()
            if doc is None:
                return True
            bd = doc.GetActiveBaseDraw()
            if bd is None:
                return True
            active_obj = bd.GetSceneCamera(doc)
            current_active = active_obj.GetName() if active_obj else None

            if current_active != self._last_active_cam:
                self._last_active_cam = current_active
                if active_obj is not None:
                    w, h, _ = _cam_read(active_obj)
                    if w > 0 and h > 0:
                        _apply_to_render(w, h)
                        if self._dialog and self._dialog.IsOpen():
                            cam_count = len(self._dialog._cam_list)
                            self._dialog.SetString(ID_LBL_STATUS,
                                "Активная камера: {}  |  Камер в сцене: {}".format(
                                    current_active, cam_count))
                            self._dialog.SetString(ID_LBL_RESOLUTION,
                                "Разрешение рендера: {}x{}  ✓ применено".format(w, h))
        except Exception:
            pass

        return True

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


ICON_B64 = _make_icon()

# ─── Регистрация ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterTagPlugin(
        id          = PLUGIN_ID_TAG,
        str         = "Camera Resolution Tag",
        info        = c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g           = CameraResolutionTag,
        description = "Obase",
        icon        = ICON_B64,
    )

    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID_CMD,
        str  = PLUGIN_NAME_V,
        info = 0,
        icon = ICON_B64,
        help = PLUGIN_HELP,
        dat  = CamResCommand(),
    )
