"""
Stepload
"""

# Stdlib
import argparse
from importlib.resources import files
from io import StringIO
import logging
import math
from pathlib import Path
import random
import sys
from typing import Dict, List

# Third-party
import pandas as pd
from pyomo.environ import (
    ConcreteModel,
    Var,
    RangeSet,
    Constraint,
    Objective,
    value,
    SolverFactory,
    TransformationFactory,
    assert_optimal_termination,
    units as pyunits,
)
from pyomo.common.log import LoggingIntercept
from pyomo.util.infeasible import log_infeasible_constraints
from pyomo.util.check_units import assert_units_consistent
from pyomo.network import Arc
from idaes.core import FlowsheetBlock
from idaes.core import MaterialBalanceType
from idaes.models.unit_models import (
    Feed,
    Product,
    Separator,
    Mixer,
    MixingType,
    MomentumMixingType,
    SplittingType,
    EnergySplittingType,
)
from idaes.core.solvers import get_solver
from idaes.core.scaling import (
    CustomScalerBase,
    set_scaling_factor,
)
from idaes.core.util.model_statistics import degrees_of_freedom

from idaes.core.util import to_json
# from idaes_connectivity.base import Connectivity, Mermaid, D2

# Package
import idaes_models.models.stepload_case.unit_models.water_prop_pack as props2
from idaes_models.models.stepload_case.unit_models.pv_system import (
    Photovoltaics,
    PVScaler,
)
from idaes_models.models.stepload_case.unit_models.dispatches_elec_splitter import (
    ElectricalSplitter,
    ElectricalSplitterScaler,
)
from idaes_models.models.stepload_case.unit_models.battery import (
    BatteryStorage,
    BatteryStorageScaler,
)
from idaes_models.models.stepload_case.unit_models.gas_boiler_pp import (
    DetailedGasBoiler,
    GasBoilerScaler,
)
from idaes_models.models.stepload_case.unit_models.heat_pump_mod import (
    HeatPump,
    HeatPumpScaler,
)
from idaes_models.models.stepload_case.unit_models.electricity_grid import (
    ElectricalGrid,
    ElectricalGridScaler,
)
from idaes_models.models.stepload_case.unit_models.thermal_plant_load import (
    EnergySinks,
    EnergySinkScaler,
)
from idaes_models.models.stepload_case.unit_models.elec_mixer import (
    ElectricalMixer,
    ElectricalMixerScaler,
)
from idaes_models.models.stepload_case.unit_models.water_tank import (
    TankStorage,
    TankStorageScaler,
)
from idaes_models.models.stepload_case.system_costing_v3 import (
    add_costing,
    cost_scaling,
)
from idaes_models.models.stepload_case.system_emissions_stepload import (
    add_emissions,
    emissions_scaling,
)

from idaes_models.models.stepload_case.total_energy_stepload import (
    add_total_energies,
    energy_scaling,
)

# from idaes_models.models.stepload_case.model_postprocessing import (
#     extract_results_old,
# )
from idaes_models.util import add_log_options, process_log_options

from idaes_models import data


__author__ = "Oluwamayowa Amusat"


_log = logging.getLogger("idaes_models.stepload-model")
g_quiet = False
g_solver_output = True

timestep_hrs = 1


