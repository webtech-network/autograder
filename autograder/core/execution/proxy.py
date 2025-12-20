class LazyExecutorProxy:
    def __init__(self, executor_cls, *args, **kwargs):
        self._executor_cls = executor_cls
        self._args = args
        self._kwargs = kwargs
        self._instance = None

    def _ensure_started(self):
        """Initializes the real executor only on first use."""
        if self._instance is None:
            print(f"[{self._executor_cls.__name__}] Lazy start triggered...")
            self._instance = self._executor_cls.start(*self._args, **self._kwargs)
        return self._instance

    def stop(self):
        """Stops the executor if it was ever started."""
        if self._instance is not None:
            self._instance.stop()
            self._instance = None

    # Forward all other attribute access to the real executor <- the actual proxy workflow
    def __getattr__(self, name):
        real_executor = self._ensure_started()
        return getattr(real_executor, name)
    
    def __repr__(self):
        """Provide debugging information."""
        status = "started" if self._instance is not None else "not started"
        return f"LazyExecutorProxy({self._executor_cls.__name__}, {status})"