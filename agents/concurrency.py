"""Thread pools that keep the submitter's context.

A plain ThreadPoolExecutor runs tasks in a fresh context, so contextvars --
such as the run an LLM call is billed to -- silently vanish at every fan-out.
Every pool in the agents uses this instead.
"""

import contextvars
from concurrent.futures import ThreadPoolExecutor


class ContextThreadPoolExecutor(ThreadPoolExecutor):
    def submit(self, fn, /, *args, **kwargs):
        return super().submit(contextvars.copy_context().run, fn, *args, **kwargs)
