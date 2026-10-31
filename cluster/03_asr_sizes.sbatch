#!/bin/bash
#SBATCH --job-name=airinsight-asr-sizes
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=general
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --requeue
#
# Transcribe the 5 WER bulletins with several Whisper sizes and cache the hypotheses in data/asr_hyp/<model>/.
# Resumable: a bulletin with a non-empty cached hypothesis is skipped. WER itself is computed afterwards by
# eval/asr_eval.py, which needs the hand-corrected references in data/gold/asr_refs/.
# The audio (data/sample_A/audio) must be copied to the cluster first. Downloading model weights needs internet on the
# compute node or a pre-filled Hugging Face cache (UNVERIFIED: ask the admins). medium / large-v3 speed on the A6000 is unmeasured.
#
#   mkdir -p logs
#   sbatch cluster/03_asr_sizes.sbatch                                            # tiny base medium large-v3
#   sbatch --time=00:05:00 --job-name=airinsight-asr-smoke cluster/03_asr_sizes.sbatch smoke   # one bulletin, tiny only
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
which ffmpeg || echo "WARNING: ffmpeg not found on this node"
if [ "${MODE}" = "smoke" ]; then
    python eval/asr_transcribe.py --smoke --models tiny
else
    python eval/asr_transcribe.py --models tiny base medium large-v3
fi
echo "end=$(date -u +%FT%TZ)"
