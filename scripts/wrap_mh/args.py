import os
from collections import OrderedDict
from mh_helpers import get_age, get_age_years
from .data import prelim_args_dict, prelim_vals_dict
from .mh_plugins import modeling_8_random


def get_parent_overrides(human):
    return OrderedDict({
        "p1": {
            'label': 'Mother',
            'gender': 0.0,
            'age': 25.0,
            'modifier': dict([
                ('macrodetails/Gender', 0.0),
                ('macrodetails/Age', get_age(25.0)),
                #("stomach/stomach-pregnant-decr|incr",1.0), #too hard for people to remove for now
            ])
        },
        "p2": {
            'label': 'Father',
            'gender': 1.0,
            'age': 25.0,
            'modifier': dict([
                ('macrodetails/Gender', 1.0), ('macrodetails/Age', get_age(25.0))
            ])
        },
        "c1": {
            'label': 'Baby',  # put random name or something
            'age': 5.0,
            'modifier': dict([
                ('macrodetails/Age', get_age(5.0))
            ])
        },
    })


def get_rand_args(human,
                  name='Human',
                  argsd=None,
                  symmetry=1,
                  macro=1,
                  height=0,
                  face=0,
                  body=0):
    random_values = modeling_8_random.randomize(human, symmetry, macro, height,
                                                face, body)
    # quantify these to 2 decimal places to reduce the  amount of variations and allow some caching
    for k in random_values:
        random_values[k] = round(random_values[k], 2)
    if argsd == None:
        args = get_default_args(name)
    else:
        args = argsd.copy()
    argsmd = OrderedDict(args['modifier'])
    for mName, val in random_values.items():
        if mName in argsmd.keys():
            v = argsmd[mName]
            mm = human.getModifier(mName)
            if mm:
                d = mm.getDefaultValue()
            else:
                d = 0
        else:
            v = d = None
        if v == None or v == d:  # don't override set values, lets see how that works
            argsmd[mName] = val
    args['modifier'] = list(argsmd.items())

    humans = dict([[name, args]])
    args = args_move_to_prelim(humans)[name]
    return args


def get_default_args(name='human', ext='.obj'):
    default_args1 = OrderedDict({
        u'age': 20.0,
        u'gender': 1.0,
        u'race': u'caucasian',
        #u'rig': 'data/rigs/default.json', # errors
        #u'output': os.path.join(BASE_DIR,'static','models','{}.obj'.format(name)),
        u'output': os.path.join('','{}{}'.format(name, ext)),
        u'proxy': [],
        u'modifier': [
            # (u'mouth/mouth-angles-up|down', -0.40)  # smile! #TODO rnadomize
        ],
        #u'pose':'data/poses/standing02.bvh',
        u'debugnumpy': False,
        u'debugopengl': False,
        u'fullloggingopengl': False,
        u'listmaterials': False,
        u'listmodifiers': False,
        u'listproxies': None,
        u'listproxymaterials': None,
        u'listproxytypes': False,
        u'listrigs': False,
        u'material': None,
        u'mhmFile': None,
        u'nomultisampling': False,
        u'noshaders': False,
        u'proxymaterial': None,
        u'runtests': False,
        u'userid': '',
        u'elementid': '',
        u'callbackurl': '',
    })
    args = default_args1.copy()
    if "modifier" not in args.keys():
        args["modifier"] = []
    if args["modifier"] == None:
        args["modifier"] = []
    #for m in modifiers:
    #    args["modifier"].append((m.fullName,m.getDefaultValue())) # decided to ignore default args
    return args


default_args = get_default_args()


def patch_args(args):
    """Adjust args so fix overwrites and macromodifiers."""
    # also will eventualy move to modifiers as a dict, and convert back to list here
    # maybe move prelim ars to args here, to prevent humanargsparse from rendering model once for each prelim args
    args = normalise_ethnicities(args)
    return args

