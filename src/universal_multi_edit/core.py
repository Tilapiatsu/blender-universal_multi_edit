from __future__ import annotations
import bpy

from bpy.app.handlers import persistent
from functools import partial
from typing import Union

from .session import UME_Session

from . import sculpt
from . import vpaint
from . import wpaint
from . import tpaint

from .protocol import UME_P_Core
from .safe_object import UME_SafeObject


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
    session: Union[UME_Session, None]

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

    def create_session(self, ctx, mode: str) -> Union[UME_Session, None]:
        objs = selected_meshes(ctx)

        if len(objs) <= 1:
            return None

        from .session import UME_Session
        from .state_machine import IdleState

        s = UME_Session()
        s.mode = mode
        s.state = IdleState(self)
        s.objects = [UME_SafeObject(o) for o in objs]
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

        if proxy and proxy.object:
            try:
                bpy.data.objects.remove(proxy.object, do_unlink=True)
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


def get_session():
    global CORE
    return CORE.session


def validate_session():
    global CORE

    session = CORE.session

    if not session:
        return

    proxy = session.proxy

    if proxy is None or proxy.object is None:
        print("UME: proxy disappeared after undo")
        CORE.destroy_session()


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


@persistent
def ume_undo_handler(scene):

    session = get_session()

    if not session:
        return

    validate_session()


@persistent
def ume_undo_post(scene):

    session = get_session()

    if session:
        session.need_recovery = True


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------


def register():
    if ume_watcher not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(ume_watcher)

    if ume_undo_handler not in bpy.apps.handlers.undo_post:
        bpy.app.handlers.undo_post.append(ume_undo_handler)
        bpy.app.handlers.undo_post.append(ume_undo_post)

    if ume_undo_handler not in bpy.apps.handlers.redo_post:
        bpy.app.handlers.redo_post.append(ume_undo_handler)


def unregister():
    if ume_watcher in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(ume_watcher)

    if ume_undo_handler in bpy.apps.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(ume_undo_handler)
        bpy.app.handlers.undo_post.remove(ume_undo_post)

    if ume_undo_handler in bpy.apps.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(ume_undo_handler)
