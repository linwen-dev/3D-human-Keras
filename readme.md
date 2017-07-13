This project aims to train a variational auto encoder on makehuman models. This should compress down the data needed to construct a human by ~100x and let it work in the browser.

The original data is from makehuman and consists of linear interpolations between morphtargets such as a tall female and short female. Machine learning is the second best solution to any problem, and in this case we already have an exact solution. So why use it? Well using a machine learning model gives us less data to load  (170mb vs ~1200mb) and allows faster calculation. These two factors let us use it in the browser, and you can see this yourself in the demo. As well as this three.js is limited to applying a few morphtargets, while this approach presents no limit.

The target data is ~1GB but using machine learning it can be compressed to a 70mb model using with 97% accuracy. The result is here http://wassname.org/makehuman_generative_model/ (you need a webgl capable browser to see it).

The result is small and fast but the parameters have some overlap, so changing the smile may slightly change the eyes. This could probably be improved with better data generation, since in makehuman the result is dependant on the order that the modifiers are applied but my model didn't know the order. Also the meta modifiers override the dependant ones is a way that I can't fully wrap my head around.

What I did was, generate 10k human models from random modifiers and save the vertices to a hdf file as y, and the modifier values as X. Run a fully connected neural network with 3 layers that have 249, 249, 57474 neurons and leaky ReLU activation's between layers. Then train for an couple of hours trying to predict X given y. The results are loaded into the browser using keras-js. If anyone is interested I can share the source code, but it's a bit messy right now as it was just a test.


To use:
- use python 2.7
- to generate data use `notebooks/Make random outputs for a VAE (to hdf).ipynb`
    - `cd vendor; hg clone https://bitbucket.org/duststorm01/makehuman-commandline` to clone the repo into this directory
- run `notebooks/main.ipynb` to train and save a model
    - to skip the previous step you can decompress the included data file and update paths in the notebook
- to see results
    - `cd output/kerasjs_and_threejs`
    - `http-server -o`
    - then open the browser at `http://127.0.0.1:8080/` and you should see controls to modify the models in real time. You will need a webgl accelerated browser.


TODO:
- [x] make a script to generate random models and save as python readable format, ideally npz, json, hdf5, csv
- [x] test a VAE on it
- [x] See if my assumptions fit
    - [ ] It can reproduce realistic humans. It seemed to just correlate all variable with age/height
    - [x] It can be compressed down to a small size (my 50mb of morphtargets is a 2mb model)
    - [x] Can be run in the browser with responsive time - it seems to run fast
