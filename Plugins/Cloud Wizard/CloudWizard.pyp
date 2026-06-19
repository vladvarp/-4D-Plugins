# coding: utf-8
"""
Cloud Wizard — Cinema 4D R26+
Plugin ID : 1069028
Файл: plugins/VAr Tools/CloudWizard.pyp

Генератор процедурных облаков для Cinema 4D.
Создаёт реалистичные кучевые и перистые облака
с помощью метабол и шумовых материалов.
"""

import c4d  # type: ignore
import os
import math
import random
import base64
import tempfile

# ─── ID ───────────────────────────────────────────────────────────────────────
PLUGIN_ID   = 1069028
PLUGIN_NAME = "Cloud Wizard"
PLUGIN_NAME_V = "Cloud Wizard v1.0"
PLUGIN_HELP = "Процедурная генерация облаков в сцене"

# ─── ID виджетов ──────────────────────────────────────────────────────────────
ID_BASE = 20000

# --- Вкладки ---
ID_TAB_GROUP        = ID_BASE + 1
ID_TAB_MAIN         = ID_BASE + 2
ID_TAB_SHAPE        = ID_BASE + 3
ID_TAB_MATERIAL     = ID_BASE + 4

# --- Тип облака ---
ID_GRP_TYPE         = ID_BASE + 10
ID_LBL_TYPE         = ID_BASE + 11
ID_COMBO_TYPE       = ID_BASE + 12   # Тип облака

# --- Общие параметры ---
ID_GRP_GENERAL      = ID_BASE + 20
ID_LBL_NAME         = ID_BASE + 21
ID_EDIT_NAME        = ID_BASE + 22   # Имя объекта
ID_LBL_SEED         = ID_BASE + 23
ID_EDIT_SEED        = ID_BASE + 24   # Seed

# --- Форма ---
ID_GRP_SHAPE        = ID_BASE + 30
ID_LBL_SCALE        = ID_BASE + 31
ID_EDIT_SCALE       = ID_BASE + 32   # Общий масштаб (м)
ID_LBL_SCALE_X      = ID_BASE + 33
ID_EDIT_SCALE_X     = ID_BASE + 34   # Масштаб X (ширина)
ID_LBL_SCALE_Y      = ID_BASE + 35
ID_EDIT_SCALE_Y     = ID_BASE + 36   # Масштаб Y (высота)
ID_LBL_SCALE_Z      = ID_BASE + 37
ID_EDIT_SCALE_Z     = ID_BASE + 38   # Масштаб Z (глубина)
ID_LBL_PUFF         = ID_BASE + 39
ID_EDIT_PUFF        = ID_BASE + 40   # Пышность (billowing)

# --- Детали ---
ID_GRP_DETAIL       = ID_BASE + 50
ID_LBL_BLOBS        = ID_BASE + 51
ID_EDIT_BLOBS       = ID_BASE + 52   # Количество шариков метаболы
ID_LBL_HULL         = ID_BASE + 53
ID_EDIT_HULL        = ID_BASE + 54   # Порог метаболы (hull size)
ID_LBL_SCATTER      = ID_BASE + 55
ID_EDIT_SCATTER     = ID_BASE + 56   # Разброс шариков
ID_LBL_VARIANCE     = ID_BASE + 57
ID_EDIT_VARIANCE    = ID_BASE + 58   # Разброс размеров шариков (0–1)

# --- Материал ---
ID_GRP_MAT          = ID_BASE + 70
ID_LBL_COLOR_MAIN   = ID_BASE + 71
ID_COLOR_MAIN       = ID_BASE + 72   # Основной цвет
ID_LBL_COLOR_SHADOW = ID_BASE + 73
ID_COLOR_SHADOW     = ID_BASE + 74   # Цвет тени
ID_LBL_LUMI         = ID_BASE + 75
ID_EDIT_LUMI        = ID_BASE + 76   # Светимость (Luminance) %
ID_LBL_TRANSP       = ID_BASE + 77
ID_EDIT_TRANSP      = ID_BASE + 78   # Прозрачность (для перистых) %
ID_CHK_NOISE        = ID_BASE + 79   # Добавить шумовой слой
ID_CHK_SSS          = ID_BASE + 80   # Рассеяние внутри (подповерхностное)

# --- Расположение ---
ID_GRP_POS          = ID_BASE + 90
ID_LBL_POS_X        = ID_BASE + 91
ID_EDIT_POS_X       = ID_BASE + 92
ID_LBL_POS_Y        = ID_BASE + 93
ID_EDIT_POS_Y       = ID_BASE + 94
ID_LBL_POS_Z        = ID_BASE + 95
ID_EDIT_POS_Z       = ID_BASE + 96

