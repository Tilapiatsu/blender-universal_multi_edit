import bpy, bmesh

NAME = "__UME_COLOR__"


def _attr_type(attr):
    # Blender version compatibility
    return getattr(attr, "data_type", getattr(attr, "type", "FLOAT_COLOR"))


def _quantize_byte_color(c):
    return (
        round(max(0.0, min(1.0, c[0])) * 255.0) / 255.0,
        round(max(0.0, min(1.0, c[1])) * 255.0) / 255.0,
        round(max(0.0, min(1.0, c[2])) * 255.0) / 255.0,
        round(max(0.0, min(1.0, c[3])) * 255.0) / 255.0,
    )


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
    session["attr_meta"] = {}
    for obj in objects:
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)
        src.faces.ensure_lookup_table()
        src.verts.ensure_lookup_table()
        attr = obj.data.color_attributes.active_color if obj.data.color_attributes else None

        if attr:
            session["attr_meta"][obj.name] = {
                "name": attr.name,
                "domain": attr.domain,
                "type": _attr_type(attr),
            }
        else:
            session["attr_meta"][obj.name] = {
                "name": "Color",
                "domain": "CORNER",
                "type": "FLOAT_COLOR",
            }
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

    proxy = bpy.data.objects.get(session["proxy"])
    if not proxy:
        return

    src = proxy.data.color_attributes.get(NAME)
    if not src:
        return

    count = min(len(src.data), len(session["map"]))

    for i in range(count):
        obj_name, domain, vidx, lidx, _ = session["map"][i]

        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        meta = session["attr_meta"].get(obj_name, None)
        if not meta:
            continue

        # -----------------------------------------
        # Find original attribute by name
        # -----------------------------------------
        attr = obj.data.color_attributes.get(meta["name"])

        if not attr:
            attr = obj.data.color_attributes.new(name=meta["name"], domain=meta["domain"], type=meta["type"])

        # -----------------------------------------
        # Ensure correct domain
        # -----------------------------------------
        if attr.domain != meta["domain"]:
            attr = obj.data.color_attributes.new(name=meta["name"] + "_UME", domain=meta["domain"], type=meta["type"])

        dst_index = vidx if meta["domain"] == "POINT" else lidx

        if dst_index >= len(attr.data):
            continue

        color = src.data[i].color[:]

        # -----------------------------------------
        # CRITICAL FIX:
        # BYTE_COLOR explicit quantization
        # -----------------------------------------
        if meta["type"] == "BYTE_COLOR":
            color = _quantize_byte_color(color)

        attr.data[dst_index].color = color

        obj.data.update()
