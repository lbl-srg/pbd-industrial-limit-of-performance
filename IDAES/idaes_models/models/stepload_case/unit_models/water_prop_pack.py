#################################################################################
# WaterTAP Copyright (c) 2020-2024, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National Laboratory,
# National Renewable Energy Laboratory, and National Energy Technology
# Laboratory (subject to receipt of any required approvals from the U.S. Dept.
# of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#################################################################################
"""
Initial property package for pure water system (liquid)
"""

# Import Python libraries
import idaes.logger as idaeslog

# Import Pyomo libraries
from pyomo.environ import (
    Constraint,
    Expression,
    Reals,
    NonNegativeReals,
    Var,
    Param,
    Suffix,
    value,
    log,
    log10,
    exp,
    check_optimal_termination,
)
from pyomo.environ import units as pyunits

# Import IDAES cores
from idaes.core import (
    declare_process_block_class,
    MaterialFlowBasis,
    PhysicalParameterBlock,
    StateBlockData,
    StateBlock,
    MaterialBalanceType,
    EnergyBalanceType,
)
from idaes.core.base.components import Component
from idaes.core.base.phases import LiquidPhase, VaporPhase
from idaes.core.util.initialization import (
    fix_state_vars,
    revert_state_vars,
    solve_indexed_blocks,
)
from watertap.core.solvers import get_solver
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_unfixed_variables,
)
from idaes.core.util.exceptions import (
    ConfigurationError,
    InitializationError,
    PropertyPackageError,
)
from idaes.core.scaling import (
    CustomScalerBase,
    set_scaling_factor,
    report_scaling_factors,
)

# Set up logger
_log = idaeslog.getLogger(__name__)


