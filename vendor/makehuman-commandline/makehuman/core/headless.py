#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Séverin Lemaignan, Jonas Hauquier

**Copyright(c):**      MakeHuman Team 2001-2014

**Licensing:**         AGPL3 (http://www.makehuman.org/doc/node/the_makehuman_application.html)

    This file is part of MakeHuman (www.makehuman.org).

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

**Coding Standards:**  See http://www.makehuman.org/node/165

Abstract
--------

Implements the command-line version of MakeHuman.
"""

import os
import sys

from core import G
import guicommon
import log
from human import Human
import files3d
import getpath
import humanmodifier
import material
import proxy

sys.path.append("./plugins")

def _load_from_plugin(plugin_name, name):
    return getattr((__import__(plugin_name, fromlist = [name])), name)


class ConsoleApp():
    def __init__(self):
        self.selectedHuman = Human(files3d.loadMesh(getpath.getSysDataPath("3dobjs/base.obj"), maxFaces = 5))
        self.log_window = None
        self.splash = None
        self.statusBar = None

    def progress(self, *args, **kwargs):
        pass

def run(args):
    G.app = ConsoleApp()
    human = G.app.selectedHuman

    import humanargparser
    humanargparser.applyModelingArguments(human, args)


    if args["output"]:
        save(human, args["output"])


    # A little debug test
    if 'PyOpenGL' in sys.modules.keys():
        log.warning("Debug test detected that OpenGL libraries were imported in the console version! This indicates bad separation from GUI.")
    if 'PyQt4' in sys.modules.keys():
        log.warning("Debug test detected that Qt libraries were imported in the console version! This indicates bad separation from GUI (unless PIL is not installed, in which case PyQt is still used as image back-end).")

def save(human, filepath):
    if not os.path.splitext(filepath)[1]:
        raise RuntimeError("Specify a file extension for the output file to determine the export format to use.")

    # TODO allow specifying custom exporter options on commandline
    if filepath.lower().endswith(".obj"):
        OBJExporter = _load_from_plugin("9_export_obj", "mh2obj")
        ObjConfig = _load_from_plugin("9_export_obj", "ObjConfig")

        exportCfg = ObjConfig()
        exportCfg.setHuman(human)
        OBJExporter.exportObj(filepath, config=exportCfg)
    elif filepath.lower().endswith(".dae"):
        DAEExporter = _load_from_plugin("9_export_collada", "mh2collada")
        DAEConfig = _load_from_plugin("9_export_collada", "DaeConfig")

        exportCfg = DAEConfig()
        exportCfg.setHuman(human)
        DAEExporter.exportCollada(filepath, config=exportCfg)
    elif filepath.lower().endswith(".fbx"):
        FBXExporter = _load_from_plugin("9_export_fbx", "mh2fbx")
        FBXConfig = _load_from_plugin("9_export_fbx", "FbxConfig")

        exportCfg = FBXConfig()
        exportCfg.setHuman(human)
        FBXExporter.exportFbx(filepath, config=exportCfg)
    elif filepath.lower().endswith(".mesh.xml"):
        OgreExporter = _load_from_plugin("9_export_ogre", "mh2ogre")
        OgreConfig = _load_from_plugin("9_export_ogre", "OgreConfig")

        exportCfg = OgreConfig()
        exportCfg.setHuman(human)
        OgreExporter.exportOgreMesh(filepath, config=exportCfg)
    else:
        raise RuntimeError("No export available for %s files." % os.path.splitext(filepath)[1])

