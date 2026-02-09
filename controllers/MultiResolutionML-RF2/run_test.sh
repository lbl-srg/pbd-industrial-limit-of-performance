#!/bin/bash

# This makes the script exit immediately if any command fails.
# It's a crucial safety measure to prevent the Python script from
# running if the dependencies failed to install.
set -e

echo "--- Starting job inside the container ---"

# Navigate to the application directory where our files are mounted.
# While not strictly necessary if using absolute paths, it's good practice.

cd /app

echo "--- Installing Python dependencies from requirements.txt ---"
pip install -r requirements.txt

echo "--- Dependencies installed. Running Python script... ---"

# Execute the main Python script.
# The "$@" is a special variable that passes along any arguments
# given to this bash script directly to the python script.
python3 multires.py "$@"

echo "--- Python script finished. ---"