def simulate_load_signal(no_timesteps, load_kW):
    load_signal = [load_kW if i in range(8, 20) else 0 for i in range(0, 24)]
    load_signal = load_signal * (no_timesteps // 24)
    time_steps = [i for i in range(0, no_timesteps)]
    load_dict = {k: v for (k, v) in zip(time_steps, load_signal)}
    return load_dict


def simulate_price_signal(no_timesteps):
    price_signal = [
        0.11,
        0.09,
        0.09,
        0.10,
        0.31,
        0.46,
        0.51,
        0.46,
        0.38,
        0.39,
        0.46,
        0.50,
        0.64,
        0.48,
        0.38,
        0.37,
        0.39,
        0.61,
        1.14,
        0.93,
        0.62,
        0.44,
        0.29,
        0.20,
    ]
    price_signal = price_signal * (no_timesteps // 24)
    time_steps = [i for i in range(0, no_timesteps)]
    cost_dict = {k: v for (k, v) in zip(time_steps, price_signal)}
    return cost_dict


def simulate_inlet_hot_water_temperatures(no_timesteps):
    random.seed(0)
    lb, ub = 8, 16
    time_steps = [i for i in range(0, no_timesteps)]
    temps = [273.15 + random.randint(lb, ub) for i in range(0, no_timesteps)]
    # cost_dict = {k : v for (k , v) in zip(time_steps, temps)}
    return temps


def load_pv_data(no_timesteps):
    pv_data_path = files(data).joinpath("pv_production.xlsx")
    pv_available = pd.read_excel(pv_data_path)
    pv_signal = pv_available["W/m2"][0:no_timesteps]
    time_steps = [i for i in range(0, no_timesteps)]
    pv_dict = {k: v for (k, v) in zip(time_steps, pv_signal)}
    return pv_dict


def add_pv(model):
    model.PV = Photovoltaics()
    return model.PV


def add_grid_connection(model, grid_limits_mw=None):
    model.electrical_grid = ElectricalGrid()
    if grid_limits_mw is not None:
        model.electrical_grid.grid_capacity.fix(grid_limits_mw)
    return model.electrical_grid


def add_battery(model, batt_mw=None):
    model.battery = BatteryStorage()
    model.battery.dt.set_value(timestep_hrs)
    if batt_mw is not None:
        model.battery.capacity_power.fix(batt_mw)
    return model.battery


def add_detailed_gas_boiler(model, prop_pack):
    model.gas_boiler = DetailedGasBoiler(property_package=prop_pack)
    return model.gas_boiler


def add_heat_pump(model, prop_pack):
    model.heat_pump = HeatPump(property_package=prop_pack)
    return model.heat_pump


def add_water_tank(model, prop_pack):
    model.hw_tank = TankStorage(property_package=prop_pack)
    model.hw_tank.Q_elect.fix(0)
    return model.hw_tank


def add_thermal_plant_loads(model, prop_pack):
    model.plant_load = EnergySinks(property_package=prop_pack)
    return model.plant_load


def build_model(timesteps=None, **kwargs):
    grid_electricity_sinks = ["battery", "heat_pump"]
    battery_electricity_sinks = ["heat_pump", "electrical_load"]
    heat_pump_electricity_sources = ["battery", "grid"]
    thermal_energy_sources = ["from_hp", "from_boiler"]
    plant_load_heat_sources = ["from_direct", "from_tank"]
    tank_water_sources = ["from_load", "from_generation"]
    tank_water_sinks = ["to_hp", "to_boiler", "to_plant"]
    electricity_generation_sources = ["pv", "grid"]

    m = ConcreteModel()
    m.periods = RangeSet(0, timesteps - 1)
    m.fs = FlowsheetBlock(m.periods, dynamic=False)

    for p in m.periods:
        # Property package
        m.fs[p].water_properties = props2.WaterParameterBlock()

        m.fs[p].plant_load = add_thermal_plant_loads(m.fs[p], m.fs[p].water_properties)
        m.fs[p].electrical_grid = add_grid_connection(m.fs[p])
        m.fs[p].PV = add_pv(m.fs[p])
        m.fs[p].generation_electricity_mixer = ElectricalMixer(
            inlet_list=electricity_generation_sources
        )
        m.fs[p].battery = add_battery(m.fs[p])
        m.fs[p].grid_splitter = ElectricalSplitter(
            outlet_list=grid_electricity_sinks, add_split_fraction_vars=False
        )
        m.fs[p].gas_boiler = add_detailed_gas_boiler(m.fs[p], m.fs[p].water_properties)
        m.fs[p].heat_pump = add_heat_pump(m.fs[p], m.fs[p].water_properties)
        m.fs[p].hw_tank = add_water_tank(m.fs[p], m.fs[p].water_properties)
        m.fs[p].heat_pump_electricity_mixer = ElectricalMixer(
            inlet_list=heat_pump_electricity_sources
        )
        m.fs[p].thermal_generation_mixer = Mixer(
            property_package=m.fs[p].water_properties,
            inlet_list=thermal_energy_sources,
            material_balance_type=MaterialBalanceType.componentPhase,
            momentum_mixing_type=MomentumMixingType.equality,
            # equality or minimize
            energy_mixing_type=MixingType.extensive,
        )
        m.fs[p].thermal_generation_splitter = Separator(
            property_package=m.fs[p].water_properties,
            outlet_list=["to_plant", "to_tank"],
            split_basis=SplittingType.totalFlow,
            energy_split_basis=EnergySplittingType.equal_temperature,
            material_balance_type=MaterialBalanceType.componentPhase,
        )
        m.fs[p].thermal_demand_mixer = Mixer(
            property_package=m.fs[p].water_properties,
            inlet_list=plant_load_heat_sources,
            momentum_mixing_type=MomentumMixingType.equality,  # .equality,
            energy_mixing_type=MixingType.extensive,
        )
        m.fs[p].tank_mixer = Mixer(
            property_package=m.fs[p].water_properties,
            inlet_list=tank_water_sources,
            momentum_mixing_type=MomentumMixingType.equality,  # .equality,
            energy_mixing_type=MixingType.extensive,
        )
        m.fs[p].feed_water = Feed(property_package=m.fs[p].water_properties)
        m.fs[p].waste_water = Product(property_package=m.fs[p].water_properties)
        m.fs[p].tank_water_splitter = Separator(
            property_package=m.fs[p].water_properties,
            outlet_list=tank_water_sinks,
            split_basis=SplittingType.totalFlow,
            energy_split_basis=EnergySplittingType.equal_temperature,
            material_balance_type=MaterialBalanceType.componentPhase,
        )

        m.fs[p].grid_power_consumed = Arc(
            source=m.fs[p].electrical_grid.power_supplied,
            dest=m.fs[p].generation_electricity_mixer.grid_port,
        )  # m.fs[p].grid_splitter.electricity_in)
        m.fs[p].pv_power_consumed = Arc(
            source=m.fs[p].PV.power_supplied,
            dest=m.fs[p].generation_electricity_mixer.pv_port,
        )
        m.fs[p].total_electricity_stream = Arc(
            source=m.fs[p].generation_electricity_mixer.electricity_out,
            dest=m.fs[p].grid_splitter.electricity_in,
        )
        m.fs[p].gridsplitter_to_battery = Arc(
            source=m.fs[p].grid_splitter.battery_port, dest=m.fs[p].battery.power_in
        )
        m.fs[p].gridsplitter_to_heatpump = Arc(
            source=m.fs[p].grid_splitter.heat_pump_port,
            dest=m.fs[p].heat_pump_electricity_mixer.grid_port,
        )
        m.fs[p].battery_to_heatpump = Arc(
            source=m.fs[p].battery.power_out,
            dest=m.fs[p].heat_pump_electricity_mixer.battery_port,
        )
        m.fs[p].electricity_to_heatpump = Arc(
            source=m.fs[p].heat_pump_electricity_mixer.electricity_out,
            dest=m.fs[p].heat_pump.power_in,
        )

        m.fs[p].tank_to_separator = Arc(
            source=m.fs[p].hw_tank.outlet_water, dest=m.fs[p].tank_water_splitter.inlet
        )
        m.fs[p].tank_separator_to_boiler = Arc(
            source=m.fs[p].tank_water_splitter.to_boiler,
            dest=m.fs[p].gas_boiler.inlet_water,
        )
        m.fs[p].tank_separator_to_hp = Arc(
            source=m.fs[p].tank_water_splitter.to_hp,
            dest=m.fs[p].heat_pump.hotside_inlet_water,
        )
        m.fs[p].tank_separator_to_plant = Arc(
            source=m.fs[p].tank_water_splitter.to_plant,
            dest=m.fs[p].thermal_demand_mixer.from_tank,
        )
        m.fs[p].boiler_thermal_generation_mixing = Arc(
            source=m.fs[p].gas_boiler.outlet_water,
            dest=m.fs[p].thermal_generation_mixer.from_boiler,
        )
        m.fs[p].hp_thermal_generation_mixing = Arc(
            source=m.fs[p].heat_pump.hotside_outlet_water,
            dest=m.fs[p].thermal_generation_mixer.from_hp,
        )
        m.fs[p].district_water_to_hp = Arc(
            source=m.fs[p].feed_water.outlet,
            dest=m.fs[p].heat_pump.coldside_inlet_water,
        )
        m.fs[p].hp_to_district_water = Arc(
            source=m.fs[p].heat_pump.coldside_outlet_water,
            destination=m.fs[p].waste_water.inlet,
        )
        m.fs[p].mixer_to_splitter = Arc(
            source=m.fs[p].thermal_generation_mixer.outlet,
            dest=m.fs[p].thermal_generation_splitter.inlet,
        )
        m.fs[p].direct_generation_to_load = Arc(
            source=m.fs[p].thermal_generation_splitter.to_plant,
            dest=m.fs[p].thermal_demand_mixer.from_direct,
        )
        m.fs[p].total_stream_to_load = Arc(
            source=m.fs[p].thermal_demand_mixer.outlet,
            destination=m.fs[p].plant_load.inlet_water,
        )
        m.fs[p].load_to_mixer_pretank = Arc(
            source=m.fs[p].plant_load.outlet_water, dest=m.fs[p].tank_mixer.from_load
        )
        m.fs[p].generation_to_mixer_pretank = Arc(
            source=m.fs[p].thermal_generation_splitter.to_tank,
            destination=m.fs[p].tank_mixer.from_generation,
        )
        m.fs[p].water_bleeding_pretank = Arc(
            source=m.fs[p].tank_mixer.outlet, destination=m.fs[p].hw_tank.inlet_water
        )

    # ========================
    # Battery constraints:
    # ========================
    # 1 . Capacity of battery in MW must be same across all time periods
    @m.Constraint(m.periods)
    def eq_battery_power_capacity_linking(m, key):
        if key == max(list(m.periods)):
            return m.fs[key].battery.capacity_power == m.fs[0].battery.capacity_power
        else:
            return (
                m.fs[key].battery.capacity_power == m.fs[key + 1].battery.capacity_power
            )

    # 2 . Capacity of battery in MWh must be same across all time periods
    @m.Constraint(m.periods)
    def eq_battery_energy_capacity_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].battery.capacity_energy - m.fs[0].battery.capacity_energy == 0
            )
        else:
            return (
                m.fs[key].battery.capacity_energy
                - m.fs[key + 1].battery.capacity_energy
                == 0
            )

    # 3. Energy at start of next time period should be same as end of previous time perios, and first must equal last
    @m.Constraint(m.periods)
    def eq_battery_storage_level_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].battery.storage_level[0] - m.fs[0].battery.initial_state == 0
            )  # constraint to ensure no energy is "magically" used
        else:
            return (
                m.fs[key].battery.storage_level[0] - m.fs[key + 1].battery.initial_state
                == 0
            )

    # ========================
    # Grid constraints:
    # ========================
    # 1. Capacity of grid in MW must be same across all time periods
    @m.Constraint(m.periods)
    def eq_grid_power_capacity_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].electrical_grid.grid_capacity
                - m.fs[0].electrical_grid.grid_capacity
                == 0
            )
        else:
            return (
                m.fs[key].electrical_grid.grid_capacity
                - m.fs[key + 1].electrical_grid.grid_capacity
                == 0
            )

    # 2. Constrain the maximum power that can be drawn from the grid at any one timestep: current assumption: 2.5x load
    @m.Constraint(m.periods)
    def eq_max_grid_capacity(m, key):
        return (
            pyunits.convert(m.fs[key].electrical_grid.E_grid[0], to_units=pyunits.MW)
            <= 2.5 * pyunits.MW
        )

    # ========================
    # Boiler constraints:
    # ========================
    # 1 . Capacity of boiler in MW must be same across all time periods
    @m.Constraint(m.periods)
    def eq_boiler_power_capacity_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].gas_boiler.capacity_power - m.fs[0].gas_boiler.capacity_power
                == 0
            )
        else:
            return (
                m.fs[key].gas_boiler.capacity_power
                - m.fs[key + 1].gas_boiler.capacity_power
                == 0
            )

    # ========================
    # Heat pump constraints:
    # ========================
    # 1 . Capacity of HP in kW must be same across all time periods
    @m.Constraint(m.periods)
    def eq_hp_power_capacity_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].heat_pump.capacity_power - m.fs[0].heat_pump.capacity_power
                == 0
            )
        else:
            return (
                m.fs[key].heat_pump.capacity_power
                - m.fs[key + 1].heat_pump.capacity_power
                == 0
            )

    # ========================
    # Tank constraints:
    # ========================
    # 1 . Volume of water tank must be same across all time periods
    @m.Constraint(m.periods)
    def eq_hw_tank_volume_linking(m, key):
        if key == max(list(m.periods)):
            return m.fs[key].hw_tank.V_tank - m.fs[0].hw_tank.V_tank == 0
        else:
            return m.fs[key].hw_tank.V_tank - m.fs[key + 1].hw_tank.V_tank == 0

    # 3 . Capacity of tank in MWh must be same across all time periods
    @m.Constraint(m.periods)
    def eq_hw_tank_energy_capacity_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].hw_tank.capacity_energy - m.fs[0].hw_tank.capacity_energy == 0
            )
        else:
            return (
                m.fs[key].hw_tank.capacity_energy
                - m.fs[key + 1].hw_tank.capacity_energy
                == 0
            )

    # # 4. Energy mass at start of next time period should be same as end of previous time perios, and first must equal last
    # @m.Constraint(m.periods)
    # def eq_hw_tank_storage_level_linking(m, key):
    #     if key == max(list(m.periods)):
    #         return m.fs[key].hw_tank.storage_level[0] - m.fs[
    #             0].hw_tank.initial_state_energy == 0  # m.fs[key].hw_tank.storage_level[0] - m.fs[0].hw_tank.initial_state_energy == 0
    #     else:
    #         return m.fs[key].hw_tank.storage_level[0] - m.fs[key + 1].hw_tank.initial_state_energy == 0

    # 5. Water mass at start of next time period should be same as end of previous time perios, and first must equal last
    @m.Constraint(m.periods)
    def eq_hw_tank_water_level_linking(m, key):
        if key == max(list(m.periods)):
            return m.fs[key].hw_tank.M[0] - m.fs[0].hw_tank.initial_state_mass == 0
        else:
            return (
                m.fs[key].hw_tank.M[0] - m.fs[key + 1].hw_tank.initial_state_mass == 0
            )

    # 6. Temperature at start of next time period should be same as end of previous time perios, and first must equal last
    # Andrew advice: use slacks instead of these start=end constraints?
    @m.Constraint(m.periods)
    def eq_hw_tank_temperature_linking(m, key):
        if key == max(list(m.periods)):
            return (
                m.fs[key].hw_tank.T[0] - m.fs[0].hw_tank.initial_state_temperature == 0
            )
        else:
            return (
                m.fs[key].hw_tank.T[0] - m.fs[key + 1].hw_tank.initial_state_temperature
                == 0
            )

    # 7. PV Area in m2 must be same across all time periods
    @m.Constraint(m.periods)
    def eq_pv_area_linking(m, key):
        if key == max(list(m.periods)):
            return m.fs[key].PV.Area - m.fs[0].PV.Area == 0
        else:
            return m.fs[key].PV.Area - m.fs[key + 1].PV.Area == 0

    TransformationFactory("network.expand_arcs").apply_to(m)

    return m


