import bpy
import bmesh
from enum import Enum
from typing import Protocol, Union


class UME_State(Enum):
    IDLE = "IDLE"
    EDIT = "EDIT"
    EXITING = "EXITING"


class UME_P_SafeObject(Protocol):
    @property
    def object(self) -> bpy.types.Object: ...

    @property
    def is_valid_object(self) -> bool: ...

    @property
    def object_in_view_layer(self) -> bool: ...


class UME_P_Core(Protocol):
    def create_session(self, ctx, mode: str): ...
    def destroy_session(self) -> None: ...
    def cleanup_session(self, ctx) -> None: ...
    def manage_session(self, context, mode: str) -> None: ...


class UME_P_EditModeState(Protocol):
    core: UME_P_Core
    name: UME_State

    def enter(self, context) -> None: ...

    def exit(self, context, mode: str = "OBJECT") -> None: ...

    def monitor(self) -> Union[float, None]: ...


class UME_P_Session(Protocol):
    mode: Union[str, None]
    state: Union[UME_P_EditModeState, None]
    topology: dict

    @property
    def proxy(self) -> bpy.types.Object: ...

    @proxy.setter
    def proxy(self, obj) -> None: ...

    def set(self, key, value) -> None: ...
    def get(self, key, default=None): ...
    def __getitem__(self, key): ...
    def __setitem__(self, key, value) -> None: ...
    def __contains__(self, key) -> bool: ...


class UME_P_Task(Protocol):
    name: str

    def setup(self, obj, bmesh): ...

    def execute_chunk(self, context, chunk_size): ...

    def cleanup(self, context): ...

    @property
    def progress(self): ...


class UME_P_EditMode(Protocol):
    name: str
    _build_proxy_task: Union[UME_P_Task, None] = None
    vert_offset: int
    face_offset: int
    loop_offset: int

    @property
    def build_proxy_task(self) -> UME_P_Task: ...

    def create_proxy_tasks(self, context, obj_list: list[UME_P_SafeObject], session, queue):
        queue.clear()

        for obj in session.objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            self.build_proxy_task.setup(obj, bm, session)
            queue.add(self.build_proxy_task)

        queue.on_finish = lambda ctx: session.enter_proxy_mode(ctx)

        bpy.ops.ume.process_tasks()

    def create_proxy(self, context, objects, session) -> UME_P_SafeObject: ...

    def transfer_back(self, context, session) -> None: ...

    def _transfer(
        self, context, session: UME_P_Session, proxy: UME_P_SafeObject, transfer_back: bool = True
    ) -> None: ...

    def _init_offsets(self) -> None: ...

    def _store_object_offsets(self, obj: bpy.types.Object, session) -> None: ...

    def _apply_offsets(self, obj) -> None: ...
