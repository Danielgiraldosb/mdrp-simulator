"""Preliminary read of X3 gen2 (partial): seed 1, instances complete for all gen2 methods, paired with
the first-generation runs of X1 (seed 1, same instances)."""
import sys
import numpy as np
import pandas as pd

OUT = r'C:/MDRP/simulator/output/paper/'
cols = ['run_id', 'gini_elig_hourly', 'gini_elig_active_hourly', 'share_active_elig', 'p25_elig_hourly']
main = pd.read_csv(OUT + 'main.csv').merge(pd.read_csv(OUT + 'main_couriers.csv')[cols], on='run_id')
gen2 = pd.read_csv(OUT + 'gen2.csv').merge(pd.read_csv(OUT + 'gen2_couriers.csv')[cols], on='run_id')
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
g = gen2[gen2.seed == seed]
n_methods = gen2.method.nunique()
full = g.groupby('instance')['method'].nunique()
full = full[full == n_methods].index.tolist()
# require both regimes
full = [i for i in full if g[g.instance == i].regime.nunique() == 2 and len(g[g.instance == i]) == 2 * n_methods]
print(f'gen2 rows {len(gen2)}; seed {seed}; instances complete: {len(full)} -> {sorted(full)}')
m = main[(main.seed == seed) & (main.instance.isin(full))]
g = g[g.instance.isin(full)]
first = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w20', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05']
met = ['coverage_rate', 'overage_mean', 'gini_elig_hourly', 'share_active_elig', 'p25_elig_hourly', 'wall_clock_sec']
pd.set_option('display.width', 220)
for reg in ('manual', 'autoaccept'):
    a = m[(m.regime == reg) & (m.method.isin(first))].groupby('method')[met].mean()
    b = g[g.regime == reg].groupby('method')[met].mean()
    t = pd.concat([a.loc[[x for x in first if x in a.index]], b])
    t['wall_clock_sec'] = (t['wall_clock_sec'] / 60).round(1)
    t = t.rename(columns={'wall_clock_sec': 'min/run'})
    print(f'\n== {reg}: mean over the {len(full)} complete instances, seed {seed} (first generation from X1) ==')
    print(t.round(3).to_string())
    # paired vs greedy and vs first-generation parent
    base = m[(m.regime == reg) & (m.method == 'greedy')].set_index('instance')
    rows = []
    parent = {'brkga_fair_w20_x': 'brkga_fair_w20', 'brkga_fair_w20_xk': 'brkga_fair_w20', 'brkga_fair_w40_xk25': 'brkga_fair_w40',
              'paybrkga_l05_xk': 'paybrkga_l05'}
    for meth in sorted(b.index):
        x = g[(g.regime == reg) & (g.method == meth)].set_index('instance').reindex(base.index)
        par = parent.get(meth, 'mipfair_a030')
        p = m[(m.regime == reg) & (m.method == par)].set_index('instance').reindex(base.index)
        d_g = (x.gini_elig_hourly - base.gini_elig_hourly)
        d_p = (x.gini_elig_hourly - p.gini_elig_hourly)
        d_c = (x.coverage_rate - p.coverage_rate)
        gap_closed = 1 - (x.gini_elig_hourly - base.gini_elig_hourly) / (p.gini_elig_hourly - base.gini_elig_hourly)
        rows.append({'method': meth, 'parent': par, 'dGini vs greedy': f'{d_g.mean():+.3f}',
                     'dGini vs parent': f'{d_p.mean():+.3f} [{d_p.min():+.3f},{d_p.max():+.3f}]',
                     'dCov vs parent': f'{d_c.mean():+.4f}', 'gap closed': f'{gap_closed.mean():.2f}',
                     'n inst with Gini<=0.40': int((x.gini_elig_hourly <= 0.40).sum())})
    print(pd.DataFrame(rows).to_string(index=False))
