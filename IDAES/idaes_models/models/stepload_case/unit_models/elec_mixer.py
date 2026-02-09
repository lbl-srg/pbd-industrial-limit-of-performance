import sys
from pandas import DataFrame
from collections import OrderedDict
import textwrap

# Import Pyomo libraries
from pyomo.environ import (
    NonNegativeReals,
    Var,
    Expression,
    SolverFactory,
    Reference,
    value,
    units as pyunits,
)
from pyomo.network import Port
from pyomo.common.config import ConfigBlock, ConfigValue, In, ListOf

# Import IDAES cores
from idaes.core import declare_process_block_class, UnitModelBlockData
from watertap.core.solvers import get_solver
from idaes.core.scaling import CustomScalerBase, set_scaling_factor, get_scaling_factor
from idaes.core.util import from_json, to_json, StoreSpec
from idaes.core.util.exceptions import ConfigurationError
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.tables import stream_table_dataframe_to_string
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_activated_constraints,
    number_activated_blocks,
)

import idaes.logger as idaeslog

_log = idaeslog.getLogger(__name__)


class ElectricalMixerScaler(CustomScalerBase):

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        self.set_variable_scaling_factor(
            model.electricity[0], 1e-6, overwrite=overwrite
        )
        for p in model.inlet_list:
            in_port = getattr(model, p + "_elec")
            self.set_variable_scaling_factor(
                in_port[0],
                get_scaling_factor(model.electricity[0]),
                overwrite=overwrite,
            )

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        for j, c in model.sum_split.items():
            self.scale_constraint_by_component(
                c,
                model.electricity[0],
                overwrite=overwrite,
            )


