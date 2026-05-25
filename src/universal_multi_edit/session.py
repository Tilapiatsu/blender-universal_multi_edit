from __future__ import annotations
import bpy
import uuid
from typing import Union

from .utils import select_all
from .protocol import UME_P_Session, UME_P_EditModeState
from .safe_object import UME_SafeObject


def topology_object_from_vertex(session: UME_Session, proxy_vert_index: int):

    for topo in session.topology["objects"]:
        start = topo["vert_start"]
        end = start + topo["vert_count"]

        if start <= proxy_vert_index < end:
            local_index = proxy_vert_index - start

            return topo["object"], local_index

    return None, None


def topology_object_from_face(session: UME_Session, proxy_face_index: int):

    for topo in session.topology["objects"]:
        start = topo["face_start"]
        end = start + topo["face_count"]

        if start <= proxy_face_index < end:
            local_index = proxy_face_index - start

            return topo["object"], local_index

    return None, None


def topology_object_from_loop(session: UME_Session, proxy_loop_index: int):

    for topo in session.topology["objects"]:
        start = topo["loop_start"]
        end = start + topo["loop_count"]

        if start <= proxy_loop_index < end:
            local_index = proxy_loop_index - start

            return topo["object"], local_index

    return None, None


class UME_Session(UME_P_Session):
    mode: Union[str, None]
    state: Union[UME_P_EditModeState, None]

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.mode = None
        self._proxy: Union[UME_SafeObject, None] = None
        self.objects: list[UME_SafeObject] = []
        self.active_object: Union[UME_SafeObject, None] = None
        self.hidden_states = {}
        self.selection_states = {}
        self.data = {}
        self.state = None
        self.monitor_running = False
        self.topology = {"objects": []}
        self.need_recovery = False
        self.proxy_undo = False

    # -----------------------------------------------------
    # PROXY
    # -----------------------------------------------------

    @property
    def proxy(self) -> Union[UME_SafeObject, None]:
        return self._proxy

    @proxy.setter
    def proxy(self, obj: Union[UME_SafeObject, bpy.types.Object]) -> None:
        if obj:
            if isinstance(obj, UME_SafeObject):
                self._proxy = obj
            elif isinstance(obj, bpy.types.Object):
                self._proxy = UME_SafeObject(obj)
            else:
                pass

    # -----------------------------------------------------
    # OBJECTS
    # -----------------------------------------------------

    def iter_objects(self):
        for o in self.objects:
            if o.object:
                yield o

    # -----------------------------------------------------
    # STORE SELECTION
    # -----------------------------------------------------

    def capture_scene_state(self, ctx):
        self.active_object = UME_SafeObject(ctx.view_layer.objects.active) if ctx.view_layer.objects.active else None

        for obj in ctx.scene.objects:
            self.selection_states[UME_SafeObject(obj)] = obj.select_get()

        for obj in self.iter_objects():
            self.hidden_states[obj] = obj.object.hide_get()

    # -----------------------------------------------------
    # RESTORE
    # -----------------------------------------------------

    def restore_scene_state(self, ctx):
        select_all(False)

        for obj, hidden in self.hidden_states.items():
            if obj and obj.object:
                obj.hide_set(hidden)

        for obj, selected in self.selection_states.items():
            if obj and obj.object:
                obj.select_set(selected)

        if not self.active_object or not self.active_object.object:
            return

        active = self.active_object.object

        if active:
            ctx.view_layer.objects.active = active

    def set(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, key):
        return key in self.data

    def __repr__(self) -> str:
        return str(
            {
                "id": self.id,
                "mode": self.mode,
                "proxy": self.proxy,
                "objects": self.objects,
                "active_object": self.active_object,
                "hidden_states": self.hidden_states,
                "selection_states": self.selection_states,
                "data": self.data,
                "state": self.state,
                "monitor_running": self.monitor_running,
            }
        )
