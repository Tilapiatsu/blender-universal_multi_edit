bl_info = {
    "name": "Multi Object Sculpt",
    "author": "Tilapiatsu",
    "version": (3, 6, 0),
    "blender": (4, 0, 0),
    "location": "Automatic on Sculpt Mode",
    "description": "Multi-object sculpt with stable multires reshape",
    "category": "Sculpt",
}

import bpy
import bmesh
from bpy.app.handlers import persistent
from mathutils import Vector

# ==========================================================
# GLOBALS
# ==========================================================

SESSION = {}

_LAST_MODE = None
PENDING_START = False
PENDING_FINISH = False
_TIMER_RUNNING = False


# ==========================================================
# HELPERS
# ==========================================================


def clear_session():
    SESSION.clear()


def selected_meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


def get_multires(obj):
    for mod in obj.modifiers:
        if mod.type == "MULTIRES":
            return mod
    return None


def has_shape_keys(obj):
    return obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 0


def restore_visibility():
    for name, state in SESSION.get("visibility", {}).items():
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_set(state)


# ==========================================================
# SHAPE KEYS
# ==========================================================


def apply_shape_key_delta(obj, deltas):

    keys = obj.data.shape_keys.key_blocks

    if obj.data.shape_keys.use_relative:
        for kb in keys:
            for idx, delta in deltas.items():
                kb.data[idx].co += delta
    else:
        kb = keys[0]
        for idx, delta in deltas.items():
            kb.data[idx].co += delta


# ==========================================================
# PROXY SOURCE MESH
# ==========================================================


def get_proxy_mesh(context, obj):

    mr = get_multires(obj)

    if not mr:
        return obj.data.copy(), False, 0

    old_view = mr.levels
    old_render = mr.render_levels

    level = mr.sculpt_levels

    mr.levels = level
    mr.render_levels = level

    dg = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(dg)

    me = bpy.data.meshes.new_from_object(eval_obj)

    mr.levels = old_view
    mr.render_levels = old_render

    return me, True, level


# ==========================================================
# PROXY BUILD
# ==========================================================


def create_proxy(context, objects):

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

    SESSION["proxy_name"] = proxy.name
    SESSION["mapping"] = mapping
    SESSION["instances"] = instances
    SESSION["multires_cache"] = multires_cache

    return proxy


# ==========================================================
# MULTIRES RESHAPE (FIXED)
# ==========================================================


def apply_multires_back(context, obj, coords, mesh_id):

    original = SESSION["multires_cache"].get(mesh_id, [])

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


# ==========================================================
# TRANSFER BACK
# ==========================================================


def transfer_back(context):

    proxy = bpy.data.objects.get(SESSION.get("proxy_name"))
    if not proxy:
        return

    proxy_verts = proxy.data.vertices
    mapping = SESSION["mapping"]
    instances = SESSION["instances"]

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

            apply_multires_back(context, obj, coords, mesh_id)
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


# ==========================================================
# SESSION
# ==========================================================


def start_multi_sculpt(context):

    clear_session()

    objs = selected_meshes(context)

    if len(objs) <= 1:
        return

    active = context.view_layer.objects.active

    SESSION["active_object"] = active.name if active else None
    SESSION["originals"] = [o.name for o in objs]
    SESSION["visibility"] = {o.name: o.hide_get() for o in objs}

    proxy = create_proxy(context, objs)

    for o in objs:
        o.hide_set(True)

    bpy.ops.object.select_all(action="DESELECT")
    proxy.select_set(True)
    context.view_layer.objects.active = proxy


def finish_multi_sculpt(context):

    if not SESSION:
        return

    transfer_back(context)

    proxy = bpy.data.objects.get(SESSION.get("proxy_name"))
    if proxy:
        bpy.data.objects.remove(proxy, do_unlink=True)

    restore_visibility()

    bpy.ops.object.select_all(action="DESELECT")

    for name in SESSION.get("originals", []):
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)

    active_name = SESSION.get("active_object")
    if active_name:
        obj = bpy.data.objects.get(active_name)
        if obj:
            context.view_layer.objects.active = obj

    clear_session()


# ==========================================================
# SAFE TIMER
# ==========================================================


def process_pending():

    global PENDING_START
    global PENDING_FINISH
    global _TIMER_RUNNING

    ctx = bpy.context

    try:
        if PENDING_START:
            PENDING_START = False

            objs = selected_meshes(ctx)

            if len(objs) > 1:
                if ctx.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")

                start_multi_sculpt(ctx)

                proxy = bpy.data.objects.get(SESSION["proxy_name"])

                if proxy:
                    bpy.ops.object.select_all(action="DESELECT")
                    proxy.select_set(True)
                    ctx.view_layer.objects.active = proxy
                    bpy.ops.object.mode_set(mode="SCULPT")

        elif PENDING_FINISH:
            PENDING_FINISH = False

            if ctx.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            finish_multi_sculpt(ctx)

    except Exception as e:
        print("MOS:", e)

    _TIMER_RUNNING = False
    return None


# ==========================================================
# MODE WATCHER
# ==========================================================


@persistent
def depsgraph_monitor(scene):

    global _LAST_MODE
    global PENDING_START
    global PENDING_FINISH
    global _TIMER_RUNNING

    ctx = bpy.context
    obj = ctx.active_object

    mode = obj.mode if obj else "OBJECT"

    if _LAST_MODE is None:
        _LAST_MODE = mode
        return

    if _LAST_MODE != "SCULPT" and mode == "SCULPT":
        if len(selected_meshes(ctx)) > 1:
            PENDING_START = True

    elif _LAST_MODE == "SCULPT" and mode != "SCULPT":
        if SESSION:
            PENDING_FINISH = True

    if (PENDING_START or PENDING_FINISH) and not _TIMER_RUNNING:
        _TIMER_RUNNING = True
        bpy.app.timers.register(process_pending, first_interval=0.01)

    _LAST_MODE = mode


# ==========================================================
# REGISTER
# ==========================================================


def register():

    if depsgraph_monitor not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_monitor)


def unregister():

    if depsgraph_monitor in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_monitor)


if __name__ == "__main__":
    register()
