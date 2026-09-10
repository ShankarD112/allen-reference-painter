"""Compare indexed queries to the original scan on identical synthetic centroids."""
import json
import platform
import time
import numpy as np
from allen_reference_painter.spatial import FaceIndex

rng=np.random.default_rng(42)
centers=rng.uniform(0,13000,(300000,3))
queries=rng.uniform(0,13000,(100,3))
t=time.perf_counter()
index=FaceIndex(centers)
build_ms=(time.perf_counter()-t)*1000
samples={}
results={}
for name in ['full_scan','spatial_index']:
    timings=[]
    found=[]
    for q in queries:
        t=time.perf_counter()
        if name=='full_scan':
            d=np.linalg.norm(centers-q,axis=1)
            ids=set(np.flatnonzero(d<=150)) or {int(np.argmin(d))}
        else:
            ids=index.near(q,150)
        timings.append((time.perf_counter()-t)*1000)
        found.append(ids)
    samples[name]={'median_ms':float(np.median(timings)),'p95_ms':float(np.percentile(timings,95))}
    results[name]=found
assert results['full_scan']==results['spatial_index']
print(json.dumps({'scope':'brush query only, synthetic 300k centroids, 100 queries; not end-to-end FPS','python':platform.python_version(),'platform':platform.platform(),'index_build_ms':build_ms,'results':samples,'median_speedup':samples['full_scan']['median_ms']/samples['spatial_index']['median_ms'],'equivalence':'PASS'},indent=2))
