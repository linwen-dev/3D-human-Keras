#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Manuel Bastioni, Marc Flerackers

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

TODO
"""

import random
#import gui3d
#import gui
#from core import G


def assignModifierValues(human, valuesDict):
    _tmp = human.symmetryModeEnabled
    human.symmetryModeEnabled = False
    for mName, val in valuesDict.items():
        try:
            human.getModifier(mName).setValue(val)
        except:
            pass
    human.applyAllTargets()
    human.symmetryModeEnabled = _tmp
    return human



def randomize(human, symmetry, macro, height, face, body):
    modifierGroups = []
    if macro:
        modifierGroups = modifierGroups + ['macrodetails', 'macrodetails-universal', 'macrodetails-proportions']
    if height:
        modifierGroups = modifierGroups + ['macrodetails-height']
    if face:
        modifierGroups = modifierGroups + ['eyebrows', 'eyes', 'chin',
                         'forehead', 'head', 'mouth', 'nose', 'neck', 'ears',
                         'cheek']
    if body:
        modifierGroups = modifierGroups + ['pelvis', 'hip', 'armslegs', 'stomach', 'breast', 'buttocks', 'torso']

    modifiers = []
    for mGroup in modifierGroups:
        modifiers = modifiers + human.getModifiersByGroup(mGroup)
    # Make sure not all modifiers are always set in the same order
    # (makes it easy to vary dependent modifiers like ethnics)
    random.shuffle(modifiers)

    randomValues = {}
    for m in modifiers:
        if m.fullName not in randomValues:
            randomValue = None
            if m.groupName == 'head':
                sigma = 0.1
            elif m.fullName in ["forehead/forehead-nubian-less|more", "forehead/forehead-scale-vert-less|more"]:
                sigma = 0.02
                # TODO add further restrictions on gender-dependent targets like pregnant and breast
            elif "trans-horiz" in m.fullName or m.fullName == "hip/hip-trans-in|out":
                if symmetry == 1:
                    randomValue = m.getDefaultValue()
                else:
                    mMin = m.getMin()
                    mMax = m.getMax()
                    w = float(abs(mMax - mMin) * (1 - symmetry))
                    mMin = max(mMin, m.getDefaultValue() - w/2)
                    mMax = min(mMax, m.getDefaultValue() + w/2)
                    randomValue = getRandomValue(mMin, mMax, m.getDefaultValue(), 0.1)
            elif m.groupName in ["forehead", "eyebrows", "neck", "eyes", "nose", "ears", "chin", "cheek", "mouth"]:
                sigma = 0.1
            elif m.groupName == 'macrodetails':
                # TODO perhaps assign uniform random values to macro modifiers?
                #randomValue = random.random()
                sigma = 0.3
            #elif m.groupName == "armslegs":
            #    sigma = 0.1
            else:
                #sigma = 0.2
                sigma = 0.1

            if randomValue is None:
                randomValue = getRandomValue(m.getMin(), m.getMax(), m.getDefaultValue(), sigma)   # TODO also allow it to continue from current value?
            randomValues[m.fullName] = randomValue
            symm = m.getSymmetricOpposite()
            if symm and symm not in randomValues:
                if symmetry == 1:
                    randomValues[symm] = randomValue
                else:
                    m2 = human.getModifier(symm)
                    symmDeviation = float((1-symmetry) * abs(m2.getMax() - m2.getMin()))/2
                    symMin =  max(m2.getMin(), min(randomValue - (symmDeviation), m2.getMax()))
                    symMax =  max(m2.getMin(), min(randomValue + (symmDeviation), m2.getMax()))
                    randomValues[symm] = getRandomValue(symMin, symMax, randomValue, sigma)

    if randomValues.get("macrodetails/Gender", 0) > 0.5 or \
       randomValues.get("macrodetails/Age", 0.5) < 0.2 or \
       randomValues.get("macrodetails/Age", 0.7) < 0.75:
        # No pregnancy for male, too young or too old subjects
        if "stomach/stomach-pregnant-decr|incr" in randomValues:
            randomValues["stomach/stomach-pregnant-decr|incr"] = 0

    oldValues = dict( [(m.fullName, m.getValue()) for m in modifiers] )

    return randomValues

    #gui3d.app.do( RandomizeAction(human, oldValues, randomValues) )

def getRandomValue(minValue, maxValue, middleValue, sigmaFactor = 0.2):
    rangeWidth = float(abs(maxValue - minValue))
    sigma = sigmaFactor * rangeWidth
    randomVal = random.gauss(middleValue, sigma)
    if randomVal < minValue:
        randomVal = minValue + abs(randomVal - minValue)
    elif randomVal > maxValue:
        randomVal = maxValue - abs(randomVal - maxValue)
    return max(minValue, min(randomVal, maxValue))

def load(app):
    category = app.getCategory('Modelling')
    taskview = category.addTask(RandomTaskView(category))

def unload(app):
    pass
