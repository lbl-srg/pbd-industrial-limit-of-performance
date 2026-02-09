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

pyunits.load_definitions_from_strings(["USD = [currency]"])
pyunits.load_definitions_from_strings(["HT_USD = [currency]"])
pyunits.load_definitions_from_strings(["M_USD = [currency]"])


def electricity_prices(no_timesteps):
    data_path = files(data).joinpath("electricity_price.csv")
    elec_price = pd.read_csv(data_path, index_col=0)
    price_signal = elec_price["price"][0:no_timesteps]
    time_steps = [i for i in range(0, no_timesteps)]
    cost_dict = {k: v for (k, v) in zip(time_steps, price_signal)}
    return cost_dict


def cost_scaling(model):
    csb = CustomScalerBase()
    overwrite = False

    for v in model.costing.cc.component_data_objects(Var, descend_into=True):
        csb.set_variable_scaling_factor(v, 1e-6, overwrite=overwrite)

    for v in model.costing.oc.component_data_objects(Var, descend_into=True):
        csb.set_variable_scaling_factor(v, 1e-4, overwrite=overwrite)

    for v in model.costing.component_data_objects(Var, descend_into=True):
        csb.set_variable_scaling_factor(v, 1, overwrite=overwrite)

    for c in model.costing.cc.component_data_objects(Constraint, descend_into=True):
        csb.scale_constraint_by_nominal_value(
            c, scheme="inverse_maximum", overwrite=overwrite
        )

    for c in model.costing.oc.component_data_objects(Constraint, descend_into=True):
        csb.scale_constraint_by_nominal_value(
            c, scheme="inverse_maximum", overwrite=overwrite
        )

    return model


