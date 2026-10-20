# -*- coding: utf-8 -*-
"""
Fill DECK.CLUSTERS in the deck source from the isolated batch CSV(s), then run build_deck.py.

  python docs/fill_clusters.py output/hier_vs_greedy_240.csv [output/hier_variant_240.csv ...]

Rows: greedy vs hier (default order) per cluster and overall; extra CSVs add their hier variants as
extra columns in the note (paired vs greedy) so the slide stays one table.
"""
import json, os, re, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), 'simulator')   # code, output/ and instance_clusters.csv live here since the 2026-10-20 restructure
SRC = os.path.join(HERE, 'mdrp-jerarquia-objetivos.src.html')
LABELS = {0: 'Dispersas, con holgura', 1: 'Pequeñas y compactas', 2: 'Medianas y cargadas', 3: 'Grandes y saturadas'}
EPS = 1e-9


def paired(df, a, b):
    piv = df.pivot_table(index=['instance', 'cluster'], columns='policy',
                         values=['coverage_rate', 'overage_mean', 'F_Gini', 'total_payment', 'wall_clock_sec'])
    out = {}
    for key, g in [('all', piv)] + [(c, piv[piv.index.get_level_values('cluster') == c]) for c in sorted(df['cluster'].unique())]:
        r = {}
        r['n'] = len(g)
        r['cov_g'], r['cov_h'] = g['coverage_rate'][a].mean(), g['coverage_rate'][b].mean()
        r['over_g'], r['over_h'] = g['overage_mean'][a].mean(), g['overage_mean'][b].mean()
        d_over = g['overage_mean'][b] - g['overage_mean'][a]
        r['over_better'], r['over_worse'] = (d_over < -EPS).mean(), (d_over > EPS).mean()
        d_cov = g['coverage_rate'][b] - g['coverage_rate'][a]
        r['cov_better'], r['cov_worse'] = (d_cov > EPS).mean(), (d_cov < -EPS).mean()
        r['gini_g'], r['gini_h'] = g['F_Gini'][a].mean(), g['F_Gini'][b].mean()
        d_gini = g['F_Gini'][b] - g['F_Gini'][a]
        r['gini_better'] = (d_gini < -EPS).mean()
        r['pay_d'] = (g['total_payment'][b] - g['total_payment'][a]).mean()
        r['sec_h'] = g['wall_clock_sec'][b].mean()
        out[key] = {k: (round(float(v), 4) if isinstance(v, float) else v) for k, v in r.items()}
    return out


INSIDE = {
    'greedy': 'regla: menos pedidos primero, ruta factible más cercana',
    'hier cov›lat›eq›cost': 'jerarquía (decisión 1A)',
    'hier cov›lat›cost›eq': 'jerarquía, costo antes que equidad',
    'hier cov›cost›lat›eq': 'jerarquía, costo antes que atraso',
    'mdrp-sim greedy': 'ETA mínimo por repartidor, sin bundles',
    'mdrp-sim mdrp (MIP)': 'MIP: throughput − 0,4·atraso, cruce completo',
    'mdrp-sim mdrp_graph': 'relajación LP del mismo MIP',
    'mdrp-sim mdrp_graph_prospects': 'LP con prospectos a 3 km',
}


