"""Corrections v54 of main.tex (on top of 64804f8): text only, no new runs.

Every replacement fixes a sentence that does not match a table of the paper, another section, the code or
the CSVs of simulator/output/paper. The reason and the source of each one are in correcciones_v54.md
(same numbering). Each old string must occur exactly once in main.tex; CRLF line endings are preserved.

usage (from the repository root, on branch correcciones-v53 at 64804f8 or later):
    python docs/paper-cmdp/apply_correcciones_v54.py --check     # dry run: verifies every old string, writes nothing
    python docs/paper-cmdp/apply_correcciones_v54.py             # applies and keeps main.before_v54.tex as backup
    python docs/paper-cmdp/apply_correcciones_v54.py --opcionales   # also applies OPC1-OPC2, only if Daniel and David approve them
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, 'paper', 'main.tex')
BACKUP = os.path.join(HERE, 'paper', 'main.before_v54.tex')

R = [
    # ---- C1-C7: introduction and Section 7 against the tables -------------------------------------------
    ('C1', r'''a managerial trade-off of a point of coverage and one to two minutes of lateness against ten points of Gini.''',
           r'''a managerial trade-off of a point of coverage and about a minute of lateness against five to ten points of Gini.'''),
    ('C2', r'''is a managerial trade-off of a point of coverage and one to two minutes of lateness against five to ten points of Gini.''',
           r'''is a managerial trade-off of a point of coverage and about a minute of lateness (1.0 manual, 0.7 auto-accept) against five to ten points of Gini.'''),
    ('C3a', r'''and in lateness ($0.5$--$1.8$ minutes under manual acceptance, $0.2$--$1.1$ under auto-accept).''',
            r'''and in lateness ($0.5$--$1.8$ minutes under manual acceptance and $0.2$--$1.1$ under auto-accept against the six order-centric policies).'''),
    ('C3b', r'''of $0.5$--$1.8$ minutes of lateness ($0.2$--$1.1$ under auto-accept),''',
            r'''of $0.5$--$1.8$ minutes of lateness against the six order-centric policies ($0.2$--$1.1$ under auto-accept),'''),
    ('C4', r'''the $\alpha$ of \textbf{MIP-Fair} is inert because coverage has priority in every round;''',
           r'''the $\alpha$ of \textbf{MIP-Fair} is inert because, with coverage first and only $k = 8$ candidates per route, the coverage-optimal assignments of a round leave the Gini block almost nothing to choose;'''),
    ('C5', r'''\textbf{Greedy} and the two \textbf{BRKGA-Fair} variants run on it meet $\alpha = 0.30$ on most days,''',
           r'''\textbf{Greedy} and the two \textbf{BRKGA-Fair} variants run on it end the day at a mean Gini coefficient of $0.21$--$0.25$, below $\alpha = 0.30$ (Table~\ref{tab:review_thin}),'''),
    ('C6', r'''the order-centric policies reach its upper bound on most days only with the widest candidate set,''',
           r'''the order-centric policies reach its upper bound on most days under both regimes only with the widest candidate set ($k_d = 50$; $k_d = 25$ suffices under auto-accept),'''),
    ('C7a', r'''and $1.7$ points less under manual acceptance,''',
            r'''and $1.6$ points less than \textbf{BRKGA} under manual acceptance,'''),
    ('C7b', r'''\textbf{Pay-BRKGA} loses $1.7$ points more than \textbf{BRKGA}''',
            r'''\textbf{Pay-BRKGA} loses $1.6$ points more than \textbf{BRKGA}'''),
    # ---- C8-C10: solver limit, sources of Table 3, Table C.16 ----------------------------------------------
    ('C8a', r'''Mixed-integer programmes are solved with a limit of 10 seconds per round,''',
            r'''Mixed-integer programmes are solved with a limit of 10 seconds per stage, each lexicographic stage being a separate solve,'''),
    ('C8b', r'''and a 10-second limit per round;''',
            r'''and a 10-second limit per stage;'''),
    ('C9a', r'''the regime and $\alpha$ columns come from X1, the $\theta$ columns from X2,''',
            r'''the regime and $\alpha$ columns come from X1 (from X3 for the rows with $k_d = 25$), the $\theta$ columns from X2,'''),
    ('C9b', r'''on the seeds of its experiment (ten in X1, five in X2), and a dash marks a parameter the policy does not have or a configuration not run in X2.''',
            r'''on the seeds of its experiment (ten in X1, five in X2 and X3), and a dash marks a parameter the policy does not have or a level not run in X2 or X3.'''),
    ('C9c', r'''Regime and $\alpha$ from X1 (ten seeds); $\theta$ from X2 (five seeds, the five configurations of the threshold experiment); a dash marks a parameter the policy does not have or a configuration not run in X2.''',
            r'''Regime and $\alpha$ from X1 (ten seeds) and, for the rows with $k_d = 25$, from X3 (five seeds); $\theta$ from X2 (five seeds, the five configurations of the threshold experiment); a dash marks a parameter the policy does not have or a level not run in X2 or X3.'''),
    ('C10', r'''none: coverage flat within 0.3 points along $\alpha$ and along $k_d$''',
            r'''none: coverage flat within 0.3 points along $\alpha$ and within 0.7 along $k_d$'''),
    # ---- C11-C18: Section 6.1 and 6.3 against Tables C.5, C.6 and C.11 ------------------------------------
    ('C11', r'''The second-generation variants that correct this are evaluated after Table~\ref{tab:scope}.''',
            r'''The second-generation variants that correct this are evaluated in the next paragraph.'''),
    ('C12', r'''and $0.401$--$0.416$ under auto-accept,''',
            r'''and $0.401$--$0.415$ under auto-accept,'''),
    ('C13', r'''Every paired interval excludes zero and no (instance, seed) pair is worse than its parent at $k_d = 25$ (Table~\ref{tab:gen2_paired}).''',
            r'''Every paired interval excludes zero (Table~\ref{tab:gen2_paired}), and no (instance, seed) pair is worse than its parent at $k_d = 25$.'''),
    ('C14', r'''(9--12\% of the gap over the two regimes)''',
            r'''(9--11\% of the gap over the two regimes)'''),
    ('C15', r'''lateness rises by $0.1$--$0.3$ minutes,''',
            r'''lateness rises by at most $0.3$ minutes ($0.1$ under auto-accept),'''),
    ('C16', r'''and at $0.50$ the proposed policies reach 35--50\%.''',
            r'''and at $0.50$ the proposed policies reach 37--46\%.'''),
    ('C17', r'''\textbf{Pay-BRKGA} moves least ($0.02$).''',
            r'''\textbf{Pay-BRKGA} moves least ($0.02$--$0.03$).'''),
    ('C18', r'''\textbf{Greedy} leaves 3\% of the eligible couriers idle and its interquartile range''',
            r'''In this pooled one-seed sample, \textbf{Greedy} leaves 3\% of the eligible couriers idle and its interquartile range'''),
    # ---- C19-C27: Sections 3 to 5 against the code -----------------------------------------------------------
    ('C19', r'''status $\sigma_c(t) \in \{\text{idle, picking-up, in-transit, dropping-off, offline}\}$ and time to next availability $\eta_c(t)$,''',
            r'''status $\sigma_c(t) \in \{\text{idle, picking-up, in-transit, dropping-off, offline}\}$, time to next availability $\eta_c(t)$ and on- and off-times $e_c$ and $l_c$ (the declared shift),'''),
    ('C20a', r'''the connected time $\conn_c(t) = t - e_c$ follows from the on-time recorded in $\mathcal{L}_t$,''',
             r'''the connected time $\conn_c(t) = \min(t, l_c) - e_c$ (in hours, $t$ read as clock time) follows from the declared shift recorded in $\mathcal{L}_t$,'''),
    ('C20b', r'''$\conn_c(t)$, $w_c(t)$ & connected time since log-in;''',
             r'''$\conn_c(t)$, $w_c(t)$ & connected time since log-in, $\min(t, l_c) - e_c$;'''),
    ('C21', r'''\lambda \sum_{(c,s) \in x_t} z_{c,s}\, \pay(c, s, \rho_{c,s}),''',
            r'''\lambda \sum_{(c,s) \in x_t} \pay(c, s, \rho_{c,s}),'''),
    ('C22', r'''be the hourly earnings of courier $c$ at the end of the day, zero if it delivered nothing.''',
            r'''be the hourly earnings of courier $c$ at the end of the day, zero if it has earned nothing.'''),
    ('C24', r'''\STATE{run the BRKGA for $G$ generations with decoder of Algorithm~\ref{alg:decoder} and score of Eq.~\eqref{eqn:brkgafair} (fitness of Eq.~\eqref{eqn:paybrkga} for \textbf{Pay-BRKGA})}''',
            r'''\STATE{run the BRKGA for $G = 10$ generations with decoder of Algorithm~\ref{alg:decoder} and score of Eq.~\eqref{eqn:brkgafair} ($\gamma = 0$, and fitness of Eq.~\eqref{eqn:paybrkga}, for \textbf{Pay-BRKGA})}'''),
    ('C25', r'''\STATE{compute from $\Hist_t$ (Eq.~\eqref{eqn:history}) the hourly earnings so far $w_c(t)$ of every connected courier}''',
            r'''\STATE{compute from $\Hist_t$ (Eq.~\eqref{eqn:history}) the value $w_c(t)$ of every connected courier under the basis in use (earnings per busy hour in the first generation, per connected hour in the second)}'''),
    ('C26a', r'''The equity-first variant is reported as an ablation.''',
             r'''The equity-first variant is reported as an ablation, and so is a coverage slack $\varepsilon$ that lets the later stages give up a fraction $\varepsilon$ of the stage-1 coverage ($\varepsilon = 0$ otherwise).'''),
    ('C26b', r'''Stage 1 maximises $\sum_o y_o$; stage 2 fixes that value and minimises $v$;''',
             r'''Stage 1 maximises $\sum_o y_o$; stage 2 keeps $\sum_o y_o \ge (1 - \varepsilon) \sum_o y_o^*$, with $y^*$ the stage-1 optimum, and minimises $v$;'''),
    ('C26c', r'''$v$, $W_{\text{ref}}$, $d_{ij}$ & Gini excess, its scale and the pairwise differences of \textbf{MIP-Fair} \\''',
             r'''$v$, $W_{\text{ref}}$, $d_{ij}$, $\varepsilon$ & Gini excess, its scale, the pairwise differences and the coverage slack of \textbf{MIP-Fair} \\'''),
    ('C27', r'''The $\alpha$ grid is centred on the inequality band of Section~\ref{sec:Problem_description}.''',
            r'''The $\alpha$ grid is placed around the survey anchors of Section~\ref{sec:Problem_description} (0.28 and 0.41).'''),
    # ---- C28-C35: Appendices B and C ---------------------------------------------------------------------------
    ('C28a', r'''are covered by unit tests against exhaustive enumeration on a test instance of three couriers and four orders; \ref{sec:App_verification} lists what each test checks.''',
             r'''are covered by unit tests against exhaustive enumeration on a test instance of three couriers and four orders, and the block linearisation against the all-pairs model on 117 real rounds (\ref{sec:App_verification}).'''),
    ('C28b', r'''\subsection{Verification against enumeration}''',
             r'''\subsection{Verification against enumeration and the all-pairs model}'''),
    ('C29', r'''and $h_B = (0, 0, 30)$,''',
            r'''and $h_B = (0, 0, 0)$,'''),
    ('C30', r'''and raises coverage by $0.007$ at eight times the CPU time''',
            r'''and raises coverage by $0.008$ at eight times the CPU time'''),
    ('C31', r'''the prefilter moves it by $0.054$--$0.131$, with every interval excluding zero''',
            r'''the prefilter moves it by $0.054$--$0.131$ for \textbf{BRKGA-Fair} and \textbf{MIP-Fair} and by $0.021$--$0.027$ for \textbf{Pay-BRKGA}, with every interval excluding zero'''),
    ('C32', r'''paired differences of the end-of-day Gini coefficient, coverage and mean lateness with 95\% intervals ($\pm 1.96$ SE over the pairs),''',
            r'''paired differences of the end-of-day Gini coefficient and coverage with 95\% intervals ($\pm 1.96$ SE over the pairs) and of mean lateness,'''),
    ('C33', r'''(98 minutes per run''',
            r'''(98.7 minutes per run'''),
    ('C34', r'''with as many pairs worse as better; this is the first-generation counterpart of the $\varepsilon$ result in Table~\ref{tab:gen2},''',
            r'''with 25--28 pairs worse and 25--37 better out of 120; this is the first-generation counterpart of the $\varepsilon$ result in Table~\ref{tab:gen2_paired},'''),
    ('C35', r'''and the active-courier Gini from $0.460$ to $0.413$.''',
            r'''and the active-courier Gini from $0.460$ to $0.413$ on the same 115 pairs.'''),
]

# C23: equation ranges typeset with a spaced hyphen ("Eqs. (8) - (10)") -> en dash, every occurrence
RANGE_OLD, RANGE_NEW, RANGE_N = r'''} - \eqref{''', r'''}--\eqref{''', 5


# Optional sentences, pending the authors' decision (D1 and D2 of correcciones_v54.md); applied only with --opcionales
OPTIONAL = [
    ('OPC1', r'''and logit acceptance on pay per kilometre under manual and auto-accept regimes.''',
             r'''and logit acceptance on pay per kilometre, estimated from field interviews and a survey, under manual and auto-accept regimes.'''),
    ('OPC2', r'''but the slope interval was not swept and the parameters are grade C.''',
             r'''but the slope interval was not swept and the parameters are grade C. The operating point $\alpha^* = 0.40$ rests on the five seeds of X3 and was not rerun in X2, so its sensitivity to the threshold is not measured.'''),
]


def main():
    global R
    check = '--check' in sys.argv
    if '--opcionales' in sys.argv:
        R = R + OPTIONAL
    s = open(PATH, 'rb').read().decode('utf-8')
    bad = [(k, s.count(old)) for k, old, new in R + OPTIONAL if s.count(old) != 1]
    n_range = s.count(RANGE_OLD)
    if n_range != RANGE_N:
        bad.append(('C23', n_range))
    if bad:
        for k, n in bad:
            print(f'ABORT {k}: {n} matches (expected {RANGE_N if k == "C23" else 1})')
        sys.exit(1)
    if check:
        print(f'OK: {len(R)} replacements and {RANGE_N} equation ranges match exactly; nothing written (--check)')
        return
    shutil.copyfile(PATH, BACKUP)
    for k, old, new in R:
        s = s.replace(old, new)
    s = s.replace(RANGE_OLD, RANGE_NEW)
    open(PATH, 'wb').write(s.encode('utf-8'))
    print(f'{len(R)} replacements and {RANGE_N} equation ranges applied; backup at {BACKUP}')


if __name__ == '__main__':
    main()
