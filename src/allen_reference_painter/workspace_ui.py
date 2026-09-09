"""Task-oriented desktop workspace, kept separate from scientific operations."""
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QKeySequence, QShortcut
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from pyvistaqt import QtInteractor
from .app import CELL_UNIT_OPTIONS, NONE_LABEL, SINGLE_COLOR_LABEL

STYLE = '''
QWidget { background: #111827; color: #e5edf8; font-family: Segoe UI, sans-serif; font-size: 12px; }
QMainWindow, QSplitter { background: #0b1020; }
QLabel#title { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#hint { color: #a7b7d0; }
QPushButton { background: #25334b; border: 1px solid #3a4c68; border-radius: 6px; padding: 8px 10px; }
QPushButton:hover { background: #344b69; border-color: #67e8d0; }
QPushButton:checked { background: #17695f; border-color: #67e8d0; }
QPushButton:disabled { color: #65738a; background: #1a2436; }
QPushButton#primary { background: #16685d; border-color: #43c4b1; font-weight: 600; }
QLineEdit, QComboBox, QTableView { background: #0b1221; border: 1px solid #34435b; border-radius: 5px; padding: 6px; selection-background-color: #17695f; }
QTabWidget::pane { border: 0; }
QTabBar::tab { padding: 10px 8px; background: #172237; color: #a7b7d0; }
QTabBar::tab:selected { background: #253b50; color: #7ce9d6; border-bottom: 2px solid #7ce9d6; }
QHeaderView::section { background: #233149; border: 0; padding: 5px; }
QTableView { alternate-background-color: #172237; }
QSlider::groove:horizontal { background: #34435b; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal { background: #7ce9d6; width: 12px; margin: -5px 0; border-radius: 6px; }
QScrollArea { border: 0; }
QToolTip { background: #25334b; color: white; border: 1px solid #7ce9d6; }
'''


