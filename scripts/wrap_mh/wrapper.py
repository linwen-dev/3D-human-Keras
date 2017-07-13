import os, sys
from collections import OrderedDict
import logging
logger = logging.getLogger('wrap_mh')
import numpy as np

# custom mh
from .config import mhpath
from .mh_helpers import clean_modifier, clean, short_hash, get_age, get_age_years
from .clean_models import remove_old_models
from .args import get_default_args, patch_args, args_move_to_prelim, prelim_move_to_args, get_rand_args
from .mh_plugins import modeling_8_child, modeling_8_random
from .mh_export import wavefront_split, wavefront_buff
from .convert import convert_obj_ctm
from .convert import convert_obj_three


from import_mh import human, resources, humanargparser, autoskinblender, export, getHuman, humanmodifier, headless, autoskinblender, export, getpath, files3d

def callMakeHuman2CTM(argsr):
    """Background task to compile"""
    # calls makehuman
    with mhpath:
        args = argsr.copy()
        name = args['output'].split('.')[-2]
        # make output to an abs path in current virtual machine
        args['output'] = os.path.abspath(args['output'])
        args = callMakeHuman(args)
        args = exportHuman(args)
        js_path = convert_obj_ctm.convert_to_ctm(args)
        js_file = os.path.split(js_path)[1]
        rurl = 'static/models/' + js_file
        logger.info( "made ", rurl)
    return js_path


def callMakeHuman(args):
    """Run makehuman with args."""
    # remove_old_models()
    args = patch_args(args)

    with mhpath:
        if 'human' not in args:
            args['human'] = getHuman()  # to get a new human
        #humanargparser.mods_loaded=False # otherwise I get key errors. I think I should modify humanargsparser to make this truly global
        if args['human'] and args['human'].modifiers:
            humanargparser.mods_loaded=True
        else:
            humanargparser.mods_loaded=False
        humanargparser.applyModelingArguments(args['human'], args)

        # this will force mh-cmd to blend colors for ethnicity
        # as the skin files don't do this and it I couldn't get it to work another way
        _autoSkinBlender = autoskinblender.EthnicSkinBlender(args['human'])
        args['human'].material._diffuseColor = _autoSkinBlender.getDiffuseColor()
    return args


def exportHuman(args, hiddenGeom=False):
    """Export to obj."""
    # with mhpath:
    dir = os.path.dirname(args['output'])
    exportCfg = export.ExportConfig()
    exportCfg.setHuman(args['human'])
    exportCfg.setupTexFolder(dir)
    exportCfg.texFolder = os.path.join(dir, 'textures')
    exportCfg.hiddenGeom = hiddenGeom
    exportCfg.useNormals = False
    exportCfg.feetOnGround = False

    # objects = human.getObjects(excludeZeroFaceObjs=not config.hiddenGeom)
    objects = args['human'].getObjects(excludeZeroFaceObjs=not exportCfg.hiddenGeom)
    meshes = [o.mesh for o in objects]

    if exportCfg.hiddenGeom:
        # Disable the face masking on copies of the input meshes
        meshes = [m.clone(filterMaskedVerts=False) for m in meshes]
        for m in meshes:
            # Would be faster if we could tell clone() to do this, but it would
            # make the interface more complex.
            # We could also let the wavefront module do this, but this would
            # introduce unwanted "magic" behaviour into the export function.
            face_mask = np.ones(m.face_mask.shape, dtype=bool)
            m.changeFaceMask(face_mask)
            m.calcNormals()
            m.updateIndexBuffer()

    objfiles = wavefront_split.writeObjFile(path=args['output'], meshes=meshes, writeMTL=False, config=exportCfg, filterMaskedFaces=not exportCfg.hiddenGeom)
    logger.info('exported to', objfiles)
    args['outputs'] = objfiles
    return args


def exportHumanToBuffer(args):
    """Export to obj buffer."""
    with mhpath:
        dir = os.path.dirname(args['output'])
        exportCfg = export.ExportConfig()
        exportCfg.setHuman(args['human'])
        exportCfg.setupTexFolder(dir)
        exportCfg.texFolder = os.path.join(dir, 'textures')
        objects = args['human'].getObjects(excludeZeroFaceObjs=True)
    objfiles = wavefront_buff.writeObjFile(args['output'], objects, True, exportCfg)
    logger.info(objfiles)
    args['outputs'] = objfiles
    return args

