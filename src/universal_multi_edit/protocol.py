import bpy
from enum import Enum
from typing import Protocol, Union


class UME_State(Enum):
    IDLE = "IDLE"
    EDIT = "EDIT"
    EXITING = "EXITING"


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

    def set(self, key, value) -> None: ...
    def get(self, key, default=None): ...
    def __getitem__(self, key): ...
    def __setitem__(self, key, value) -> None: ...
    def __contains__(self, key) -> bool: ...


class UME_P_EditMode(Protocol):
    name: str
    vert_offset: int
    face_offset: int
    loop_offset: int

    def create_proxy(self, context, objects, session) -> bpy.types.Object: ...

    def transfer_back(self, context, session) -> None: ...

    def _transfer(
        self, context, session: UME_P_Session, proxy: bpy.types.Object, transfer_back: bool = True
    ) -> None: ...

    def _init_offsets(self) -> None: ...

    def _store_object_offsets(self, obj: bpy.types.Object, session) -> None: ...

    def _apply_offsets(self, obj) -> None: ...