class FlowsheetScaler(CustomScalerBase):

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        pass

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        pass

        for j, c in model.eq_grid_power_capacity_linking.items():
            # self.scale_constraint_by_nominal_value(c, scheme="inverse_maximum", overwrite=overwrite,)
            self.scale_constraint_by_component(
                c,
                model.fs[0].electrical_grid.grid_capacity,
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_power_capacity_linking.items():
            self.scale_constraint_by_component(
                c,
                model.fs[0].battery.capacity_power,
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_energy_capacity_linking.items():
            self.scale_constraint_by_component(
                c,
                model.fs[0].battery.capacity_energy,
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_storage_level_linking.items():
            self.scale_constraint_by_component(
                c,
                model.fs[0].battery.storage_level[0],
                overwrite=overwrite,
            )

        # for j, c in model.eq_hw_tank_storage_level_linking.items():
        #     self.scale_constraint_by_component(c, model.fs[0].hw_tank.storage_level[0], overwrite=overwrite)

        for j, c in model.eq_max_grid_capacity.items():
            self.scale_constraint_by_component(
                c, model.fs[0].electrical_grid.grid_capacity, overwrite=overwrite
            )

        for j, c in model.eq_boiler_power_capacity_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].gas_boiler.capacity_power, overwrite=overwrite
            )

        for j, c in model.eq_hp_power_capacity_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].heat_pump.capacity_power, overwrite=overwrite
            )

        for j, c in model.eq_hw_tank_volume_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].hw_tank.V_tank, overwrite=overwrite
            )

        for j, c in model.eq_hw_tank_energy_capacity_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].hw_tank.capacity_energy, overwrite=overwrite
            )

        for j, c in model.eq_hw_tank_temperature_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].hw_tank.T[0], overwrite=overwrite
            )

        for j, c in model.eq_hw_tank_water_level_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].hw_tank.M_tank, overwrite=overwrite
            )

        for j, c in model.eq_pv_area_linking.items():
            self.scale_constraint_by_component(
                c, model.fs[0].PV.Area, overwrite=overwrite
            )


