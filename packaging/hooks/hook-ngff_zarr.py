"""NGFF 0.36 inspects Dask source to select its Zarr compatibility path."""
from PyInstaller.utils.hooks import collect_data_files

# ngff_zarr.to_ngff_zarr calls inspect.getsource(dask.array.core.to_zarr).
# Preserve the source without changing or bypassing upstream feature detection.
module_collection_mode = {"dask.array.core": "pyz+py"}
datas = collect_data_files("ngff_zarr")
