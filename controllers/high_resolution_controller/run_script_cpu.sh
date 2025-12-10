#!/bin/bash
#SBATCH --job-name=highres1
#SBATCH --account=pc_pbd2025
#SBATCH --partition=lr8
#SBATCH --qos=lr8_normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=128
#SBATCH --time=3-00:00:00

apptainer exec --bind .:/app docker://python:3.11-bookworm /app/run_test.sh