# --- Нижний блок ---
ID_GRP_BOTTOM       = ID_BASE + 100
ID_LBL_STATUS       = ID_BASE + 101
ID_BTN_GENERATE     = ID_BASE + 102
ID_BTN_CLEAR        = ID_BASE + 103
ID_BTN_RANDOMIZE    = ID_BASE + 104
ID_CHK_SKY          = ID_BASE + 105  # Добавить физическое небо
ID_CHK_HDRI_SUN     = ID_BASE + 106  # Добавить солнце

# ─── Типы облаков ─────────────────────────────────────────────────────────────
CLOUD_TYPES = [
    "Кучевые (Cumulus)",          # 0
    "Перистые (Cirrus)",          # 1
    "Грозовые (Cumulonimbus)",    # 2
    "Слоистые (Stratus)",         # 3
    "Высококучевые (Altocumulus)",# 4
]

# Профили форм для каждого типа: (blob_count, hull, scatter, scale_y_factor, puff)
CLOUD_PROFILES = {
    0: dict(blobs=34, hull=72, scatter=1.0, sy=0.55, puff=0.65),   # Cumulus
    1: dict(blobs=18, hull=55, scatter=2.5, sy=0.18, puff=0.25),   # Cirrus
    2: dict(blobs=55, hull=68, scatter=0.8, sy=2.20, puff=0.80),   # Cumulonimbus
    3: dict(blobs=22, hull=80, scatter=3.0, sy=0.12, puff=0.30),   # Stratus
    4: dict(blobs=28, hull=65, scatter=1.2, sy=0.40, puff=0.55),   # Altocumulus
}

# ─── Иконка ───────────────────────────────────────────────────────────────────
_ICON_B64 = "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"


def _make_icon():
    """Декодирует base64-иконку в BaseBitmap.
    Если строка — заглушка '000', возвращает None."""
    if _ICON_B64 == "000":
        return None
    try:
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
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        return bmp
    except Exception:
        return None


# ─── Генерация облака ─────────────────────────────────────────────────────────

def _random_on_ellipsoid(rng, rx, ry, rz):
    """Возвращает случайную точку внутри эллипсоида (rx, ry, rz).
    Использует метод rejection sampling для равномерности."""
    for _ in range(200):
        x = rng.uniform(-rx, rx)
        y = rng.uniform(-ry, ry)
        z = rng.uniform(-rz, rz)
        # Проверяем, внутри ли эллипсоида
        if (x/rx)**2 + (y/ry)**2 + (z/rz)**2 <= 1.0:
            return x, y, z
    # Fallback: возвращаем точку на оси
    return 0.0, rng.uniform(-ry*0.5, ry*0.5), 0.0


