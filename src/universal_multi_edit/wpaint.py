import bpy, bmesh
from .session import UME_Session

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
        session.set("wpaint_meta", {})

        self._init_offsets()

        for obj in objects:
            self._store_object_offsets(obj, session)

            session["wpaint_meta"][obj.name] = {"active_group": active_group(obj)}
            vmap = {}
            src = bmesh.new()
            src.from_mesh(obj.data)
            src.transform(obj.matrix_world)
            for v in src.verts:
                nv = bm.verts.new(v.co)
                vmap[v] = nv
            bm.verts.ensure_lookup_table()
            for f in src.faces:
                try:
                    bm.faces.new([vmap[v] for v in f.verts])
                except:
                    pass
            src.free()

            self._apply_offsets(obj)

        bm.to_mesh(me)
        bm.free()

        proxy = bpy.data.objects.new("UME_Proxy", me)
        context.scene.collection.objects.link(proxy)

        proxy.vertex_groups.new(name=NAME)

        self._transfer(context, session, proxy, transfer_back=False)

        return proxy

    def transfer_back(self, context, session) -> None:
        proxy = session.proxy
        if not proxy:
            return

        self._transfer(context, session, proxy, transfer_back=True)

    def _transfer(self, context, session: UME_Session, proxy: bpy.types.Object, transfer_back: bool = True) -> None:
        for topo in self._iter_topology_objects(session):
            obj = topo["object"]

            if not obj:
                continue

            meta = session["wpaint_meta"].get(obj.name)

            if not meta:
                continue

            active_name = meta["active_group"]

            if transfer_back:
                src = proxy.vertex_groups.get(NAME)
                dst = obj.vertex_groups.get(active_name)
            else:
                src = obj.vertex_groups.get(active_name)
                dst = proxy.vertex_groups.get(NAME)

            if not dst:
                dst = obj.vertex_groups.new(name=active_name)

            self._transfer_vertex_weights(src, dst, topo, transfer_back=transfer_back)

            if transfer_back:
                obj.data.update()
            else:
                proxy.data.update()
