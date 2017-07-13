#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
Argument parser for advanced commandline options, intended to modify the human


**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Jonas Hauquier, Séverin Lemaignan

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

Adds extra arguments to the arg parser and allows parsing and effecting them on
the human.
"""

import getpath
import sys
import os
import log

def addModelingArguments(argparser):
    """
    Add commandline options dealing with modeling the human to an existing
    argparse parser object.
    """

    # TODO add range validation on numeric values
    # Macro properties
    macroGroup = argparser.add_argument_group('Macro properties', description="Optional macro properties to set on human")
    macroGroup.add_argument("--age", default=None, type=float, help="Human age, in years")
    macroGroup.add_argument("--gender", default=None, type=float, help="Human gender (0.0: female, 1.0: male)")
    macroGroup.add_argument("--male", action="store_true", help="Produces a male character (overrides the gender argument)")
    macroGroup.add_argument("--female", action="store_true", help="Produces a female character (overrides the gender argument)")
    macroGroup.add_argument("--race", default=None, help="One of [caucasian, asian, african]")

    # Modifier parameters
    modGroup = argparser.add_argument_group('Modifiers loading')
    modGroup.add_argument("--listmodifiers", action="store_true", help="List all modifier names")
    modGroup.add_argument("-m","--modifier", nargs=2, metavar=("modifierName","value"), action="append", help="Specify a modifier and its value to apply to the human")

    # Proxies
    proxyGroup = argparser.add_argument_group('Proxy mesh specification')
    proxyGroup.add_argument("--listproxytypes", action="store_true", help="List the available proxy type names")
    modGroup.add_argument("--listproxies", metavar="proxyType", help="List all proxy files of specified proxy type")
    proxyGroup.add_argument("-p","--proxy", nargs=2, metavar=("proxyType","proxyFile"), action="append", help="Load a proxy of a specific type")

    # Rig parameters
    rigGroup = argparser.add_argument_group('Rig settings')
    rigGroup.add_argument("--listrigs", action="store_true", help="List the available rig types")
    rigGroup.add_argument("--rig", metavar="rigType", default=None, help="Setup a rig. (default: none)")
    # TODO allow setting a pose

    # Material properties
    matGroup = argparser.add_argument_group('Material settings')
    matGroup.add_argument("--listmaterials", action="store_true", help="List the available skin materials")
    matGroup.add_argument("--material", metavar="materialFile", default=None, help="Specify a skin material to apply to the human")
    # TODO
    matGroup.add_argument("--listproxymaterials", metavar=("proxyType"), help="List the available materials for the specified proxy")
    matGroup.add_argument("--proxymaterial", metavar=("proxyType","materialFile"), nargs=2, default=None, help="Specify a material to apply to the proxy")

    return argparser


def validate(argOptions):
    """
    Perform some validation on the input, print preliminary output and exit if
    required.
    """
    if argOptions.get("male", None):
        argOptions["gender"] = 0.9
    elif argOptions.get("female", None):
        argOptions["gender"] = 0.1

    if argOptions.get('listmodifiers', False):
        import humanmodifier
        modifiers = _loadModifiers(human=None)
        print """
