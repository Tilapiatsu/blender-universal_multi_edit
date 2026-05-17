from __future__ import annotations
import bpy

from bpy.app.handlers import persistent
from functools import partial
from .session import UME_Session
from .edit_mode import UME_EditMode
from . import sculpt
from . import vpaint
from . import wpaint
from . import tpaint

from enum import Enum
from typing import Protocol, Union
from dataclasses import dataclass

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


class UME_State(Enum):
    IDLE = "IDLE"
    EDIT = "EDIT"
    EXITING = "EXITING"


class UME_Core:
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

    def create_session(self, ctx, mode):
        objs = selected_meshes(ctx)

        if len(objs) <= 1:
            return None

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

    def manage_session(self, context, mode) -> None:
        if self.session:
            return

        self.session = self.create_session(context, mode)

        if not self.session:
            return

        module = MODE_MODULES[mode].Mode()

        self.session.state = EditState(self, module)

        try:
            self.session.state.enter(context)

        except Exception as e:
            self.cleanup_session(context)
            self.destroy_session()


CORE = UME_Core()


class UME_EditModeState(Protocol):
    core: UME_Core
    name: UME_State

    def enter(self, context) -> None: ...

    def exit(self, context, mode: str = "OBJECT") -> None: ...

    def monitor(self) -> Union[float, None]: ...


@dataclass
class IdleState(UME_EditModeState):
    core: UME_Core
    name = UME_State.IDLE

    def __init__(self, core: UME_Core) -> None:
        self.core = core

    def enter(self, context) -> None:
        print("Entering OBJECT mode")

    def exit(self, context, mode: str = "OBJECT") -> None: ...

    def monitor(self) -> Union[float, None]: ...


@dataclass
class EditState(UME_EditModeState):
    core: UME_Core
    module: UME_EditMode
    name = UME_State.EDIT

    def __init__(self, core: UME_Core, module: UME_EditMode) -> None:
        self.core = core
        self.module = module

    def enter(self, context) -> None:
        mode = self.module.name
        print(f"Entering {mode} mode")
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            session = self.core.session
            if session is None:
                return

            proxy = self.module.create_proxy(context, list(session.iter_objects()), session)
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

            context.view_layer.objects.active = proxy

            # -------------------------------------
            # switch mode
            # -------------------------------------

            bpy.ops.object.mode_set(mode=mode)

            # -------------------------------------
            # start monitor
            # -------------------------------------

            if not session.monitor_running:
                session.monitor_running = True
                bpy.app.timers.register(self.monitor, first_interval=0.1)

        except Exception as e:
            print("UME ENTER ERROR:", e)

    def exit(self, context, mode: str = "OBJECT") -> None:
        session = self.core.session
        if not session:
            return

        print(f"Exiting {session.mode} mode")

        if session.state is None:
            return

        if session.state.name != UME_State.EDIT:
            return

        try:
            self.module.transfer_back(context, session)

        except Exception as e:
            print("UME EXIT ERROR:", e)

        self.core.cleanup_session(context)
        session.monitor_running = False
        if mode in SUPPORTED:
            session.state = EditState(self.core, MODE_MODULES[mode].Mode())
            session.mode = mode
            session.state.enter(context)
        else:
            session.state = IdleState(self.core)
            self.core.destroy_session()

    def monitor(self) -> Union[float, None]:
        session = self.core.session
        if not session:
            return

        ctx = bpy.context
        proxy = session.proxy

        # -----------------------------------------
        # proxy deleted manually
        # -----------------------------------------

        if not proxy:
            try:
                self.exit(ctx)
            except Exception as e:
                print("UME MONITOR:", e)

            return None

        # -----------------------------------------
        # user exited mode
        # -----------------------------------------

        mode = proxy.mode
        if mode != session.mode:
            try:
                if mode in SUPPORTED:
                    self.exit(ctx, mode)
                else:
                    self.exit(ctx)
            except Exception as e:
                print("UME MONITOR:", e)

            return None

        return 0.1


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
