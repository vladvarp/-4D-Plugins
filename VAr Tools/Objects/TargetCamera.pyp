"""
TargetCamera.pyp  —  Cinema 4D R26
Создаёт иерархию:
  Cam_Target_Line  (SplineObject — корень, pivot в центре линии)
    ├─ Target Camera   (Ocamera + тег)
    └─ Camera Target   (Onull)

Тег каждый кадр:
  • LookAt: камера смотрит на таргет
  • Сплайн: точки = мировые позиции камеры и таргета
  • Near/Far clip-рамки: реагируют на стандартные галочки камеры
"""

import c4d
import math

PLUGIN_ID_CMD   = 1068859
PLUGIN_ID_TAG   = 1068860

TAG_LINK_TARGET = 1000
TAG_LINK_SPLINE = 1001

NAME_CAM    = "Target Camera"
NAME_TARGET = "Camera Target"
NAME_SPLINE = "Cam_Target_Line"
NAME_NEAR   = "Cam_NearClip_Rect"
NAME_FAR    = "Cam_FarClip_Rect"


# ══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные функции
# ══════════════════════════════════════════════════════════════════════════════

def get_fov_and_aspect(cam):
    doc = cam.GetDocument()
    if not doc:
        return math.radians(45), 16.0 / 9.0
    rd     = doc.GetActiveRenderData()
    rend_w = float(rd[c4d.RDATA_XRES] or 1920)
    rend_h = float(rd[c4d.RDATA_YRES] or 1080)
    aspect = rend_w / max(rend_h, 1.0)
    film_w = float(cam[c4d.CAMERAOBJECT_FILM_X] or 36.0)
    focal  = float(cam[c4d.CAMERAOBJECT_FOCUS]  or 36.0)
    if focal <= 0:
        focal = 36.0
    fov_h = 2.0 * math.atan(film_w * 0.5 / focal)
    return fov_h, aspect


def set_rect_points(sp, hw, hh):
    sp.SetPoint(0, c4d.Vector(-hw, -hh, 0))
    sp.SetPoint(1, c4d.Vector( hw, -hh, 0))
    sp.SetPoint(2, c4d.Vector( hw,  hh, 0))
    sp.SetPoint(3, c4d.Vector(-hw,  hh, 0))
    sp.Message(c4d.MSG_UPDATE)


def make_rect_spline(color):
    sp = c4d.SplineObject(4, c4d.SPLINETYPE_LINEAR)
    sp[c4d.SPLINEOBJECT_CLOSED]    = True
    sp[c4d.ID_BASEOBJECT_USECOLOR] = 2
    sp[c4d.ID_BASEOBJECT_COLOR]    = color
    set_rect_points(sp, 1.0, 1.0)
    return sp


def update_clip_rect(cam, rect_obj, dist):
    """Размер рамки = реальный срез фрустума на расстоянии dist."""
    fov_h, aspect = get_fov_and_aspect(cam)
    hw = dist * math.tan(fov_h * 0.5)
    hh = hw / aspect
    set_rect_points(rect_obj, hw, hh)
    # Рамка — дочерний объект камеры, смещение по локальной -Z камеры.
    # Строим чистую матрицу: единичное вращение + только offset по Z.
    ml     = c4d.Matrix()
    ml.off = c4d.Vector(0.0, 0.0, -dist)
    rect_obj.SetMl(ml)