def add_scaling(model):
    f_sf = [
        1e-2 if value(model.fs[p].plant_load.Q_load[0]) > 0 else 1
        for p in model.periods
    ]
    time_steps = [i for i in range(0, len(model.periods))]
    f_sf_set = {k: v for (k, v) in zip(time_steps, f_sf)}

    enth_sf = 1e-6

    overwrite = True

    for p in model.periods:
        scaler = EnergySinkScaler()
        set_scaling_factor(
            model.fs[p].plant_load.properties_in[0].flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p].plant_load.properties_out[0].flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        if f_sf_set[p] == 1:
            set_scaling_factor(model.fs[p].plant_load.Q_load[0], f_sf_set[p])
        scaler.scale_model(
            model.fs[p].plant_load,
            submodel_scalers={
                "control_volume.properties_in": props2.WaterPropertiesScaler,
                "control_volume.properties_out": props2.WaterPropertiesScaler,
            },
        )

        scaler = GasBoilerScaler()
        set_scaling_factor(
            model.fs[p].gas_boiler.properties_in[0].flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p].gas_boiler.properties_out[0].flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p].gas_boiler.properties_in[0].enth_mass_phase["Liq"], enth_sf
        )
        set_scaling_factor(
            model.fs[p].gas_boiler.properties_out[0].enth_mass_phase["Liq"], enth_sf
        )
        scaler.scale_model(
            model.fs[p].gas_boiler,
            submodel_scalers={
                "control_volume.properties_in": props2.WaterPropertiesScaler,
                "control_volume.properties_out": props2.WaterPropertiesScaler,
            },
        )

        scaler = HeatPumpScaler()
        set_scaling_factor(
            model.fs[p]
            .heat_pump.properties_in_hotside[0]
            .flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p]
            .heat_pump.properties_out_hotside[0]
            .flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p]
            .heat_pump.properties_in_coldside[0]
            .flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p]
            .heat_pump.properties_out_coldside[0]
            .flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p].heat_pump.properties_in_hotside[0].enth_mass_phase["Liq"],
            enth_sf,
        )
        set_scaling_factor(
            model.fs[p].heat_pump.properties_out_hotside[0].enth_mass_phase["Liq"],
            enth_sf,
        )
        set_scaling_factor(
            model.fs[p].heat_pump.properties_in_coldside[0].enth_mass_phase["Liq"],
            enth_sf,
        )
        set_scaling_factor(
            model.fs[p].heat_pump.properties_out_coldside[0].enth_mass_phase["Liq"],
            enth_sf,
        )
        scaler.scale_model(
            model.fs[p].heat_pump,
            submodel_scalers={
                "control_volume.properties_in_hotside": props2.WaterPropertiesScaler,
                "control_volume.properties_out_hotside": props2.WaterPropertiesScaler,
                "control_volume.properties_in_coldside": props2.WaterPropertiesScaler,
                "control_volume.properties_out_coldside": props2.WaterPropertiesScaler,
            },
        )

        scaler = TankStorageScaler()
        set_scaling_factor(
            model.fs[p].hw_tank.properties_in[0].flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p].hw_tank.properties_out[0].flow_mass_phase_comp["Liq", "H2O"],
            f_sf_set[p],
        )
        set_scaling_factor(
            model.fs[p].hw_tank.properties_in[0].enth_mass_phase["Liq"], enth_sf
        )
        set_scaling_factor(
            model.fs[p].hw_tank.properties_out[0].enth_mass_phase["Liq"], enth_sf
        )
        scaler.scale_model(
            model.fs[p].hw_tank,
            submodel_scalers={
                "control_volume.properties_in": props2.WaterPropertiesScaler,
                "control_volume.properties_out": props2.WaterPropertiesScaler,
            },
        )

        scaler = BatteryStorageScaler()
        scaler.scale_model(
            model.fs[p].battery,
        )

        scaler = ElectricalGridScaler()
        scaler.scale_model(
            model.fs[p].electrical_grid,
        )

        scaler = ElectricalSplitterScaler()
        scaler.scale_model(
            model.fs[p].grid_splitter,
        )

        scaler = ElectricalMixerScaler()
        scaler.scale_model(
            model.fs[p].heat_pump_electricity_mixer,
        )

        scaler = PVScaler()
        scaler.scale_model(
            model.fs[p].PV,
        )

        scaler = ElectricalMixerScaler()
        scaler.scale_model(
            model.fs[p].generation_electricity_mixer,
        )

    scaler = FlowsheetScaler()
    scaler.scale_model(model)

    csb = CustomScalerBase()
    for p in model.periods:

        DEFAULT_SCALING_FACTORS = {
            "flow_mass_phase_comp": f_sf_set[p],
            "pressure": 1e-5,
            "temperature": 1e-2,
            "split_fraction": 1,
            "enth_mass_phase": enth_sf,
        }
        DEFAULT_SCALING_FACTORS["enth_flow_phase"] = (
            DEFAULT_SCALING_FACTORS["flow_mass_phase_comp"]
            * DEFAULT_SCALING_FACTORS["enth_mass_phase"]
        )

        for unit in (
            "feed_water",
            "waste_water",
            "thermal_generation_splitter",
            "tank_water_splitter",
            "thermal_generation_mixer",
            "thermal_demand_mixer",
            "tank_mixer",
        ):
            block = getattr(model.fs[p], unit)
            for v in block.component_data_objects(Var, descend_into=True):
                for k in DEFAULT_SCALING_FACTORS.keys():
                    if k in v.name:
                        csb.set_variable_scaling_factor(
                            v, DEFAULT_SCALING_FACTORS[k], overwrite=overwrite
                        )

    csb = CustomScalerBase()
    for p in model.periods:
        for unit in (
            "thermal_generation_splitter",
            "tank_water_splitter",
            "thermal_generation_mixer",
            "thermal_demand_mixer",
            "tank_mixer",
        ):
            block = getattr(model.fs[p], unit)
            for c in block.component_data_objects(Constraint, descend_into=True):
                csb.scale_constraint_by_nominal_value(
                    c, scheme="inverse_maximum", overwrite=overwrite
                )

    # scale arcs
    csb = CustomScalerBase()
    for p in model.periods:
        arcs_in_period = list(model.fs[p].component_objects(Arc, descend_into=True))
        for arc in arcs_in_period:
            for constr_name, c in arc.component_map(ctype=Constraint).items():
                if "pressure" in constr_name:
                    for index in c:
                        csb.set_constraint_scaling_factor(
                            c[index],
                            DEFAULT_SCALING_FACTORS["pressure"],
                            overwrite=overwrite,
                        )
                if "temperature" in constr_name:
                    for index in c:
                        csb.set_constraint_scaling_factor(
                            c[index],
                            DEFAULT_SCALING_FACTORS["temperature"],
                            overwrite=overwrite,
                        )

    # report_scaling_factors(model.fs[0].heat_pump)
    # report_scaling_factors(model, descend_into=True)
    # assert False

    return model


