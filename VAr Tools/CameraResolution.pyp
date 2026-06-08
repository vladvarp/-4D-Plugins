# coding: utf-8
"""
Camera Resolution Manager — Cinema 4D R26+
Plugin ID : 1068834
Файл: plugins/VAr Tools/CameraResolution.pyp
"""

import c4d
import os
import base64

# ─── ID ───────────────────────────────────────────────────────────────────────
PLUGIN_ID   = 1068834
PLUGIN_NAME = "Resolution Manager v1.4"
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
ROW_STRIDE      = 10
ID_CAM_ROWS_START = ID_BASE + 100

# ─── Пресеты ──────────────────────────────────────────────────────────────────
PRESETS = [
    ("Custom",                           0,    0),
    ("HD 720p - 1280 x 720",          1280,  720),
    ("FHD 1080p - 1920 x 1080",       1920, 1080),
    ("2K - 2048 x 1080",              2048, 1080),
    ("4K UHD - 3840 x 2160",          3840, 2160),
    ("4K DCI - 4096 x 2160",          4096, 2160),
    ("Instagram 1:1 - 1080 x 1080",   1080, 1080),
    ("Instagram 4:5 - 1080 x 1350",   1080, 1350),
    ("Instagram Story - 1080 x 1920", 1080, 1920),
    ("Twitter/X - 1200 x 675",        1200,  675),
    ("Facebook - 1200 x 630",         1200,  630),
    ("A4 Portrait - 2480 x 3508",     2480, 3508),
    ("A4 Landscape - 3508 x 2480",    3508, 2480),
    ("Square 1:1 - 1000 x 1000",      1000, 1000),
    ("Cinemascope - 2390 x 1000",     2390, 1000),
]

# ─── Иконка ───────────────────────────────────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAxElEQVR4nGM0MjL6"
    "zzCAgGkgLR91wKgDBoUDWGhl8JYtWwiq8fHxoZ0DYBbgAjAHYjhAJE8Eq4Y3k95Q"
    "yVmoYMDTwKgDUNIArvgnJEc1BxACN+puoPA1mjTwqicmKzIiV8e4fIluMTrA5RBi"
    "cg7BNACzfNq+aQTVkAOISoQwy/E5giYOgPksyykLhcanlqoOQAb4LKcEDHg5MLgd"
    "QCifk6uWaAfQAxB0ADE+I9f3DAxEFsUwC0gtiokBjKM9o1EHjHgHAACzpjMj5tOp"
    "3AAAAABJRU5ErkJggg=="
)


def _make_icon():
    SIZE = 32
    try:
        import tempfile
        raw = base64.b64decode(_ICON_B64)
        tmp = tempfile.mktemp(suffix=".png")
        with open(tmp, "wb") as f:
            f.write(raw)
        try:
            bmp = c4d.bitmaps.BaseBitmap()
        except AttributeError:
            bmp = c4d.BaseBitmap()
        result = bmp.InitWith(tmp)
        try:
            os.remove(tmp)
        except Exception:
            pass
        ok = result[0] if isinstance(result, tuple) else result
        if ok == c4d.IMAGERESULT_OK:
            return bmp
    except Exception:
        pass
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()
    bmp.Init(SIZE, SIZE, 32)
    cx, cy, r = SIZE//2, SIZE//2, SIZE//2-1
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x-cx, y-cy
            if dx*dx+dy*dy <= r*r:
                bmp.SetPixel(x, y, 60, 130, 220)
            else:
                bmp.SetPixel(x, y, 40, 40, 40)
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            bmp.SetPixel(cx+dx, cy-7+dy, 255, 255, 255)
    for dy in range(0, 9):
        for dx in range(-1, 1):
            bmp.SetPixel(cx+dx, cy-2+dy, 255, 255, 255)
    return bmp


# ─── Работа с данными камеры через UserData ───────────────────────────────────
#
# Данные хранятся в пользовательских данных объекта (User Data).
# Ищем поля по имени — это надёжнее чем по ID, который меняется
# при добавлении/удалении других полей.
#
UD_NAME_W     = "CamRes_W"
UD_NAME_H     = "CamRes_H"
UD_NAME_RATIO = "CamRes_Ratio"


