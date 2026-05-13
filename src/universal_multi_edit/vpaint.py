import bpy, bmesh

NAME = "__UME_COLOR__"


def linear_to_srgb(c):
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _read_color(attr, idx):
    c = attr.data[idx].color[:]
    return (float(c[0]), float(c[1]), float(c[2]), float(c[3]))


def _ensure_proxy_attr(me):
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    return me.color_attributes.new(name=NAME, domain="CORNER", type="FLOAT_COLOR")


def create_proxy(ctx, objects, session):
    me = bpy.data.meshes.new("UME_VPaint")
    bm = bmesh.new()
    session["map"] = []
    for obj in objects:
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)
        src.faces.ensure_lookup_table()
        src.verts.ensure_lookup_table()
        attr = obj.data.color_attributes.active_color if obj.data.color_attributes else None
        vmap = {v: bm.verts.new(v.co) for v in src.verts}
        bm.verts.ensure_lookup_table()
        for f in src.faces:
            try:
                nf = bm.faces.new([vmap[v] for v in f.verts])
            except:
                continue
            for ls in f.loops:
                # support POINT and CORNER domains
                if attr:
                    src_idx = ls.vert.index if attr.domain == "POINT" else ls.index
                    col = _read_color(attr, src_idx) if src_idx < len(attr.data) else (1, 1, 1, 1)
                else:
                    col = (1, 1, 1, 1)
                session["map"].append((obj.name, attr.domain if attr else "CORNER", ls.vert.index, ls.index, col))
        src.free()
    bm.to_mesh(me)
    bm.free()
    proxy = bpy.data.objects.new("UME_Proxy", me)
    ctx.scene.collection.objects.link(proxy)
    pa = _ensure_proxy_attr(me)
    # write colors after mesh exists
    for i, item in enumerate(session["map"]):
        if i < len(pa.data):
            pa.data[i].color = item[4]
    me.color_attributes.active_color = pa
    return proxy


def transfer_back(ctx, session):
    p = bpy.data.objects.get(session["proxy"])
    if not p:
        return
    src = p.data.color_attributes.get(NAME)
    if not src:
        return
    count = min(len(src.data), len(session["map"]))
    for i in range(count):
        oname, domain, vidx, lidx, _ = session["map"][i]
        o = bpy.data.objects.get(oname)
        if not o:
            continue
        if not o.data.color_attributes:
            attr = o.data.color_attributes.new(name="Color", domain=domain, type="FLOAT_COLOR")
        else:
            attr = o.data.color_attributes.active_color
            if attr.domain != domain:
                attr = o.data.color_attributes.new(name=attr.name + "_UME", domain=domain, type="FLOAT_COLOR")
        dst_idx = vidx if domain == "POINT" else lidx
        if dst_idx < len(attr.data):
            attr.data[dst_idx].color = _read_color(src, i)
        o.data.update()
