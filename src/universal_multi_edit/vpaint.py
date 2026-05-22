import bpy, bmesh
from .safe_object import (
    UME_SafeObject,
)

from .protocol import UME_P_Session
from .edit_mode import UME_EditMode

NAME = "__UME_COLOR__"


def byte_to_float(c):
    return (
        float(c[0]),
        float(c[1]),
        float(c[2]),
        float(c[3]),
    )


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


def _attr_type(attr):
    # Blender version compatibility
    return getattr(attr, "data_type", getattr(attr, "type", "FLOAT_COLOR"))


def _ensure_proxy_attr(me: bpy.types.Mesh) -> bpy.types.AttributeGroupMesh:
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    return me.color_attributes.new(name=NAME, domain="CORNER", type="FLOAT_COLOR")


class Mode(UME_EditMode):
    name: str = "VERTEX_PAINT"

    def create_proxy(self, context, objects: list[UME_SafeObject], session: UME_P_Session) -> UME_SafeObject:
        if not session:
            return
        me = bpy.data.meshes.new("UME_VPaint")
        bm = bmesh.new()
        session.set("map", [])
        session.set("attr_meta", {})

        self._init_offsets()

        for obj in objects:
            if not obj.object:
                continue
            self._store_object_offsets(obj, session)
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
                    bm.faces.new([vmap[v] for v in f.verts])
                except:
                    continue
                for ls in f.loops:
                    # support POINT and CORNER domains
                    if attr:
                        src_idx = ls.vert.index if attr.domain == "POINT" else ls.index
                        if src_idx < len(attr.data):
                            raw = attr.data[src_idx].color[:]
                            if session["attr_meta"][obj.name]["type"] == "BYTE_COLOR":
                                col = byte_to_float(raw)
                            else:
                                col = raw
                        else:
                            col = (0, 0, 0, 0)
                    else:
                        col = (0, 0, 0, 0)

                    session["map"].append((obj.name, attr.domain if attr else "CORNER", ls.vert.index, ls.index, col))

            src.free()

            self._apply_offsets(obj)

        bm.to_mesh(me)
        bm.free()
        proxy = bpy.data.objects.new("UME_Proxy", me)
        context.scene.collection.objects.link(proxy)
        _ensure_proxy_attr(me)

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

        src = proxy.object.data.color_attributes.get(NAME)

        if not src:
            return

        for topo in self._iter_topology_objects(session):
            obj = topo["object"]

            if not obj:
                continue

            me = obj.data
            meta = session["attr_meta"].get(obj.name)

            if not meta:
                continue

            attr_name = meta["name"]
            attr_type = meta["type"]
            domain = meta["domain"]

            # -------------------------------------------------
            # recover/create destination attr
            # -------------------------------------------------

            if transfer_back:
                src = proxy.object.data.color_attributes.get(NAME)
                dst = me.color_attributes.get(attr_name)
            else:
                src = me.color_attributes.get(attr_name)
                dst = proxy.object.data.color_attributes.get(NAME)

            if not dst:
                dst = me.color_attributes.new(name=attr_name, type=attr_type, domain=domain)

            # -------------------------------------------------
            # transfer
            # -------------------------------------------------

            if attr_type == "BYTE_COLOR":
                self._transfer_byte_colors(src, dst, topo, transfer_back=transfer_back)

            else:
                self._transfer_float_colors(src, dst, topo, transfer_back=transfer_back)

            # -------------------------------------------------
            # restore active attr
            # -------------------------------------------------

            if transfer_back:
                me.color_attributes.active_color = dst
                me.update()
            else:
                proxy.data.color_attributes.active_color = dst
                proxy.data.update()
