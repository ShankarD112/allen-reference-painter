"""One supported launcher for source installs and packaged desktop executables."""
from __future__ import annotations
import argparse
import logging
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description='Allen Reference Painter desktop')
    parser.add_argument('--demo',action='store_true',help='Open synthetic offline practice data; not Allen anatomy')
    parser.add_argument('--self-test',action='store_true',help='Run offline packaged GUI smoke test and exit')
    parser.add_argument('--self-test-real',action='store_true',help='Run integration test against the real Allen atlas (downloads data)')
    parser.add_argument('--self-test-output',default=None,help='Folder for smoke-test outputs')
    args = parser.parse_args()
    args.self_test = args.self_test or args.self_test_real
    from .runtime import configure_logging
    log_path = configure_logging()
    log = logging.getLogger('allen_reference_painter.launcher')
    if args.self_test:
        logging.getLogger('allen_reference_painter').addHandler(logging.StreamHandler(sys.stderr))
    from qtpy import QtCore, QtWidgets
    from .jobs import Job
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName('AllenReferencePainter')
    app.setOrganizationName('AllenReferencePainter')
    app.setStyle('Fusion')

    def exception_hook(kind, value, traceback):
        log.error('unhandled exception',exc_info=(kind,value,traceback))
        if args.self_test:
            app.exit(1)
        else:
            QtWidgets.QMessageBox.critical(None,'Something went wrong',f'{value}\n\nDetails were saved to {log_path}.')
    sys.excepthook = exception_hook

    class Startup(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.job = None
            self.window = None
            self.setWindowTitle('Allen Reference Painter')
            self.resize(540,320)
            self.setStyleSheet('QWidget {background:#111827;color:#e5edf8;font:14px "Segoe UI";} QPushButton {padding:12px;background:#17695f;border:0;border-radius:6px;}')
            layout = QtWidgets.QVBoxLayout(self)
            title = QtWidgets.QLabel('Allen Reference Painter')
            title.setStyleSheet('font-size:26px;font-weight:bold;')
            layout.addWidget(title)
            self.message = QtWidgets.QLabel('Explore brain regions. Paint an ROI. Export atlas coordinates.\n\nThe first Allen atlas load downloads reference data from BrainGlobe. Later launches reuse your local cache.')
            self.message.setWordWrap(True)
            layout.addWidget(self.message)
            self.progress = QtWidgets.QProgressBar()
            self.progress.hide()
            layout.addWidget(self.progress)
            self.open_button = QtWidgets.QPushButton('Open Allen mouse atlas')
            self.open_button.clicked.connect(lambda:self.start(False))
            layout.addWidget(self.open_button)
            self.demo_button = QtWidgets.QPushButton('Try offline demo · synthetic anatomy')
            self.demo_button.clicked.connect(lambda:self.start(True))
            layout.addWidget(self.demo_button)
            if args.demo or args.self_test:
                QtCore.QTimer.singleShot(0,lambda:self.start(not args.self_test_real))

        def start(self,demo):
            if self.job is not None:
                return
            self.open_button.setEnabled(False)
            self.demo_button.setEnabled(False)
            self.message.setText('Opening synthetic practice data…' if demo else 'Opening Allen mouse atlas…\n\nFirst run may download a large atlas. Keep this window open. Your local cache will be reused on subsequent launches.')
            self.progress.setRange(0,0)
            self.progress.show()
            def load():
                # Import heavy dependencies off the GUI thread before constructing widgets.
                from . import desktop
                import numpy as np
                from .meshes import load_atlas_mesh
                if demo:
                    from .demo import DemoAtlas
                    atlas = DemoAtlas()
                else:
                    from brainglobe_atlasapi.bg_atlas import BrainGlobeAtlas
                    atlas = BrainGlobeAtlas('allen_mouse_25um')
                np.asarray(atlas.annotation)  # force lazy volume I/O in this thread
                shell = None
                for region in ['root','grey','CH','CTX','HPF']:
                    try:
                        shell = load_atlas_mesh(atlas, region)
                        break
                    except Exception:
                        log.warning('reference mesh unavailable region=%s',region,exc_info=True)
                return atlas,shell
            self.job = Job(load,'Opening atlas',self)
            self.job.succeeded.connect(self.ready)
            self.job.failed.connect(self.failed)
            self.job.finished.connect(self.finished)
            self.job.start()

        @QtCore.Slot(object)
        def ready(self,result):
            try:
                from .desktop import PainterWindow
                self.window = PainterWindow(*result)
                self.window.show()
                self.hide()
                if args.self_test:
                    QtCore.QTimer.singleShot(300,self.self_test)
            except Exception as exc:
                log.exception('window creation failed')
                self.failed(str(exc))

        def self_test(self):
            from .smoke import exercise_window
            try:
                exercise_window(self.window,Path(args.self_test_output) if args.self_test_output else None)
                log.info('self_test.PASS')
                self.window._dirty = False
                self.window.close()
                app.exit(0)
            except Exception:
                log.exception('self_test.FAIL')
                app.exit(1)

        @QtCore.Slot(str)
        def failed(self,message):
            self.message.setText(f'Could not open the atlas.\n{message}\n\nCheck your connection, then retry, or try the offline demo.\nDiagnostics: {log_path}')
            self.progress.hide()
            if args.self_test:
                app.exit(1)

        @QtCore.Slot()
        def finished(self):
            self.job.deleteLater()
            self.job = None
            self.open_button.setEnabled(True)
            self.demo_button.setEnabled(True)

        def closeEvent(self,event):
            if self.job is not None and self.job.isRunning():
                self.message.setText('Atlas loading is still running. Please wait for it to finish before closing.')
                event.ignore()
            else:
                event.accept()

    startup = Startup()
    startup.show()
    result = app.exec()
    # Never destroy a running QThread, including failure paths during construction.
    if startup.job is not None:
        startup.job.wait()
    return result

if __name__ == '__main__':
    raise SystemExit(main())
