import bpy
from enum import Enum
from typing import Protocol, Union
from dataclasses import dataclass

from .edit_modes.edit_mode import UME_EditMode
from .core import SUPPORTED, MODE_MODULES
from .protocol import UME_P_Core, UME_P_EditModeState, UME_State
from .utils import select_all


@dataclass
class IdleState(UME_P_EditModeState):
    core: UME_P_Core
    name = UME_State.IDLE

    def __init__(self, core: UME_P_Core) -> None:
        self.core = core

    def enter(self, context) -> None:
        print("Entering OBJECT mode")

    def exit(self, context, mode: str = "OBJECT") -> None: ...

    def monitor(self) -> Union[float, None]: ...


@dataclass
class EditState(UME_P_EditModeState):
    core: UME_P_Core
    module: UME_EditMode
    name = UME_State.EDIT

    def __init__(self, core: UME_P_Core, module: UME_EditMode) -> None:
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

            # -------------------------------------
            # hide originals
            # -------------------------------------

            for obj in session.iter_objects():
                if not obj.object:
                    continue
                obj.hide_set(True)

            # -------------------------------------
            # activate proxy
            # -------------------------------------

            select_all(False)

            proxy.hide_set(False)
            proxy.select_set(True)

            context.view_layer.objects.active = proxy.object

            # -------------------------------------
            # switch mode
            # -------------------------------------

            bpy.ops.object.mode_set(mode=mode)

            bpy.ops.ed.undo_push(message="UME_PROXY_CREATED")

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
            if not session.need_recovery and not session.proxy_undo:
                self.module.transfer_back(context, session)

        except Exception as e:
            print("UME EXIT ERROR:", e)

        self.core.cleanup_session(context)
        session.monitor_running = False
        if mode in SUPPORTED:
            session.state = EditState(self.core, MODE_MODULES[mode].Mode())
            if session.state is None:
                return

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

        if session.need_recovery:
            self.session_recorvery(ctx, session)
            return

        # -----------------------------------------
        # proxy deleted manually
        # -----------------------------------------
        if not proxy.object:
            try:
                if session.proxy_undo:
                    self.core.cleanup_session(ctx)
                    bpy.ops.object.mode_set(mode="OBJECT")
                    self.core.destroy_session()

                else:
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

    def session_recorvery(self, context, session):
        if session and session.need_recovery:
            session.need_recovery = False
            self.core.cleanup_session(context)