@declare_process_block_class("WaterParameterBlock")
class WaterParameterData(PhysicalParameterBlock):
    """Parameter block for a water property package."""

    CONFIG = PhysicalParameterBlock.CONFIG()

    def build(self):
        """
        Callable method for Block construction.
        """
        super(WaterParameterData, self).build()

        self._state_block_class = WaterStateBlock

        # components
        self.H2O = Component()

        # phases
        self.Liq = LiquidPhase()

        """ References
        This package was developed from the following references:
        - K.G.Nayar, M.H.Sharqawy, L.D.Banchik, and J.H.Lienhard V, "Thermophysical properties of seawater: A review and
        new correlations that include pressure dependence,"Desalination, Vol.390, pp.1 - 24, 2016.
        doi: 10.1016/j.desal.2016.02.024(preprint)
        - Mostafa H.Sharqawy, John H.Lienhard V, and Syed M.Zubair, "Thermophysical properties of seawater: A review of
        existing correlations and data,"Desalination and Water Treatment, Vol.16, pp.354 - 380, April 2010.
        (2017 corrections provided at http://web.mit.edu/seawater)
        """

        # Parameters
        # molecular weight
        self.mw_comp = Param(
            self.component_list,
            initialize=18.01528e-3,
            units=pyunits.kg / pyunits.mol,
            doc="Molecular weight",
        )

        # Liq mass density parameters, 0-180 C
        # eq. 8 in Sharqawy et al. (2010)
        dens_units = pyunits.kg / pyunits.m**3
        t_inv_units = pyunits.K**-1
        s_inv_units = pyunits.kg / pyunits.g

        self.dens_mass_param_A1 = Var(
            within=Reals,
            initialize=9.999e2,
            units=dens_units,
            doc="Mass density parameter A1",
        )
        self.dens_mass_param_A2 = Var(
            within=Reals,
            initialize=2.034e-2,
            units=dens_units * t_inv_units,
            doc="Mass density parameter A2",
        )
        self.dens_mass_param_A3 = Var(
            within=Reals,
            initialize=-6.162e-3,
            units=dens_units * t_inv_units**2,
            doc="Mass density parameter A3",
        )
        self.dens_mass_param_A4 = Var(
            within=Reals,
            initialize=2.261e-5,
            units=dens_units * t_inv_units**3,
            doc="Mass density parameter A4",
        )
        self.dens_mass_param_A5 = Var(
            within=Reals,
            initialize=-4.657e-8,
            units=dens_units * t_inv_units**4,
            doc="Mass density parameter A5",
        )

        # specific enthalpy parameters, 0-120 C
        # Table 9 in Nayar et al. (2016) - ignores salinity-based parameters
        enth_mass_units = pyunits.J / pyunits.kg
        P_inv_units = pyunits.MPa**-1

        self.enth_mass_param_A1 = Var(
            within=Reals,
            initialize=996.7767,
            units=enth_mass_units * P_inv_units,
            doc="Specific enthalpy parameter A1",
        )
        self.enth_mass_param_A2 = Var(
            within=Reals,
            initialize=-3.2406,
            units=enth_mass_units * P_inv_units * t_inv_units,
            doc="Specific enthalpy parameter A2",
        )
        self.enth_mass_param_A3 = Var(
            within=Reals,
            initialize=0.0127,
            units=enth_mass_units * P_inv_units * t_inv_units**2,
            doc="Specific enthalpy parameter A3",
        )
        self.enth_mass_param_A4 = Var(
            within=Reals,
            initialize=-4.7723e-5,
            units=enth_mass_units * P_inv_units * t_inv_units**3,
            doc="Specific enthalpy parameter A4",
        )
        self.enth_mass_param_C1 = Var(
            within=Reals,
            initialize=141.355,
            units=enth_mass_units,
            doc="Specific enthalpy parameter C1",
        )
        self.enth_mass_param_C2 = Var(
            within=Reals,
            initialize=4202.07,
            units=enth_mass_units * t_inv_units,
            doc="Specific enthalpy parameter C2",
        )
        self.enth_mass_param_C3 = Var(
            within=Reals,
            initialize=-0.535,
            units=enth_mass_units * t_inv_units**2,
            doc="Specific enthalpy parameter C3",
        )
        self.enth_mass_param_C4 = Var(
            within=Reals,
            initialize=0.004,
            units=enth_mass_units * t_inv_units**3,
            doc="Specific enthalpy parameter C4",
        )

        # traditional parameters are the only Vars currently on the block and should be fixed
        for v in self.component_objects(Var):
            v.fix()

    @classmethod
    def define_metadata(cls, obj):
        """Define properties supported and units."""
        obj.add_properties(
            {
                "flow_mass_phase_comp": {"method": None},
                "temperature": {"method": None},
                "pressure": {"method": None},
                "dens_mass_phase": {"method": "_dens_mass_phase"},
                "flow_vol_phase": {"method": "_flow_vol_phase"},
                "flow_vol": {"method": "_flow_vol"},
                "enth_mass_phase": {"method": "_enth_mass_phase"},
            }
        )

        obj.define_custom_properties(
            {
                "enth_flow_phase": {"method": "_enth_flow_phase"},
            }
        )

        obj.add_default_units(
            {
                "time": pyunits.s,
                "length": pyunits.m,
                "mass": pyunits.kg,
                "amount": pyunits.mol,
                "temperature": pyunits.K,
            }
        )


