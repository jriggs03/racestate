"""A single consumer keeps ordering and ownership straightforward."""
from queue import Empty


def consume(queue, state, stop):
    while not stop.is_set() or not queue.empty():
        try:
            event = queue.get(timeout=0.1)
        except Empty:
            continue
        try:
            state.apply(event)
        finally:
            queue.task_done()