def find_child(parent, name):
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

    def Init(self, node):
        node[TAG_LINK_TARGET] = None
        node[TAG_LINK_SPLINE] = None
        return True

    def GetDDescription(self, node, description, flags):
        if not description.LoadDescription("tbaselist2d"):
            return False

        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bc[c4d.DESC_NAME] = "Таргет"
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TAG_LINK_TARGET, c4d.DTYPE_BASELISTLINK, 0)),
            bc, c4d.ID_ROOT)

        bs = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
        bs[c4d.DESC_NAME] = "Сплайн"
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(TAG_LINK_SPLINE, c4d.DTYPE_BASELISTLINK, 0)),
            bs, c4d.ID_ROOT)

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def Execute(self, tag, doc, op, bt, priority, flags):
        cam = op
        if cam is None:
            return c4d.EXECUTIONRESULT_OK

        target = tag[TAG_LINK_TARGET]
        if target is None or not target.IsAlive():
            return c4d.EXECUTIONRESULT_OK

        # Мировые позиции
        cam_pos    = cam.GetMg().off
        target_pos = target.GetMg().off
        diff       = target_pos - cam_pos
        dist_len   = diff.GetLength()

        if dist_len < 0.001:
            return c4d.EXECUTIONRESULT_OK

        # ── LookAt ───────────────────────────────────────────────────────────
        forward  = diff / dist_len          # нормализованный вектор к таргету
        world_up = c4d.Vector(0, 1, 0)

        right = forward.Cross(world_up)
        if right.GetLength() < 0.0001:
            world_up = c4d.Vector(0, 0, 1)
            right    = forward.Cross(world_up)
        right  = right.GetNormalized()
        up_vec = right.Cross(forward).GetNormalized()

        # C4D-камера смотрит в локальный -Z, поэтому v3 = -forward
        mg     = cam.GetMg()
        mg.v1  = right
        mg.v2  = up_vec
        mg.v3  = -forward
        cam.SetMg(mg)

        # ── Сплайн: pivot в центре отрезка камера↔таргет ─────────────────────
        spline = tag[TAG_LINK_SPLINE]
        if spline and spline.IsAlive():
            center     = (cam_pos + target_pos) * 0.5
            half_vec   = (target_pos - cam_pos) * 0.5   # вектор от центра к таргету
            # Перемещаем pivot сплайна в центр (сохраняем вращение = единичное)
            mg_sp      = spline.GetMg()
            mg_sp.off  = center
            spline.SetMg(mg_sp)
            # Точки в локальных координатах сплайна: -half и +half вдоль мирового вектора
            inv        = ~spline.GetMg()
            p0         = inv * cam_pos
            p1         = inv * target_pos
            spline.ResizeObject(2)
            spline.SetPoint(0, p0)
            spline.SetPoint(1, p1)
            spline.Message(c4d.MSG_UPDATE)

        # ── Клиппинг-рамки (управляются стандартными галочками камеры) ────────
        near_en = bool(cam[c4d.CAMERAOBJECT_NEAR_CLIPPING_ENABLE])
        far_en  = bool(cam[c4d.CAMERAOBJECT_FAR_CLIPPING_ENABLE])

        near_dist = float(cam[c4d.CAMERAOBJECT_NEAR_CLIPPING] or 100.0)
        far_dist  = float(cam[c4d.CAMERAOBJECT_FAR_CLIPPING]  or 10000.0)
        if near_dist <= 0: near_dist = 1.0
        if far_dist  <= 0: far_dist  = 10000.0

        # Near rect
        near_rect = find_child(cam, NAME_NEAR)
        if near_en:
            if not near_rect:
                near_rect = make_rect_spline(c4d.Vector(0.2, 0.85, 1.0))
                near_rect.SetName(NAME_NEAR)
                doc.InsertObject(near_rect, cam, None)
                c4d.EventAdd()
            update_clip_rect(cam, near_rect, near_dist)
        else:
            if near_rect:
                near_rect.Remove()
                c4d.EventAdd()

        # Far rect
        far_rect = find_child(cam, NAME_FAR)
        if far_en:
            if not far_rect:
                far_rect = make_rect_spline(c4d.Vector(1.0, 0.4, 0.1))
                far_rect.SetName(NAME_FAR)
                doc.InsertObject(far_rect, cam, None)
                c4d.EventAdd()
            update_clip_rect(cam, far_rect, far_dist)
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

        # ── Сплайн-линия (корень системы, pivot в центре) ────────────────────
        spline = c4d.SplineObject(2, c4d.SPLINETYPE_LINEAR)
        spline.SetName(NAME_SPLINE)
        spline[c4d.SPLINEOBJECT_CLOSED]    = False
        spline[c4d.ID_BASEOBJECT_USECOLOR] = 2
        spline[c4d.ID_BASEOBJECT_COLOR]    = c4d.Vector(0.9, 0.85, 0.1)
        # Начальные точки: камера слева (-Z), таргет справа (+Z)
        spline.SetPoint(0, c4d.Vector(0, 0, -250))
        spline.SetPoint(1, c4d.Vector(0, 0,  250))
        spline.Message(c4d.MSG_UPDATE)
        # Сплайн вставляем в корень сцены
        doc.InsertObject(spline)
        doc.AddUndo(c4d.UNDOTYPE_NEW, spline)

        # ── Камера — дочерний объект сплайна, смещена по -Z ──────────────────
        cam = c4d.BaseObject(c4d.Ocamera)
        cam.SetName(NAME_CAM)
        cam[c4d.CAMERAOBJECT_FOCUS]                = 36.0
        # Near/Far выключены по умолчанию — пользователь включает сам
        cam[c4d.CAMERAOBJECT_NEAR_CLIPPING_ENABLE] = False
        cam[c4d.CAMERAOBJECT_NEAR_CLIPPING]        = 100.0
        cam[c4d.CAMERAOBJECT_FAR_CLIPPING_ENABLE]  = False
        cam[c4d.CAMERAOBJECT_FAR_CLIPPING]         = 10000.0
        cam.SetAbsPos(c4d.Vector(0, 0, -250))      # мировая позиция при создании
        doc.InsertObject(cam, spline, None)
        doc.AddUndo(c4d.UNDOTYPE_NEW, cam)

        # ── Таргет впереди камеры — дочерний объект сплайна, смещён по +Z ────
        target = c4d.BaseObject(c4d.Onull)
        target.SetName(NAME_TARGET)
        target[c4d.NULLOBJECT_DISPLAY] = 2         # крест
        target[c4d.NULLOBJECT_RADIUS]  = 20.0
        target.SetAbsPos(c4d.Vector(0, 0, 250))    # мировая позиция при создании
        doc.InsertObject(target, spline, None)
        doc.AddUndo(c4d.UNDOTYPE_NEW, target)

        # ── Тег на камере ─────────────────────────────────────────────────────
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
