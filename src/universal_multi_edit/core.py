import bpy
from bpy.app.handlers import persistent

from . import sculpt, vpaint, wpaint, tpaint

SESSION = {}

_LAST_MODE = None
PENDING = {"start": False, "finish": False, "mode": None}
_TIMER = False


SUPPORTED = {"SCULPT", "VERTEX_PAINT", "WEIGHT_PAINT", "TEXTURE_PAINT"}


# -------------------------------------------------
def selected_meshes(ctx):
    return [o for o in ctx.selected_objects if o.type == "MESH"]


# -------------------------------------------------
def start(ctx, mode):

    objs = selected_meshes(ctx)
    if len(objs) <= 1:
        return None

    SESSION.clear()

    SESSION["mode"] = mode
    SESSION["objects"] = [o.name for o in objs]
    SESSION["active"] = ctx.view_layer.objects.active.name if ctx.view_layer.objects.active else None
    SESSION["visibility"] = {o.name: o.hide_get() for o in objs}

    proxy = None

    if mode == "SCULPT":
        proxy = sculpt.create_proxy(ctx, objs, SESSION)
    elif mode == "VERTEX_PAINT":
        proxy = vpaint.create_proxy(ctx, objs, SESSION)
    elif mode == "TEXTURE_PAINT":
        proxy = tpaint.create_proxy(ctx, objs, SESSION)
    elif mode == "WEIGHT_PAINT":
        proxy = wpaint.create_proxy(ctx, objs, SESSION)

    if not proxy:
        print("UME: proxy creation failed")
        return None

    # IMPORTANT: force link only here (single authority)
    if proxy.name not in ctx.scene.collection.objects:
        ctx.scene.collection.objects.link(proxy)

    SESSION["proxy"] = proxy.name

    for o in objs:
        o.hide_set(True)

    bpy.ops.object.select_all(action="DESELECT")
    proxy.select_set(True)
    ctx.view_layer.objects.active = proxy

    return proxy


# -------------------------------------------------
def finish(ctx):

    mode = SESSION.get("mode")

    if mode == "SCULPT":
        sculpt.transfer_back(ctx, SESSION)
    elif mode == "VERTEX_PAINT":
        vpaint.transfer_back(ctx, SESSION)
    elif mode == "WEIGHT_PAINT":
        wpaint.transfer_back(ctx, SESSION)
    elif mode == "TEXTURE_PAINT":
        tpaint.transfer_back(ctx, SESSION)

    proxy = bpy.data.objects.get(SESSION.get("proxy"))
    if proxy:
        bpy.data.objects.remove(proxy, do_unlink=True)

    for name, state in SESSION["visibility"].items():
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_set(state)

    bpy.ops.object.select_all(action="DESELECT")

    for n in SESSION["objects"]:
        o = bpy.data.objects.get(n)
        if o:
            o.select_set(True)

    if SESSION.get("active"):
        act = bpy.data.objects.get(SESSION["active"])
        if act:
            ctx.view_layer.objects.active = act

    SESSION.clear()


# -------------------------------------------------
def timer():

    global _TIMER

    ctx = bpy.context

    try:
        if PENDING["start"]:
            PENDING["start"] = False

            if ctx.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            # IMPORTANT: create proxy FIRST
            start(ctx, PENDING["mode"])

            proxy = bpy.data.objects.get(SESSION.get("proxy"))
            if not proxy:
                print("UME: proxy missing after creation")
                return None

            # delay mode switch one tick (CRITICAL FIX)
            def _enter_mode():
                bpy.ops.object.select_all(action="DESELECT")
                proxy.select_set(True)
                ctx.view_layer.objects.active = proxy
                bpy.ops.object.mode_set(mode=PENDING["mode"])
                return None

            bpy.app.timers.register(_enter_mode, first_interval=0.01)

        elif PENDING["finish"]:
            PENDING["finish"] = False

            if ctx.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            finish(ctx)

    except Exception as e:
        print("UME:", e)

    _TIMER = False
    return None


# -------------------------------------------------
@persistent
def watcher(scene):

    global _LAST_MODE, _TIMER

    ctx = bpy.context
    obj = ctx.active_object
    mode = obj.mode if obj else "OBJECT"

    if _LAST_MODE is None:
        _LAST_MODE = mode
        return

    if _LAST_MODE != mode and mode in SUPPORTED:
        if len(selected_meshes(ctx)) > 1:
            PENDING["start"] = True
            PENDING["mode"] = mode

    elif SESSION and _LAST_MODE == SESSION.get("mode") and mode != _LAST_MODE:
        PENDING["finish"] = True

    if (PENDING["start"] or PENDING["finish"]) and not _TIMER:
        _TIMER = True
        bpy.app.timers.register(timer, first_interval=0.01)

    _LAST_MODE = mode


def register():
    bpy.app.handlers.depsgraph_update_post.append(watcher)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(watcher)
