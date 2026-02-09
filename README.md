# Platform-Based Design with Limit of Performance Analysis

This repository contains the models used
for the paper about Platform-Based Design
with limit of performance analysis.

The directory structure is as follows:
```
- modelica: Contains Modelica models
  - Buildings: Git submodule pointing to the Buildings library
  - IndustrialPilot: Models for the industrial pilot simulation
  - Modelica_Requirements: Git submodule pointing to the Modelica_Requirements library
- controllers: Contains the black-box optimal control models
  - HighResolution: The high-resolution controller
  - MultiResolution: The multi-resolution controller
  - MultiResolutionML-RF1: The multi-resolution with Random Forests (κ=1) controller
  - MultiResolutionML-RF2: The multi-resolution with Random Forests (κ=2) controller
  - MultiResolutionML-GB: The multi-resolution with Gradient Boosting controller
```

To simulate a Modelica model with Dymola on Linux, use
```bash
$ cd modelica/
$ export MODELICAPATH=`pwd`/Buildings:`pwd`/Modelica_Requirements
$ cd IndustrialPilot/
$ dymola package.mo &
```
The top-level models are in the package `IndustrialPilot.Examples`.

# Controllers

The controllers folder contains all of the controllers implemented in the paper.
Each controller is packaged with the Dymola FMU evalautator (**data/fmu_edit.fmu**), and the JADE optimizer implemented in Python (**_JADE.py**).
The full code implementation (with all hyperparameters as outlined in the paper) for all multi-resolution controllers can be found in the **multires.py** file, while the high-resolution controller is found in **highres.py**.
The requirements.txt file contains all of the Python requirements needed to run the controllers.

Running the controller is possible by navigating into the controller folder (e.g. MultiResolutionML-GB) and running the Python code:
```bash
cd MultiResolutionML-GB
python multires.py
```

To exactly replicate the environemtnt used in the paper, it is also possible to run the controllers using Apptainer (version 1.4.2-1.el8):

```bash
cd MultiResolutionML-GB
apptainer exec --bind .:/app docker://python:3.11-bookworm /app/run_test.sh
```
where **run_test.sh** contains the specifications regardin the controller code.
