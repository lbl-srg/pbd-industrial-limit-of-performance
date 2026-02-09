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
import watertap_solvers  # watertap.core.plugins.solvers
from idaes.core.scaling import CustomScalerBase, set_scaling_factor, get_scaling_factor
from idaes.core.util.config import is_physical_parameter_block
from idaes.core.solvers import (
    get_solver,
)  # from watertap.core.solvers import get_solver # from idaes.core.solvers import get_solver
import idaes.core.util.scaling as iscale
from idaes.core.util.tables import stream_table_dataframe_to_string
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_activated_constraints,
    number_activated_blocks,
)
import idaes.logger as idaeslog

_log = idaeslog.getLogger(__name__)


class HeatPumpScaler(CustomScalerBase):

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        # Call scaling methods for sub-models
        self.call_submodel_scaler_method(
            submodel=model.properties_in_hotside,
            method="variable_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_in_coldside,
            method="variable_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.propagate_state_scaling(
            target_state=model.properties_out_hotside,
            source_state=model.properties_in_hotside,
            overwrite=overwrite,
        )
        self.propagate_state_scaling(
            target_state=model.properties_out_coldside,
            source_state=model.properties_in_coldside,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_out_hotside,
            method="variable_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_out_coldside,
            method="variable_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.gross_power_in[0], 1e-4, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.Q_hotside[0],
            self.get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.Q_coldside[0],
            self.get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.capacity_power,
            self.get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        # Call scaling methods for sub-models
        self.call_submodel_scaler_method(
            submodel=model.properties_in_hotside,
            method="constraint_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_out_hotside,
            method="constraint_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_in_coldside,
            method="constraint_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )
        self.call_submodel_scaler_method(
            submodel=model.properties_out_coldside,
            method="constraint_scaling_routine",
            submodel_scalers=submodel_scalers,
            overwrite=overwrite,
        )

        for j, c in model.eq_hotside_water_production.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_p_con1.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in_hotside[0].pressure,
                overwrite=overwrite,
            )

        for j, c in model.eq_f_con1.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in_hotside[0].flow_mass_phase_comp["Liq", "H2O"],
                overwrite=overwrite,
            )

        for j, c in model.eq_coldside_water_production.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_p_con2.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in_coldside[0].pressure,
                overwrite=overwrite,
            )

        for j, c in model.eq_f_con2.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in_coldside[0].flow_mass_phase_comp["Liq", "H2O"],
                overwrite=overwrite,
            )

        for j, c in model.eq_T_con1.items():
            self.scale_constraint_by_component(
                c,
                model.properties_in_coldside[0].temperature,
                overwrite=overwrite,
            )

        for j, c in model.eq_actual_heat.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_hotside_coldside_energy_transfer.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_power_bound_out.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        # for j, c in model.eq_power_bound_out.items():
        #     self.scale_constraint_by_nominal_value(c, scheme="inverse_maximum", overwrite=overwrite,)


