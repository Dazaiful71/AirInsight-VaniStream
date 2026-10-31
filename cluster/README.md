# cluster/ - sbatch scripts (NOT submitted; written but never run)

Written from the facts in ROADMAP section 5 (Slurm, partition `general`, `gpu_single` = 1 GPU, 32 cores, 64 GB, `--job-name` and `--output` set, test with `--time=00:05:00` first). I did not have the cluster's own `templates/gpu_single` file, so compare these headers with it before the first submission (UNVERIFIED).

| Script | What it runs | Resumable by | Smoke mode |
|---|---|---|---|
| `01_bart_label_store.sbatch` | `cluster/bart_label_store.py`: BART zero-shot silver labels for every `store_A` segment into `data/silver_bart/labels.csv` (store is read-only) | ids already in `labels.csv` are skipped | first 200 segments |
| `02_finetune_genre.sbatch` | `eval/finetune_genre.py`: 5 seeds, train-day silver labels, leakage-filtered, `models/finetune_silver/seed_<n>/` | `DONE` marker per seed | 64 examples, 1 epoch, 1 seed, separate folder |
| `03_asr_sizes.sbatch` | `eval/asr_transcribe.py`: hypotheses for tiny, base, medium, large-v3 into `data/asr_hyp/` | non-empty cached hypothesis skipped | 1 bulletin, tiny only |
| `04_scale_benchmark.sbatch` | `eval/scale_benchmark.py`: 10,000 SYNTHETIC segments; no GPU requested on purpose | skips if the result file exists | 1,000 segments |

## Order and usage

1. One-time: `module load python/3.11.14`, `uv venv ~/airinsight_env`, `source ~/airinsight_env/bin/activate`, `uv pip install -r requirements.txt jiwer pytest` (CUDA torch wheel needed for GPU jobs; UNVERIFIED which wheel the nodes need).
2. Copy the project, `data/sample_A/` (audio and text), `store_A/` and `data/gold/` to the cluster. Check `ffmpeg` and internet access from a compute node (UNVERIFIED; ask the admins).
3. `mkdir -p logs` (Slurm will not create the `--output` folder).
4. For each job first `sbatch --time=00:05:00 --job-name=<name>-smoke cluster/<script> smoke`, check the log, then submit without `smoke`. Monitor with `squeue -l` and `nvidia-smi`.
5. After 01 finishes the labels are in `data/silver_bart/labels.csv`; after 02 run `python eval/genre_eval.py` (needs a labelled gold sheet); after 03 run `python eval/asr_eval.py` (needs `data/gold/asr_refs/`).

Nothing here has been submitted, so queue time, run time, memory and whether the nodes can reach Hugging Face are all UNKNOWN.
