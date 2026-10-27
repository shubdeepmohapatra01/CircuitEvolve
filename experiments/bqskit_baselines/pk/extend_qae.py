import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'stage1'))
from run_b4_best import cell
from multiprocessing import get_context
cells = [('qae/qae_13', e, K, s) for e in (1e-3, 1e-5) for K in (11, 12, 13, 14) for s in range(5)]
if __name__ == '__main__':
    with get_context('spawn').Pool(processes=12) as p:
        p.starmap(cell, cells, chunksize=1)
    print('done', flush=True)
