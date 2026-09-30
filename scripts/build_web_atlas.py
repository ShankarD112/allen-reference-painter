"""Package exact BrainGlobe meshes and annotation slices for static hosting.

Run with Python dependencies from pyproject.toml. No remeshing, simplification,
vertex processing, or face reordering. Atlas version is deliberately pinned.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path,default=Path('.atlas-cache'))
    parser.add_argument('--output',type=Path,default=Path('public/data'))
    parser.add_argument('--regions',nargs='*',help='Optional acronym subset; default all structures')
    args=parser.parse_args()
    from brainglobe_atlasapi import BrainGlobeAtlas
    args.cache.mkdir(parents=True,exist_ok=True)
    (args.cache/'config').mkdir(exist_ok=True)
    atlas=BrainGlobeAtlas('allen_mouse_25um',version='3.1',brainglobe_dir=args.cache.resolve(),config_dir=(args.cache/'config').resolve(),check_latest=False)
    out=args.output; (out/'meshes').mkdir(parents=True,exist_ok=True)
    structures=[]
    for sid,s in atlas.structures.items():
        rgb=s.get('rgb_triplet',[180,200,220])
        structures.append({'id':int(sid),'acronym':s['acronym'],'name':s['name'],'path':list(map(int,s['structure_id_path'])),'color':'#'+''.join(f'{int(c):02x}' for c in rgb)})
    chosen=[s for s in structures if not args.regions or s['acronym'] in args.regions or s['acronym']=='root']
    errors=[]
    def package(s):
        try:
            mesh=atlas.mesh_from_structure(s['id'])
            vertices=np.asarray(mesh.points,dtype='<f8');faces=np.asarray(mesh.get_cells_type('triangle'),dtype='<u4')
            if not len(vertices) or not len(faces):raise ValueError('Empty mesh')
            if not np.isfinite(vertices).all() or faces.max()>=len(vertices):raise ValueError('Invalid geometry')
            geometry=vertices.tobytes()+faces.astype('<i8').tobytes()
            payload=struct.pack('<II',len(vertices),len(faces))+vertices.tobytes()+faces.tobytes()
            file=f'meshes/{s["id"]}.bin.gz'
            (out/file).write_bytes(gzip.compress(payload,mtime=0))
            s.update(file=file,vertices=len(vertices),triangles=len(faces),mesh_geometry_sha256=hashlib.sha256(geometry).hexdigest())
            return s
        except Exception as exc:
            errors.append({'region':s['acronym'],'error':'No decodable mesh available from the pinned BrainGlobe atlas.'})
            return s
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i,_ in enumerate(pool.map(package,chosen)):
            if i%100==0:print(f'Packaged {i+1}/{len(chosen)} meshes',flush=True)
    print('Downloading original annotation volume',flush=True)
    annotation=np.asarray(atlas.annotation,dtype='<u4')
    for axis in (0,2):
        directory=out/'slices'/str(axis);directory.mkdir(parents=True,exist_ok=True)
        for i in range(annotation.shape[axis]):
            # Both orientations store DV rows: coronal columns=ML; sagittal columns=AP.
            section=annotation[i,:,:] if axis==0 else annotation[:,:,i].T
            (directory/f'{i}.bin.gz').write_bytes(gzip.compress(np.ascontiguousarray(section,dtype='<u4').tobytes(),mtime=0))
    manifest={'schema_version':1,'atlas':'allen_mouse_25um','atlas_version':'3.1','atlas_resolution_um':list(atlas.resolution),'atlas_shape':list(atlas.shape),'axis_order':['AP','DV','ML'],'coordinate_units':'um','coordinate_origin':'BrainGlobe atlas origin','orientation':'asr','citation':atlas.metadata['citation'],'source':'https://brainglobe.s3.us-west-2.amazonaws.com/atlas/','regions':structures,'slices':True,'mesh_errors':errors}
    (out/'atlas.json').write_text(json.dumps(manifest,separators=(',',':')))
    print(f'Finished: {len(chosen)-len(errors)} meshes; {len(errors)} unavailable. '+json.dumps(errors),flush=True)

if __name__=='__main__':main()
