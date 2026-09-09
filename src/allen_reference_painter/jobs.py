"""Background I/O with results delivered to a GUI-thread QObject."""
import logging
import time
from qtpy import QtCore

log = logging.getLogger(__name__)

class Job(QtCore.QThread):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, operation, name, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.name = name

    def run(self):
        started = time.perf_counter()
        log.info('job.start operation=%s', self.name)
        try:
            result = self.operation()
        except Exception as exc:
            log.exception('job.failed operation=%s', self.name)
            self.failed.emit(str(exc))
        else:
            log.info('job.complete operation=%s elapsed_ms=%.1f', self.name, (time.perf_counter()-started)*1000)
            self.succeeded.emit(result)
