import bpy, bmesh

from .edit_mode import UME_EditMode

NAME = "__UME_WEIGHT__"


def active_group(obj):
    vg = obj.vertex_groups.active
    return vg.name if vg else obj.vertex_groups.new(name=NAME).name


class Mode(UME_EditMode):
    name: str = "WEIGHT_PAINT"

    def create_proxy(self, context, objects, session) -> bpy.types.Object:
        me = bpy.data.meshes.new("UME_WPaint")
        bm = bmesh.new()
        group = {}
        session.set("vert_map", [])
        for obj in objects:
            group[obj.name] = active_group(obj)
            session.set("group", group)
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
        context.scene.collection.objects.link(obj)

        obj.vertex_groups.new(name=NAME)

        vg = obj.vertex_groups.active
        for i, (oname, vi) in enumerate(session["vert_map"]):
            src_obj = bpy.data.objects.get(oname)
            if not src_obj or not group[src_obj.name]:
                continue
            g = src_obj.vertex_groups.get(group[src_obj.name])
            w = 0.0
            if g:
                try:
                    w = g.weight(vi)
                except:
                    pass
            vg.add([i], w, "REPLACE")
        return obj

    def transfer_back(self, context, session) -> None:
        p = session.proxy
        if not p:
            return
        group = session.get("group")
        for i, (oname, vi) in enumerate(session["vert_map"]):
            o = bpy.data.objects.get(oname)
            if not o:
                continue
            vg = group[oname]
            dst = o.vertex_groups.get(vg) or o.vertex_groups.new(name=vg)
            try:
                w = p.vertex_groups.get(NAME).weight(i)
            except:
                w = 0.0
            dst.add([vi], w, "REPLACE")
