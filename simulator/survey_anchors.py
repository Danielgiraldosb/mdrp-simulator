"""Survey anchors for the tolerated inequality alpha (criterion B, issue #15) and survey supply rates (P37).

Reads the raw courier survey (Bogota, May-June 2021, n = 135; not in the repository because it holds the
respondents' answers) and prints aggregates only:

  - replication of the published figures: Gini of daily income 0.391 outside the bonus ladder (V117) and
    0.257 inside it (V124); median income per connected hour 2,622.38 COP (V30 band midpoints over the
    weekly hours of the grid B67-B73 times 52/12)
  - the anchors on the basis of Eq. (gini), income per connected hour: daily income over the hours connected
    per working day (grid hours / days with at least one hour), with a 95% bootstrap interval
  - orders per connected hour outside (V115) and inside (V122) the ladder

    python survey_anchors.py "<path>/DATOS_JUNIO Junio 17 2021.xlsx"
"""
import sys

import numpy as np
import pandas as pd

MID_V30 = {1: 50_000, 2: 200_000, 3: 400_000, 4: 650_000, 5: 1_000_000, 6: 1_350_000, 7: 1_650_000,
           8: 1_950_000, 9: 2_250_000}                 # monthly income bands (COP), midpoints
DAYS = [f'B{d}' for d in range(67, 74)]                 # Monday .. Sunday
SLOTS = list('ABCDEFGHIJKLMNOPQRSTUVW') + ['1']         # 24 one-hour slots ('1' = 23-24 h); 'Y' = does not know


def gini(x):
    """Mean absolute difference over twice the mean, the form of Eq. (gini)."""
    x = np.asarray(x, dtype=float)
    return float(np.abs(x[:, None] - x[None, :]).sum() / (2 * len(x) ** 2 * x.mean()))


def main(path):
    df = pd.read_excel(path, sheet_name=0, dtype=str).replace({'#NULL!': np.nan, 'None': np.nan})
    num = lambda c: pd.to_numeric(df[c], errors='coerce')
    hours = pd.DataFrame({d: df[[f'{d}.{s}' for s in SLOTS]].apply(pd.to_numeric, errors='coerce')
                         .fillna(0).clip(0, 1).sum(axis=1) for d in DAYS})
    week_h = hours.sum(axis=1)
    day_h = week_h / (hours > 0).sum(axis=1).replace(0, np.nan)
    out_d, in_d = num('V117'), num('V124')               # daily income outside / inside the ladder
    print(f'respondents {len(df)}; weekly hours median {week_h.median():.0f}; hours per working day median {day_h.median():.1f}')
    print(f'daily income Gini: outside {gini(out_d.dropna()):.3f} (n {out_d.notna().sum()}, {int((out_d == 0).sum())} zeros), '
          f'inside {gini(in_d.dropna()):.3f} (n {in_d.notna().sum()})')
    ihr = num('V30').map(MID_V30) / (week_h * 52 / 12)
    print(f'monthly income per connected hour: median {ihr.median():.2f} COP, P25 {ihr.quantile(.25):.2f}, P75 {ihr.quantile(.75):.2f}')
    out_h, in_h = (out_d / day_h).dropna(), (in_d / day_h).dropna()
    rng = np.random.default_rng(1)
    for name, x in (('outside', out_h.to_numpy()), ('inside', in_h.to_numpy())):
        boots = [gini(x[rng.integers(0, len(x), len(x))]) for _ in range(2000)]
        print(f'ANCHOR {name} the ladder, income per connected hour: Gini {gini(x):.3f} '
              f'[{np.percentile(boots, 2.5):.3f}, {np.percentile(boots, 97.5):.3f}] (n {len(x)}), median {np.median(x):.0f} COP/h')
    print(f"orders per connected hour (medians): outside {(num('V115') / day_h).median():.2f}, "
          f"inside {(num('V122') / day_h).median():.2f}")


if __name__ == '__main__':
    main(sys.argv[1])
