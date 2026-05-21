import bpy, bmesh
from .safe_object import UME_SafeObject
from .session import UME_Session

from .edit_mode import UME_EditMode

NAME = "__UME_WEIGHT__"


def active_group(obj: UME_SafeObject):
    vg = obj.object.vertex_groups.active
    return vg.name if vg else obj.object.vertex_groups.new(name=NAME).name


class Mode(UME_EditMode):
    name: str = "WEIGHT_PAINT"

    def create_proxy(self, context, objects: list[UME_SafeObject], session) -> bpy.types.Object:
        me = bpy.data.meshes.new("UME_WPaint")
        bm = bmesh.new()
        session.set("wpaint_meta", {})

        self._init_offsets()

        for obj in objects:
            if not obj.object:
                return

            self._store_object_offsets(obj, session)

            session["wpaint_meta"][obj.name] = {"active_group": active_group(obj)}
            vmap = {}
            src = bmesh.new()
            src.from_mesh(obj.object.data)
            src.transform(obj.object.matrix_world)
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

        session.proxy = proxy
        proxy.vertex_groups.new(name=NAME)

        self._transfer(context, session, session.proxy, transfer_back=False)

        return session.proxy

    def transfer_back(self, context, session) -> None:
        proxy = session.proxy

        if not proxy:
            return
        if not proxy.object:
            return

        self._transfer(context, session, proxy, transfer_back=True)

    def _transfer(self, context, session: UME_Session, proxy: UME_SafeObject, transfer_back: bool = True) -> None:
        for topo in self._iter_topology_objects(session):
            obj = topo["object"]
            if not proxy.object:
                return

            if not obj or not obj.object:
                continue

            meta = session["wpaint_meta"].get(obj.name)

            if not meta:
                continue

            active_name = meta["active_group"]

            if transfer_back:
                src = proxy.object.vertex_groups.get(NAME)
                dst = obj.object.vertex_groups.get(active_name)
            else:
                src = obj.object.vertex_groups.get(active_name)
                dst = proxy.object.vertex_groups.get(NAME)

            if not dst:
                dst = obj.object.vertex_groups.new(name=active_name)

            self._transfer_vertex_weights(src, dst, topo, transfer_back=transfer_back)

            if transfer_back:
                obj.object.data.update()
            else:
                proxy.object.data.update()
