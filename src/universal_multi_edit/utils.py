import bpy


def new_proxy_object(context, name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)
    return obj


def active_color_name(obj):

    if not obj.data.color_attributes:
        return None

    a = obj.data.color_attributes.active_color
    if a:
        return a.name

    return obj.data.color_attributes[0].name


def has_shape_keys(obj):
    return obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 0


def apply_shape_key_delta(obj, deltas):

    keys = obj.data.shape_keys.key_blocks

    if obj.data.shape_keys.use_relative:
        for kb in keys:
            for idx, delta in deltas.items():
                kb.data[idx].co += delta
    else:
        kb = keys[0]
        for idx, delta in deltas.items():
            kb.data[idx].co += delta


def get_multires(obj):
    for mod in obj.modifiers:
        if mod.type == "MULTIRES":
            return mod
    return None


def get_proxy_mesh(context, obj):

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


def ensure_active_color_layer(mesh, name):
    layer = mesh.color_attributes.get(name)

    if layer is None:
        layer = mesh.color_attributes.new(name=name, domain="CORNER", type="BYTE_COLOR")

    mesh.color_attributes.active_color = layer
    return layer
