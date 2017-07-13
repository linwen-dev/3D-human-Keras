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



def assignModifierValues(self, valuesDict):
    _tmp = self.human.symmetryModeEnabled
    self.human.symmetryModeEnabled = False
    for mName, val in valuesDict.items():
        try:
            self.human.getModifier(mName).setValue(val)
        except:
            pass
    self.human.applyAllTargets()
    self.human.symmetryModeEnabled = _tmp

def randomizeArgs(args1,args2, human,symmetry=1, macro=1, height=1, face=1, body=1, baby=True):
    """
    Randomise attributes from two parents args
    TODO get it working
    """
    args1d=dict(args1)
    args2d=dict(args2)
    
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

    modifiers2 = []
    for mGroup in modifierGroups:
        modifiers2 = modifiers2 + human.getModifiersByGroup(mGroup)
    
    # now only do modifiers set in parents
    modifiers = []
    for m in modifiers2:
        if (m.fullName in args1d) or (m.fullName in args2d):
            modifiers.append(m)
    # Make sure not all modifiers are always set in the same order 
    # (makes it easy to vary dependent modifiers like ethnics)
    indices=range(len(modifiers))
    random.shuffle(indices)

    def getMin(m):
        return m.getMin()
    
    def getMax(m):
        return m.getMax()

    def getDefaultValue(m):
        """
        Instead of centered on the default, the gaussian distribution will be around the mean of the parents traits.
        """
        ma=args1d.get(m.fullName,m.getDefaultValue())
        mb=args2d.get(m.fullName,m.getDefaultValue())
        return (ma+mb)/2
    
    def getRange(m):
        """
        Get range of parent values as a % of full range to modify sigma with
        """
        ma=args1d.get(m.fullName,m.getDefaultValue())
        mb=args2d.get(m.fullName,m.getDefaultValue())
        return abs(ma-mb)/abs(m.getMin()-m.getMax())

    randomValues = {}
    for i in indices:
        m=modifiers[i]
        sm=getRange(m)*2.3+0.05# tweaked by experimentation for now added a bit of mutation to the range of parents values
        if m.fullName not in randomValues:
            randomValue = None
            if m.groupName == 'head':
                sigma = 0.1*sm
            elif m.fullName in ["forehead/forehead-nubian-less|more", "forehead/forehead-scale-vert-less|more"]:
                sigma = 0.02*sm
                # TODO add further restrictions on gender-dependent targets like pregnant and breast
            elif "trans-horiz" in m.fullName or m.fullName == "hip/hip-trans-in|out":
                if symmetry == 1:
                    randomValue = getDefaultValue(m)
                else:
                    mMin = getMin(m)
                    mMax = getMax(m)
                    w = float(abs(mMax - mMin) * (1 - symmetry))
                    mMin = max(mMin, getDefaultValue(m) - w/2)
                    mMax = min(mMax, getDefaultValue(m) + w/2)
                    randomValue = getRandomValue(mMin, mMax, getDefaultValue(m), 0.1*sm)
            elif m.groupName in ["forehead", "eyebrows", "neck", "eyes", "nose", "ears", "chin", "cheek", "mouth"]:
                sigma = 0.1*sm
            elif m.groupName == 'macrodetails':
                # TODO perhaps assign uniform random values to macro modifiers?
                #randomValue = random.random()
                sigma = 0.3*sm
            #elif m.groupName == "armslegs":
            #    sigma = 0.1*sm
            else:
                #sigma = 0.2
                sigma = 0.1*sm

            if randomValue is None:
                randomValue = getRandomValue(getMin(m), getMax(m), getDefaultValue(m), sigma)   # TODO also allow it to continue from current value?
            randomValues[m.fullName] = randomValue
            
            # Now lets get the opposite modifier and make it as symetric as asked            
            symm = m.getSymmetricOpposite()
            if symm and symm not in randomValues:
                if symmetry == 1:
                    randomValues[symm] = randomValue
                else:
                    m2  = parent1.getModifier(symm)
                    symmDeviation = float((1-symmetry) * abs(getMax(m2) - getMin(m2)))/2
                    symMin =  max(getMin(m2), min(randomValue - (symmDeviation), getMax(m2)))
                    symMax =  max(getMin(m2), min(randomValue + (symmDeviation), getMax(m2)))
                    randomValues[symm] = getRandomValue(symMin, symMax, randomValue, sigma)

    if randomValues.get("macrodetails/Gender", 0) > 0.5 or \
       randomValues.get("macrodetails/Age", 0.5) < 0.2 or \
       randomValues.get("macrodetails/Age", 0.7) < 0.75 or \
       baby:
        # No pregnancy for male, too young or too old subjects
        if "stomach/stomach-pregnant-decr|incr" in randomValues:
            randomValues["stomach/stomach-pregnant-decr|incr"] = 0
    
    return randomValues


def getRandomValue(minValue, maxValue, middleValue, sigmaFactor = 0.2):
    rangeWidth = float(abs(maxValue - minValue))
    sigma = sigmaFactor * rangeWidth
    randomVal = random.gauss(middleValue, sigma)
    if randomVal < minValue:
        randomVal = minValue + abs(randomVal - minValue)
    elif randomVal > maxValue:
        randomVal = maxValue - abs(randomVal - maxValue)
    return max(minValue, min(randomVal, maxValue))


