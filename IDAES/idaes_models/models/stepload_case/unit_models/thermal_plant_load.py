import sys
from pandas import DataFrame
from collections import OrderedDict
import textwrap

# Import Pyomo libraries
from pyomo.environ import Var, Param, NonNegativeReals, units as pyunits, value
from pyomo.network import Port
from pyomo.common.config import ConfigBlock, ConfigValue, In

# Import IDAES cores
from idaes.core import declare_process_block_class, UnitModelBlockData
from idaes.core.scaling import (
    CustomScalerBase,
    set_scaling_factor,
    report_scaling_factors,
)
from idaes.core.util.config import is_physical_parameter_block
from watertap.core.solvers import get_solver
from idaes.core.util.tables import stream_table_dataframe_to_string
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_activated_constraints,
    number_activated_blocks,
)
import idaes.logger as idaeslog

_log = idaeslog.getLogger(__name__)


class EnergySinkScaler(CustomScalerBase):

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

        # for t in self.flowsheet().config.time:
        #     self.set_variable_scaling_factor(model.Q_load[t], 1e-5, overwrite=overwrite)
        self.set_variable_scaling_factor(model.Q_load[0], 1e-5, overwrite=overwrite)

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

        # Scale unit level constraints
        for j, c in model.eq_flow_con1.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        # Scale unit level constraints
        for j, c in model.eq_heat_water_relationship.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )


@declare_process_block_class("EnergySinks", doc="Plant Loads")
class EnergySinkData(UnitModelBlockData):
    """
    Unit model for battery storage
    """

    default_scaler = EnergySinkScaler

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

        self.cp = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=4.184,
            units=pyunits.kJ / (pyunits.kg * pyunits.K),
            doc="Heat capacity of water",
        )

        self.Q_load = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            doc="Thermal load",
            units=pyunits.kW,
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

        # Thermal load satisfaction
        @self.Constraint(self.flowsheet().config.time)
        def eq_heat_water_relationship(b, t):
            return (
                b.Q_load[t]
                - b.properties_in[t].flow_mass_phase_comp["Liq", "H2O"]
                * b.cp
                * (b.properties_in[t].temperature - b.properties_out[t].temperature)
                == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_flow_con1(b, t):
            return (
                b.properties_in[0].flow_mass_phase_comp["Liq", "H2O"]
                == b.properties_out[0].flow_mass_phase_comp["Liq", "H2O"]
            )

    def initialize_build(self, outlvl=idaeslog.NOTSET, solver=None, optarg=None):
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="unit")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="unit")
        opt = get_solver(solver=solver, options=optarg)

        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info(
            "Plant load initialization status {}.".format(idaeslog.condition(res))
        )
