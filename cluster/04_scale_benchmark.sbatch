#!/bin/bash
#SBATCH --job-name=airinsight-scale
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=general
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --requeue
#
# 10,000-segment scale benchmark on SYNTHETIC vectors (index build, query latency with and without the SQL prefilter,
# novelty-gate time, peak memory). Resumable: skips if results/scale_benchmark_n10000_*.json already exists.
#
# This job deliberately does NOT request a GPU: flat FAISS search and the SQLite prefilter run on CPU, and the cluster's
# rule is GPUs only for the approved task. Resources otherwise follow the documented gpu_single template (32 cores, 64 GB).
# Add "#SBATCH --gres=gpu:1" only if you decide to benchmark GPU search (UNVERIFIED whether that would be approved).
#
#   mkdir -p logs
#   sbatch cluster/04_scale_benchmark.sbatch                                      # 10,000 segments, 200 queries
#   sbatch --time=00:05:00 --job-name=airinsight-scale-smoke cluster/04_scale_benchmark.sbatch smoke   # 1,000 segments
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p logs
module load python/3.11.14
source "${AIRINSIGHT_ENV:-$HOME/airinsight_env}/bin/activate"
MODE="${1:-full}"
echo "job ${SLURM_JOB_ID:-local} mode=${MODE} host=$(hostname) start=$(date -u +%FT%TZ)"
if [ "${MODE}" = "smoke" ]; then
    python eval/scale_benchmark.py --smoke
else
    python eval/scale_benchmark.py --n 10000
fi
echo "end=$(date -u +%FT%TZ)"
