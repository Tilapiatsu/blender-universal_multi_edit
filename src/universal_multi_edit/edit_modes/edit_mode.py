from typing import Tuple
import bpy

from ..protocol import UME_P_Session, UME_P_EditMode
from ..safe_object import UME_SafeObject
from ..utils import get_multires, select_all


class UME_EditMode(UME_P_EditMode):
    name: str
    vert_offset: int
    face_offset: int
    loop_offset: int

    def create_proxy(self, context, objects: list[UME_SafeObject], session: UME_P_Session) -> UME_SafeObject: ...

    def transfer_back(self, context, session: UME_P_Session) -> None: ...

    def _transfer(self, context, session: UME_P_Session, proxy: UME_SafeObject, transfer_back: bool = True) -> None: ...

    def _init_offsets(self) -> None:
        self.vert_offset = 0
        self.face_offset = 0
        self.loop_offset = 0

    def _store_object_offsets(self, obj: UME_SafeObject, session) -> None:
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

    def _apply_offsets(self, obj: UME_SafeObject) -> None:
        if not obj.object:
            return
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
        self,
        src_obj: UME_SafeObject,
        dst_obj: UME_SafeObject,
        topo: dict,
        transfer_back: bool = True,
    ):
        if not src_obj.object or not dst_obj.object:
            return

        src_verts = src_obj.data.vertices
        dst_verts = dst_obj.data.vertices

        src_matrix = src_obj.matrix_world
        dst_inv = dst_obj.matrix_world.inverted()

        for proxy_index, local_index in self._iter_vertex_range(topo):
            src_index = proxy_index if transfer_back else local_index
            dst_index = local_index if transfer_back else proxy_index

            # always convert through world space
            world = src_matrix @ src_verts[src_index].co
            local = dst_inv @ world

            dst_verts[dst_index].co = local

    def _set_vertex_positions(self, src_pos: list, dst_obj: UME_SafeObject, topo: dict, transfer_back: bool = True):
        if not dst_obj.object:
            return

        dst_verts = dst_obj.data.vertices

        for proxy_index, local_index in self._iter_vertex_range(topo):
            dst_verts[local_index if transfer_back else proxy_index].co = src_pos[
                proxy_index if transfer_back else local_index
            ]

    def _extract_local_positions_from_proxy(
        self,
        proxy: UME_SafeObject,
        dst_obj: UME_SafeObject,
        topo: dict,
    ):
        positions = []

        if not proxy.object or not dst_obj.object:
            return positions
        else:
            proxy = proxy.object
            dst_obj = dst_obj.object

        proxy_matrix = proxy.matrix_world
        dst_inv = dst_obj.matrix_world.inverted()

        for proxy_index, _local_index in self._iter_vertex_range(topo):
            world = proxy_matrix @ proxy.data.vertices[proxy_index].co
            local = dst_inv @ world
            positions.append(local.copy())

        return positions

    # ---------------------------------------------------------
    # TRANSFER FLOAT COLORS
    # ---------------------------------------------------------

    def _transfer_float_colors(self, src_attr, dst_attr, topo: dict, transfer_back: bool = True):
        if transfer_back:
            local_size = len(dst_attr.data)
            proxy_size = len(src_attr.data)
        else:
            local_size = len(src_attr.data)
            proxy_size = len(dst_attr.data)
        for proxy_loop, local_loop in self._iter_loop_range(topo):
            if proxy_loop >= proxy_size or local_loop >= local_size:
                break
            dst_attr.data[local_loop if transfer_back else proxy_loop].color = src_attr.data[
                proxy_loop if transfer_back else local_loop
            ].color

    # ---------------------------------------------------------
    # TRANSFER BYTE COLORS
    # ---------------------------------------------------------

    def _transfer_byte_colors(self, src_attr, dst_attr, topo: dict, transfer_back: bool = True):
        if transfer_back:
            local_size = len(dst_attr.data)
            proxy_size = len(src_attr.data)
        else:
            local_size = len(src_attr.data)
            proxy_size = len(dst_attr.data)

        for proxy_loop, local_loop in self._iter_loop_range(topo):
            if proxy_loop >= proxy_size or local_loop >= local_size:
                break
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

    def _transfer_shape_keys(self, proxy: UME_SafeObject, obj: UME_SafeObject, topo, transfer_back: bool = True):
        if not proxy.object or not obj.object:
            return

        if transfer_back:
            keys = obj.data.shape_keys
        else:
            keys = proxy.data.shape_keys

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
                dst = proxy.data.vertices[proxy_vert].co
            else:
                src = proxy.data.vertices[proxy_vert].co
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

        self._transfer_vertex_positions(proxy, obj, topo, transfer_back)

    def _transfer_multires(
        self,
        ctx,
        proxy: UME_SafeObject,
        dst_obj: UME_SafeObject,
        topo,
        multires,
        transfer_back: bool = True,
    ):
        if not transfer_back:
            return

        if not proxy.object or not dst_obj.object:
            return

        # ----------------------------------------
        # Extract proxy coords in LOCAL SPACE
        # ----------------------------------------

        coords = self._extract_local_positions_from_proxy(
            proxy,
            dst_obj,
            topo,
        )

        # ----------------------------------------
        # Build evaluated topology mesh
        # ----------------------------------------

        src_mesh, _, _ = self._get_evaluated_object(ctx, dst_obj)

        if not src_mesh:
            return

        reshape_obj = src_mesh

        try:
            if len(reshape_obj.data.vertices) != len(coords):
                print("UME: multires vertex mismatch")
                return

            # ----------------------------------------
            # write coords
            # ----------------------------------------

            for i, co in enumerate(coords):
                reshape_obj.data.vertices[i].co = co

            reshape_obj.data.update()

            # ----------------------------------------
            # multires reshape
            # ----------------------------------------

            ctx.scene.collection.objects.link(reshape_obj.object)

            select_all(False)

            reshape_obj.select_set(True)
            dst_obj.select_set(True)

            if dst_obj.object:
                ctx.view_layer.objects.active = dst_obj.object

            bpy.ops.object.multires_reshape(modifier=multires.name)

        except Exception as e:
            print("UME multires reshape failed:", e)

        finally:
            select_all(False)

            if reshape_obj.object and reshape_obj.name in bpy.data.objects:
                bpy.data.objects.remove(reshape_obj.object, do_unlink=True)

    def _get_multires(self, obj: UME_SafeObject):
        for mod in obj.modifiers:
            if mod.type == "MULTIRES":
                return mod
        return None

    def _get_evaluated_object(self, context, obj: UME_SafeObject) -> Tuple[UME_SafeObject, bool, int]:
        mr = get_multires(obj)

        if mr is None:
            return obj, False, 0

        old_view = mr.levels
        old_render = mr.render_levels

        level = mr.sculpt_levels

        mr.levels = level
        mr.render_levels = level

        dg = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(dg)

        me = bpy.data.meshes.new_from_object(eval_obj)

        obj_eval = bpy.data.objects.new(
            name=f"{obj.name}_eval",
            object_data=me,
        )

        obj_eval.matrix_world = obj.matrix_world.copy()

        mr.levels = old_view
        mr.render_levels = old_render

        return UME_SafeObject(obj_eval), True, level

    def _has_shape_keys(self, obj: bpy.types.Mesh) -> bool:
        return obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 0
