from multiprocessing import freeze_support
from allen_reference_painter.main import main

if __name__ == '__main__':
    freeze_support()
    raise SystemExit(main())
