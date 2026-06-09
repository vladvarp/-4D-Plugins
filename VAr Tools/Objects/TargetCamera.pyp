"""
TargetCamera.pyp  —  Cinema 4D R26
═══════════════════════════════════════════════════════════════════════════════
Создаёт систему «Target Camera» по аналогии с 3ds Max:

  Камера  ──сплайн──►  Null-таргет
     │
     └─ тег TagData: каждый кадр направляет камеру на таргет
                     обновляет сплайн-линию
                     показывает Near / Far прямоугольные рамки
                     (размер = реальный фрустум на заданном расстоянии)

User Data на камере:
  [1]  bool  «Показать Near Clip Rect»
  [2]  bool  «Показать Far Clip Rect»

Установка:
  Plugins/TargetCamera/TargetCamera.pyp
"""

import c4d
import math

# ── Уникальные ID (зарегистрированы через plugincafe) ─────────────────────────
PLUGIN_ID_CMD = 1068859   # CommandData — кнопка «Target Camera»
PLUGIN_ID_TAG = 1068860   # TagData   — «TargetCam Controller»

# User Data слоты на камере
UD_NEAR_ENABLE = 1
UD_FAR_ENABLE  = 2

# Константы тега для хранения ссылки на таргет и сплайн
TAG_LINK_TARGET = 1000
TAG_LINK_SPLINE = 1001

# Имена объектов
NAME_CAM    = "Target Camera"
NAME_TARGET = "Camera Target"
NAME_SPLINE = "Cam_Target_Line"
NAME_NEAR   = "Cam_NearClip_Rect"
NAME_FAR    = "Cam_FarClip_Rect"


# ══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные функции
# ══════════════════════════════════════════════════════════════════════════════

def get_fov_and_aspect(cam):
    """
    Возвращает (fov_h_rad, aspect).
    fov_h_rad  — горизонтальный угол обзора в радианах.
    aspect     — ширина/высота из активных рендер-настроек.
    """
    doc = cam.GetDocument()
    if not doc:
        return math.radians(45), 16.0 / 9.0

    rd     = doc.GetActiveRenderData()
    rend_w = float(rd[c4d.RDATA_XRES] or 1920)
    rend_h = float(rd[c4d.RDATA_YRES] or 1080)
    aspect = rend_w / rend_h

    film_w = float(cam[c4d.CAMERAOBJECT_FILM_X] or 36.0)
    focal  = float(cam[c4d.CAMERAOBJECT_FOCUS]  or 36.0)
    if focal <= 0:
        focal = 36.0

    fov_h = 2.0 * math.atan(film_w * 0.5 / focal)
    return fov_h, aspect


def update_rect_points(sp_obj, half_w, half_h):
    """Обновляет 4 точки прямоугольного сплайна."""
    sp_obj.SetPoint(0, c4d.Vector(-half_w, -half_h, 0))
    sp_obj.SetPoint(1, c4d.Vector( half_w, -half_h, 0))
    sp_obj.SetPoint(2, c4d.Vector( half_w,  half_h, 0))
    sp_obj.SetPoint(3, c4d.Vector(-half_w,  half_h, 0))
    sp_obj.Message(c4d.MSG_UPDATE)


def make_rect_spline(color):
    """Создаёт новый прямоугольный SplineObject (4 точки, замкнутый)."""
    sp = c4d.SplineObject(4, c4d.SPLINETYPE_LINEAR)
    sp[c4d.SPLINEOBJECT_CLOSED]        = True
    sp[c4d.ID_BASEOBJECT_USECOLOR]     = 2          # кастомный цвет
    sp[c4d.ID_BASEOBJECT_COLOR]        = color
    # Начальные точки — единичный квадрат
    update_rect_points(sp, 1.0, 1.0)
    return sp


def set_clip_rect(cam, rect_obj, dist):
    """
    Пересчитывает размер и Z-позицию прямоугольника клиппинга.
    rect_obj — дочерний объект камеры (локальные координаты).
    dist     — расстояние от камеры (единицы сцены, всегда > 0).
    """
    fov_h, aspect = get_fov_and_aspect(cam)
    half_w = dist * math.tan(fov_h * 0.5)
    half_h = half_w / aspect

    update_rect_points(rect_obj, half_w, half_h)

    # C4D: камера смотрит в -Z локально
    ml     = rect_obj.GetMl()
    ml.off = c4d.Vector(0.0, 0.0, -dist)
    rect_obj.SetMl(ml)


