import bpy
import uuid
from .state_machine import UME_State


class UME_Session:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.mode = None
        self.proxy_name = None
        self.objects = []
        self.active_object = None
        self.hidden_states = {}
        self.selection_states = {}
        self.data = {}
        self.running = False
        self.state = UME_State.IDLE
        self.internal_transition = False
        self.monitor_running = False

    # -----------------------------------------------------
    # PROXY
    # -----------------------------------------------------

    @property
    def proxy(self):
        return bpy.data.objects.get(self.proxy_name)

    # -----------------------------------------------------
    # OBJECTS
    # -----------------------------------------------------

    def iter_objects(self):

        for name in self.objects:
            obj = bpy.data.objects.get(name)

            if obj:
                yield obj

    # -----------------------------------------------------
    # STORE SELECTION
    # -----------------------------------------------------

    def capture_scene_state(self, ctx):

        self.active_object = ctx.view_layer.objects.active.name if ctx.view_layer.objects.active else None

        for obj in ctx.scene.objects:
            self.selection_states[obj.name] = obj.select_get()

        for obj in self.iter_objects():
            self.hidden_states[obj.name] = obj.hide_get()

    # -----------------------------------------------------
    # RESTORE
    # -----------------------------------------------------

    def restore_scene_state(self, ctx):
        bpy.ops.object.select_all(action="DESELECT")

        for name, hidden in self.hidden_states.items():
            obj = bpy.data.objects.get(name)

            if obj:
                obj.hide_set(hidden)

        for name, selected in self.selection_states.items():
            obj = bpy.data.objects.get(name)

            if obj:
                obj.select_set(selected)

        active = bpy.data.objects.get(self.active_object)

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
                "proxy_name": self.proxy_name,
                "objects": self.objects,
                "active_object": self.active_object,
                "hidden_states": self.hidden_states,
                "selection_states": self.selection_states,
                "data": self.data,
                "running": self.running,
                "state": self.state,
                "internal_transition": self.internal_transition,
                "monitor_running": self.monitor_running,
            }
        )