class WaterPropertiesScaler(CustomScalerBase):
    """
    Scaler for saponification properties package.

    Flow and concentration are scaled by default value (if no user input provided),
    pressure is scaled assuming order of magnitude of 1e5 Pa, and temperature is
    scaled using the average of the bounds. Constraints using the inverse maximum
    scheme.
    """

    UNIT_SCALING_FACTORS = {
        "Pressure": (pyunits.Pa, 1e-5),
        "Temperature": (pyunits.K, 1e-2),
    }

    DEFAULT_SCALING_FACTORS = {
        "flow_mass_phase_comp": 1e-2,
        "dens_mass_phase": 1e-3,
        "enth_mass_phase": 1e-5,
        "mw_comp": 1e-2,
    }

    def variable_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        self.scale_variable_by_units(model.pressure, overwrite=overwrite)
        self.scale_variable_by_units(model.temperature, overwrite=overwrite)
        # self.set_variable_scaling_factor(model.flow_mass_phase_comp['Liq', 'H2O'], 1e-2, overwrite=overwrite)

        for k, v in model.flow_mass_phase_comp.items():
            if k == ("Liq", "H2O"):
                self.scale_variable_by_default(v, overwrite=overwrite)

        if model.is_property_constructed("dens_mass_phase"):
            for k, v in model.dens_mass_phase.items():
                if k == ("Liq", "H2O"):
                    self.set_variable_by_default(v, overwrite=overwrite)

        for k, v in model.enth_mass_phase.items():
            if k == ("Liq"):
                self.scale_variable_by_default(v, overwrite=overwrite)

        # if model.is_property_constructed("enth_mass_phase"):
        #     for k, v in model.enth_mass_phase.items():
        #         if k == ('Liq', "H2O"):
        #             self.scale_variable_by_default(v, overwrite=overwrite)

        if model.is_property_constructed("flow_vol_phase"):
            for k, v in self.flow_vol_phase.items():
                sf = self.get_scaling_factor(
                    model.flow_mass_phase_comp[k]
                ) / self.get_scaling_factor(model.dens_mass_phase[k])
                self.set_variable_scaling_factor(v, sf, overwrite=overwrite)

        if model.is_property_constructed("flow_vol"):
            sf_liq = self.get_scaling_factor(model.flow_vol_phase["Liq"])
            self.set_variable_scaling_factor(v, sf_liq, overwrite=overwrite)

        if model.is_property_constructed("enth_flow_phase"):
            for k, v in self.enth_flow_phase.items():
                sf = self.get_scaling_factor(
                    model.flow_mass_phase_comp[k]
                ) * self.get_scaling_factor(model.enth_mass_phase[k])
                self.set_variable_scaling_factor(v, sf, overwrite=overwrite)

    def constraint_scaling_routine(
        self, model, overwrite: bool = False, submodel_scalers: dict = None
    ):
        # pass
        if model.is_property_constructed("enth_mass_phase"):
            for k, v in model.eq_enth_mass_phase.items():
                sf = self.get_scaling_factor(model.enth_mass_phase[k])
                self.scale_constraint_by_component(
                    model.eq_enth_mass_phase[k],
                    model.enth_mass_phase[k],
                    overwrite=overwrite,
                )


