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
import random
import base64
import tempfile

_NOISE_BUYA            = getattr(c4d, 'SLA_NOISE_NOISE_BUYA',            0)
_NOISE_TURBULENCE      = getattr(c4d, 'SLA_NOISE_NOISE_TURBULENCE',      1)
_NOISE_WAVY_TURBULENCE = getattr(c4d, 'SLA_NOISE_NOISE_WAVY_TURBULENCE', 2)
_NOISE_DENTS           = getattr(c4d, 'SLA_NOISE_NOISE_DENTS',           3)

# ─── ID ───────────────────────────────────────────────────────────────────────
PLUGIN_ID     = 1069028
PLUGIN_NAME   = "Cloud Wizard"
PLUGIN_NAME_V = "Cloud Wizard v1.8.2"
PLUGIN_HELP   = "Процедурная генерация облаков в сцене"

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
ID_CHK_CREATE_MAT   = ID_BASE + 108  # Создавать материал

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
ID_BTN_RAND_MAT     = ID_BASE + 107
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

    # ── Создаём Metaball ──────────────────────────────────────────────────────
    meta = c4d.BaseObject(c4d.Ometaball)
    meta.SetName(params["name"])

    pos = c4d.Vector(params["pos_x"], params["pos_y"], params["pos_z"])
    meta.SetAbsPos(pos)

    # Порог (Hull Value) — чем меньше, тем мягче поверхность
    hull_c4d = max(1.0, min(100.0, float(hull_val)))
    meta[c4d.METABALLOBJECT_THRESHOLD] = hull_c4d / 100.0

    # Точность (Subdivision)
    # Перистые и слоистые делаем грубее (быстрее), грозовые — детальнее
    subdiv_map = {0: 8, 1: 12, 2: 6, 3: 14, 4: 9}
    meta[c4d.METABALLOBJECT_SUBEDITOR] = subdiv_map.get(cloud_type, 8)
    meta[c4d.METABALLOBJECT_SUBRAY]    = max(4, subdiv_map.get(cloud_type, 8) - 2)

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

    # ── Создаём материал (опционально) ──────────────────────────────────────────
    if params.get("create_mat"):
        mat = _create_cloud_material(params, rng)
        doc.InsertMaterial(mat)

        # ── Применяем материал к метаболе ────────────────────────────────────
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
            try:
                sun[c4d.LIGHT_TYPE]       = c4d.LIGHT_TYPE_DISTANT
            except Exception:
                pass
            try:
                sun[c4d.LIGHT_COLOR]      = c4d.Vector(1.0, 0.97, 0.88)
            except Exception:
                pass
            try:
                sun[c4d.LIGHT_INTENSITY]  = 1.5
            except Exception:
                try:
                    sun[c4d.LIGHT_BRIGHTNESS] = 1.5
                except Exception:
                    pass
            try:
                sun[c4d.LIGHT_SHADOWTYPE] = c4d.LIGHT_SHADOWTYPE_AREA
            except Exception:
                pass
            # Угол солнца ~45°
            sun.SetRelRot(c4d.Vector(
                c4d.utils.DegToRad(-45.0),
                c4d.utils.DegToRad(35.0),
                0.0
            ))
            doc.InsertObject(sun)

    # ── Вставляем метаболу в документ ──────────────────────────────────────────
    doc.InsertObject(meta)
    doc.SetActiveObject(meta)
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
        try:
            noise_shader[c4d.SLA_NOISE_NOISE]     = _NOISE_BUYA
            noise_shader[c4d.SLA_NOISE_OCTAVES]   = 5
            noise_shader[c4d.SLA_NOISE_SCALE]     = 45.0
            noise_shader[c4d.SLA_NOISE_GLOBAL_SCALE] = 250.0
        except Exception:
            pass
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
        try:
            diff_noise[c4d.SLA_NOISE_NOISE]   = _NOISE_TURBULENCE
            diff_noise[c4d.SLA_NOISE_OCTAVES] = 4
            diff_noise[c4d.SLA_NOISE_SCALE]   = 60.0
            diff_noise[c4d.SLA_NOISE_GLOBAL_SCALE] = 180.0
        except Exception:
            pass
        mat[c4d.MATERIAL_DIFFUSION_SHADER] = diff_noise
        mat.InsertShader(diff_noise)

    # ── Шум на Bump для детализации поверхности ────────────────────────────────
    if params.get("use_noise"):
        mat[c4d.MATERIAL_USE_BUMP] = True
        bump_noise = c4d.BaseShader(c4d.Xnoise)
        bump_type_map = {0: _NOISE_TURBULENCE,
                         1: _NOISE_BUYA,
                         2: _NOISE_TURBULENCE,
                         3: _NOISE_WAVY_TURBULENCE,
                         4: _NOISE_DENTS}
        try:
            bump_noise[c4d.SLA_NOISE_NOISE]   = bump_type_map.get(cloud_type,
                                                    _NOISE_TURBULENCE)
            bump_noise[c4d.SLA_NOISE_OCTAVES] = 6
            bump_noise[c4d.SLA_NOISE_SCALE]   = 35.0
            bump_noise[c4d.SLA_NOISE_GLOBAL_SCALE] = 120.0
        except Exception:
            pass
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
    """Удаляет все метаболы, созданные Cloud Wizard."""
    removed = 0

    def _walk(obj):
        nonlocal removed
        to_delete = []
        while obj:
            nxt = obj.GetNext()
            if obj.GetType() == c4d.Ometaball:
                to_delete.append(obj)
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
        self.AddStaticText(ID_LBL_TYPE, c4d.BFH_LEFT, initw=100, name="Тип облака:")
        self.AddComboBox(ID_COMBO_TYPE, c4d.BFH_SCALEFIT, initw=200)
        for i, name in enumerate(CLOUD_TYPES):
            self.AddChild(ID_COMBO_TYPE, i, name)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Основные параметры ───────────────────────────────────────────────
        self.GroupBegin(ID_GRP_GENERAL, c4d.BFH_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(8, 4, 8, 2)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, name="Основные параметры:")
        self.GroupEnd()

        self.GroupBegin(ID_GRP_GENERAL, c4d.BFH_SCALEFIT, cols=4, rows=1)
        self.GroupBorderSpace(8, 4, 8, 2)
        self.AddStaticText(ID_LBL_NAME, c4d.BFH_LEFT, initw=90, name="Имя:")
        self.AddEditText(ID_EDIT_NAME, c4d.BFH_SCALEFIT, initw=150)
        self.AddStaticText(ID_LBL_SEED, c4d.BFH_LEFT, initw=60, name="Зерно:")
        self.AddEditNumberArrows(ID_EDIT_SEED, c4d.BFH_LEFT, initw=120)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Форма ────────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, name="Форма:")
        self.GroupEnd()

        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_SCALE, c4d.BFH_LEFT, initw=120, name="Масштаб:")
        self.AddEditNumberArrows(ID_EDIT_SCALE, c4d.BFH_LEFT, initw=120)
        self.AddStaticText(ID_LBL_PUFF, c4d.BFH_LEFT, initw=120, name="Пышность:")
        self.AddEditSlider(ID_EDIT_PUFF, c4d.BFH_SCALEFIT, initw=120)

        self.AddStaticText(ID_LBL_SCALE_X, c4d.BFH_LEFT, initw=120, name="Ширина (X):")
        self.AddEditSlider(ID_EDIT_SCALE_X, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(ID_LBL_SCALE_Y, c4d.BFH_LEFT, initw=120, name="Высота (Y):")
        self.AddEditSlider(ID_EDIT_SCALE_Y, c4d.BFH_SCALEFIT, initw=120)

        self.AddStaticText(ID_LBL_SCALE_Z, c4d.BFH_LEFT, initw=120, name="Глубина (Z):")
        self.AddEditSlider(ID_EDIT_SCALE_Z, c4d.BFH_SCALEFIT, initw=120)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Детали ───────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_DETAIL, c4d.BFH_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_SCALEFIT, name="Детализация метаболы:")
        self.GroupEnd()

        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_BLOBS, c4d.BFH_LEFT, initw=120, name="Шариков:")
        self.AddEditNumberArrows(ID_EDIT_BLOBS, c4d.BFH_LEFT, initw=120)
        self.AddStaticText(ID_LBL_HULL, c4d.BFH_LEFT, initw=120, name="Hull (%):")
        self.AddEditSlider(ID_EDIT_HULL, c4d.BFH_SCALEFIT, initw=120)

        self.AddStaticText(ID_LBL_SCATTER, c4d.BFH_LEFT, initw=120, name="Разброс:")
        self.AddEditSlider(ID_EDIT_SCATTER, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(ID_LBL_VARIANCE, c4d.BFH_LEFT, initw=120, name="Вариация:")
        self.AddEditSlider(ID_EDIT_VARIANCE, c4d.BFH_SCALEFIT, initw=120)
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Материал ─────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_MAT, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFH_LEFT, initw=160, name="Материал:")
        self.AddCheckbox(ID_CHK_CREATE_MAT, c4d.BFH_LEFT, initw=0, inith=0, name="Создавать материал")
        self.GroupEnd()

        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=4, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_COLOR_MAIN, c4d.BFH_LEFT, initw=160, name="Основной цвет:")
        self.AddColorField(ID_COLOR_MAIN, c4d.BFH_LEFT, initw=120, inith=14)
        self.AddStaticText(ID_LBL_COLOR_SHADOW, c4d.BFH_LEFT, initw=100, name="Цвет тени:")
        self.AddColorField(ID_COLOR_SHADOW, c4d.BFH_LEFT, initw=120, inith=14)
        self.GroupEnd()

        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=3, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_COLOR_MAIN, c4d.BFH_LEFT, initw=160, name="")
        self.AddCheckbox(ID_CHK_NOISE, c4d.BFH_LEFT, initw=120, inith=0, name="Noise")
        self.AddCheckbox(ID_CHK_SSS,   c4d.BFH_LEFT, initw=0, inith=0, name="Luminance")
        self.GroupEnd()

        self.GroupBegin(ID_GRP_SHAPE, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_LUMI, c4d.BFH_LEFT, initw=160, name="Светимость (%):")
        self.AddEditSlider(ID_EDIT_LUMI, c4d.BFH_SCALEFIT, initw=120)
        self.AddStaticText(ID_LBL_TRANSP, c4d.BFH_LEFT, initw=160, name="Прозрачность (%):")
        self.AddEditSlider(ID_EDIT_TRANSP, c4d.BFH_SCALEFIT, initw=120)
        self.GroupEnd()





        self.AddSeparatorH(0)

        # ── Позиция ──────────────────────────────────────────────────────────
        self.GroupBegin(ID_GRP_POS, c4d.BFH_SCALEFIT, cols=6, rows=1)
        self.GroupBorderSpace(8, 4, 8, 4)
        self.AddStaticText(ID_LBL_POS_X, c4d.BFH_LEFT, initw=26, name="X:")
        self.AddEditNumberArrows(ID_EDIT_POS_X, c4d.BFH_SCALEFIT, initw=70)
        self.AddStaticText(ID_LBL_POS_Y, c4d.BFH_LEFT, initw=26, name="Y:")
        self.AddEditNumberArrows(ID_EDIT_POS_Y, c4d.BFH_SCALEFIT, initw=70)
        self.AddStaticText(ID_LBL_POS_Z, c4d.BFH_LEFT, initw=26, name="Z:")
        self.AddEditNumberArrows(ID_EDIT_POS_Z, c4d.BFH_SCALEFIT, initw=70)
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
        self.GroupBegin(ID_GRP_BOTTOM, c4d.BFH_SCALEFIT, cols=2, rows=2)
        self.GroupBorderSpace(8, 4, 8, 6)

        self.AddButton(ID_BTN_GENERATE,  c4d.BFH_SCALEFIT, inith=20, name="⛅ Создать облако")
        self.AddButton(ID_BTN_CLEAR,     c4d.BFH_SCALEFIT, inith=20, name="⛔ Удалить все облака")
        self.AddButton(ID_BTN_RANDOMIZE, c4d.BFH_SCALEFIT, inith=20, name="⇄ Случайные формы")
        self.AddButton(ID_BTN_RAND_MAT,  c4d.BFH_SCALEFIT, inith=20, name="⇄ Случайный материал")
        self.GroupEnd()

        self.GroupBegin(ID_GRP_BOTTOM, c4d.BFH_SCALEFIT, cols=1, rows=2)
        self.GroupBorderSpace(8, 4, 8, 6)
        self.AddStaticText(ID_LBL_STATUS, c4d.BFH_SCALEFIT | c4d.BFH_CENTER, name="Готов к работе")
        self.GroupEnd()

        return True

    # ── InitValues ───────────────────────────────────────────────────────────

    def InitValues(self):
        # Тип — кучевые по умолчанию
        self.SetInt32(ID_COMBO_TYPE, 0)

        # Имя
        self.SetString(ID_EDIT_NAME, "Cloud_001")

        # Seed
        self.SetInt32(ID_EDIT_SEED, 515627, min=0, max=9999999)

        # Масштаб
        self.SetFloat(ID_EDIT_SCALE, 836.8843, min=10.0, max=50000.0, step=1.0,
                      format=c4d.FORMAT_METER)

        # Форма
        self.SetFloat(ID_EDIT_PUFF,       0.55, min=0.1, max=1.5, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_X,  2.3287, min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_Y,    0.65, min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_Z,  1.0142, min=0.1, max=5.0, step=0.05)


        # Детали
        self.SetInt32(ID_EDIT_BLOBS,         34, min=4,   max=200)
        self.SetFloat(ID_EDIT_HULL,          72, min=1.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_SCATTER,        1, min=0.1, max=4.0,   step=0.05)
        self.SetFloat(ID_EDIT_VARIANCE,  0.6316, min=0.0, max=1.0,   step=0.05)

        # Материал
        self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.97, 0.97, 1.00), 1.0, 1.0, 0)
        self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.60, 0.67, 0.78), 1.0, 1.0, 0)
        self.SetFloat(ID_EDIT_LUMI,   18.0, min=0.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_TRANSP,  0.0, min=0.0, max=100.0, step=1.0)
        self.SetBool(ID_CHK_NOISE, False)
        self.SetBool(ID_CHK_SSS,   False)
        self.SetBool(ID_CHK_CREATE_MAT, False)

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
            self._randomize_shape()
            return True

        if widget_id == ID_BTN_RAND_MAT:
            self._randomize_material()
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
        self.SetFloat(ID_EDIT_HULL,    float(p["hull"]),    min=1.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_SCATTER, p["scatter"],        min=0.1, max=4.0,   step=0.05)
        self.SetFloat(ID_EDIT_PUFF,    p["puff"],           min=0.1, max=1.5,   step=0.05)

        # Высота по профилю
        current_sy = p["sy"]
        self.SetFloat(ID_EDIT_SCALE_Y, min(4.9, max(0.1, current_sy)),
                      min=0.1, max=5.0, step=0.05)

        # Особые цветовые настройки для типов
        if cloud_type == 1:   # Перистые — более прозрачные, холоднее
            self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.94, 0.96, 1.00), 1.0, 1.0, 0)
            self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.70, 0.78, 0.90), 1.0, 1.0, 0)
            self.SetFloat(ID_EDIT_TRANSP, 35.0, min=0.0, max=100.0, step=1.0)
        elif cloud_type == 2:  # Грозовые — темнее
            self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.82, 0.84, 0.88), 1.0, 1.0, 0)
            self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.28, 0.30, 0.36), 1.0, 1.0, 0)
            self.SetFloat(ID_EDIT_TRANSP, 0.0, min=0.0, max=100.0, step=1.0)
        else:
            self.SetColorField(ID_COLOR_MAIN,   c4d.Vector(0.97, 0.97, 1.00), 1.0, 1.0, 0)
            self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(0.60, 0.67, 0.78), 1.0, 1.0, 0)
            self.SetFloat(ID_EDIT_TRANSP, 0.0, min=0.0, max=100.0, step=1.0)

    def _randomize_shape(self):
        """Случайная генерация параметров формы."""
        import time
        rng = random.Random(int(time.time() * 1000) % 9999999)

        new_seed = rng.randint(0, 9999999)
        self.SetInt32(ID_EDIT_SEED, new_seed)
        self.SetFloat(ID_EDIT_SCALE,
                      rng.uniform(200.0, 1200.0), min=10.0, max=50000.0, step=10.0)
        self.SetFloat(ID_EDIT_SCALE_X,
                      rng.uniform(0.5, 3.0), min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_Y,
                      rng.uniform(0.3, 1.5), min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_SCALE_Z,
                      rng.uniform(0.5, 2.0), min=0.1, max=5.0, step=0.05)
        self.SetFloat(ID_EDIT_PUFF,
                      rng.uniform(0.3, 1.2), min=0.1, max=1.5, step=0.05)
        self.SetInt32(ID_EDIT_BLOBS,    rng.randint(12, 80))
        self.SetFloat(ID_EDIT_HULL,
                      rng.uniform(40.0, 90.0), min=1.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_SCATTER,
                      rng.uniform(0.5, 2.5), min=0.1, max=4.0, step=0.05)
        self.SetFloat(ID_EDIT_VARIANCE,
                      rng.uniform(0.1, 0.8), min=0.0, max=1.0, step=0.05)

        self.SetString(ID_LBL_STATUS,
                       "Случайный seed: {}".format(new_seed))

    def _randomize_material(self):
        """Случайная генерация параметров материала."""
        import time
        rng = random.Random(int(time.time() * 1000) % 9999999)

        wb = rng.uniform(0.88, 1.00)
        self.SetColorField(ID_COLOR_MAIN, c4d.Vector(wb, wb, min(wb + 0.03, 1.0)), 1.0, 1.0, 0)
        sd = rng.uniform(0.45, 0.75)
        self.SetColorField(ID_COLOR_SHADOW, c4d.Vector(sd, sd + 0.05, sd + 0.12), 1.0, 1.0, 0)

        self.SetFloat(ID_EDIT_LUMI,  rng.uniform(5.0, 35.0),  min=0.0, max=100.0, step=1.0)
        self.SetFloat(ID_EDIT_TRANSP, rng.uniform(0.0, 15.0), min=0.0, max=100.0, step=1.0)

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
            create_mat   = self.GetBool(ID_CHK_CREATE_MAT),
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
