import os
import json
import subprocess
import join_ctm
import logging
logger = logging.getLogger('convert_obj_ctm')
import tempfile

def convert_to_ctm(args, ctmconv_path, tmpdir, outfile):
    """
    This function will convert .obj output to ctm
    This need the openctm 1.0.3. This means we need to compile the opctm lib and tools
    """
    print(args)
    if not tmpdir: tmpdir=tempfile.gettempdir()
    objfiles = args['outputs'] # should be obj files, (which have name.mtl beside the name.obj)
    infile = args['output'] # should be threejs js file
    tmpfiles = []

    # Path
    ctmdir = os.path.dirname(ctmconv_path)
    add_to_path = [
        os.path.join(ctmdir, 'lib'), os.path.join(ctmdir, 'tools'),
        os.path.join(ctmdir, 'lib', 'liblzma')
    ]
    os.sys.path.extend(add_to_path)
    if os.path.join(ctmdir, 'tools') not in os.environ.get('LD_LIBRARY_PATH',
                                                           ''):
        os.environ['LD_LIBRARY_PATH'] = os.environ.get(
            'LD_LIBRARY_PATH', '') + ':' + ':'.join(add_to_path)

    for file in objfiles:
        ctmconv = os.path.abspath(os.path.join(ctmconv_path, 'ctmconv'))
        # the input and output must just be files names or it seg faults

        ctm_name = os.path.basename(file.replace('.obj', '.ctm'))
        ctm_path = os.path.join(tmpdir, ctm_name)

        tmpfiles.append(ctm_path)
        cwd_path = os.path.dirname(file.replace('.obj', '.ctm'))
        cmd = [ctmconv, file, ctm_path, '--method', 'MG2']
        logger.info("cmd: ", ' '.join(cmd), 'cwd', cwd_path)
        # try:
        output = subprocess.check_output(cmd, cwd=cwd_path)  # doesn't seem to work right now
        # except subprocess.CalledProcessError, e:
        # logger.error("ctmconv failed with output:\n", e.output)
        # else:
        if 'Error:' in output:
            logger.error(output)
            raise Exception("The word 'Error' occured in the ctmconv output indicating an error.", cmd, 0, output)
        logger.info('ctmconv output', output)
        print('ctmconv output', output)

    offsets = join_ctm.join(tmpfiles, outfile)

    js_file = infile.replace('.obj', '.js')
    # write the offsets etc to json file
    out = open(js_file, "r")
    jsonl = out.read()
    out.close()
    try:
        js = json.loads(jsonl)
    except Exception, e:
        print "json loading error", out, e
        raise(e)

    def shadeRGBColor(color, t):
        R = color[0]
        G = color[1]
        B = color[2]
        # TODO check this there is a var problem here
        return (t - R) * p + R, (t - G) * p + G, (t - B) * p + B

    def blendRGBColors(color, c1, p):
        R = color[0]
        G = color[1]
        B = color[2]
        return (c1[0] - R) * p + R, (c1[1] - G) * p + G, (c1[2] - B) * p + B

    js['offsets'] = offsets  # add ctm file offsets info
    materials = js.get('materials', [])
    for i in range(len(materials)):
        js['materials'][i][
            'shading'] = 'lambert'  # phong=MeshPhongMaterial,basic=MeshBasicMaterial, else->MeshLambertMaterial
        if 'mapDiffuse' in js['materials'][i]:
            js['materials'][i]['mapDiffuse'] = "textures/" + js['materials'][
                i]['mapDiffuse']
            js['materials'][i]['mapDiffuse'] = js['materials'][i][
                'mapDiffuse'].replace(
                    'darkskinned', 'lightskinned'
                )  #  only if we want to ingore african skins and have a nice blend
            # js['materials'][i]['mapDiffuse']='' # to try with no textures... it looks wierd
            # colors=js['materials'][i]['colorDiffuse']
            # newcolors=[ c*c for c in colors]
            # js['materials'][i]['colorDiffuse']=newcolors

    # now join ctms files and get offsets
    if not outfile:
        outjs = js_file
    else:
        outjs = outfile.replace('.ctm', '.js')
    out = open(outjs, "w")
    json.dump(js, out, indent=True)
    out.close()

    return outjs