def find_direct_child(parent, name):
    """Ищет прямого потомка по имени."""
    ch = parent.GetDown()
    while ch:
        if ch.GetName() == name:
            return ch
        ch = ch.GetNext()
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  TagData — TargetCam Controller
# ══════════════════════════════════════════════════════════════════════════════

class TargetCamTag(c4d.plugins.TagData):
    """
    Тег, который живёт на камере и каждый кадр:
      1. Поворачивает камеру в сторону таргета (LookAt).
      2. Обновляет сплайн-линию.
      3. Управляет Near / Far clip-прямоугольниками.
    """

    def Init(self, node):
        # Инициализируем BaseLink-параметры
        node[TAG_LINK_TARGET] = None
        node[TAG_LINK_SPLINE] = None
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription("tbaselist2d"):
            return False

        # Слот таргета
        bc_target                   = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc_target[c4d.DESC_NAME]    = "Таргет"
        bc_target[c4d.DESC_SHORT_NAME] = "Таргет"
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TAG_LINK_TARGET, c4d.DTYPE_BASELISTLINK, 0)),
            bc_target,
            c4d.ID_ROOT
        )

        # Слот сплайна
        bc_spline                   = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc_spline[c4d.DESC_NAME]    = "Сплайн"
        bc_spline[c4d.DESC_SHORT_NAME] = "Сплайн"
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TAG_LINK_SPLINE, c4d.DTYPE_BASELISTLINK, 0)),
            bc_spline,
            c4d.ID_ROOT
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Execute(self, tag, doc, op, bt, priority, flags):
        cam = op
        if cam is None:
            return c4d.EXECUTIONRESULT_OK

        # ── Таргет ────────────────────────────────────────────────────────────
        target = tag[TAG_LINK_TARGET]
        if target is None or not target.IsAlive():
            return c4d.EXECUTIONRESULT_OK

        cam_pos    = cam.GetMg().off
        target_pos = target.GetMg().off
        diff       = target_pos - cam_pos

        if diff.GetLength() < 0.001:
            return c4d.EXECUTIONRESULT_OK

        # ── LookAt-матрица ────────────────────────────────────────────────────
        forward = diff.GetNormalized()            # направление камера → таргет
        world_up = c4d.Vector(0, 1, 0)

        right = forward.Cross(world_up)
        if right.GetLength() < 0.001:             # гимбал при взгляде прямо вверх
            world_up = c4d.Vector(0, 0, 1)
            right    = forward.Cross(world_up)
        right  = right.GetNormalized()
        up_vec = right.Cross(forward).GetNormalized()

        # C4D: v3 (ось Z объекта) = назад;  камера смотрит в -Z
        mg     = cam.GetMg()
        mg.v1  = right
        mg.v2  = up_vec
        mg.v3  = -forward
        cam.SetMg(mg)

        # ── Сплайн-линия ──────────────────────────────────────────────────────
        spline = tag[TAG_LINK_SPLINE]
        if spline and spline.IsAlive():
            spline.ResizeObject(2)
            spline.SetPoint(0, cam_pos)
            spline.SetPoint(1, target_pos)
            spline.Message(c4d.MSG_UPDATE)

        # ── Клиппинг-прямоугольники ───────────────────────────────────────────
        near_en   = cam[c4d.ID_USERDATA, UD_NEAR_ENABLE] or False
        far_en    = cam[c4d.ID_USERDATA, UD_FAR_ENABLE]  or False

        near_dist = float(cam[c4d.CAMERAOBJECT_NEAR_CLIPPING] or 100.0)
        far_dist  = float(cam[c4d.CAMERAOBJECT_FAR_CLIPPING]  or 10000.0)
        if near_dist <= 0: near_dist = 1.0
        if far_dist  <= 0: far_dist  = 10000.0

        # Near
        near_rect = find_direct_child(cam, NAME_NEAR)
        if near_en:
            if not near_rect:
                near_rect = make_rect_spline(c4d.Vector(0.2, 0.85, 1.0))
                near_rect.SetName(NAME_NEAR)
                doc.InsertObject(near_rect, cam, None)
                c4d.EventAdd()
            set_clip_rect(cam, near_rect, near_dist)
        else:
            if near_rect:
                near_rect.Remove()
                c4d.EventAdd()

        # Far
        far_rect = find_direct_child(cam, NAME_FAR)
        if far_en:
            if not far_rect:
                far_rect = make_rect_spline(c4d.Vector(1.0, 0.4, 0.1))
                far_rect.SetName(NAME_FAR)
                doc.InsertObject(far_rect, cam, None)
                c4d.EventAdd()
            set_clip_rect(cam, far_rect, far_dist)
        else:
            if far_rect:
                far_rect.Remove()
                c4d.EventAdd()

        return c4d.EXECUTIONRESULT_OK