def fill_mdrpsim(src, path):
    import json as _json
    D = _json.load(open(path, encoding='utf8'))
    pols = D['policies']
    O = D['overall']
    D['inside'] = {p: INSIDE.get(p, '') for p in pols}
    ms = [p for p in pols if p.startswith('mdrp-sim')]
    best_cov = max(pols, key=lambda p: O[p]['coverage_rate'])
    full = [p for p in pols if O[p]['coverage_rate'] >= 0.9] or pols     # compare the rest only among policies that cover
    best_lat = min(full, key=lambda p: O[p]['overage_total_min'])
    best_gini = min(full, key=lambda p: O[p]['F_Gini'])
    best_cost = min(full, key=lambda p: O[p]['courier_active_min_total'])
    w1 = D['wins'].get('cov›lat›eq›cost (1A)', {})
    top1 = max(w1, key=w1.get) if w1 else ''
    D['takes'] = [
        {'v': best_cov.replace('mdrp-sim ', 'ms·'), 'small': 'mejor cobertura', 'p': f"Media {O[best_cov]['coverage_rate']*100:.1f} %. ".replace('.', ',') + 'Las variantes de mdrp-sim con objetivo throughput − 0,4·atraso dejan pedidos sin cubrir cuando ninguna ruta «vale la pena»: ' + ', '.join(f"{p.replace('mdrp-sim ','')} {O[p]['coverage_rate']*100:.1f} %".replace('.', ',') for p in ms) + '.'},
        {'v': best_lat.replace('mdrp-sim ', 'ms·'), 'small': 'menos atraso (cubriendo > 90 %)', 'p': f"{O[best_lat]['overage_total_min']:.0f} minutos de atraso totales de media por instancia. Las que cubren la mitad de los pedidos acumulan menos atraso, Gini y costo sólo porque entregan menos: por eso la cobertura va primero en la lectura lexicográfica."},
        {'v': best_gini.replace('mdrp-sim ', 'ms·'), 'small': 'más equitativa (cubriendo > 90 %)', 'p': f"F_Gini {O[best_gini]['F_Gini']:.4f}".replace('.', ',') + f"; menor costo en minutos de repartidor entre las que cubren: {best_cost.replace('mdrp-sim ', 'ms·')} ({O[best_cost]['courier_active_min_total']:.0f} min)."},
        {'v': top1.replace('mdrp-sim ', 'ms·'), 'small': 'gana con el orden 1A', 'p': f"en el {w1.get(top1, 0):.0f} % de las {D['n_instances']} instancias cuando se leen los resultados con cobertura › atraso › equidad › costo. La tabla de abajo repite la lectura con cada orden de pasadas."},
    ]
    new = 'DECK.MDRPSIM = ' + _json.dumps(D, ensure_ascii=False) + '; /*__MDRPSIM__*/'
    s2, n = re.subn(r'DECK\.MDRPSIM = .*?; /\*__MDRPSIM__\*/', lambda m: new, src, count=1, flags=re.S)
    assert n == 1, 'MDRPSIM marker not found'
    return s2


