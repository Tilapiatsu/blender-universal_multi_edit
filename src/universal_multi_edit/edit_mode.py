import bpy
from typing import Protocol

from .protocol import UME_P_Session, UME_P_EditMode


class UME_EditMode(UME_P_EditMode):
    name: str
    vert_offset: int
    face_offset: int
    loop_offset: int

    def create_proxy(self, context, objects, session: UME_P_Session) -> bpy.types.Object: ...

    def transfer_back(self, context, session: UME_P_Session) -> None: ...

    def _transfer(
        self, context, session: UME_P_Session, proxy: bpy.types.Object, transfer_back: bool = True
    ) -> None: ...

    def _init_offsets(self) -> None:
        self.vert_offset = 0
        self.face_offset = 0
        self.loop_offset = 0

    def _store_object_offsets(self, obj: bpy.types.Object, session) -> None:
        obj_topology = {
            "object": obj,
            "vert_start": self.vert_offset,
            "vert_count": len(obj.data.vertices),
            "face_start": self.face_offset,
            "face_count": len(obj.data.polygons),
            "loop_start": self.loop_offset,
            "loop_count": len(obj.data.loops),
        }

        session.topology["objects"].append(obj_topology)

    def _apply_offsets(self, obj) -> None:
        self.vert_offset += len(obj.data.vertices)
        self.face_offset += len(obj.data.polygons)
        self.loop_offset += len(obj.data.loops)

    # ---------------------------------------------------------
    # TOPOLOGY ITERATION
    # ---------------------------------------------------------

    def _iter_topology_objects(self, session: UME_P_Session):
        for topo in session.topology["objects"]:
            yield topo

    # ---------------------------------------------------------
    # VERTEX RANGES
    # ---------------------------------------------------------

    def _iter_vertex_range(self, topo: dict):
        start = topo["vert_start"]
        count = topo["vert_count"]

        for local_index in range(count):
            proxy_index = start + local_index

            yield proxy_index, local_index

    # ---------------------------------------------------------
    # FACE RANGES
    # ---------------------------------------------------------

    def _iter_face_range(self, topo: dict):
        start = topo["face_start"]
        count = topo["face_count"]

        for local_index in range(count):
            proxy_index = start + local_index

            yield proxy_index, local_index

    # ---------------------------------------------------------
    # LOOP RANGES
    # ---------------------------------------------------------

    def _iter_loop_range(self, topo: dict):
        start = topo["loop_start"]
        count = topo["loop_count"]

        for local_index in range(count):
            proxy_index = start + local_index

            yield proxy_index, local_index

    # ---------------------------------------------------------
    # TRANSFER VERTEX POSITIONS
    # ---------------------------------------------------------

    def _transfer_vertex_positions(
        self, proxy_me: bpy.types.Mesh, dst_me: bpy.types.Mesh, topo: dict, transfer_back: bool = True
    ):
        proxy_verts = proxy_me.vertices
        dst_verts = dst_me.vertices

        for proxy_index, local_index in self._iter_vertex_range(topo):
            dst_verts[local_index if transfer_back else proxy_index].co = proxy_verts[
                proxy_index if transfer_back else local_index
            ].co

    # ---------------------------------------------------------
    # TRANSFER FLOAT COLORS
    # ---------------------------------------------------------

    def _transfer_float_colors(self, src_attr, dst_attr, topo: dict, transfer_back: bool = True):
        for proxy_loop, local_loop in self._iter_loop_range(topo):
            dst_attr.data[local_loop if transfer_back else proxy_loop].color = src_attr.data[
                proxy_loop if transfer_back else local_loop
            ].color

    # ---------------------------------------------------------
    # TRANSFER BYTE COLORS
    # ---------------------------------------------------------

    def _transfer_byte_colors(self, src_attr, dst_attr, topo: dict, transfer_back: bool = True):
        for proxy_loop, local_loop in self._iter_loop_range(topo):
            dst_attr.data[local_loop if transfer_back else proxy_loop].color_srgb = src_attr.data[
                proxy_loop if transfer_back else local_loop
            ].color_srgb

    # ---------------------------------------------------------
    # TRANSFER VERTEX WEIGHTS
    # ---------------------------------------------------------

    def _transfer_vertex_weights(self, proxy_group, dst_group, topo: dict, transfer_back: bool = True):
        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            try:
                weight = proxy_group.weight(proxy_vert if transfer_back else local_vert)

            except:
                continue

            dst_group.add([local_vert if transfer_back else proxy_vert], weight, "REPLACE")

    def _transfer_uvs(self, src_uv, dst_uv, topo: dict, transfer_back: bool = True):
        for proxy_loop, local_loop in self._iter_loop_range(topo):
            dst_uv.data[local_loop if transfer_back else proxy_loop].uv = src_uv.data[
                proxy_loop if transfer_back else local_loop
            ].uv

    def _transfer_normals(self, proxy_me, dst_me, topo: dict, transfer_back: bool = True):
        proxy_me.calc_normals_split()
        normals = []
        for proxy_loop, local_loop in self._iter_loop_range(topo):
            normals.append(proxy_me.loops[proxy_loop if transfer_back else local_loop].normal)

        dst_me.normals_split_custom_set(normals)

    def _transfer_masks(self, src_attr, dst_attr, topo: dict, transfer_back: bool = True):

        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            dst_attr.data[local_vert if transfer_back else proxy_vert].value = src_attr.data[
                proxy_vert if transfer_back else local_vert
            ].value

    def _transfer_shape_keys(self, proxy_me, obj, topo, transfer_back: bool = True):
        if transfer_back:
            keys = obj.data.shape_keys
        else:
            keys = proxy_me.shape_keys

        if not keys:
            return

        basis = keys.reference_key

        if not basis:
            return

        # -----------------------------------------------------
        # compute sculpt delta
        # -----------------------------------------------------

        deltas = []

        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            if transfer_back:
                src = obj.data.vertices[local_vert].co
                dst = proxy_me.vertices[proxy_vert].co
            else:
                src = proxy_me.data.vertices[proxy_vert].co
                dst = obj.data.vertices[local_vert].co

            deltas.append(dst - src)

        # -----------------------------------------------------
        # apply to relative keys
        # -----------------------------------------------------

        for key in keys.key_blocks:
            if key == basis:
                continue

            # absolute shape keys:
            # skip entirely
            if not key.relative_key:
                continue

            for i, delta in enumerate(deltas):
                key.data[i].co += delta

        # -----------------------------------------------------
        # update basis
        # -----------------------------------------------------

        self._transfer_vertex_positions(proxy_me, obj.data, topo, transfer_back)

    def _transfer_multires(self, ctx, proxy_me, obj, topo, multires, transfer_back: bool = True):
        depsgraph = ctx.evaluated_depsgraph_get()
        if transfer_back:
            eval_obj = obj.evaluated_get(depsgraph)
        else:
            eval_obj = proxy_me.evaluated_get(depsgraph)

        eval_me = eval_obj.to_mesh()

        try:
            # -----------------------------------------
            # copy proxy coords into evaluated mesh
            # -----------------------------------------

            for proxy_vert, local_vert in self._iter_vertex_range(topo):
                if transfer_back:
                    eval_me.vertices[local_vert].co = proxy_me.vertices[proxy_vert].co
                else:
                    eval_me.vertices[proxy_vert].co = obj.data.vertices[local_vert].co

            # -----------------------------------------
            # reshape multires
            # -----------------------------------------

            temp = bpy.data.objects.new("UME_TEMP", eval_me)
            ctx.scene.collection.objects.link(temp)
            ctx.view_layer.update()
            bpy.ops.object.select_all(action="DESELECT")
            temp.select_set(True)
            ctx.view_layer.objects.active = temp
            bpy.ops.object.multires_reshape(modifier=multires.name)
            bpy.data.objects.remove(temp, do_unlink=True)

        finally:
            eval_obj.to_mesh_clear()