def instantiate_model(model, load_kW, data=None):
    num_periods = len(model.periods)
    _log.debug(f"instantiate model: #periods={num_periods}")
    # Hot water temperatures
    boiler_efficiency = 0.90
    heat_pump_COP = 3.0
    batt_effs = 0.95
    feedwater_temps = simulate_inlet_hot_water_temperatures(num_periods)
    load_profile = simulate_load_signal(num_periods, load_kW)
    for p in model.periods:
        model.fs[p].feed_water.pressure.fix(101325)
        model.fs[p].feed_water.temperature.fix(feedwater_temps[p])

        # Fix temperatures
        model.fs[p].gas_boiler.properties_out[0].temperature.fix(92 + 273.15)
        model.fs[p].heat_pump.properties_out_hotside[0].temperature.fix(92 + 273.15)
        model.fs[p].plant_load.properties_in[0].temperature.fix(90 + 273.15)
        model.fs[p].plant_load.properties_out[0].temperature.fix(70 + 273.15)
        # Set parameters
        model.fs[p].battery.eta_discharge.set_value(batt_effs)
        model.fs[p].battery.eta_charge.set_value(batt_effs)
        model.fs[p].gas_boiler.eta.set_value(boiler_efficiency)
        model.fs[p].heat_pump.COP.set_value(heat_pump_COP)
        # Set loads
        # thermal_load_value = 1e3
        _log.debug(f"get model load for period={p}")
        model.fs[p].plant_load.Q_load[0].fix(load_profile[p])

    return model


def instantiate_pv_with_data(model):
    pv_power = load_pv_data(len(model.periods))
    for p in model.periods:
        model.fs[p].PV.power_per_unit_area[0].set_value(
            pv_power[p] * pyunits.W / pyunits.m**2
        )
    return model


def create_steady_state_problem(model):
    # 1. Fix capacities of boiler, gas turbine, battery and tank storage
    for p in model.periods:
        model.fs[p].gas_boiler.capacity_power.fix(1.5e3)
        model.fs[p].heat_pump.capacity_power.fix(1.5e3)
        model.fs[p].hw_tank.capacity_energy.fix(15 * 1e3)
        model.fs[p].PV.Area.fix(1000 * pyunits.m**2)
        # model.fs[p].mixer_to_splitter_expanded.flow_mass_phase_comp_equality.deactivate()

    # model.fs[0].hw_tank.initial_state_energy.fix(4 * 1e3)

    assert degrees_of_freedom(model) == 0
    return model


def add_upper_bounds(model, load_kW):
    gen_max = 1.5
    store_max = 15
    for p in model.periods:
        model.fs[p].heat_pump.capacity_power.setub(gen_max * load_kW * pyunits.kW)
        model.fs[p].heat_pump.Q_hotside[0].setub(gen_max * load_kW * pyunits.kW)
        model.fs[p].heat_pump.Q_coldside[0].setub(gen_max * load_kW * pyunits.kW)
        model.fs[p].heat_pump.gross_power_in[0].setub(gen_max * load_kW * pyunits.kW)

        model.fs[p].gas_boiler.capacity_power.setub(gen_max * load_kW * pyunits.kW)
        model.fs[p].gas_boiler.Q_actual[0].setub(gen_max * load_kW * pyunits.kW)

        model.fs[p].battery.capacity_energy.setub(store_max * load_kW * pyunits.kWh)
        model.fs[p].battery.initial_state.setub(store_max * load_kW * pyunits.kWh)
        model.fs[p].battery.storage_level[0].setub(store_max * load_kW * pyunits.kWh)

        model.fs[p].hw_tank.initial_state_energy.setub(
            store_max * load_kW * pyunits.kWh
        )
        model.fs[p].hw_tank.capacity_energy.setub(store_max * load_kW * pyunits.kWh)
        model.fs[p].hw_tank.storage_level[0].setub(store_max * load_kW * pyunits.kWh)
        model.fs[p].hw_tank.M[0].setub(
            (3600 * store_max * load_kW)
            / (
                value(model.fs[0].hw_tank.cp)
                * value(model.fs[0].hw_tank.T[0].ub - model.fs[0].hw_tank.T_ref)
            )
        )
        model.fs[p].hw_tank.M_tank.setub(
            (3600 * store_max * load_kW)
            / (
                value(model.fs[0].hw_tank.cp)
                * value(model.fs[0].hw_tank.T[0].ub - model.fs[0].hw_tank.T_ref)
            )
        )
        model.fs[p].hw_tank.initial_state_mass.setub(
            (3600 * store_max * load_kW)
            / (
                value(model.fs[0].hw_tank.cp)
                * value(model.fs[0].hw_tank.T[0].ub - model.fs[0].hw_tank.T_ref)
            )
        )
        model.fs[p].hw_tank.V_tank.setub(
            (3.6 * store_max * load_kW)
            / (
                value(model.fs[0].hw_tank.cp)
                * value(model.fs[0].hw_tank.T[0].ub - model.fs[0].hw_tank.T_ref)
            )
        )

        # Replace this with data from ETA team
        model.fs[p].PV.Area.setub(1e6 * pyunits.m**2)

    return model


