

class ResourceWaster(ApeComponent):

    def _start(self):
        self._use_ram()
        self.thread = _CpuWaster(self)
        self.thread.start()
    def _stop(self):
        self.thread.keep_running = False

    def perform_action(self, request):