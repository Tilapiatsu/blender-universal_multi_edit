import bpy
from .protocol import UME_P_SafeObject


class UME_SafeObject(UME_P_SafeObject):
    def __init__(self, object: bpy.types.Object) -> None:
        self.name = object.name

    @property
    def object(self) -> bpy.types.Object:
        if self.is_valid_object:
            return bpy.data.objects.get(self.name)
        return None

    @object.setter
    def object(self, obj) -> None:
        self.name = obj.name

    @property
    def is_valid_object(self) -> bool:
        obj = bpy.data.objects.get(self.name)

        try:
            return obj is not None and obj.name in bpy.data.objects
        except Exception:
            return False

    @property
    def object_in_view_layer(self) -> bool:
        obj = bpy.data.objects.get(self.name)

        if not self.is_valid_object:
            return False

        try:
            return obj.name in {o.name for o in bpy.context.view_layer.objects}
        except Exception:
            return False

    @property
    def modifiers(self):
        return self.object.modifiers

    @property
    def matrix_world(self):
        return self.object.matrix_world

    @property
    def matrix_local(self):
        return self.object.matrix_local

    @property
    def data(self):
        return self.object.data

    @property
    def mode(self) -> str:
        return self.object.mode

    @property
    def vertex_groups(self) -> bpy.types.VertexGroups:
        return self.object.vertex_groups

    def shape_key_add(self, name: str, from_mix=False) -> None:
        self.object.shape_key_add(name=name, from_mix=from_mix)

    def evaluated_get(self, dependency_depsgraph):
        return self.object.evaluated_get(dependency_depsgraph)

    def select_set(self, select: bool) -> None:
        if self.object_in_view_layer:
            self.object.select_set(select)

    def hide_set(self, hide: bool) -> None:
        if self.object_in_view_layer:
            self.object.hide_set(hide)

    def __repr__(self) -> str:
        return self.name