def add_battery_charging_constraints(model):
    rate_max = 3 * pyunits.h

    def eq_battery_charge_limit(m, key):
        return (
            m.fs[key].battery.capacity_power * rate_max
            <= m.fs[key].battery.capacity_energy
        )

    model.battery_charging_limit_constraint = Constraint(
        model.periods, rule=eq_battery_charge_limit
    )

    return model


def deactivate_enthapy_constraints(model):
    m1 = degrees_of_freedom(model)
    for p in model.periods:
        if value(model.fs[p].plant_load.Q_load[0]) == 0:
            # m.fs[p].thermal_demand_mixer.enthalpy_mixing_equations.deactivate()
            model.fs[p].thermal_demand_mixer.from_direct_state[0.0].eq_enth_flow_phase[
                "Liq"
            ].deactivate()
            model.fs[p].thermal_demand_mixer.from_tank_state[0.0].eq_enth_flow_phase[
                "Liq"
            ].deactivate()
            model.fs[p].thermal_demand_mixer.mixed_state[0.0].eq_enth_flow_phase[
                "Liq"
            ].deactivate()
            model.fs[p].thermal_demand_mixer.mixed_state[0.0].enth_flow_phase[
                "Liq"
            ].fix(0)
            model.fs[p].thermal_demand_mixer.from_direct_state[0.0].enth_flow_phase[
                "Liq"
            ].fix(0)
            model.fs[p].thermal_demand_mixer.from_tank_state[0.0].enth_flow_phase[
                "Liq"
            ].fix(0)

            # m.fs[p].tank_mixer.from_load_state[0.0].eq_enth_flow_phase['Liq'].deactivate()
            # m.fs[p].tank_mixer.from_load_state[0.0].enth_flow_phase['Liq'].fix(0)

    m2 = degrees_of_freedom(model)
    assert m1 == m2
    return model


def solve_model(model, tol):
    """Fixing currently unused variables"""
    assert_units_consistent(model)
    # assert False
    solver = get_solver()
    solver.options["nlp_scaling_method"] = "user-scaling"
    solver.options["max_iter"] = 3000
    solver.options["tol"] = tol

    result = solver.solve(model, tee=g_solver_output)

    # output = StringIO()
    # with LoggingIntercept(output, "pyomo.util.infeasible", logging.INFO):
    #     log_infeasible_constraints(m)
    # print(output.getvalue().splitlines())

    assert_optimal_termination(result)
    if result.Solver[0]["Termination condition"] == "optimal":
        return result
    else:
        output = StringIO()
        with LoggingIntercept(output, "pyomo.util.infeasible", logging.INFO):
            log_infeasible_constraints(model)
        # print(output.getvalue().splitlines())
        for i in range(0, len(output.getvalue().splitlines())):
            print(output.getvalue().splitlines()[i])


def solve_model_baron(model):
    """Fixing currently unused variables"""
    assert_units_consistent(model)
    solver = SolverFactory("baron")
    solver.options["maxTime"] = 3000
    result = solver.solve(model, tee=True)
    # result = SolverFactory('baron').solve(model, options={'MaxTime': 1000, 'contol':1e-6})

    output = StringIO()
    with LoggingIntercept(output, "pyomo.util.infeasible", logging.INFO):
        log_infeasible_constraints(model)
    print(output.getvalue().splitlines())

    assert_optimal_termination(result)
    if result.Solver[0]["Termination condition"] == "optimal":
        return result
    else:
        output = StringIO()
        with LoggingIntercept(output, "pyomo.util.infeasible", logging.INFO):
            log_infeasible_constraints(model)
        # print(output.getvalue().splitlines())
        for line in output.getvalue().splitlines():
            print(line)


def create_optimization_problem(model):
    for p in model.periods:
        model.fs[p].gas_boiler.capacity_power.unfix()
        model.fs[p].heat_pump.capacity_power.unfix()
        model.fs[p].hw_tank.capacity_energy.unfix()
        model.fs[p].PV.Area.unfix()
    return model


def system_design_information(model):
    design_characteristics = {}
    design_characteristics["PV Area (m2)"] = value(model.fs[0].PV.Area)
    design_characteristics["PV capacity (kW)"] = value(
        model.costing.cc.pv_capacity_conversion * model.fs[0].PV.Area
    )
    design_characteristics["Battery capacity (kWh)"] = value(
        model.fs[0].battery.capacity_energy
    )
    design_characteristics["Battery capacity (kW)"] = value(
        model.fs[0].battery.capacity_power
    )
    # design_characteristics['Tank capacity (kWh)'] = value(model.fs[0].hw_tank.capacity_energy)
    design_characteristics["Tank volume (m3)"] = value(model.fs[0].hw_tank.V_tank)
    design_characteristics["Tank water mass (kg)"] = value(model.fs[0].hw_tank.M_tank)
    design_characteristics["Heat pump (kW)"] = value(
        model.fs[0].heat_pump.capacity_power
    )
    design_characteristics["Gas boiler (kW)"] = value(
        model.fs[0].gas_boiler.capacity_power
    )
    design_characteristics["Emissions (M_kg/yr)"] = value(
        model.emissions.total_annual_emissions
    )
    design_characteristics["Imported energy (MWh/a)"] = value(model.energies.tot_energy)
    design_characteristics["Capital cost (M_USD)"] = value(
        model.costing.cc.total_capital_cost
    )
    design_characteristics["Operating cost (M_USD/yr)"] = value(
        model.costing.oc.total_operating_cost
    )
    design_characteristics["Annualized cost (M_USD/yr)"] = value(
        model.costing.total_annualized_cost
    )
    design_characteristics["Tank capacity (kWh)"] = (
        value(model.fs[0].hw_tank.M_tank)
        * value(model.fs[0].hw_tank.cp)
        * value(model.fs[0].hw_tank.T[0].ub - model.fs[0].hw_tank.T_ref)
        / 3600
    )

    return design_characteristics


