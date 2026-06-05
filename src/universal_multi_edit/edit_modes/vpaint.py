import bpy, bmesh
from ..safe_object import (
    UME_SafeObject,
)

from ..protocol import UME_P_Session
from .edit_mode import UME_EditMode


def float_to_byte(c):

    def q(x):
        s = x
        return int(s * 255.0 + 0.5) / 255.0

    return (q(c[0]), q(c[1]), q(c[2]), max(0.0, min(1.0, c[3])))


def srgb_to_linear(x):
    x = max(0.0, min(1.0, float(x)))
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4


def linear_to_srgb(x):
    x = max(0.0, min(1.0, float(x)))
    if x <= 0.0031308:
        return x * 12.92
    return 1.055 * (x ** (1.0 / 2.4)) - 0.055


class Mode(UME_EditMode):
    name: str = "VERTEX_PAINT"

    def create_proxy(self, context, objects: list[UME_SafeObject], session: UME_P_Session) -> UME_SafeObject:
        if not session:
            return
        me = bpy.data.meshes.new("UME_VPaint")
        bm = bmesh.new()
        session.set("original_vertexcolor", {})

        self._init_offsets()

        for obj in objects:
            if not obj.object:
                continue

            self._store_object_offsets(obj, session)
            self._store_object_color(obj, session, transfer_back=False)

            src = bmesh.new()
            src.from_mesh(obj.data)
            src.transform(obj.matrix_world)
            src.faces.ensure_lookup_table()
            src.verts.ensure_lookup_table()

            vmap = {v: bm.verts.new(v.co) for v in src.verts}
            bm.verts.ensure_lookup_table()
            for f in src.faces:
                try:
                    bm.faces.new([vmap[v] for v in f.verts])
                except:
                    continue

            src.free()

            self._apply_offsets(obj)

        bm.to_mesh(me)
        bm.free()
        proxy = bpy.data.objects.new("UME_Proxy", me)
        context.scene.collection.objects.link(proxy)

        session.proxy = proxy
        self._transfer(context, session, session.proxy, transfer_back=False)

        return session.proxy

    def transfer_back(self, context, session: UME_P_Session) -> None:
        proxy = session.proxy
        if not proxy or not proxy.object:
            return

        self._transfer(context, session, proxy, transfer_back=True)

    def _transfer(self, context, session: UME_P_Session, proxy: UME_SafeObject, transfer_back: bool = True) -> None:
        if not proxy.object:
            return

        for topo in self._iter_topology_objects(session):
            obj = topo["object"]

            if not obj or not obj.object:
                continue

            if transfer_back:
                src = proxy
                dst = obj
            else:
                src = obj
                dst = proxy

            if transfer_back:
                self._store_object_color(src, session, transfer_back=transfer_back)

            original_color = session["original_vertexcolor"].get(src.name)

            if not original_color and not transfer_back:
                continue

            for c_name in original_color["colors"].keys():
                attr_type = original_color["colors"][c_name]["type"]
                attr_domain = original_color["colors"][c_name]["domain"]
                src_attr_name = c_name
                dst_attr_name = original_color["colors"][c_name]["name"] if transfer_back else f"{c_name}_{attr_type}"
                src_color = src.data.color_attributes.get(src_attr_name)
                dst_color = dst.data.color_attributes.get(dst_attr_name)

                print(src.name, dst.name, "src=" + src_attr_name, "dst=" + dst_attr_name, attr_type, attr_domain)

                if src_color is None:
                    print(f"not {src_attr_name}")
                    self._remove_vertex_color(dst, c_name)
                    continue

                if not transfer_back:
                    if not dst_color:
                        dst_color = self._create_vertex_color(dst, dst_attr_name, attr_type, attr_domain)
                    self._transfer_vertex_colors(src_color, dst_color, topo, attr_type, transfer_back=transfer_back)

                else:
                    # if self._is_vertex_color_modified(
                    #     session, topo, dst, src, dst_attr_name, attr_type, attr_domain, transfer_back=transfer_back
                    # ):
                    if True:
                        if dst_color is None:
                            dst_color = self._create_vertex_color(dst, dst_attr_name, attr_type, attr_domain)
                        self._transfer_vertex_colors(src_color, dst_color, topo, attr_type, transfer_back=transfer_back)

                dst.object.data.update()

            for w in dst.vertex_groups:
                if w.name not in src.vertex_groups:
                    self._remove_vertex_group(dst, w.name)

            if original_color["active"] and original_color["active"] in dst.data.color_attributes:
                dst.data.color_attributes.active = dst.data.color_attributes.get(original_color["active"])
                dst.data.update()
