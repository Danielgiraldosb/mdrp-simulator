"""Final read of X3 gen2 (1,920 runs, 8 configs x 24 zones x 2 regimes x 5 seeds), paired by (instance, seed,
regime) with the first-generation runs of X1 (same seeds 1-5). Prints, per regime: means over the 120 zone-days,
paired deltas vs greedy and vs the first-generation parent (mean, 95% CI of the paired mean), share of the
greedy->parent gap closed, coverage delta vs parent, number of zone-days meeting alpha, per-seed means (stability)
and the compliance curve of the k_d = 25 variants for alpha in 0.30..0.50 (Table 9).

    python analyze_gen2_final.py > output/paper/gen2_final.txt
"""
import numpy as np
import pandas as pd

OUT = r'C:/MDRP/simulator/output/paper/'
COLS = ['run_id', 'gini_elig_hourly', 'gini_elig_active_hourly', 'share_active_elig', 'p25_elig_hourly']
FIRST = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w20', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05']
PARENT = {'brkga_fair_w20_x': 'brkga_fair_w20', 'brkga_fair_w20_xk': 'brkga_fair_w20',
          'brkga_fair_w40_xk25': 'brkga_fair_w40', 'paybrkga_l05_xk': 'paybrkga_l05'}
MET = ['coverage_rate', 'overage_mean', 'gini_elig_hourly', 'gini_elig_active_hourly', 'share_active_elig',
       'p25_elig_hourly', 'wall_clock_sec']
KEY = ['instance', 'seed']


def ci(x: pd.Series) -> str:
    x = x.dropna()
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
    return f'{x.mean():+.3f} [{x.mean() - h:+.3f},{x.mean() + h:+.3f}]'


def main() -> None:
    main_df = pd.read_csv(OUT + 'main.csv').merge(pd.read_csv(OUT + 'main_couriers.csv')[COLS], on='run_id')
    gen2 = pd.read_csv(OUT + 'gen2.csv').merge(pd.read_csv(OUT + 'gen2_couriers.csv')[COLS], on='run_id')
    seeds = sorted(gen2.seed.unique())
    m = main_df[main_df.seed.isin(seeds)]
    print(f'gen2 rows {len(gen2)} ({gen2.method.nunique()} configs, {gen2.instance.nunique()} zones, seeds {seeds}, '
          f'{gen2.regime.nunique()} regimes)')
    pd.set_option('display.width', 250)
    for reg in ('manual', 'autoaccept'):
        a = m[(m.regime == reg) & (m.method.isin(FIRST))].groupby('method')[MET].mean()
        b = gen2[gen2.regime == reg].groupby('method')[MET].mean()
        t = pd.concat([a.loc[[x for x in FIRST if x in a.index]], b])
        t['wall_clock_sec'] = (t['wall_clock_sec'] / 60).round(1)
        t = t.rename(columns={'wall_clock_sec': 'min/run', 'gini_elig_hourly': 'F_Gini', 'gini_elig_active_hourly': 'F_Gini_act',
                              'share_active_elig': 'active', 'p25_elig_hourly': 'p25_hourly'})
        print(f'\n== {reg}: mean over {gen2[gen2.regime == reg].groupby("method").size().max()} zone-days '
              f'(first generation from X1, same seeds) ==')
        print(t.round(3).to_string())
        base = m[(m.regime == reg) & (m.method == 'greedy')].set_index(KEY)
        rows = []
        for meth in sorted(b.index):
            x = gen2[(gen2.regime == reg) & (gen2.method == meth)].set_index(KEY).reindex(base.index)
            par = PARENT.get(meth, 'mipfair_a030')
            p = m[(m.regime == reg) & (m.method == par)].set_index(KEY).reindex(base.index)
            d_g = x.gini_elig_hourly - base.gini_elig_hourly
            d_p = x.gini_elig_hourly - p.gini_elig_hourly
            d_c = x.coverage_rate - p.coverage_rate
            gap = 1 - (x.gini_elig_hourly - base.gini_elig_hourly) / (p.gini_elig_hourly - base.gini_elig_hourly)
            per_seed = x.groupby(level='seed')['gini_elig_hourly'].mean()
            rows.append({'method': meth, 'parent': par, 'dGini vs greedy': ci(d_g), 'dGini vs parent': ci(d_p),
                         'dCov vs parent': ci(d_c), 'gap closed': f'{gap.mean():.2f}',
                         'days<=0.40': f'{int((x.gini_elig_hourly <= 0.40).sum())}/{len(x)}',
                         'per-seed F_Gini': ' '.join(f'{v:.3f}' for v in per_seed.values),
                         'worse than parent': int((d_p > 0).sum())})
        print(pd.DataFrame(rows).to_string(index=False))
        # compliance curve (Table 9): share of zone-days with F_Gini <= alpha
        print(f'\n-- {reg}: share of zone-days with F_Gini <= alpha (eligible statistic) --')
        alphas = [0.30, 0.35, 0.40, 0.45, 0.50]
        comp = {}
        for meth in ['greedy', 'hier', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05']:
            s = m[(m.regime == reg) & (m.method == meth)].gini_elig_hourly
            comp[meth] = [f'{(s <= al).mean():.2f}' for al in alphas]
        for meth in ['brkga_fair_w40_xk25', 'mipfair_a030_xk25_e000', 'mipfair_a030_xk_e000', 'brkga_fair_w20_xk']:
            s = gen2[(gen2.regime == reg) & (gen2.method == meth)].gini_elig_hourly
            comp[meth] = [f'{(s <= al).mean():.2f}' for al in alphas]
        print(pd.DataFrame(comp, index=[f'alpha={al:.2f}' for al in alphas]).T.to_string())
        # by city, k_d = 25 variants vs parents and greedy
        print(f'\n-- {reg}: F_Gini by city (mean over zone-days) --')
        city_rows = {}
        for meth in ['greedy', 'brkga_fair_w40', 'mipfair_a030']:
            city_rows[meth] = m[(m.regime == reg) & (m.method == meth)].groupby('city').gini_elig_hourly.mean()
        for meth in ['brkga_fair_w40_xk25', 'mipfair_a030_xk25_e000']:
            city_rows[meth] = gen2[(gen2.regime == reg) & (gen2.method == meth)].groupby('city').gini_elig_hourly.mean()
        print(pd.DataFrame(city_rows).round(3).to_string())


if __name__ == '__main__':
    main()