def extract_and_save_in_background(m, fname, res):
    print("Saving results in background...")
    var_json = extract_results_old(m, fname)
    print("Saving done...")
    res.put(var_json)


def setup_model(m, timesteps=None, load_kw=None):
    """Create and solve square system.
    Then add costing model to square system case and re-solve.
    """
    # square system
    m = instantiate_model(m, load_kw)
    m = instantiate_pv_with_data(m)
    m = add_upper_bounds(m, load_kw)
    m = add_battery_charging_constraints(m)
    m = deactivate_enthapy_constraints(m)
    m = add_scaling(m)
    dof_prefixing = degrees_of_freedom(m)
    _log.info(f"Degrees of freedom before fixing anything: {dof_prefixing}")

    m = create_steady_state_problem(m)

    # add costing
    m = add_costing(m, no_timesteps=timesteps)
    m = cost_scaling(m)
    return dof_prefixing


def diagram(m, output_file="", diagram_class=None):
    """Write a diagram to a file.

    Returns:
       (pyomo.Block) The built and initialized model.
    """
    _log.info("diagram.begin")

    output_path = Path(output_file)

    for p in m.periods:
        flowsheet = m.fs[p]
        break

    _log.debug("diagram: create diagram")
    conn = Connectivity(input_model=flowsheet)
    dia = diagram_class(conn)
    _log.info(f"diagram.write.begin: file='{output_path}'")
    dia.write(output_path)
    _log.info(f"diagram.write.end: file='{output_path}'")
    _log.info("diagram.end")
    return m


def run(m, timesteps=None, load_kw=None, dof_prefixing=None, emissions_obj=None):
    """Run (solve the model)."""
    _log.info(f"run.begin: num_timesteps={timesteps} load={load_kw} kW")

    assert degrees_of_freedom(m) == 0

    _log.info("run.solve.begin")
    try:
        res = solve_model(m, tol=1e-8)
    except RuntimeError as err:
        _log.error(f"run.end: Initial solve failed, error='{err}'")
        return -1
    _log.info("run.solve.end")

    # Create optimization problem and re-solve
    m = create_optimization_problem(m)
    assert degrees_of_freedom(m) == dof_prefixing
    res = solve_model(m, tol=1e-7)

    m = add_total_energies(m, no_timesteps=timesteps)
    m = energy_scaling(m)
    _log.info("run.solve-energy-case.begin")
    try:
        res = solve_model(m, tol=1e-8)
    except RuntimeError as err:
        _log.error(
            f"run.solve-energy-case.end: Initial imported energy case failed, error='{err}'"
        )
        return -1
    _log.info("run.solve-energy-case.end")

    # Add emissions model to optimization problem and re-solve
    m = add_emissions(m, no_timesteps=timesteps)
    m = emissions_scaling(m)
    _log.info("run.solve-emiss1.begin")
    try:
        res = solve_model(m, tol=1e-8)
    except RuntimeError as err:
        _log.error(
            f"run.solve-emiss1.end: Initial emissions solve failed, error='{err}'"
        )
        return -1
    _log.info("run.solve-emiss1.end")
    emissions_ub = math.floor(value(m.emissions.total_annual_emissions))  # * 10) / 10
    print(f"\nEmissions upper bound: {emissions_ub}")
    base_emissions = round(value(m.emissions.total_annual_emissions), 4)
    base_energy = round(value(m.energies.tot_energy))
    base_emissions_design = system_design_information(m)

    current_dir = Path(__file__).resolve().parent
    results_dir = current_dir / "results"
    opt_cost_path = results_dir / r"optimal_cost_case_final.gz"
    _log.info(f"saving optimal cost case model file='{opt_cost_path}'")
    to_json(m, fname=opt_cost_path, gz=True, human_read=True)
    _log.info(f"saved optimal cost case model")

    if emissions_obj:
        # 2. Make emissions the objective of optimization problem
        m.objective = Objective(expr=m.emissions.total_annual_emissions)
        _log.info("run.solve-emiss2.begin")
        try:
            res = solve_model(m, tol=1e-8)
        except RuntimeError as err:
            _log.error(
                f"run.solve-emiss2.end: Emissions objective solve failed, error='{err}'"
            )
            return -1
        _log.info("run.solve-emiss2.end")
        emissions_lb = math.ceil(
            value(m.emissions.total_annual_emissions)
        )  # * 10) / 10
        print(f"\nEmissions lower bound: {emissions_lb}")
        best_case_emissions = round(value(m.emissions.total_annual_emissions), 4)
        best_case_emissions_design = system_design_information(m)

        opt_emiss_path = results_dir / r"optimal_emissions_case_final.gz"
        _log.info(f"saving optimal emissions case model file='{opt_emiss_path}'")
        to_json(
            m,
            fname=opt_emiss_path,
            gz=True,
            human_read=True,
        )
        _log.info(f"saved optimal emissions case model")

        # 3. Add emissions as constraints and re-solve each case
        m.objective = Objective(expr=m.costing.total_annualized_cost)
        if timesteps < 8760:
            _log.warning("Reducing emissions limits for run under 1 year")
            emissions_limits_range = [emissions_lb, 3, 5, 7, emissions_ub]
        else:
            emissions_limits_range = [
                emissions_lb,
                1.25,
                1.5,
                1.75,
                2,
                3,
                5,
                7,
                emissions_ub,
            ]
        _log.info(f"run for emissions limits={emissions_limits_range}")
        system_dict = {}
        # base_emissions = round(value(m.emissions.total_annual_emissions), 4)
        # system_dict[base_emissions] = system_design_information(m)
        system_dict[base_emissions] = base_emissions_design
        system_dict[best_case_emissions] = best_case_emissions_design
        emiss_limits_paths = []
        for emissions_limit in emissions_limits_range:
            print(f"\nRunning emissions case...{emissions_limit}")
            m.emissions.annual_emissions_limit.value = (
                emissions_limit * pyunits.HT_kg / pyunits.yr
            )  # pyunits.M_kg / pyunits.yr
            _log.info(f"run.solve-emiss-case.begin limit={emissions_limit}")
            try:
                res = solve_model(m, tol=1e-8)
            except RuntimeError as err:
                _log.error(
                    f"run.solve-emiss-case.end: Emissions case solve failed, error='{err}'"
                )
                return -1
            _log.info("run.solve-emiss-case.end")
            fname = r"emissions_case_" + str(emissions_limit) + "HTkg_yr.gz"
            emissions_limits_path = results_dir / fname
            to_json(m, fname=emissions_limits_path, gz=True, human_read=True)
            system_dict[emissions_limit] = system_design_information(m)
            emiss_limits_paths.append(emissions_limits_path)

        xv = pd.DataFrame(system_dict).T
        # xv["Tank capacity (kWh)"] = (
        #     xv["Tank water mass (kg)"]
        #     * value(m.fs[0].hw_tank.cp)
        #     * value(m.fs[0].hw_tank.T[0].ub - m.fs[0].hw_tank.T_ref)
        #     / 3600
        # )
        tradeoffs_path = results_dir / "tradeoffs_results.csv"
        xv.to_csv(tradeoffs_path)
        _log.info(f"run.end: results={tradeoffs_path}")

        print_output_files(
            {
                "optimal cost case": opt_cost_path,
                "optimal emissions case": opt_emiss_path,
                "tradeoffs": tradeoffs_path,
                "emissions limits cases": emiss_limits_paths,
            }
        )
    else:
        m_clone = m.clone()
        m_clone.objective = Objective(expr=m_clone.energies.tot_energy)
        _log.info("run.solve-energies.begin")
        try:
            res = solve_model(m_clone, tol=1e-8)
        except RuntimeError as err:
            _log.error(
                f"run.solve-energies.end: Imorted energy objective solve failed, error='{err}'"
            )
            return -1
        _log.info("run.solve-energies.end")
        energy_lb = value(m_clone.energies.tot_energy)
        print(f"\nEnergy lower bound: {energy_lb}")
        best_case_energy = round(value(m_clone.energies.tot_energy))
        best_case_emissions_design = system_design_information(m_clone)

        opt_energy_path = results_dir / r"optimal_imported_energy_case_final.gz"
        _log.info(f"saving optimal imported energy case model file='{opt_energy_path}'")
        to_json(
            m_clone,
            fname=opt_energy_path,
            gz=True,
            human_read=True,
        )
        _log.info(f"saved optimal imported energy case model")

        energy_limits_range = [
            250,
            500,
            750,
            1000,
            1250,
            1500,
            1750,
            2000,
            2500,
            3000,
            3499,
            4000,
            4500,
            5000,
        ]
        _log.info(f"run for imported energy limits={energy_limits_range}")

        system_dict = {}
        system_dict[base_energy] = base_emissions_design
        system_dict[best_case_energy] = best_case_emissions_design

        energy_limits_paths = []

        for imported_energy_limit in energy_limits_range:
            print(f"\nRunning imported energy case...{imported_energy_limit}")
            m.energies.tot_energy.setub(
                imported_energy_limit * pyunits.MWh / pyunits.yr
            )
            _log.info(f"run.solve-energy-case.begin limit={imported_energy_limit}")
            try:
                res = solve_model(m, tol=1e-8)
            except RuntimeError as err:
                _log.error(
                    f"run.solve-energy-case.end: Imported energy case solve failed, error='{err}'"
                )
                return -1
            _log.info("run.solve-energy-case.end")
            fname = r"imported_energy_case_" + str(imported_energy_limit) + "MWh_yr.gz"
            energy_limits_path = results_dir / fname
            to_json(m, fname=energy_limits_path, gz=True, human_read=True)
            system_dict[imported_energy_limit] = system_design_information(m)
            energy_limits_paths.append(energy_limits_path)

        xv = pd.DataFrame(system_dict).T
        tradeoffs_path = results_dir / "imported_energy_tradeoffs_results.csv"
        xv.to_csv(tradeoffs_path)
        _log.info(f"run.end: results={tradeoffs_path}")

        print_output_files(
            {
                "optimal cost case": opt_cost_path,
                "optimal imported energy case": opt_energy_path,
                "tradeoffs": tradeoffs_path,
                "emissions limits cases": energy_limits_paths,
            }
        )
    return 0