@declare_process_block_class("HeatPump", doc="Heat Pump model")
class HeatPumpData(UnitModelBlockData):
    """
    Unit model for battery storage
    """

    default_scaler = HeatPumpScaler

    CONFIG = ConfigBlock()

    CONFIG.declare(
        "dynamic",
        ConfigValue(
            domain=In([False]),
            default=False,
            description="Dynamic model flag - must be False",
            doc="""Heat pump does not support dynamic models, thus this must be False.""",
        ),
    )

    CONFIG.declare(
        "has_holdup",
        ConfigValue(
            default=False,
            domain=In([False]),
            description="Holdup construction flag",
            doc="""Heat pump does not have defined volume, thus this must be False.""",
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
            bounds=(0, 150e3),
            doc="Nameplate power of boiler",
            units=pyunits.kW,
        )

        self.COP = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=3.0,
            doc="Heat pump heating COP",
        )

        self.cp = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=4.184,
            units=pyunits.kJ / (pyunits.kg * pyunits.K),
            doc="Heat capacity of water",
        )

        self.Q_hotside = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1000.0,
            bounds=(0, 150e3),
            doc="Theoretical hotside energy",
            units=pyunits.kW,
        )

        self.Q_coldside = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=1000.0,
            bounds=(0, 150e3),
            doc="Theoretical coldside energy",
            units=pyunits.kW,
        )

        self.gross_power_in = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 50e3),
            doc="Power in",
            units=pyunits.kW,
        )

        # Ports
        tmp_dict = dict(**self.config.property_package_args)
        tmp_dict["has_phase_equilibrium"] = False
        tmp_dict["parameters"] = self.config.property_package
        tmp_dict["defined_state"] = True  # inlet block is an inlet
        self.properties_in_hotside = self.config.property_package.state_block_class(
            self.flowsheet().config.time,
            doc="Material properties of liquid inlet hotside",
            **tmp_dict,
        )
        self.properties_in_coldside = self.config.property_package.state_block_class(
            self.flowsheet().config.time,
            doc="Material properties of liquid inlet coldside",
            **tmp_dict,
        )

        # Add outlet blocks
        tmp_dict["defined_state"] = False  # outlet and waste block is not an inlet
        self.properties_out_hotside = self.config.property_package.state_block_class(
            self.flowsheet().config.time,
            doc="Material properties of hotside liquid outlet",
            **tmp_dict,
        )

        self.properties_out_coldside = self.config.property_package.state_block_class(
            self.flowsheet().config.time,
            doc="Material properties of coldside liquid outlet",
            **tmp_dict,
        )

        self.add_port(name="hotside_inlet_water", block=self.properties_in_hotside)
        self.add_port(name="hotside_outlet_water", block=self.properties_out_hotside)
        self.add_port(name="coldside_inlet_water", block=self.properties_in_coldside)
        self.add_port(name="coldside_outlet_water", block=self.properties_out_coldside)

        self.power_in = Port(noruleinit=True, doc="A port for electricity inflow")
        self.power_in.add(self.gross_power_in, "electricity")

        # Hotside thermal energy
        @self.Constraint(self.flowsheet().config.time)
        def eq_hotside_water_production(b, t):
            return (
                b.Q_hotside[t]
                - b.properties_in_hotside[t].flow_mass_phase_comp["Liq", "H2O"]
                * b.cp
                * (
                    b.properties_out_hotside[t].temperature
                    - b.properties_in_hotside[t].temperature
                )
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_p_con1(b, t):
            return (
                b.properties_in_hotside[t].pressure
                - b.properties_out_hotside[t].pressure
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_f_con1(b, t):
            return (
                b.properties_in_hotside[t].flow_mass_phase_comp["Liq", "H2O"]
                - b.properties_out_hotside[t].flow_mass_phase_comp["Liq", "H2O"]
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_coldside_water_production(b, t):
            return (
                b.Q_coldside[t]
                - b.properties_in_coldside[t].flow_mass_phase_comp["Liq", "H2O"]
                * b.cp
                * (
                    b.properties_in_coldside[t].temperature
                    - b.properties_out_coldside[t].temperature
                )
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_p_con2(b, t):
            return (
                b.properties_in_coldside[t].pressure
                - b.properties_out_coldside[t].pressure
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_f_con2(b, t):
            return (
                b.properties_in_coldside[t].flow_mass_phase_comp["Liq", "H2O"]
                - b.properties_out_coldside[t].flow_mass_phase_comp["Liq", "H2O"]
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_T_con1(b, t):
            return (
                b.properties_in_coldside[t].temperature
                - b.properties_out_coldside[t].temperature
                <= 4 * pyunits.K
            )

        # Heat pump energy generation
        @self.Constraint(self.flowsheet().config.time)
        def eq_actual_heat(b, t):
            return b.Q_hotside[t] - b.COP * b.gross_power_in[t] == 0

        # Heat pump energy generation
        @self.Constraint(self.flowsheet().config.time)
        def eq_hotside_coldside_energy_transfer(b, t):
            return b.Q_hotside[t] - b.Q_coldside[t] - b.gross_power_in[t] == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_power_bound_out(b, t):
            return b.Q_hotside[t] <= b.capacity_power

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

        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="unit")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="unit")
        opt = get_solver(solver=solver, options=optarg)

        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info(
            "Heat pump initialization status {}.".format(idaeslog.condition(res))
        )