def _ud_find(obj, name):
    """Возвращает DescID пользовательского поля по имени, или None."""
    ud = obj.GetUserDataContainer()
    if not ud:
        return None
    for descid, bc in ud:
        if bc.GetString(c4d.DESC_NAME) == name:
            return descid
    return None


def _ud_ensure(obj, name, dtype, default_val):
    """
    Гарантирует существование пользовательского поля с заданным именем.
    Если поля нет — создаёт его. Возвращает DescID.
    dtype: c4d.DTYPE_LONG или c4d.DTYPE_BOOL
    """
    did = _ud_find(obj, name)
    if did is not None:
        return did

    bc = c4d.GetCustomDataTypeDefault(dtype)
    bc.SetString(c4d.DESC_NAME, name)
    bc.SetString(c4d.DESC_SHORT_NAME, name)
    bc.SetBool(c4d.DESC_HIDE, False)

    if dtype == c4d.DTYPE_LONG:
        bc.SetInt32(c4d.DESC_MIN, 1)
        bc.SetInt32(c4d.DESC_MAX, 99999)
        bc.SetInt32(c4d.DESC_STEP, 1)
        bc.SetInt32(c4d.DESC_DEFAULT, int(default_val))

    did = obj.AddUserData(bc)
    obj[did] = default_val
    return did


def _cam_read(obj):
    """Читает w, h, ratio из пользовательских данных объекта камеры."""
    _rw, _rh = _get_render_resolution()
    w     = _rw if _rw >= 1 else 1920
    h     = _rh if _rh >= 1 else 1080
    ratio = False
    try:
        did = _ud_find(obj, UD_NAME_W)
        if did is not None:
            val = obj[did]
            if isinstance(val, (int, float)) and val >= 1:
                w = int(val)
    except Exception:
        pass
    try:
        did = _ud_find(obj, UD_NAME_H)
        if did is not None:
            val = obj[did]
            if isinstance(val, (int, float)) and val >= 1:
                h = int(val)
    except Exception:
        pass
    try:
        did = _ud_find(obj, UD_NAME_RATIO)
        if did is not None:
            ratio = bool(obj[did])
    except Exception:
        pass
    return w, h, ratio


def _cam_write(obj, w, h, ratio):
    """Записывает w, h, ratio в пользовательские данные объекта камеры."""
    try:
        did_w     = _ud_ensure(obj, UD_NAME_W,     c4d.DTYPE_LONG, 1920)
        did_h     = _ud_ensure(obj, UD_NAME_H,     c4d.DTYPE_LONG, 1080)
        did_ratio = _ud_ensure(obj, UD_NAME_RATIO,  c4d.DTYPE_BOOL, False)
        obj[did_w]     = int(w)
        obj[did_h]     = int(h)
        obj[did_ratio] = bool(ratio)
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
        if pw == w and ph == h:
            return i
    return 0


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


# ─── Диалог ───────────────────────────────────────────────────────────────────

class CamResDialog(c4d.gui.GeDialog):

    def __init__(self, command):
        super(CamResDialog, self).__init__()
        self._command           = command
        self._cam_list          = []   # [(name, obj), ...]
        self._last_active_cam     = None
        self._last_active_cam_obj = None
        self._plugin_active_obj = None  # объект камеры, активированной через плагин
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

        self.GroupBegin(base+9, c4d.BFH_SCALEFIT, cols=7, rows=1)
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
                pluginid=PLUGIN_ID,
                defaultw=680,
                defaulth=280,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dialog is None:
            self._dialog = CamResDialog(self)
        return self._dialog.Restore(PLUGIN_ID, secret)

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


# ─── Регистрация ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = "Resolution Manager",
        info = 0,
        icon = _make_icon(),
        help = PLUGIN_HELP,
        dat  = CamResCommand(),
    )
