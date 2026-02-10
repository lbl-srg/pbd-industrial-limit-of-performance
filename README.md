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
- IDAES: Contains the models for the architectural optimization problem
  -idaes_models/
    - data: Data on annual electricity cost and solar profiles used for architectural optimization.
    - models: Python scripts containing the unit models, cost models and full IDAES flowsheet.
```

# Modelica

To simulate a Modelica model with Dymola on Linux, use
```bash
$ cd modelica/
$ export MODELICAPATH=`pwd`/Buildings:`pwd`/Modelica_Requirements
$ cd IndustrialPilot/
$ dymola package.mo &
```
The top-level models are in the package `IndustrialPilot.Examples`.


# Controllers

The controllers folder contains all of the controllers implemented in the paper. Each controller is packaged with the Dymola FMU evaluator (**data/fmu_edit.fmu**) and the JADE optimizer implemented in Python (**_JADE.py**).

The full code implementation (with all hyperparameters as outlined in the paper) for all multi-resolution controllers is located in **multires.py**, while the high-resolution controller is in **highres.py**. The **requirements.txt** file contains all Python dependencies.

### Running Locally
To run the controller locally, navigate into the specific controller folder (e.g., `MultiResolutionML-GB`) and execute the Python script:

```bash
cd MultiResolutionML-GB
python multires.py
```

### Running with Apptainer (Reproducibility)
To exactly replicate the environment used in the paper, you can run the controllers using Apptainer (tested with version 1.4.2):

```bash
cd MultiResolutionML-GB
apptainer exec --bind .:/app docker://python:3.11-bookworm /app/run_test.sh
```

The **run_test.sh** script contains the specifications regarding the controller execution (including dependency installation).

***

# IDAES

The IDAES folder contains the unit models and flowsheets for the multi-objective architectural optimization problem presented in the in the paper. To run the idaes model for the pilot, from inside the IDAES directory, run

```
python -m idaes_models.models.stepload_case.flowsheets.heating_flowsheet_stepload_additional_constraints 
```

Due to the size of the optimization problem, running the IDAES model for the full year takes a few days. However, the model can be tested/run for a shorter time interval by passing in the ``--days`` flag. For example, to optimize over the first 7 days of the year, run

```
python -m idaes_models.models.stepload_case.flowsheets.heating_flowsheet_stepload_additional_constraints --days 7
```

Instructions for installing the IDAES model are in the IDAES folder README.

***