def _generate_cloud(params):
    """
    Создаёт группу объектов Cinema 4D, образующих облако.

    params — dict с ключами:
        name, seed, cloud_type, scale, sx, sy, sz,
        puff, blobs, hull, scatter, variance,
        color_main, color_shadow, luminance, transparency,
        use_noise, use_sss, pos_x, pos_y, pos_z,
        add_sky, add_sun
    """
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return False, "Нет активного документа"

    rng = random.Random(params["seed"])

    cloud_type  = params["cloud_type"]
    profile     = CLOUD_PROFILES[cloud_type]
    base_scale  = params["scale"]

    # Размеры главного эллипсоида для размещения шариков
    rx = base_scale * params["sx"] * 0.5
    ry = base_scale * params["sy"] * profile["sy"] * 0.5
    rz = base_scale * params["sz"] * 0.5

    blob_count  = params["blobs"]
    hull_val    = params["hull"]        # 1–100 → C4D threshold
    scatter_mul = params["scatter"]     # Множитель разброса
    variance    = params["variance"]    # 0–1 разброс размеров
    puff        = params["puff"]        # 0–1 → размер сферы

    # ── Создаём корневую null-группу ─────────────────────────────────────────
    root_null = c4d.BaseObject(c4d.Onull)
    root_null.SetName(params["name"])
    root_null[c4d.NULLOBJECT_DISPLAY] = c4d.NULLOBJECT_DISPLAY_NONE

    pos = c4d.Vector(params["pos_x"], params["pos_y"], params["pos_z"])
    root_null.SetAbsPos(pos)

    # ── Создаём Metaball ──────────────────────────────────────────────────────
    meta = c4d.BaseObject(c4d.Ometaball)
    meta.SetName(params["name"] + "_Metaball")

    # Порог (Hull Value) — чем меньше, тем мягче поверхность
    hull_c4d = max(1.0, min(100.0, float(hull_val)))
    meta[c4d.METABALLOBJECT_THRESHOLD] = hull_c4d / 100.0

    # Точность (Subdivision)
    # Перистые и слоистые делаем грубее (быстрее), грозовые — детальнее
    subdiv_map = {0: 8, 1: 12, 2: 6, 3: 14, 4: 9}
    meta[c4d.METABALLOBJECT_SUBEDITOR] = subdiv_map.get(cloud_type, 8)
    meta[c4d.METABALLOBJECT_SUBRAY]    = max(4, subdiv_map.get(cloud_type, 8) - 2)

    meta.InsertUnder(root_null)

    # ── Добавляем дочерние сферы в метаболу ──────────────────────────────────
    # Базовый радиус одного шарика = пышность * масштаб / кубический корень из числа шариков
    blob_base_r = puff * base_scale * 0.42 / max(1.0, blob_count ** (1.0/3.0))

    for i in range(blob_count):
        sphere = c4d.BaseObject(c4d.Osphere)

        # Случайный размер с вариацией
        r_variation = 1.0 + rng.uniform(-variance * 0.5, variance * 0.5)
        # Первые 3 шарика — "опорные", крупнее, чтобы сформировать базу
        if i < 3:
            r_variation = rng.uniform(1.1, 1.5)

        blob_r = blob_base_r * max(0.2, r_variation) * scatter_mul
        sphere[c4d.PRIM_SPHERE_RAD] = blob_r

        # Позиция внутри эллипсоида
        x, y, z = _random_on_ellipsoid(rng, rx * scatter_mul,
                                              ry * scatter_mul,
                                              rz * scatter_mul)

        # Для кучевых — добавляем вертикальную башнеобразность
        if cloud_type == 0 or cloud_type == 2:
            # Верхние шарики смещаем вверх и уменьшаем
            if i > blob_count * 0.5:
                y += rng.uniform(0, ry * 0.6)
                sphere[c4d.PRIM_SPHERE_RAD] *= rng.uniform(0.5, 0.85)

        # Для перистых — вытягиваем по X
        if cloud_type == 1:
            x *= rng.uniform(1.5, 3.0)
            sphere[c4d.PRIM_SPHERE_RAD] *= rng.uniform(0.3, 0.7)

        # Для грозовых — резко вытягиваем по Y вверху
        if cloud_type == 2 and i > blob_count * 0.7:
            y += ry * rng.uniform(0.5, 1.5)

        sphere.SetAbsPos(c4d.Vector(x, y, z))
        sphere.SetName("blob_{:03d}".format(i))
        sphere.InsertUnder(meta)

    # ── Создаём материал ──────────────────────────────────────────────────────
    mat = _create_cloud_material(params, rng)
    doc.InsertMaterial(mat)

    # ── Применяем материал к метаболе ────────────────────────────────────────
    tag = meta.MakeTag(c4d.Ttexture)
    tag[c4d.TEXTURETAG_MATERIAL] = mat
    tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_SPHERICAL

    # ── Физическое небо (опционально) ─────────────────────────────────────────
    if params.get("add_sky"):
        # Проверяем, есть ли уже Physical Sky
        existing_sky = _find_object_by_type(doc, c4d.Osky)
        if existing_sky is None:
            sky = c4d.BaseObject(c4d.Osky)
            sky.SetName("Physical Sky")
            doc.InsertObject(sky)

    # ── Солнечный свет (опционально) ──────────────────────────────────────────
    if params.get("add_sun"):
        existing_sun = _find_sun_light(doc)
        if existing_sun is None:
            sun = c4d.BaseObject(c4d.Olight)
            sun.SetName("Sun Light")
            sun[c4d.LIGHT_TYPE]      = c4d.LIGHT_TYPE_DISTANT
            sun[c4d.LIGHT_COLOR]     = c4d.Vector(1.0, 0.97, 0.88)
            sun[c4d.LIGHT_INTENSITY] = 1.5
            sun[c4d.LIGHT_SHADOWTYPE] = c4d.LIGHT_SHADOWTYPE_AREA
            # Угол солнца ~45°
            sun.SetRelRot(c4d.Vector(
                c4d.utils.DegToRad(-45.0),
                c4d.utils.DegToRad(35.0),
                0.0
            ))
            doc.InsertObject(sun)

    # ── Вставляем root_null в документ ───────────────────────────────────────
    doc.InsertObject(root_null)
    doc.SetActiveObject(root_null)
    c4d.EventAdd()

    return True, "Облако «{}» создано ({} шариков)".format(params["name"], blob_count)


