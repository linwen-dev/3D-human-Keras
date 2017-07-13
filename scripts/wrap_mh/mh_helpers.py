"""Utils."""

import os, re
import uuid
import re

re_NonAlphaNumeric = re.compile('[^0-9a-zA-Z]')

# def getDominantAge(human):
#     """Only until makehuman-commandline implements this"""
#     age=human.getAgeYears()
#     if  age<25:
#         return 'young'
#     elif age<50:
#         return 'middleage'
#     else:
#         return 'old'


def get_age_years(age, human):
    """
    Return the approximate age of the human in years.
    """
    try:
        age = float(age)
    except TypeError:
        age = human.getModifier('macrodetails/Age').getDefaultValue()
    if age < 0.5:
        return human.MIN_AGE + ((human.MID_AGE - human.MIN_AGE) * 2) * age
    else:
        return human.MID_AGE + (
            (human.MAX_AGE - human.MID_AGE) * 2) * (age - 0.5)


def get_age(ageYears, human):
    """
    Set age in amount of years.
    """
    ageYears = float(ageYears)
    if ageYears < human.MIN_AGE or ageYears > human.MAX_AGE:
        raise RuntimeError(
            "Invalid age specified, should be minimum %s and maximum %s." %
            (human.MIN_AGE, human.MAX_AGE))
    if ageYears < human.MID_AGE:
        age = (ageYears - human.MIN_AGE) / (
            (human.MID_AGE - human.MIN_AGE) * 2)
    else:
        age = ((ageYears - human.MID_AGE) /
               ((human.MAX_AGE - human.MID_AGE) * 2)) + 0.5
    return age

def clean_modifier(s):
    """Clean modifier names."""
    # Remove invalid characters
    s = re_NonAlphaNumeric.sub('', s)

    # Remove leading characters until we find a letter or underscore
    # s = re.sub('^[^a-zA-Z_]+', '_', s)
    return s

def clean(s):
    """Remove invalid characters."""
    s = re.sub('[^0-9a-zA-Z_]', '_', s)
    return s


def short_hash(s, n=3):
    """Generate a short hash."""
    import hashlib
    import base64
    hasher = hashlib.sha1(s)
    short_h = base64.urlsafe_b64encode(hasher.digest()).rstrip('=')[0:n]
    return short_h


def getRandomOutput(name="human.obj", ext='.obj', base_dir='.'):
    """Random output name."""
    if not name.endswith(ext):
        name = name + ext
    u = uuid.uuid4()
    o = os.path.join(base_dir, 'static', 'models', u.hex + '.' + name)
    return o


def TryFloat(s):
    """Coerce to float."""
    try:
        f = float(s)
        return f
    except ValueError:
        return s
    except:
        print s
        return s