class _WaterStateBlock(StateBlock):
    """
    This Class contains methods which should be applied to Property Blocks as a
    whole, rather than individual elements of indexed Property Blocks.
    """

    default_scaler = WaterPropertiesScaler

    def fix_initialization_states(self):
        """
        Fixes state variables for state blocks.

        Returns:
            None
        """
        # Fix state variables
        fix_state_vars(self)

        # Constraint on water concentration at outlet - unfix in these cases
        for b in self.values():
            if b.config.defined_state is False:
                b.conc_mol_comp["H2O"].unfix()

    def initialize(
        self,
        state_args=None,
        state_vars_fixed=False,
        hold_state=False,
        outlvl=idaeslog.NOTSET,
        solver=None,
        optarg=None,
    ):
        """
        Initialization routine for property package.
        Keyword Arguments:
            state_args : Dictionary with initial guesses for the state vars
                         chosen. Note that if this method is triggered
                         through the control volume, and if initial guesses
                         were not provided at the unit model level, the
                         control volume passes the inlet values as initial
                         guess.The keys for the state_args dictionary are:
                         flow_mass_phase_comp : value at which to initialize
                                               phase component flows
                         pressure : value at which to initialize pressure
                         temperature : value at which to initialize temperature
            outlvl : sets output level of initialization routine
            optarg : solver options dictionary object (default={})
            state_vars_fixed: Flag to denote if state vars have already been
                              fixed.
                              - True - states have already been fixed by the
                                       control volume 1D. Control volume 0D
                                       does not fix the state vars, so will
                                       be False if this state block is used
                                       with 0D blocks.
                             - False - states have not been fixed. The state
                                       block will deal with fixing/unfixing.
            solver : Solver object to use during initialization if None is provided
                     it will use the default solver for IDAES (default = None)
            hold_state : flag indicating whether the initialization routine
                         should unfix any state variables fixed during
                         initialization (default=False).
                         - True - states variables are not unfixed, and
                                 a dict of returned containing flags for
                                 which states were fixed during
                                 initialization.
                        - False - state variables are unfixed after
                                 initialization by calling the
                                 release_state method
        Returns:
            If hold_states is True, returns a dict containing flags for
            which states were fixed during initialization.
        """
        # Get loggers
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="properties")

        # Set solver and options
        opt = get_solver(solver, optarg)

        # Fix state variables
        flags = fix_state_vars(self, state_args)
        # Check when the state vars are fixed already result in dof 0
        for k in self.keys():
            dof = degrees_of_freedom(self[k])
            if dof != 0:
                raise PropertyPackageError(
                    "State vars fixed but degrees of "
                    "freedom for state block is not "
                    "zero during initialization."
                )

        # ---------------------------------------------------------------------
        skip_solve = True  # skip solve if only state variables are present
        for k in self.keys():
            if number_unfixed_variables(self[k]) != 0:
                skip_solve = False

        if not skip_solve:
            # Initialize properties
            with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
                results = solve_indexed_blocks(opt, [self], tee=slc.tee)
            init_log.info_high(
                "Property initialization: {}.".format(idaeslog.condition(results))
            )

        # If input block, return flags, else release state
        if state_vars_fixed is False:
            if hold_state is True:
                return flags
            else:
                self.release_state(flags)

        if (not skip_solve) and (not check_optimal_termination(results)):
            raise InitializationError(
                f"{self.name} failed to initialize successfully. Please "
                f"check the output logs for more information."
            )

    def release_state(self, flags, outlvl=idaeslog.NOTSET):
        """
        Method to release state variables fixed during initialisation.
        Keyword Arguments:
            flags : dict containing information of which state variables
                    were fixed during initialization, and should now be
                    unfixed. This dict is returned by initialize if
                    hold_state=True.
            outlvl : sets output level of of logging
        """
        # Unfix state variables
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        revert_state_vars(self, flags)
        init_log.info("{} State Released.".format(self.name))

    def calculate_state(
        self,
        var_args=None,
        hold_state=False,
        outlvl=idaeslog.NOTSET,
        solver=None,
        optarg=None,
    ):
        """
        Solves state blocks given a set of variables and their values. These variables can
        be state variables or properties. This method is typically used before
        initialization to solve for state variables because non-state variables (i.e. properties)
        cannot be fixed in initialization routines.
        Keyword Arguments:
            var_args : dictionary with variables and their values, they can be state variables or properties
                       {(VAR_NAME, INDEX): VALUE}
            hold_state : flag indicating whether all of the state variables should be fixed after calculate state.
                         True - State variables will be fixed.
                         False - State variables will remain unfixed, unless already fixed.
            outlvl : idaes logger object that sets output level of solve call (default=idaeslog.NOTSET)
            solver : solver name string if None is provided the default solver
                     for IDAES will be used (default = None)
            optarg : solver options dictionary object (default={})
        Returns:
            results object from state block solve
        """
        # Get logger
        solve_log = idaeslog.getSolveLogger(self.name, level=outlvl, tag="properties")

        # Initialize at current state values (not user provided)
        self.initialize(solver=solver, optarg=optarg, outlvl=outlvl)

        # Set solver and options
        opt = get_solver(solver, optarg)

        # Fix variables and check degrees of freedom
        flags = (
            {}
        )  # dictionary noting which variables were fixed and their previous state
        for k in self.keys():
            sb = self[k]
            for (v_name, ind), val in var_args.items():
                var = getattr(sb, v_name)
                if iscale.get_scaling_factor(var[ind]) is None:
                    _log.warning(
                        "While using the calculate_state method on {sb_name}, variable {v_name} "
                        "was provided as an argument in var_args, but it does not have a scaling "
                        "factor. This suggests that the calculate_scaling_factor method has not been "
                        "used or the variable was created on demand after the scaling factors were "
                        "calculated. It is recommended to touch all relevant variables (i.e. call "
                        "them or set an initial value) before using the calculate_scaling_factor "
                        "method.".format(v_name=v_name, sb_name=sb.name)
                    )
                if var[ind].is_fixed():
                    flags[(k, v_name, ind)] = True
                    if value(var[ind]) != val:
                        raise ConfigurationError(
                            "While using the calculate_state method on {sb_name}, {v_name} was "
                            "fixed to a value {val}, but it was already fixed to value {val_2}. "
                            "Unfix the variable before calling the calculate_state "
                            "method or update var_args."
                            "".format(
                                sb_name=sb.name,
                                v_name=var.name,
                                val=val,
                                val_2=value(var[ind]),
                            )
                        )
                else:
                    flags[(k, v_name, ind)] = False
                    var[ind].fix(val)

            if degrees_of_freedom(sb) != 0:
                raise RuntimeError(
                    "While using the calculate_state method on {sb_name}, the degrees "
                    "of freedom were {dof}, but 0 is required. Check var_args and ensure "
                    "the correct fixed variables are provided."
                    "".format(sb_name=sb.name, dof=degrees_of_freedom(sb))
                )

        # Solve
        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            results = solve_indexed_blocks(opt, [self], tee=slc.tee)
            solve_log.info_high(
                "Calculate state: {}.".format(idaeslog.condition(results))
            )

        if not check_optimal_termination(results):
            _log.warning(
                "While using the calculate_state method on {sb_name}, the solver failed "
                "to converge to an optimal solution. This suggests that the user provided "
                "infeasible inputs, or that the model is poorly scaled, poorly initialized, "
                "or degenerate."
            )

        # unfix all variables fixed with var_args
        for (k, v_name, ind), previously_fixed in flags.items():
            if not previously_fixed:
                var = getattr(self[k], v_name)
                var[ind].unfix()

        # fix state variables if hold_state
        if hold_state:
            fix_state_vars(self)

        return results


