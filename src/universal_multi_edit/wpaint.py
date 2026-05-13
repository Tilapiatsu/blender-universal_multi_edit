import bpy, bmesh

NAME = "__UME_WEIGHT__"


def active_group(obj):
    vg = obj.vertex_groups.active
    return vg.name if vg else obj.vertex_groups.new(name="Group").name


def create_proxy(ctx, objects, session):
    me = bpy.data.meshes.new("UME_WPaint")
    bm = bmesh.new()
    session["vert_map"] = []
    group = active_group(ctx.view_layer.objects.active)
    session["group"] = group
    for obj in objects:
        vmap = {}
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)
        for v in src.verts:
            nv = bm.verts.new(v.co)
            vmap[v] = nv
            session["vert_map"].append((obj.name, v.index))
        bm.verts.ensure_lookup_table()
        for f in src.faces:
            try:
                bm.faces.new([vmap[v] for v in f.verts])
            except:
                pass
        src.free()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("UME_Proxy", me)
    ctx.scene.collection.objects.link(obj)
    if group:
        obj.vertex_groups.new(name=group)
    vg = obj.vertex_groups.active
    for i, (oname, vi) in enumerate(session["vert_map"]):
        src_obj = bpy.data.objects.get(oname)
        if not src_obj or not group:
            continue
        g = src_obj.vertex_groups.get(group)
        w = 0.0
        if g:
            try:
                w = g.weight(vi)
            except:
                pass
        vg.add([i], w, "REPLACE")
    return obj


def transfer_back(ctx, session):
    p = bpy.data.objects.get(session["proxy"])
    if not p:
        return
    group = session.get("group")
    vg = p.vertex_groups.get(group) if group else None
    if not vg:
        return
    for i, (oname, vi) in enumerate(session["vert_map"]):
        o = bpy.data.objects.get(oname)
        if not o:
            continue
        dst = o.vertex_groups.get(group) or o.vertex_groups.new(name=group)
        try:
            w = vg.weight(i)
        except:
            w = 0.0
        dst.add([vi], w, "REPLACE")
