#!/usr/bin/env python
#-*- coding: UTF-8 -*-

"""
This module demonstrates the functionality of PyAssimp.

http://graphics.pixar.com/usd/files/SkinningOM.md.html
"""

import os, sys
import bisect
import logging
logging.basicConfig(level=logging.INFO)

import pyassimp
import pyassimp.postprocess

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

joint_paths = []
rest_transforms = []
joint_to_path = {}

def add_joints(stage, path, node):
    global joint_paths
    path += str(node)
    joint_paths.append(path)

    # this is legit because assimp has a restriction that every joint has to
    # be uniquely named, and if it isn't it will be made so during import
    joint_to_path[str(node)] = path

    xform = node.contents.mTransformation
    rest_transform = Gf.Matrix4d(xform.a1, xform.b1, xform.c1, xform.d1, xform.a2, xform.b2, xform.c2, xform.d2,
                                 xform.a3, xform.b3, xform.c3, xform.d3, xform.a4, xform.b4, xform.c4, xform.d4)

    rest_transforms.append(rest_transform)

    joint = UsdSkel.Joint.Define(stage, path)

    for child in node.children:
        add_joints(stage, path + "/", child)


def recur_node(stage, path, node, level = 0):
    path += str(node)

    xform = node.contents.mTransformation

    xformPrim = UsdGeom.Xform.Define(stage, path)
    xformOp = xformPrim.MakeMatrixXform()
    xformOp.Set(Gf.Matrix4d(xform.a1, xform.b1, xform.c1, xform.d1, xform.a2, xform.b2, xform.c2, xform.d2,
                            xform.a3, xform.b3, xform.c3, xform.d3, xform.a4, xform.b4, xform.c4, xform.d4))

    xformPrim.SetXformOpOrder(orderedXformOps=[xformOp], resetXformStack=False)

    #spherePrim = UsdGeom.Sphere.Define(stage, path + "/geom")
    #sphere = UsdGeom.Sphere(spherePrim)
    #radiusAttr = sphere.GetRadiusAttr()
    #radiusAttr.Set(1)

    for child in node.children:
        recur_node(stage, path + "/", child, level + 1)

def find_key(arr, x):
    'Find rightmost value less than or equal to x and return index'
    i = bisect.bisect_right(arr, x)
    if i:
        return i-1
    raise ValueError

