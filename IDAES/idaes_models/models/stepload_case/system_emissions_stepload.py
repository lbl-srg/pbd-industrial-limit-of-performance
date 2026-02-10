import pandas as pd
from importlib.resources import files
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
from ... import data

__author__ = "Oluwamayowa Amusat"


pyunits.load_definitions_from_strings(["M_kg = [weight]"])
pyunits.load_definitions_from_strings(["HT_kg = [weight]"])
pyunits.load_definitions_from_strings(["H_kg = [weight]"])


def electricity_emissions_data(no_timesteps):
    data_path = files(data).joinpath("electricity_co2_content.csv")
    elec_price = pd.read_csv(data_path)
    price_signal = elec_price["aer_gen_co2e"][0:no_timesteps]
    time_steps = [i for i in range(0, no_timesteps)]
    emissions_dict = {k: v for (k, v) in zip(time_steps, price_signal)}
    return emissions_dict


def emissions_scaling(model):
    csb = CustomScalerBase()
    overwrite = False

    hourly_emissions_sf = 1e0
    hour_year_sf = 1e0

    for p in model.periods:
        csb.set_variable_scaling_factor(
            model.emissions.hourly_gas_emissions[p], hourly_emissions_sf
        )
        csb.set_variable_scaling_factor(
            model.emissions.hourly_electricity_emissions[p], hourly_emissions_sf
        )
    # csb.set_variable_scaling_factor(model.emissions.annual_gas_emissions, hourly_emissions_sf * hour_year_sf)
    # csb.set_variable_scaling_factor(model.emissions.annual_electricity_emissions, hourly_emissions_sf * hour_year_sf)
    # csb.set_variable_scaling_factor(model.emissions.total_annual_emissions, hourly_emissions_sf * hour_year_sf)

    for c in model.emissions.component_data_objects(Constraint, descend_into=True):
        csb.scale_constraint_by_nominal_value(
            c, scheme="inverse_maximum", overwrite=overwrite
        )

    return model


def add_emissions(model, no_timesteps):
    emissions_dict = electricity_emissions_data(no_timesteps)
    model.emissions = Block()
    model.emissions.total_sim_period = Param(
        initialize=len(model.periods), units=pyunits.h
    )
    model.emissions.year = Param(
        initialize=8760, units=pyunits.h / pyunits.yr, doc="Hours per year"
    )
    model.costing.kg_to_Mkg = Param(initialize=1e-6, units=pyunits.M_kg / pyunits.kg)
    model.costing.kg_to_HTkg = Param(initialize=1e-5, units=pyunits.HT_kg / pyunits.kg)
    model.costing.kg_to_Hkg = Param(initialize=1e-2, units=pyunits.H_kg / pyunits.kg)
    model.costing.Hkg_to_HTkg = Param(
        initialize=1e-3, units=pyunits.HT_kg / pyunits.H_kg
    )

    # Emissions
    for p in model.periods:
        model.fs[p].electrical_grid.electricity_emissions = Param(
            initialize=emissions_dict[p], units=pyunits.g / pyunits.kWh
        )
        model.fs[p].gas_boiler.gas_emissions = Param(
            initialize=202, units=pyunits.g / pyunits.kWh
        )

    model.emissions.annual_emissions_limit = Param(
        initialize=100, units=pyunits.HT_kg / pyunits.yr, doc="Emissions limit annually"
    )

    model.emissions.hourly_gas_emissions = Var(
        model.periods,
        initialize=0,
        units=pyunits.H_kg,
        domain=NonNegativeReals,
        bounds=(0, 1e2),
        doc="Hourly gas emissions in Kg",
    )

    model.emissions.hourly_electricity_emissions = Var(
        model.periods,
        initialize=0,
        units=pyunits.H_kg,
        domain=NonNegativeReals,
        bounds=(0, 1e2),
        doc="Hourly emissions from electricity in Kg",
    )

    model.emissions.annual_gas_emissions = Var(
        initialize=0,
        units=pyunits.HT_kg / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 100),
        doc="Annual gas emissions in kg/year",
    )

    model.emissions.annual_electricity_emissions = Var(
        initialize=0,
        units=pyunits.HT_kg / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 100),
        doc="Annual electricity emissions in kg/year",
    )

    model.emissions.total_annual_emissions = Var(
        initialize=0,
        units=pyunits.HT_kg / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 100),
        doc="Annual emissions in megatonne/year",
    )

    @model.emissions.Constraint(model.periods)
    def eq_hourly_gas_emissions(b, t):
        # return (pyunits.convert(model.emissions.hourly_gas_emissions[t], to_units=pyunits.g) == model.fs[t].gas_boiler.gas_emissions * model.fs[t].gas_boiler.Q_theoretical[0] * model.fs[t].battery.dt)
        return (
            model.emissions.hourly_gas_emissions[t]
            == pyunits.convert(
                model.fs[t].gas_boiler.gas_emissions
                * model.fs[t].gas_boiler.Q_theoretical[0]
                * model.fs[t].battery.dt,
                to_units=pyunits.kg,
            )
            * model.costing.kg_to_Hkg
        )

    model.emissions.annual_gas_emissions_constraint = Constraint(
        expr=model.emissions.annual_gas_emissions
        - model.costing.Hkg_to_HTkg
        * (model.emissions.year / model.emissions.total_sim_period)
        * sum(model.emissions.hourly_gas_emissions[key] for key in model.periods)
        == 0
    )

    @model.emissions.Constraint(model.periods)
    def eq_hourly_electricity_emissions(b, t):
        # return (pyunits.convert(model.emissions.hourly_electricity_emissions[t], to_units=pyunits.g) == model.fs[t].electrical_grid.E_grid[0] * model.fs[0].battery.dt * model.fs[t].electrical_grid.electricity_emissions)
        return (
            model.emissions.hourly_electricity_emissions[t]
            == pyunits.convert(
                model.fs[t].electrical_grid.E_grid[0]
                * model.fs[0].battery.dt
                * model.fs[t].electrical_grid.electricity_emissions,
                to_units=pyunits.kg,
            )
            * model.costing.kg_to_Hkg
        )

    model.emissions.annual_electricity_emissions_constraint = Constraint(
        expr=model.emissions.annual_electricity_emissions
        - model.costing.Hkg_to_HTkg
        * (model.emissions.year / model.emissions.total_sim_period)
        * sum(
            model.emissions.hourly_electricity_emissions[key] for key in model.periods
        )
        == 0
    )

    model.emissions.total_emissions_constraint = Constraint(
        expr=model.emissions.total_annual_emissions
        - (
            model.emissions.annual_electricity_emissions
            + model.emissions.annual_gas_emissions
        )
        == 0
    )

    model.emissions.annual_emissions_limit_constraint = Constraint(
        expr=model.emissions.total_annual_emissions
        - model.emissions.annual_emissions_limit
        <= 0
    )

    return model
