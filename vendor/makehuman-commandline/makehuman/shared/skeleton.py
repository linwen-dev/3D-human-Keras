#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Thomas Larsson, Jonas Hauquier

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

General skeleton, rig or armature class.
A skeleton is a hierarchic structure of bones, defined between a head and tail
joint position. Bones can be detached from each other (their head joint doesn't
necessarily need to be at the same position as the tail joint of their parent
bone).

A pose can be applied to the skeleton by setting a pose matrix for each of the
bones, allowing static posing or animation playback.
The skeleton supports skinning of a mesh using a list of vertex-to-bone
assignments.
"""

import math
from math import pi

import numpy as np
import numpy.linalg as la
import transformations as tm
import matrix
import animation
from animation import VertexBoneWeights
import makehuman

import log

D = pi/180


class Skeleton(object):

    def __init__(self, name="Skeleton"):
        self.name = name
        self._clear()
        self.scale = 1.0

    def _clear(self):
        self.description = ""
        self.version = "1"
        self.license = makehuman.getAssetLicense()

        self.bones = {}     # Bone lookup list by name
        self.boneslist = None  # Breadth-first ordered list of all bones
        self.roots = []     # Root bones of this skeleton, a skeleton can have multiple root bones.

        self.joint_pos_idxs = {}  # Lookup by joint name referencing vertex indices on the human, to determine joint position
        self.planes = {}    # Named planes defined between joints, used for calculating bone roll angle
        self.plane_map_strategy = 3  # The remapping strategy used by addReferencePlanes() for remapping orientation planes from a reference skeleton

        self.vertexWeights = None  # Source vertex weights, defined on the basemesh, for this skeleton
        self.has_custom_weights = False  # True if this skeleton has its own .mhw file

    def fromFile(self, filepath, mesh=None):
        """
        Load skeleton from json rig file.
        """
        import json
        from collections import OrderedDict
        import getpath
        import os
        self._clear()
        skelData = json.load(open(filepath, 'rb'), object_pairs_hook=OrderedDict)

        self.name = skelData.get("name", self.name)
        self.version = int(skelData.get("version", self.version))
        self.description = skelData.get("description", self.description)
        self.plane_map_strategy = int(skelData.get("plane_map_strategy", self.plane_map_strategy))

        self.license.fromJson(skelData)

        for joint_name, v_idxs in skelData.get("joints", dict()).items():
            if isinstance(v_idxs, list) and len(v_idxs) > 0:
                self.joint_pos_idxs[joint_name] = v_idxs

        self.planes = skelData.get("planes", dict())

        # Order bones breadth-first
        breadthfirst_bones = []
        prev_len = -1   # anti-deadlock
        while(len(breadthfirst_bones) != len(skelData["bones"]) and prev_len != len(breadthfirst_bones)):
            prev_len = len(breadthfirst_bones)
            for bone_name, bone_defs in skelData["bones"].items():
                if bone_name not in breadthfirst_bones:
                    if not bone_defs.get("parent", None):
                        breadthfirst_bones.append(bone_name)
                    elif bone_defs["parent"] in breadthfirst_bones:
                        breadthfirst_bones.append(bone_name)
        if len(breadthfirst_bones) != len(skelData["bones"]):
            missing = [bname for bname in skelData["bones"].keys() if bname not in breadthfirst_bones]
            log.warning("Some bones defined in file %s could not be added to skeleton %s, because they have an invalid parent bone (%s)", filepath, self.name, ', '.join(missing))

        for bone_name in breadthfirst_bones:
            bone_defs = skelData["bones"][bone_name]
            rotation_plane = bone_defs.get("rotation_plane", 0)
            if rotation_plane == [None, None, None]:
                log.warning("Invalid rotation plane specified for bone %s. Please make sure that you edited the .mhskel file by hand to include roll plane joints." % bone_name)
                rotation_plane = 0
            self.addBone(bone_name, bone_defs.get("parent", None), bone_defs["head"], bone_defs["tail"], rotation_plane, bone_defs.get("reference",None), bone_defs.get("weights_reference",None))

        self.build()

        if "weights_file" in skelData and skelData["weights_file"]:
            weights_file = skelData["weights_file"]
            weights_file = getpath.thoroughFindFile(weights_file, os.path.dirname(getpath.canonicalPath(filepath)), True)

            self.vertexWeights = VertexBoneWeights.fromFile(weights_file, mesh.getVertexCount() if mesh else None, rootBone=self.roots[0].name)
            self.has_custom_weights = True

    def toFile(self, filename, ref_weights=None):
        """
        Export skeleton and its weights to JSON.
        Specify ref_weights (the weights of the default or reference rig
        for vertices of the basemesh) if this is an arbitrary skeleton
        and its weights were not mapped yet.
        """
        import json
        from collections import OrderedDict
        import os

        fn = os.path.splitext(os.path.basename(filename))[0]
        weights_file = "%s_weights.mhw" % fn

        jsondata = OrderedDict({ "name": self.name,
                                 "version": self.version,
                                 "description": self.description,
                                 "plane_map_strategy": self.plane_map_strategy,
                               })
        jsondata.update(self.license.asDict())

        jsondata["weights_file"] = weights_file

        bones = OrderedDict()
        for bone in self.getBones():
            bonedef = {"head": bone.headJoint,
                       "tail": bone.tailJoint,
                      }
            if bone.reference_bones:
                bonedef["reference"] = bone.reference_bones
            if bone.parent:
                bonedef["parent"] = bone.parent.name
            if bone.roll:
                bonedef["rotation_plane"] = bone.roll
            if bone.weight_reference_bones != bone.reference_bones:
                bonedef["weights_reference"] = bone.weight_reference_bones

            bones[bone.name] = bonedef
        jsondata["bones"] = bones

        jsondata["joints"] = self.joint_pos_idxs
        jsondata["planes"] = self.planes

        f = open(filename, 'w')
        json.dump(jsondata, f, indent=4, separators=(',', ': '))
        f.close()

        # Save weights
        weights = self.getVertexWeights(ref_weights)
        weights.toFile(os.path.join(os.path.dirname(filename), weights_file))

    def getVertexWeights(self, referenceWeights=None, force_remap=False):
        """
        Get the vertex weights of this skeleton. If this is called for the first
        time, and referenceWeights is specified (weight of the mh reference rig), 
        and the weights for this skeleton were not explicitly defined, the
        weights will be initialized as a remapping of the reference weights
        through specified reference bones.
        When force_remap is True, weights will always be returned as referenceWeights
        remapped to this skeleton, this is for example needed when passing proxy
        vertexweights through this method.
        Returns the vertex weights for this skeleton.
        """
        from collections import OrderedDict
        if referenceWeights is None:
            return self.vertexWeights
        if not force_remap and self.vertexWeights is not None:
            return self.vertexWeights

        # Remap vertex weights from reference bones
        weights = OrderedDict()

        for bone in self.getBones():
            b_weights = []
            if len(bone.weight_reference_bones) > 0:
                add_count = 0
                for rbname in bone.weight_reference_bones:
                    if rbname in referenceWeights.data:
                        vrts,wghs = referenceWeights.data[rbname]
                        b_weights.extend( zip(vrts,wghs) )
                        add_count += 1
                    else:
                        if not makehuman.isRelease():
                            # This warning is emitted when the reference skeleton does not have a bone
                            # with name rbname. In other words: this skeleton references a bone that does
                            # not exist.
                            # Often this warning is harmless, and is the result of the autoBuildWeightReferences()
                            # method, in which case it simply means that the default skeleton has some bones that have
                            # no weights and that therefore it cannot copy any weights for that reference bone to this
                            # bone. It might be a problem if this bone references only bones with no weights, though.
                            log.debug("Weight reference bone %s, referenced by %s is not present in reference weights. This is probably harmless.", rbname, bone.name)
                if add_count == 0:
                    if not makehuman.isRelease():
                        # This is emitted when this bone has a few weight references, but all of these referenced bones
                        # have no weights attached to them in the reference skeleton. Therefore this bone will not
                        # receive any weights. This is ok if this is supposed to be a "pentograph" bone, and is not
                        # supposed to have any weights.
                        log.warning("No weights could be mapped to bone %s because all of its weight reference bones had no weights. This bone will not have any weights.", bone.name)
            else:
                # Try to map by bone name
                if bone.name in referenceWeights.data:
                    # Implicitly map bone by name to reference skeleton weights
                    vrts,wghs = referenceWeights.data[bone.name]
                    b_weights = zip(vrts,wghs)
                else:
                    if not makehuman.isRelease():
                        # This warning is emitted when no matching bones in the reference skeleton can be found, and
                        # this bone cannot be mapped to any reference bone. This is because the skeleton definition
                        # does not explicitly define a set of reference bones for this bone, and the reference skeleton
                        # does not hava a bone with the same name as this bone. This bone will not receive any weights.
                        # This warning is rather serious: it means that one of the bones in your seleton will not have
                        # weights.
                        log.warning("No explicit weight reference bone mapping for bone %s, and cannot implicitly map by name. This bone will not have any weights. This might be normal if this is for example a proxy only weighted to a few bones.", bone.name)

            if len(b_weights) > 0:
                weights[bone.name] = b_weights

        vertWeights = referenceWeights.create(weights, vertexCount=referenceWeights.vertexCount, rootBone=self.roots[0].name)
        if self.vertexWeights is None:
            self.vertexWeights = vertWeights
        return vertWeights

    def hasCustomVertexWeights(self):
        return self.has_custom_weights

    def autoBuildWeightReferences(self, referenceSkel):
        """
        Complete the vertex reference weights by taking the (pose) reference
        weights defined on this skeleton, and potentially complete them with
        extra bones from the reference skeleton.
        If a bone of this skeleton references a bone in the reference skeleton,
        and that referenced bone has a chain or chains of bones until an end
        connector (a bone with no children) that are all unreferenced by this
        skeleton, then all those bones are added as vertex weight reference
        bones. Only affects bones that have not explicitly defined weight
        reference bones.
        :param referenceSkel: Reference skeleton to obtain structure from.
         This is the default or master skeleton.
        """
        included = dict()
        for bone in self.getBones():
            if bone._weight_reference_bones is None:
                included[bone.name] = True
                bone._weight_reference_bones = list(bone.reference_bones)
            else:
                included[bone.name] = False

        def _update_reverse_ref_map(skel):
            result = dict()
            for bone in skel.getBones():
                for ref in bone.weight_reference_bones:
                    if ref not in result:
                        result[ref] = []
                    result[ref].append(bone.name)
            return result

        reverse_ref_map = _update_reverse_ref_map(self)

        def _hasUnreferencedTail(bone, reverse_ref_map, first_bone=False):
            """Returns True if there is a chain of child bones of this bone,
            up to an end connector, that are not referenced.
            """
            # TODO perhaps relax the unreferenced criterium if the bone referrer bone is the same that references the first bone
            if not first_bone and (bone.name in reverse_ref_map and len(reverse_ref_map) > 0):
                return False
            #if first_bone and not bone.hasChildren():
            #    return False  # Exclude trivial case
            if bone.hasChildren():
                return any( [_hasUnreferencedTail(child, reverse_ref_map) for child in bone.children] )
            else:
                # This is an end-connector
                return True

        def _getAllChildren(bone, reverse_ref_map):
            result = []
            for child in bone.children:
                result.append(child)
                result.extend( _getAllChildren(child, reverse_ref_map) )
            return result

        def _getUnreferencedChildren(bone, reverse_ref_map):
            result = _getAllChildren(bone, reverse_ref_map)
            return [ b.name for b in result if _hasUnreferencedTail(b, reverse_ref_map) ]

        for rbone in reversed(referenceSkel.getBones()):  # Traverse from children to parent
            if rbone.name not in reverse_ref_map:
                continue
            if _hasUnreferencedTail(rbone, reverse_ref_map, first_bone=True):
                extra_vertweight_refs = _getUnreferencedChildren(rbone, reverse_ref_map)
                #log.debug("%s -> %s", reverse_ref_map[rbone.name], extra_vertweight_refs)
                for bone_name in reverse_ref_map[rbone.name]:
                    bone = self.getBone(bone_name)
                    if included[bone.name]:
                        bone._weight_reference_bones.extend(extra_vertweight_refs)
                        bone._weight_reference_bones = list(set(bone._weight_reference_bones))
                reverse_ref_map = _update_reverse_ref_map(self)  # Make sure that another parent bone cannot be weighted to these again

    def addReferencePlanes(self, referenceSkel):
        """
        Add bone rotation reference planes to map from a reference rig to
        this skeleton, using specified reference bones.
        """
        def _add_plane_from_ref(plane_name):
            self.planes[plane_name] = []
            for joint in referenceSkel.planes[plane_name]:
                if joint not in transferred_joints:
                    if joint in self.joint_pos_idxs:
                        # Create new joint name, so we don't override the 
                        # original one in this skeleton (which might have a 
                        # different position)
                        idx = 1
                        while "%s_%s" % (joint, idx) in self.joint_pos_idxs:
                            idx += 1
                        transferred_joints[joint] = "%s_%s" % (joint, idx)
                        #log.message("Renaming plane joint %s from ref skeleton to %s" % (joint, transferred_joints[joint]))
                    else:
                        transferred_joints[joint] = joint
                new_joint = transferred_joints[joint]
                self.joint_pos_idxs[new_joint] = referenceSkel.joint_pos_idxs[joint]
                self.planes[plane_name].append(new_joint)

        def _remap_plane_strategy_1(bone, ref_bone_names):
            # Strategy 1: use the first ref bone only
            try:
                ref_bone = referenceSkel.getBone(ref_bone_names[0])
            except KeyError:
                log.warning("Bone %s has an unresolved reference %s, cannot remap an orientation plane" % (bone.name, ref_bone_names[0]))
                return
            bone.roll = ref_bone.roll
            _add_plane_from_ref(bone.roll)

        def _remap_plane_strategy_2(bone, ref_bone_names):
            # Strategy 2: use the last ref bone only
            try:
                ref_bone = referenceSkel.getBone(ref_bone_names[-1])
            except KeyError:
                log.warning("Bone %s has an unresolved reference %s, cannot remap an orientation plane" % (bone.name, ref_bone_names[-1]))
                return
            bone.roll = ref_bone.roll
            _add_plane_from_ref(bone.roll)

        def _remap_plane_strategy_3(bone, ref_bone_names):
            # Strategy 3: average the normal of all the planes
            bone.roll = list()
            remaps = 0
            for ref_bone in ref_bone_names:
                try:
                    ref_bone = referenceSkel.getBone(ref_bone)
                except KeyError:
                    continue
                bone.roll.append(ref_bone.roll)
                _add_plane_from_ref(ref_bone.roll)
                remaps += 1
            if remaps == 0 and len(ref_bone_names) > 0:
                log.warning("Bone %s has no resolved references %s, cannot remap an orientation plane" % (bone.name, ref_bone_names))

        if self.plane_map_strategy == 1:
            _remap_plane = _remap_plane_strategy_1
        elif self.plane_map_strategy == 2:
            _remap_plane = _remap_plane_strategy_2
        else:
            _remap_plane = _remap_plane_strategy_3

        transferred_joints = dict()
        for bone in self.getBones():
            if not isinstance(bone.roll, basestring):
                if len(bone.reference_bones) > 0:
                    ref_bones = bone.reference_bones
                else:
                    # Try to map bones by name
                    ref_bones = [bone.name]

                _remap_plane(bone, ref_bones)

        # Rebuild skeleton matrices with new bone orientations
        self.build()

    def getJointPosition(self, joint_name, human, rest_coord=True):
        """
        Calculate the position of specified named joint from the current
        state of the human mesh. If this skeleton contains no vertex mapping
        for that joint name, it falls back to looking for a vertex group in the
        human basemesh with that joint name.
        """
        if not joint_name:
            raise RuntimeError("Cannot get joint position, no reference vertices or joint name specified.")
        if joint_name in self.joint_pos_idxs:
            v_idx = self.joint_pos_idxs[joint_name]
            if rest_coord:
                verts = human.getRestposeCoordinates()[v_idx]
            else:
                verts = human.meshData.getCoords(v_idx)
            return verts.mean(axis=0)
        else:
            return _getHumanJointPosition(human, joint_name, rest_coord)

    def __repr__(self):
        return ("  <Skeleton %s>" % self.name)

    def display(self):
        log.debug("<Skeleton %s", self.name)
        for bone in self.getBones():
            bone.display()
        log.debug(">")

    def canonalizeBoneNames(self):
        newBones = {}
        for bName, bone in self.bones.items():
            canonicalName = bName.lower().replace(' ','_').replace('-','_')
            bone.name = canonicalName
            newBones[bone.name] = bone
        self.bones = newBones

    def clone(self):
        return self.scaled(self.scale)

    def scaled(self, scale):
        """
        Create a scaled clone of this skeleton
        """
        from core import G

        result = type(self)(self.name)
        result.joint_pos_idxs = dict(self.joint_pos_idxs)
        result.vertexWeights = self.vertexWeights
        result.scale = scale
        result.version = self.version
        result.license = self.license.copy()
        result.description = self.description
        result.planes = dict(self.planes)

        for bone in self.getBones():
            parentName = bone.parent.name if bone.parent else None
            rbone = result.addBone(bone.name, parentName, bone.headJoint, bone.tailJoint, bone.roll, bone.reference_bones, bone._weight_reference_bones)
            rbone.matPose = bone.matPose.copy()
            rbone.matPose[:3,3] *= scale

        # Fit joint positions to that of original skeleton
        human = G.app.selectedHuman
        result.updateJoints(human.meshData, ref_skel=self)  # copy bone normals from self

        return result

    def transformed(self, transform_mat):
        """Create a clone of this skeleton with its joint locations transformed
        with the specified transformation matrix.
        """
        # TODO perhaps use this instead of using scaled() and the "meshOrientation" arg in all getters used by exporters?
        raise NotImplementedError()

    def createFromPose(self):
        """
        Create a clone of this skeleton with its current pose applied as rest pose.

        Note: this pose is undone when self.updateJointPositions() is called on this
        skeleton
        """
        result = self.clone()

        for bone in result.getBones():
            bone.rotateRest( self.getBone(bone.name).matPose )
            bone.setToRestPose()

        return result

    def addBone(self, name, parentName, headJoint, tailJoint, roll=0, reference_bones=None, weight_reference_bones=None):
        if name in self.bones.keys():
            raise RuntimeError("The skeleton %s already contains a bone named %s." % (self.__repr__(), name))
        bone = Bone(self, name, parentName, headJoint, tailJoint, roll, reference_bones, weight_reference_bones)
        self.bones[name] = bone
        if not parentName:
            self.roots.append(bone)
        return bone

    def build(self, ref_skel=None):
        """Rebuild bone rest matrices and determine local bone orientation
        (roll or bone normal). Pass a ref_skel to copy the bone orientation from
        the reference skeleton to the bones of this skeleton.
        """
        self.__cacheGetBones()
        for bone in self.getBones():
            bone.build(ref_skel)

    def update(self):
        """
        Update skeleton pose matrices after setting a new pose.
        """
        for bone in self.getBones():
            bone.update()

    def updateJoints(self, humanMesh, ref_skel=None):
        """
        Update skeleton rest matrices to new joint positions after modifying
        human. For a base skeleton this should happen when the mesh is in rest
        pose (but nothing prevents you from doing otherwise), for user-selected 
        export skeletons this can be done in any pose.
        Pass a ref_skel to copy its bone normals (see build).
        When a reference skeleton is passed, we assume we don't need to fit the
        joints to the basemesh rest pose coordinates, but to the posed ones.
        """
        for bone in self.getBones():
            bone.updateJointPositions(in_rest=not ref_skel)

        self.build(ref_skel)

    def getBoneCount(self):
        return len(self.getBones())

    def getPose(self):
        """
        Retrieves the current pose of this skeleton as a list of pose matrices,
        one matrix per bone, bones in breadth-first order (same order as
        getBones()).

        returns     np.array((nBones, 4, 4), dtype=float32)
        """
        nBones = self.getBoneCount()
        poseMats = np.zeros((nBones,4,4),dtype=np.float32)

        for bIdx, bone in enumerate(self.getBones()):    # TODO eliminate loop?
            poseMats[bIdx] = bone.matPose

        return poseMats

    def setPose(self, poseMats):
        """
        Set pose of this skeleton as a list of pose matrices, one matrix per
        bone with bones in breadth-first order (same order as getBones()).
        Converts the pose from global coordinates to coordinates relative to
        the local bone rest axis.

        poseMats    np.array((nBones, 4, 4), dtype=float32)
        """
        for bIdx, bone in enumerate(self.getBones()):
            bone.matPose = np.identity(4, dtype=np.float32)

            # Calculate rotations
            bone.matPose[:3,:3] = poseMats[bIdx,:3,:3]
            invRest = la.inv(bone.matRestGlobal)
            bone.matPose = np.dot(np.dot(invRest, bone.matPose), bone.matRestGlobal)

            # Add translations from original
            if poseMats.shape[2] == 4:
                # Note: we generally only have translations on the root bone
                trans = poseMats[bIdx,:3,3]
                trans = np.dot(invRest[:3,:3], trans.T)  # Describe translation in bone-local axis directions
                bone.matPose[:3,3] = trans.T
            else:
                # No translation
                bone.matPose[:3,3] = [0, 0, 0]
        # TODO avoid this loop, eg by storing a pre-allocated poseMats np array in skeleton and keeping a reference to a sub-array in each bone. It would allow batch processing of all pose matrices in one np call
        self.update()

    def isInRestPose(self):
        for bone in self.getBones():
            if not bone.isInRestPose():
                return False
        return True

    def setToRestPose(self):
        for bone in self.getBones():
            bone.setToRestPose()

    def skinMesh(self, meshCoords, vertBoneMapping):
        """
        Update (pose) assigned mesh using linear blend skinning.
        """
        nVerts = len(meshCoords)
        coords = np.zeros((nVerts,3), float)
        if meshCoords.shape[1] != 4:
            meshCoords_ = np.ones((nVerts, 4), dtype=np.float32)   # TODO also allow skinning vectors (normals)? -- in this case you need to renormalize normals, unless you only multiply each normal with the transformation with largest weight
            meshCoords_[:,:3] = meshCoords
            meshCoords = meshCoords_
            log.debug("Unoptimized data structure passed to skinMesh, this will incur performance penalty when used for animation.")
        for bname, mapping in vertBoneMapping.items():
            try:
                verts,weights = mapping
                bone = self.getBone(bname)
                vec = np.dot(bone.matPoseVerts, meshCoords[verts].transpose())
                vec *= weights
                coords[verts] += vec.transpose()[:,:3]
            except KeyError as e:
                if not makehuman.isRelease():
                    log.warning("Could not skin bone %s: no such bone in skeleton (%s)" % (bname, e))

        return coords

    def getBones(self):
        """
        Returns linear list of all bones in breadth-first order.
        """
        if self.boneslist is None:
            self.__cacheGetBones()
        return self.boneslist

    def __cacheGetBones(self):
        from Queue import deque

        result = []
        queue = deque(self.roots)
        while len(queue) > 0:
            bone = queue.popleft()
            bone.index = len(result)
            result.append(bone)
            queue.extend(bone.children)
        self.boneslist = result

    def getJointNames(self):
        """
        Returns a list of all joints defining the bone positions (minus end
        effectors for leaf bones). The names are the same as the corresponding
        bones in this skeleton.
        List is in depth-first order (usually the order of joints in a BVH file)
        """
        return self._retrieveJointNames(self.roots[0])

    def _retrieveJointNames(self, parentBone):
        result = [parentBone.name]
        for child in parentBone.children:
            result.extend(self._retrieveJointNames(child))
        return result

    def getBone(self, name):
        return self.bones[name]

    def containsBone(self, name):
        return name in self.bones

    def getBoneByReference(self, referenceBoneName):
        """
        Retrieve a bone by name, and if not present in the skeleton
        retrieves a bone that references this bone name as reference bone.
        :param referenceBoneName: bone name
        :return: Bone matching the query, None if no such bone is found
        """
        if self.containsBone(referenceBoneName):
            return self.getBone(referenceBoneName)

        for bone in self.getBones():
            if referenceBoneName in bone.reference_bones:
                return bone

        return None

    def getBoneToIdxMapping(self):
        result = {}
        boneNames = [ bone.name for bone in self.getBones() ]
        for idx, name in enumerate(boneNames):
            result[name] = idx
        return result

    def compare(self, other):
        pass
        # TODO compare two skeletons (structure only)


class Bone(object):

    def __init__(self, skel, name, parentName, headJoint, tailJoint, roll=0, reference_bones=None, weight_reference_bones=None):
        """
        Construct a new bone for specified skeleton.
        headPos and tailPos should be in world space coordinates (relative to root).
        parentName should be None for a root bone.
        """
        self.name = name
        self.skeleton = skel

        self.headJoint = headJoint
        self.tailJoint = tailJoint

        self.headPos = np.zeros(3,dtype=np.float32)
        self.tailPos = np.zeros(3,dtype=np.float32)

        self.roll = roll
        self.length = 0
        self.yvector4 = None    # Direction vector of this bone

        self.updateJointPositions()

        self.children = []
        if parentName:
            self.parent = skel.getBone(parentName)
            self.parent.children.append(self)
        else:
            self.parent = None

        self.index = None   # The index of this bone in the breadth-first bone list
        self.level = None   # The level in the hierarchy (number of parent levels)
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0

        self.reference_bones = []  # Used for mapping animations and poses
        if reference_bones is not None:
            if not isinstance(reference_bones, list):
                reference_bones = [ reference_bones ]
            self.reference_bones.extend( set(reference_bones) )

        self._weight_reference_bones = None  # For mapping vertex weights (can be automatically set by calling autoBuildWeightReferences())
        if weight_reference_bones is not None:
            if not isinstance(weight_reference_bones, list):
                weight_reference_bones = [ weight_reference_bones ]
            self._weight_reference_bones = list( set(weight_reference_bones) )

        # Matrices:
        # static
        #  matRestGlobal:     4x4 rest matrix, relative world (bind pose matrix)
        #  matRestRelative:   4x4 rest matrix, relative parent
        # posed
        #  matPose:           4x4 pose matrix, relative parent and own rest pose
        #  matPoseGlobal:     4x4 matrix, relative world
        #  matPoseVerts:      4x4 matrix, relative world and own rest pose

        self.matRestGlobal = None
        self.matRestRelative = None
        self.matPose = np.identity(4, np.float32)  # Set pose matrix to rest pose
        self.matPoseGlobal = None
        self.matPoseVerts = None

    @property
    def planes(self):
        return self.skeleton.planes

    def updateJointPositions(self, human=None, in_rest=True):
        """
        Update the joint positions of this bone based on the current state
        of the human mesh.
        Remember to call build() after calling this method.
        """
        if not human:
            from core import G
            human = G.app.selectedHuman
        self.headPos[:] = self.skeleton.getJointPosition(self.headJoint, human, in_rest)[:3] * self.skeleton.scale
        self.tailPos[:] = self.skeleton.getJointPosition(self.tailJoint, human, in_rest)[:3] * self.skeleton.scale

    def getRestMatrix(self, meshOrientation='yUpFaceZ', localBoneAxis='y', offsetVect=[0,0,0]):
        """
        Global rest matrix for this bone

        meshOrientation: What axis points up along the model, and which direction
                         the model is facing.
            allowed values: yUpFaceZ (0), yUpFaceX (1), zUpFaceNegY (2), zUpFaceX (3)

        localBoneAxis: How to orient the local axes around the bone, which axis
                       points along the length of the bone. Global (g) assumes the
                       same axes as the global coordinate space used for the model.
            allowed values: y, x, g
        """
        #self.calcRestMatrix()  # TODO perhaps interesting method to replace the current
        return transformBoneMatrix(self.matRestGlobal, meshOrientation, localBoneAxis, offsetVect)

    def getRelativeMatrix(self, meshOrientation='yUpFaceZ', localBoneAxis='y', offsetVect=[0,0,0]):
        restmat = self.getRestMatrix(meshOrientation, localBoneAxis, offsetVect)

        # TODO this matrix is possibly the same as self.matRestRelative, but with optional adapted axes
        if self.parent:
            parmat = self.parent.getRestMatrix(meshOrientation, localBoneAxis, offsetVect)
            return np.dot(la.inv(parmat), restmat)
        else:
            return restmat

    def getBindMatrix(self, offsetVect=[0,0,0]):
        #self.calcRestMatrix()
        self.matRestGlobal
        restmat = self.matRestGlobal.copy()
        restmat[:3,3] += offsetVect

        bindinv = np.transpose(restmat)
        bindmat = la.inv(bindinv)
        return bindmat,bindinv

    @property
    def weight_reference_bones(self):
        if self._weight_reference_bones is None:
            return self.reference_bones
        else:
            return self._weight_reference_bones

    def __repr__(self):
        return ("  <Bone %s>" % self.name)

    def build(self, ref_skel=None):
        """
        Calculate this bone's rest matrices and determine its local axis (roll
        or bone normal).
        Sets matPoseVerts, matPoseGlobal and matRestRelative.
        This method needs to be called everytime the skeleton structure is
        changed, the rest pose is changed or joint positions are updated.
        Pass a ref_skel to copy the bone normals from a reference skeleton
        instead of recalculating them (Recalculating bone normals generally
        only works if the skeleton is in rest pose).
        """
        head3 = np.array(self.headPos[:3], dtype=np.float32)
        head4 = np.append(head3, 1.0)

        tail3 = np.array(self.tailPos[:3], dtype=np.float32)
        tail4 = np.append(head3, 1.0)

        # Update rest matrices
        if ref_skel:
            # Direct or reference bone-mapped copy of ref_skel's normals
            normal = copy_normal(self, ref_skel)
        else:
            # Calculate normal from bone's plane definition
            normal = self.get_normal()
        self.matRestGlobal = getMatrix(head3, tail3, normal)
        self.length = matrix.magnitude(tail3 - head3)
        if self.parent:
            self.matRestRelative = np.dot(la.inv(self.parent.matRestGlobal), self.matRestGlobal)
        else:
            self.matRestRelative = self.matRestGlobal

        #vector4 = tail4 - head4
        self.yvector4 = np.array((0, self.length, 0, 1))

        # Update pose matrices
        self.update()

    def get_normal(self):
        """The normal calculated for this bone. The normal is used as one of
        the local axis for the bone to determine the local coordinate system 
        for the bone (see getMatrix for details).
        This normal is derived from the normal of a plane that is defined 
        between three predefined joint positions. These joint positions are 
        updated as the human is modified.
        This approach generally works only for the human in rest pose, for bone
        orientation in other poses, the normals should be first calculated in
        rest pose, then the pose applied (on the base skeleton), which rotates
        the calculated normals accordingly (createFromPose()). Then, if need be, 
        this normal can be grabbed from the global rest matrix and remapped to
        the bones of a different skeleton (see copy_normal).
        """
        if isinstance(self.roll, list):
            # Average the normal over multiple planes
            count = 0
            normal = np.zeros(3, dtype=np.float32)
            for plane_name in self.roll:
                norm = get_normal(self.skeleton, plane_name, self.planes)
                if not np.allclose(norm, np.zeros(3), atol=1e-05):
                    count += 1
                    normal += norm
            if count > 0 and not np.allclose(normal, np.zeros(3), atol=1e-05):
                normal /= count
            else:
                normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        elif isinstance(self.roll, basestring):
            plane_name = self.roll  # TODO ugly.. why not call this something else than "roll"?
            normal = get_normal(self.skeleton, plane_name, self.planes)
            if np.allclose(normal, np.zeros(3), atol=1e-05):
                normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        else:
            normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        return normal

    def update(self):
        """
        Recalculate global pose matrix ... TODO
        Needs to happen after setting pose matrix
        Should be called after changing pose (matPose)
        """
        if self.parent:
            self.matPoseGlobal = np.dot(self.parent.matPoseGlobal, np.dot(self.matRestRelative, self.matPose))
        else:
            self.matPoseGlobal = np.dot(self.matRestRelative, self.matPose)

        try:
            self.matPoseVerts = np.dot(self.matPoseGlobal, la.inv(self.matRestGlobal))
        except:
            log.debug("Cannot calculate pose verts matrix for bone %s %s %s", self.name, self.getRestHeadPos(), self.getRestTailPos())
            log.debug("Non-singular rest matrix %s", self.matRestGlobal)

    def getHead(self):
        """
        The current head position of this bone (posed) in world space.
        """
        return self.matPoseGlobal[:3,3].copy()

    def getTail(self):
        """
        The current tail position of this bone (posed) in world space.
        """
        tail4 = np.dot(self.matPoseGlobal, self.yvector4)
        return tail4[:3].copy()

    def getLength(self):
        return self.yvector4[1]

    def getRestHeadPos(self):
        """
        The head position of this bone in world space.
        """
        # TODO allow repose (is not affected by createFromPose)
        return self.headPos.copy()

    def getRestTailPos(self):
        """
        The head position of this bone in world space.
        """
        # TODO allow repose (is not affected by createFromPose)
        return self.tailPos.copy()

    def getRestOffset(self):
        # TODO make configurable like getRestMatrix
        if self.parent:
            return self.getRestHeadPos() - self.parent.getRestHeadPos()
        else:
            return self.getRestHeadPos()

    def getRestDirection(self):
        # TODO make configurable like getRestMatrix
        return matrix.normalize(self.getRestOffset())

    def getRestOrientationQuat(self):
        # TODO make configurable like getRestMatrix
        return tm.quaternion_from_matrix(self.matRestGlobal)

    def getRoll(self):
        """
        The roll angle of this bone. (in rest)
        """
        R = self.matRestGlobal
        qy = R[0,2] - R[2,0];
        qw = R[0,0] + R[1,1] + R[2,2] + 1;

        if qw < 1e-4:
            roll = pi
        else:
            roll = 2*math.atan2(qy, qw);
        return roll

    def getName(self):
        return self.name

    def hasParent(self):
        return self.parent != None

    def isRoot(self):
        return not self.hasParent()

    def hasChildren(self):
        return len(self.children) > 0

    def setToRestPose(self):   # used to be zeroTransformation()
        """
        Reset bone pose matrix to default (identity).
        """
        self.matPose = np.identity(4, np.float32)
        self.update()

    def isInRestPose(self):
        return animation.isRest(self.matPose)

    def setRotationIndex(self, index, angle, useQuat):
        """
        Set the rotation for one of the three rotation channels, either as
        quaternion or euler matrix. index should be 1,2 or 3 and represents
        x, y and z axis accordingly
        """
        if useQuat:
            quat = tm.quaternion_from_matrix(self.matPose)
            log.debug("%s", str(quat))
            quat[index] = angle/1000
            log.debug("%s", str(quat))
            _normalizeQuaternion(quat)
            log.debug("%s", str(quat))
            self.matPose = tm.quaternion_matrix(quat)
            return quat[0]*1000
        else:
            angle = angle*D
            ax,ay,az = tm.euler_from_matrix(self.matPose, axes='sxyz')
            if index == 1:
                ax = angle
            elif index == 2:
                ay = angle
            elif index == 3:
                az = angle
            mat = tm.euler_matrix(ax, ay, az, axes='sxyz')
            self.matPose[:3,:3] = mat[:3,:3]
            return 1000.0

    Axes = [
        np.array((1,0,0)),
        np.array((0,1,0)),
        np.array((0,0,1))
    ]

    def rotate(self, angle, axis, rotWorld):
        """
        Rotate bone with specified angle around given axis.
        Set rotWorld to true to rotate in world space, else rotation happens in
        local coordinates.
        Axis should be 0, 1 or 2 for rotation around x, y or z axis.
        """
        mat = tm.rotation_matrix(angle*D, Bone.Axes[axis])
        if rotWorld:
            mat = np.dot(mat, self.matPoseGlobal)
            self.matPoseGlobal[:3,:3] = mat[:3,:3]
            self.matPose = self.getPoseFromGlobal()
        else:
            mat = np.dot(mat, self.matPose)
            self.matPose[:3,:3] = mat[:3,:3]

    def setRotation(self, angles):
        """
        Sets rotation of this bone (in local space) as Euler rotation
        angles x,y and z.
        """
        ax,ay,az = angles
        mat = tm.euler_matrix(ax, ay, az, axes='szyx')
        self.matPose[:3,:3] = mat[:3,:3]

    def getRotation(self):
        """
        Get rotation matrix of rotation of this bone in local space.
        """
        qw,qx,qy,qz = tm.quaternion_from_matrix(self.matPose)
        ax,ay,az = tm.euler_from_matrix(self.matPose, axes='sxyz')
        return (1000*qw,1000*qx,1000*qy,1000*qz, ax/D,ay/D,az/D)

    def getPoseQuaternion(self):
        """
        Get quaternion of orientation of this bone in local space.
        """
        return tm.quaternion_from_matrix(self.matPose)

    def setPoseQuaternion(self, quat):
        """
        Set orientation of this bone in local space as quaternion.
        """
        self.matPose = tm.quaternion_matrix(quat)

    def rotateRest(self, rotMat):
        """
        Apply a rotation to this bone and set it as new rest orientation.
        :param rotMat: Rotation matrix
        """
        self.matRestRelative = np.dot(self.matRestRelative, rotMat)
        if self.parent:
            self.matRestGlobal = np.dot(self.parent.matRestGlobal, self.matRestRelative)
        else:
            self.matRestGlobal = self.matRestRelative

        # Update pose matrices
        self.update()


    def stretchTo(self, goal, doStretch):
        """
        Orient bone to point to goal position. Set doStretch to true to
        position the tail joint at goal, false to maintain length of this bone.
        """
        length, self.matPoseGlobal = _getMatrix(self.getHead(), goal, 0)
        if doStretch:
            factor = length/self.length
            self.matPoseGlobal[:3,1] *= factor
        pose = self.getPoseFromGlobal()

        az,ay,ax = tm.euler_from_matrix(pose, axes='szyx')
        rot = tm.rotation_matrix(-ay + self.roll_angle, Bone.Axes[1])
        self.matPoseGlobal[:3,:3] = np.dot(self.matPoseGlobal[:3,:3], rot[:3,:3])
        #pose2 = self.getPoseFromGlobal()

    ## TODO decouple this specific method from general armature?
    ## It is used by constraints.py and is related to IK
    ## TODO maybe place in an extra IK armature class or a separate module?
    def poleTargetCorrect(self, head, goal, pole, angle):
        """
        Resolve a pole target type of IK constraint.
        http://www.blender.org/development/release-logs/blender-246/inverse-kinematics/
        """
        yvec = goal-head
        xvec = pole-head
        xy = np.dot(xvec, yvec)/np.dot(yvec,yvec)
        xvec = xvec - xy * yvec
        xlen = math.sqrt(np.dot(xvec,xvec))
        if xlen > 1e-6:
            xvec = xvec / xlen
            zvec = self.matPoseGlobal[:3,2]
            zlen = math.sqrt(np.dot(zvec,zvec))
            zvec = zvec / zlen
            angle0 = math.asin( np.dot(xvec,zvec) )
            rot = tm.rotation_matrix(angle - angle0, Bone.Axes[1])
            self.matPoseGlobal[:3,:3] = np.dot(self.matPoseGlobal[:3,:3], rot[:3,:3])

    def getPoseFromGlobal(self):
        """
        Returns the pose matrix for this bone (relative to parent and rest pose)
        calculated from its global pose matrix.
        """
        if self.parent:
            return np.dot(la.inv(self.matRestRelative), np.dot(la.inv(self.parent.matPoseGlobal), self.matPoseGlobal))
        else:
            return np.dot(la.inv(self.matRestRelative), self.matPoseGlobal)


YZRotation = np.array(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
ZYRotation = np.array(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))

def toZisUp3(vec):
    """
    Convert vector from MH coordinate system (y is up) to Blender coordinate
    system (z is up).
    """
    return np.dot(ZYRotation[:3,:3], vec)

def fromZisUp4(mat):
    """
    Convert matrix from Blender coordinate system (z is up) to MH coordinate
    system (y is up).
    """
    return np.dot(YZRotation, mat)

YUnit = np.array((0,1,0))

def getMatrix(head, tail, normal):
    """Generate a bone local rest matrix. The Y axis of the bone is the vector
    between head and tail, the normal specified is used as X axis (or at least, 
    a vector similar to the direction of normal, but perpendicular to Y).
    Z is calculated as perpendicular on X and Y.
    This method generates a local orthogonal base for the bone, originating in
    the bone's head position, with Y axis along the length of the bone.
    X is usually seen as the main rotation axis of the bone, Y indicates the 
    main direction towards which the bone is rotated along the X axis.
    """
    mat = np.identity(4, dtype=np.float32)
    bone_direction = tail - head
    bone_direction = matrix.normalize(bone_direction[:3])
    normal = matrix.normalize(normal[:3])

    # This would be the ideal case, where normal is always perpendicular to 
    # bone_direction, which in practice will often not be the case
    '''
    # Construct a base with orthonormal vectors
    mat[:3,0] = normal[:3]          # bone local X axis
    mat[:3,1] = bone_direction[:3]  # bone local Y axis
    # Create a Z vector perpendicular on X and Y axes
    z_axis = matrix.normalize(np.cross(normal, bone_direction))
    mat[:3,2] = z_axis[:3]          # bone local Z axis
    '''

    # We want an orthonormal base, so...
    # Take Z as perpendicular to normal and bone_direction
    # We want a right handed axis system so use cross product order X * Y * Z 
    z_axis = matrix.normalize(np.cross(normal, bone_direction))

    # We now have two vertices that are orthogonal, we still need Y
    # Calculate Y as orthogonal on the other two, it should approximate the
    # normal specified as argument to this function
    x_axis = matrix.normalize(np.cross(bone_direction, z_axis))

    # Now we construct our orthonormal base
    mat[:3,0] = x_axis[:3]          # bone local X axis
    mat[:3,1] = bone_direction[:3]  # bone local Y axis
    mat[:3,2] = z_axis[:3]          # bone local Z axis

    # Add head position as translation
    mat[:3,3] = head[:3]

    return mat

## TODO do y-z conversion inside this method or require caller to do it?
def _getMatrix(head, tail, roll):
    """
    Calculate an orientation (rest) matrix for a bone between specified head
    and tail positions with given bone roll angle.
    Returns length of the bone and rest orientation matrix in global coordinates.
    """
    # TODO validate, or replace

    vector = toZisUp3(tail - head)
    length = math.sqrt(np.dot(vector, vector))
    if length == 0:
        vector = [0,0,1]
    else:
        vector = vector/length
    yproj = np.dot(vector, YUnit)

    if yproj > 1-1e-6:
        axis = YUnit
        angle = 0
    elif yproj < -1+1e-6:
        axis = YUnit
        angle = pi
    else:
        axis = np.cross(YUnit, vector)
        axis = axis / math.sqrt(np.dot(axis,axis))
        angle = math.acos(yproj)
    mat = tm.rotation_matrix(angle, axis)
    if roll:
        mat = np.dot(mat, tm.rotation_matrix(roll, YUnit))
    mat = fromZisUp4(mat)
    mat[:3,3] = head
    return length, mat

def get_roll_to(head, tail, normal):
    """
    Compute the roll angle for a bone to make the bone's local x axis align with
    the specified normal.
    """
    p1 = toZisUp3(head)
    p2 = toZisUp3(tail)
    xvec = normal

    pvec = matrix.normalize(p2-p1)
    xy = np.dot(xvec,pvec)
    yvec = matrix.normalize(pvec-xy*xvec)
    zvec = matrix.normalize(np.cross(xvec, yvec))
    mat = np.asarray((xvec,yvec,zvec), dtype=np.float32)

    try:
        assertOrthogonal(mat)
    except Exception as e:
        log.warning("Calculated matrix is not orthogonal (%s)" % e)
    quat = tm.quaternion_from_matrix(mat)
    if abs(quat[0]) < 1e-4:
        return 0
    else:
        roll = math.pi - 2*math.atan(quat[2]/quat[0])

    if roll < -math.pi:
        roll += 2*math.pi
    elif roll > math.pi:
        roll -= 2*math.pi
    return roll

def get_normal(skel, plane_name, plane_defs, human=None):
    """
    Return the normal of a triangle plane defined between three joint positions,
    using counter-clockwise winding order (right-handed).
    """
    if plane_name not in plane_defs:
        log.warning("No plane with name %s defined for skeleton.", plane_name)
        return np.asarray([0,1,0], dtype=np.float32)

    if not human:
        from core import G
        human = G.app.selectedHuman

    joint_names = plane_defs[plane_name]

    j1,j2,j3 = joint_names
    p1 = skel.getJointPosition(j1, human)[:3] * skel.scale
    p2 = skel.getJointPosition(j2, human)[:3] * skel.scale
    p3 = skel.getJointPosition(j3, human)[:3] * skel.scale
    pvec = matrix.normalize(p2-p1)
    yvec = matrix.normalize(p3-p2)
    return matrix.normalize(np.cross(yvec, pvec))

def copy_normal(target_bone, ref_skel):
    """Copy a normal (bone orientation) from a reference skeleton and map it to
    the target_bone. This is used in the following scenario: calculate the
    normals/orientations of the base skeleton in rest, apply a pose to the
    base skeleton. Then, using this base skeleton with the pose transformed
    into its rest pose (createFromPose) as ref_skel, the orientations can be
    mapped/copied onto a different skeleton that is fit into the same pose
    (With fitting we mean updating the rest pose joint positions so that they
    fit inside a posed human mesh, posed by the base skeleton).

    The reference bones defined for the target bone are used for getting to the
    correct bone (or bones) of the base skeleton to copy the normal from. If
    no reference bones are specified, it looks for a bone in the base skeleton
    with the same name as the target bone (implicit mapping).
    """

    def _get_normal(bone):
        """Grab the normal from a bone's global rest matrix. We assume that
        this bone is in the same rest pose as the bone we want to map it to.
        """
        return bone.matRestGlobal[:3, 0].reshape(3)  # X axis

    if ref_skel.name == target_bone.skeleton.name:
        direct_copy = True  # No remapping is needed, the skeletons are the same
    else:
        direct_copy = False

    if not direct_copy and len(target_bone.reference_bones) > 0:
        if len(target_bone.reference_bones) == 1:
            rbone = ref_skel.getBone(target_bone.reference_bones[0])
            return _get_normal(rbone)
        else:
            normal = np.zeros(3, dtype=np.float32)
            count = 0
            for rbname in target_bone.reference_bones:
                rbone = ref_skel.getBone(rbname)
                norm = _get_normal(rbone)
                if not np.allclose(norm, np.zeros(3), atol=1e-05):
                    count += 1
                    normal += norm
            if count > 0 and not np.allclose(normal, np.zeros(3), atol=1e-05):
                normal /= count
            else:
                normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
            return normal
    else:
        # Direct mapping: Try to map by bone name
        if ref_skel.containsBone(target_bone.name):
            return _get_normal(ref_skel.getBone(target_bone.name))
        else:
            log.warning("No normal found for bone %s: no reference bones and could not map implicitly by name", target_bone.name)
            return np.asarray([0.0, 1.0, 0.0], dtype=np.float32)

def assertOrthogonal(mat):
    prod = np.dot(mat, mat.transpose())
    diff = prod - np.identity(3,float)
    sum = 0
    for i in range(3):
        for j in range(3):
            if abs(diff[i,j]) > 1e-5:
                raise AssertionError("Not orthogonal: diff[%d,%d] = %g\n%s\n\%s" % (i, j, diff[i,j], mat, prod))
    return True


def _normalizeQuaternion(quat):
    # TODO transformations.py already contains these
    r2 = quat[1]*quat[1] + quat[2]*quat[2] + quat[3]*quat[3]
    if r2 > 1:
        r2 = 1
    if quat[0] >= 0:
        sign = 1
    else:
        sign = -1
    quat[0] = sign*math.sqrt(1-r2)

def _getHumanJointPosition(human, jointName, rest_coord=True):
    """
    Get the position of a joint from the human mesh.
    This position is determined by the center of the joint helper with the
    specified name.
    Note: you probably want to use Skeleton.getJointPosition()
    """
    if not jointName.startswith("joint-"):
        jointName = "joint-" + jointName
    fg = human.meshData.getFaceGroup(jointName)
    if fg is None:
        log.warning('Cannot find position for joint %s', jointName)
        return np.asarray([0,0,0], dtype=np.float32)
    v_idx = human.meshData.getVerticesForGroups([fg.name])
    if rest_coord:
        verts = human.getRestposeCoordinates()[v_idx]
    else:
        verts = human.meshData.getCoords(v_idx)
    return verts.mean(axis=0)


_Identity = np.identity(4, float)
_RotX = tm.rotation_matrix(math.pi/2, (1,0,0))
_RotY = tm.rotation_matrix(math.pi/2, (0,1,0))
_RotNegX = tm.rotation_matrix(-math.pi/2, (1,0,0))
_RotZ = tm.rotation_matrix(math.pi/2, (0,0,1))
_RotZUpFaceX = np.dot(_RotZ, _RotX)
_RotXY = np.dot(_RotNegX, _RotY)

def transformBoneMatrix(mat, meshOrientation='yUpFaceZ', localBoneAxis='y', offsetVect=[0,0,0]):
    """
    Transform orientation of bone matrix to fit the chosen coordinate system
    and mesh orientation.

    meshOrientation: What axis points up along the model, and which direction
                     the model is facing.
        allowed values: yUpFaceZ (0), yUpFaceX (1), zUpFaceNegY (2), zUpFaceX (3)

    localBoneAxis: How to orient the local axes around the bone, which axis
                   points along the length of the bone. Global (g) assumes the
                   same axes as the global coordinate space used for the model.
        allowed values: y, x, g
    """
    mat = mat.copy()
    mat[:3,3] += offsetVect

    if meshOrientation == 0 or meshOrientation == 'yUpFaceZ':
        rot = _Identity
    elif meshOrientation == 1 or meshOrientation == 'yUpFaceX':
        rot = _RotY
    elif meshOrientation == 2 or meshOrientation == 'zUpFaceNegY':
        rot = _RotX
    elif meshOrientation == 3 or meshOrientation == 'zUpFaceX':
        rot = _RotZUpFaceX
    else:
        log.warning('invalid meshOrientation parameter %s', meshOrientation)
        return None

    if localBoneAxis.lower() == 'y':
        # Y along self, X bend
        return np.dot(rot, mat)

    elif localBoneAxis.lower() == 'x':
        # X along self, Y bend
        return np.dot(rot, np.dot(mat, _RotXY) )

    elif localBoneAxis.lower() == 'g':
        # Global coordinate system
        tmat = np.identity(4, float)
        tmat[:,3] = np.dot(rot, mat[:,3])
        return tmat

    log.warning('invalid localBoneAxis parameter %s', localBoneAxis)
    return None

def load(filename, mesh=None):
    """
    Load a skeleton from a json rig file.
    """
    skel = Skeleton()
    skel.fromFile(filename, mesh)
    return skel

def peekMetadata(filename):
    import json
    skelData = json.load(open(filename, 'rb'))
    desc = skelData.get("description", "")
    name = skelData.get("name", "Skeleton")
    tags = set( map(lambda s: s.lower(), skelData.get("tags", [])) )
    return (name, desc, tags)
