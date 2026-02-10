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
from watertap.core.solvers import get_solver
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


class BatteryStorageScaler(CustomScalerBase):

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):

        self.set_variable_scaling_factor(
            model.gross_power_in[0], 1e-4, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.gross_power_out[0],
            get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.net_power_in[0],
            get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.net_power_out[0],
            get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.capacity_power,
            get_scaling_factor(model.gross_power_in[0]),
            overwrite=overwrite,
        )
        self.set_variable_scaling_factor(
            model.state_of_charge[0], 1, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.initial_state_of_charge[0], 1, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.storage_level[0], 1e-5, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.capacity_energy, 1e-6, overwrite=overwrite
        )
        self.set_variable_scaling_factor(
            model.initial_state,
            get_scaling_factor(model.capacity_energy),
            overwrite=overwrite,
        )

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):

        for j, c in model.eq_battery_accumulation.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_soc_final.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_soc_initial.items():
            self.scale_constraint_by_component(
                c,
                model.storage_level[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_charging_losses.items():
            self.scale_constraint_by_component(
                c,
                model.gross_power_in[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_battery_discharging_losses.items():
            self.scale_constraint_by_component(
                c,
                model.gross_power_in[0],
                overwrite=overwrite,
            )

        for j, c in model.eq_state_of_charge_bounds.items():
            self.scale_constraint_by_nominal_value(
                c,
                scheme="inverse_maximum",
                overwrite=overwrite,
            )

        for j, c in model.eq_power_bound_in.items():
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


@declare_process_block_class("BatteryStorage", doc="Battery model")
class BatteryStorageData(UnitModelBlockData):
    """
    Unit model for battery storage
    """

    default_scaler = BatteryStorageScaler

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
        """Building model
        This model does not use the flowsheet's time domain. Instead, it only models a single timestep, with initial
        conditions provided by `initial_state_of_charge` and `initial_energy_throughput`. The model calculates change
        in stored energy across a single time step using the power flow variables, `power_in` and `power_out`, and
        the `dr_hr` parameter.
        Args:
            None
        Returns:
            None
        """
        super().build()

        # Design variables and parameters
        self.capacity_power = Var(
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 500e3),
            doc="Nameplate power of battery energy storage",
            units=pyunits.kW,
        )

        self.capacity_energy = Var(
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 2000e3),
            doc="Capacity of battery energy storage",
            units=pyunits.kWh,
        )

        self.eta_charge = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=0.95,
            doc="Charging efficiency, (0, 1]",
        )

        self.eta_discharge = Param(
            within=NonNegativeReals,
            mutable=True,
            initialize=0.95,
            doc="Discharging efficiency, (0, 1]",
        )

        # Initial conditions
        self.initial_state = Var(
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 2000e3),
            doc="State of charge at t - 1",
            units=pyunits.kWh,
        )

        # Power flows and energy storage
        self.dt = Param(
            within=NonNegativeReals,
            initialize=1,
            doc="Time step for converting between electricity power flows and stored energy",
            units=pyunits.hr,
        )

        self.storage_level = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 2000e3),
            doc="Battery state of charge (MWh)",
            units=pyunits.kWh,
        )

        self.net_power_in = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 500e3),
            doc="Power in",
            units=pyunits.kW,
        )

        self.net_power_out = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 500e3),
            doc="Power out",
            units=pyunits.kW,
        )

        self.gross_power_in = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 500e3),
            doc="Power in",
            units=pyunits.kW,
        )

        self.gross_power_out = Var(
            self.flowsheet().config.time,
            within=NonNegativeReals,
            initialize=0.0,
            bounds=(0, 500e3),
            doc="Power out",
            units=pyunits.kW,
        )

        self.state_of_charge = Var(
            self.flowsheet().config.time,
            initialize=0.5,
            bounds=(0, 1),
            doc="Battery state of charge at t",
            units=pyunits.dimensionless,
        )

        self.initial_state_of_charge = Var(
            self.flowsheet().config.time,
            initialize=0.5,
            bounds=(0, 1),
            doc="Battery state of charge at t-1",
            units=pyunits.dimensionless,
        )

        # Ports
        self.power_in = Port(noruleinit=True, doc="A port for electricity inflow")
        self.power_in.add(self.gross_power_in, "electricity")
        # self.power_in.add(self.net_power_in, "Net electricity")

        self.power_out = Port(noruleinit=True, doc="A port for electricity outflow")
        # self.power_out.add(self.gross_power_out, "Gross electricity")
        self.power_out.add(self.net_power_out, "electricity")

        @self.Constraint(self.flowsheet().config.time)
        def eq_battery_accumulation(b, t):
            return (
                b.storage_level[t]
                == b.initial_state
                + b.dt * b.net_power_in[t]
                - b.dt * b.gross_power_out[t]
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_battery_soc_initial(b, t):
            return (
                b.initial_state - b.initial_state_of_charge[t] * b.capacity_energy == 0
            )

        @self.Constraint(self.flowsheet().config.time)
        def eq_battery_soc_final(b, t):
            return b.storage_level[t] - b.state_of_charge[t] * b.capacity_energy == 0

        # Battery charging energy losses
        @self.Constraint(self.flowsheet().config.time)
        def eq_battery_charging_losses(b, t):
            return (b.gross_power_in[t] * b.eta_charge) - b.net_power_in[t] == 0

        # Battery discharging energy losses
        @self.Constraint(self.flowsheet().config.time)
        def eq_battery_discharging_losses(b, t):
            return b.net_power_out[t] - (b.eta_discharge * b.gross_power_out[t]) == 0

        @self.Constraint(self.flowsheet().config.time)
        def eq_state_of_charge_bounds(b, t):
            return b.storage_level[t] <= b.capacity_energy

        @self.Constraint(self.flowsheet().config.time)
        def eq_power_bound_in(b, t):
            return b.gross_power_in[t] <= b.capacity_power

        @self.Constraint(self.flowsheet().config.time)
        def eq_power_bound_out(b, t):
            return b.net_power_out[t] <= b.capacity_power

    def initialize_build(self, outlvl=idaeslog.NOTSET, solver=None, optarg=None):
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="properties")
        opt = get_solver(solver=solver, options=optarg)

        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            res = opt.solve(self, tee=slc.tee)
        init_log.info(
            "Battery initialization status {}.".format(idaeslog.condition(res))
        )

        init_log.info_high("Initialization Step 3 {}.".format(idaeslog.condition(res)))

    def _get_stream_table_contents(self, time_point=0):
        io_dict = {}
        io_dict["Power Inlet"] = self.power_in
        io_dict["Power Outlet"] = self.power_out
        return create_stream_table_dataframe(io_dict, time_point=time_point)

    # def report(self, time_point=0, dof=False, ostream=None, prefix=""):
    #     time_point = float(time_point)

    #     if ostream is None:
    #         ostream = sys.stdout

    #     # Get DoF and model stats
    #     if dof:
    #         dof_stat = degrees_of_freedom(self)
    #         nv = number_variables(self)
    #         nc = number_activated_constraints(self)
    #         nb = number_activated_blocks(self)

    #     # Get stream table
    #     stream_attributes = OrderedDict()
    #     stream_attributes["Inlet"] = {'electricity': value(self.gross_power_in[time_point])}
    #     stream_attributes["Outlet"] = {'electricity': value(self.net_power_out[time_point])}
    #     stream_attributes["MWh"] = {}
    #     stream_attributes["MWh"]['initial_state_of_charge'] = value(self.initial_state)
    #     stream_attributes["kWh"]['charge_level'] = value(self.storage_level[time_point])

    #     stream_table = DataFrame.from_dict(stream_attributes, orient="columns")

    #     if hasattr(self, "is_flowsheet") and self.is_flowsheet:
    #         model_type = "Flowsheet"
    #     else:
    #         model_type = "Unit"

    #     max_str_length = 84
    #     tab = " " * 4
    #     ostream.write("\n" + "=" * max_str_length + "\n")

    #     lead_str = f"{prefix}{model_type} : {self.name}"
    #     trail_str = f"Time: {time_point}"
    #     mid_str = " " * (max_str_length - len(lead_str) - len(trail_str))
    #     ostream.write(lead_str + mid_str + trail_str)

    #     if dof:
    #         ostream.write("\n" + "=" * max_str_length + "\n")
    #         ostream.write(f"{prefix}{tab}Local Degrees of Freedom: {dof_stat}")
    #         ostream.write('\n')
    #         ostream.write(f"{prefix}{tab}Total Variables: {nv}{tab}"
    #                       f"Activated Constraints: {nc}{tab}"
    #                       f"Activated Blocks: {nb}")

    #     if stream_table is not None:
    #         ostream.write("\n" + "-" * max_str_length + "\n")
    #         ostream.write(f"{prefix}{tab}Stream Table")
    #         ostream.write('\n')
    #         ostream.write(
    #             textwrap.indent(
    #                 stream_table_dataframe_to_string(stream_table),
    #                 prefix + tab))
    #     ostream.write("\n" + "=" * max_str_length + "\n")
