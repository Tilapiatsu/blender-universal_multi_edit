import bpy
import functools

from bpy.app.handlers import persistent

from .session import UME_Session
from .state_machine import UME_State

from . import sculpt
from . import vpaint
from . import wpaint
from . import tpaint

SESSION = None

SUPPORTED = {
    "SCULPT",
    "VERTEX_PAINT",
    "WEIGHT_PAINT",
    "TEXTURE_PAINT",
}

MODE_MODULES = {
    "SCULPT": sculpt,
    "VERTEX_PAINT": vpaint,
    "WEIGHT_PAINT": wpaint,
    "TEXTURE_PAINT": tpaint,
}


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------


def selected_meshes(ctx):

    return [o for o in ctx.selected_objects if o.type == "MESH"]


def current_mode(ctx):
    obj = ctx.active_object

    if not obj:
        return "OBJECT"

    return obj.mode


# ---------------------------------------------------------
# SESSION MANAGEMENT
# ---------------------------------------------------------


def create_session(ctx, mode):
    global SESSION
    objs = selected_meshes(ctx)

    if len(objs) <= 1:
        return None

    s = UME_Session()
    s.mode = mode
    s.objects = [o.name for o in objs]
    s.capture_scene_state(ctx)
    SESSION = s
    return s


def destroy_session():
    global SESSION
    SESSION = None


# ---------------------------------------------------------
# CLEANUP
# ---------------------------------------------------------


def cleanup_session(ctx):
    global SESSION

    if not SESSION:
        return

    proxy = SESSION.proxy

    # -----------------------------------------
    # remove proxy
    # -----------------------------------------

    if proxy:
        try:
            bpy.data.objects.remove(proxy, do_unlink=True)
        except:
            pass

    # -----------------------------------------
    # restore scene
    # -----------------------------------------

    SESSION.restore_scene_state(ctx)


# ---------------------------------------------------------
# ENTER
# ---------------------------------------------------------


def enter_mode(ctx, mode):
    global SESSION
    if SESSION:
        return

    session = create_session(ctx, mode)

    if not session:
        return

    module = MODE_MODULES[mode]

    try:
        if ctx.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        proxy = module.create_proxy(ctx, list(session.iter_objects()), session)

        session.proxy_name = proxy.name

        # -------------------------------------
        # hide originals
        # -------------------------------------

        for obj in session.iter_objects():
            obj.hide_set(True)

        # -------------------------------------
        # activate proxy
        # -------------------------------------

        bpy.ops.object.select_all(action="DESELECT")

        proxy.hide_set(False)
        proxy.select_set(True)

        ctx.view_layer.objects.active = proxy

        # -------------------------------------
        # switch mode
        # -------------------------------------

        bpy.ops.object.mode_set(mode=mode)

        session.state = UME_State.ACTIVE

        # -------------------------------------
        # start monitor
        # -------------------------------------

        if not session.monitor_running:
            session.monitor_running = True
            bpy.app.timers.register(session_monitor, first_interval=0.1)

    except Exception as e:
        print("UME ENTER ERROR:", e)
        cleanup_session(ctx)
        destroy_session()


# ---------------------------------------------------------
# EXIT
# ---------------------------------------------------------


def exit_mode(ctx):
    global SESSION
    if not SESSION:
        return

    session = SESSION

    if session.state != UME_State.ACTIVE:
        return

    session.state = UME_State.EXITING
    module = MODE_MODULES[session.mode]

    try:
        module.transfer_back(ctx, session)

    except Exception as e:
        print("UME EXIT ERROR:", e)

    cleanup_session(ctx)
    session.monitor_running = False
    session.state = UME_State.IDLE
    destroy_session()


def session_monitor():
    global SESSION
    if not SESSION:
        return None

    ctx = bpy.context
    proxy = SESSION.proxy

    # -----------------------------------------
    # proxy deleted manually
    # -----------------------------------------

    if not proxy:
        try:
            exit_mode(ctx)
        except Exception as e:
            print("UME MONITOR:", e)

        return None

    # -----------------------------------------
    # user exited mode
    # -----------------------------------------

    mode = proxy.mode if proxy else "OBJECT"

    if mode != SESSION.mode:
        try:
            exit_mode(ctx)
        except Exception as e:
            print("UME MONITOR:", e)

        return None

    return 0.1


# ---------------------------------------------------------
# WATCHER
# ---------------------------------------------------------


@persistent
def ume_watcher(scene):
    global SESSION
    ctx = bpy.context

    if SESSION:
        return

    obj = ctx.active_object

    if not obj:
        return

    mode = obj.mode

    if mode not in SUPPORTED:
        return

    if len(selected_meshes(ctx)) <= 1:
        return

    bpy.app.timers.register(functools.partial(_safe_enter, ctx, mode), first_interval=0.01)


# ---------------------------------------------------------
# SAFE WRAPPERS
# ---------------------------------------------------------


def _safe_enter(ctx, mode):
    try:
        enter_mode(ctx, mode)

    except Exception as e:
        print("UME SAFE ENTER:", e)


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------


def register():
    if ume_watcher not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(ume_watcher)


def unregister():
    if ume_watcher in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(ume_watcher)
