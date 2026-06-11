# -*- coding: utf-8 -*-
import c4d
from c4d import gui

# ─── НАСТРОЙКА ───────────────────────────────────────────────────────────────

# Структура меню:

MENU_NAME = "VAr Tools"

MENU_ITEMS = [
    1068825,    # Object Renamer Pro
    1068834,    # Camera Resolution 

    None,
    {"name": "Tools", "items": [
        {"name": "Axis", "items": [
            1068828,   # Axis2Center
            1068829,   # Axis2Bottom
            1068830,   # Axis Drop
        ]},

        {"name": "Location", "items": [
            1068826,   # Drop2Floor
            1068827,   # Drop2Floor 0(XZ)
            1068838,   # Center2Parent XZ
            1068839,   # Center2World XZ
        ]},

        {"name": "Clean", "items": [
            1068831,   # Clean Nulls
            1068832,   # Clean Empty Nulls
        ]},
    ]},

    {"name": "Objects", "items": [
        {"name": "Primitivs", "items": [
            1068871,    # TriCube
            1068872,    # HexSphere
            1068873,    # DiamondCylinder
            1068874,    # TriTorus
            1068875,    # BrickPlane
            1068899,    # MolecularHexLattice 
        ]},

        {"name": "XPressos objects", "items": [
            1068852,    # HierarchyFilter
        ]},       
        

    ]},

    {"name": "Tegs", "items": [
        1068900,    # ChildSelector
        1068859,    # TargetCamera
        1068903,    # CameraVisibility
    ]},

    {"name": "Deformers", "items": [
        1068837,    # PolySubdivider
    ]},

    None,
    1068833,    # AboutVArTools
]

# ─── КОД ─────────────────────────────────────────────────────────────────────

_PLUGINS_SUBTITLES = ("IDS_EDITOR_PLUGINS", "Extensions", "Расширения", "Plug-ins", "Plugins")

def _build_container(items):
    """Рекурсивно строит BaseContainer из списка items."""
    container = c4d.BaseContainer()
    for item in items:
        if item is None:
            container.InsData(c4d.MENURESOURCE_SEPERATOR, True)
        elif isinstance(item, int):
            container.InsData(c4d.MENURESOURCE_COMMAND, "PLUGIN_CMD_{}".format(item))
        elif isinstance(item, dict):
            sub = _build_container(item["items"])
            sub.InsData(c4d.MENURESOURCE_SUBTITLE, item["name"])
            container.InsData(c4d.MENURESOURCE_SUBMENU, sub)
    return container

def EnhanceMainMenu():
    mainMenu = gui.GetMenuResource("M_EDITOR")
    if not mainMenu:
        return

    submenu = _build_container(MENU_ITEMS)
    submenu.InsData(c4d.MENURESOURCE_SUBTITLE, MENU_NAME)

    for key, val in mainMenu:
        if isinstance(val, c4d.BaseContainer):
            if val.GetString(c4d.MENURESOURCE_SUBTITLE) in _PLUGINS_SUBTITLES:
                val.InsData(c4d.MENURESOURCE_SUBMENU, submenu)
                return

    pluginsMenu = gui.SearchPluginMenuResource()
    if pluginsMenu:
        mainMenu.InsDataAfter(c4d.MENURESOURCE_STRING, submenu, pluginsMenu)
    else:
        mainMenu.InsData(c4d.MENURESOURCE_STRING, submenu)

def PluginMessage(id, data):
    if id == c4d.C4DPL_BUILDMENU:
        EnhanceMainMenu()
    return True
