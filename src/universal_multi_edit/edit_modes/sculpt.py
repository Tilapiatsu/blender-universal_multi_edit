import bpy
import bmesh
from typing import Union
from ..safe_object import UME_SafeObject


from .edit_mode import UME_EditMode
from ..protocol import UME_P_Session
from ..task_manager import UME_Task


class InitProxyTask(UME_Task):
    name = "Initialize proxy"

    def __init__(self):
        super().__init__()

    def execute_chunk(self, context, chunk_size):
        proxy = bpy.data.meshes.new("UME_PROXY")
        proxy_obj = bpy.data.objects.new("UME_PROXY", proxy)
        context.collection.objects.link(proxy_obj)
        self.session.proxy = UME_SafeObject(proxy_obj)

        return True


class BuildProxyTask(UME_Task):
    name = "Building proxy"

    def __init__(self):
        super().__init__()
        self.obj = None
        self.vertices = None
        self.bm = None

    def execute_chunk(self, context, chunk_size):
        end = min(self.current + chunk_size, self.total)
        for i in range(self.current, end):
            print(i)
            v = self.vertices[i]

            # create proxy data
            self.bm.verts.new(v.co)

        self.current = end

        return self.current >= self.total


class CommitProxyTask(UME_Task):
    name = "Finalizing proxy"

    def __init__(self):
        super().__init__()
        self.obj = None
        self.vertices = None
        self.bm = None


class Mode(UME_EditMode):
    name: str = "SCULPT"
    _init_proxy_task: Union[UME_Task, None] = None
    _build_proxy_task: Union[UME_Task, None] = None
    _commit_proxy_task: Union[UME_Task, None] = None

    @property
    def init_proxy_task(self) -> UME_Task:
        if self._init_proxy_task is None:
            self._init_proxy_task = InitProxyTask()

        return self._init_proxy_task

    @property
    def build_proxy_task(self) -> UME_Task:
        if self._build_proxy_task is None:
            self._build_proxy_task = BuildProxyTask()

        return self._build_proxy_task

    @property
    def commit_proxy_task(self) -> UME_Task:
        if self._commit_proxy_task is None:
            self._commit_proxy_task = CommitProxyTask()

        return self._commit_proxy_task

    def create_proxy(self, context, objects: list[UME_SafeObject], session: UME_P_Session) -> UME_SafeObject:
        mesh = bpy.data.meshes.new("UME_ProxyMesh")
        bm = bmesh.new()

        mapping = []
        instances = {}
        multires_cache = {}

        processed = set()

        self._init_offsets()

        for obj in objects:
            if not obj.object:
                continue
            mesh_id = obj.data.name_full

            if mesh_id in processed:
                instances[mesh_id]["users"].append(obj.name)
                continue

            processed.add(mesh_id)

            src_obj, is_multires, level = self._get_evaluated_object(context, obj)
            src_mesh = src_obj.data
            if is_multires:
                src_obj = UME_SafeObject(bpy.data.objects.new(f"{obj.name}_orig_eval", object_data=src_mesh))
                self._store_object_offsets(src_obj, session)
                session.topology["objects"][-1]["object"] = obj
            else:
                self._store_object_offsets(UME_SafeObject(src_obj), session)

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
            if is_multires:
                bpy.data.meshes.remove(src_mesh)

        bm.normal_update()
        bm.to_mesh(mesh)
        bm.free()

        proxy = UME_SafeObject(bpy.data.objects.new("UME_Proxy", mesh))
        context.scene.collection.objects.link(proxy.object)

        session.proxy = proxy
        session.set("mapping", mapping)
        session.set("instances", instances)
        session.set("multires_cache", multires_cache)

        return session.proxy

    def transfer_back(self, context, session) -> None:
        proxy = session.proxy
        if not proxy or not proxy.object:
            return

        self._transfer(context, session, proxy, transfer_back=True)

    def _transfer(
        self,
        context,
        session: UME_P_Session,
        proxy: UME_SafeObject,
        transfer_back: bool = True,
    ) -> None:
        if not proxy.object:
            return

        for topo in self._iter_topology_objects(session):
            obj = topo["object"]

            if not obj.object:
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
