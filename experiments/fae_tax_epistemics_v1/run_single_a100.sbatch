#!/usr/bin/env bash
#SBATCH --job-name=fae-tax-epistemics
#SBATCH --partition=a100
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=14
#SBATCH --mem=220G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:?PROJECT_DIR must name the staged Pixieology source directory}"
export PROVIDER="${PROVIDER:-slurm_paid}"
export POD_STARTED_EPOCH="${POD_STARTED_EPOCH:-$(date +%s)}"
exec bash "${PROJECT_DIR}/experiments/fae_tax_epistemics_v1/run_single_a100.sh"