def build_workspace(w):
    central = QtWidgets.QWidget()
    w.setCentralWidget(central)
    outer = QtWidgets.QVBoxLayout(central)
    outer.setContentsMargins(12, 12, 12, 6)
    header = QtWidgets.QHBoxLayout()
    title = QtWidgets.QLabel('Allen Reference Painter')
    title.setObjectName('title')
    header.addWidget(title)
    badge = QtWidgets.QLabel('  DEMO · SYNTHETIC ANATOMY  ' if w._is_demo else '  MOUSE ATLAS · 25 µm  ')
    badge.setObjectName('hint')
    header.addWidget(badge)
    header.addStretch()
    help_button = QtWidgets.QPushButton('Quick guide')
    help_button.clicked.connect(w._show_guide)
    header.addWidget(help_button)
    outer.addLayout(header)
    subtitle = QtWidgets.QLabel('Explore brain regions, paint a region of interest, and export coordinates for analysis.')
    subtitle.setObjectName('hint')
    outer.addWidget(subtitle)
    splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
    outer.addWidget(splitter, 1)
    w.tabs = QtWidgets.QTabWidget()
    w.tabs.setMinimumWidth(310)
    w.tabs.setMaximumWidth(470)
    splitter.addWidget(w.tabs)

    def page(title):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setSpacing(10)
        scroll.setWidget(content)
        w.tabs.addTab(scroll, title)
        return layout

    def hint(layout, text):
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setObjectName('hint')
        layout.addWidget(label)
        return label

    def button(layout, attr, text, callback, primary=False):
        b = QtWidgets.QPushButton(text)
        b.clicked.connect(callback)
        if primary:
            b.setObjectName('primary')
        setattr(w, attr, b)
        layout.addWidget(b)
        return b

    def check(layout, attr, text, checked, callback=None):
        b = QtWidgets.QCheckBox(text)
        b.setChecked(checked)
        if callback:
            b.toggled.connect(lambda _: callback())
        setattr(w, attr, b)
        layout.addWidget(b)
        return b

    def slider(layout, attr, title, low, high, value, callback):
        label = QtWidgets.QLabel(f'{title} · {value}')
        layout.addWidget(label)
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        s.setRange(low, high)
        s.setValue(value)
        s.setAccessibleName(title)
        s.valueChanged.connect(lambda v: (label.setText(f'{title} · {v}'), callback()))
        layout.addWidget(s)
        setattr(w, attr, s)
        return s

    regions = page('1 Regions')
    hint(regions, 'Find a brain region by name or acronym. Load it, then switch to Paint.')
    w.region_search = QtWidgets.QLineEdit(placeholderText='Search regions, e.g. ENT or hippocampus')
    w.region_search.textChanged.connect(w._filter_region_picker)
    w.region_search.returnPressed.connect(w._load_selected_region)
    regions.addWidget(w.region_search)
    w.region_picker = QtWidgets.QComboBox()
    regions.addWidget(w.region_picker)
    button(regions, 'load_region_button', 'Load region', w._load_selected_region, True)
    w.region_table = QtWidgets.QTableWidget(0, 4)
    w.region_table.setHorizontalHeaderLabels(['Show', 'Area', 'Name', 'Color'])
    w.region_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    w.region_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    w.region_table.verticalHeader().hide()
    w.region_table.setColumnWidth(0, 42)
    w.region_table.setColumnWidth(1, 56)
    w.region_table.setColumnWidth(2, 110)
    w.region_table.horizontalHeader().setStretchLastSection(True)
    w.region_table.setMinimumHeight(180)
    w.region_table.cellClicked.connect(w._region_table_clicked)
    regions.addWidget(w.region_table, 1)
    button(regions, 'remove_region_button', 'Remove active region', w._remove_active_region)
    check(regions, 'reference_checkbox', 'Show reference brain', True, w._refresh_scene)
    slider(regions, 'brain_opacity_slider', 'Reference opacity (%)', 0, 50, 8, w._refresh_scene)
    slider(regions, 'active_opacity_slider', 'Active region opacity (%)', 5, 100, 60, w._refresh_scene)
    slider(regions, 'reference_opacity_slider', 'Other regions opacity (%)', 0, 100, 30, w._refresh_scene)

    paint = page('2 Paint')
    hint(paint, 'Choose Paint or Erase, then click the active mesh. Navigate lets you rotate without painting.')
    paint.addWidget(QtWidgets.QLabel('Active region'))
    w.active_combo = QtWidgets.QComboBox()
    w.active_combo.currentTextChanged.connect(w._set_active_area)
    paint.addWidget(w.active_combo)
    w.mode_buttons = {}
    for label, mode in [('Navigate', 'navigate'), ('Paint', 'paint'), ('Erase', 'erase')]:
        b = button(paint, f'{mode}_button', label, lambda _=False, m=mode: w._set_mode(m))
        b.setCheckable(True)
        w.mode_buttons[mode] = b
    w.mode_button = w.paint_button
    slider(paint, 'brush_slider', 'Brush radius (µm)', 25, 800, 150, w._update_pick_markers)
    check(paint, 'continuous_checkbox', 'Paint continuously while dragging', True)
    check(paint, 'symmetry_checkbox', 'Mirror across the brain midline', False, w._update_pick_markers)
    check(paint, 'sync_slice_checkbox', 'Move slices to the clicked point', True)
    button(paint, 'paint_color_button', 'Choose ROI color', w._choose_paint_color)
    button(paint, 'mirror_color_button', 'Choose mirror marker color', w._choose_mirror_color)
    slider(paint, 'paint_opacity_slider', 'Paint opacity (%)', 10, 100, 90, w._refresh_scene)
    button(paint, 'undo_button', 'Undo stroke  ·  Ctrl+Z', w._undo)
    button(paint, 'redo_button', 'Redo stroke  ·  Ctrl+Shift+Z', w._redo)
    button(paint, 'clear_button', 'Clear active paint', w._clear_active_paint)
    paint.addStretch()

    cells = page('3 Cells')
    hint(cells, 'Import a coordinate table. X = AP, Y = DV, Z = ML. Coordinates use the BrainGlobe atlas origin, not bregma.')
    cells.addWidget(QtWidgets.QLabel('Coordinate units in your file'))
    w.cell_units_combo = QtWidgets.QComboBox()
    w.cell_units_combo.addItems(list(CELL_UNIT_OPTIONS))
    w.cell_units_combo.currentTextChanged.connect(w._apply_cell_units_to_loaded_cells)
    cells.addWidget(w.cell_units_combo)
    hint(cells, 'Auto detect asks you to confirm units: small values can mean mm, voxels, or µm.')
    button(cells, 'load_cells_button', 'Import cell table…', w._load_cells_dialog, True)
    button(cells, 'apply_cell_units_button', 'Apply coordinate units', w._apply_cell_units_to_loaded_cells)
    w.cell_summary = hint(cells, 'No cells loaded. CSV, TSV, TXT, XLS and XLSX are supported.')
    button(cells, 'view_cell_table_button', 'Choose visible cells…', w._show_cell_table_dialog)
    w.view_cell_table_button.setEnabled(False)
    for attr, title, initial in [('cell_label_combo', 'Cell labels / hover', NONE_LABEL), ('cell_colorby_combo', 'Color cells by', SINGLE_COLOR_LABEL)]:
        cells.addWidget(QtWidgets.QLabel(title))
        combo = QtWidgets.QComboBox()
        combo.addItem(initial)
        combo.currentTextChanged.connect(w._cell_metadata_options_changed)
        setattr(w, attr, combo)
        cells.addWidget(combo)
    slider(cells, 'cell_size_slider', 'Cell point size', 4, 60, 14, w._resize_cells)
    button(cells, 'clear_cells_button', 'Remove cells', w._clear_cells)
    cells.addStretch()

    export = page('4 Export')
    hint(export, 'Save atlas-space meshes and face IDs for analysis. Exports include coordinates in microns and atlas metadata.')
    button(export, 'save_roi_button', 'Export active ROI…', w._save_active_roi, True)
    button(export, 'save_scene_button', 'Export entire scene…', w._save_scene_outputs)
    hint(export, 'Screenshots capture the current cell selection. Slice images include the heatmap legend.')
    for attr, text, callback in [('screenshot_button','3D screenshot', w._save_3d_screenshot), ('coronal_shot','Coronal screenshot', w._save_coronal_screenshot), ('sagittal_shot','Sagittal screenshot',w._save_sagittal_screenshot), ('both_shot','Both slices',w._save_both_2d_screenshots), ('all_shot','All views',w._save_all_view_screenshots)]:
        button(export, attr, text, callback)
    button(export, 'output_button', 'Open output folder', w._open_outputs)
    button(export, 'logs_button', 'Open application logs', w._open_logs)
    export.addStretch()

    center = QtWidgets.QWidget()
    center_layout = QtWidgets.QVBoxLayout(center)
    center_layout.setContentsMargins(6, 0, 6, 0)
    toolbar = QtWidgets.QHBoxLayout()
    w.mode_hint = QtWidgets.QLabel('Navigate · Drag to rotate · Wheel to zoom')
    w.mode_hint.setWordWrap(True)
    w.mode_hint.setMinimumWidth(80)
    w.mode_hint.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
    toolbar.addWidget(w.mode_hint, 1)
    for text, cb in [('Iso',w._view_iso),('AP',w._view_yz),('DV',w._view_xz),('ML',w._view_xy)]:
        b = QtWidgets.QPushButton(text)
        b.clicked.connect(cb)
        toolbar.addWidget(b)
    center_layout.addLayout(toolbar)
    w.plotter = QtInteractor(center, auto_update=False)
    center_layout.addWidget(w.plotter.interactor, 1)
    splitter.addWidget(center)
    right = QtWidgets.QWidget()
    right.setMinimumWidth(280)
    right_layout = QtWidgets.QVBoxLayout(right)
    right_layout.setContentsMargins(6, 0, 0, 0)
    right_layout.addWidget(QtWidgets.QLabel('SLICE INSPECTOR'))
    for plane, axis in [('coronal',0),('sagittal',2)]:
        label = QtWidgets.QLabel(plane.title())
        setattr(w, f'{plane}_label', label)
        right_layout.addWidget(label)
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        s.setRange(0,w.shape[axis]-1)
        s.setAccessibleName(f'{plane} slice')
        s.valueChanged.connect(w._on_slice_changed)
        setattr(w, f'{plane}_slider',s)
        right_layout.addWidget(s)
        fig = Figure(figsize=(4,3),dpi=90)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumSize(160,150)
        setattr(w,f'{plane}_fig',fig)
        setattr(w,f'{plane}_canvas',canvas)
        right_layout.addWidget(canvas,1)
    options_button = QtWidgets.QPushButton('Slice display options ▸')
    options_button.setCheckable(True)
    right_layout.addWidget(options_button)
    options = QtWidgets.QWidget()
    options_layout = QtWidgets.QVBoxLayout(options)
    options_layout.setContentsMargins(0, 0, 0, 0)
    options.hide()
    right_layout.addWidget(options)
    options_button.toggled.connect(options.setVisible)
    options_button.toggled.connect(lambda checked: options_button.setText('Slice display options ▾' if checked else 'Slice display options ▸'))
    check(options_layout,'show_painted_2d_checkbox','Show ROI on slices',True,w._update_slice_views)
    check(options_layout,'show_cells_2d_checkbox','Show cells on slices',True,w._update_slice_views)
    check(options_layout,'coronal_cells_2d_checkbox','Coronal cells',True,w._update_slice_views)
    check(options_layout,'sagittal_cells_2d_checkbox','Sagittal cells',True,w._update_slice_views)
    check(options_layout,'cell_heatmap_2d_checkbox','Match 3D heatmap colors',True,w._heatmap_changed)
    slider(options_layout,'slice_thickness_slider','Cell / ROI slab thickness (µm)',25,1000,250,w._update_slice_views)
    check(options_layout,'show_coronal_plane_checkbox','Show coronal plane in 3D',False,w._update_slice_planes)
    check(options_layout,'show_sagittal_plane_checkbox','Show sagittal plane in 3D',False,w._update_slice_planes)
    slider(options_layout,'plane_opacity_slider','3D slice plane opacity (%)',1,60,12,w._update_slice_planes)
    w.cell_colorbar_title = QtWidgets.QLabel('Cell colors')
    right_layout.addWidget(w.cell_colorbar_title)
    w.cell_colorbar_fig = Figure(figsize=(4,.6),dpi=90)
    w.cell_colorbar_canvas = FigureCanvasQTAgg(w.cell_colorbar_fig)
    w.cell_colorbar_canvas.setFixedHeight(65)
    right_layout.addWidget(w.cell_colorbar_canvas)
    splitter.addWidget(right)
    splitter.setSizes([335,760,330])
    splitter.setCollapsible(0,False)
    splitter.setCollapsible(1,False)
    w.status = w.statusBar()
    w.shortcuts = []
    for key, callback in [('Ctrl+Z',w._undo),('Ctrl+Shift+Z',w._redo),('Ctrl+O',w._load_cells_dialog),('Ctrl+S',w._save_scene_outputs),('Escape',lambda:w._set_mode('navigate'))]:
        shortcut = QShortcut(QKeySequence(key),w)
        shortcut.activated.connect(callback)
        w.shortcuts.append(shortcut)
