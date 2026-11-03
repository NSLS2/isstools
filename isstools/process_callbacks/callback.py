
from bluesky.callbacks import CallbackBase

class ScanProcessingCallback(CallbackBase):
    def __init__(self, draw_func_interp, draw_func_bin, cloud_dispatcher,thread, print_func=None):
        self.draw_func_interp = draw_func_interp
        self.draw_func_bin = draw_func_bin
        self.cloud_dispatcher = cloud_dispatcher
        self.thread = thread
        if print_func is None:
            self.print = print
        else:
            def _print_func(msg):
                print_func(msg, tag='Processing', add_timestamp=True)
            self.print = _print_func
        super().__init__()

    def stop(self, doc):
        if doc['exit_status'] == 'success':
            self.thread.add_doc(doc)  # this queues it for processing
        else:
            reason = doc.get('reason', 'Unknown')
            self.print(f'Scan failed, reason: {reason}')