@declare_process_block_class("WaterStateBlock", block_class=_WaterStateBlock)
class WaterStateBlockData(StateBlockData):
    """A water property package."""

    def build(self):
        """Callable method for Block construction."""
        super().build()

        self.scaling_factor = Suffix(direction=Suffix.EXPORT)

        # Add state variables
        self.flow_mass_phase_comp = Var(
            self.params.phase_list,
            self.params.component_list,
            initialize=0.5,
            bounds=(0.0, None),
            domain=NonNegativeReals,
            units=pyunits.kg / pyunits.s,
            doc="Mass flow rate",
        )

        self.temperature = Var(
            initialize=298.15,
            bounds=(273.15, 1000),
            domain=NonNegativeReals,
            units=pyunits.K,
            doc="Temperature",
        )

        self.pressure = Var(
            initialize=101325,
            bounds=(1e3, 5e7),
            domain=NonNegativeReals,
            units=pyunits.Pa,
            doc="Pressure",
        )

    # -----------------------------------------------------------------------------
    # Property Methods

    def _dens_mass_phase(self):
        self.dens_mass_phase = Var(
            self.params.phase_list,
            initialize={"Liq": 1e3},
            bounds=(1e-3, 1e6),
            units=pyunits.kg * pyunits.m**-3,
            doc="Mass density water",
        )

        # Sharqawy et al. (2010), eq. 8, 0-180 C
        def rule_dens_mass_phase(b, phase):
            t = b.temperature - 273.15 * pyunits.K
            dens_mass = (
                b.params.dens_mass_param_A1
                + b.params.dens_mass_param_A2 * t
                + b.params.dens_mass_param_A3 * t**2
                + b.params.dens_mass_param_A4 * t**3
                + b.params.dens_mass_param_A5 * t**4
            )
            return b.dens_mass_phase["Liq"] == dens_mass

        self.eq_dens_mass_phase = Constraint(
            self.params.phase_list, rule=rule_dens_mass_phase
        )

    def _flow_vol_phase(self):
        self.flow_vol_phase = Var(
            self.params.phase_list,
            initialize=1,
            bounds=(None, None),
            units=pyunits.m**3 / pyunits.s,
            doc="Volumetric flow rate",
        )

        def rule_flow_vol_phase(b, p):
            return (
                b.flow_vol_phase[p]
                == b.flow_mass_phase_comp[p, "H2O"] / b.dens_mass_phase[p]
            )

        self.eq_flow_vol_phase = Constraint(
            self.params.phase_list, rule=rule_flow_vol_phase
        )

    def _flow_vol(self):
        def rule_flow_vol(b):
            return sum(b.flow_vol_phase[p] for p in b.params.phase_list)

        self.flow_vol = Expression(rule=rule_flow_vol)

    def _enth_mass_phase(self):
        self.enth_mass_phase = Var(
            self.params.phase_list,  # ['Liq','Vap']
            initialize=1e6,
            bounds=(1, 1e9),
            units=pyunits.J * pyunits.kg**-1,
            doc="Specific enthalpy",
        )

        # Nayar et al. (2016), eq. 25 and 26, 0-120 C
        def rule_enth_mass_phase(b, p):
            # temperature in degC, but pyunits in K
            t = b.temperature - 273.15 * pyunits.K
            P = b.pressure - 101325 * pyunits.Pa
            P_MPa = pyunits.convert(P, to_units=pyunits.MPa)

            # water enthalpy without pressure effects
            h_w = (
                b.params.enth_mass_param_C1
                + b.params.enth_mass_param_C2 * t
                + b.params.enth_mass_param_C3 * t**2
                + b.params.enth_mass_param_C4 * t**3
            )

            # water enthalpy with pressure effects
            h_w_P = h_w + P_MPa * (
                b.params.enth_mass_param_A1
                + b.params.enth_mass_param_A2 * t
                + b.params.enth_mass_param_A3 * t**2
                + b.params.enth_mass_param_A4 * t**3
            )

            return b.enth_mass_phase[p] == h_w_P

        self.eq_enth_mass_phase = Constraint(
            self.params.phase_list, rule=rule_enth_mass_phase
        )

    def _enth_flow_phase(self):
        # enthalpy flow variable
        self.enth_flow_phase = Var(
            self.params.phase_list,  # ['Liq','Vap']
            initialize=1e6,
            bounds=(None, None),
            units=pyunits.J / pyunits.s,
            doc="Enthalpy flow",
        )

        # enthalpy flow [J/s]
        def rule_enth_flow_phase(b, p):
            return (
                b.enth_flow_phase[p]
                == b.flow_mass_phase_comp[p, "H2O"] * b.enth_mass_phase[p]
            )

        self.eq_enth_flow_phase = Constraint(
            self.params.phase_list, rule=rule_enth_flow_phase
        )

    # General Methods
    # NOTE: For scaling in the control volume to work properly, these methods must
    # return a pyomo Var or Expression

    def get_material_flow_terms(self, p, j):
        """Create material flow terms for control volume."""
        return self.flow_mass_phase_comp[p, j]

    def get_enthalpy_flow_terms(self, p):
        """Create enthalpy flow terms."""
        return self.enth_flow_phase[p]

    def default_material_balance_type(self):
        return MaterialBalanceType.componentTotal

    def default_energy_balance_type(self):
        return EnergyBalanceType.enthalpyTotal

    def get_material_flow_basis(self):
        return MaterialFlowBasis.mass

    def define_state_vars(self):
        """Define state vars."""
        return {
            "flow_mass_phase_comp": self.flow_mass_phase_comp,
            "temperature": self.temperature,
            "pressure": self.pressure,
        }
