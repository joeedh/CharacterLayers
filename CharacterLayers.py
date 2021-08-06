import bpy, bmesh, random, time
from bpy.props import *

def obkey(ob):
  if ob.library:
    return ob.name + ":|:" + ob.library.filepath
  else:
    return ob.name + ":|:"

def getob(key):
  key = key.split(":|:")
  name, lib = key
  
  if lib.strip() == '':    
    return bpy.data.objects[name] if name in bpy.data.objects else None
    
  for ob in bpy.data.objects:
    lib2 = "" if not ob.library else ob.library.filepath

    if lib == lib2 and ob.name == name:
      return ob
    
class DepCache:
  def __init__(self):
    self.cache = {}
  
  def get(self, ob):
    if obkey(ob) in self.cache:
      return self.cache[obkey(ob)]
    
    ret = []
    self.cache[obkey(ob)] = ret
    return ret
  
  def link(self, a, b):
    self.get(a).append(obkey(b))
    self.get(b).append(obkey(a))
    
  def clear(self, ob):
    self.cache[obkey(ob)] = []

class GlobalData:
  def __init__(self):
      self.dcache = DepCache()
      self.last_update_key = None
      self.version = 29
      self.timer = None
      self.onrender = None
      self.onframe = None
      self.filepath = bpy.data.filepath
      
def addonBackup():
  def visUpdate(self, context):
      ob = self.id_data
      
      depends = bpy._characterLayers.dcache.get(ob)
      print("DEPENDS", depends)
      
      for dep in depends:
          dst = getob(dep)
          
          if not dst:
              print("failed to find", dep)
              continue
          
          cl = dst.characterLayers
          
          ok = False
          for i in range(len(cl.layers)):
              if cl.layers[i] and self.visibleLayers[i]:
                  ok = True
                  break
          
          try:
              dst.hide_render = not ok
              dst.hide_set(not ok)
          except:
              print("failed to hide " + dst.name_full)
              continue
                      
          print(dst.name_full, "hidden:", not ok)

  deflayers = [False for x in range(32)]
  deflayers[0] = True
  
  if not hasattr(bpy, "_characterLayers"):
      bpy._characterLayers = GlobalData()

  bpy._characterLayers.filepath = bpy.data.filepath
  
  def onFrame(scene):
    flagUpdate()
    
  def onRender(arg):
      print("ON RENDER!")
      
      #prevent crash in viewport
      ctx.scene.render.use_lock_interface = True
      
      #update visibility
      vlayer = bpy.context.view_layer
      for ob in vlayer.objects:
          cl = ob.characterLayers
          if cl.isController:
              visUpdate(cl, bpy.context)

  if bpy._characterLayers.onrender:
      if bpy._characterLayers.onrender in bpy.app.handlers.render_pre:
          bpy.app.handlers.render_pre.remove(bpy._characterLayers.onrender)
  if hasattr(bpy._characterLayers, 'onframe') and bpy._characterLayers.onframe:
      if bpy._characterLayers.onframe in bpy.app.handlers.frame_change_post:
          bpy.app.handlers.frame_change_post.remove(bpy._characterLayers.onframe)
  
  bpy._characterLayers.onrender = onRender
  bpy._characterLayers.onframe = onFrame
  
  bpy.app.handlers.render_pre.append(onRender)
  bpy.app.handlers.frame_change_post.append(onFrame)
  
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
      
      dcache = bpy._characterLayers.dcache

      for ob in obs:
          dcache.clear(ob)
      
      for ob in obs:
          cl = ob.characterLayers
          if cl.isController: continue
          
          dst = cl.getSourceMaskOb()
          if not dst: continue
      
          print("LINK", obkey(ob), obkey(dst))
          
          dcache.link(ob, dst)

      for ob in obs:
        cl = ob.characterLayers
        
        if cl.isController:
          visUpdate(cl, bpy.context)          
      
  def checkUpdateDepends(ctx=bpy.context):
      key = ctx.scene.name + ":" + bpy.data.filepath
      vlayer = ctx.view_layer
      key += ":" + str(len(vlayer.objects))
      key += ":" + str(ctx.scene.frame_current)
      
      if key != bpy._characterLayers.last_update_key:
          bpy._characterLayers.last_update_key = key
          
          print("rebuilding dependency list for character layers");
          updateDepends(ctx)

  def timer_loop():
      if timer_loop != bpy._characterLayers.timer:
          return
      
      try:
        checkUpdateDepends()
      except:
        import traceback
        
        try:
          traceback.print_last()
        except:
          pass
          
        print("error in checkUpdateDepends")
        
      return 0.125

  bpy._characterLayers.timer = timer_loop
  bpy.app.timers.register(timer_loop)

  def layersUpdate(self, context):
    flagUpdate()

  class CharacterLayers (bpy.types.PropertyGroup):
      #used by cloth objects
      layers   : BoolVectorProperty(size=32, update=layersUpdate, override={'LIBRARY_OVERRIDABLE'}, default=deflayers, subtype="LAYER", options={"LIBRARY_EDITABLE", "ANIMATABLE"})
      
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
      visibleLayers : BoolVectorProperty(size=32, subtype="LAYER",  update=visUpdate, override={'LIBRARY_OVERRIDABLE'}, options={"LIBRARY_EDITABLE", "ANIMATABLE"})
      
      
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

try:
    import rig_character_layers
except:
    #multiple rigs may have different version of the addon,
    #use the latest one
    
    bad = False
    
    if hasattr(bpy, "_characterLayers"):
        bad = bpy._characterLayers.version >= GlobalData().version
        
        #we have to re-add timer handler 
        #when file path changes
        bad = bad and bpy._characterLayers.filepath == bpy.data.filepath
    
    if not bad:
      addonBackup()