# ══════════════════════════════════════════════════════════════════════════════
#  CommandData — «Target Camera» (кнопка в меню)
# ══════════════════════════════════════════════════════════════════════════════

class TargetCameraCmd(c4d.plugins.CommandData):

    def Execute(self, doc):
        doc.StartUndo()

        # ── 1. Камера ──────────────────────────────────────────────────────────
        cam = c4d.BaseObject(c4d.Ocamera)
        cam.SetName(NAME_CAM)
        cam[c4d.CAMERAOBJECT_FOCUS]              = 36.0
        cam[c4d.CAMERAOBJECT_NEAR_CLIPPING_ENABLE] = True
        cam[c4d.CAMERAOBJECT_NEAR_CLIPPING]      = 100.0
        cam[c4d.CAMERAOBJECT_FAR_CLIPPING_ENABLE]  = True
        cam[c4d.CAMERAOBJECT_FAR_CLIPPING]       = 10000.0
        cam.SetAbsPos(c4d.Vector(0, 0, -500))

        # User Data: Near rect enable
        bc1 = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BOOL)
        bc1[c4d.DESC_NAME]       = "Показать Near Clip Rect"
        bc1[c4d.DESC_SHORT_NAME] = "Near Rect"
        bc1[c4d.DESC_DEFAULT]    = False
        bc1[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_OFF
        cam.AddUserData(bc1)   # → ID_USERDATA, 1

        # User Data: Far rect enable
        bc2 = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BOOL)
        bc2[c4d.DESC_NAME]       = "Показать Far Clip Rect"
        bc2[c4d.DESC_SHORT_NAME] = "Far Rect"
        bc2[c4d.DESC_DEFAULT]    = False
        bc2[c4d.DESC_ANIMATE]    = c4d.DESC_ANIMATE_OFF
        cam.AddUserData(bc2)   # → ID_USERDATA, 2

        doc.InsertObject(cam)
        doc.AddUndo(c4d.UNDOTYPE_NEW, cam)

        # ── 2. Таргет (Null) ──────────────────────────────────────────────────
        target = c4d.BaseObject(c4d.Onull)
        target.SetName(NAME_TARGET)
        target[c4d.NULLOBJECT_DISPLAY] = 2   # отображение: крест
        target[c4d.NULLOBJECT_RADIUS]  = 25.0
        target.SetAbsPos(c4d.Vector(0, 0, 0))
        doc.InsertObject(target)
        doc.AddUndo(c4d.UNDOTYPE_NEW, target)

        # ── 3. Сплайн-линия ───────────────────────────────────────────────────
        spline = c4d.SplineObject(2, c4d.SPLINETYPE_LINEAR)
        spline.SetName(NAME_SPLINE)
        spline[c4d.SPLINEOBJECT_CLOSED]        = False
        spline[c4d.ID_BASEOBJECT_USECOLOR]     = 2
        spline[c4d.ID_BASEOBJECT_COLOR]        = c4d.Vector(0.9, 0.85, 0.1)
        spline.SetPoint(0, cam.GetAbsPos())
        spline.SetPoint(1, target.GetAbsPos())
        spline.Message(c4d.MSG_UPDATE)
        doc.InsertObject(spline)
        doc.AddUndo(c4d.UNDOTYPE_NEW, spline)

        # ── 4. Тег на камере ──────────────────────────────────────────────────
        tag = cam.MakeTag(PLUGIN_ID_TAG)
        tag.SetName("TargetCam Controller")
        tag[TAG_LINK_TARGET] = target
        tag[TAG_LINK_SPLINE] = spline
        doc.AddUndo(c4d.UNDOTYPE_NEW, tag)

        doc.EndUndo()
        doc.SetActiveObject(cam)
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED


# ══════════════════════════════════════════════════════════════════════════════
#  Регистрация плагинов
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Минимальная 32×32 иконка (чистый серый квадрат)
    icon = c4d.bitmaps.BaseBitmap()
    icon.Init(32, 32, 32)
    for x in range(32):
        for y in range(32):
            icon.SetPixel(x, y, 80, 140, 200)

    c4d.plugins.RegisterTagPlugin(
        id          = PLUGIN_ID_TAG,
        str         = "TargetCam Controller",
        info        = c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g           = TargetCamTag,
        description = "",
        icon        = None,
    )

    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID_CMD,
        str  = "Target Camera",
        info = 0,
        icon = icon,
        help = "Создать Target Camera (аналог 3ds Max)",
        dat  = TargetCameraCmd(),
    )
