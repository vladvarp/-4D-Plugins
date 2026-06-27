# coding: utf-8
"""
Python Info — Cinema 4D R26+
Plugin ID : 1069900
Отображает информацию о версии Python и установленных библиотеках.
"""

import c4d  # type: ignore
import sys
import os
import pkg_resources
import base64
import tempfile
import ctypes

PLUGIN_ID = 1069094
PLUGIN_NAME = "Python Info"
PLUGIN_HELP = "Информация о Python и установленных библиотеках"

ID_TAB_GROUP  = 1000
ID_TAB_INFO   = 1001
ID_TAB_C4D    = 1002
ID_TAB_STDLIB = 1003
ID_TAB_OTHER  = 1004
ID_TAB_PIP    = 1005
ID_TAB_PATHS  = 1006

ID_TXT_INFO   = 2001
ID_TXT_C4D    = 2002
ID_TXT_STDLIB = 2003
ID_TXT_OTHER  = 2004
ID_TXT_PIP    = 2005
ID_TXT_PATHS  = 2006


def _collect_data():
    data = {}

    # ── Python Info ──
    lines = []
    lines.append("Версия:        {}".format(sys.version.replace("\n", " ")))
    lines.append("Интерпретатор: {}".format(sys.executable))
    lines.append("Платформа:     {}".format(sys.platform))
    lines.append("Разрядность:   {}".format(sys.maxsize > 2**32 and "64-bit" or "32-bit"))
    lines.append("")
    lines.append("Builtin module names ({}):".format(len(sys.builtin_module_names)))
    lines.append("")
    builtins = sorted(sys.builtin_module_names, key=str.lower)
    for m in builtins:
        lines.append("  {}".format(m))
    data["info"] = "\n".join(lines)

    # ── Модули ──
    loaded = sorted(sys.modules.keys(), key=str.lower)
    c4d_mods = [m for m in loaded if m.startswith("c4d")]

    _stdlib_names = set()
    stdlib_dir = os.path.dirname(os.__file__)
    if os.path.isdir(stdlib_dir):
        for item in os.listdir(stdlib_dir):
            name = item.split(".")[0].split(os.sep)[0]
            _stdlib_names.add(name)

    stdlib_mods = []
    third_party = []
    other_mods = []
    for m in loaded:
        if m.startswith("c4d"):
            continue
        root = m.split(".")[0]
        if root in _stdlib_names:
            stdlib_mods.append(m)
        elif root in {p.project_name.lower().replace("-", "_").replace(" ", "_")
                      for p in pkg_resources.working_set}:
            third_party.append(m)
        else:
            other_mods.append(m)

    # ── c4d ──
    lines = []
    lines.append("Cinema 4D модули ({}):".format(len(c4d_mods)))
    lines.append("")
    for m in c4d_mods:
        lines.append("  {}".format(m))
    data["c4d"] = "\n".join(lines)

    # ── stdlib ──
    lines = []
    lines.append("Стандартная библиотека ({}):".format(len(stdlib_mods)))
    lines.append("")
    for m in stdlib_mods:
        lines.append("  {}".format(m))
    data["stdlib"] = "\n".join(lines)

    # ── other ──
    lines = []
    if third_party:
        lines.append("Сторонние пакеты ({}):".format(len(third_party)))
        lines.append("")
        for m in third_party:
            lines.append("  {}".format(m))
        lines.append("")
    lines.append("Прочие модули ({}):".format(len(other_mods)))
    lines.append("")
    for m in other_mods:
        lines.append("  {}".format(m))
    data["other"] = "\n".join(lines)

    # ── pip ──
    lines = []
    lines.append("Пакеты ({}):".format(len(list(pkg_resources.working_set))))
    lines.append("")
    try:
        for p in sorted(pkg_resources.working_set, key=lambda x: x.project_name.lower()):
            lines.append("  {} {}".format(p.project_name, p.version))
    except Exception as e:
        lines.append("  Ошибка: {}".format(e))
    data["pip"] = "\n".join(lines)

    # ── paths ──
    lines = []
    lines.append("sys.path ({}):".format(len(sys.path)))
    lines.append("")
    for i, p in enumerate(sys.path):
        lines.append("  {:>2}. {}".format(i + 1, p))
    data["paths"] = "\n".join(lines)

    return data


