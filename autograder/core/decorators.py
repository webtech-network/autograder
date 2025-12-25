
import functools
from autograder.core.execution.proxy import LazyExecutorProxy


def With(executor_cls, **executor_config):
    """
    Aspect that injects a Lazy Executor into the template.
    Removes the need for 'clean' flags or manual start/stop calls.
    """
    def decorator(cls):
        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            kwargs.pop('clean', None)
            self.executor = LazyExecutorProxy(executor_cls, **executor_config)
            original_init(self, *args, **kwargs)

        original_stop = getattr(cls, 'stop', lambda s: None)

        @functools.wraps(original_stop)
        def new_stop(self):
            original_stop(self)
            if getattr(self, 'executor', None):
                self.executor.stop()

        cls.__init__ = new_init
        cls.stop = new_stop
        cls.requires_execution_helper = property(lambda self: True)
        cls.execution_helper = property(lambda self: self.executor)

        return cls
    return decorator
