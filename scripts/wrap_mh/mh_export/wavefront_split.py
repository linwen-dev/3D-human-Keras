#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
"""
Extended wavefont file to output three.js json files and other changes
"""

"""
Handles WaveFront .obj 3D mesh files.

**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Manuel Bastioni, Marc Flerackers, Jonas Hauquier

**Copyright(c):**      MakeHuman Team 2001-2015

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

"""

import os
import codecs
import math
#import numpy as np
from codecs import open  # TODO should Wavefront OBJ files contain unicode characters, or would it be better to strip them?
import wrap_mh
from wrap_mh.convert import convert_obj_three

def loadObjFile(path, obj = None):
    """
    Parse and load a Wavefront OBJ file as mesh.
    Parser does not support normals, and assumes all objects should be smooth
    shaded. Use duplicate vertices for achieving hard edges.
    """
    if obj == None:
        import module3d
        name = os.path.splitext( os.path.basename(path) )[0]
        obj = module3d.Object3D(name)

    objFile = open(path, 'rU', encoding="utf-8")

    fg = None
    mtl = None

    verts = []
    uvs = []
    fverts = []
    fuvs = []
    groups = []
    has_uv = False
    materials = {}
    faceGroups = {}

    for objData in objFile:

        lineData = objData.split()
        if len(lineData) > 0:

            command = lineData[0]

            # Vertex coordinate
            if command == 'v':
                verts.append((float(lineData[1]), float(lineData[2]), float(lineData[3])))

            # Vertex texture (UV) coordinate
            elif command == 'vt':
                uvs.append((float(lineData[1]), float(lineData[2])))

            # Face definition (reference to vertex attributes)
            elif command == 'f':
                if not fg:
                    if 0 not in faceGroups:
                        faceGroups[0] = obj.createFaceGroup('default-dummy-group')
                    fg = faceGroups[0]

                uvIndices = []
                vIndices = []
                for faceData in lineData[1:]:
                    vInfo = faceData.split('/')
                    vIdx = int(vInfo[0]) - 1  # -1 because obj is 1 based list
                    vIndices.append(vIdx)

                    # If there are other data (uv, normals, etc)
                    if len(vInfo) > 1 and vInfo[1] != '':
                        uvIndex = int(vInfo[1]) - 1  # -1 because obj is 1 based list
                        uvIndices.append(uvIndex)

                if len(vIndices) == 3:
                    vIndices.append(vIndices[0])
                fverts.append(tuple(vIndices))

                if len(uvIndices) > 0:
                    if len(uvIndices) == 3:
                        uvIndices.append(uvIndices[0])
                    has_uv = True
                if len(uvIndices) < 4:
                    uvIndices = [0, 0, 0, 0]
                fuvs.append(tuple(uvIndices))

                groups.append(fg.idx)

            elif command == 'g':
                fgName = lineData[1]
                if fgName not in faceGroups:
                    faceGroups[fgName] = obj.createFaceGroup(fgName)
                fg =  faceGroups[fgName]

            elif command == 'usemtl':
                pass # ignore materials

            elif command == 'o':

                obj.name = lineData[1]

    objFile.close()

    # Sanity check for loose vertices
    strayVerts = []
    referencedVerts = set([ v for fvert in fverts for v in fvert ])
    for vIdx in xrange(len(verts)):
        if vIdx not in referencedVerts:
            strayVerts.append(vIdx)
    if len(strayVerts) > 0:
        import log
        msg = "Error loading OBJ file %s: Contains loose vertices, not connected to a face (%s)"
        log.error(msg, path, strayVerts)
        raise RuntimeError(msg % (path, strayVerts))

    obj.setCoords(verts)
    obj.setUVs(uvs)
    obj.setFaces(fverts, fuvs if has_uv else None, groups)

    obj.calcNormals()
    obj.updateIndexBuffer()

    return obj

