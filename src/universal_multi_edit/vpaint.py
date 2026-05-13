import bpy
import bmesh
from .utils import new_proxy_object, active_color_name, ensure_active_color_layer


def create_proxy(context, objects, session):

    mesh = bpy.data.meshes.new("UME_VPaint")
    bm = bmesh.new()

    mapping = []

    active = context.view_layer.objects.active
    cname = active_color_name(active)

    if cname:
        ensure_active_color_layer(mesh, cname)
        mesh.color_attributes.active_color_index = mesh.color_attributes.find(cname)

    for obj in objects:
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)

        src.verts.ensure_lookup_table()
        src.faces.ensure_lookup_table()

        color_layer = None

        if cname and cname in obj.data.color_attributes:
            color_layer = src.loops.layers.color.verify()

        vmap = {}

        for i, v in enumerate(src.verts):
            nv = bm.verts.new(v.co)
            vmap[v] = nv
            mapping.append((obj.name, i))

        bm.verts.ensure_lookup_table()

        dst_color = ensure_active_color_layer(obj, cname)

        for f in src.faces:
            nf = bm.faces.new([vmap[v] for v in f.verts])

            for l_src, l_dst in zip(f.loops, nf.loops):
                if color_layer:
                    l_dst[dst_color] = l_src[color_layer]

        src.free()

    bm.to_mesh(mesh)
    bm.free()

    proxy = new_proxy_object(context, "UME_Proxy", mesh)

    session["proxy_name"] = proxy.name
    session["mapping"] = mapping
    session["active_color"] = cname

    return proxy


def transfer_back(context, session):

    proxy = bpy.data.objects.get(session["proxy_name"])
    if not proxy:
        return

    if not proxy.data.color_attributes:
        return

    layer_name = session["active_color"]

    src = proxy.data.color_attributes.get(layer_name)

    if not src:
        return

    for name in session["originals"]:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue

        dst = obj.data.color_attributes.get(session["active_color"])

        if not dst:
            dst = obj.data.color_attributes.new(name=session["active_color"], domain="CORNER", type="BYTE_COLOR")

        count = min(len(dst.data), len(src.data))

        for i in range(count):
            dst.data[i].color = src.data[i].color

        obj.data.update()
