import os
import sys
import json
from collections import OrderedDict

from .mh_helpers import clean, short_hash, clean_modifier
from .config import mhpath

#===============================================================================
# Import Makehuman resources, needs to be with makehuman dir as current dir
#===============================================================================

appcwd = os.path.abspath(os.curdir)
sys.path.append(mhpath)
sys.path.append(appcwd)
sys.path.append('.')

with mhpath:
    import makehuman
    oldpath = os.sys.path
    makehuman.set_sys_path()
    # make makehuman paths absolute by going through newest paths and making abs
    for i in range(len(os.sys.path)):
        p = os.sys.path[i]
        if p[0:2] == './':
            os.sys.path[i] = os.path.join(
                os.path.abspath('.'), p.replace('./', ''))
        else:
            break

    makehuman.init_logging()
    #import image_pil as image_lib
    #
    import proxy as mhproxy
    import humanargparser
    import targets as mhtargets
    from human import Human
    import files3d
    import getpath
    import humanmodifier
    from core import G
    import headless
    import autoskinblender
    import export

class MHStaticResources(object):
    """
    Get makehuman resources once, so webapp can access them. Cache some tasks too
    """

    def add_mh_paths(self):
        with self.mhpath:
            sys.path.append(self.mhpath)
            sys.path.append('.')
            makehuman.set_sys_path()
            # make makehuman paths absolute by going through newest paths and making abs
            for i in range(len(os.sys.path)):
                p = os.sys.path[i]
                if p[0:2] == './':
                    os.sys.path[i] = os.path.join(os.path.abspath('.'), p)
                else:
                    break

    #@cache_disk
    @property
    def modifiers(self):
        if self._modifiers is None:
            print "Loading modifiers"
            with self.mhpath:
                global mods_loaded
                humanargparser.mods_loaded = False
                self._modifiers = humanargparser._loadModifiers(None)
                self._modifiers.sort()
                # add a couple of properties for convenience
                for m in self._modifiers:
                    m.cleanname = clean_modifier(m.name)
                    m.shortname = short_hash(m.fullName)
        return self._modifiers

    def named_modifiers(self):
        """For convenience put modifiers in a dict with fullname as key."""
        return OrderedDict((m.fullName, m) for m in self.modifiers)

    def clean_modifiers(self):
        """Map modifier names to cleaned names."""
        modifier_req = OrderedDict()
        for m in self.modifiers:
            modifier_req[m.cleanname] = m.fullName
        return modifier_req

    def _listDataFiles(self,
                       foldername,
                       extensions,
                       onlySysData=False,
                       recursive=True):
        with self.mhpath:  # sadly makehuman seems hardcoded
            if onlySysData:
                paths = [getpath.getSysDataPath(foldername)]
            else:
                paths = [getpath.getDataPath(foldername),
                         getpath.getSysDataPath(foldername)]
        return list(getpath.search(paths, extensions, recursive))

    #@cache_disk
    @property
    def targets(self):
        """Load makehuman targets"""
        if self._targets is None:
            cwd = os.path.abspath('.')
            with self.mhpath:
                global _targets
                try:
                    _targets == None
                except NameError:
                    print "loading targets"
                    self._targets = mhtargets.getTargets()
                else:
                    print "targets preloaded"
        return self._targets

    #@cache_disk
    @property
    def proxies(self):
        if self._proxies is None:
            print "Loading proxies"
            cwd = os.path.abspath('.')
            with self.mhpath:
                mhproxy.ProxyTypes
                self._proxies = OrderedDict()
                for proxyType in mhproxy.ProxyTypes:
                    files = list(self._listDataFiles(proxyType.lower(),
                                                     ['.proxy', '.mhclo']))
                    for f in files:
                        if proxyType not in self._proxies.keys():
                            self._proxies[proxyType] = OrderedDict()
                        filesname = clean(os.path.splitext(os.path.basename(f))[0])
                        self._proxies[proxyType][filesname] = f
            #if 'Proxymeshes' in self._proxies:
            #    self._proxies.pop('Proxymeshes') # not supported in mh-cmd yet
        return self._proxies

    def reverse_proxies(self):
        """Make reverse proxies."""
        revProxies = dict()
        for k in self.proxies:
            d = self.proxies[k]
            revProxies[k] = dict(zip(d.values(), d.keys()))
        return revProxies

    @property
    def sliders(self, filename=None):
        """
        make a nested dict to generate controls. From mhpath

        sort modifiers into ordered dict with values of (label,OrderedDict) with the end of each branch ending in a (catagory,[(label,modifiers),(label2,modifiers2)...])
        """
        if not filename:
            filename = os.path.join(self.mhpath, 'data', 'modifiers',
                                    'modeling_sliders.json')
        if self._modeling_sliders is None:
            print "Loading modeling sliders"
            with self.mhpath:
                # from guimodifier in makehuman
                self._modeling_sliders = ['Traits', OrderedDict(), 'M']
                moddict = OrderedDict((m.fullName, m) for m in self.modifiers)
                with open(filename, 'r') as fi:
                    data = json.load(fi)
                for taskName, taskViewProps in data.items():
                    sName = taskViewProps.get('saveName', None)
                    label = taskViewProps.get('label', taskName)
                    self._modeling_sliders[1][sName] = (label, OrderedDict(), sName)
                    for sliderCategory, sliderDefs in taskViewProps[
                            'modifiers'].items():
                        self._modeling_sliders[1][sName][1][clean(
                            sliderCategory)] = (sliderCategory.capitalize(), [],
                                                sliderCategory.capitalize())
                        for sDef in sliderDefs:
                            modifierName = sDef['mod']
                            modifier = moddict[modifierName]
                            label = sDef.get('label', None)
                            self._modeling_sliders[1][sName][1][clean(
                                sliderCategory)][1].append([label, modifier, label
                                                            ])
        return self._modeling_sliders

    def getHuman(self):
        """Load a human model with modifiers."""
        with self.mhpath:
            # maxFaces *uint* Number of faces per vertex (pole), None for default (min 4)
            human = Human(files3d.loadMesh(
                getpath.getSysDataPath("3dobjs/base.obj"),
                maxFaces=5))
            # load modifiers onto human
            humanmodifier.mods_loaded = False
            modifiers = humanmodifier.loadModifiers(
                getpath.getSysDataPath('modifiers/modeling_modifiers.json'), human)
            return human

    @property
    def human(self):
        if self._human:
            return self._human
        else:
            self._human = self.getHuman()
            return self._human

    def __init__(self, mhpath):
        self.mhpath = mhpath
        self._targets = None
        self._human = None
        self._modifiers = None
        self._proxies = None
        self._modeling_sliders = None


def getHuman():
    with mhpath:
        thuman = Human(files3d.loadMesh(
            getpath.getSysDataPath("3dobjs/base.obj"),
            maxFaces=5))
        humanmodifier.mods_loaded = False
        modifiers = humanmodifier.loadModifiers(
            getpath.getSysDataPath('modifiers/modeling_modifiers.json'), thuman)
    return thuman


# init mh resources
resources = MHStaticResources(mhpath=mhpath)

# Init console app
with mhpath:
    G.app = headless.ConsoleApp()
G.app.selectedHuman = human = resources.getHuman()
headless.OBJExporter = None
headless.MHXExporter = None
headless.MhxConfig = None
humanargparser.mods_loaded = False
