import bpy


class UME_OT_background_processor(bpy.types.Operator):
    bl_idname = "ume.process"
    bl_label = "Processing"

    _timer = None

    def modal(self, context, event):

        if event.type == "TIMER":
            finished = queue.execute()

            context.area.tag_redraw()

            if finished:
                self.finish(context)
                return {"FINISHED"}

        return {"PASS_THROUGH"}


classes = (UME_OT_background_processor,)


def register():
    for c in classes:
        c.register()


def unregister():
    for c in classes:
        c.unregister()