class PythonInfoDialog(c4d.gui.GeDialog):

    _data = None

    def CreateLayout(self):
        self.SetTitle(PLUGIN_NAME)

        self.TabGroupBegin(ID_TAB_GROUP, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT)

        # Tab 1: Info
        self.GroupBegin(ID_TAB_INFO, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, title="Python")
        self.AddMultiLineEditText(
            ID_TXT_INFO, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=0, inith=0,
            style=c4d.DR_MULTILINE_WORDWRAP | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()

        # Tab 2: c4d
        self.GroupBegin(ID_TAB_C4D, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, title="Cinema 4D")
        self.AddMultiLineEditText(
            ID_TXT_C4D, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=0, inith=0,
            style=c4d.DR_MULTILINE_WORDWRAP | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()

        # Tab 3: stdlib
        self.GroupBegin(ID_TAB_STDLIB, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, title="Стандартная библиотека")
        self.AddMultiLineEditText(
            ID_TXT_STDLIB, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=0, inith=0,
            style=c4d.DR_MULTILINE_WORDWRAP | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()

        # Tab 4: other
        self.GroupBegin(ID_TAB_OTHER, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, title="Сторонние / Прочие")
        self.AddMultiLineEditText(
            ID_TXT_OTHER, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=0, inith=0,
            style=c4d.DR_MULTILINE_WORDWRAP | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()

        # Tab 5: pip
        self.GroupBegin(ID_TAB_PIP, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, title="pip пакеты")
        self.AddMultiLineEditText(
            ID_TXT_PIP, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=0, inith=0,
            style=c4d.DR_MULTILINE_WORDWRAP | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()

        # Tab 6: paths
        self.GroupBegin(ID_TAB_PATHS, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, title="sys.path")
        self.AddMultiLineEditText(
            ID_TXT_PATHS, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=0, inith=0,
            style=c4d.DR_MULTILINE_WORDWRAP | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()

        self.GroupEnd()
        return True

    def InitValues(self):
        if self._data is None:
            self._data = _collect_data()
        self.SetString(ID_TXT_INFO,   self._data["info"])
        self.SetString(ID_TXT_C4D,    self._data["c4d"])
        self.SetString(ID_TXT_STDLIB, self._data["stdlib"])
        self.SetString(ID_TXT_OTHER,  self._data["other"])
        self.SetString(ID_TXT_PIP,    self._data["pip"])
        self.SetString(ID_TXT_PATHS,  self._data["paths"])
        return True


class PythonInfoCommand(c4d.plugins.CommandData):

    _dialog = None

    def Execute(self, doc):
        if self._dialog is None:
            self._dialog = PythonInfoDialog()
        if self._dialog.IsOpen():
            self._dialog.Close()
        else:
            self._dialog.Open(
                dlgtype=c4d.DLG_TYPE_ASYNC,
                pluginid=PLUGIN_ID,
                defaultw=800,
                defaulth=700,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dialog is None:
            self._dialog = PythonInfoDialog()
        return self._dialog.Restore(PLUGIN_ID, secret)

    def GetState(self, doc):
        return c4d.CMD_ENABLED


# ─── Встроенная иконка (base64 PNG 32×32) ────────────────────────────────────
_ICON_B64 = (
    "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"
)


def _make_icon():
    """Декодирует встроенный base64 PNG во временный файл и возвращает BaseBitmap."""
    bmp = c4d.bitmaps.BaseBitmap()
    try:
        data = base64.b64decode(_ICON_B64.replace(" ", ""))
        fd, tmp = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, data)
            os.close(fd)
            bmp.InitWith(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return None
    return bmp


ICON = _make_icon()

if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str=PLUGIN_NAME,
        info=0,
        icon=ICON,
        help=PLUGIN_HELP,
        dat=PythonInfoCommand(),
    )