def normalise_ethnicities(args):
    """
    Makehuman doens't normalize ethnicities properly unless they are floats.

    Lets normalise here justi n case.
    """
    argsmd = OrderedDict(args['modifier'])
    asian = argsmd.get('macrodetails/Asian', 0.0)
    african = argsmd.get('macrodetails/African', 0.0)
    caucasian = argsmd.get('macrodetails/Caucasian', 0.0)
    racesum = sum([asian, african, caucasian])
    if racesum == 0:
        asian = african = caucasian = 1.0 / 3
    else:
        asian = asian / racesum
        african = african / racesum
        caucasian = caucasian / racesum
    argsmd['macrodetails/Asian'] = asian
    argsmd['macrodetails/African'] = african
    argsmd['macrodetails/Caucasian'] = caucasian
    args['modifier'] = list(argsmd.items())
    return args


def getDominantEthnicity(args):
    argsmd = OrderedDict(args['modifier'])
    asian = argsmd.get('macrodetails/Asian', 0.0)
    african = argsmd.get('macrodetails/African', 0.0)
    caucasian = argsmd.get('macrodetails/Caucasian', 0.0)
    if asian > (max(african, caucasian)):
        return 'asian'
    elif african > caucasian:
        return 'african'
    else:
        return 'caucasuan'


def prelim_move_to_args(humans):
    """
    We have the prominant age, race, gender sliders which can be overwritten by harder to find macro modifiers
    Here we move macromodifiers to the prominant sliders or turn off sliders
    TODO: maybe just make those prominant slider directly control the macro mods?
    """

    for hName in humans.keys():
        argsmd = OrderedDict(humans[hName]['modifier'])
        for pak, pa in prelim_args_dict.items():
            if pak in humans[hName]:
                if pak == 'race':
                    pass
                elif pak == 'age':
                    argsmd[pa] = get_age(humans[hName][pak])
                elif pak == 'gender':
                    argsmd[pa] = humans[hName][pak]
                else:
                    print "Error unrecognised prelim arg:", pa

        humans[hName]['modifier'] = list(argsmd.items())
    return humans


def args_move_to_prelim(humans):
    """
    We have the prominant age, race, gender sliders which can be overwritten by harder to find macro modifiers
    Here we move macromodifiers to the prominant sliders or turn off sliders
    TODO: maybe just make those prominant slider directly control the macro mods?
    """
    for hName in humans.keys():
        argsmd = OrderedDict(humans[hName]['modifier'])
        for pak, pa in prelim_args_dict.items():
            if pa in argsmd.keys():
                if pak == 'race':
                    race = getDominantEthnicity(humans[hName])
                    humans[hName][pak] = race
                elif pak == 'age':
                    humans[hName][pak] = get_age_years(argsmd[pa])
                    #del argsmd[pa]
                elif pak == 'gender':
                    humans[hName][pak] = argsmd[pa]
                    #del argsmd[pa]
                else:
                    print "Error unrecognised prelim arg:", pa

        humans[hName]['modifier'] = list(argsmd.items())
    return humans


def apply_parent_overrides(args, key):
    """Parent override, TODO move to sep function."""
    parent_overrides = get_parent_overrides(human)
    argsmd = dict(args['modifier'])
    if key in parent_overrides:
        overides = parent_overrides[key]
        if 'macrodetails/Age' in overides:
            if argsmd.get(
                    'macrodetails/Age',
                    0) < parent_overrides[key]['modifier']['macrodetails/Age']:
                argsmd['macrodetails/Age'] = parent_overrides[key]['modifier'][
                    'macrodetails/Age']
        if 'age' in overides:
            if args['age'] < overides.get('age', 20):
                args['age'] = parent_overrides[key]['age']
        if 'gender' in overides:
            args['gender'] = parent_overrides[key]['gender']
        if 'modifier' in overides:
            for m in overides['modifier']:
                argsmd[m] = overides['modifier'][m]
        args['modifier'] = list(argsmd.items())
    return args
