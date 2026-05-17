import bpy
import bmesh
from .utils import new_object

from .edit_mode import UME_EditMode


class Mode(UME_EditMode):
    name: str = "TEXTURE_PAINT"

    def create_proxy(self, context, objects, session) -> bpy.types.Object:
        mesh = bpy.data.meshes.new("UME_TPaint")
        bm = bmesh.new()

        uv = bm.loops.layers.uv.verify()

        mat_lookup = {}
        mat_index = 0

        for obj in objects:
            src = bmesh.new()
            src.from_mesh(obj.data)
            src.transform(obj.matrix_world)

            src.verts.ensure_lookup_table()
            src.faces.ensure_lookup_table()

            src_uv = src.loops.layers.uv.verify()

            vmap = {}

            for v in src.verts:
                vmap[v] = bm.verts.new(v.co)

            bm.verts.ensure_lookup_table()

            for f in src.faces:
                nf = bm.faces.new([vmap[v] for v in f.verts])

                mat = obj.material_slots[f.material_index].material
                if mat not in mat_lookup:
                    mat_lookup[mat] = mat_index
                    mat_index += 1

                nf.material_index = mat_lookup[mat]

                for ls, ld in zip(f.loops, nf.loops):
                    ld[uv].uv = ls[src_uv].uv

            src.free()

        bm.to_mesh(mesh)
        bm.free()

        proxy = new_object(context, "UME_Proxy", mesh)

        # preserve materials in correct order
        ordered = sorted(mat_lookup.items(), key=lambda x: x[1])
        for mat, _ in ordered:
            proxy.data.materials.append(mat)

        session["proxy"] = proxy.name
        session["mat_lookup"] = mat_lookup

        return proxy

    def transfer_back(self, context, session) -> None:
        pass  # texture paint = destructive paint, no need
