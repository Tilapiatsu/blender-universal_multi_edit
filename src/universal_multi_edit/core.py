from __future__ import annotations
import bpy

from bpy.app.handlers import persistent
from functools import partial

from . import sculpt
from . import vpaint
from . import wpaint
from . import tpaint

from .protocol import UME_P_Core


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


class UME_Core(UME_P_Core):
    def __init__(self):
        self.session = None

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def selected_meshes(ctx):
        return [o for o in ctx.selected_objects if o.type == "MESH"]

    @staticmethod
    def current_mode(ctx):
        obj = ctx.active_object

        if not obj:
            return "OBJECT"

        return obj.mode

    # ---------------------------------------------------------
    # SESSION MANAGEMENT
    # ---------------------------------------------------------

    def create_session(self, ctx, mode: str):
        objs = selected_meshes(ctx)

        if len(objs) <= 1:
            return None

        from .session import UME_Session
        from .state_machine import IdleState

        s = UME_Session()
        s.mode = mode
        s.state = IdleState(self)
        s.objects = [o.name for o in objs]
        s.capture_scene_state(ctx)
        self.session = s
        return s

    def destroy_session(self):
        self.session = None

    def cleanup_session(self, ctx):
        if not self.session:
            return

        proxy = self.session.proxy

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

        self.session.restore_scene_state(ctx)

    def manage_session(self, context, mode: str) -> None:
        if self.session:
            return

        self.session = self.create_session(context, mode)

        if not self.session:
            return

        module = MODE_MODULES[mode].Mode()

        from .state_machine import EditState

        self.session.state = EditState(self, module)

        if self.session.state is None:
            return

        try:
            self.session.state.enter(context)

        except Exception as e:
            print(e)
            self.cleanup_session(context)
            self.destroy_session()


CORE = UME_Core()


def selected_meshes(ctx):
    return [o for o in ctx.selected_objects if o.type == "MESH"]


def current_mode(ctx):
    obj = ctx.active_object

    if not obj:
        return "OBJECT"

    return obj.mode


# ---------------------------------------------------------
# WATCHER
# ---------------------------------------------------------


@persistent
def ume_watcher(scene):
    global CORE

    if CORE.session:
        return

    ctx = bpy.context
    obj = ctx.active_object

    if not obj:
        return

    mode = obj.mode

    if mode not in SUPPORTED:
        return

    if len(selected_meshes(ctx)) <= 1:
        return

    bpy.app.timers.register(partial(CORE.manage_session, ctx, mode), first_interval=0.1)


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------


def register():
    if ume_watcher not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(ume_watcher)


def unregister():
    if ume_watcher in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(ume_watcher)
