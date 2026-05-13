import bpy
from bpy.app.handlers import persistent

from . import sculpt
from . import vpaint
from . import tpaint

SESSION = {}

_LAST_MODE = None
PENDING_START = False
PENDING_FINISH = False
_TIMER_RUNNING = False
PENDING_MODE = None

SUPPORTED_PROXY_MODES = {
    "SCULPT",
    "VERTEX_PAINT",
    "TEXTURE_PAINT",
}


def selected_meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


def clear_session():
    SESSION.clear()


def start_session(context, mode):

    objs = selected_meshes(context)

    if len(objs) <= 1:
        return

    active = context.view_layer.objects.active

    SESSION["mode"] = mode
    SESSION["originals"] = [o.name for o in objs]
    SESSION["visibility"] = {o.name: o.hide_get() for o in objs}
    SESSION["active_object"] = active.name if active else None

    if mode == "SCULPT":
        proxy = sculpt.create_proxy(context, objs, SESSION)

    elif mode == "VERTEX_PAINT":
        proxy = vpaint.create_proxy(context, objs, SESSION)

    elif mode == "TEXTURE_PAINT":
        proxy = tpaint.create_proxy(context, objs, SESSION)

    else:
        return

    for o in objs:
        o.hide_set(True)

    bpy.ops.object.select_all(action="DESELECT")
    proxy.select_set(True)
    context.view_layer.objects.active = proxy


def finish_session(context):

    mode = SESSION.get("mode")

    if mode == "SCULPT":
        sculpt.transfer_back(context, SESSION)

    elif mode == "VERTEX_PAINT":
        vpaint.transfer_back(context, SESSION)

    elif mode == "TEXTURE_PAINT":
        pass

    proxy = bpy.data.objects.get(SESSION.get("proxy_name"))
    if proxy:
        bpy.data.objects.remove(proxy, do_unlink=True)

    for name, state in SESSION["visibility"].items():
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_set(state)

    bpy.ops.object.select_all(action="DESELECT")

    for name in SESSION["originals"]:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)

    act = bpy.data.objects.get(SESSION["active_object"])
    if act:
        context.view_layer.objects.active = act

    clear_session()


def process_pending():

    global PENDING_START
    global PENDING_FINISH
    global _TIMER_RUNNING
    global PENDING_MODE

    ctx = bpy.context

    try:
        if PENDING_START:
            mode = PENDING_MODE
            PENDING_START = False

            if ctx.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            start_session(ctx, mode)

            proxy = bpy.data.objects.get(SESSION["proxy_name"])

            bpy.ops.object.select_all(action="DESELECT")
            proxy.select_set(True)
            ctx.view_layer.objects.active = proxy
            bpy.ops.object.mode_set(mode=mode)

        elif PENDING_FINISH:
            PENDING_FINISH = False

            if ctx.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            finish_session(ctx)

    except Exception as e:
        print("UME:", e)

    _TIMER_RUNNING = False
    return None


@persistent
def depsgraph_monitor(scene):

    global _LAST_MODE
    global PENDING_START
    global PENDING_FINISH
    global _TIMER_RUNNING
    global PENDING_MODE

    ctx = bpy.context
    obj = ctx.active_object

    mode = obj.mode if obj else "OBJECT"

    if _LAST_MODE is None:
        _LAST_MODE = mode
        return

    if _LAST_MODE != mode and mode in SUPPORTED_PROXY_MODES:
        if len(selected_meshes(ctx)) > 1:
            PENDING_START = True
            PENDING_MODE = mode

    elif SESSION and _LAST_MODE == SESSION.get("mode") and mode != _LAST_MODE:
        PENDING_FINISH = True

    if (PENDING_START or PENDING_FINISH) and not _TIMER_RUNNING:
        _TIMER_RUNNING = True
        bpy.app.timers.register(process_pending, first_interval=0.01)

    _LAST_MODE = mode


def register():
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_monitor)


def unregister():
    if depsgraph_monitor in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_monitor)
