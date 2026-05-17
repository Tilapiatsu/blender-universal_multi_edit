import bpy
from typing import Protocol


class UME_EditMode(Protocol):
    name: str

    def create_proxy(self, context, objects, session) -> bpy.types.Object: ...

    def transfer_back(self, context, session) -> None: ...
