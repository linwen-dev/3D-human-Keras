import os
import datetime
import time

last_clean = int(time.time())

def remove_old_models():
    """
    Remove models older than an 10 mins
    """
    i = 0
    models_dir = os.path.join(BASE_DIR, 'static', 'models')
    filenames = os.listdir(models_dir)
    global last_clean
    if int(time.time()) - last_clean < 600 and len(
            filenames) < 2000:  # 100 MB of 100km models and tiny js files
        return 0

    for file in filenames:
        curpath = os.path.join(models_dir, file)
        name, ext = os.path.splitext(file)
        file_modified = datetime.datetime.fromtimestamp(os.path.getmtime(
            curpath))
        if datetime.datetime.now() - file_modified > datetime.timedelta(
                seconds=405):
            if ext in ['.js', '.json', '.obj', '.utf8', '.mtl', '.ctm']:
                os.remove(curpath)
                i += 1
            else:
                print curpath, "not known ext"
    print "Removed {} old model files of ext{} from {}".format(i, ext,
                                                               models_dir)
    last_clean = int(time.time())
    return i

# remove_old_models()
