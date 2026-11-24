"""X2k50 (2026-11-24): sensitivity of the alpha* = 0.40 operating point, BRKGA-Fair (w = 40, k_d = 50), to the behavioural
threshold. theta = 615 and 1,242 come from threshold.csv (method brkga_fair_w40_xk50, manual regime, seeds 1-5); theta = 903
is the supp.csv run of the same method, regime and seeds (E11). MIP-Fair k_d = 50 (mipfair_a030_xk50_e000) is reported too
if its threshold rows exist. Each theta != 903 is paired on (instance, seed) with theta = 903 (runs without a courier table are dropped);
theta = 903 uses all its runs, as analyze_x2.py does. The k_d = 25 variants are printed alongside for reference (theta = 903 from gen2.csv).

Prints per configuration and theta: n pairs, coverage (mean, relative % over 903, paired delta with 95 % CI), lateness
(overage_mean, paired delta), eligible Gini, compliance (% of pairs with eligible Gini <= alpha) for alpha in
{0.30, 0.35, 0.40, 0.45}. Only the manual regime exists: under auto-accept theta is never read.
Writes output/paper/x2_k50_summary.txt (table plus KEY = VALUE lines read by the section 6.4 patch script).

    python analyze_couriers.py output/paper/threshold.csv --out output/paper/threshold_couriers.csv
    python analyze_x2_k50.py
"""
import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'paper', '')
KEY = ['instance', 'seed']
ALPHAS = [0.30, 0.35, 0.40, 0.45]
THETAS = [615.0, 903.0, 1242.0]
# method -> table holding its theta = 903 manual rows
SRC903 = {'brkga_fair_w40_xk50': 'supp', 'mipfair_a030_xk50_e000': 'supp',
          'brkga_fair_w40_xk25': 'gen2', 'mipfair_a030_xk25_e000': 'gen2'}
TAG = {'brkga_fair_w40_xk50': 'BF50', 'mipfair_a030_xk50_e000': 'MF50',
       'brkga_fair_w40_xk25': 'BF25', 'mipfair_a030_xk25_e000': 'MF25'}


def load(name: str) -> pd.DataFrame:
    d = pd.read_csv(OUT + f'{name}.csv')
    cp = OUT + f'{name}_couriers.csv'
    if os.path.exists(cp):
        d = d.merge(pd.read_csv(cp)[['run_id', 'gini_elig_hourly']], on='run_id', how='left')
    else:
        d['gini_elig_hourly'] = np.nan
    return d[d.regime == 'manual']


def ci(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) < 2:
        return 'n/a'
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return f'{x.mean():+.3f} [{x.mean() - h:+.3f},{x.mean() + h:+.3f}]'


def main() -> None:
    x2 = load('threshold')
    src = {'supp': load('supp'), 'gen2': load('gen2')}
    rows, kv = [], {}
    for meth, sname in SRC903.items():
        per = {903.0: src[sname][src[sname].method == meth].set_index(KEY)}
        for th in (615.0, 1242.0):
            per[th] = x2[(x2.method == meth) & (x2.ppk_threshold == th)].set_index(KEY)
        if per[615.0].empty and per[1242.0].empty:
            print(f'{meth}: no threshold rows yet')
            continue
        # pairs: each theta != 903 is paired on (instance, seed) with theta = 903 (as analyze_x2.py); 903 uses all its runs
        ok = {th: per[th][per[th].gini_elig_hourly.notna()] for th in THETAS}
        missing = {int(th): len(per[th]) for th in THETAS}
        for th in THETAS:
            idx = ok[903.0].index if th == 903.0 else ok[th].index.intersection(ok[903.0].index)
            b = per[903.0].reindex(idx)
            d = per[th].reindex(idx)
            r = {'config': meth, 'theta': int(th), 'n pairs': len(idx), 'rows': missing[int(th)],
                 'coverage': round(d.coverage_rate.mean(), 4),
                 'cov rel %': round(100.0 * (d.coverage_rate.mean() / b.coverage_rate.mean() - 1.0), 1),
                 'dCov [CI]': ci(d.coverage_rate - b.coverage_rate) if th != 903 else '0',
                 'late min': round(d.overage_mean.mean(), 2),
                 'dLate [CI]': ci(d.overage_mean - b.overage_mean) if th != 903 else '0',
                 'Gini': round(d.gini_elig_hourly.mean(), 3),
                 'dGini [CI]': ci(d.gini_elig_hourly - b.gini_elig_hourly) if th != 903 else '0'}
            t = TAG[meth]
            kv[f'{t}_N_{int(th)}'] = len(idx)
            kv[f'{t}_COV_{int(th)}'] = f'{d.coverage_rate.mean():.4f}'
            kv[f'{t}_COVREL_{int(th)}'] = f"{r['cov rel %']:+.1f}"
            kv[f'{t}_LATE_{int(th)}'] = f'{d.overage_mean.mean():.2f}'
            kv[f'{t}_DLATE_{int(th)}'] = f'{(d.overage_mean - b.overage_mean).mean():+.2f}'
            kv[f'{t}_GINI_{int(th)}'] = f'{d.gini_elig_hourly.mean():.3f}'
            for a in ALPHAS:
                c = 100.0 * float((d.gini_elig_hourly <= a).mean())
                r[f'<={a:.2f} %'] = round(c, 0)
                kv[f'{t}_COMP{int(round(a * 100)):02d}_{int(th)}'] = f'{c:.0f}'
            rows.append(r)
    pd.set_option('display.width', 250)
    tab = pd.DataFrame(rows)
    head = ('X2k50: compliance (% of paired instance-seed runs with eligible Gini <= alpha), coverage and lateness by theta, '
            'manual regime (auto-accept does not read theta); theta = 903 from supp.csv (k_d = 50) / gen2.csv (k_d = 25)\n')
    txt = head + (tab.to_string(index=False) if len(tab) else '(no rows)') + '\n\n# KEY = VALUE (read by patch_main.py)\n' \
        + '\n'.join(f'{k} = {v}' for k, v in kv.items()) + '\n'
    print(txt)
    open(OUT + 'x2_k50_summary.txt', 'w', encoding='utf-8').write(txt)


if __name__ == '__main__':
    main()