def main(filename=None):
    # when loading a BVH file, assimp creates a mesh for visualization, and
    # binds the joints to it with uniform weights.
    # this extra gemometry can be disregarded.
    #
    scene = pyassimp.load(filename)#, processing=pyassimp.postprocess.aiProcess_Triangulate)

    #the model we load
    print("MODEL:" + filename)
    print

    #write some statistics
    print("SCENE:")
    print("  meshes:" + str(len(scene.meshes)))
    print("  materials:" + str(len(scene.materials)))
    print("  textures:" + str(len(scene.textures)))
    print

    print("MESHES:")
    for index, mesh in enumerate(scene.meshes):
        print("  MESH" + str(index+1))
        print("    material id:" + str(mesh.materialindex+1))
        print("    vertices:" + str(len(mesh.vertices)))
        print("    first 3 verts:\n" + str(mesh.vertices[:3]))
        if len(mesh.normals):
                print("    first 3 normals:\n" + str(mesh.normals[:3]))
        else:
                print("    no normals")
        print("    colors:" + str(len(mesh.colors)))
        tcs = mesh.texturecoords
        if len(tcs):
            for index, tc in enumerate(tcs):
                print("    texture-coords "+ str(index) + ":" + str(len(tcs[index])) + "first3:" + str(tcs[index][:3]))
        else:
            print("    no texture coordinates")

        print("    uv-component-count:" + str(len(mesh.numuvcomponents)))
        print("    faces:" + str(len(mesh.faces)) + " -> first:\n" + str(mesh.faces[:3]))
        print("    bones:" + str(len(mesh.bones)) + " -> first:" + str([str(b) for b in mesh.bones[:3]]))
        print

    print("MATERIALS:")
    for index, material in enumerate(scene.materials):
        print("  MATERIAL (id:" + str(index+1) + ")")
        for key, value in material.properties.items():
            print("    %s: %s" % (key, value))
    print

    print("TEXTURES:")
    for index, texture in enumerate(scene.textures):
        print("  TEXTURE" + str(index+1))
        print("    width:" + str(texture.width))
        print("    height:" + str(texture.height))
        print("    hint:" + str(texture.achformathint))
        print("    data (size):" + str(len(texture.data)))

    # stage
    stage = Usd.Stage.CreateNew('foo.usda')

    # skeleton
    skelPrim = UsdSkel.Skeleton.Define(stage, "/Perfume")
    add_joints(stage, "/Perfume/", scene.rootnode)

    skel = UsdSkel.Skeleton(skelPrim)
    joints_rel = skel.GetJointsRel()
    for joint in joint_paths:
        joints_rel.AppendTarget(joint)

    skel.CreateRestTransformsAttr(rest_transforms)

    # a dummy hierachy - test only - remove
    #recur_node(stage, "/", scene.rootnode)
    # a dummy hierachy - test only - remove

    for idx, animationPtr in enumerate(scene.animations):
        animation = animationPtr.contents
        name = "Anim1"
        if hasattr(animation, 'mName'):
            name = str(animation.mName.data)
        print "duration", animation.mDuration
        print "ticks per second", animation.mTicksPerSecond
        ticksPerSecond = 24.0
        if animation.mTicksPerSecond > 0:
            ticksPerSecond = animation.mTicksPerSecond
        print "channels", animation.mNumChannels

        # packed joint animation
        animPrim = UsdSkel.PackedJointAnimation.Define(stage, "/" + name)
        anim = UsdSkel.PackedJointAnimation(animPrim)

        uniform_translation = True
        uniform_scale = True
        uniform_scale = True

        # add the animation's joint rels
        joints_rel = anim.GetJointsRel()
        for idx in range(0, animation.mNumChannels):
            channel = animation.mChannels[idx].contents
            joint_name = str(channel.mNodeName.data)
            joint_path = joint_to_path[joint_name].replace("/Perfume", "/" + name)
            print idx, joint_name, joint_path, channel.mNumPositionKeys, channel.mNumRotationKeys, channel.mNumScalingKeys
            joints_rel.AppendTarget(joint_path)
            if channel.mNumPositionKeys > 1:
                uniform_translation = False
            if channel.mNumRotationKeys > 1:
                uniform_rotation  = False
            if channel.mNumScalingKeys > 1:
                uniform_scale = False

        if uniform_rotation:
            rotations = []
            for idx in range(0, animation.mNumChannels):
                channel = animation.mChannels[idx].contents
                v = channel.mRotationKeys[0]
                vh = Gf.Quath(v.mValue.w, v.mValue.x, v.mValue.y, v.mValue.z)
                rotations.append(vh)
            anim.CreateRotationsAttr(rotations)
        else:
            # find the union of all the rotation key times
            unique_keys = set()
            for idx in range(0, animation.mNumChannels):
                channel = animation.mChannels[idx].contents
                k = channel.mNumRotationKeys
                for idx in range(0, k):
                    unique_keys.add(channel.mRotationKeys[idx].mTime)
            keys = list(sorted(unique_keys))

            attr = anim.CreateRotationsAttr()

            for key in keys:
                values = []
                for idx in range(0, animation.mNumChannels):
                    channel = animation.mChannels[idx].contents
                    channel_keys = []
                    k = channel.mNumRotationKeys

                    # make a searchable python list of this channel's key times
                    for idx in range(0, k):
                        channel_keys.append(channel.mRotationKeys[idx].mTime)

                    idx = find_key(channel_keys, key)
                    v = channel.mRotationKeys[idx].mValue
                    values.append(Gf.Quath(v.w, v.x, v.y, v.z))
                attr.Set(values, key)

        if uniform_translation:
            translations = []
            for idx in range(0, animation.mNumChannels):
                channel = animation.mChannels[idx].contents
                v = channel.mTranslationKeys[0]
                vh = Gf.Vec3f(v.mValue.x, v.mValue.y, v.mValue.z)
                translations.append(vh)
            anim.CreateRotationsAttr(translations)
        else:
            # find the union of all the translation key times
            unique_keys = set()
            for idx in range(0, animation.mNumChannels):
                channel = animation.mChannels[idx].contents
                k = channel.mNumPositionKeys
                for idx in range(0, k):
                    unique_keys.add(channel.mPositionKeys[idx].mTime)
            keys = list(sorted(unique_keys))

            attr = anim.CreateTranslationsAttr()

            for key in keys:
                values = []
                for idx in range(0, animation.mNumChannels):
                    channel = animation.mChannels[idx].contents
                    channel_keys = []
                    k = channel.mNumPositionKeys

                    # make a searchable python list of this channel's key times
                    for idx in range(0, k):
                        channel_keys.append(channel.mPositionKeys[idx].mTime)

                    idx = find_key(channel_keys, key)
                    v = channel.mPositionKeys[idx].mValue
                    values.append(Gf.Vec3f(v.x, v.y, v.z))
                attr.Set(values, key)


        if uniform_scale:
            scales = []
            for idx in range(0, animation.mNumChannels):
                channel = animation.mChannels[idx].contents
                v = channel.mScalingKeys[0]
                vh = Gf.Vec3h(v.mValue.x, v.mValue.y, v.mValue.z)
                scales.append(vh)
            anim.CreateScalesAttr(scales)
        else:
            # find the union of all the rotation key times
            unique_keys = set()
            for idx in range(0, animation.mNumChannels):
                channel = animation.mChannels[idx].contents
                k = channel.mNumScalingKeys
                for idx in range(0, k):
                    unique_keys.add(channel.mScalingKeys[idx].mTime)
            keys = list(sorted(unique_keys))

            attr = anim.CreateScalesAttr()

            for key in keys:
                values = []
                for idx in range(0, animation.mNumChannels):
                    channel = animation.mChannels[idx].contents
                    channel_keys = []
                    k = channel.mNumScalingKeys

                    # make a searchable python list of this channel's key times
                    for idx in range(0, k):
                        channel_keys.append(channel.mScalingKeys[idx].mTime)

                    idx = find_key(channel_keys, key)
                    v = channel.mScalingKeys[idx].mValue
                    values.append(Gf.Vec3h(v.x, v.y, v.z))
                attr.Set(values, key)


    # save the usd file
    stage.GetRootLayer().Save()


    # Finally release the model
    pyassimp.release(scene)

def usage():
    print("Usage: sample.py <3d model>")

if __name__ == "__main__":

    if len(sys.argv) != 2:
        usage()
    else:
        main(sys.argv[1])
