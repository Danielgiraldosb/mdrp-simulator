"""Row-by-row diff of the generated tables before and after the instance-1 rerun (2026-11-05)."""
import difflib
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
OLD = r'C:/MDRP/simulator/output/paper/backup_inst1_20261105/tables'
NEW = r'C:/MDRP/simulator/output/paper/tables'
EXTRA_OLD = r'C:/Users/akavallo/AppData/Local/Temp/claude/C--MDRP/ee02e25a-3a7f-4dd7-9e24-1dd1a8c8cffc/scratchpad'
PAIRS = [(f'{OLD}/{f}', f'{NEW}/{f}') for f in ('benchmark.tex', 'scope.tex', 'compliance.tex', 'city.tex', 'ablations.tex',
                                                'review_gen2.tex', 'review_metrics.tex', 'review_emissions.tex',
                                                'review2_ilp.tex', 'review2_arrival.tex', 'review2_thin.tex', 'threshold.txt')]
PAIRS += [(f'{EXTRA_OLD}/old_gen2/benchmark.tex', f'{NEW}/gen2/benchmark.tex'),
          (f'{EXTRA_OLD}/old_gen2/compliance.tex', f'{NEW}/gen2/compliance.tex'),
          (f'{EXTRA_OLD}/old_tables/sensitivity.tex', f'{NEW}/sensitivity.tex'),
          (f'{EXTRA_OLD}/old_tables/sensitivity_gini.tex', f'{NEW}/sensitivity_gini.tex')]
for a, b in PAIRS:
    A = open(a, encoding='utf-8').read().splitlines()
    B = open(b, encoding='utf-8').read().splitlines()
    ch = [(x, y) for x, y in zip(A, B) if x != y]
    print(f'##### {os.path.relpath(b, NEW)}: {len(ch)} of {len(B)} rows changed' + ('' if len(A) == len(B) else f' (rows {len(A)} -> {len(B)})'))
    for x, y in ch:
        xs, ys = x.split('&'), y.split('&')
        cells = [f'{i}:{p.strip()}->{q.strip()}' for i, (p, q) in enumerate(zip(xs, ys)) if p != q]
        print('   ', xs[0].strip()[:55], '|', '; '.join(cells)[:260])
