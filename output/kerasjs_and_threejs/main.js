// @author: wassname
// @license: MIT

if (!Detector.webgl) {
    Detector.addGetWebGLMessage();
}

// we require, model.json, model_weights.buf, model_metadata.json
const model = new KerasJS.Model({
  filepaths: {
    model: 'data/model.json',
    weights: 'data/model_weights.buf',
    metadata: 'data/model_metadata.json'
  },
  gpu: false
})

var updateModel = function(){
    if (params){
    var data = params.values()
    var inputData = {
     'input': new Float32Array(data)
    }
    return model.predict(inputData)
      .then(outputData => {
        // The mode predict a change for each vector, so we add it to the reference model to create the new position
        var v =  outputData['output']
        var new_vertices = []
        for (let i=0;i*3<v.length;i++){
            var dvert = new THREE.Vector3(v[i*3],v[i*3+1],v[i*3+2])
            var vert = human_base2.geometry.vertices[i]
            new_vertices.push(dvert.add(vert))
        }
        human_base.geometry.vertices = new_vertices
        human_base.geometry.elementsNeedUpdate = true;
      })
      .catch(err => {
        throw err
     })
}}
model.ready()
  .then(() => {
    return updateModel()
  })
  .catch(err => {
    throw err
})



// setup controls
var gui
var params
var Params = function(labels){
    this._labels=labels;

    // store
    for (var i=0;i<labels.length;i++){
        this[labels[i]]=0.5;
    }

    // serialise
    var self=this;
    this.values = function(){
        var data=[]
        for (let label of labels){
            data.push(self[label])
        }
        return data
    }
}

function setupDatGui(labels){
    params = new Params(labels)
    gui = new dat.GUI();

    var modifiersFolder = gui.addFolder('modifiers')
    modifiersFolder.open();


    // make random and reset
    params.resetLabels= function(){
           params._labels.forEach(label=>params[label]=0.5)
          // Iterate over all controllers
          for (var j in modifiersFolder.__folders) {
              var folder = modifiersFolder.__folders[j]
              for (var i in folder.__controllers) {
                folder.__controllers[i].updateDisplay();
              }
          }
          updateModel()
    }
    modifiersFolder.add(params, 'resetLabels');

    // make random and reset
    var randNormal = d3.randomNormal(0.5,0.2)
    params.randomLabels= function (){
          params._labels.forEach(label=>params[label]=_.clamp(randNormal(),0,1))
          // Iterate over all controllers
          for (var j in modifiersFolder.__folders) {
              var folder = modifiersFolder.__folders[j]
              for (var i in folder.__controllers) {
                folder.__controllers[i].updateDisplay();
              }
          }
          updateModel()
    }
    modifiersFolder.add(params, 'randomLabels');


    // get uniq groups from name like macrodetails/age-old|young
    var groups = labels.map(l=>l.split('/')[0]).reduce((accum,group)=>{accum[group]=group;return accum},{})
    // make groups
    for (let group in groups){
        groups[group]=modifiersFolder.addFolder(group)
        if (group.startsWith('macro')) groups[group].open()
    }

    // make controllers for each label
    for (let label of labels){
        [group, name] = label.split('/')
        var controller = groups[group].add(params, label, 0.001, 1.0);
        controller.onFinishChange(updateModel)
    }

    // add skins controls
    /** Set this bodies texture map from a loaded skin material **/
    function setSkin(skinName) {
        var index = skinNames.indexOf(skinName);
        if (human_base) {
            human_base.material.materials[0].map=skins[index];
            human_base2.material.materials[0].map=skins[index];
        }
    }
    var skinGui = this.gui.addFolder("Skins");
    var skinNames = skins.map(s=>s.name)
    params.skin = skinNames[0]
    skinGui
        .add(params, 'skin', skinNames)
        .onChange(setSkin);
    skinGui.open();

    // add body part opacity
    var bodyPartGui = this.gui.addFolder("bodyParts");
    for (let material of human_base.material.materials){
        var folder = bodyPartGui.addFolder(material.name)
        var controller = folder.add(material,'visible')
        var controller = folder.add(material,'opacity')
    }

    gui.width = 400;
    gui.open();
}



// SETUP threejs display
var SCREEN_WIDTH = window.innerWidth;
var SCREEN_HEIGHT = window.innerHeight;
var FLOOR = -25;
var container, stats;
var camera, scene;
var webglRenderer;
var mesh, zmesh, geometry;
var mouseX = 0, mouseY = 0;
var windowHalfX = window.innerWidth / 2;
var windowHalfY = window.innerHeight / 2;
// var render_canvas = 0, render_gl = 1;
// var has_gl = 0;/
// var bcanvas = document.getElementById( "rcanvas" );
var bwebgl = document.getElementById( "rwebgl" );
var renderer;
var human_base
var labels
var skins
var skinUrls = [
    "young_caucasian_female_special_suit.png",
    "young_caucasian_male_special_suit.png",
    "young_lightskinned_male_diffuse.png",
    "young_lightskinned_female_diffuse.png",
    "young_darkskinned_female_diffuse.png",
    "young_darkskinned_male_diffuse.png",
    "middleage_darkskinned_female_diffuse.png",
    "middleage_darkskinned_male_diffuse.png",
    "middleage_lightskinned_female_diffuse.png",
    "middleage_lightskinned_female_diffuse2.png",
    "middleage_lightskinned_male_diffuse.png",
    "middleage_lightskinned_male_diffuse2.png",
    "old_darkskinned_female_diffuse.png",
    "old_darkskinned_male_diffuse.png",
    "old_lightskinned_female_diffuse.png",
    "old_lightskinned_female_diffuse2.png",
    "old_lightskinned_male_diffuse.png",
    "old_lightskinned_male_diffuse2.png",
    "young_lightskinned_female_diffuse3.png",
    "young_lightskinned_male_diffuse3.png"
]
init();
animate();