TEMPLATE_FILE_JSON = u"""\
{

    "metadata" :
    {
        "formatVersion" : 3.1,
        "sourceFile"    : "%(fname)s",
        "generatedBy"   : "OBJConverter",
        "vertices"      : %(nvertex)d,
        "faces"         : %(nface)d,
        "normals"       : %(nnormal)d,
        "uvs"           : %(nuv)d,
        "materials"     : %(nmaterial)d
    },

    "materials": [%(materials)s],

    "data": "%(data)s"

}
"""

def writeJsonFile(path,materialsstr,nfaces,nvertices,normals,nnuvs,nmeterials):
    """Write json file for three.js binary files CTMLoader."""
    text = TEMPLATE_FILE_JSON % {
        "name"      : __file__,

        "materials" : materialsstr,
        "data"      : os.path.split(path.replace('.js','.ctm'))[1],

        "fname"     : os.path.basename(path),
        "nvertex"   : nvertices,
        "nface"     : nfaces,
        "nmaterial" : nmeterials,
        "nnormal"   : normals,
        "nuv"       : nnuvs
        }
    if isinstance(path, file):
        out=path
    else:
        out=open(path,'w')
    out.write(text)
    out.close()
    return text

def writeObjFile(path, meshes, writeMTL=True, config=None, filterMaskedFaces=True):
    if not isinstance(meshes, list):
        meshes = [meshes]

    mtlfile = path.replace(".obj",".mtl")

    scale = config.scale if config is not None else 1.0

    # Scale and filter out masked faces and unused verts
    if scale == 1.0 and not filterMaskedFaces:
        pass
    elif filterMaskedFaces:
        meshes = [m.clone(scale=scale, filterMaskedVerts=True) for m in meshes]
    else:
        # Unfiltered
        meshes = [m.clone(scale=scale, filterMaskedVerts=False) for m in meshes]

    if config and config.feetOnGround:
        offset = config.offset
    else:
        offset = [0,0,0]


    # write each mesh to a seperate obj file
    nfaces=0
    nvertices= 0
    normals=0
    nnuvs=0
    nmeterials=0
    files=[]
    for i, mesh in enumerate(meshes):
        if i==0:
            objfile = "%s.obj" % path.replace('.obj','')
        else:
            objfile = "%s__%s.obj" % (path.replace('.obj',''), mesh.name.replace('.obj',''))
        # TODO let us be given a stream here
        fp=open(objfile, 'w', encoding="utf-8")
        files.append(objfile)

        fp.write(
        "# MakeHuman exported OBJ\n" +
        "# www.makehuman.org\n\n")

        if writeMTL:
            fp.write("mtllib %s\n" % os.path.basename(mtlfile))

        # Vertices
        fp.write("".join( ["v %.4f %.4f %.4f\n" % tuple(co + offset) for co in mesh.coord] ))

        # Vertex normals
        if config is None or config.useNormals:
            fp.write("".join( ["vn %.4f %.4f %.4f\n" % tuple(no) for no in mesh.vnorm] ))

        # UV vertices
        if mesh.has_uv:
            fp.write("".join( ["vt %.6f %.6f\n" % tuple(uv) for uv in mesh.texco] ))

        # Faces
        nVerts = 1
        nTexVerts = 1
        fp.write("usemtl %s\n" % mesh.material.name)
        fp.write("g %s\n" % mesh.name)

        if config is None or config.useNormals:
            if mesh.has_uv:
                for fn,fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    fuv = mesh.fuvs[fn]
                    line = [" %d/%d/%d" % (fv[n]+nVerts, fuv[n]+nTexVerts, fv[n]+nVerts) for n in range(4)]
                    fp.write("f" + "".join(line) + "\n")
            else:
                for fn,fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    line = [" %d//%d" % (fv[n]+nVerts, fv[n]+nVerts) for n in range(4)]
                    fp.write("f" + "".join(line) + "\n")
        else:
            if mesh.has_uv:
                for fn,fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    fuv = mesh.fuvs[fn]
                    line = [" %d/%d" % (fv[n]+nVerts, fuv[n]+nTexVerts) for n in range(4)]
                    fp.write("f" + "".join(line) + "\n")
            else:
                for fn,fv in enumerate(mesh.fvert):
                    if not mesh.face_mask[fn]:
                        continue
                    line = [" %d" % (fv[n]+nVerts) for n in range(4)]
                    fp.write("f" + "".join(line) + "\n")

        nVerts += len(mesh.coord)
        nTexVerts += len(mesh.texco)

        nfaces+=len(mesh.fvert)
        nvertices+= len(mesh.coord)
        normals+=len(mesh.vnorm)
        nnuvs+=len(mesh.texco)
        nmeterials+=1

        fp.close()



    if writeMTL:
        if isinstance(writeMTL, file):
            fp=writeMTL
        else:
            fp = open(mtlfile, 'w', encoding="utf-8")
        fp.write(
            '# MakeHuman exported MTL\n' +
            '# www.makehuman.org\n\n')
        for mesh in meshes:
            writeMaterial(fp, mesh.material, config)
        fp.close()
        files.append(mtlfile)

    # now convert obj's to threejs

    materials=dict([ (str(mesh.material.name),i) for i,mesh in enumerate(meshes)])

    basename=os.path.dirname(mtlfile)

    mtlfilename=os.path.basename(mtlfile)
    materialsstr=convert_obj_three.generate_materials_string(materials,mtlfile,basename)
    jsfile=path.replace('.obj','.js')
    writeJsonFile(path=jsfile,materialsstr=materialsstr,nfaces=nfaces,nvertices=nvertices,normals=normals,nnuvs=nnuvs,nmeterials=nmeterials)
    files.append(jsfile)
    return files


