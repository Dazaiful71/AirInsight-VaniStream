#!/bin/bash
#SBATCH --job-name=airinsight-finetune
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=general
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --requeue
#
# Fine-tune the genre classifier on TRAIN-day SILVER labels (leakage-filtered), 5 seeds, one checkpoint folder per seed
# under models/finetune_silver/. Resumable: a seed with a DONE marker is skipped. Scoring on gold happens later with
# eval/genre_eval.py (only after the gold sheet is labelled).
#
#   mkdir -p logs
#   sbatch cluster/02_finetune_genre.sbatch                                      # real job (all 5 seeds)
#   sbatch --time=00:05:00 --job-name=airinsight-finetune-smoke cluster/02_finetune_genre.sbatch smoke   # 64 examples, 1 epoch, 1 seed
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
    python eval/finetune_genre.py --smoke
else
    python eval/finetune_genre.py
fi
echo "end=$(date -u +%FT%TZ)"
