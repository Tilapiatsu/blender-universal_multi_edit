import bpy
import bmesh

from .utils import get_proxy_mesh, get_multires, has_shape_keys, apply_shape_key_delta


def create_proxy(context, objects, session):

    mesh = bpy.data.meshes.new("MOS_ProxyMesh")
    bm = bmesh.new()

    mapping = []
    instances = {}
    multires_cache = {}

    processed = set()

    for obj in objects:
        mesh_id = obj.data.name_full

        if mesh_id in processed:
            instances[mesh_id]["users"].append(obj.name)
            continue

        processed.add(mesh_id)

        src_mesh, is_multires, level = get_proxy_mesh(context, obj)

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
        bpy.data.meshes.remove(src_mesh)

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    proxy = bpy.data.objects.new("MOS_Proxy", mesh)
    context.scene.collection.objects.link(proxy)

    session.set("proxy_name", proxy.name)
    session.set("mapping", mapping)
    session.set("instances", instances)
    session.set("multires_cache", multires_cache)

    return proxy


def apply_multires_back(context, obj, coords, mesh_id, session):

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
        print("MOS: multires vertex mismatch")
        return

    for i, v in enumerate(src_mesh.vertices):
        v.co = coords[i]

    src_obj = bpy.data.objects.new("MOS_ReshapeSource", src_mesh)
    context.scene.collection.objects.link(src_obj)

    bpy.ops.object.select_all(action="DESELECT")

    obj.select_set(True)
    src_obj.select_set(True)

    context.view_layer.objects.active = obj

    mr = get_multires(obj)

    try:
        bpy.ops.object.multires_reshape(modifier=mr.name)
    except Exception as e:
        print("MOS reshape failed:", e)

    bpy.data.objects.remove(src_obj, do_unlink=True)


def transfer_back(context, session):
    proxy = bpy.data.objects.get(session.get("proxy_name"))
    if not proxy:
        return

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

            apply_multires_back(context, obj, coords, mesh_id, session)
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
