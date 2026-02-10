import sys
from pandas import DataFrame
from collections import OrderedDict
import textwrap
from copy import deepcopy

# Import Pyomo libraries
from pyomo.environ import Var, Param, NonNegativeReals, units as pyunits, value
from pyomo.network import Port
from pyomo.common.config import ConfigBlock, ConfigValue, In

# Import IDAES cores
from idaes.core import declare_process_block_class, UnitModelBlockData
from idaes.core.util.config import is_physical_parameter_block
from watertap.core.solvers import get_solver
from idaes.core.scaling import CustomScalerBase, set_scaling_factor, get_scaling_factor
from idaes.core.util.constants import Constants
from idaes.core.util.tables import stream_table_dataframe_to_string
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_activated_constraints,
    number_activated_blocks,
)
import idaes.logger as idaeslog

_log = idaeslog.getLogger(__name__)


class TankStorageScaler(CustomScalerBase):

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        # Call scaling methods for sub-models
        self.call_submodel_scaler_method(
            submodel=model.properties_in,
            method="variable_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.propagate_state_scaling(
            target_state=model.properties_out,
            source_state=model.properties_in,
            overwrite=overwrite,
        )

        self.call_submodel_scaler_method(
            submodel=model.properties_out,
            method="variable_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )

        self.set_variable_scaling_factor(model.V_tank, 1e-3, overwrite=overwrite)
        self.set_variable_scaling_factor(model.A_tank, 1e-3, overwrite=overwrite)
        self.set_variable_scaling_factor(
            model.M_tank, get_scaling_factor(model.V_tank) * 1e-3, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.V[0], get_scaling_factor(model.V_tank), overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.M[0], get_scaling_factor(model.M_tank), overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.initial_state_mass,
            get_scaling_factor(model.M_tank),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(model.Q_in[0], 1e-3, overwrite=overwrite)
        self.set_variable_scaling_factor(
            model.Q_out[0], get_scaling_factor(model.Q_in[0]), overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.Q_elect[0], get_scaling_factor(model.Q_in[0]), overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.Q_loss[0],
            get_scaling_factor(model.Q_in[0]) * 1e2,
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.T[0],
            get_scaling_factor(model.properties_in[0].temperature),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.initial_state_temperature,
            get_scaling_factor(model.properties_in[0].temperature),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(model.Diameter, 1e-1, overwrite=overwrite)
        self.set_variable_scaling_factor(model.Height, 1e-1, overwrite=overwrite)
        self.set_variable_scaling_factor(
            model.storage_level[0], 1e-4, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.capacity_energy,
            get_scaling_factor(model.storage_level[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.initial_state_energy,
            get_scaling_factor(model.storage_level[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.initial_state_of_charge[0], 1, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.state_of_charge[0], 1, overwrite=overwrite
        )

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        # Call scaling methods for sub-models
        self.call_submodel_scaler_method(
            submodel=model.properties_in,
            method="constraint_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_out,
            method="constraint_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )

        for j, c in model.eq_mass_balance.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_energy_in.items():
            self.scale_constraint_by_component(
                c,
                model.Q_in[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_energy_out.items():
            self.scale_constraint_by_component(
                c,
                model.Q_out[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_tank_losses.items():
            self.scale_constraint_by_component(
                c,
                model.Q_loss[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_storage_level.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_initial_storage_level.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_temperature_equality.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in[0].temperature,
                overwrite=overwrite,
            )

        for j, c in model.eq_energy_bounds.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_water_volume_bounds.items():
            self.scale_constraint_by_component(
                c,
                model.V_tank,
                overwrite=overwrite,
            )

        for j, c in model.eq_water_mass_bounds.items():
            self.scale_constraint_by_component(
                c,
                model.M_tank,
                overwrite=overwrite,
            )

        # for j, c in model.eq_mass_density_relationship.items():
        #     self.scale_constraint_by_component(c, model.M_tank, overwrite=overwrite,)

        for j, c in model.eq_mass_density_capacity_relationship.items():
            self.scale_constraint_by_component(
                c,
                model.M_tank,
                overwrite=overwrite,
            )

        for j, c in model.eq_mass_density_relationship.items():
            self.scale_constraint_by_component(
                c,
                model.V_tank,
                overwrite=overwrite,
            )

        # for j, c in model.eq_mass_density_capacity_relationship.items():
        #     self.scale_constraint_by_component(c, model.V_tank, overwrite=overwrite,)

        for j, c in model.eq_state_of_charge_relationship.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_tank_soc_initial.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_tank_volume.items():
            self.scale_constraint_by_component(
                c,
                model.V_tank,
                overwrite=overwrite,
            )

        for j, c in model.eq_tank_area.items():
            self.scale_constraint_by_component(
                c,
                model.A_tank,
                overwrite=overwrite,
            )

        for j, c in model.eq_h_to_d_ratio.items():
            self.scale_constraint_by_component(
                c,
                model.initial_state_of_charge[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_tank_energy_accumulation.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_tank_pressure.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in[0].pressure,
                overwrite=overwrite,
            )


@declare_process_block_class("TankStorage", doc="Hot water tank model")
class TankStorageData(UnitModelBlockData):
    """
    Unit model for battery storage
    """

    default_scaler = TankStorageScaler

    CONFIG = ConfigBlock()
    CONFIG.declare(
        "dynamic",
        ConfigValue(
            domain=In([False]),
            default=False,
            description="Dynamic model flag - must be False",
            doc="""Battery does not support dynamic models, thus this must be False.""",
        ),
    )
    CONFIG.declare(
        "has_holdup",
        ConfigValue(
            default=False,
            domain=In([False]),
            description="Holdup construction flag",
            doc="""Battery does not have defined volume, thus this must be False.""",
        ),
    )

    CONFIG.declare(
        "property_package",
        ConfigValue(
            domain=is_physical_parameter_block,
            description="Property package to use for control volume",
            doc="""Property parameter object used to define property calculations""",
        ),
    )

    CONFIG.declare(
        "property_package_args",
        ConfigBlock(
            implicit=True,
            description="Arguments to use for constructing property packages",
            doc="""A ConfigBlock with arguments to be passed to a property block(s)
    and used when constructing these,
    **default** - None.
    **Valid values:** {
    see property package for documentation.}""",
        ),
    )

    def build(self):
        super().build()

        self.U = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=0.4,
            units=pyunits.W / (pyunits.m**2 * pyunits.K),
            doc="Overall heat transfer coefficient",
        )

        self.H_to_D_ratio = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=1,
            units=pyunits.dimensionless,
            doc="Ratio of the tank height to its diameter",
        )

        self.T_ref = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=70 + 273.15,
            units=pyunits.K,
            doc="Reference temperature for tank. Set at lowest allowable operating temperature, 50C",
        )

        self.T_amb = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=20 + 273.15,
            units=pyunits.K,
            doc="Ambient temperature in K",
        )

        self.rho = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=1000,
            units=pyunits.kg / pyunits.m**3,
            doc="Water density",
        )

        self.cp = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=4.184,
            units=pyunits.kJ / (pyunits.kg * pyunits.K),
            doc="Heat capacity of water",
        )

        self.tank_pressure = Param(
            within=NonNegativeReals,
            initialize=101325,
            mutable=True,
            units=pyunits.Pa,
            doc="Tank Pressure in Pa",
        )

        # Design variables
        self.dt = Param(
            within=NonNegativeReals,
            initialize=1,
            doc="Time step for converting between electricity power flows and stored energy",
            units=pyunits.hr,
        )

        self.V_tank = Var(
            within=NonNegativeReals,
            initialize=100,
            bounds=(0, 1e5),
            doc="Tank volume",
            units=pyunits.m**3,
        )

        self.A_tank = Var(
            within=NonNegativeReals,
            initialize=100,
            bounds=(0, 1e5),
            doc="Tank Area",
            units=pyunits.m**2,
        )

        self.Diameter = Var(
            within=NonNegativeReals,
            initialize=1,
            bounds=(0, 50),
            doc="Tank diameter in m",
            units=pyunits.m,
        )

        self.Height = Var(
            within=NonNegativeReals,
            initialize=1,
            bounds=(0, 50),
            doc="Tank height in m",
            units=pyunits.m,
        )

        self.V = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 1e5),
            doc="Volume of water in tank at time t",
            units=pyunits.m**3,
        )

        self.M_tank = Var(
            within=NonNegativeReals,
            initialize=132,
            bounds=(0, 1e7),
            doc="Maximum tank capacity for water in Kg",
            units=pyunits.kg,
        )

        self.M = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 1e7),
            doc="Mass of water in tank at time t",
            units=pyunits.kg,
        )

        self.T = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=75 + 273.15,
            bounds=(50 + 273.15, 90 + 273.15),
            units=pyunits.K,
            doc="Temperature of water in tank in K",
        )

        self.initial_state_mass = Var(
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 1e7),
            doc="Mass state of charge at t - 1",
            units=pyunits.kg,
        )

        self.initial_state_temperature = Var(
            within=NonNegativeReals,
            initialize=75 + 273.15,
            bounds=(50 + 273.15, 90 + 273.15),
            units=pyunits.K,
            doc="Temperature of water in tank in K",
        )

        self.initial_state_energy = Var(
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 200e3),
            doc="Energy state of charge at t - 1",
            units=pyunits.kWh,
        )

        self.Q_in = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1e3,
            doc="Heat added to tank from input stream",
            bounds=(0, 50e3),
            units=pyunits.kW,
        )

        self.Q_out = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 50e3),
            doc="Heat removed from tank via output stream",
            units=pyunits.kW,
        )

        self.Q_loss = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 50e3),
            doc="Tank heat loss to atmosphere",
            units=pyunits.kW,
        )

        self.Q_elect = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 50e3),
            doc="External heat addition, e.g. through electric heaters",
            units=pyunits.kW,
        )

        self.initial_state_of_charge = Var(
            self.flowsheet().config.time,
            initialize=0.5,
            bounds=(0, 1),
            doc="Tank state of charge at t-1",
            units=pyunits.dimensionless,
        )

        self.state_of_charge = Var(
            self.flowsheet().config.time,
            initialize=0.5,
            bounds=(0, 1),
            doc="Tank state of charge",
            units=pyunits.dimensionless,
        )

        self.storage_level = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 200e3),
            doc="Tank state of charge (J)",
            units=pyunits.kWh,
        )

        self.capacity_energy = Var(
            within=NonNegativeReals,
            initialize=1e3,
            bounds=(0, 200e3),
            doc="Capacity of tank storage",
            units=pyunits.kWh,
        )

        # Ports
        tmp_dict = dict(**self.config.property_package_args)
        tmp_dict["has_phase_equilibrium"] = False
        tmp_dict["parameters"] = self.config.property_package
        tmp_dict["defined_state"] = True  # inlet block is an inlet
        self.properties_in = self.config.property_package.state_block_class(
            self.flowsheet().config.time,
            doc="Material properties of liquid inlet",
            **tmp_dict,
        )

        # Add outlet and waste block
        tmp_dict["defined_state"] = False  # outlet and waste block is not an inlet
        self.properties_out = self.config.property_package.state_block_class(
            self.flowsheet().config.time,
            doc="Material properties of liquid outlet",
            **tmp_dict,
        )

        self.add_port(name="inlet_water", block=self.properties_in)
        self.add_port(name="outlet_water", block=self.properties_out)

        self.power_in = Port(noruleinit=True, doc="A port for electricity inflow")
        self.power_in.add(self.Q_elect, "electricity")

        ############################################################################################################
        #                                   MODEL EQUATIONS
        ############################################################################################################

        @self.Constraint(self.flowsheet().config.time)
        def eq_mass_balance(b, t):
            return b.M[t] == b.initial_state_mass + pyunits.convert(
                b.dt, to_units=pyunits.s
            ) * (
                b.properties_in[t].flow_mass_phase_comp["Liq", "H2O"]
                - b.properties_out[t].flow_mass_phase_comp["Liq", "H2O"]
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_energy_in(b, t):
            return (
                b.properties_in[t].flow_mass_phase_comp["Liq", "H2O"]
                * b.cp
                * (b.properties_in[t].temperature - b.T_ref)
            ) - b.Q_in[t] == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_energy_out(b, t):
            return (
                b.properties_out[t].flow_mass_phase_comp["Liq", "H2O"]
                * b.cp
                * (b.properties_out[t].temperature - b.T_ref)
            ) - b.Q_out[t] == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_tank_losses(b, t):
            # return pyunits.convert((b.U * b.A_tank * (b.T[t] - b.T_amb)), to_units=pyunits.kW) - b.Q_loss[t] == 0
            return (
                pyunits.convert(
                    (b.U * b.A_tank * (b.T[t] - b.T_amb) * b.state_of_charge[t]),
                    to_units=pyunits.kW,
                )
                - b.Q_loss[t]
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_storage_level(b, t):
            return (
                pyunits.convert(
                    (b.M[t] * b.cp * (b.T[t] - b.T_ref)), to_units=pyunits.kWh
                )
                - b.storage_level[t]
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_initial_storage_level(b, t):
            return (
                pyunits.convert(
                    (
                        b.initial_state_mass
                        * b.cp
                        * (b.initial_state_temperature - b.T_ref)
                    ),
                    to_units=pyunits.kWh,
                )
                - b.initial_state_energy
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_temperature_equality(b, t):
            return b.properties_out[t].temperature == b.T[t]

        @self.Constraint(self.flowsheet().config.time)
        def eq_energy_bounds(b, t):
            return b.storage_level[t] <= b.capacity_energy

        @self.Constraint(self.flowsheet().config.time)
        def eq_water_volume_bounds(b, t):
            return b.V[t] - b.V_tank <= 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_water_mass_bounds(b, t):
            return b.M[t] - b.M_tank <= 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_mass_density_relationship(b, t):
            return (b.M[t] / b.rho) - b.V[t] == 0

        # @self.Constraint(self.flowsheet().config.time)
        # def eq_mass_density_relationship(b, t):
        #     return b.M[t] - b.rho * b.V[t] == 0

        # @self.Constraint()
        # def eq_mass_density_capacity_relationship(b):
        #     return (b.M_tank / b.rho) - b.V_tank == 0
        @self.Constraint()
        def eq_mass_density_capacity_relationship(b):
            return b.M_tank - b.rho * b.V_tank == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_state_of_charge_relationship(b, t):
            return b.storage_level[t] - b.capacity_energy * b.state_of_charge[t] == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_tank_soc_initial(b, t):
            return (
                b.initial_state_energy
                - b.initial_state_of_charge[t] * b.capacity_energy
                == 0
            )

        @self.Constraint()
        def eq_tank_volume(b, t):
            return b.V_tank - 0.25 * Constants.pi * b.Diameter**2 * b.Height == 0

        @self.Constraint()
        def eq_tank_area(b, t):
            return (
                b.A_tank - Constants.pi * b.Diameter * ((0.5 * b.Diameter) + b.Height)
                == 0
            )

        @self.Constraint()
        def eq_h_to_d_ratio(b, t):
            return b.Height - b.H_to_D_ratio * b.Diameter == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_tank_energy_accumulation(b, t):
            return b.storage_level[t] - b.initial_state_energy == b.dt * (
                b.Q_in[t] - b.Q_out[t] + b.Q_elect[t] - b.Q_loss[t]
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_tank_pressure(b, t):
            return b.properties_out[t].pressure - b.tank_pressure == 0

        # @self.Constraint(self.flowsheet().config.time)
        # def eq_try_complementarity(b, t):
        #     return b.Q_in[t] * b.Q_out[t] == 0

    def initialize_build(
        self, state_args=None, outlvl=idaeslog.NOTSET, solver=None, optarg=None
    ):

        # Set solver options
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="properties")

        # Create solver
        opt = get_solver(solver=solver, options=optarg)

        self.properties_in.initialize(
            outlvl=outlvl,
            optarg=optarg,
            solver=solver,
            state_args=state_args,
            # hold_state=True,
        )

        if state_args is None:
            self.state_args = state_args = {}
            state_dict = self.properties_in[
                self.flowsheet().config.time.first()
            ].define_port_members()

            for k in state_dict.keys():
                if state_dict[k].is_indexed():
                    state_args[k] = {}
                    for m in state_dict[k].keys():
                        state_args[k][m] = state_dict[k][m].value
                else:
                    state_args[k] = state_dict[k].value

        state_args_out = deepcopy(state_args)

        self.properties_out.initialize(
            outlvl=outlvl,
            optarg=optarg,
            solver=solver,
            state_args=state_args_out,
        )

        # solve unit
        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info("Tank initialization status {}.".format(idaeslog.condition(res)))
