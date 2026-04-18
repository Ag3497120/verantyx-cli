#!/bin/bash
echo "Launching Parallel Grid Search Benchmarks..."

PYTHONPATH=src python3 bench_v7_parallel_runner.py --output "pure_cpu_test_w_0.9_0.5.jsonl" --syn-w 0.9 --hyp-w 0.5 --hol-w 0.3 > /dev/null 2>&1 &
PYTHONPATH=src python3 bench_v7_parallel_runner.py --output "pure_cpu_test_w_1.0_0.7.jsonl" --syn-w 1.0 --hyp-w 0.7 --hol-w 0.4 > /dev/null 2>&1 &
PYTHONPATH=src python3 bench_v7_parallel_runner.py --output "pure_cpu_test_w_0.8_0.2.jsonl" --syn-w 0.8 --hyp-w 0.2 --hol-w 0.1 > /dev/null 2>&1 &

echo "3 instances spawned in the background natively. Use 'pgrep -f bench_v7' to monitor."
