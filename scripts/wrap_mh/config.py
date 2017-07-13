# Set location of makehuman lib here
from path import Path
import os
mhpath = Path(__file__).abspath().dirname().joinpath('..', '..', 'vendor/makehuman-commandline/makehuman')
print(mhpath)
ctmconv_path = Path(os.path.abspath('vendor/OpenCTM-master/tools'))