@declare_process_block_class(
    "ElectricalMixer", doc="Mixes electricity flow from multiple inlets"
)
class ElectricalMixerData(UnitModelBlockData):
    """
    Unit model to split a electricity from a single inlet into multiple outlets based on split fractions
    """

    default = ElectricalMixerScaler

    CONFIG = ConfigBlock()
    CONFIG.declare(
        "dynamic",
        ConfigValue(
            domain=In([False]),
            default=False,
            description="Dynamic model flag - must be False",
        ),
    )
    CONFIG.declare(
        "has_holdup",
        ConfigValue(
            default=False,
            domain=In([False]),
            description="Holdup construction flag - must be False",
        ),
    )
    CONFIG.declare(
        "inlet_list",
        ConfigValue(
            domain=ListOf(str),
            description="List of inlet names",
            doc="""A list containing names of inlets,
                **default** - None.
                **Valid values:** {
                **None** - use num_inlets argument,
                **list** - a list of names to use for inlets.}""",
        ),
    )
    CONFIG.declare(
        "num_inlets",
        ConfigValue(
            domain=int,
            description="Number of inlets to unit",
            doc="""Argument indicating number (int) of inlets to construct,
                not used if inlet_list arg is provided,
                **default** - None.
                **Valid values:** {
                **None** - use inlet_list arg instead, or default to 2 if neither argument
                provided,
                **int** - number of inlets to create (will be named with sequential integers
                from 1 to num_inlets).}""",
        ),
    )
    CONFIG.declare(
        "add_split_fraction_vars",
        ConfigValue(
            domain=bool,
            default=False,
            description="Add split fraction variables. Set it to True if these variables are needed",
        ),
    )

    def build(self):
        """ """
        super().build()
        time = self.flowsheet().config.time

        self.create_inlets()

        self.electricity = Var(
            time,
            domain=NonNegativeReals,
            initialize=0.0,
            doc="Electricity into control volume",
            units=pyunits.kW,
        )
        self.electricity_out = Port(noruleinit=True, doc="A port for electricity flow")
        self.electricity_out.add(self.electricity, "electricity")

        @self.Constraint(time, doc="Mix constraint")
        def sum_split(b, t):
            return b.electricity[t] == sum(
                getattr(b, o + "_elec")[t] for o in b.inlet_list
            )

        if self.config.add_split_fraction_vars:
            self.split_fraction = Var(
                self.inlet_list,
                time,
                bounds=(0, 1),
                initialize=1.0 / len(self.inlet_list),
                doc="Split fractions for outlet streams",
            )

            @self.Constraint(time, self.inlet_list, doc="Split fraction definition")
            def split_fraction_definition(b, t, o):
                inlet_obj = getattr(b, o + "_elec")
                return inlet_obj[t] == b.split_fraction[o, t] * b.electricity[t]

        else:
            self.split_fraction = Expression(
                self.inlet_list,
                time,
                rule=lambda b, o, t: getattr(b, o + "_elec")[t] / b.electricity[t],
                doc="Split fractions for inlet streams",
            )

    def create_inlets(self):
        """
        Create list of inlet stream names based on config arguments.

        Returns:
            list of strings
        """
        config = self.config
        if config.inlet_list is not None and config.num_inlets is not None:
            # If both arguments provided and not consistent, raise Exception
            if len(config.inlet_list) != config.num_inlets:
                raise ConfigurationError(
                    "{} ElectricalSplitter provided with both inlet_list and "
                    "num_inlets arguments, which were not consistent ("
                    "length of inlet_list was not equal to num_inlets). "
                    "Please check your arguments for consistency, and "
                    "note that it is only necessry to provide one of "
                    "these arguments.".format(self.name)
                )
        elif config.inlet_list is None and config.num_inlets is None:
            # If no arguments provided for outlets, default to num_outlets = 2
            config.num_inlets = 2

        # Create a list of names for outlet StateBlocks
        if config.inlet_list is not None:
            inlet_list = self.config.inlet_list
        else:
            inlet_list = ["inlet_{}".format(n) for n in range(1, config.num_inlets + 1)]
        self.inlet_list = inlet_list

        for p in self.inlet_list:
            inlet_obj = Var(
                self.flowsheet().config.time,
                domain=NonNegativeReals,
                initialize=0.0,
                doc="Electricity at inlet {}".format(p),
                units=pyunits.kW,
            )
            setattr(self, p + "_elec", inlet_obj)
            inlet_port = Port(noruleinit=True, doc="inlet {}".format(p))
            inlet_port.add(getattr(self, p + "_elec"), "electricity")
            setattr(self, p + "_port", inlet_port)

    def initialize_build(self, outlvl=idaeslog.NOTSET, solver=None, optarg=None):
        if self.config.add_split_fraction_vars:
            inlet_vars = [Reference(self.split_fraction[o, :]) for o in self.inlet_list]
        else:
            inlet_vars = [getattr(self, o + "_elec") for o in self.inlet_list]

        # fix or unfix electricity flows so all are fixed
        list_of_initialization_fixes = []
        for t in self.flowsheet().config.time:
            # see how many electricity flows are unfixed
            n = sum(1 for v in inlet_vars if v[t].fixed)
            # if number of inlets we're good
            if n == len(self.inlet_list):
                continue
            # if not enough fixed, start fixing from the back until there are are enough
            else:
                for v in reversed(inlet_vars):
                    if not v[t].fixed:
                        v[t].fix()
                        n += 1
                        list_of_initialization_fixes.append(v[t])
                    if n == len(self.inlet_list):
                        break

        assert degrees_of_freedom(self) == 0

        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="unit")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="unit")
        opt = get_solver(solver=solver, options=optarg)
        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info(
            "Electrical mixer status status {}.".format(idaeslog.condition(res))
        )

        # Unfix any variables that were fixed for initialization
        for t in self.flowsheet().config.time:
            for init_fix in list_of_initialization_fixes:
                init_fix.unfix()

    def calculate_scaling_factors(self):
        super().calculate_scaling_factors()

        if iscale.get_scaling_factor(self.electricity) is None:
            sf = iscale.get_scaling_factor(self.electricity, default=1e-6, warning=True)
            iscale.set_scaling_factor(self.electricity, sf)

        for p in self.inlet_list:
            in_port = getattr(self, p + "_elec")
            if iscale.get_scaling_factor(in_port) is None:
                sf = iscale.get_scaling_factor(self.electricity, default=1e-6)
                iscale.set_scaling_factor(in_port, sf)
