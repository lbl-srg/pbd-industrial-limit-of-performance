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
from idaes.core.solvers import get_solver
from idaes.core.scaling import CustomScalerBase, set_scaling_factor, get_scaling_factor
from idaes.core.util.tables import stream_table_dataframe_to_string
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_activated_constraints,
    number_activated_blocks,
)
import idaes.logger as idaeslog

_log = idaeslog.getLogger(__name__)


class PVScaler(CustomScalerBase):

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):

        self.set_variable_scaling_factor(model.E_PV[0], 1e-3, overwrite=overwrite)
        self.set_variable_scaling_factor(model.Area, 1e-3, overwrite=overwrite)

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        for j, c in model.eq_power_generation.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )


@declare_process_block_class("Photovoltaics", doc="PV model")
class PVData(UnitModelBlockData):
    """
    Unit model for battery storage
    """

    default_scaler = PVScaler

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

    def build(self):
        super().build()

        # Design variables and parameters
        self.power_per_unit_area = Param(
            self.flowsheet().config.time,
            initialize=0.0,
            doc="Power per unit area pf PV installed (m2)",
            units=pyunits.kW / pyunits.m**2,
        )

        self.E_PV = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 1e4),
            doc="PV Power Generated",
            units=pyunits.kW,
        )

        self.Area = Var(
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 1e6),
            doc="PV area (m2)",
            units=pyunits.m**2,
        )

        # Port
        self.power_supplied = Port(
            noruleinit=True, doc="A port for electricity outflow"
        )
        self.power_supplied.add(self.E_PV, "electricity")

        @self.Constraint(self.flowsheet().config.time)
        def eq_power_generation(b, t):
            return b.E_PV[t] <= b.Area * b.power_per_unit_area[t]

    def initialize_build(self, outlvl=idaeslog.NOTSET, solver=None, optarg=None):
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="unit")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="unit")
        opt = get_solver(solver=solver, options=optarg)

        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info("Grid initialization status {}.".format(idaeslog.condition(res)))
