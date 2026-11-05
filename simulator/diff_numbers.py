"""Old -> new numbers from the tables and analysis printouts (instance-1 rerun), and where the old values appear in
the prose of main.tex (outside tabular environments). Prints candidate sentences to review; edits nothing."""
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:/MDRP/simulator/output/paper/'
B = P + 'backup_inst1_20261105/'
SCR = r'C:/Users/akavallo/AppData/Local/Temp/claude/C--MDRP/ee02e25a-3a7f-4dd7-9e24-1dd1a8c8cffc/scratchpad/'
FILES = [(B + 'tables/' + f, P + 'tables/' + f) for f in ('benchmark.tex', 'scope.tex', 'compliance.tex', 'city.tex', 'ablations.tex',
          'review_gen2.tex', 'review_metrics.tex', 'review_emissions.tex', 'review2_ilp.tex', 'review2_arrival.tex',
          'review2_thin.tex', 'threshold.txt', 'stats.txt')]
FILES += [(SCR + 'old_gen2/benchmark.tex', P + 'tables/gen2/benchmark.tex'), (SCR + 'old_gen2/compliance.tex', P + 'tables/gen2/compliance.tex')]
FILES += [(B + f, P + f) for f in ('gen2_final.txt', 'supp_analysis.txt', 'x2_analysis.txt', 'review_analysis.txt', 'main_couriers_all.txt')]
NUM = re.compile(r'[-+]?\d+(?:[.,]\d+)?')
pairs = {}
for a, b in FILES:
    try:
        A = open(a, encoding='utf-8').read().splitlines()
        Bl = open(b, encoding='utf-8').read().splitlines()
    except FileNotFoundError as e:
        print('missing', e.filename)
        continue
    for x, y in zip(A, Bl):
        nx, ny = NUM.findall(x), NUM.findall(y)
        if len(nx) != len(ny):
            continue
        for p, q in zip(nx, ny):
            p2, q2 = p.lstrip('+-'), q.lstrip('+-')
            if p2 != q2 and ('.' in p2) and len(p2) >= 3:
                pairs.setdefault(p2, set()).add(q2)
tex = open(r'C:/MDRP/docs/paper-cmdp/paper/main.tex', encoding='utf-8').read()
prose = re.sub(r'\\begin\{tabular\}.*?\\end\{tabular\}', lambda m: ' ' * len(m.group(0)), tex, flags=re.S)
lines = prose.split('\n')
hits = []
for old, news in sorted(pairs.items()):
    pat = re.compile(r'(?<![\d.])' + re.escape(old) + r'(?![\d])')
    for i, l in enumerate(lines):
        for m in pat.finditer(l):
            hits.append((i + 1, m.start(), old, '/'.join(sorted(news)), l[max(0, m.start() - 90):m.end() + 50]))
print(f'{len(pairs)} changed values; {len(hits)} occurrences in the prose')
for ln, pos, old, new, ctx in sorted(hits):
    print(f'L{ln} {old} -> {new} :: {ctx}')
