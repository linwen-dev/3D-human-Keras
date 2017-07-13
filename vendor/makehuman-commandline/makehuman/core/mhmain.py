#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Glynn Clements, Jonas Hauquier

**Copyright(c):**      MakeHuman Team 2001-2015

**Licensing:**         AGPL3

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

Main application GUI component.
"""

import sys
import os
import glob
import imp

from core import G
import mh
from progress import Progress
import files3d
import gui3d
import geometry3d
import animation3d
import events3d
import human
import skeleton
import guifiles
import managed_file
import algos3d
import gui
import language
import log
import contextlib

@contextlib.contextmanager
def outFile(path):
    from codecs import open
    path = mh.getPath(path)
    tmppath = path + '.tmp'
    try:
        with open(tmppath, 'w', encoding="utf-8") as f:
            yield f
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmppath, path)
    except:
        if os.path.exists(tmppath):
            os.remove(tmppath)
        log.error('unable to save file %s', path, exc_info=True)

@contextlib.contextmanager
def inFile(path):
    from codecs import open
    try:
        path = mh.getPath(path)
        if not os.path.isfile(path):
            yield []
            return
        with open(path, 'rU', encoding="utf-8") as f:
            yield f
    except:
        log.error('Failed to load file %s', path, exc_info=True)

class PluginCheckBox(gui.CheckBox):

    def __init__(self, module):

        super(PluginCheckBox, self).__init__(module, module not in gui3d.app.getSetting('excludePlugins'))
        self.module = module

    def onClicked(self, event):
        if self.selected:
            excludes = gui3d.app.getSetting('excludePlugins')
            excludes.remove(self.module)
            gui3d.app.setSetting('excludePlugins', excludes)
        else:
            excludes = gui3d.app.getSetting('excludePlugins')
            excludes.append(self.module)
            gui3d.app.setSetting('excludePlugins', excludes)

        gui3d.app.saveSettings()

class PluginsTaskView(gui3d.TaskView):

    def __init__(self, category):
        gui3d.TaskView.__init__(self, category, 'Plugins')

        self.scroll = self.addTopWidget(gui.VScrollArea())
        self.pluginsBox = gui.GroupBox('Plugins')
        self.pluginsBox.setSizePolicy(
            gui.SizePolicy.MinimumExpanding,
            gui.SizePolicy.MinimumExpanding)
        self.scroll.setWidget(self.pluginsBox)

        for module in sorted(gui3d.app.modules):
            self.pluginsBox.addWidget(PluginCheckBox(module))

class SymmetryAction(gui3d.Action):
    def __init__(self, human, direction):
        super(SymmetryAction, self).__init__('Apply symmetry %s' % ("left" if direction == 'l' else "right"))
        self.human = human
        self.direction = direction
        self.before = [(m.fullName, m.getValue()) for m in human.modifiers]

    def do(self):
        if self.direction == 'r':
            self.human.applySymmetryRight()
        else:
            self.human.applySymmetryLeft()
        self.human.applyAllTargets()
        mh.redraw()
        return True

    def undo(self):
        for (modifierName, value) in self.before:
            self.human.getModifier(modifierName).setValue(value)
        self.human.applyAllTargets()
        mh.redraw()
        return True


class MHApplication(gui3d.Application, mh.Application):
    def __init__(self):
        if G.app is not None:
            raise RuntimeError('MHApplication is a singleton')
        G.app = self
        gui3d.Application.__init__(self)
        mh.Application.__init__(self)

        self.shortcuts = {
            # Actions
            'undo':         (mh.Modifiers.CTRL, mh.Keys.z),
            'redo':         (mh.Modifiers.CTRL, mh.Keys.y),
            'modelling':    (mh.Modifiers.CTRL, mh.Keys.m),
            'save':         (mh.Modifiers.CTRL, mh.Keys.s),
            'load':         (mh.Modifiers.CTRL, mh.Keys.l),
            'export':       (mh.Modifiers.CTRL, mh.Keys.e),
            'rendering':    (mh.Modifiers.CTRL, mh.Keys.r),
            'help':         (mh.Modifiers.CTRL, mh.Keys.h),
            'exit':         (mh.Modifiers.CTRL, mh.Keys.q),
            'stereo':       (mh.Modifiers.CTRL, mh.Keys.w),
            'wireframe':    (mh.Modifiers.CTRL, mh.Keys.f),
            'savetgt':      (mh.Modifiers.ALT, mh.Keys.t),
            'qexport':      (mh.Modifiers.ALT, mh.Keys.e),
            'smooth':       (mh.Modifiers.ALT, mh.Keys.s),
            'grab':         (mh.Modifiers.ALT, mh.Keys.g),
            'profiling':    (mh.Modifiers.ALT, mh.Keys.p),
            # Camera navigation
            'rotateD':      (0, mh.Keys.N2),
            'rotateL':      (0, mh.Keys.N4),
            'rotateR':      (0, mh.Keys.N6),
            'rotateU':      (0, mh.Keys.N8),
            'panU':         (0, mh.Keys.UP),
            'panD':         (0, mh.Keys.DOWN),
            'panR':         (0, mh.Keys.RIGHT),
            'panL':         (0, mh.Keys.LEFT),
            'zoomIn':       (0, mh.Keys.PLUS),
            'zoomOut':      (0, mh.Keys.MINUS),
            'front':        (0, mh.Keys.N1),
            'right':        (0, mh.Keys.N3),
            'top':          (0, mh.Keys.N7),
            'back':         (mh.Modifiers.CTRL, mh.Keys.N1),
            'left':         (mh.Modifiers.CTRL, mh.Keys.N3),
            'bottom':       (mh.Modifiers.CTRL, mh.Keys.N7),
            'resetCam':     (0, mh.Keys.PERIOD),
            # Version check
            '_versionSentinel': (0, 0x87654321)
        }

        self.mouseActions = {
            (0, mh.Buttons.LEFT_MASK): self.mouseRotate,
            (0, mh.Buttons.RIGHT_MASK): self.mouseZoom,
            (0, mh.Buttons.MIDDLE_MASK): self.mouseTranslate,
            (mh.Modifiers.CTRL, mh.Buttons.RIGHT_MASK): self.mouseFocus
        }

        self._undeclared_settings = dict()

        if mh.isRelease():
            self._default_settings = {
                'realtimeUpdates': True,
                'realtimeFitting': True,
                'sliderImages': True,
                'excludePlugins': [
                    "7_data",
                    "7_example",
                    "7_material_editor",
                    "7_profile",
                    "7_scene_editor",
                    "7_scripting",
                    "7_shell",
                    "7_targets",
                ],
                'rtl': False,
                'invertMouseWheel': False,
                'lowspeed': 1,
                'preloadTargets': True,
                'cameraAutoZoom': False,
                'language': 'english',
                'highspeed': 5,
                'realtimeNormalUpdates': False,
                'units': 'metric',
                'guiTheme': 'makehuman',
                'restoreWindowSize': True,
                'windowGeometry': ''
            }
        else:
            self._default_settings = {
                'realtimeUpdates': True,
                'realtimeFitting': True,
                'realtimeNormalUpdates': False,
                'cameraAutoZoom': False,
                'lowspeed': 1,
                'highspeed': 5,
                'units':'metric',
                'invertMouseWheel':False,
                'language':'english',
                'excludePlugins':[],
                'rtl': False,
                'sliderImages': True,
                'guiTheme': 'makehuman',
                'preloadTargets': False,
                'restoreWindowSize': True,
                'windowGeometry': ''
            }

        self._settings = dict(self._default_settings)

        self.loadHandlers = {}
        self.saveHandlers = []

        self.dialog = None
        self.helpIds = set()

        self.tool = None
        self.selectedGroup = None

        self.undoStack = []
        self.redoStack = []

        self.actions = None

        self.clearColor = [0.5, 0.5, 0.5]
        self.gridColor = [1.0, 1.0, 1.0]
        self.gridSubColor = [0.7, 0.7, 0.7]

        self.modules = {}

        self.selectedHuman = None
        self.currentFile = managed_file.File()
        self._scene = None
        self.backplaneGrid = None
        self.groundplaneGrid = None
        self.backgroundGradient = None

        self.theme = None

        @self.currentFile.mhEvent
        def onModified(event):
            self.updateFilenameCaption()

        #self.modelCamera = mh.Camera()
        #self.modelCamera.switchToOrtho()
        self.modelCamera = mh.OrbitalCamera()
        #self.modelCamera.debug = True

        @self.modelCamera.mhEvent
        def onChanged(event):
            self.callEventHandlers('onCameraChanged', event)

        mh.cameras.append(self.modelCamera)

        #self.guiCamera = mh.Camera()
        #self.guiCamera._fovAngle = 45
        #self.guiCamera._eyeZ = 10
        #self.guiCamera._projection = 0

        # TODO use simpler camera for gui
        self.guiCamera = mh.OrbitalCamera()

        mh.cameras.append(self.guiCamera)

    @property
    def settings(self):
        """READ-ONLY dict of the settings of this application. Changing this
        dict has NO impact."""
        return dict(self._settings)

    def addSetting(self, setting_name, default_value, value=None):
        """Declare a new setting for this application. Only has an impact the
        first time it's called for a unique setting_name. It's impossible to
        re-declare defaults for settings.
        """
        if setting_name == 'version':
            raise KeyError('The keyword "version" is protected for settings')

        if setting_name in self._default_settings:
            log.notice("Setting %s is already declared. Adding it again has no effect." % setting_name)
            return
        self._default_settings[setting_name] = default_value
        if value is None:
            if setting_name in self._undeclared_settings:
                # Deferred set of setting value
                log.debug("Assigning setting %s value %s that was loaded before the setting was declared." % (setting_name, self._undeclared_settings[setting_name]))
                self._settings[setting_name] = self._undeclared_settings[setting_name]
                del self._undeclared_settings[setting_name]
            else:
                self._settings[setting_name] = default_value
        else:
            self._settings[setting_name] = value

    def getSetting(self, setting_name):
        """Retrieve the value of a setting.
        """
        if setting_name not in self._default_settings:
            raise KeyError("Setting %s is unknown, make sure to declare it first with addSetting()" % setting_name)
        return self._settings.get(setting_name, self.getSettingDefault(setting_name))

    def getSettingDefault(self, setting_name):
        """Retrieve the default value declared for a setting."""
        return self._default_settings[setting_name]

    def setSetting(self, setting_name, value):
        """Change the value of a setting. If value == None, the default value
        for that setting is restored."""
        if setting_name not in self._default_settings:
            raise KeyError("Setting %s is not declared" % setting_name)
        if value is None:
            self._settings[setting_name] = self.getSettingDefault(setting_name)
        else:
            self._settings[setting_name] = value

    def resetSettings(self):
        """Restore all settings to their defaults
        """
        self._settings = dict(self._default_settings)

    def _versionSentinel(self):
        # dummy method used for checking the shortcuts.ini version
        pass

    @property
    def args(self):
        return G.args

    def loadHumanMHM(self, filename):
        self.selectedHuman.load(filename, True)
        self.clearUndoRedo()
        # Reset mesh is never forced to wireframe
        self.actions.wireframe.setChecked(False)

    # TO THINK: Maybe move guisave's saveMHM here as saveHumanMHM?

    def loadHuman(self):
        # Set a lower than default MAX_FACES value because we know the human has a good topology (will make it a little faster)
        # (we do not lower the global limit because that would limit the selection of meshes that MH would accept too much)
        self.selectedHuman = self.addObject(human.Human(files3d.loadMesh(mh.getSysDataPath("3dobjs/base.obj"), maxFaces = 5)))

        # Set the base skeleton
        base_skel = skeleton.load(mh.getSysDataPath('rigs/default.mhskel'), self.selectedHuman.meshData)
        self.selectedHuman.setBaseSkeleton(base_skel)

    def loadScene(self):
        userSceneDir = mh.getDataPath("scenes")
        if not os.path.exists(userSceneDir):
            os.makedirs(userSceneDir)

        from scene import Scene
        from getpath import findFile
        self.setScene( Scene(findFile("scenes/default.mhscene")) )

    def loadMainGui(self):
        @self.selectedHuman.mhEvent
        def onMouseDown(event):
          if self.tool:
            self.selectedGroup = self.getSelectedFaceGroup()
            self.tool.callEvent("onMouseDown", event)
          else:
            self.currentTask.callEvent("onMouseDown", event)

        @self.selectedHuman.mhEvent
        def onMouseMoved(event):
          if self.tool:
            self.tool.callEvent("onMouseMoved", event)
          else:
            self.currentTask.callEvent("onMouseMoved", event)

        @self.selectedHuman.mhEvent
        def onMouseDragged(event):
          if self.tool:
            self.tool.callEvent("onMouseDragged", event)
          else:
            self.currentTask.callEvent("onMouseDragged", event)

        @self.selectedHuman.mhEvent
        def onMouseUp(event):
          if self.tool:
            self.tool.callEvent("onMouseUp", event)
          else:
            self.currentTask.callEvent("onMouseUp", event)

        @self.selectedHuman.mhEvent
        def onMouseEntered(event):
          if self.tool:
            self.tool.callEvent("onMouseEntered", event)
          else:
            self.currentTask.callEvent("onMouseEntered", event)

        @self.selectedHuman.mhEvent
        def onMouseExited(event):
          if self.tool:
            self.tool.callEvent("onMouseExited", event)
          else:
            self.currentTask.callEvent("onMouseExited", event)

        @self.selectedHuman.mhEvent
        def onMouseWheel(event):
          if self.tool:
            self.tool.callEvent("onMouseWheel", event)
          else:
            self.currentTask.callEvent("onMouseWheel", event)

        @self.selectedHuman.mhEvent
        def onChanging(event):
            self.callEventHandlers('onHumanChanging', event)

        @self.selectedHuman.mhEvent
        def onChanged(event):
            self.actions.pose.setEnabled(self.selectedHuman.isPoseable())

            if event.change == 'smooth':
                # Update smooth action state (without triggering it)
                self.actions.smooth.setChecked(self.selectedHuman.isSubdivided())
            elif event.change in ['poseState', 'poseRefresh']:
                self.actions.pose.setChecked(self.selectedHuman.isPosed())
            elif event.change == 'load':
                self.currentFile.loaded(event.path)
            elif event.change == 'save':
                self.currentFile.saved(event.path)
            elif event.change == 'reset':
                self.currentFile.closed()
            self.callEventHandlers('onHumanChanged', event)

        @self.selectedHuman.mhEvent
        def onTranslated(event):
            self.callEventHandlers('onHumanTranslated', event)

        @self.selectedHuman.mhEvent
        def onRotated(event):
            self.callEventHandlers('onHumanRotated', event)

        @self.selectedHuman.mhEvent
        def onShown(event):
            self.callEventHandlers('onHumanShown', event)

        @self.selectedHuman.mhEvent
        def onHidden(event):
            self.callEventHandlers('onHumanHidden', event)

        @self.modelCamera.mhEvent
        def onRotated(event):
            self.callEventHandlers('onCameraRotated', event)

        # Set up categories and tasks
        self.files = guifiles.FilesCategory(self)
        self.getCategory("Modelling")
        self.getCategory("Geometries")
        self.getCategory("Materials")
        self.getCategory("Pose/Animate")
        self.getCategory("Rendering")

    def loadPlugins(self):

        # Load plugins not starting with _
        pluginsToLoad = glob.glob(mh.getSysPath(os.path.join("plugins/",'[!_]*.py')))

        # Load plugin packages (folders with a file called __init__.py)
        for fname in os.listdir(mh.getSysPath("plugins/")):
            if fname[0] != "_":
                folder = os.path.join("plugins", fname)
                if os.path.isdir(folder) and ("__init__.py" in os.listdir(folder)):
                    pluginsToLoad.append(folder)

        pluginsToLoad.sort()

        fprog = Progress(len(pluginsToLoad))
        for path in pluginsToLoad:
            self.loadPlugin(path)
            fprog.step()

    def loadPlugin(self, path):

        try:
            name, ext = os.path.splitext(os.path.basename(path))
            if name not in self.getSetting('excludePlugins'):
                log.message('Importing plugin %s', name)
                #module = imp.load_source(name, path)

                module = None
                fp, pathname, description = imp.find_module(name, ["plugins/"])
                try:
                    module = imp.load_module(name, fp, pathname, description)
                finally:
                    if fp:
                        fp.close()
                if module is None:
                    log.message("Could not import plugin %s", name)
                    return

                self.modules[name] = module
                log.message('Imported plugin %s', name)
                log.message('Loading plugin %s', name)
                module.load(self)
                log.message('Loaded plugin %s', name)

                # Process all non-user-input events in the queue to make sure
                # any callAsync events are run.
                self.processEvents()
            else:
                self.modules[name] = None
        except Exception, _:
            log.warning('Could not load %s', name, exc_info=True)

    def unloadPlugins(self):

        for name, module in self.modules.iteritems():
            if module is None:
                continue
            try:
                log.message('Unloading plugin %s', name)
                module.unload(self)
                log.message('Unloaded plugin %s', name)
            except Exception, _:
                log.warning('Could not unload %s', name, exc_info=True)

    def getLoadedPlugins(self):
        """
        Get the names of loaded plugins.
        """
        return self.modules.keys()

    def getPlugin(self, name):
        """
        Get the (python) module of the plugin with specified name.
        """
        return self.modules[name]

    def loadGui(self):

        progress = Progress(5)

        category = self.getCategory('Settings')
        category.addTask(PluginsTaskView(category))
        progress.step()

        mh.refreshLayout()
        progress.step()

        self.switchCategory("Modelling")
        progress.step()

        # Create viewport grid
        self.loadGrid()
        progress.step()

        # Create background gradient
        self.loadBackgroundGradient()
        progress.step()

        # self.progressBar.hide()

    def loadGrid(self):
        if self.backplaneGrid:
            self.removeObject(self.backplaneGrid)

        if self.groundplaneGrid:
            self.removeObject(self.groundplaneGrid)

        offset = self.selectedHuman.getJointPosition('ground')[1]
        spacing = 1 if self.getSetting('units') == 'metric' else 3.048

        # Background grid
        gridSize = int(200/spacing)
        if gridSize % 2 != 0:
            gridSize += 1
        if self.getSetting('units') == 'metric':
            subgrids = 10
        else:
            subgrids = 12
        backGridMesh = geometry3d.GridMesh(gridSize, gridSize, spacing, offset = -10, plane = 0, subgrids = subgrids)
        backGridMesh.setMainColor(self.gridColor)
        backGridMesh.setSubColor(self.gridSubColor)
        backGridMesh.restrictVisibleToCamera = True
        backGridMesh.minSubgridZoom = (1.0/spacing) * float(subgrids)/5
        self.backplaneGrid = gui3d.Object(backGridMesh)
        self.backplaneGrid.excludeFromProduction = True
        self.backplaneGrid.placeAtFeet = True
        self.backplaneGrid.lockRotation = True
        self.backplaneGrid.setShadeless(1)
        #self.backplaneGrid.setPosition([0,offset,0])
        self.addObject(self.backplaneGrid)

        # Ground grid
        gridSize = int(20/spacing)
        if gridSize % 2 != 0:
            gridSize += 1
        groundGridMesh = geometry3d.GridMesh(gridSize, gridSize, spacing, offset = 0, plane = 1, subgrids = subgrids)
        groundGridMesh.setMainColor(self.gridColor)
        groundGridMesh.setSubColor(self.gridSubColor)
        groundGridMesh.minSubgridZoom = (1.0/spacing) * float(subgrids)/5
        self.groundplaneGrid = gui3d.Object(groundGridMesh)
        self.groundplaneGrid.excludeFromProduction = True
        self.groundplaneGrid.placeAtFeet = True
        self.groundplaneGrid.setShadeless(1)
        #self.groundplaneGrid.setPosition([0,offset,0])
        groundGridMesh.restrictVisibleAboveGround = True
        self.addObject(self.groundplaneGrid)

        self.actions.grid.setChecked(True)

    def loadBackgroundGradient(self):
        import numpy as np

        if self.backgroundGradient:
            self.removeObject(self.backgroundGradient)

        mesh = geometry3d.RectangleMesh(10, 10, centered=True)

        mesh.setColors(self.bgBottomLeftColor, self.bgBottomRightColor, 
                       self.bgTopRightColor, self.bgTopLeftColor)

        self.backgroundGradient = gui3d.Object(mesh)
        self.backgroundGradient.priority = -200
        self.backgroundGradient.excludeFromProduction = True
        self.backgroundGradient.setShadeless(1)
        self.backgroundGradient.material.configureShading(vertexColors=True)

        self.addObject(self.backgroundGradient)

        self._updateBackgroundDimensions()

    def onResizedCallback(self, event):
        gui3d.Application.onResizedCallback(self, event)
        self._updateBackgroundDimensions()

    def _updateBackgroundDimensions(self, width=G.windowWidth, height=G.windowHeight):
        if self.backgroundGradient is None:
            return

        cam = self.backgroundGradient.mesh.getCamera()
        #minX,minY,_ = cam.convertToWorld2D(0,0)
        #maxX,maxY,_ = cam.convertToWorld2D(width, height)
        #self.backgroundGradient.mesh.resize(abs(maxX - minX), abs(maxY - minY))

        # TODO hack for orbital camera, properly clean this up some day
        height = cam.getScale()
        aspect = cam.getAspect()
        width = height * aspect
        self.backgroundGradient.mesh.resize(2.1*width, 2.1*height)

        self.backgroundGradient.setPosition([0, 0, -0.85*cam.farPlane])

    def loadMacroTargets(self):
        """
        Preload all target files belonging to group macrodetails and its child
        groups.
        """
        import targets
        #import getpath
        for target in targets.getTargets().findTargets('macrodetails'):
            #log.debug('Preloading target %s', getpath.getRelativePath(target.path))
            algos3d.getTarget(self.selectedHuman.meshData, target.path)

    def loadFinish(self):
        self.selectedHuman.updateMacroModifiers()
        self.selectedHuman.applyAllTargets()

        self.currentFile.modified = False

        #printtree(self)

        mh.changeCategory("Modelling")

        self.redraw()

    def startupSequence(self):
        self._processCommandlineArgs(beforeLoaded = True)

        mainwinGeometry = self.mainwin.storeGeometry()
        mainwinBorder = (self.mainwin.frameGeometry().width() - self.mainwin.width(),
             self.mainwin.frameGeometry().height() - self.mainwin.height())

        # Move main window completely behind splash screen
        self.mainwin.resize(self.splash.width() - mainwinBorder[0], self.splash.height() - mainwinBorder[1])
        self.mainwin.move(self.splash.pos())

        #self.splash.setFormat('<br><br><b><font size="10" color="#ffffff">%s</font></b>')

        progress = Progress([36, 6, 15, 333, 40, 154, 257, 5], messaging=True)

        progress.firststep('Loading human')
        self.loadHuman()

        progress.step('Loading scene')
        self.loadScene()

        progress.step('Loading main GUI')
        self.loadMainGui()

        progress.step('Loading plugins')
        self.loadPlugins()

        progress.step('Loading GUI')
        self.loadGui()

        progress.step('Loading theme')
        try:
            self.setTheme(self.getSetting('guiTheme'))
        except:
            self.setTheme("default")

        progress.step('Applying targets')
        self.loadFinish()
        
        progress.step('Loading macro targets')
        if self.getSetting('preloadTargets'):
            self.loadMacroTargets()

        progress.step('Loading done')

        log.message('') # Empty status indicator

        if sys.platform.startswith("darwin"):
            self.splash.resize(0,0) # work-around for mac splash-screen closing bug

        self.mainwin.show()
        self.splash.hide()
        # self.splash.finish(self.mainwin)
        self.splash.close()
        self.splash = None

        self.prompt('Warning', 'MakeHuman is a character creation suite. It is designed for making anatomically correct humans.\nParts of this program may contain nudity.\nDo you want to proceed?', 'Yes', 'No', None, self.stop, 'nudityWarning')

        if not self.args.get('noshaders', False) and \
          ( not mh.Shader.supported() or mh.Shader.glslVersion() < (1,20) ):
            self.prompt('Warning', 'Your system does not support OpenGL shaders (GLSL v1.20 required).\nOnly simple shading will be available.', 'Ok', None, None, None, 'glslWarning')

        # Restore main window size and position
        geometry = self.getSetting('windowGeometry')
        if self.getSetting('restoreWindowSize') and geometry:
            self.mainwin.restoreGeometry(geometry)
        else:
            self.mainwin.restoreGeometry(mainwinGeometry)

        self._processCommandlineArgs(beforeLoaded = False)

    def _processCommandlineArgs(self, beforeLoaded):
        if beforeLoaded:
            if self.args.get('noshaders', False):
                log.message("Force shaders disabled")

        else: # After application is loaded
            if self.args.get('mhmFile', None):
                import getpath
                mhmFile = getpath.pathToUnicode( self.args.get('mhmFile') )
                log.message("Loading MHM file %s (as specified by commandline argument)", mhmFile)
                if not os.path.isfile(mhmFile):
                    mhmFile = getpath.findFile(mhmFile, mh.getPath("models"))
                if os.path.isfile(mhmFile):
                    self.loadHumanMHM(mhmFile)
                else:
                    log.error("Failed to load MHM file. The MHM file specified as argument (%s) does not exist!", mhmFile)
            if self.args.get('runtests', False):
                log.message("Running test suite")
                import testsuite
                testsuite.runAll()

            # Apply options from advanced commandline args to human
            import humanargparser
            humanargparser.applyModelingArguments(self.selectedHuman, self.args)

    # Events
    def onStart(self, event):
        self.startupSequence()

    def onStop(self, event):
        if self.getSetting('restoreWindowSize'):
            self.setSetting('windowGeometry', self.mainwin.storeGeometry())

        self.saveSettings(True)
        self.unloadPlugins()
        self.dumpMissingStrings()

    def onQuit(self, event):
        self.promptAndExit()

    def onMouseDown(self, event):
        if self.selectedHuman.isVisible():
            # Normalize modifiers
            modifiers = mh.getKeyModifiers() & (mh.Modifiers.CTRL | mh.Modifiers.ALT | mh.Modifiers.SHIFT)

            if (modifiers, event.button) in self.mouseActions:
                action = self.mouseActions[(modifiers, event.button)]
                if action == self.mouseFocus:
                    self.modelCamera.mousePickHumanFocus(event.x, event.y)
                elif action == self.mouseZoom:
                    self.modelCamera.mousePickHumanCenter(event.x, event.y)

    def onMouseDragged(self, event):

        if self.selectedHuman.isVisible():
            # Normalize modifiers
            modifiers = mh.getKeyModifiers() & (mh.Modifiers.CTRL | mh.Modifiers.ALT | mh.Modifiers.SHIFT)

            if (modifiers, event.button) in self.mouseActions:
                self.mouseActions[(modifiers, event.button)](event)

    def onMouseWheel(self, event):
        if self.selectedHuman.isVisible():
            zoomOut = event.wheelDelta > 0
            if self.getSetting('invertMouseWheel'):
                zoomOut = not zoomOut

            if event.x is not None:
                self.modelCamera.mousePickHumanCenter(event.x, event.y)

            if zoomOut:
                self.zoomOut()
            else:
                self.zoomIn()

    # Undo-redo
    def do(self, action):
        if action.do():
            self.undoStack.append(action)
            del self.redoStack[:]
            self.currentFile.changed()
            log.message('do %s', action.name)
            self.syncUndoRedo()

    def did(self, action):
        self.undoStack.append(action)
        self.currentFile.changed()
        del self.redoStack[:]
        log.message('did %s', action.name)
        self.syncUndoRedo()

    def undo(self):
        if self.undoStack:
            action = self.undoStack.pop()
            log.message('undo %s', action.name)
            action.undo()
            self.redoStack.append(action)
            self.currentFile.changed()
            self.syncUndoRedo()

    def redo(self):
        if self.redoStack:
            action = self.redoStack.pop()
            log.message('redo %s', action.name)
            action.do()
            self.undoStack.append(action)
            self.currentFile.changed()
            self.syncUndoRedo()

    def syncUndoRedo(self):
        self.actions.undo.setEnabled(bool(self.undoStack))
        self.actions.redo.setEnabled(bool(self.redoStack))
        self.redraw()

    def clearUndoRedo(self):
        self.undoStack = []
        self.redoStack = []
        self.syncUndoRedo()

    # Settings

    def loadSettings(self):
        with inFile("settings.ini") as f:
            if f:
                settings = mh.parseINI(f.read())

                if 'version' in settings and settings['version'] == mh.getVersionDigitsStr():
                    # Only load settings for this specific version
                    del settings['version']
                    for setting_name, value in settings.items():
                        try:
                            self.setSetting(setting_name, value)
                        except:
                            # Store the values of (yet) undeclared settings and defer until plugins are loaded
                            self._undeclared_settings[setting_name] = value
                else:
                    log.warning("Incompatible MakeHuman settings (version %s) detected (expected %s). Loading default settings." % (settings.get('version','undefined'), mh.getVersionDigitsStr()))
            else:
                log.warning("No settings file found, starting with default settings.")

        if 'language' in self.settings:
            self.setLanguage(self.settings['language'])

        gui.Slider.showImages(self.settings['sliderImages'])

        with inFile("shortcuts.ini") as f:
            shortcuts = {}
            for line in f:
                modifier, key, action = line.strip().split(' ')
                shortcuts[action] = (int(modifier), int(key))
            if shortcuts.get('_versionSentinel') != (0, 0x87654321):
                log.warning('shortcuts.ini out of date; ignoring')
            else:
                self.shortcuts.update(shortcuts)

        with inFile("mouse.ini") as f:
            mouseActions = dict([(method.__name__, shortcut)
                                 for shortcut, method in self.mouseActions.iteritems()])
            for line in f:
                modifier, button, method = line.strip().split(' ')
                if hasattr(self, method):
                    mouseActions[method] = (int(modifier), int(button))
            self.mouseActions = dict([(shortcut, getattr(self, method))
                                      for method, shortcut in mouseActions.iteritems()])

        with inFile("help.ini") as f:
            helpIds = set()
            for line in f:
                helpIds.add(line.strip())
            if self.dialog is not None:
                self.dialog.helpIds.update(self.helpIds)
            self.helpIds = helpIds

    def saveSettings(self, promptOnFail=False):
        try:
            if not os.path.exists(mh.getPath()):
                os.makedirs(mh.getPath())

            with outFile("settings.ini") as f:
                settings = self.settings
                settings['version'] = mh.getVersionDigitsStr() 
                f.write(mh.formatINI(settings))

            with outFile("shortcuts.ini") as f:
                for action, shortcut in self.shortcuts.iteritems():
                    f.write('%d %d %s\n' % (shortcut[0], shortcut[1], action))

            with outFile("mouse.ini") as f:
                for mouseAction, method in self.mouseActions.iteritems():
                    f.write('%d %d %s\n' % (mouseAction[0], mouseAction[1], method.__name__))

            if self.dialog is not None:
                self.helpIds.update(self.dialog.helpIds)

            with outFile("help.ini") as f:
                for helpId in self.helpIds:
                    f.write('%s\n' % helpId)
        except:
            log.error('Failed to save settings file', exc_info=True)
            if promptOnFail:
                self.prompt('Error', 'Could not save settings file.', 'OK')

    # Themes
    def setTheme(self, theme):
        # Disabling this check allows faster testing of a skin by reloading it.
        #if self.theme == theme:
        #    return

        # Set defaults
        self.clearColor = [0.5, 0.5, 0.5]
        self.gridColor = [1.0, 1.0, 1.0]
        self.gridSubColor = [0.7, 0.7, 0.7]
        log._logLevelColors[log.DEBUG] = 'grey'
        log._logLevelColors[log.NOTICE] = 'blue'
        log._logLevelColors[log.WARNING] = 'darkorange'
        log._logLevelColors[log.ERROR] = 'red'
        log._logLevelColors[log.CRITICAL] = 'red'
        self.bgBottomLeftColor = [0.101, 0.101, 0.101]
        self.bgBottomRightColor = [0.101, 0.101, 0.101]
        self.bgTopLeftColor = [0.312, 0.312, 0.312]
        self.bgTopRightColor = [0.312, 0.312, 0.312]

        f = open(os.path.join(mh.getSysDataPath("themes/"), theme + ".mht"), 'rU')

        update_log = False
        for data in f.readlines():
            lineData = data.split()

            if len(lineData) > 0:
                if lineData[0] == "version":
                    log.message('Theme %s version %s', theme, lineData[1])
                elif lineData[0] == "color":
                    if lineData[1] == "clear":
                        self.clearColor[:] = [float(val) for val in lineData[2:5]]
                    elif lineData[1] == "grid":
                        self.gridColor[:] = [float(val) for val in lineData[2:5]]
                    elif lineData[1] == "subgrid":
                        self.gridSubColor[:] = [float(val) for val in lineData[2:5]]
                    elif lineData[1] == "bgbottomleft":
                        self.bgBottomLeftColor[:] = [float(val) for val in lineData[2:5]]
                    elif lineData[1] == "bgbottomright":
                        self.bgBottomRightColor[:] = [float(val) for val in lineData[2:5]]
                    elif lineData[1] == "bgtopleft":
                        self.bgTopLeftColor[:] = [float(val) for val in lineData[2:5]]
                    elif lineData[1] == "bgtopright":
                        self.bgTopRightColor[:] = [float(val) for val in lineData[2:5]]
                elif lineData[0] == "logwindow_color":
                    logLevel = lineData[1]
                    if hasattr(log, logLevel) and isinstance(getattr(log, logLevel), int):
                        update_log = True
                        logLevel = int(getattr(log, logLevel))
                        log._logLevelColors[logLevel] = lineData[2]

        if self.groundplaneGrid:
            self.groundplaneGrid.mesh.setMainColor(self.gridColor)
            self.groundplaneGrid.mesh.setSubColor(self.gridSubColor)
        if self.backplaneGrid:
            self.backplaneGrid.mesh.setMainColor(self.gridColor)
            self.backplaneGrid.mesh.setSubColor(self.gridSubColor)
        if self.backgroundGradient:
            self.backgroundGradient.mesh.setColors(self.bgBottomLeftColor, 
                                                   self.bgBottomRightColor, 
                                                   self.bgTopRightColor, 
                                                   self.bgTopLeftColor)
        mh.setClearColor(self.clearColor[0], self.clearColor[1], self.clearColor[2], 1.0)

        if update_log:
            self.log_window.updateView()
        log.debug("Loaded theme %s", mh.getSysDataPath('themes/'+theme+'.mht'))

        try:
            f = open(mh.getSysDataPath('themes/%s.qss' % theme), 'r')
            qStyle = "\n".join(f.readlines())
            self.setStyleSheet(qStyle)
            # Also set stylesheet on custom slider style
            for widget in self.allWidgets():
                if isinstance(widget, gui.Slider):
                    widget.setStyleSheet(qStyle)
            log.debug("Loaded Qt style %s", mh.getSysDataPath('themes/'+theme+'.qss'))
        except:
            self.setStyleSheet("")
            # Also set stylesheet on custom slider style
            for widget in self.allWidgets():
                if isinstance(widget, gui.Slider):
                    widget.setStyleSheet("")
            '''
            if theme != "default":
                log.warning('Could not open Qt style file %s.', mh.getSysDataPath('themes/'+theme+'.qss'))
            '''

        self.theme = theme
        self.reloadIcons()
        self.callEventHandlers('onThemeChanged', events3d.ThemeChangedEvent(self.theme))
        self.redraw()

    def reloadIcons(self):
        if not self.actions:
            return
        for action in self.actions:
            action.setIcon(gui.Action.getIcon(action.name))

    def getLookAndFeelStyles(self):
        return [ str(style) for style in gui.QtGui.QStyleFactory.keys() ]

    def setLookAndFeel(self, platform):
        style = gui.QtGui.QStyleFactory.create(platform)
        self.setStyle(style)

    def getLookAndFeel(self):
        return str(self.style().objectName())

    def getThemeResource(self, folder, id):
        if '/' in id:
            return id
        path = os.path.join(mh.getSysDataPath("themes/"), self.theme, folder, id)
        if os.path.exists(path):
            return path
        else:
            return os.path.join(mh.getSysDataPath("themes/default/"), folder, id)

    def setLanguage(self, lang):
        log.debug("Setting language to %s", lang)
        language.language.setLanguage(lang)
        self.setSetting('rtl', language.language.rtl)

    def getLanguages(self):
        """
        The languages available on this MH installation, by listing all .json
        files in the languages folder in user and system data path.
        """
        return language.getLanguages()

    def getLanguageString(self, string, appendData=None, appendFormat=None):
        return language.language.getLanguageString(string,appendData,appendFormat)

    def dumpMissingStrings(self):
        language.language.dumpMissingStrings()

    # Caption
    def setCaption(self, caption):
        """Set the main window caption."""
        mh.setCaption(caption)

    def updateFilenameCaption(self):
        """Calculate and set the window title according to the
        name of the current open file and the version of MH."""
        filename = self.currentFile.name
        if filename is None:
            filename = "Untitled"
        if mh.isRelease():
            from getpath import pathToUnicode
            self.setCaption(
                "MakeHuman %s - [%s][*]" %
                (mh.getVersionStr(), pathToUnicode(filename)))
        else:
            from getpath import pathToUnicode
            self.setCaption(
                "MakeHuman r%s (%s) - [%s][*]" %
                (os.environ['HGREVISION'], os.environ['HGNODEID'], 
                pathToUnicode(filename)))
        self.mainwin.setWindowModified(self.currentFile.modified)

    # Global status bar
    def status(self, text, *args):
        if self.statusBar is None:
            return
        self.statusBar.showMessage(text, *args)

    def statusPersist(self, text, *args):
        if self.statusBar is None:
            return
        self.statusBar.setMessage(text, *args)

    # Global progress bar
    def progress(self, value, text=None, *args):
        if text is not None:
            self.status(text, *args)

        if self.splash:
            self.splash.setProgress(value)
            self.splash.raise_()

        if self.progressBar is None:
            return

        if value >= 1.0:
            self.progressBar.reset()
        else:
            self.progressBar.setProgress(value)

        self.mainwin.canvas.blockRedraw = True

        # Process all non-user-input events in the queue to run callAsync tasks.
        # This is invoked here so events are processed in every step during the
        # onStart() init sequence.
        self.processEvents()

        self.mainwin.canvas.blockRedraw = False

    # Global dialog
    def prompt(self, title, text, button1Label, button2Label=None, button1Action=None, button2Action=None, helpId=None, fmtArgs = None):
        if fmtArgs is None:
            fmtArgs = []
        elif isinstance(fmtArgs, basestring):
            fmtArgs = [fmtArgs]
        if self.dialog is None:
            self.dialog = gui.Dialog(self.mainwin)
            self.dialog.helpIds.update(self.helpIds)
        return self.dialog.prompt(title, text, button1Label, button2Label, button1Action, button2Action, helpId, fmtArgs)

    def about(self):
        """
        Show about dialog
        """
        #gui.QtGui.QMessageBox.about(self.mainwin, 'About MakeHuman', mh.getCopyrightMessage())
        #aboutbox = gui.AboutBox(self.mainwin, 'About MakeHuman', mh.getCopyrightMessage())
        abouttext = '<h1>MakeHuman license</h1>' + mh.getCopyrightMessage() + "\n" + mh.getCredits(richtext=True) + "\n\n" + mh.getSoftwareLicense(richtext=True) + "\n\n\n" + mh.getThirdPartyLicenses(richtext=True)

        aboutbox = gui.AboutBoxScrollbars(self.mainwin, 'About MakeHuman', abouttext, "MakeHuman v"+mh.getVersionStr(verbose=False, full=True))
        aboutbox.show()
        aboutbox.exec_()

    def setGlobalCamera(self):
        human = self.selectedHuman

        tl = animation3d.Timeline(0.20)
        tl.append(animation3d.PathAction(self.modelCamera, [self.modelCamera.getPosition(), [0.0, 0.0, 0.0]]))
        tl.append(animation3d.RotateAction(self.modelCamera, self.modelCamera.getRotation(), [0.0, 0.0, 0.0]))
        tl.append(animation3d.ZoomAction(self.modelCamera, self.modelCamera.zoomFactor, 1.0))
        tl.append(animation3d.UpdateAction(self))
        tl.start()

    def setTargetCamera(self, vIdx, zoomFactor = 1.0, animate = True):
        if isinstance(vIdx, (tuple, list)):
            return
        human = self.selectedHuman
        coord = human.meshData.coord[vIdx]
        direction = human.meshData.vnorm[vIdx].copy()
        self.modelCamera.focusOn(coord, direction, zoomFactor, animate)
        if not animate:
            self.redraw()

    def setFaceCamera(self):
        self.setTargetCamera(132, 8.7)

    def setLeftHandFrontCamera(self):
        self.setTargetCamera(9828, 10)

    def setLeftHandTopCamera(self):
        self.setTargetCamera(9833, 10)

    def setRightHandFrontCamera(self):
        self.setTargetCamera(3160, 10)

    def setRightHandTopCamera(self):
        self.setTargetCamera(3165, 10)

    def setLeftFootFrontCamera(self):
        self.setTargetCamera(12832, 7.7)

    def setLeftFootLeftCamera(self):
        self.setTargetCamera(12823, 7)

    def setRightFootFrontCamera(self):
        self.setTargetCamera(6235, 7.7)

    def setRightFootRightCamera(self):
        self.setTargetCamera(6208, 7)

    def setLeftArmFrontCamera(self):
        self.setTargetCamera(9981, 4.2)

    def setLeftArmTopCamera(self):
        self.setTargetCamera(9996, 2.9)

    def setRightArmFrontCamera(self):
        self.setTargetCamera(3330, 4.2)

    def setRightArmTopCamera(self):
        self.setTargetCamera(3413, 2.9)

    def setLeftLegFrontCamera(self):
        self.setTargetCamera(11325, 2.7)

    def setLeftLegLeftCamera(self):
        self.setTargetCamera(11381, 2.3)

    def setRightLegFrontCamera(self):
        self.setTargetCamera(4707, 2.7)

    def setRightLegRightCamera(self):
        self.setTargetCamera(4744, 2.3)

    def getScene(self):
        """
        The scene used for rendering the viewport.
        """
        return self._scene

    def setScene(self, scene):
        """
        Set the scene used for rendering the viewport,
        and connect its events with appropriate handler methods.
        """
        setSceneEvent = managed_file.FileModifiedEvent.fromObjectAssignment(
            scene.file if scene else None,
            self._scene.file if self._scene else None)

        self._scene = scene

        if self._scene is None:
            return

        @self._scene.file.mhEvent
        def onModified(event):
            self._sceneChanged(event)

        self._sceneChanged(setSceneEvent)

    scene = property(getScene, setScene)

    def _sceneChanged(self, event):
        """
        Method to be called internally when the scene is modified,
        that updates the view according to the modified scene,
        and emits the onSceneChanged event application - wide.
        """
        if event.file != self.scene.file:
            return

        if event.objectWasChanged:
            from glmodule import setSceneLighting
            setSceneLighting(self.scene)

        for category in self.categories.itervalues():
            self.callEventHandlers('onSceneChanged', event)

    # Shortcuts
    def setShortcut(self, modifier, key, action):

        shortcut = (modifier, key)

        if shortcut in self.shortcuts.values():
            self.prompt('Warning', 'This combination is already in use.', 'OK', helpId='shortcutWarning')
            return False

        self.shortcuts[action.name] = shortcut
        mh.setShortcut(modifier, key, action)

        return True

    def getShortcut(self, action):
        return self.shortcuts.get(action.name)

    # Mouse actions
    def setMouseAction(self, modifier, key, method):

        mouseAction = (modifier, key)

        if mouseAction in self.mouseActions:
            self.prompt('Warning', 'This combination is already in use.', 'OK', helpId='mouseActionWarning')
            return False

        # Remove old entry
        for s, m in self.mouseActions.iteritems():
            if m == method:
                del self.mouseActions[s]
                break

        self.mouseActions[mouseAction] = method

        #for mouseAction, m in self.mouseActions.iteritems():
        #    print mouseAction, m

        return True

    def getMouseAction(self, method):

        for mouseAction, m in self.mouseActions.iteritems():
            if m == method:
                return mouseAction

    # Load handlers

    def addLoadHandler(self, keyword, handler):
        """Register a handler for handling the loading of the specified
        keyword from MHM file."""
        self.loadHandlers[keyword] = handler

    def getLoadHandler(self, keyword):
        """Retrieve the plugin or handler that handles the loading of the
        specified keyword from MHM file.
        """
        self.loadHandlers.get(keyword, None)

    # Save handlers

    def addSaveHandler(self, handler, priority = None):
        """
        Register a handler to trigger when a save action happens, when called
        the handler gets the chance to write property lines to the MHM file.
        If priority is specified, should be an integer number > 0.
        0 is highest priority.
        """
        if priority is None:
            self.saveHandlers.append(handler)
        else:
            # TODO more robust solution for specifying priority weights
            self.saveHandlers.insert(priority, handler)

    # Shortcut methods

    def goToModelling(self):
        mh.changeCategory("Modelling")
        self.redraw()

    def doSave(self):
        if self.currentFile.path:
            from guisave import saveMHM
            self.currentTask.hide()
            saveMHM(self.currentFile.path)
            self.currentTask.show()
            self.redraw()
        else:
            self.goToSave()

    def goToSave(self):
        mh.changeTask("Files", "Save")
        self.redraw()

    def goToLoad(self):
        mh.changeTask("Files", "Load")
        self.redraw()

    def goToExport(self):
        mh.changeTask("Files", "Export")
        self.redraw()

    def goToRendering(self):
        mh.changeCategory("Rendering")
        self.redraw()

    def goToHelp(self):
        mh.changeCategory("Help")

    def toggleSolid(self):
        self.selectedHuman.setSolid(not self.actions.wireframe.isChecked())
        self.redraw()

    def toggleSubdivision(self):
        self.selectedHuman.setSubdivided(self.actions.smooth.isChecked(), True)
        self.redraw()

    def togglePose(self):
        self.selectedHuman.setPosed(self.actions.pose.isChecked())
        self.redraw()

    def toggleGrid(self):
        if self.backplaneGrid and self.groundplaneGrid:
            self.backplaneGrid.setVisibility( self.actions.grid.isChecked() )
            self.groundplaneGrid.setVisibility( self.actions.grid.isChecked() )
            self.redraw()

    def symmetryRight(self):
        human = self.selectedHuman
        self.do( SymmetryAction(human, 'r') )

    def symmetryLeft(self):
        human = self.selectedHuman
        self.do( SymmetryAction(human, 'l') )

    def symmetry(self):
        human = self.selectedHuman
        human.symmetryModeEnabled = self.actions.symmetry.isChecked()

    def saveTarget(self, path=None):
        """
        Export the current modifications to the human as one single target,
        relative to the basemesh.
        """
        if path is None:
            path = mh.getPath("full_target.target")
        if os.path.splitext(path)[1] != '.target':
            raise RuntimeError("Cannot save target to file %s, expected a path to a .target file." % path)
        human = self.selectedHuman
        algos3d.saveTranslationTarget(human.meshData, path)
        log.message("Full target exported to %s", path)

    def grabScreen(self):
        import datetime
        grabPath = mh.getPath('grab')
        if not os.path.exists(grabPath):
            os.makedirs(grabPath)
        grabName = datetime.datetime.now().strftime('grab_%Y-%m-%d_%H.%M.%S.png')
        filename = os.path.join(grabPath, grabName)
        mh.grabScreen(0, 0, G.windowWidth, G.windowHeight, filename)
        self.status("Screengrab saved to %s", filename)

    def resetHuman(self):
        if self.currentFile.modified:
            self.prompt('Reset', 'By resetting the human you will lose all your changes, are you sure?', 'Yes', 'No', self._resetHuman)
        else:
            self._resetHuman()

    def _resetHuman(self):
        self.selectedHuman.resetMeshValues()
        self.selectedHuman.applyAllTargets()
        self.clearUndoRedo()
        # Reset mesh is never forced to wireframe
        self.actions.wireframe.setChecked(False)

    # Camera navigation
    def rotateCamera(self, axis, amount):
        self.modelCamera.addRotation(axis, amount)
        if axis == 1 and self.modelCamera.getRotation()[1] in [0, 90, 180, 270]:
            # Make sure that while rotating the grid never appears
            self.modelCamera.addRotation(1, 0.001)
        self.redraw()

    def panCamera(self, axis, amount):
        self.modelCamera.addTranslation(axis, amount)
        self.redraw()

    def cameraSpeed(self):
        if mh.getKeyModifiers() & mh.Modifiers.SHIFT:
            return self.getSetting('highspeed')
        else:
            return self.getSetting('lowspeed')

    def zoomCamera(self, amount):
        self.modelCamera.addZoom(amount * self.cameraSpeed())
        self.redraw()

    def rotateAction(self, axis):
        return animation3d.RotateAction(self.modelCamera, self.modelCamera.getRotation(), axis)

    def axisView(self, axis):
        tmp = self.modelCamera.limitInclination
        self.modelCamera.limitInclination = False
        animation3d.animate(self, 0.20, [self.rotateAction(axis)])
        self.modelCamera.limitInclination = tmp

    def rotateDown(self):
        self.rotateCamera(0, 5.0)

    def rotateUp(self):
        self.rotateCamera(0, -5.0)

    def rotateLeft(self):
        self.rotateCamera(1, -5.0)

    def rotateRight(self):
        self.rotateCamera(1, 5.0)

    def panUp(self):
        self.panCamera(1, 0.05)

    def panDown(self):
        self.panCamera(1, -0.05)

    def panRight(self):
        self.panCamera(0, 0.05)

    def panLeft(self):
        self.panCamera(0, -0.05)

    def zoomOut(self):
        self.zoomCamera(0.65)

    def zoomIn(self):
        self.zoomCamera(-0.65)

    def frontView(self):
        self.axisView([0.0, 0.0, 0.0])

    def rightView(self):
        self.axisView([0.0, 90.0, 0.0])

    def topView(self):
        self.axisView([90.0, 0.0, 0.0])

    def backView(self):
        self.axisView([0.0, 180.0, 0.0])

    def leftView(self):
        self.axisView([0.0, -90.0, 0.0])

    def bottomView(self):
        self.axisView([-90.0, 0.0, 0.0])

    def resetView(self):
        cam = self.modelCamera
        animation3d.animate(self, 0.20, [
            self.rotateAction([0.0, 0.0, 0.0]),
            animation3d.PathAction(self.modelCamera, [self.modelCamera.getPosition(), [0.0, 0.0, 0.0]]),
            animation3d.ZoomAction(self.modelCamera, self.modelCamera.zoomFactor, 1.0) ])

    # Mouse actions
    def mouseTranslate(self, event):

        speed = self.cameraSpeed()
        self.modelCamera.addXYTranslation(event.dx * speed, event.dy * speed)

    def mouseRotate(self, event):

        speed = self.cameraSpeed()

        rotX = 0.5 * event.dy * speed
        rotY = 0.5 * event.dx * speed
        self.modelCamera.addRotation(0, rotX)
        self.modelCamera.addRotation(1, rotY)

    def mouseZoom(self, event):

        speed = self.cameraSpeed()

        if self.getSetting('invertMouseWheel'):
            speed *= -1

        self.modelCamera.addZoom( -0.05 * event.dy * speed )

    def mouseFocus(self, ev):
        pass

    def promptAndExit(self):
        if self.currentFile.modified:
            self.prompt('Exit', 'You have unsaved changes. Are you sure you want to exit the application?', 'Yes', 'No', self.stop)
        else:
            self.stop()

    def toggleProfiling(self):
        import profiler
        if self.actions.profiling.isChecked():
            profiler.start()
            log.notice('profiling started')
        else:
            profiler.stop()
            log.notice('profiling stopped')
            mh.changeTask('Utilities', 'Profile')

    def createActions(self):
        """
        Creates the actions toolbar with icon buttons.
        """
        self.actions = gui.Actions()

        def action(*args, **kwargs):
            action = gui.Action(*args, **kwargs)
            self.mainwin.addAction(action)
            if toolbar is not None:
                toolbar.addAction(action)
            return action


        # Global actions (eg. keyboard shortcuts)
        toolbar = None

        self.actions.rendering = action('rendering', self.getLanguageString('Rendering'),     self.goToRendering)
        self.actions.modelling = action('modelling', self.getLanguageString('Modelling'),     self.goToModelling)
        self.actions.exit      = action('exit'     , self.getLanguageString('Exit'),          self.promptAndExit)

        self.actions.rotateU   = action('rotateU',   self.getLanguageString('Rotate Up'),     self.rotateUp)
        self.actions.rotateD   = action('rotateD',   self.getLanguageString('Rotate Down'),   self.rotateDown)
        self.actions.rotateR   = action('rotateR',   self.getLanguageString('Rotate Right'),  self.rotateRight)
        self.actions.rotateL   = action('rotateL',   self.getLanguageString('Rotate Left'),   self.rotateLeft)
        self.actions.panU      = action('panU',      self.getLanguageString('Pan Up'),        self.panUp)
        self.actions.panD      = action('panD',      self.getLanguageString('Pan Down'),      self.panDown)
        self.actions.panR      = action('panR',      self.getLanguageString('Pan Right'),     self.panRight)
        self.actions.panL      = action('panL',      self.getLanguageString('Pan Left'),      self.panLeft)
        self.actions.zoomIn    = action('zoomIn',    self.getLanguageString('Zoom In'),       self.zoomIn)
        self.actions.zoomOut   = action('zoomOut',   self.getLanguageString('Zoom Out'),      self.zoomOut)

        self.actions.profiling = action('profiling', self.getLanguageString('Profiling'),     self.toggleProfiling, toggle=True)


        # 1 - File toolbar
        toolbar = self.file_toolbar = mh.addToolBar("File")

        self.actions.load      = action('load',      self.getLanguageString('Load'),          self.goToLoad)
        self.actions.save      = action('save',      self.getLanguageString('Save'),          self.doSave)
        self.actions.export    = action('export',    self.getLanguageString('Export'),        self.goToExport)


        # 2 - Edit toolbar
        toolbar = self.edit_toolbar = mh.addToolBar("Edit")

        self.actions.undo      = action('undo',      self.getLanguageString('Undo'),          self.undo)
        self.actions.redo      = action('redo',      self.getLanguageString('Redo'),          self.redo)
        self.actions.reset     = action('reset',     self.getLanguageString('Reset'),         self.resetHuman)


        # 3 - View toolbar
        toolbar = self.view_toolbar = mh.addToolBar("View")

        self.actions.smooth    = action('smooth',    self.getLanguageString('Smooth'),        self.toggleSubdivision, toggle=True)
        self.actions.wireframe = action('wireframe', self.getLanguageString('Wireframe'),     self.toggleSolid, toggle=True)
        self.actions.pose      = action('pose', self.getLanguageString('Pose'),               self.togglePose,  toggle=True)
        self.actions.grid      = action('grid', self.getLanguageString('Grid'),               self.toggleGrid,  toggle=True)


        # 4 - Symmetry toolbar
        toolbar = self.sym_toolbar = mh.addToolBar("Symmetry")

        self.actions.symmetryR = action('symm1', self.getLanguageString('Symmmetry R>L'),     self.symmetryLeft)
        self.actions.symmetryL = action('symm2', self.getLanguageString('Symmmetry L>R'),     self.symmetryRight)
        self.actions.symmetry  = action('symm',  self.getLanguageString('Symmmetry'),         self.symmetry, toggle=True)


        # 5 - Camera toolbar
        toolbar = self.camera_toolbar = mh.addToolBar("Camera")

        self.actions.front     = action('front',     self.getLanguageString('Front view'),    self.frontView)
        self.actions.back      = action('back',      self.getLanguageString('Back view'),     self.backView)
        self.actions.right     = action('right',     self.getLanguageString('Right view'),    self.rightView)
        self.actions.left      = action('left',      self.getLanguageString('Left view'),     self.leftView)
        self.actions.top       = action('top',       self.getLanguageString('Top view'),      self.topView)
        self.actions.bottom    = action('bottom',    self.getLanguageString('Bottom view'),   self.bottomView)
        self.actions.resetCam  = action('resetCam',  self.getLanguageString('Reset camera'),  self.resetView)


        # 6 - Other toolbar
        toolbar = self.other_toolbar = mh.addToolBar("Other")

        self.actions.grab      = action('grab',      self.getLanguageString('Grab screen'),   self.grabScreen)
        self.actions.help      = action('help',      self.getLanguageString('Help'),          self.goToHelp)


    def createShortcuts(self):
        for action, (modifier, key) in self.shortcuts.iteritems():
            action = getattr(self.actions, action, None)
            if action is not None:
                mh.setShortcut(modifier, key, action)

    def OnInit(self):
        mh.Application.OnInit(self)

        #[BAL 07/14/2013] work around focus bug in PyQt on OS X
        if sys.platform == 'darwin':
            G.app.mainwin.raise_()

        self.setLanguage("english")

        self.loadSettings()

        # Necessary because otherwise setting back to default theme causes crash
        log.message("Initializing default theme first.")
        self.setTheme("default")
        log.debug("Using Qt system style %s", self.getLookAndFeel())

        self.createActions()
        self.syncUndoRedo()

        self.createShortcuts()

        self.splash = gui.SplashScreen(self.getThemeResource('images', 'splash.png'), mh.getVersionDigitsStr())
        self.splash.show()
        if sys.platform != 'darwin':
            self.mainwin.hide()  # Fix for OSX crash thanks to Francois (issue #593)

        self.tabs = self.mainwin.tabs

        @self.tabs.mhEvent
        def onTabSelected(tab):
            self.switchCategory(tab.name)

    def run(self):
        self.start()

    def addExporter(self, exporter):
        self.getCategory('Files').getTaskByName('Export').addExporter(exporter)
