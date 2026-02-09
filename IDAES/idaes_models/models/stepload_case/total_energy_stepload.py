import pandas as pd
from pyomo.environ import (
    ConcreteModel,
    Var,
    Set,
    RangeSet,
    Constraint,
    Objective,
    Param,
    Block,
    value,
    Reals,
    NonNegativeReals,
    SolverFactory,
    TransformationFactory,
    assert_optimal_termination,
    units as pyunits,
)
from idaes.core.scaling import (
    CustomScalerBase,
    set_scaling_factor,
    report_scaling_factors,
)


# super_model.emissions.deactivate()


def energy_scaling(model):
    csb = CustomScalerBase()
    overwrite = False

    total_energy_sf = 1e-2

    csb.set_variable_scaling_factor(model.energies.tot_energy, total_energy_sf)

    for c in model.energies.component_data_objects(Constraint, descend_into=True):
        csb.scale_constraint_by_nominal_value(
            c, scheme="inverse_maximum", overwrite=overwrite
        )

    return model


def add_total_energies(model, no_timesteps):
    model.energies = Block()
    model.energies.year = Param(
        initialize=8760, units=pyunits.h / pyunits.yr, doc="Hours per year"
    )
    model.energies.total_sim_period = Param(
        initialize=len(model.periods), units=pyunits.h
    )
    model.energies.annual_energy_limit = Param(
        initialize=6000,
        units=pyunits.MWh / pyunits.yr,
        doc="External energy limit annually",
    )

    model.energies.tot_energy = Var(
        initialize=1e3,
        domain=NonNegativeReals,
        bounds=(0, 1e4),
        units=pyunits.MWh / pyunits.yr,
        doc="Annual energy use",
    )

    model.energies.tot_energy_con = Constraint(
        expr=pyunits.convert(
            model.energies.tot_energy, to_units=pyunits.kWh / pyunits.yr
        )
        - (model.energies.year / model.energies.total_sim_period)
        * sum(
            model.fs[key].battery.dt
            * (
                model.fs[key].electrical_grid.E_grid[0]
                + model.fs[key].gas_boiler.Q_theoretical[0]
            )
            for key in model.periods
        )
        == 0
    )

    model.energies.annual_energies_limit_constraint = Constraint(
        expr=model.energies.tot_energy - model.energies.annual_energy_limit <= 0
    )

    return model