def print_output_files(fmap: Dict[str, Path | List[Path]]):
    """Print a neat little table of the generated output files.
    Note that this output is valid YAML.
    """
    print("ResultFiles:")
    indent = " " * 4
    for k, v in fmap.items():
        if isinstance(v, Path):
            print(f"{indent}{k}: {v}")
        else:  # List[Path]
            print(f"{indent}{k}:")
            for p in v:
                print(f"{indent}{indent}- {p}")


def main():
    global g_quiet, g_solver_output
    p = argparse.ArgumentParser()
    default_days = 8760 // 24
    p.add_argument(
        "--days",
        type=int,
        default=default_days,
        help=f"Number of days to run the model (default={default_days})",
    )
    p.add_argument(
        "--diagram",
        default=None,
        help=f"Before running, write a Mermaid or D2 diagram in the given file",
    )
    diagram_types = ["mermaid", "d2"]
    default_diagram_type = diagram_types[0]
    p.add_argument(
        "--diagram-type",
        default=default_diagram_type,
        choices=diagram_types,
        help=f"Type of diagram (default={default_diagram_type})",
    )
    p.add_argument("--load", type=int, default=1000, help="Load in kW (default=1000)")
    p.add_argument(
        "--no-tee",
        "-T",
        action="store_true",
        default=False,
        help="Do not print ('tee') the solver output to the console",
    )
    p.add_argument(
        "--no-solve", "-S", action="store_true", help="Don't attempt to solve the model"
    )
    p.add_argument(
        "--emissions_obj",
        action="store_true",
        help=f"Boolean for choosing second objective: emissions (True) or imported energy (False). (default=False)",
    )
    add_log_options(p)
    args = p.parse_args()
    g_quiet = process_log_options(_log, args)
    g_solver_output = not args.no_tee
    model_kw = {
        "timesteps": args.days * 24,
        "load_kw": args.load,
    }
    m = build_model(**model_kw)
    model_kw["dof_prefixing"] = setup_model(m, **model_kw)
    model_kw["emissions_obj"] = args.emissions_obj
    status_code = 0
    if args.diagram is not None:
        klass = (Mermaid, D2)[diagram_types.index(args.diagram_type)]
        m = diagram(m, output_file=args.diagram, diagram_class=klass)
    if not args.no_solve:
        status_code = run(m, **model_kw)
    return status_code


if __name__ == "__main__":
    sys.exit(main())
