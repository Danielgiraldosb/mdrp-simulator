@echo off
cd /d C:\MDRP\simulator
set PYTHONIOENCODING=utf-8
echo == X2k50 threshold start %date% %time% >> output\paper\x2k50.stdout.txt
python -u batch_paper.py --experiment threshold --methods brkga_fair_w40_xk50 --workers 12 --timeout-min 150 >> output\paper\x2k50.stdout.txt 2>&1
echo == X2k50 threshold done %date% %time% >> output\paper\x2k50.stdout.txt
