import bpy
import time

from .protocol import UME_P_SafeObject, UME_P_Session, UME_P_Task


class UME_Task(UME_P_Task):
    """
    Base class for any background operation.

    Child classes should implement:

        setup()
        execute_chunk()
        cleanup()
    """

    name = "Task"

    def __init__(self):
        self.total = 1
        self.current = 0

        self.started = False
        self.finished = False

    def setup(self, obj: UME_P_SafeObject, bmesh, session: UME_P_Session):
        self.session = session
        self.obj = obj
        self.vertices = self.obj.data.vertices
        self.total = len(self.vertices)
        self.bm = bmesh

    def execute_chunk(self, context, chunk_size):
        """
        Process one chunk.

        Return:
            True -> task complete
            False -> task still running
        """
        raise NotImplementedError()

    def cleanup(self, context):
        """
        Called once after task completion
        """
        pass

    @property
    def progress(self) -> float:
        if self.total <= 0:
            return 0.0

        return min(self.current / self.total, 1.0)


class UME_TaskQueue:
    def __init__(self):
        self.tasks: list[UME_Task] = []

        self.current_index = 0

        self.chunk_size = 10000

        self.min_chunk = 1000
        self.max_chunk = 500000

        self.target_frame = 0.02

        self.cancelled = False

        self.on_finish = None

        self.progress = 0.0
        self.status = ""

    def add(self, task: UME_Task):
        self.tasks.append(task)

    def clear(self):
        self.tasks.clear()
        self.current_index = 0

    @property
    def current_task(self):
        if self.current_index >= len(self.tasks):
            return None

        return self.tasks[self.current_index]

    @property
    def finished(self):
        return self.current_index >= len(self.tasks)

    def cancel(self):
        self.cancelled = True

    def execute(self, context):
        if self.cancelled:
            self.clear()
            return True

        task = self.current_task

        if task is None:
            if self.on_finish:
                self.on_finish(context)

            return True

        if not task.started:
            print("starting task")
            # task.setup(context)
            task.started = True

        start = time.perf_counter()
        complete = task.execute_chunk(context, self.chunk_size)
        elapsed = time.perf_counter() - start

        # ------------------------------------------
        # adaptive chunk sizing
        # ------------------------------------------

        if elapsed < self.target_frame:
            self.chunk_size = int(self.chunk_size * 1.3)

        else:
            self.chunk_size = int(self.chunk_size * 0.7)

        self.chunk_size = max(self.min_chunk, min(self.chunk_size, self.max_chunk))

        # ------------------------------------------
        # update progress
        # ------------------------------------------

        total_progress = 0.0

        for i, t in enumerate(self.tasks):
            if i < self.current_index:
                total_progress += 1.0

            elif i == self.current_index:
                total_progress += t.progress

        self.progress = total_progress / max(len(self.tasks), 1)
        self.status = f"{task.name} {task.progress * 100:.1f}%"

        print(self.status)

        if complete:
            task.cleanup(context)
            task.finished = True
            self.current_index += 1

        return self.finished


# ------------------------------------------------------------
# Global queue instance
# ------------------------------------------------------------

QUEUE = UME_TaskQueue()


# ------------------------------------------------------------
# Modal operator
# ------------------------------------------------------------


class UME_OT_process_tasks(bpy.types.Operator):
    bl_idname = "ume.process_tasks"
    bl_label = "UME Background Processing"

    _timer = None

    def execute(self, context):
        wm = context.window_manager
        wm.progress_begin(0, 100)
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        finished = QUEUE.execute(context)

        wm = context.window_manager
        wm.progress_update(QUEUE.progress * 100)

        context.workspace.status_text_set(QUEUE.status)

        for area in context.screen.areas:
            area.tag_redraw()

        if finished:
            self.finish(context)
            return {"FINISHED"}

        return {"RUNNING_MODAL"}

    def finish(self, context):
        wm = context.window_manager
        wm.progress_end()
        context.workspace.status_text_set(None)
        wm.event_timer_remove(self._timer)


# ------------------------------------------------------------
# registration
# ------------------------------------------------------------

classes = (UME_OT_process_tasks,)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
