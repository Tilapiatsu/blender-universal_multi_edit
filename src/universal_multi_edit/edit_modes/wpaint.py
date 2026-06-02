import bpy, bmesh
from ..safe_object import UME_SafeObject
from ..protocol import UME_P_Session

from .edit_mode import UME_EditMode

NAME = "__UME_WEIGHT__"


def active_group(obj: UME_SafeObject):
    vg = obj.object.vertex_groups.active
    return vg.name if vg else obj.object.vertex_groups.new(name=NAME).name


class Mode(UME_EditMode):
    name: str = "WEIGHT_PAINT"

    def create_proxy(self, context, objects: list[UME_SafeObject], session) -> UME_SafeObject:
        me = bpy.data.meshes.new("UME_WPaint")
        bm = bmesh.new()
        session.set("wpaint_meta", {})
        session.set("original_vertexweight", {})

        self._init_offsets()

        for obj in objects:
            if not obj.object:
                continue

            self._store_object_offsets(obj, session)

            self._store_object_weights(obj, session)

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

        session.proxy = proxy

        self._transfer(context, session, session.proxy, transfer_back=False)

        return session.proxy

    def transfer_back(self, context, session) -> None:
        proxy = session.proxy
        if not proxy or not proxy.object:
            return

        self._transfer(context, session, proxy, transfer_back=True)

    def _transfer(self, context, session: UME_P_Session, proxy: UME_SafeObject, transfer_back: bool = True) -> None:
        for topo in self._iter_topology_objects(session):
            obj = topo["object"]
            if not proxy.object:
                return

            if not obj or not obj.object:
                continue

            if transfer_back:
                src = proxy
                dst = obj
            else:
                src = obj
                dst = proxy

            if transfer_back:
                self._store_object_weights(src, session)

            originial_weight = session["original_vertexweight"].get(src.name)

            if not originial_weight and not transfer_back:
                continue

            for w in originial_weight["weights"]:
                src_weight = src.vertex_groups.get(w["name"])
                dst_weight = dst.vertex_groups.get(w["name"])

                if not src_weight:
                    continue

                if not dst_weight:
                    dst_weight = self._create_vertex_weight(dst, w["name"])

                self._transfer_vertex_weights(src_weight, dst_weight, topo, transfer_back=transfer_back)

                dst.object.data.update()

            dst.vertex_groups.active = dst.vertex_groups.get(originial_weight["active"])

    def _store_object_weights(self, obj: UME_SafeObject, session: UME_P_Session):
        for vw in obj.vertex_groups:
            if obj.name not in session["original_vertexweight"]:
                session["original_vertexweight"][obj.name] = {"active": None, "weights": []}

            if self._is_active_vertex_group(obj, vw.name):
                session["original_vertexweight"][obj.name]["active"] = vw.name

            session["original_vertexweight"][obj.name]["weights"].append({"name": vw.name})
