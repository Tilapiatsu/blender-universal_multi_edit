import bpy
from .session import UME_Session


def new_object(context, name: str, mesh: bpy.types.Mesh):
    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)
    return obj


def active_color(obj: bpy.types.Object):

    if not obj.data.color_attributes:
        return None

    a = obj.data.color_attributes.active_color
    if a:
        return a.name

    return obj.data.color_attributes[0].name


def has_shape_keys(obj: bpy.types.Mesh):
    return obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 0


def apply_shape_key_delta(obj: bpy.types.Object, deltas: dict):

    keys = obj.data.shape_keys.key_blocks

    if obj.data.shape_keys.use_relative:
        for kb in keys:
            for idx, delta in deltas.items():
                kb.data[idx].co += delta
    else:
        kb = keys[0]
        for idx, delta in deltas.items():
            kb.data[idx].co += delta


def get_multires(obj: bpy.types.Object):
    for mod in obj.modifiers:
        if mod.type == "MULTIRES":
            return mod
    return None


def get_proxy_mesh(context, obj: bpy.types.Object):

    mr = get_multires(obj)

    if not mr:
        return obj.data.copy(), False, 0

    old_view = mr.levels
    old_render = mr.render_levels

    level = mr.sculpt_levels

    mr.levels = level
    mr.render_levels = level

    dg = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(dg)

    me = bpy.data.meshes.new_from_object(eval_obj)

    mr.levels = old_view
    mr.render_levels = old_render

    return me, True, level


def ensure_active_color_layer(mesh: bpy.types.Mesh, name: str):
    layer = mesh.color_attributes.get(name)

    if layer is None:
        layer = mesh.color_attributes.new(name=name, domain="CORNER", type="BYTE_COLOR")

    mesh.color_attributes.active_color = layer
    return layer


def deselect_all():
    for o in bpy.context.selected_objects:
        o.select_set(False)


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
