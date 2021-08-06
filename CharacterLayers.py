import bpy, bmesh, random, time
from bpy.props import *

def visUpdate(self, context):
    ob = self.id_data
    for dep in self.depends:
        if not dep.object:
            continue
        
        cl = dep.object.characterLayers
        ok = False
        for i in range(len(cl.layers)):
            if cl.layers[i] and self.visibleLayers[i]:
                ok = True
                break
        
        try:
            dep.object.hide_render = not ok
            dep.object.hide_set(not ok)
        except:
            print("failed to hide" + dep.object.name)
            continue
                    
        print("OK", ok)

deflayers = [False for x in range(32)]
deflayers[0] = True

class GlobalData:
    def __init__(self):
        self.last_update_key = None
        self.version = 0
        self.timer = None
        self.onrender = None
        
if not hasattr(bpy, "_characterLayers"):
    bpy._characterLayers = GlobalData()

def onRender(arg):
    print("ON RENDER!")
    
    #update visibility
    vlayer = bpy.context.view_layer
    for ob in vlayer.objects:
        cl = ob.characterLayers
        if cl.isController:
            visUpdate(cl, bpy.context)

if bpy._characterLayers.onrender:
    if bpy._characterLayers.onrender in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(bpy._characterLayers.onrender)

bpy._characterLayers.onrender = onRender
bpy.app.handlers.render_pre.append(onRender)
    
if bpy._characterLayers.version != GlobalData().version:
    bpy._characterLayers = GlobalData()

def flagUpdate():
  bpy._characterLayers.last_update_key = None
  
def updateDepends(ctx=bpy.context):
    print("updating dependencies for scene")
    vlayer = ctx.view_layer
    
    obs = []
    for ob in vlayer.objects:
        cl = ob.characterLayers

        if cl.maskSourceType != "NONE":
            obs.append(ob)
            
            if not cl.scriptRef:
                cl.scriptRef = bpy.data.texts["CharacterLayers.py"]
                ob["_clScriptRef"] = bpy.data.texts["CharacterLayers.py"]
    
    for ob in obs:
        cl = ob.characterLayers
        cl.depends.clear()
    
    for ob in obs:
        cl = ob.characterLayers
        if cl.isController: continue
        
        dst = cl.getSourceMaskOb()
        if not dst: continue
    
        link = cl.depends.add()
        link.object = dst
        
        cl2 = dst.characterLayers
        
        link2 = cl2.depends.add()
        link2.object = ob
            
        print(link, link2)
    print(obs)
    
def checkUpdateDepends(ctx=bpy.context):
    key = ctx.scene.name + ":" + bpy.data.filepath
    
    if key != bpy._characterLayers.last_update_key:
        bpy._characterLayers.last_update_key = key
        
        print("rebuilding dependency list for character layers");
        updateDepends(ctx)

def timer_loop():
    if timer_loop != bpy._characterLayers.timer:
        return
    
    checkUpdateDepends()
    
    return 0.125

bpy._characterLayers.timer = timer_loop
bpy.app.timers.register(timer_loop)

#dependency link list is rebuilt at every file load
class DependLink (bpy.types.PropertyGroup):
    object : PointerProperty(type=bpy.types.Object)
    
bpy.utils.register_class(DependLink)

def layersUpdate(self, context):
  flagUpdate()

class CharacterLayers (bpy.types.PropertyGroup):
    #used by cloth objects
    layers   : BoolVectorProperty(size=32, update=layersUpdate, override={'LIBRARY_OVERRIDABLE'}, default=deflayers, subtype="LAYER", options={"LIBRARY_EDITABLE"})
    depends  : CollectionProperty(type=DependLink, override={'LIBRARY_OVERRIDABLE'})
    
    maskSourceType : EnumProperty(items=[
        ("NONE", "None", "", 0),
        ("OBJECT", "Object", "", 1),
        ("ARMATURE", "Armature Modifier", "", 2)
    ])
    
    maskSourceOb: PointerProperty(type=bpy.types.Object)
    #backref to linked in script
    scriptRef : PointerProperty(type=bpy.types.Text)
    
    #used by dest rig
    isController  : BoolProperty()
    visibleLayers : BoolVectorProperty(size=32, subtype="LAYER",  update=visUpdate, override={'LIBRARY_OVERRIDABLE'}, options={"LIBRARY_EDITABLE"})
    
    
    def getSourceMaskOb(self):
        ob = self.id_data
        ob2 = None
        
        if self.maskSourceType == "OBJECT":
            ob2 = self.maskSourceOb
        elif self.maskSourceType == "ARMATURE":
            for mod in ob.modifiers:
                if mod.type == "ARMATURE":
                    ob2 = mod.object
                    break
            
        if not ob2:
            print("no character layer source mask object")
            return
        
        return ob2
    
bpy.utils.register_class(CharacterLayers)
bpy.types.Object.characterLayers = PointerProperty(type=CharacterLayers)

class CharacterLayersPanel(bpy.types.Panel):
    """"""
    bl_label = "Character Layers"
    bl_idname = "SCENE_PT_character_layers_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        cl = context.object.characterLayers
        layout.prop(cl, "isController")
        
        if not cl.isController:
            layout.label(text="Layers")

            layout.prop(cl, "layers")        
            layout.prop(cl, "maskSourceType")
            if cl.maskSourceType == "OBJECT":
                layout.prop(cl, "maskSourceOb")
        else:
            layout.prop(cl, "visibleLayers")

bpy.utils.register_class(CharacterLayersPanel)
