bl_info = {
    "name": "Universal Multi Edit",
    "author": "Tilapiatsu",
    "version": (4, 5, 0),
    "blender": (4, 0, 0),
    "location": "Automatic on mode switch",
    "description": "Multi-object Sculpt / Vertex Paint / Texture Paint workflows",
    "category": "Object",
}

from . import core

modules = (core,)


def register():
    for m in modules:
        m.register()


def unregister():
    for m in reversed(modules):
        m.unregister()
