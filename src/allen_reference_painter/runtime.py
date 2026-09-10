"""Writable user paths and bounded, local application diagnostics."""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import sys


def data_dir() -> Path:
    override = os.environ.get('ALLEN_PAINTER_DATA_DIR')
    if override:
        root = Path(override).expanduser()
    elif sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'AllenReferencePainter'
    elif sys.platform == 'darwin':
        root = Path.home() / 'Library/Application Support/AllenReferencePainter'
    else:
        root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'allen-reference-painter'
    root.mkdir(parents=True, exist_ok=True)
    return root


def configure_logging() -> Path:
    folder = data_dir() / 'logs'
    folder.mkdir(exist_ok=True)
    path = folder / 'application.log'
    logger = logging.getLogger('allen_reference_painter')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=4, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)
    logger.info('session.start python=%s platform=%s frozen=%s', platform.python_version(), platform.platform(), bool(getattr(sys, 'frozen', False)))
    return path
