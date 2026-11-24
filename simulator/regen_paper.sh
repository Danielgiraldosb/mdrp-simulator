#!/bin/sh
# Regenerates every derived table, figure and analysis printout of the paper from the run tables in output/paper.
# Order matters: courier tables first, F8 before analyze_review (it reads F8_emissions_runs.csv).
set -e
cd "$(dirname "$0")"
O=output/paper
for s in main gen2 supp threshold review; do
  python analyze_couriers.py $O/$s.csv --out $O/${s}_couriers.csv > $O/${s}_couriers_all.txt 2>&1
done
python tables_paper.py $O/main.csv --couriers-table $O/main_couriers.csv \
  --extra-runs $O/review.csv --extra-methods greedy_arrival > $O/tables_stdout.txt 2>&1
python tables_paper.py $O/main.csv $O/gen2.csv --couriers-table $O/main_couriers.csv \
  --configs greedy,brkga_fair_w40,brkga_fair_w20_xk,brkga_fair_w40_xk25,mipfair_a030,mipfair_a030_xk_e000,mipfair_a030_xk25_e000,paybrkga_l05,paybrkga_l05_xk \
  --out-dir $O/tables/gen2 > $O/tables_gen2_stdout.txt 2>&1
# the k_d = 50 rows of tab:compliance (supplement of X3, same five seeds): tables/gen2_kd50/compliance.tex
python tables_paper.py $O/main.csv $O/gen2.csv --couriers-table $O/main_couriers.csv \
  --configs greedy,brkga_fair_w40,brkga_fair_w40_xk25,mipfair_a030,mipfair_a030_xk25_e000 \
  --extra-runs $O/supp.csv --extra-methods brkga_fair_w40_xk50,mipfair_a030_xk50_e000 \
  --out-dir $O/tables/gen2_kd50 > $O/tables_gen2_kd50_stdout.txt 2>&1
python analyze_gen2_final.py > $O/gen2_final.txt 2>&1
python analyze_supp.py > $O/supp_analysis.txt 2>&1
python analyze_x2.py > $O/x2_analysis.txt 2>&1
python analyze_x2_k50.py > $O/x2_k50_stdout.txt 2>&1   # writes $O/x2_k50_summary.txt (X2k50, BRKGA-Fair k_d = 50)
python figures_paper.py --fig f3f4 f5 f7 f8 --extra-csv $O/gen2.csv > $O/figures_stdout.txt 2>&1
python analyze_review.py > $O/review_tables_stdout.txt 2>&1
python analyze_review2.py > $O/review_analysis.txt 2>&1
python tables_extra.py --instances > $O/tables_extra_stdout.txt 2>&1
python diag_supply.py > $O/supply_stdout.txt 2>&1
python eligibility_thresholds.py > $O/eligibility_stdout.txt 2>&1   # needs output/paper/couriers/ (not in the repository)
python claims_text.py > $O/claims_v54.txt 2>&1
echo regenerated