Available modifiers:
        name    { min, max} : description
  ==========================================================================="""
        print "\n".join(['  %s\t{%s, %s}\t: %s' % (m.fullName, m.getMin(), m.getMax(), m.description) for m in modifiers])
        sys.exit()

    if argOptions.get('listproxytypes', False):
        import proxy
        print "Available proxy types:"
        for pType in proxy.ProxyTypes:
            if pType == "Proxymeshes":
                desc = "Attach a proxy with an alternative body topology"
                multi = False
            else:
                desc = "Attach %s proxy" % pType.lower()
                multi = not(pType in proxy.SimpleProxyTypes)
            desc = desc + " (%s)" % ("Multiple allowed" if multi else "Only one")
            spacing = '\t' if len(pType) > 5 else '\t\t'
            print "  %s%s%s" % (pType.lower(), spacing, desc)
        sys.exit()

    def _listDataFiles(foldername, extensions, onlySysData=False, recursive=True):
        import getpath
        if onlySysData:
            paths = [getpath.getSysDataPath(foldername)]
        else:
            paths = [getpath.getDataPath(foldername), 
                     getpath.getSysDataPath(foldername)]

        return getpath.search(paths, extensions, recursive)
        

    if argOptions.get('listproxies', None):
        # TODO list and allow loading by UUID too
        import proxy
        proxyType = argOptions['listproxies']
        if proxyType not in [p.lower() for p in proxy.ProxyTypes]:
            raise RuntimeError("Unknown proxy type (%s) passed to --listproxies argument. See --listproxytypes for valid options." % proxyType)
        files = _listDataFiles(proxyType, ['.proxy', '.mhclo'])
        print "Available %s proxies:" % proxyType
        print "\n".join(['  %s' % fname for fname in files])
        sys.exit()

    if argOptions.get('listrigs', False):
        files = _listDataFiles('rigs', ['.mhskel'], onlySysData=True, recursive=False)
        print "Available rigs:"
        print "\n".join(['  %s' % r for r in files])
        sys.exit()

    if argOptions.get('listmaterials', False):
        files = _listDataFiles('skins', ['.mhmat'])
        print "Available materials:"
        print "\n".join(['  %s' % r for r in files])
        sys.exit()

    # TODO
    #if argOptions.get('listproxymaterials', False):
    #    proxyFilePath = ...
    #    files = _listDataFiles(proxyFilePath, ['.mhmat'])
    #    print "Available materials:"
    #    print "\n".join(['  %s' % r for r in files])
    #    sys.exit()

# TODO load default eyes when no eyes are specified?

def applyModelingArguments(human, argOptions):
    """
    Apply the commandline argument options parsed by argparse to the human.
    Does nothing if no advanced commandline args were specified.
    """
    _selectivelyLoadModifiers(human)

    ### Macro properties
    if argOptions.get("age", None):
        human.setAgeYears(argOptions["age"], updateModifier=False)
    if argOptions.get("gender", None) is not None:
        human.setGender(argOptions["gender"], updateModifier=False)
    if argOptions.get("race", None) is not None:
        if argOptions["race"] == "caucasian":
            human.setCaucasian(0.9, updateModifier=False)
        elif argOptions["race"] == "african":
            human.setAfrican(0.9, updateModifier=False)
        elif argOptions["race"] == "asian":
            human.setAsian(0.9, updateModifier=False)
        else:
            raise RuntimeError('Unknown race "%s" specified on commandline. Must be one of [caucasian, african, asian]' % argOptions["race"])

    ### Modifiers (can override some macro parameters set above)
    if argOptions.get("modifier", None) is not None:
        for mName, value in argOptions["modifier"]:
            try:
                human.getModifier(mName).setValue(float(value))
            except:
                raise RuntimeError('No modifier named "%s" as specified by --modifier command. See --listmodifiers for list of acceptable options.' % mName)

    # Update human
    human.updateMacroModifiers()
    human.applyAllTargets()

    ### Skeleton
    if argOptions.get("rig", None):
        addRig(human, argOptions['rig'])

    def _isMultiProxy(proxyType):
        if proxyType == "Proxymeshes":
            return False
        import proxy
        return not(proxyType in proxy.SimpleProxyTypes)

    ### Proxies
    proxies = argOptions.get("proxy", None)
    if proxies is not None:
        appliedSimpleTypes = []
        for proxyType, proxyFile in proxies:
            import proxy
            if proxyType not in [p.lower() for p in proxy.ProxyTypes]:
                raise RuntimeError('Error in --proxy argument! Proxy type "%s" unknown, see --listproxytypes for the allowed options.' % proxyType)
            if not _isMultiProxy(proxyType):
                if proxyType in appliedSimpleTypes:
                    raise RuntimeError('Error in --proxy argument! Only one instance of proxy type "%s" is allowed.' % proxyType)
                appliedSimpleTypes.append(proxyType)
            addProxy(human, proxyFile, proxyType)
        del appliedSimpleTypes


    ### Material
    if argOptions.get("material", None):
        applyMaterial(argOptions["material"], human)


    ### Proxy material
    # TODO
    #if argOptions.get("proxymaterial", None):
    #    applyMaterial(argOptions["material"], proxyObj)


    # TODO perhaps allow disabling this option (default to off?)
    # Set a suiting default material based on predominant gender and ethnic properties
    if not argOptions.get('material', None) and human.getDominantGender() and human.getEthnicity():
        matFile = 'data/skins/young_%(race)s_%(gender)s/young_%(race)s_%(gender)s.mhmat' % {
            "race": human.getEthnicity(), 
            "gender": human.getDominantGender() }

        try:
            applyMaterial(matFile, human)
        except:
            log.error('Auto-apply Material file "%s" does not exist.', matFile)


def addProxy(human, mhclofile, type):
    # TODO if eyes proxy is loaded, the one loaded by default should be removed

    if not os.path.isfile(mhclofile):
        mhclofile = getpath.findFile(mhclofile, 
                                     searchPaths = [getpath.getDataPath(), 
                                                    getpath.getSysDataPath(),
                                                    getpath.getPath(),
                                                    getpath.getSysPath()])
        if not os.path.isfile(mhclofile):
            #log.error("Proxy file %s does not exist (%s).", mhclofile, type)
            #return
            raise RuntimeError('Proxy file "%s" does not exist (%s).' % (mhclofile, type))

    import proxy
    pxy = proxy.loadProxy(human, mhclofile, type=type.capitalize())
    mesh,obj = pxy.loadMeshAndObject(human)

    if type == "proxymeshes":
        human.setProxy(pxy)
        return

    mesh,obj = pxy.loadMeshAndObject(human)

    if not mesh:
        raise RuntimeError('Failed to load proxy mesh "%s"', pxy.obj_file)

    def _adaptProxyToHuman(pxy, obj):
        mesh = obj.getSeedMesh()
        pxy.update(mesh)
        mesh.update()
        # Update subdivided mesh if smoothing is enabled
        if obj.isSubdivided():
            obj.getSubdivisionMesh()

    _adaptProxyToHuman(pxy, obj)
    obj.setSubdivided(human.isSubdivided())

    if type == "hair":
        human.hairProxy = pxy
    elif type == "eyes":
        human.eyesProxy = pxy
    elif type == "eyebrows":
        human.eyebrowsProxy = pxy
    elif type == "eyelashes":
        human.eyelashesProxy = pxy
    elif type == "teeth":
        human.teethProxy = pxy
    elif type == "tongue":
        human.tongueProxy = pxy
    elif type == "clothes":
        human.addClothesProxy(pxy)
    else:
        raise RuntimeError("Unknown proxy type: %s" % type)

def addRig(human, rigfile):
    if not os.path.isfile(rigfile):
        rigfile = getpath.findFile(rigfile, 
                                   searchPaths = [getpath.getSysDataPath(),
                                                  getpath.getSysPath()])
        if not os.path.isfile(rigfile):
            #log.error("Rig file %s does not exist.", mhclofile)
            #return
            raise RuntimeError('Rig file "%s" does not exist.' % rigfile)

    import skeleton

    if not human.getBaseSkeleton():
        # TODO when starting in GUI mode, base skeleton will be loaded twice
        base_skel = skeleton.load(getpath.getSysDataPath('rigs/default.mhskel'), human.meshData)
        human.setBaseSkeleton(base_skel)

    referenceRig = human.getBaseSkeleton()

    # TODO update skeleton library when in gui mode
    skel = skeleton.load(rigfile, human.meshData)
    skel.autoBuildWeightReferences(referenceRig)
    vertexWeights = skel.getVertexWeights(referenceRig.getVertexWeights())
    skel.addReferencePlanes(referenceRig)  # Not strictly needed for the new way in which we determine bone normals

    human.setSkeleton(skel)

def applyMaterial(matFile, obj):
    if not os.path.isfile(matFile):
        matFile = getpath.findFile(matFile, 
                                   searchPaths = [getpath.getDataPath(), 
                                                  getpath.getSysDataPath(),
                                                  getpath.getPath(),
                                                  getpath.getSysPath()])
    if not os.path.isfile(matFile):
        raise RuntimeError('Material file "%s" does not exist.', matFile)
    else:
        import material
        obj.material = material.fromFile( matFile )


def _loadModifiers(human):
    """
    Load modifiers from file. Set human to None to not assign them to a human.
    """
    import humanmodifier
    modifiers = humanmodifier.loadModifiers(getpath.getSysDataPath('modifiers/modeling_modifiers.json'), human)
    modifiers.extend(humanmodifier.loadModifiers(getpath.getSysDataPath('modifiers/measurement_modifiers.json'), human))
    return modifiers

mods_loaded = False
def _selectivelyLoadModifiers(human):
    """
    Load modifiers if they're not already loaded.
    Only add missing ones.
    """
    global mods_loaded
    if mods_loaded:
        return
    modifiers = _loadModifiers(human)
    alreadyLoaded = human.modifierNames
    for m in modifiers:
        if m.fullName not in alreadyLoaded:
            m.setHuman(human)
    mods_loaded = True

