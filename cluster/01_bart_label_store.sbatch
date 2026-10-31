#!/bin/bash
#SBATCH --job-name=airinsight-bart-label
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=general
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --requeue
#
# BART zero-shot genre labelling of every segment in store_A (SILVER labels, written to data/silver_bart/labels.csv).
# Resumable: segments already in labels.csv are skipped, so a requeued or resubmitted job continues where it stopped.
# Never modifies store_A.
#
#   mkdir -p logs                                  # Slurm does not create the --output folder
#   sbatch cluster/01_bart_label_store.sbatch                                   # real job
#   sbatch --time=00:05:00 --job-name=airinsight-bart-smoke cluster/01_bart_label_store.sbatch smoke   # 5-minute test (200 segments)
#
# Resources follow the documented gpu_single template (1 GPU, 32 cores, 64 GB); compare with templates/gpu_single (UNVERIFIED).
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p logs
module load python/3.11.14
source "${AIRINSIGHT_ENV:-$HOME/airinsight_env}/bin/activate"
MODE="${1:-full}"
echo "job ${SLURM_JOB_ID:-local} mode=${MODE} host=$(hostname) start=$(date -u +%FT%TZ)"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv || echo "nvidia-smi not available"
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
if [ "${MODE}" = "smoke" ]; then
    python cluster/bart_label_store.py --smoke
else
    python cluster/bart_label_store.py
fi
echo "end=$(date -u +%FT%TZ)"