function init() {

    container = document.getElementById( 'container' );
    camera = new THREE.PerspectiveCamera( 75, SCREEN_WIDTH / SCREEN_HEIGHT, 1, 1000 );
    camera.position.z = 100;
    scene = new THREE.Scene();

    // LIGHTS
    var ambient = new THREE.AmbientLight( 0x221100 );
    scene.add( ambient );
    var directionalLight = new THREE.DirectionalLight( 0xffeedd, 1.5 );
    directionalLight.position.set( 0, -70, 100 ).normalize();
    scene.add( directionalLight );


    // RENDERER
    webglRenderer = new THREE.WebGLRenderer({ antialias: true });
    webglRenderer.setClearColor( 0xffffff );
    webglRenderer.setPixelRatio( window.devicePixelRatio );
    webglRenderer.setSize( SCREEN_WIDTH, SCREEN_HEIGHT );
    webglRenderer.domElement.style.position = "relative";
    container.appendChild( webglRenderer.domElement );
    renderer = webglRenderer;
    has_gl = 1;

    // CONTROLS
    controls = new THREE.OrbitControls( camera, renderer.domElement );
    controls.enableZoom = true;

    // Load the base model twice, (once for reference)
    var jsonLoader = new THREE.JSONLoader();
    var modelPromise = new Promise(function(resolve, reject) {
        jsonLoader.load( "data/human_base.json", (geometry, materials)=>resolve([geometry, materials]) , undefined, reject)
    })
    .then(([geometry, materials])=>{
        human_base = createScene( geometry, materials, 0, FLOOR+10, 0, 0 )
        return human_base
    })
    var modelPromise2 = new Promise(function(resolve, reject) {
        jsonLoader.load( "data/human_base.json", (geometry, materials)=>resolve([geometry, materials]) , undefined, reject)
    })
    .then(([geometry, materials])=>{
        human_base2 = createScene( geometry, materials, 20, FLOOR+25, 0, 0 )
        human_base2.visible = false;
        return human_base2

    })

    /**
     * Load skin textures
     * @param  {String} baseUrl     Base string to add to urls
     * @param  {Array} textureUrls  Urls for textures
     * @return {Array}             Array containing textures
     */
    function loadTextures(baseUrl, textureUrls) {

        var textureLoader = new THREE.TextureLoader(this.manager);
        var textures = [];

        for (var i = 0; i < textureUrls.length; i++) {

            textures[i] = textureLoader.load(baseUrl + textureUrls[i]);
            textures[i].mapping = THREE.UVMapping;
            textures[i].name = textureUrls[i];

        }
        return textures;

    }
    skins = loadTextures('data/skins/',skinUrls)

    // load labels
    var loader = new THREE.XHRLoader( this.manager );
    var labelPromise = new Promise(function(resolve, reject) {
        loader.load( "data/labels.json", resolve, undefined, reject)
    }).then((text) => {
        labels = JSON.parse(text)
        return labels
    })

    Promise.all([modelPromise,labelPromise])
        .then(([model, labels]) => setupDatGui(labels))

    // setUpGrids()
    //
    window.addEventListener( 'resize', onWindowResize, false );
    onWindowResize()
}
function onWindowResize() {
    windowHalfX = window.innerWidth / 2;
    windowHalfY = window.innerHeight / 2;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    if ( webglRenderer ) webglRenderer.setSize( window.innerWidth*2/3, window.innerHeight*2/3 );
    // if ( canvasRenderer ) canvasRenderer.setSize( window.innerWidth, window.innerHeight );
}
function createScene( geometry, materials, x, y, z, b ) {
    geometry.computeBoundingBox();
    geometry.computeVertexNormals();

    zmesh = new THREE.SkinnedMesh( geometry, new THREE.MultiMaterial( materials ) );
    zmesh.position.set( x, y, z );
    zmesh.scale.set( 3, 3, 3 );
    zmesh.castShadow = true;
    zmesh.receiveShadow = true;

    // if there are helpers hide them, but show body Or DefaultSkin
    zmesh.material.materials.filter(m=>{
        return typeof(m.name)=='string' ? m.name.startsWith('helper-') || m.name.startsWith('joint-'): ''
    }).map(material=>{
        material.opacity=0
        material.visible=false
        material.transparent = true;
    })

    // set skin
    materials.map(m => m.skinning = true)
    zmesh.material.materials[0].map=skins[0]

    scene.add( zmesh );
    return zmesh
}
function animate() {
    render();
    requestAnimationFrame( animate );
}
function render() {
    controls.update();
    webglRenderer.render( scene, camera );
}

/** Setup grids for comparison **/
function setUpGrids(){


    // 3 major grids
    var size = 50;
    var grids = new THREE.Group()
    var rotations = [[Math.PI/2,0,0],[0,Math.PI/2,0],[0,0,Math.PI/2]]
    var gridsSmall = rotations.map(coords=>{
        grid = new THREE.GridHelper( size, 30 );
        grid.position.set(0,FLOOR,0)
        // grid.material.linewidth=0.5
        grid.material.transparent=true
        grid.material.opacity=0.3
        grid.rotation.set(...coords)
        return grid

    })
    gridsSmall.map(grid=>grids.add(grid))


    var gridsLarge = rotations.map(coords=>{
        grid = new THREE.GridHelper( size, 6 );
        grid.position.set(0,FLOOR,0)
        // grid.material.linewidth=1.5
        grid.rotation.set(...coords)
        return grid

    })
    gridsLarge.map(grid=>grids.add(grid))

    scene.add( grids );
}
