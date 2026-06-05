from __future__ import annotations
import bpy
from typing import Union, Tuple, overload, TypeAlias
from mathutils import Vector

from ..protocol import UME_P_Session, UME_P_EditMode
from ..safe_object import UME_SafeObject
from ..utils import get_multires, select_all

ColorTuple: TypeAlias = tuple[float, float, float, float]


class UME_Color:
    def __init__(self, color: ColorTuple) -> None:
        self.color = color

    def __getitem__(self, index):
        if index > len(self.color) or index < 0:
            raise IndexError
        return self.color[index]

    @overload
    def __eq__(self, color: UME_Color) -> bool: ...

    @overload
    def __eq__(self, color: ColorTuple) -> bool: ...

    def __eq__(self, color: object) -> bool:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented

        return (
            self.color[0] == color[0]
            and self.color[1] == color[1]
            and self.color[2] == color[2]
            and self.color[3] == color[3]
        )

    @overload
    def __gt__(self, color: UME_Color) -> bool: ...

    @overload
    def __gt__(self, color: ColorTuple) -> bool: ...

    def __gt__(self, color: object) -> bool:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented

        return (
            self.color[0] > color[0] or self.color[1] > color[1] or self.color[2] > color[2] or self.color[3] > color[3]
        )

    @overload
    def __lt__(self, color: UME_Color) -> bool: ...

    @overload
    def __lt__(self, color: ColorTuple) -> bool: ...

    def __lt__(self, color: object) -> bool:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented

        return (
            self.color[0] < color[0] or self.color[1] < color[1] or self.color[2] < color[2] or self.color[3] < color[3]
        )

    @overload
    def __ge__(self, color: UME_Color) -> bool: ...

    @overload
    def __ge__(self, color: ColorTuple) -> bool: ...

    def __ge__(self, color: object) -> bool:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented

        return (
            self.color[0] >= color[0]
            or self.color[1] >= color[1]
            or self.color[2] >= color[2]
            or self.color[3] >= color[3]
        )

    @overload
    def __le__(self, color: UME_Color) -> bool: ...

    @overload
    def __le__(self, color: ColorTuple) -> bool: ...

    def __le__(self, color: object) -> bool:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented

        return (
            self.color[0] <= color[0]
            or self.color[1] <= color[1]
            or self.color[2] <= color[2]
            or self.color[3] <= color[3]
        )

    def __repr__(self) -> str:
        return str(self.color)

    @overload
    def max(self, color: UME_Color) -> UME_Color: ...

    @overload
    def max(self, color: ColorTuple) -> UME_Color: ...

    def max(self, color: object) -> UME_Color:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented
        return UME_Color(
            (
                max(self.color[0], color[0]),
                max(self.color[1], color[1]),
                max(self.color[2], color[2]),
                max(self.color[3], color[3]),
            )
        )

    @overload
    def delta(self, color: UME_Color) -> UME_Color: ...

    @overload
    def delta(self, color: ColorTuple) -> UME_Color: ...

    def delta(self, color: object) -> UME_Color:
        if not isinstance(color, (UME_Color, tuple)):
            return NotImplemented
        return UME_Color(
            (
                abs(self.color[0] - color[0]),
                abs(self.color[1] - color[1]),
                abs(self.color[2] - color[2]),
                abs(self.color[3] - color[3]),
            )
        )


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

        old_pos = {}
        new_pos = {}

        for proxy_index, local_index in self._iter_vertex_range(topo):
            src_index = proxy_index if transfer_back else local_index
            dst_index = local_index if transfer_back else proxy_index

            # always convert through world space
            world = src_matrix @ src_verts[src_index].co
            local = dst_inv @ world

            old_pos[dst_index] = dst_verts[dst_index].co
            new_pos[dst_index] = local

            dst_verts[dst_index].co = local

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

    def _transfer_vertex_weights(self, src_group, dst_group, topo: dict, transfer_back: bool = True):
        for src_vert, local_vert in self._iter_vertex_range(topo):
            try:
                weight = src_group.weight(src_vert if transfer_back else local_vert)

            except RuntimeError:
                continue

            dst_group.add([local_vert if transfer_back else src_vert], weight, "REPLACE")

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

    def _transfer_shape_keys(
        self, session: UME_P_Session, proxy: UME_SafeObject, obj: UME_SafeObject, topo, transfer_back: bool = True
    ):
        if not proxy.object or not obj.object:
            return

        if transfer_back:
            src_obj = proxy
            dst_obj = obj
            src_keys = src_obj.data.shape_keys
            dst_keys = dst_obj.data.shape_keys
        else:
            src_obj = obj
            dst_obj = proxy
            src_keys = src_obj.data.shape_keys
            dst_keys = dst_obj.data.shape_keys

        if not src_keys:
            if not transfer_back:
                return
            else:
                self._remove_deleted_shape_key([], dst_obj, dst_keys)
                return

        else:
            basis = src_keys.reference_key

        src_matrix = src_obj.matrix_world
        dst_inv = dst_obj.matrix_world.inverted()

        basis_modified = False

        # -----------------------------------------------------
        # apply to relative keys
        # -----------------------------------------------------
        for key in src_keys.key_blocks:
            is_basis = key == basis

            # absolute shape keys           # skip entirely
            if not key.relative_key:
                continue

            # create shape key if missing
            if not transfer_back and (not dst_keys or key.name not in dst_keys.key_blocks):
                # print(f"Create {key.name} for {dst_obj.name}")
                dst_obj.shape_key_add(name=key.name)
                dst_keys = dst_obj.data.shape_keys

            if not transfer_back:
                # print(f"Store shapekey {key.name} for {src_obj.name}")
                session["original_shapekey"][src_obj.name][key.name] = [
                    src_obj.data.vertices[i].co - key.data[i].co if not is_basis else key.data[i].co
                    for i, _ in enumerate(key.data)
                ]

            if is_basis:
                if not transfer_back:
                    basis_modified = self._is_shape_key_modified(session, topo, dst_obj, src_obj, key.name, is_basis)
                else:
                    basis_modified = self._is_shape_key_modified(session, topo, src_obj, dst_obj, key.name, is_basis)

            if transfer_back:
                shape_key_modified = self._is_shape_key_modified(session, topo, src_obj, dst_obj, key.name, is_basis)

                if is_basis and not dst_obj.data.shape_keys:
                    dst_keys = self._create_shape_key(dst_obj, key.name)

                elif not basis_modified and not shape_key_modified:  # shape keys has not been modified
                    if not is_basis:
                        continue

                elif shape_key_modified and (
                    not dst_obj.data.shape_keys or key.name not in dst_obj.data.shape_keys.key_blocks
                ):
                    dst_keys = self._create_shape_key(dst_obj, key.name)

            if not dst_keys or key.name not in dst_keys.key_blocks:
                continue

            self._set_shape_key_delta(
                topo, transfer_back, key.data, dst_keys.key_blocks[key.name].data, src_matrix, dst_inv
            )
            if is_basis:
                self._set_shape_key_delta(topo, transfer_back, key.data, dst_obj.data.vertices, src_matrix, dst_inv)

        if not dst_keys.key_blocks:
            return

        self._remove_deleted_shape_key(src_keys.key_blocks, dst_obj, dst_keys)

        if len(dst_obj.data.shape_keys.key_blocks) == 1:
            self._remove_deleted_shape_key([], dst_obj, dst_keys)

    def _remove_deleted_shape_key(self, src_key_blocks, dst_obj, dst_keys):
        to_remove = []

        if not dst_keys:
            return

        for key in dst_keys.key_blocks:
            if not len(src_key_blocks):
                to_remove.append(key.name)
                continue

            if src_key_blocks and key.name not in src_key_blocks:
                to_remove.append(key.name)

        if not len(to_remove):
            return

        for key in reversed(to_remove):
            for k in dst_obj.data.shape_keys.key_blocks:
                if k.name == key:
                    dst_obj.object.shape_key_remove(k)

        dst_obj.data.update()

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
                if not mod.sculpt_levels:
                    continue
                return mod
        return None

    def _get_evaluated_object(self, context, obj: UME_SafeObject) -> Tuple[UME_SafeObject, bool, int]:
        mr = get_multires(obj)

        if mr is None:
            return obj, False, 0

        old_view = mr.levels
        old_render = mr.render_levels

        level = mr.sculpt_levels

        if level == 0:
            return obj, False, 0

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

    def _has_shape_keys(self, obj: UME_SafeObject) -> bool:
        return obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 0

    def _apply_shape_key_delta(self, obj: bpy.types.Object, deltas: dict):
        keys = obj.data.shape_keys.key_blocks

        if obj.data.shape_keys.use_relative:
            for kb in keys:
                for idx, delta in deltas.items():
                    kb.data[idx].co += delta
        else:
            kb = keys[0]
            for idx, delta in deltas.items():
                kb.data[idx].co += delta

    def _set_shape_key_delta(self, topo, transfer_back: bool, src_verts, dst_verts, src_matrix, dst_inv):
        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            src_index = proxy_vert if transfer_back else local_vert
            dst_index = local_vert if transfer_back else proxy_vert
            src_pos = src_verts[src_index].co

            dst_verts[dst_index].co = self._get_local_pos(src_matrix, src_pos, dst_inv)

    def _get_local_pos(self, src_matrix, src_pos, dst_inv):
        world = src_matrix @ src_pos
        return dst_inv @ world

    def _is_shape_key_modified(
        self,
        session,
        topo,
        dst_obj: bpy.types.Object,
        src_obj: bpy.types.Object,
        key_name: str,
        is_basis: bool,
        threshold=0.0001,
    ):
        if key_name in session["original_shapekey"][src_obj.name].keys():
            old = session["original_shapekey"][src_obj.name][key_name]
        else:
            # print(f"{key_name} does not exist in {src_obj.name}")
            old = [Vector((0, 0, 0)) for _ in range(len(src_obj.data.vertices))]

        new_base = dst_obj.data.vertices

        if not dst_obj.data.shape_keys:
            return True
        if not is_basis and (dst_obj.data.shape_keys and key_name in dst_obj.data.shape_keys.key_blocks):
            new = dst_obj.data.shape_keys.key_blocks[key_name].data
        else:
            # print(f"{key_name} does not exist in {dst_obj.name}")
            new = new_base

        max_delta = 0.0
        # print(f"{key_name} in {dst_obj.name}")

        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            # print("proxy", proxy_vert, new_base[proxy_vert].co - new[proxy_vert].co)
            # print("old  ", local_vert, old[local_vert])
            delta = (new_base[proxy_vert].co - new[proxy_vert].co - old[local_vert]).length

            max_delta = max(max_delta, delta)

            if max_delta > threshold:
                # print(f"{key_name} has changed at index {proxy_vert} | {max_delta}")
                return True

        return False

    def _create_shape_key(self, obj, name):
        obj.shape_key_add(name=name)
        return obj.data.shape_keys

    def _has_vertex_group(self, obj: UME_SafeObject) -> bool:
        return len(obj.vertex_groups) > 0

    def _is_active_vertex_group(self, obj: UME_SafeObject, name: str) -> bool:
        return False if obj.vertex_groups.active is None else obj.vertex_groups.active.name == name

    def _create_vertex_weight(self, obj: UME_SafeObject, name: str) -> bpy.types.VertexGroup:
        # print("create vertex weight", name, "for", obj.name)
        return obj.vertex_groups.new(name=name)

    def _is_vertex_group_modified(
        self,
        session,
        topo,
        dst_obj: bpy.types.Object,
        src_obj: bpy.types.Object,
        group_name: str,
        transfer_back=True,
        threshold=0.0001,
    ):
        if group_name in session["original_vertexweight"][src_obj.name]["weights"].keys():
            original = session["original_vertexweight"][src_obj.name]["weights"][group_name]
        else:
            original = {i: 0.0 for i in range(1)}

        dst_group = dst_obj.vertex_groups.get(group_name)
        dst_group_exist = dst_group is not None
        max_delta = 0.0

        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            src_idx = proxy_vert if transfer_back else local_vert
            dst_idx = local_vert if transfer_back else proxy_vert

            try:
                if dst_group_exist:
                    dst_weight = dst_group.weight(dst_idx)
                else:
                    dst_weight = 0.0
            except RuntimeError:
                dst_weight = 0.0

            if src_idx not in original.keys():
                continue

            original_weight = original[src_idx]

            if not original_weight:
                continue

            delta = abs(dst_weight - original_weight)
            max_delta = max(max_delta, delta)

            if max_delta > threshold:
                return True

        return False

    def _remove_vertex_group(self, obj, name: str):
        if name not in obj.vertex_groups:
            return
        # print(f"removing vertex group{name} in {obj.name}")
        obj.vertex_groups.remove(obj.vertex_groups[name])

    def _store_object_weights(self, obj: UME_SafeObject, session: UME_P_Session):
        for vw in obj.vertex_groups:
            if obj.name not in session["original_vertexweight"]:
                session["original_vertexweight"][obj.name] = {"active": None, "weights": {}}

            if self._is_active_vertex_group(obj, vw.name):
                session["original_vertexweight"][obj.name]["active"] = vw.name

            values = {}
            # if not transfer_back:
            for i in range(len(obj.data.vertices)):
                try:
                    v = {i: vw.weight(i)}
                    values.update(v)
                except RuntimeError:
                    continue

            session["original_vertexweight"][obj.name]["weights"][vw.name] = values

    def _has_vertex_color(self, obj: UME_SafeObject) -> bool:
        return len(obj.data.color_attributes) > 0

    def _create_vertex_color(
        self, obj: UME_SafeObject, name: str, type: str, domain: str
    ) -> bpy.types.AttributeGroupMesh:
        print(f"create color attribute {name} for {obj.name}")
        return obj.data.color_attributes.new(name=name, type=type, domain=domain)

    def _is_vertex_color_modified(
        self,
        session,
        topo,
        dst_obj: bpy.types.Object,
        src_obj: bpy.types.Object,
        color_name: str,
        attr_type,
        attr_domain,
        transfer_back=True,
        threshold=0.0001,
    ):
        if color_name in session["original_vertexcolor"][src_obj.name]["colors"].keys():
            original = session["original_vertexcolor"][src_obj.name]["colors"][color_name]
        else:
            original = {"values": {i: UME_Color((0.0, 0.0, 0.0, 0.0))} for i in range(1)}

        dst_color = dst_obj.data.color_attributes.get(color_name)
        dst_color_exist = dst_color is not None
        max_delta = UME_Color((0.0, 0.0, 0.0, 0.0))
        threshold_color = UME_Color((threshold, threshold, threshold, threshold))

        for proxy_vert, local_vert in self._iter_vertex_range(topo):
            src_idx = proxy_vert if transfer_back else local_vert
            dst_idx = local_vert if transfer_back else proxy_vert

            try:
                if dst_color_exist:
                    dst_value = UME_Color(
                        (
                            dst_color.data[dst_idx].color
                            if attr_type == "FLOAT_COLOR"
                            else dst_color.data[dst_idx].color_srgb
                        )
                    )
                else:
                    dst_value = UME_Color((0.0, 0.0, 0.0, 0.0))
            except RuntimeError:
                dst_value = UME_Color((0.0, 0.0, 0.0, 0.0))

            if src_idx not in original["values"].keys():
                continue

            original_color = original["values"][src_idx]
            print(original_color)

            if not original_color:
                continue

            delta = dst_value.delta(original_color)
            max_delta = max_delta.max(delta)

            print(max_delta)
            if max_delta > threshold_color:
                print("modified")
                return True

        return False

    def _transfer_vertex_colors(
        self, src: UME_SafeObject, dst: UME_SafeObject, topo, attr_type: str, transfer_back: bool = False
    ) -> None:
        if attr_type == "BYTE_COLOR":
            print("transfer byte")
            self._transfer_byte_colors(src, dst, topo, transfer_back=transfer_back)

        else:
            print("transfer float")
            self._transfer_float_colors(src, dst, topo, transfer_back=transfer_back)

    def _store_object_color(self, obj: UME_SafeObject, session: UME_P_Session, transfer_back=False):
        for c in obj.data.color_attributes:
            if c.data_type not in ["FLOAT_COLOR", "BYTE_COLOR"]:
                continue

            if obj.name not in session["original_vertexcolor"]:
                session["original_vertexcolor"][obj.name] = {"active": None, "colors": {}}

            if self._is_active_vertex_color(obj, c.name):
                session["original_vertexcolor"][obj.name]["active"] = c.name

            attr_type = getattr(c, "data_type", "FLOAT_COLOR")
            values = {
                "name": c.name.split(f"_{attr_type}")[0] if transfer_back else f"{c.name}_{attr_type}",
                "domain": c.domain,
                "type": attr_type,
                "values": {},
            }

            for ls in obj.data.loops:
                # support POINT and CORNER domains
                if c:
                    src_idx = ls.vertex_index if c.domain == "POINT" else ls.index
                    if src_idx < len(c.data):
                        raw = c.data[src_idx].color[:]
                        if values["type"] == "BYTE_COLOR":
                            col = self._byte_to_float(raw)
                        else:
                            col = raw
                    else:
                        col = (0, 0, 0, 0)
                else:
                    col = (0, 0, 0, 0)

                values["values"][ls.vertex_index] = col
                # .append((obj.name, c.domain if attr else "CORNER", ls.vert.index, ls.index, col))

            session["original_vertexcolor"][obj.name]["colors"][c.name] = values

    @staticmethod
    def _byte_to_float(c):
        return (
            float(c[0]),
            float(c[1]),
            float(c[2]),
            float(c[3]),
        )

    def _is_active_vertex_color(self, obj: UME_SafeObject, name: str) -> bool:
        return False if obj.data.color_attributes.active is None else obj.data.color_attributes.active.name == name

    def _remove_vertex_color(self, obj: UME_SafeObject, name: str) -> None:
        if name not in obj.data.color_attributes:
            return
        obj.data.color_attributes.remove(obj.data.color_attributes[name])