def make_child(args1, args2, args=None, name='c1', symmetry=1, macro=1, height=1, face=1, body=1):
    """Given parent args, generate a child by randomizing parameters between the parents."""
    random_values = modeling_8_child.randomizeArgs(args1['modifier'],
                                                   args2['modifier'],
                                                   human,
                                                   symmetry=1,
                                                   macro=1,
                                                   height=1,
                                                   face=1,
                                                   body=1)

    # quantify these to 2 decimal places to reduce the  amount of variations and allow some caching
    for k in random_values:
        random_values[k] = round(random_values[k], config['DECIMAL_PLACES'])

    # define child overrides
    ageYears = 13
    overrides = {'age': ageYears,
                 'modifier': {
                     "stomach/stomach-pregnant-decr|incr": 0.0,
                     'macrodetails/Age': get_age(ageYears)
                 }, }

    # if no args are passed lets set defaults with child overrides
    argsmd = OrderedDict(args['modifier'])
    if args == None:
        args = get_default_args(name=name)
        args['age'] = overrides['age']
        for mName in overrides['modifier']:
            argsmd[mName] = overrides['modifier'][mName]

    humans = dict([[name, args]])
    args = prelim_move_to_args(humans)[name]

    for mName, val in random_values.items():
        makeRandom = 0
        if mName in argsmd.keys():
            value = argsmd[mName]
            m = human.getModifier(mName)
            default_value = m.getDefaultValue()
            if value == default_value:
                makeRandom = 1
        else:
            makeRandom = 1
        if makeRandom:  # don't override set values
            if mName == 'macrodetails/Gender':
                gender = argsmd[mName]
                gender = max(0.0, min(gender, 1.0))  # make gender 0 or 1
                argsmd[mName] = gender
                args['gender'] = gender
            else:
                argsmd[mName] = val
            if mName in overrides['modifier'].keys():
                argsmd[mName] = overrides['modifier'][mName]

    # dict2list
    args['modifier'] = list(argsmd.items())

    humans = dict([[name, args]])
    args = args_move_to_prelim(humans)[name]
    return args


def getSwag(args):
    """modify the args based on gender"""
    # get gender from args
    gender = None
    if 'modifier' in args.keys():
        if args['modifier']:
            for i in args['modifier']:
                m, v = i
                if m == 'macrodetails/Gender':
                    gender = v

    if not gender:
        gender = args['gender']

    if 'proxy' not in args.keys():
        args['proxy'] = []

    if gender < 0.5:
        bgender = 'female'
        defaultProxies = [
            [u'clothes', resources.proxies['Clothes']['short01']],
            [u'clothes', resources.proxies['Clothes']['tshirt02']],
            [u'eyebrows', resources.proxies['Eyebrows']['eyebrow007']],
            [u'eyelashes', resources.proxies['Eyelashes']['eyelashes02']],
            [u'eyes', resources.proxies['Eyes']['low_poly']],
            [u'hair', resources.proxies['Hair']['ponytail01']]
        ]
        argProxyTypes = [unicode(t) for t, p in args['proxy']]
        for proxyType, prxy in defaultProxies:
            if proxyType == 'clothes':
                if [proxyType, prxy] not in args['proxy']:
                    args['proxy'].append([proxyType, prxy])
            elif proxyType not in argProxyTypes:  # set clother if no clothes are set etc
                args['proxy'].append([proxyType, prxy])
        # if 'pose' in args:
        #    args['pose']='data/poses/standing04.bvh'
    elif gender >= 0.5:
        bgender = 'male'
        defaultProxies = [
            [u'clothes', resources.proxies['Clothes']['male_casualsuit01']],
            [u'eyebrows', resources.proxies['Eyebrows']['eyebrow010']],
            [u'eyes', resources.proxies['Eyes']['low_poly']],
            [u'hair', resources.proxies['Hair']['mhair02']]
        ]
        argProxyTypes = [unicode(t) for t, p in args['proxy']]
        for proxyType, prxy in defaultProxies:
            if proxyType == 'clothes':
                if [proxyType, prxy] not in args['proxy']:
                    args['proxy'].append([proxyType, prxy])
            elif proxyType not in argProxyTypes:  # set clother if no clothes are set etc
                args['proxy'].append([proxyType, prxy])
        # if 'pose' in args:
        #    args['pose']='data/poses/standing02.bvh'
    return args


def add_pose(poseFile, phuman):
    """
    e.g. pose='data/poses/mh-rigging351-benchmark1.bvh'

    Must have a rig, and pose must work with rig, try in makehuman gui first

    This is currently broken for humans who deviate from the base mesh. I'm not sure why as it works in the gui
    """
    cwd = os.path.abspath('.')
    with mhpath:
        import libraries_pose
        pose = libraries_pose.PoseLibraryTaskView()
        logger.info("human", phuman)
        pose.setHuman(phuman)
        pose.loadPose(poseFile, apply_pose=True)

        def _adaptProxyToHuman(pxy, obj):
            mesh = obj.getSeedMesh()
            pxy.update(mesh, fit_to_posed=True)
            mesh.update()
            # Update subdivided mesh if smoothing is enabled
            if obj.isSubdivided():
                obj.getSubdivisionMesh()

        # human argparse needs to do this for clothes tryin to get clothes working
        proxies = phuman.clothesProxies.values()
        for pxy in phuman.getProxies():
            if pxy.object:
                obj = pxy.object
                obj.changeVertexMask(None)
                _adaptProxyToHuman(pxy, obj)
