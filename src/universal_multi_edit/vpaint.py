import bpy
import bmesh
from .utils import new_object, active_color

NAME = "__UME_COLOR__"


def create_proxy(ctx, objects, session):
    me = bpy.data.meshes.new("UME_VPaint")
    bm = bmesh.new()
    layer = bm.loops.layers.color.new(NAME)
    session["loop_map"] = []
    for obj in objects:
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)
        attr = obj.data.color_attributes.active_color if obj.data.color_attributes else None
        vmap = {v: bm.verts.new(v.co) for v in src.verts}
        bm.verts.ensure_lookup_table()
        for f in src.faces:
            try:
                nf = bm.faces.new([vmap[v] for v in f.verts])
            except:
                continue
            for ls, ld in zip(f.loops, nf.loops):
                col = (1, 1, 1, 1)
                if attr and ls.index < len(attr.data):
                    col = attr.data[ls.index].color[:]
                ld[layer] = col
                session["loop_map"].append((obj.name, ls.index))
        src.free()
    bm.to_mesh(me)
    bm.free()
    # force FLOAT_COLOR layer to avoid darkening
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    ca = me.color_attributes.new(name=NAME, domain="CORNER", type="FLOAT_COLOR")
    for i in range(min(len(ca.data), len(session["loop_map"]))):
        pass
    obj = bpy.data.objects.new("UME_Proxy", me)
    ctx.scene.collection.objects.link(obj)
    me.color_attributes.active_color = ca
    return obj


def transfer_back(ctx, session):
    p = bpy.data.objects.get(session["proxy"])
    if not p:
        return
    src = p.data.color_attributes.get(NAME)
    if not src:
        return
    count = min(len(src.data), len(session["loop_map"]))
    for i in range(count):
        oname, li = session["loop_map"][i]
        o = bpy.data.objects.get(oname)
        if not o or not o.data.color_attributes:
            continue
        dst = o.data.color_attributes.active_color
        if li < len(dst.data):
            dst.data[li].color = src.data[i].color[:]
        o.data.update()