def add_costing(model, no_timesteps):
    timecosts = electricity_prices(no_timesteps)
    model.costing = Block()
    model.costing.cc = Block()
    model.costing.oc = Block()
    model.costing.total_sim_period = Param(
        initialize=len(model.periods), units=pyunits.h
    )
    model.costing.year = Param(
        initialize=8760, units=pyunits.h / pyunits.yr, doc="Hours per year"
    )
    model.costing.cap_recovery_factor = Param(initialize=0.1, units=1 / pyunits.yr)
    model.costing.htusd_to_usd = Param(
        initialize=1e-6, units=pyunits.M_USD / pyunits.USD
    )

    # Capital costs
    model.costing.cc.fixed_tank_unit_cost = Param(initialize=1520, units=pyunits.USD)
    model.costing.cc.variable_tank_unit_cost = Param(
        initialize=4845, units=pyunits.USD / pyunits.m**3
    )
    model.costing.cc.fixed_heat_pump_unit_cost = Param(initialize=0, units=pyunits.USD)
    model.costing.cc.variable_heat_pump_unit_cost = Param(
        initialize=2055, units=pyunits.USD / pyunits.kW
    )
    model.costing.cc.fixed_boiler_unit_cost = Param(initialize=79670, units=pyunits.USD)
    model.costing.cc.variable_boiler_unit_cost = Param(
        initialize=367, units=pyunits.USD / pyunits.kW
    )
    model.costing.cc.fixed_battery_unit_cost = Param(initialize=0, units=pyunits.USD)
    model.costing.cc.variable_battery_unit_cost = Param(
        initialize=757, units=pyunits.USD / pyunits.kWh
    )
    model.costing.cc.fixed_pv_unit_cost = Param(initialize=0, units=pyunits.USD)
    model.costing.cc.variable_pv_unit_cost = Param(
        initialize=3500, units=pyunits.USD / pyunits.kW
    )
    model.costing.cc.pv_capacity_conversion = Param(
        initialize=0.17939, units=pyunits.kW / pyunits.m**2
    )

    # Operating costs
    for p in model.periods:
        model.fs[p].electrical_grid.grid_electricity_unit_costs = Param(
            initialize=timecosts[p], units=pyunits.USD / pyunits.kWh
        )
        model.fs[p].gas_boiler.gas_unit_costs = Param(
            initialize=0.384, units=pyunits.USD / pyunits.m**3
        )  # $0.039/kWh to m3 with HHV
        # model.fs[p].gas_boiler.gas_unit_costs = Param(initialize=0.55, units=pyunits.USD / pyunits.m**3) # $0.056/kWh to m3 with HHV
        model.fs[p].heat_pump.water_unit_costs = Param(
            initialize=1e-3, units=pyunits.USD / pyunits.m**3
        )

    model.costing.oc.operating_costs_grid = Var(
        initialize=0,
        units=pyunits.USD / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Electricity purchase cost in USD",
    )

    model.costing.oc.operating_costs_boiler = Var(
        initialize=0,
        units=pyunits.USD / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Boiler operating cost due to NG purchase, in USD",
    )

    model.costing.oc.operating_costs_water = Var(
        initialize=0,
        units=pyunits.USD / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Water purchase cost in USD",
    )

    model.costing.cc.capital_cost_boiler = Var(
        initialize=0,
        units=pyunits.USD,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Boiler purchase cost in USD",
    )

    model.costing.cc.capital_cost_battery = Var(
        initialize=0,
        units=pyunits.USD,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Battery purchase cost in USD",
    )

    model.costing.cc.capital_cost_tank = Var(
        initialize=0,
        units=pyunits.USD,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Tank purchase cost in USD",
    )

    model.costing.cc.capital_cost_hp = Var(
        initialize=0,
        units=pyunits.USD,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="Heat pump purchase cost in USD",
    )

    model.costing.cc.capital_cost_pv = Var(
        initialize=0,
        units=pyunits.USD,
        domain=NonNegativeReals,
        bounds=(0, 1e8),
        doc="PV purchase cost in USD",
    )

    model.costing.cc.total_capital_cost = Var(
        initialize=0,
        units=pyunits.M_USD,
        domain=NonNegativeReals,
        bounds=(0, 1e3),
        doc="Total capital cost in 1,000,000 USD",
    )

    model.costing.oc.total_operating_cost = Var(
        initialize=0,
        units=pyunits.M_USD / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 1e3),
        doc="Total operating cost in 1,000,000 USD",
    )

    model.costing.total_annualized_cost = Var(
        initialize=0,
        units=pyunits.M_USD / pyunits.yr,
        domain=NonNegativeReals,
        bounds=(0, 1e3),
        doc="Annualized cost in in 1,000,000 USD",
    )
    # ==========================
    #  1. Capital costs
    # ==========================
    # Tank cost
    model.costing.cc.tank_cost_constraint = Constraint(
        expr=model.costing.cc.capital_cost_tank
        - (
            model.costing.cc.fixed_tank_unit_cost
            + (model.costing.cc.variable_tank_unit_cost * model.fs[0].hw_tank.V_tank)
        )
        == 0
    )

    # Battery cost
    model.costing.cc.battery_cost_constraint = Constraint(
        expr=model.costing.cc.capital_cost_battery
        - (
            model.costing.cc.fixed_battery_unit_cost
            + (
                model.fs[0].battery.capacity_energy
                * model.costing.cc.variable_battery_unit_cost
            )
        )
        == 0
    )

    # Boiler cost
    model.costing.cc.boiler_cost_constraint = Constraint(
        expr=model.costing.cc.capital_cost_boiler
        - (
            model.costing.cc.fixed_boiler_unit_cost
            + (
                model.costing.cc.variable_boiler_unit_cost
                * model.fs[0].gas_boiler.capacity_power
            )
        )
        == 0
    )

    # Heat pump
    model.costing.cc.hp_cost_constraint = Constraint(
        expr=model.costing.cc.capital_cost_hp
        - (
            model.costing.cc.fixed_heat_pump_unit_cost
            + (
                model.costing.cc.variable_heat_pump_unit_cost
                * model.fs[0].heat_pump.capacity_power
            )
        )
        == 0
    )

    # PV
    model.costing.cc.pv_cost_constraint = Constraint(
        expr=model.costing.cc.capital_cost_pv
        - (
            model.costing.cc.fixed_pv_unit_cost
            + (
                model.costing.cc.variable_pv_unit_cost
                * model.costing.cc.pv_capacity_conversion
                * model.fs[0].PV.Area
            )
        )
        == 0
    )

    # ==========================
    #  2. Operating costs
    # ==========================
    # Cost grid electricity
    model.costing.oc.grid_op_cost_constraint = Constraint(
        expr=model.costing.oc.operating_costs_grid
        - (model.costing.year / model.costing.total_sim_period)
        * model.fs[0].battery.dt
        * sum(
            model.fs[key].electrical_grid.E_grid[0]
            * model.fs[key].electrical_grid.grid_electricity_unit_costs
            for key in model.periods
        )
        == 0
    )

    # Cost O/C (gas) for boiler
    model.costing.oc.boiler_op_cost_constraint = Constraint(
        expr=model.costing.oc.operating_costs_boiler
        - (model.costing.year / model.costing.total_sim_period)
        * sum(
            pyunits.convert(model.fs[key].battery.dt, to_units=pyunits.s)
            * model.fs[key].gas_boiler.flow_vol_gas[0]
            * model.fs[key].gas_boiler.gas_unit_costs
            for key in model.periods
        )
        == 0
    )

    # Cost O/C (gas) for water
    model.costing.oc.water_op_cost_constraint = Constraint(
        expr=model.costing.oc.operating_costs_water
        - (model.costing.year / model.costing.total_sim_period)
        * sum(
            pyunits.convert(model.fs[key].battery.dt, to_units=pyunits.s)
            * model.fs[key].feed_water.properties[0].flow_mass_phase_comp["Liq", "H2O"]
            * (1 / (1000 * pyunits.kg / pyunits.m**3))
            * model.fs[key].heat_pump.water_unit_costs
            for key in model.periods
        )
        == 0
    )

    # ==========================
    #  3. Total costs
    # ==========================
    # Total capital cost
    model.costing.capital_cost_constraint = Constraint(
        expr=model.costing.cc.total_capital_cost
        == model.costing.htusd_to_usd
        * (
            model.costing.cc.capital_cost_hp
            + model.costing.cc.capital_cost_boiler
            + model.costing.cc.capital_cost_tank
            + model.costing.cc.capital_cost_battery
            + model.costing.cc.capital_cost_pv
        )
    )

    # Total operating cost
    model.costing.operating_cost_constraint = Constraint(
        expr=model.costing.oc.total_operating_cost
        == model.costing.htusd_to_usd
        * (
            model.costing.oc.operating_costs_grid
            + model.costing.oc.operating_costs_boiler
            + model.costing.oc.operating_costs_water
        )
    )

    model.costing.system_cost_constraint = Constraint(
        expr=model.costing.total_annualized_cost
        == (model.costing.cc.total_capital_cost * model.costing.cap_recovery_factor)
        + model.costing.oc.total_operating_cost
    )

    model.objective = Objective(expr=model.costing.total_annualized_cost)

    return model