def _create_cloud_material(params, rng):
    """Создаёт и возвращает материал для облака."""
    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(params["name"] + "_Mat")

    cloud_type  = params["cloud_type"]
    col_main    = params["color_main"]
    col_shadow  = params["color_shadow"]
    luminance   = params["luminance"] / 100.0
    transparency = params["transparency"] / 100.0

    # ── Цвет (Color) ──────────────────────────────────────────────────────────
    mat[c4d.MATERIAL_USE_COLOR] = True
    mat[c4d.MATERIAL_COLOR_COLOR] = col_main

    # Немного зашумить цвет для перистых
    if params.get("use_noise") and cloud_type == 1:
        noise_shader = c4d.BaseShader(c4d.Xnoise)
        noise_shader[c4d.SLA_NOISE_NOISE]     = c4d.SLA_NOISE_NOISE_BUYA
        noise_shader[c4d.SLA_NOISE_OCTAVES]   = 5
        noise_shader[c4d.SLA_NOISE_SCALE]     = 45.0
        noise_shader[c4d.SLA_NOISE_GLOBAL_SCALE] = 250.0
        mat[c4d.MATERIAL_COLOR_SHADER] = noise_shader
        mat.InsertShader(noise_shader)

    # ── Светимость (Luminance) ─────────────────────────────────────────────────
    if luminance > 0.0:
        mat[c4d.MATERIAL_USE_LUMINANCE] = True
        mat[c4d.MATERIAL_LUMINANCE_COLOR]     = col_main
        mat[c4d.MATERIAL_LUMINANCE_BRIGHTNESS] = luminance

    # ── Прозрачность (Transparency) ───────────────────────────────────────────
    # Перистые по умолчанию немного прозрачны
    effective_transp = transparency
    if cloud_type == 1 and effective_transp < 0.05:
        effective_transp = 0.35

    if effective_transp > 0.0:
        mat[c4d.MATERIAL_USE_TRANSPARENCY] = True
        mat[c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS] = effective_transp
        mat[c4d.MATERIAL_TRANSPARENCY_REFRACTION]  = 1.0

    # ── Specular — матовый для облаков ────────────────────────────────────────
    mat[c4d.MATERIAL_USE_SPECULAR] = True
    mat[c4d.MATERIAL_SPECULAR_WIDTH]      = 0.65
    mat[c4d.MATERIAL_SPECULAR_HEIGHT]     = 0.12
    mat[c4d.MATERIAL_SPECULAR_FALLOFF]    = 0.45
    mat[c4d.MATERIAL_SPECULAR_INNERWIDTH] = 0.0

    # ── Рассеяние (Diffusion) — для объёма ────────────────────────────────────
    if params.get("use_noise"):
        mat[c4d.MATERIAL_USE_DIFFUSION] = True
        diff_noise = c4d.BaseShader(c4d.Xnoise)
        diff_noise[c4d.SLA_NOISE_NOISE]   = c4d.SLA_NOISE_NOISE_TURBULENCE
        diff_noise[c4d.SLA_NOISE_OCTAVES] = 4
        diff_noise[c4d.SLA_NOISE_SCALE]   = 60.0
        diff_noise[c4d.SLA_NOISE_GLOBAL_SCALE] = 180.0
        mat[c4d.MATERIAL_DIFFUSION_SHADER] = diff_noise
        mat.InsertShader(diff_noise)

    # ── Шум на Bump для детализации поверхности ────────────────────────────────
    if params.get("use_noise"):
        mat[c4d.MATERIAL_USE_BUMP] = True
        bump_noise = c4d.BaseShader(c4d.Xnoise)
        bump_type_map = {0: c4d.SLA_NOISE_NOISE_TURBULENCE,
                         1: c4d.SLA_NOISE_NOISE_BUYA,
                         2: c4d.SLA_NOISE_NOISE_TURBULENCE,
                         3: c4d.SLA_NOISE_NOISE_WAVY_TURBULENCE,
                         4: c4d.SLA_NOISE_NOISE_DENTS}
        bump_noise[c4d.SLA_NOISE_NOISE]   = bump_type_map.get(cloud_type,
                                                c4d.SLA_NOISE_NOISE_TURBULENCE)
        bump_noise[c4d.SLA_NOISE_OCTAVES] = 6
        bump_noise[c4d.SLA_NOISE_SCALE]   = 35.0
        bump_noise[c4d.SLA_NOISE_GLOBAL_SCALE] = 120.0
        mat[c4d.MATERIAL_BUMP_SHADER]     = bump_noise
        mat[c4d.MATERIAL_BUMP_STRENGTH]   = 0.18
        mat.InsertShader(bump_noise)

    # ── Environment (отражение неба) ──────────────────────────────────────────
    mat[c4d.MATERIAL_USE_ENVIRONMENT] = True
    mat[c4d.MATERIAL_ENVIRONMENT_COLOR]      = col_shadow
    mat[c4d.MATERIAL_ENVIRONMENT_BRIGHTNESS] = 0.08

    mat.Update(True, True)
    return mat


def _find_object_by_type(doc, obj_type):
    """Рекурсивно ищет первый объект заданного типа в документе."""
    def _walk(obj):
        while obj:
            if obj.GetType() == obj_type:
                return obj
            found = _walk(obj.GetDown())
            if found:
                return found
            obj = obj.GetNext()
        return None
    return _walk(doc.GetFirstObject())


def _find_sun_light(doc):
    """Ищет направленный источник света с именем «Sun Light»."""
    def _walk(obj):
        while obj:
            if obj.GetType() == c4d.Olight:
                if "Sun" in obj.GetName() or "sun" in obj.GetName():
                    return obj
            found = _walk(obj.GetDown())
            if found:
                return found
            obj = obj.GetNext()
        return None
    return _walk(doc.GetFirstObject())


