import sys
from pandas import DataFrame
from collections import OrderedDict
import textwrap
from copy import deepcopy

# Import Pyomo libraries
from pyomo.environ import Var, Param, NonNegativeReals, units as pyunits, value, Block
from pyomo.network import Port
from pyomo.common.config import ConfigBlock, ConfigValue, In

# Import IDAES cores
from idaes.core import declare_process_block_class, UnitModelBlockData
from idaes.core.util.config import is_physical_parameter_block
from idaes.core.solvers import (
    get_solver,
)  # from watertap.core.solvers import get_solver
from idaes.core.scaling import CustomScalerBase, set_scaling_factor, get_scaling_factor
from idaes.core.util.tables import (
    stream_table_dataframe_to_string,
    create_stream_table_dataframe,
)
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_activated_constraints,
    number_activated_blocks,
)
import idaes.logger as idaeslog

_log = idaeslog.getLogger(__name__)


class GasBoilerScaler(CustomScalerBase):

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

        self.set_variable_scaling_factor(
            model.Q_theoretical[0], 1e-5, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.Q_actual[0],
            self.get_scaling_factor(model.Q_theoretical[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.capacity_power,
            self.get_scaling_factor(model.Q_theoretical[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(model.flow_vol_gas[0], 1, overwrite=overwrite)

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

        for j, c in model.eq_actual_heat.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_theoretical_heat.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_p_con1.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in[0].pressure,
                overwrite=overwrite,
            )

        for j, c in model.eq_power_bound_out.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        # for j, c in model.eq_power_bound_out.items():
        #     self.scale_constraint_by_component(c, model.Q_theoretical[0], overwrite=overwrite,)

        for j, c in model.eq_hot_water_production.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_f_con1.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in[0].flow_mass_phase_comp["Liq", "H2O"],
                overwrite=overwrite,
            )


@declare_process_block_class("DetailedGasBoiler", doc="Boiler model")
class GasBoilerData(UnitModelBlockData):
    """
    Unit model for gas boiler
    """

    default_scaler = GasBoilerScaler

    CONFIG = ConfigBlock()
    CONFIG.declare(
        "dynamic",
        ConfigValue(
            domain=In([False]),
            default=False,
            description="Dynamic model flag - must be False",
            doc="""Boiler does not support dynamic models, thus this must be False.""",
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

        # Design variables and parameters
        self.capacity_power = Var(
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 50e3),
            doc="Nameplate power of boiler",
            units=pyunits.kW,
        )

        self.eta = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=0.90,
            doc="Boilerfficiency, (0, 1]",
        )

        self.HHV = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=35396,
            units=pyunits.kJ / pyunits.m**3,
            doc="HHV for natural gas",
        )

        self.LHV = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=31670,
            units=pyunits.kJ / pyunits.m**3,
            doc="LHV for natural gas",
        )

        self.cp = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=4.184,
            units=pyunits.kJ / (pyunits.kg * pyunits.K),
            doc="Heat capacity of water",
        )

        self.Q_theoretical = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1000.0,
            bounds=(0, 100e3),
            doc="Theoretical heat output of boiler (kW)",
            units=pyunits.kW,
        )

        self.Q_actual = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1000.0,
            bounds=(0, 50e3),
            doc="Theoretical heat output of boiler (kW)",
            units=pyunits.kW,
        )

        self.flow_vol_gas = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 100),
            doc="Natural gas volume in m3/s",
            units=pyunits.m**3 / pyunits.s,
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

        self.gas_inlet = Port(noruleinit=True, doc="A port for gas inflow")
        self.gas_inlet.add(self.flow_vol_gas, "Natural gas volume in")
        self.gas_inlet.add(self.HHV, "Gas heating value")

        # Gas boiler theoretical energy generation
        @self.Constraint(self.flowsheet().config.time)
        def eq_theoretical_heat(b, t):
            return b.Q_theoretical[t] - b.HHV * b.flow_vol_gas[t] == 0

        # Gas boiler actual energy generation
        @self.Constraint(self.flowsheet().config.time)
        def eq_actual_heat(b, t):
            return b.Q_actual[t] - b.eta * b.Q_theoretical[t] == 0

        # Gas boiler actual energy generation
        @self.Constraint(self.flowsheet().config.time)
        def eq_hot_water_production(b, t):
            return (
                b.Q_actual[t]
                - b.properties_in[t].flow_mass_phase_comp["Liq", "H2O"]
                * b.cp
                * (b.properties_out[t].temperature - b.properties_in[t].temperature)
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_power_bound_out(b, t):
            return b.Q_actual[t] - b.capacity_power <= 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_p_con1(b, t):
            return b.properties_in[0].pressure - b.properties_out[0].pressure == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_f_con1(b, t):
            return (
                b.properties_in[t].flow_mass_phase_comp["Liq", "H2O"]
                == b.properties_out[t].flow_mass_phase_comp["Liq", "H2O"]
            )

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

        fixed_flag = False
        for t in self.flowsheet().config.time:
            if self.Q_theoretical[t].fixed:
                fixed_flag = True
                continue
            else:
                self.Q_theoretical[t].fix()

        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="unit")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="unit")
        opt = get_solver(solver=solver, options=optarg)
        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info("Gas boiler status status {}.".format(idaeslog.condition(res)))

        if fixed_flag is False:
            self.Q_theoretical[t].unfix()