def writeMaterial(fp, mat, texPathConf = None):
    fp.write("\nnewmtl %s\n" % mat.name)
    diff = mat.diffuseColor
    spec =  mat.specularColor
    amb = mat.ambientColor
    emi = mat.emissiveColor
    # alpha=0 is necessary for correct transparency in Blender.
    # But may lead to problems with other apps.
    if mat.diffuseTexture:
        alpha = 0
    else:
        alpha = mat.opacity
    fp.write(
        "Kd %.4g %.4g %.4g\n" % (diff.r, diff.g, diff.b) +
        "Ks %.4g %.4g %.4g\n" % (spec.r, spec.g, spec.b) +
        "Ka %.4g %.4g %.4g\n" % (amb.r, amb.g, amb.b) +
        "Ke %.4g %.4g %.4g\n" % (emi.r, emi.g, emi.b) +
        "d %.4g\n" % alpha

    )

    writeTexture(fp, "map_Kd", mat.diffuseTexture, texPathConf)
    writeTexture(fp, "map_Ks", mat.specularMapTexture, texPathConf)
    #writeTexture(fp, "map_Tr", mat.translucencyMapTexture, texPathConf)
    # Disabled because Blender interprets map_Disp as map_D
    if mat.normalMapTexture:
        texPathConf.copyTextureToNewLocation(mat.normalMapTexture)
    #writeTexture(fp, "map_Disp", mat.specularMapTexture, texPathConf)
    #writeTexture(fp, "map_Disp", mat.displacementMapTexture, texPathConf)

    #writeTexture(fp, "map_Kd", os.path.join(getpath.getSysDataPath("textures"), "texture.png"), texPathConf)


def writeTexture(fp, key, filepath, pathConfig = None):
    if not filepath:
        return

    if pathConfig:
        newpath = pathConfig.copyTextureToNewLocation(filepath) # TODO use shared code for exporting texture files
        fp.write("%s %s\n" % (key, newpath))
    else:
        fp.write("%s %s\n" % (key, filepath))
