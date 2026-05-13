import bpy
import bmesh
from .utils import new_object, active_color

UME_COLOR = "__UME_VERTEX_COLOR__"


def create_proxy(ctx, objects, session):

    mesh = bpy.data.meshes.new("UME_VPaint")
    bm = bmesh.new()

    color_layer = bm.loops.layers.color.new(UME_COLOR)

    session["loop_map"] = []

    for obj in objects:
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)

        src.faces.ensure_lookup_table()
        src.verts.ensure_lookup_table()

        src_attr = None
        if obj.data.color_attributes:
            src_attr = obj.data.color_attributes.active_color

        vmap = {}

        for v in src.verts:
            vmap[v] = bm.verts.new(v.co)

        bm.verts.ensure_lookup_table()

        for face in src.faces:
            try:
                new_face = bm.faces.new([vmap[v] for v in face.verts])
            except ValueError:
                continue

            for ls, ld in zip(face.loops, new_face.loops):
                # safe color read
                col = (1, 1, 1, 1)

                if src_attr and ls.index < len(src_attr.data):
                    col = src_attr.data[ls.index].color[:]
                    print(src_attr.data[ls.index].color[0])

                ld[color_layer] = col

                # CRITICAL: store exact ownership
                session["loop_map"].append((obj.name, ls.index))

        src.free()

    bm.to_mesh(mesh)
    bm.free()

    proxy = bpy.data.objects.new("UME_Proxy", mesh)
    ctx.scene.collection.objects.link(proxy)

    # force one attribute only
    while len(proxy.data.color_attributes) > 1:
        proxy.data.color_attributes.remove(proxy.data.color_attributes[0])

    attr = proxy.data.color_attributes[0]
    attr.name = UME_COLOR
    proxy.data.color_attributes.active_color = attr
    proxy.data.color_attributes.active_color_index = 0

    session["proxy"] = proxy.name

    return proxy


def transfer_back(ctx, session):

    proxy = bpy.data.objects.get(session["proxy"])
    if not proxy:
        return

    src = proxy.data.color_attributes.get(UME_COLOR)
    if not src:
        return

    loop_map = session.get("loop_map", [])

    count = min(len(loop_map), len(src.data))

    for i in range(count):
        obj_name, loop_index = loop_map[i]

        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        dst = obj.data.color_attributes.active_color
        if not dst:
            continue

        if loop_index >= len(dst.data):
            continue

        dst.data[loop_index].color = src.data[i].color[:]

        obj.data.update()
