# -*- coding: utf-8 -*-
import c4d # type: ignore
from c4d import gui # type: ignore

# ─── НАСТРОЙКА ───────────────────────────────────────────────────────────────

# Структура меню:

MENU_NAME = "AR"
MENU_ITEMS = [
    1069095,   # Менеджер экшонов
    1069096,   # Воспроизвести последний
    1069097,   # Лог событий
    None,
    1069098,   # Info
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
