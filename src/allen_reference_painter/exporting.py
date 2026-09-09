"""Portable coordinate-aware exports, published only after every file succeeds."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import uuid
import numpy as np
import trimesh


def export_snapshot(snapshot, destination, active_only=False):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    stem = ('roi' if active_only else 'scene') + '_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    staging = Path(tempfile.mkdtemp(prefix='.export-', dir=destination))
    final = destination / stem
    try:
        manifest = {k: snapshot[k] for k in ('atlas', 'atlas_resolution_um', 'atlas_shape', 'paint_color', 'mirror_color')}
        manifest['atlas_version'] = snapshot.get('atlas_version', 'unspecified')
        manifest.update(schema_version=2, coordinate_units='um', axis_order=['AP', 'DV', 'ML'], coordinate_origin='BrainGlobe atlas origin', created_utc=datetime.now(timezone.utc).isoformat(), regions=[], cells_file=None)
        for region in snapshot['regions']:
            acronym = region['area']
            # Structure acronyms are data, never path components supplied unchecked.
            safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in acronym)
            mesh = trimesh.Trimesh(vertices=region['vertices'], faces=region['faces'], process=False)
            ids = np.asarray(region['painted_faces'], dtype=np.int64)
            item = {k: region[k] for k in ('area','name','structure_id','color','visible')}
            item['n_painted_faces'] = len(ids)
            geometry_hash = hashlib.sha256()
            geometry_hash.update(np.asarray(region['vertices'], dtype='<f8').tobytes())
            geometry_hash.update(np.asarray(region['faces'], dtype='<i8').tobytes())
            item['mesh_geometry_sha256'] = geometry_hash.hexdigest()
            if not active_only:
                name = f'{safe}_full_mesh.ply'
                mesh.export(staging / name)
                item['full_mesh_file'] = name
            if len(ids):
                roi = trimesh.Trimesh(vertices=region['vertices'], faces=region['faces'][ids], process=False)
                roi.remove_unreferenced_vertices()
                name = f'{safe}_painted_roi.ply'
                roi.export(staging / name)
                faces_name = f'{safe}_painted_face_ids.csv'
                with (staging / faces_name).open('w', newline='', encoding='utf-8') as handle:
                    writer = csv.writer(handle)
                    writer.writerow(['area','face_id','center_x_um','center_y_um','center_z_um'])
                    for face_id, xyz in zip(ids, region['centroids'][ids]):
                        writer.writerow([acronym, int(face_id), *xyz])
                metadata = {k: manifest[k] for k in ('atlas','atlas_resolution_um','atlas_shape','paint_color','mirror_color','coordinate_units','axis_order','coordinate_origin')}
                metadata.update(atlas_version=manifest['atlas_version'], mesh_geometry_sha256=item['mesh_geometry_sha256'], area=acronym, region_name=region['name'], structure_id=region['structure_id'], n_painted_faces=len(ids), ply_file=name, face_ids_file=faces_name, region_color=region['color'])
                metadata_name = f'{safe}_metadata.json'
                (staging / metadata_name).write_text(json.dumps(metadata, indent=2), encoding='utf-8')
                item.update(painted_roi_file=name, painted_face_ids_file=faces_name, metadata_file=metadata_name)
            manifest['regions'].append(item)
        if snapshot.get('cells') is not None and not active_only:
            cells = snapshot['cells']
            frame = cells['dataframe'].copy()
            for i, axis in enumerate('xyz'):
                frame[f'app_{axis}_um'] = cells['xyz'][:, i]
            frame['app_selected'] = cells['selection']
            frame.to_csv(staging / 'imported_cells_atlas_coordinates.csv', index=False)
            manifest.update(cells_file='imported_cells_atlas_coordinates.csv', cell_coordinate_mode=cells['mode'], cell_label_column=cells['label'], cell_color_column=cells['color'], selected_cell_count=int(cells['selection'].sum()))
        (staging / 'scene_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        staging.rename(final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return str(final)
