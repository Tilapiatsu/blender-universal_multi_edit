import bpy
import bmesh
from .utils import new_proxy_object


def create_proxy(context, objects, session):
    mesh = bpy.data.meshes.new("UME_TPaint")
    bm = bmesh.new()

    uv_layer = bm.loops.layers.uv.verify()

    mapping = []
    face_material_map = []

    for obj in objects:
        src = bmesh.new()
        src.from_mesh(obj.data)
        src.transform(obj.matrix_world)

        src.verts.ensure_lookup_table()
        src.faces.ensure_lookup_table()

        src_uv = src.loops.layers.uv.verify()

        vmap = {}

        for v in src.verts:
            nv = bm.verts.new(v.co)
            vmap[v] = nv

        bm.verts.ensure_lookup_table()

        for f in src.faces:
            nf = bm.faces.new([vmap[v] for v in f.verts])

            nf.material_index = min(f.material_index, len(mesh.data.materials) - 1)

            face_material_map.append((len(mapping), obj.name, f.material_index))

            for ls, ld in zip(f.loops, nf.loops):
                ld[uv_layer].uv = ls[src_uv].uv

        src.free()

    bm.to_mesh(mesh)
    bm.free()

    proxy = bpy.data.objects.new("UME_Proxy", mesh)
    context.scene.collection.objects.link(proxy)

    # copy ALL materials in stable order per object (NOT flattened blindly)
    for obj in objects:
        for slot in obj.material_slots:
            if slot.material:
                if slot.material.name not in [m.name for m in proxy.data.materials]:
                    proxy.data.materials.append(slot.material)

    session["proxy_name"] = proxy.name
    session["face_material_map"] = face_material_map

    return proxy