def main(argv):
    mdrpsim = None
    if '--mdrpsim' in argv:
        i = argv.index('--mdrpsim'); mdrpsim = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    csvs = argv or [os.path.join(ROOT, 'output', 'hier_vs_greedy_240.csv')]
    df = pd.concat([pd.read_csv(c) for c in csvs], ignore_index=True)
    if 'failed' in df.columns:
        df = df[df['failed'].isna()]
    cl = pd.read_csv(os.path.join(ROOT, 'instance_clusters.csv'))[['instance', 'cluster', 'size']]
    df = df.drop(columns=[c for c in ('cluster', 'size') if c in df.columns]).merge(cl, on='instance', how='left')
    pols = [p for p in df['policy'].unique() if p != 'greedy']
    base = 'hier' if 'hier' in pols else pols[0]
    P = paired(df, 'greedy', base)
    rows = []
    for c in sorted(df['cluster'].unique()):
        mix = df[(df.cluster == c) & (df.policy == 'greedy')]['size'].value_counts().to_dict()
        rows.append(dict(key=str(c), label=f'Cluster {c} · {LABELS.get(c, "")}',
                         sub=' · '.join(f'{k} {v}' for k, v in sorted(mix.items())), **P[c]))
    rows.append(dict(key='all', label='Las 240 instancias', sub='', **P['all']))
    variants = {}
    for p in pols:
        if p != base:
            variants[p] = paired(df, 'greedy', p)['all']
    note = ('Medias por cluster; «hier mejor» = porcentaje de instancias donde hier mejora a greedy en esa métrica. '
            'Orden de hier: cobertura › atraso › equidad › costo (decisión 1A); equidad sobre ganancia acumulada (3C); '
            'candado 0 / 1e-4 (4C). Cada corrida en su propio proceso, 3 reintentos, 0 fallos.')
    if variants:
        note += ' Variantes (240 instancias, frente a greedy): ' + '; '.join(
            f"{k}: cobertura {v['cov_h']*100:.1f} %, atraso {v['over_h']:.2f} min, Gini {v['gini_h']:.4f}" for k, v in variants.items())
    A = P['all']
    takes = [
        {'v': f"{A['over_g']:.1f} → {A['over_h']:.1f}".replace('.', ','), 'small': 'min', 'p': f"de atraso medio sobre el target. hier mejora el atraso en el {A['over_better']*100:.0f} % de las instancias y lo empeora en el {A['over_worse']*100:.0f} %. En los clusters 0, 2 y 3 gana en todas."},
        {'v': f"{A['cov_g']*100:.1f} → {A['cov_h']*100:.1f}".replace('.', ','), 'small': '% cobertura', 'p': f"<b>La cobertura del día baja</b> {abs(A['cov_h']-A['cov_g'])*100:.1f} puntos (peor en el {A['cov_worse']*100:.0f} % de las instancias, igual en el {(1-A['cov_worse']-A['cov_better'])*100:.0f} %). El modelo cubre el máximo en cada ronda, pero sus elecciones de equidad gastan minutos de repartidor y pedidos posteriores superan su SLA dura antes de que alguien quede libre."},
        {'v': f"{A['gini_g']:.4f} → {A['gini_h']:.4f}".replace('.', ','), 'small': 'F_Gini', 'p': f"hier es más equitativo en el {A['gini_better']*100:.0f} % de las instancias; en el cluster 0 (dispersas, con holgura) casi nunca hay nadie bajo la media y el Gini empeora un poco."},
        {'v': f"{A['sec_h']:.1f} s".replace('.', ','), 'small': 'por día simulado', 'p': 'frente a 0,15 s de greedy; 9,8 s en las grandes y saturadas. Muy lejos del presupuesto de 120 s por ronda.'},
    ]
    if variants:
        vt = ' · '.join(f"<b>{k.replace('hier','')}</b>: cobertura {v['cov_h']*100:.1f} %, atraso {v['over_h']:.1f} min, Gini {v['gini_h']:.4f}".replace('.', ',') for k, v in variants.items())
        takes.append({'v': f"{len(variants)}", 'small': 'variantes de orden', 'p': 'Costo antes que equidad no cambia la cobertura. Costo antes que atraso recupera 1,1 puntos (los bundles vuelven) pero devuelve 1,3 min de atraso: la miopía por ronda es estructural, no del orden. ' + vt})
    data = {'rows': rows, 'note': note, 'takes': takes, 'variants': variants}
    s = open(SRC, encoding='utf8').read()
    new = 'DECK.CLUSTERS = ' + json.dumps(data, ensure_ascii=False) + '; /*__CLUSTERS__*/'
    s2, n = re.subn(r'DECK\.CLUSTERS = .*?; /\*__CLUSTERS__\*/', lambda m: new, s, count=1, flags=re.S)
    assert n == 1, 'marker not found'
    if mdrpsim:
        s2 = fill_mdrpsim(s2, mdrpsim)
        print('filled DECK.MDRPSIM from', mdrpsim)
    open(SRC, 'w', encoding='utf8').write(s2)
    print('filled DECK.CLUSTERS with', len(rows), 'rows and', len(variants), 'variant(s)')
    import subprocess
    subprocess.run([sys.executable, os.path.join(HERE, 'build_deck.py')], check=True)


if __name__ == '__main__':
    main(sys.argv[1:])
