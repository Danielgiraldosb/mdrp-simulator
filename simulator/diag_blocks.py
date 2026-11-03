"""Review level 2 (2026-11-03): exactness of the block linearisation of MIP-Fair on real rounds.

Runs MIP-Fair (alpha = 0.30, first generation, k = 8) on a slice of a real day. In every round the same
candidate set and histories are solved twice, with the block split of the paper (fixed-fixed constant,
free-fixed linear, free-free variables) and with the all-pairs model (one d_ij per pair of the Gini population),
and the stage optima (coverage, Gini excess v) and solve times are recorded; the block decision drives the
simulation. Equal optima on every round is the empirical counterpart of the algebraic argument.

    python diag_blocks.py --instance Instancia_10 --from 11:00 --until 13:00
"""
import argparse
import os
import sys
import time

import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)

from batch_paper import DEFAULT_INSTANCES_DIR  # noqa: E402
from config import Config  # noqa: E402
from loader_real import load_real_instance  # noqa: E402
from mip_fair import MIPFairPolicy  # noqa: E402
from run import run_simulation  # noqa: E402


class TwinMIPFair(MIPFairPolicy):
    """Solves every round with both formulations; returns the block decision."""

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.compare = []

    def _solve(self, cands, histories, t, exposure=None):
        self.cfg.mipfair_pairs = 'all'
        t0 = time.perf_counter()
        try:
            super()._solve(cands, histories, t, exposure)
            rec_all = dict(self.rounds.pop())
            ok_all = True
        except Exception as exc:          # time limit without an optimum, or solver error
            rec_all, ok_all = {'v': float('nan'), 'coverage': float('nan'), 'err': str(exc)[:80]}, False
        t_all = time.perf_counter() - t0
        self.cfg.mipfair_pairs = 'blocks'
        t0 = time.perf_counter()
        out = super()._solve(cands, histories, t, exposure)
        t_blk = time.perf_counter() - t0
        rec = self.rounds[-1]
        n = rec['n_couriers']
        n_free = len({k[0] for k in cands})
        self.compare.append(dict(time=t, n_population=n, n_free=n_free, candidates=len(cands),
                                 coverage_blocks=rec['coverage'], coverage_all=rec_all.get('coverage'),
                                 v_blocks=rec['v'], v_all=rec_all.get('v'), ok_all=ok_all,
                                 pairs_all=n * (n - 1) // 2, pairs_blocks=n_free * (n_free - 1) // 2,
                                 sec_blocks=round(t_blk, 3), sec_all=round(t_all, 3)))
        return out


def hhmm(s: str) -> float:
    h, m = s.split(':')
    return int(h) * 60 + int(m)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--instance', default='Instancia_10')
    ap.add_argument('--from', dest='t_from', default='11:00')
    ap.add_argument('--until', dest='t_until', default='13:00')
    ap.add_argument('--time-limit', type=float, default=60.0, help='seconds per stage (both formulations)')
    ap.add_argument('--out', default=os.path.join(THIS_DIR, 'output', 'paper', 'blocks_check.csv'))
    a = ap.parse_args()
    f, u = hhmm(a.t_from), hhmm(a.t_until)
    cfg = Config(seed=1, sim_start_clock_min=f, sim_end=u - f, acceptance_mode='logit_ppk', accept_regime='manual',
                 accept_ppk_threshold=903.0, real_max_radius_km=3.0, real_circuity=1.3, ilp_solver='GUROBI',
                 ilp_time_limit_sec=a.time_limit, max_bundle_size=3, mipfair_alpha=0.30, mipfair_scope='all',
                 mipfair_priority='coverage', mipfair_basis='hourly', mipfair_cand_top_k=8)
    inst = load_real_instance(a.instance, DEFAULT_INSTANCES_DIR, cfg)
    pol = TwinMIPFair(cfg)
    run_simulation(cfg, inst, policy=pol, policy_name='mip_fair', verbose=False)
    df = pd.DataFrame(pol.compare)
    df.to_csv(a.out, index=False)
    ok = df[df.ok_all]
    dv = (ok.v_blocks - ok.v_all).abs()
    dc = (ok.coverage_blocks - ok.coverage_all).abs()
    print(f'{a.instance} {a.t_from}-{a.t_until}: {len(df)} rounds, {len(ok)} solved by both')
    print(f'  population per round {df.n_population.median():.0f} (max {df.n_population.max()}), free {df.n_free.median():.0f}')
    print(f'  pair variables: all-pairs median {df.pairs_all.median():.0f}, blocks median {df.pairs_blocks.median():.0f}')
    print(f'  max |coverage diff| {dc.max():.0f}; max |v diff| {dv.max():.2e}; rounds with v > 0: {(ok.v_blocks > 1e-9).sum()}')
    print(f'  solve s/round: blocks mean {df.sec_blocks.mean():.2f} max {df.sec_blocks.max():.2f}; '
          f'all-pairs mean {df.sec_all.mean():.2f} max {df.sec_all.max():.2f}')


if __name__ == '__main__':
    main()
