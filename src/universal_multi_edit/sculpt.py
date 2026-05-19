import bpy
import bmesh

from .edit_mode import UME_EditMode
from .protocol import UME_P_Session
from .utils import get_proxy_mesh, get_multires, has_shape_keys, apply_shape_key_delta


class Mode(UME_EditMode):
    name: str = "SCULPT"

    def create_proxy(self, context, objects: list, session: UME_P_Session) -> bpy.types.Object:
        mesh = bpy.data.meshes.new("UME_ProxyMesh")
        bm = bmesh.new()

        mapping = []
        instances = {}
        multires_cache = {}

        processed = set()

        self._init_offsets()

        for obj in objects:
            mesh_id = obj.data.name_full

            if mesh_id in processed:
                instances[mesh_id]["users"].append(obj.name)
                continue

            processed.add(mesh_id)

            src_obj, is_multires, level = self._get_evaluated_object(context, obj)
            src_mesh = src_obj.data
            if is_multires:
                src_obj = bpy.data.objects.new(f"{obj.name}_orig_eval", object_data=src_mesh)
                self._store_object_offsets(src_obj, session)
                session.topology["objects"][-1]["object"] = obj
            else:
                self._store_object_offsets(src_obj, session)
            # else:
            #     src_obj = obj
            #     self._store_object_offsets(src_obj, session)

            instances[mesh_id] = {
                "source": obj.name,
                "users": [obj.name],
                "multires": is_multires,
                "level": level,
                "vert_count": len(src_mesh.vertices),
            }

            # store original evaluated coords for no-change detection
            if is_multires:
                multires_cache[mesh_id] = [v.co.copy() for v in src_mesh.vertices]

            src = bmesh.new()
            src.from_mesh(src_mesh)
            src.verts.ensure_lookup_table()
            src.faces.ensure_lookup_table()

            src.transform(obj.matrix_world)

            vmap = {}

            for i, v in enumerate(src.verts):
                nv = bm.verts.new(v.co)
                vmap[v] = nv
                mapping.append((mesh_id, i))

            bm.verts.ensure_lookup_table()

            for e in src.edges:
                try:
                    bm.edges.new((vmap[e.verts[0]], vmap[e.verts[1]]))
                except:
                    pass

            for f in src.faces:
                try:
                    bm.faces.new([vmap[v] for v in f.verts])
                except:
                    pass

            src.free()
            self._apply_offsets(src_obj)
            bpy.data.meshes.remove(src_mesh)

        bm.normal_update()
        bm.to_mesh(mesh)
        bm.free()

        proxy = bpy.data.objects.new("UME_Proxy", mesh)
        context.scene.collection.objects.link(proxy)

        session.set("proxy_name", proxy.name)
        session.set("mapping", mapping)
        session.set("instances", instances)
        session.set("multires_cache", multires_cache)

        return proxy

    def apply_multires_back(self, context, obj, coords, mesh_id, session: UME_P_Session):
        original = session.get("multires_cache").get(mesh_id, [])

        # no-change detection
        if len(original) == len(coords):
            changed = False
            for a, b in zip(original, coords):
                if (a - b).length > 0.00001:
                    changed = True
                    break
            if not changed:
                return

        # Build clean reshape source from evaluated topology
        src_mesh, _, _ = get_proxy_mesh(context, obj)

        if len(src_mesh.vertices) != len(coords):
            bpy.data.meshes.remove(src_mesh)
            print("UME: multires vertex mismatch")
            return

        for i, v in enumerate(src_mesh.vertices):
            v.co = coords[i]

        src_obj = bpy.data.objects.new("UME_ReshapeSource", src_mesh)
        context.scene.collection.objects.link(src_obj)

        bpy.ops.object.select_all(action="DESELECT")

        obj.select_set(True)
        src_obj.select_set(True)

        context.view_layer.objects.active = obj

        mr = get_multires(obj)

        try:
            bpy.ops.object.multires_reshape(modifier=mr.name)
        except Exception as e:
            print("UME reshape failed:", e)

        bpy.data.objects.remove(src_obj, do_unlink=True)

    def transfer_back(self, context, session) -> None:
        proxy = bpy.data.objects.get(session.get("proxy_name"))
        if not proxy:
            return

        self._transfer(context, session, proxy, transfer_back=True)

    def _transfer(
        self,
        context,
        session: UME_P_Session,
        proxy: bpy.types.Object,
        transfer_back: bool = True,
    ) -> None:

        for topo in self._iter_topology_objects(session):
            obj = topo["object"]

            if not obj:
                continue

            multires = self._get_multires(obj)

            if multires:
                self._transfer_multires(
                    context,
                    proxy,
                    obj,
                    topo,
                    multires,
                    transfer_back,
                )

            else:
                self._transfer_vertex_positions(
                    proxy,
                    obj,
                    topo,
                    transfer_back,
                )

            obj.data.update()

        bpy.data.meshes.remove(proxy.data)

    def _transfer_bak(
        self, context, session: UME_P_Session, proxy: bpy.types.Object, transfer_back: bool = True
    ) -> None:
        proxy_verts = proxy.data.vertices
        mapping = session.get("mapping")
        instances = session.get("instances")

        grouped = {}

        for pidx, (mesh_id, vidx) in enumerate(mapping):
            grouped.setdefault(mesh_id, []).append((pidx, vidx))

        for mesh_id, items in grouped.items():
            data = instances[mesh_id]
            obj = bpy.data.objects.get(data["source"])

            if not obj:
                continue

            inv = obj.matrix_world.inverted()

            # ------------------------------------
            # MULTIRES
            # ------------------------------------
            if data["multires"]:
                coords = []

                for proxy_idx, src_idx in items:
                    world = proxy_verts[proxy_idx].co.copy()
                    local = inv @ world
                    coords.append(local)

                self.apply_multires_back(context, obj, coords, mesh_id, session)
                continue

            # ------------------------------------
            # NORMAL
            # ------------------------------------
            old_pos = {}
            new_pos = {}

            for proxy_idx, src_idx in items:
                world = proxy_verts[proxy_idx].co.copy()
                local = inv @ world

                old_pos[src_idx] = obj.data.vertices[src_idx].co.copy()
                new_pos[src_idx] = local

            deltas = {}

            for idx in old_pos:
                deltas[idx] = new_pos[idx] - old_pos[idx]

            if has_shape_keys(obj):
                apply_shape_key_delta(obj, deltas)
            else:
                for idx, co in new_pos.items():
                    obj.data.vertices[idx].co = co

            obj.data.update()