def _remove_clouds(doc):
    """Удаляет все объекты, созданные Cloud Wizard (по наличию тега _Metaball)."""
    removed = 0

    def _walk(obj):
        nonlocal removed
        to_delete = []
        while obj:
            nxt = obj.GetNext()
            # Ищем null-группы с дочерней метаболой
            if obj.GetType() == c4d.Onull:
                child = obj.GetDown()
                while child:
                    if child.GetType() == c4d.Ometaball:
                        to_delete.append(obj)
                        break
                    child = child.GetNext()
            obj = nxt
        for o in to_delete:
            o.Remove()
            removed += 1

    _walk(doc.GetFirstObject())
    c4d.EventAdd()
    return removed


# ─── Диалог ───────────────────────────────────────────────────────────────────

class CloudWizardDialog(c4d.gui.GeDialog):

    def __init__(self, command):
        super(CloudWizardDialog, self).__init__()
        self._command     = command
        self._cloud_count = 0   # счётчик созданных облаков за сессию

    # ── CreateLayout ─────────────────────────────────────────────────────────

    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME)

        # ── Тип облака ──────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_TYPE, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(8, 6, 8, 4)
        self.AddStaticText(ID_LBL_TYPE, c4d.BFH_LEFT, initw=90, name="Тип облака:")
        self.AddComboBox(ID_COMBO_TYPE, c4d.BFH_SCALEFIT, initw=200)
        for i, name in enumerate(CLOUD_TYPES):
            self.AddChild(ID_COMBO_TYPE, i, name)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Основные параметры ───────────────────────────────────────────────
        self.GroupBegin(ID_GRP_GENERAL, c4d.BFH_SCALEFIT, cols=4, rows=2)
        self.GroupBorderSpace(8, 4, 8, 2)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, cols=4, name="Основные параметры")

        self.AddStaticText(ID_LBL_NAME, c4d.BFH_LEFT, initw=90, name="Имя:")
        self.AddEditText(ID_EDIT_NAME, c4d.BFH_SCALEFIT, initw=150)
        self.AddStaticText(ID_LBL_SEED, c4d.BFH_LEFT, initw=60, name="Seed:")
        self.AddEditNumberArrows(ID_EDIT_SEED, c4d.BFH_LEFT, initw=80)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Форма ────────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=4, rows=4)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, cols=4, name="Форма")

        self.AddStaticText(ID_LBL_SCALE, c4d.BFH_LEFT, initw=90, name="Масштаб (м):")
        self.AddEditNumberArrows(ID_EDIT_SCALE, c4d.BFH_LEFT, initw=80)
        self.AddStaticText(ID_LBL_PUFF, c4d.BFH_LEFT, initw=80, name="Пышность:")
        self.AddEditSlider(ID_EDIT_PUFF, c4d.BFH_SCALEFIT, initw=120)

        self.AddStaticText(ID_LBL_SCALE_X, c4d.BFH_LEFT, initw=90, name="Ширина (X):")
        self.AddEditSlider(ID_EDIT_SCALE_X, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(ID_LBL_SCALE_Y, c4d.BFH_LEFT, initw=80, name="Высота (Y):")
        self.AddEditSlider(ID_EDIT_SCALE_Y, c4d.BFH_SCALEFIT, initw=120)

        self.AddStaticText(ID_LBL_SCALE_Z, c4d.BFH_LEFT, initw=90, name="Глубина (Z):")
        self.AddEditSlider(ID_EDIT_SCALE_Z, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(0, c4d.BFH_LEFT, initw=80, name="")
        self.AddStaticText(0, c4d.BFH_LEFT, initw=120, name="")
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Детали ───────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_DETAIL, c4d.BFH_SCALEFIT, cols=4, rows=3)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, cols=4, name="Детализация метаболы")

        self.AddStaticText(ID_LBL_BLOBS, c4d.BFH_LEFT, initw=90, name="Шариков:")
        self.AddEditNumberArrows(ID_EDIT_BLOBS, c4d.BFH_LEFT, initw=70)
        self.AddStaticText(ID_LBL_HULL, c4d.BFH_LEFT, initw=80, name="Hull (%):")
        self.AddEditSlider(ID_EDIT_HULL, c4d.BFH_SCALEFIT, initw=120)

        self.AddStaticText(ID_LBL_SCATTER, c4d.BFH_LEFT, initw=90, name="Разброс:")
        self.AddEditSlider(ID_EDIT_SCATTER, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(ID_LBL_VARIANCE, c4d.BFH_LEFT, initw=80, name="Вариация:")
        self.AddEditSlider(ID_EDIT_VARIANCE, c4d.BFH_SCALEFIT, initw=120)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Материал ─────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_MAT, c4d.BFH_SCALEFIT, cols=4, rows=4)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, cols=4, name="Материал")

        self.AddStaticText(ID_LBL_COLOR_MAIN, c4d.BFH_LEFT, initw=90, name="Основной цвет:")
        self.AddColorField(ID_COLOR_MAIN, c4d.BFH_LEFT, initw=120, inith=14)
        self.AddStaticText(ID_LBL_COLOR_SHADOW, c4d.BFH_LEFT, initw=90, name="Цвет тени:")
        self.AddColorField(ID_COLOR_SHADOW, c4d.BFH_LEFT, initw=120, inith=14)

        self.AddStaticText(ID_LBL_LUMI, c4d.BFH_LEFT, initw=90, name="Светимость (%):")
        self.AddEditSlider(ID_EDIT_LUMI, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(ID_LBL_TRANSP, c4d.BFH_LEFT, initw=90, name="Прозрачность (%):")
        self.AddEditSlider(ID_EDIT_TRANSP, c4d.BFH_SCALEFIT, initw=120)

        self.AddCheckbox(ID_CHK_NOISE, c4d.BFH_LEFT, initw=0, inith=0,
                         name="Noise-шейдеры (Bump + Diffusion)")
        self.AddStaticText(0, c4d.BFH_LEFT, name="")
        self.AddCheckbox(ID_CHK_SSS, c4d.BFH_LEFT, initw=0, inith=0,
                         name="Luminance-гало")
        self.AddStaticText(0, c4d.BFH_LEFT, name="")
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Позиция ──────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_POS, c4d.BFH_SCALEFIT, cols=6, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_POS_X, c4d.BFH_LEFT, initw=26, name="X:")
        self.AddEditNumberArrows(ID_EDIT_POS_X, c4d.BFH_LEFT, initw=70)
        self.AddStaticText(ID_LBL_POS_Y, c4d.BFH_LEFT, initw=26, name="Y:")
        self.AddEditNumberArrows(ID_EDIT_POS_Y, c4d.BFH_LEFT, initw=70)
        self.AddStaticText(ID_LBL_POS_Z, c4d.BFH_LEFT, initw=26, name="Z:")
        self.AddEditNumberArrows(ID_EDIT_POS_Z, c4d.BFH_LEFT, initw=70)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Дополнительно ────────────────────────────────────────────────────
        self.GroupBegin(ID_BASE + 110, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(8, 2, 8, 2)
        self.AddCheckbox(ID_CHK_SKY,      c4d.BFH_LEFT, initw=0, inith=0,
                         name="Добавить Physical Sky")
        self.AddCheckbox(ID_CHK_HDRI_SUN, c4d.BFH_LEFT, initw=0, inith=0,
                         name="Добавить направленный свет (Sun)")
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Нижняя панель кнопок ─────────────────────────────────────────────
        self.GroupBegin(ID_GRP_BOTTOM, c4d.BFH_SCALEFIT, cols=3, rows=2)
        self.GroupBorderSpace(8, 4, 8, 6)

        self.AddButton(ID_BTN_GENERATE,  c4d.BFH_SCALEFIT, inith=24, name="⛅  Создать облако")
        self.AddButton(ID_BTN_RANDOMIZE, c4d.BFH_SCALEFIT, inith=24, name="🎲  Случайные параметры")
        self.AddButton(ID_BTN_CLEAR,     c4d.BFH_SCALEFIT, inith=24, name="🗑  Удалить все облака")

        self.AddStaticText(ID_LBL_STATUS, c4d.BFH_SCALEFIT | c4d.BFH_CENTER,
                           cols=3, name="Готов к работе")
        self.GroupEnd()

        return True

    # ── InitValues ───────────────────────────────────────────────────────────

    def InitValues(self):
        # Тип — кучевые по умолчанию
        self.SetInt32(ID_COMBO_TYPE, 0)

        # Имя
        self.SetString(ID_EDIT_NAME, "Cloud_001")

        # Seed
        self.SetInt32(ID_EDIT_SEED, 42, min=0, max=9999999)

        # Масштаб
        self.SetFloat(ID_EDIT_SCALE, 500.0, min=10.0, max=50000.0, step=10.0,
                      format=c4d.FORMAT_METER)

        # Форма
        self.SetFloat(ID_EDIT_SCALE_X, 1.0, min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_Y, 1.0, min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_Z, 1.0, min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_PUFF, 0.65, min=0.1, max=1.5, step=0.05)

        # Детали
        self.SetInt32(ID_EDIT_BLOBS, 34, min=4, max=200)
        self.SetFloat(ID_EDIT_HULL,     72.0, min=1.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_SCATTER,   1.0, min=0.1, max=4.0,   step=0.05)
        self.SetFloat(ID_EDIT_VARIANCE,  0.4, min=0.0, max=1.0,   step=0.05)

        # Материал
        self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.97, 0.97, 1.00))
        self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.60, 0.67, 0.78))
        self.SetFloat(ID_EDIT_LUMI,   18.0, min=0.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_TRANSP,  0.0, min=0.0, max=100.0, step=1.0)
        self.SetBool(ID_CHK_NOISE, True)
        self.SetBool(ID_CHK_SSS,   False)

        # Позиция
        self.SetFloat(ID_EDIT_POS_X, 0.0,    min=-100000.0, max=100000.0,
                      step=10.0, format=c4d.FORMAT_METER)
        self.SetFloat(ID_EDIT_POS_Y, 1500.0, min=-100000.0, max=100000.0,
                      step=10.0, format=c4d.FORMAT_METER)
        self.SetFloat(ID_EDIT_POS_Z, 0.0,    min=-100000.0, max=100000.0,
                      step=10.0, format=c4d.FORMAT_METER)

        # Доп
        self.SetBool(ID_CHK_SKY,      False)
        self.SetBool(ID_CHK_HDRI_SUN, False)

        return True

    # ── Command ──────────────────────────────────────────────────────────────

    def Command(self, widget_id, msg):

        if widget_id == ID_COMBO_TYPE:
            self._apply_profile()
            return True

        if widget_id == ID_BTN_RANDOMIZE:
            self._randomize()
            return True

        if widget_id == ID_BTN_GENERATE:
            self._generate()
            return True

        if widget_id == ID_BTN_CLEAR:
            doc = c4d.documents.GetActiveDocument()
            if doc:
                n = _remove_clouds(doc)
                self.SetString(ID_LBL_STATUS,
                    "Удалено объектов: {}".format(n) if n else "Облака не найдены")
            return True

        return True

    # ── Вспомогательные методы ───────────────────────────────────────────────

    def _apply_profile(self):
        """Заполняет поля значениями из профиля выбранного типа облака."""
        cloud_type = self.GetInt32(ID_COMBO_TYPE)
        p = CLOUD_PROFILES[cloud_type]

        self.SetInt32(ID_EDIT_BLOBS, p["blobs"])
        self.SetFloat(ID_EDIT_HULL,    float(p["hull"]),    min=1.0, max=100.0)
        self.SetFloat(ID_EDIT_SCATTER, p["scatter"],        min=0.1, max=4.0)
        self.SetFloat(ID_EDIT_PUFF,    p["puff"],           min=0.1, max=1.5)

        # Высота по профилю
        current_sy = p["sy"]
        self.SetFloat(ID_EDIT_SCALE_Y, min(4.9, max(0.1, current_sy)),
                      min=0.1, max=5.0)

        # Особые цветовые настройки для типов
        if cloud_type == 1:   # Перистые — более прозрачные, холоднее
            self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.94, 0.96, 1.00))
            self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.70, 0.78, 0.90))
            self.SetFloat(ID_EDIT_TRANSP, 35.0, min=0.0, max=100.0)
        elif cloud_type == 2:  # Грозовые — темнее
            self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.82, 0.84, 0.88))
            self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.28, 0.30, 0.36))
            self.SetFloat(ID_EDIT_TRANSP, 0.0, min=0.0, max=100.0)
        else:
            self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.97, 0.97, 1.00))
            self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.60, 0.67, 0.78))
            self.SetFloat(ID_EDIT_TRANSP, 0.0, min=0.0, max=100.0)

    def _randomize(self):
        """Случайная генерация всех параметров."""
        import time
        rng = random.Random(int(time.time() * 1000) % 9999999)

        new_seed = rng.randint(0, 9999999)
        self.SetInt32(ID_EDIT_SEED, new_seed)
        self.SetFloat(ID_EDIT_SCALE,
                      rng.uniform(200.0, 1200.0), min=10.0, max=50000.0)
        self.SetFloat(ID_EDIT_SCALE_X,
                      rng.uniform(0.5, 3.0), min=0.1, max=5.0)
        self.SetFloat(ID_EDIT_SCALE_Y,
                      rng.uniform(0.3, 1.5), min=0.1, max=5.0)
        self.SetFloat(ID_EDIT_SCALE_Z,
                      rng.uniform(0.5, 2.0), min=0.1, max=5.0)
        self.SetFloat(ID_EDIT_PUFF,
                      rng.uniform(0.3, 1.2), min=0.1, max=1.5)
        self.SetInt32(ID_EDIT_BLOBS,    rng.randint(12, 80))
        self.SetFloat(ID_EDIT_HULL,
                      rng.uniform(40.0, 90.0), min=1.0, max=100.0)
        self.SetFloat(ID_EDIT_SCATTER,
                      rng.uniform(0.5, 2.5), min=0.1, max=4.0)
        self.SetFloat(ID_EDIT_VARIANCE,
                      rng.uniform(0.1, 0.8), min=0.0, max=1.0)

        # Цвет с лёгкой вариацией
        wb = rng.uniform(0.88, 1.00)
        self.SetColorField(ID_COLOR_MAIN, c4d.Vector(wb, wb, min(wb + 0.03, 1.0)))
        sd = rng.uniform(0.45, 0.75)
        self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(sd, sd + 0.05, sd + 0.12))

        self.SetFloat(ID_EDIT_LUMI,  rng.uniform(5.0, 35.0),  min=0.0, max=100.0)
        self.SetFloat(ID_EDIT_TRANSP, rng.uniform(0.0, 15.0), min=0.0, max=100.0)

        self.SetString(ID_LBL_STATUS,
                       "Случайный seed: {}".format(new_seed))

    def _collect_params(self):
        """Собирает все параметры из диалога в словарь."""
        return dict(
            name         = self.GetString(ID_EDIT_NAME)   or "Cloud",
            seed         = self.GetInt32(ID_EDIT_SEED),
            cloud_type   = self.GetInt32(ID_COMBO_TYPE),
            scale        = self.GetFloat(ID_EDIT_SCALE),
            sx           = self.GetFloat(ID_EDIT_SCALE_X),
            sy           = self.GetFloat(ID_EDIT_SCALE_Y),
            sz           = self.GetFloat(ID_EDIT_SCALE_Z),
            puff         = self.GetFloat(ID_EDIT_PUFF),
            blobs        = self.GetInt32(ID_EDIT_BLOBS),
            hull         = self.GetFloat(ID_EDIT_HULL),
            scatter      = self.GetFloat(ID_EDIT_SCATTER),
            variance     = self.GetFloat(ID_EDIT_VARIANCE),
            color_main   = self.GetColorField(ID_COLOR_MAIN)["color"],
            color_shadow = self.GetColorField(ID_COLOR_SHADOW)["color"],
            luminance    = self.GetFloat(ID_EDIT_LUMI),
            transparency = self.GetFloat(ID_EDIT_TRANSP),
            use_noise    = self.GetBool(ID_CHK_NOISE),
            use_sss      = self.GetBool(ID_CHK_SSS),
            pos_x        = self.GetFloat(ID_EDIT_POS_X),
            pos_y        = self.GetFloat(ID_EDIT_POS_Y),
            pos_z        = self.GetFloat(ID_EDIT_POS_Z),
            add_sky      = self.GetBool(ID_CHK_SKY),
            add_sun      = self.GetBool(ID_CHK_HDRI_SUN),
        )

    def _generate(self):
        """Читает параметры и вызывает генератор облака."""
        try:
            params = self._collect_params()
        except Exception as e:
            self.SetString(ID_LBL_STATUS, "Ошибка чтения параметров: {}".format(e))
            return

        self.SetString(ID_LBL_STATUS, "Генерация...")
        self.Enable(ID_BTN_GENERATE, False)

        try:
            ok, msg = _generate_cloud(params)
            self._cloud_count += 1 if ok else 0

            # Автоинкремент имени для следующего облака
            if ok:
                current_name = params["name"]
                # Ищем суффикс вида _NNN
                import re
                m = re.match(r"^(.*?)(\d+)$", current_name)
                if m:
                    prefix  = m.group(1)
                    num     = int(m.group(2)) + 1
                    new_name = "{}{}".format(prefix, str(num).zfill(len(m.group(2))))
                else:
                    new_name = current_name + "_002"
                self.SetString(ID_EDIT_NAME, new_name)

                # Немного сдвигаем позицию, чтобы следующее облако не совпадало
                cur_x = self.GetFloat(ID_EDIT_POS_X)
                self.SetFloat(ID_EDIT_POS_X,
                              cur_x + params["scale"] * 0.6,
                              min=-100000.0, max=100000.0)

            self.SetString(ID_LBL_STATUS, msg)

        except Exception as e:
            self.SetString(ID_LBL_STATUS, "Ошибка генерации: {}".format(e))
        finally:
            self.Enable(ID_BTN_GENERATE, True)


# ─── CommandData ──────────────────────────────────────────────────────────────

class CloudWizardCommand(c4d.plugins.CommandData):

    def __init__(self):
        super(CloudWizardCommand, self).__init__()
        self._dialog = None

    def Execute(self, doc):
        if self._dialog is None:
            self._dialog = CloudWizardDialog(self)
        if self._dialog.IsOpen():
            self._dialog.Close()
        else:
            self._dialog.Open(
                dlgtype  = c4d.DLG_TYPE_ASYNC,
                pluginid = PLUGIN_ID,
                defaultw = 460,
                defaulth = 620,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dialog is None:
            self._dialog = CloudWizardDialog(self)
        return self._dialog.Restore(PLUGIN_ID, secret)

    def GetState(self, doc):
        return c4d.CMD_ENABLED


# ─── Регистрация ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    icon = _make_icon()
    c4d.plugins.RegisterCommandPlugin(
        id   = PLUGIN_ID,
        str  = PLUGIN_NAME_V,
        info = 0,
        icon = icon,
        help = PLUGIN_HELP,
        dat  = CloudWizardCommand(),
    )
