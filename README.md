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
  - HighResolution: The high-resolution optimal control code (denoted as HR in the paper)
  - MultiResolution: The multi-resolution optimal control code (denoted as MR in the paper)
  - MultiResolutionML-RF1: The multi-resolution with Random Forests (hard coded $$\kappa=1$$) optimal control code
  - MultiResolutionML-RF2: The multi-resolution with Random Forests (hard coded $$\kappa=2$$) optimal control code
  - MultiResolutionML-GB: The multi-resolution with Gradient Boosting optimal control code
```

To simulate a Modelica model with Dymola on Linux, use
```bash
$ cd modelica/
$ export MODELICAPATH=`pwd`/Buildings:`pwd`/Modelica_Requirements
$ cd IndustrialPilot/
$ dymola package.mo &
```
The top-level models are in the package `IndustrialPilot.Examples`.
