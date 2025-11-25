within IndustrialPilot.BaseClasses;
partial model Plant_generic
  extends Modelica.Icons.Example;

  Modelica.Units.SI.HeatFlowRate Qprod;

  package Medium = Buildings.Media.Water "Medium model";
  final parameter Medium.ThermodynamicState state_default=Medium.setState_pTX(
      T=Medium.T_default,
      p=Medium.p_default,
      X=Medium.X_default[1:Medium.nXi]) "Medium state at default values";
  // Density at medium default values, used to compute the size of control volumes
  final parameter Modelica.Units.SI.SpecificHeatCapacity cp_default=
      Medium.specificHeatCapacityCp(
      state=state_default)
    "Specific heat capacity, used to verify energy conservation";

  parameter Examples.Data.Design dat(
    QCon_flow_nominal(displayUnit="MW") = 516500,
    QGas_flow_nominal(displayUnit="MW") = 448000,
    ETan=4180041598,
    EBat(displayUnit="kWh") = 2375049600,
    QLoa_flow_nominal(displayUnit="MW") = 1000000,
    surPv=2000)                                    "Design data" annotation (
      Placement(transformation(origin={-490,370}, extent={{-10,-10},{10,10}})));

  final parameter Modelica.Units.SI.TemperatureDifference dTLoa = 20
    "Temperature difference of the load";

  parameter Modelica.Units.SI.MassFlowRate m_flow_nominal_hp_evaporator=dat.QLoa_flow_nominal/4184/4
    "Nominal mass flow rate of the evaporator side of the HP";

    parameter Modelica.Units.SI.MassFlowRate m_flow_nominal_hp_condenser=dat.QLoa_flow_nominal/4184/dTLoa
    "Nominal mass flow rate of the condenser side of the HP";

  parameter Modelica.Units.SI.MassFlowRate m_flow_nominal_gas=dat.QLoa_flow_nominal/4184/dTLoa
    "Nominal mass flow rate for gas";

    parameter Modelica.Units.SI.MassFlowRate m_flow_nominal_system=max(m_flow_nominal_hp_condenser, m_flow_nominal_gas)
    "Nominal mass flow rate of the system";

  final parameter Modelica.Units.SI.Volume VTan = dat.ETan/(1000*4200*dTLoa)
    "Volume of the tank";

  final parameter Modelica.Units.SI.Temperature TLoaMin = 273.15+64
    "Minimum temperature of the load";
  final parameter Modelica.Units.SI.Temperature TLoaMax = TLoaMin+2
    "Maximum temperature of the load";

  Buildings.Fluid.Boilers.BoilerPolynomial boi(
    redeclare package Medium = Medium "Water",
    m_flow_nominal=m_flow_nominal_gas,
    dp_nominal(displayUnit="kPa") = 42000,
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    fue=Buildings.Fluid.Data.Fuels.NaturalGasHigherHeatingValue(),
    Q_flow_nominal=dat.QGas_flow_nominal,
    allowFlowReversal = false) "Gas boiler"
    annotation (Placement(transformation(extent={{-80,-260},{-100,-240}})));

  Buildings.Fluid.Storage.StratifiedEnhanced tan(redeclare package Medium =
        Medium "Water",
    m_flow_nominal=m_flow_nominal_system,
    final VTan=VTan,
    hTan=5,
    dIns=0.1,
    nSeg=10) "Water tank"
    annotation (Placement(transformation(extent={{-20,-20},{0,0}})));

  Buildings.Fluid.FixedResistances.Junction jun1(redeclare package Medium =
        Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Leaving)
    annotation (Placement(transformation(extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-330,-130})));

  Buildings.Fluid.Movers.Preconfigured.FlowControlled_m_flow pumCon(
    redeclare package Medium = Medium "Water",
    m_flow_nominal=m_flow_nominal_hp_condenser,
    dp_nominal(displayUnit="Pa") = 42000 + 4000 + 200,
    allowFlowReversal = false) "Pump for heat pump condenser"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-330,-210})));

  Buildings.Fluid.Actuators.Valves.ThreeWayLinear valLoaPri(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system,
    dpValve_nominal(displayUnit="Pa") = 4000,
    dpFixed_nominal={4000,4000},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Entering)
   "Three-way valve for load on the primary side"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-10,130})));

  Buildings.Fluid.FixedResistances.Junction jun2(redeclare package Medium =
        Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Leaving)
     annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=270,
        origin={30,130})));

  Buildings.Fluid.Movers.Preconfigured.FlowControlled_m_flow pumLoaPri(
    redeclare package Medium = Medium "Water",
    m_flow_nominal=m_flow_nominal_system,
    dp_nominal(displayUnit="Pa") = 24000 + 200 + 2000,
    allowFlowReversal = false)
    "Pump to provide the load on the primary sidePump for boiler" annotation (
      Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-10,170})));

  Buildings.Fluid.Sensors.TemperatureTwoPort senTLoaPriEnt(redeclare package
      Medium = Medium "Water", m_flow_nominal=
        m_flow_nominal_system)
    "Load water temperature entering the primary side of the heat exchanger"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-10,210})));

  Buildings.Fluid.Sensors.TemperatureTwoPort senTConLvg(redeclare package
      Medium = Medium "Water", m_flow_nominal=
        m_flow_nominal_hp_evaporator) "Condenser water leaving temperature"
                                      annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-330,-170})));

  Buildings.Fluid.Movers.Preconfigured.FlowControlled_m_flow pumEva(
    redeclare package Medium = Medium "Water",
    use_riseTime=false,
    m_flow_nominal=m_flow_nominal_hp_evaporator,
    dp_nominal(displayUnit="kPa") = 19000)
    "Pump for heat pump evaporator" annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-330,-290})));

  Buildings.Fluid.Sensors.TemperatureTwoPort senTEvaEnt(redeclare package
      Medium = Medium "Water", m_flow_nominal=
        m_flow_nominal_hp_evaporator) "Evaporator water entering temperature"
                                      annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-330,-330})));

  Buildings.Fluid.Sensors.TemperatureTwoPort senTEvaLvg(redeclare package
      Medium = Medium "Water", m_flow_nominal=
        m_flow_nominal_hp_evaporator) "Evaporator water leaving temperature"
                                      annotation (Placement(transformation(
        extent={{10,-10},{-10,10}},
        rotation=90,
        origin={-290,-330})));

  Buildings.Fluid.Sources.Boundary_pT souNet(
    redeclare package Medium = Medium "Water",
    use_T_in=true,
    nPorts=1)
    "Water from the network going throuh the evaporator side of the hp"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-330,-370})));

  Modelica.Blocks.Sources.Constant setpointConLvg(k(
      final unit="K",
      displayUnit="degC") = 365.15)
    "Temperature setpoint for the water leaving the heat pump on the condenser side"
    annotation (Placement(transformation(extent={{-420,-120},{-400,-100}})));

  Buildings.Controls.OBC.CDL.Reals.PID conPIDHp(
    reverseActing=false,
    Ti=120,
    u_s(final unit="K", displayUnit="degC"),
    u_m(final unit="K", displayUnit="degC"),
    k=0.1)
    annotation (Placement(transformation(extent={{-380,-120},{-360,-100}})));

  Buildings.Controls.OBC.CDL.Reals.PID conPIDLoa(
    k=0.1,
    Ti= 100,
    u_s(final unit="K", displayUnit="degC"),
    u_m(final unit="K", displayUnit="degC"))
    annotation (Placement(transformation(origin={-100,20},   extent = {{-60, 100}, {-40, 120}})));

  Modelica.Blocks.Sources.Constant setpointLoaEnt(k(
      final unit="K",
      displayUnit="degC") = 363.15)
    annotation (Placement(transformation(origin={-100,20},   extent = {{-100, 100}, {-80, 120}})));

  Modelica.Blocks.Sources.Constant setpointBoiLvg(k(
      final unit="K",
      displayUnit="degC") = 365.15)
    "Temperature setpoint for the water leaving the boiler"
    annotation (Placement(transformation(extent={{-200,-120},{-180,-100}})));

  Buildings.Controls.OBC.CDL.Reals.PID conPIDBoiLvg(
    reverseActing=false,
    Ti=120,
    u_s(final unit="K", displayUnit="degC"),
    u_m(final unit="K", displayUnit="degC"),
    k=0.1)
    annotation (Placement(transformation(extent={{-160,-120},{-140,-100}})));

  Buildings.Fluid.HeatPumps.Carnot_TCon heaPum(
    redeclare package Medium1 = Medium "Water",
    redeclare package Medium2 = Medium "Water",
    m1_flow_nominal=m_flow_nominal_hp_condenser,
    m2_flow_nominal=m_flow_nominal_hp_evaporator,
    show_T=true,
    QCon_flow_nominal=dat.QCon_flow_nominal,
    dTEva_nominal=-4,
    dTCon_nominal=22,
    etaCarnot_nominal=0.6824,
    dp1_nominal(displayUnit="kPa") = 42000,
    dp2_nominal(displayUnit="kPa") = 19000,
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    QCon_flow_max=dat.QCon_flow_nominal,
    allowFlowReversal1 = false,
    allowFlowReversal2 = false) "Heat pump"
    annotation (Placement(transformation(extent={{-300,-260},{-320,-240}})));

  Buildings.Fluid.Actuators.Valves.ThreeWayLinear valHp(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_hp_condenser,
    dpValve_nominal= 4000,
    dpFixed_nominal={4000,4000},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Entering)
                          "Three-way valve for heat pump"
    annotation (Placement(
        transformation(
        extent={{-10,-10},{10,10}},
        rotation=270,
        origin={-290,-130})));

  Buildings.Fluid.FixedResistances.Junction jun3(redeclare package Medium =
        Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Leaving)
    annotation (Placement(transformation(extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-110,-130})));

  Buildings.Fluid.Movers.Preconfigured.FlowControlled_m_flow pumBoi(
    redeclare package Medium = Medium "Water",
    m_flow_nominal=m_flow_nominal_gas,
    dp_nominal(displayUnit="Pa") = 200 + 4000 + 42000,
    allowFlowReversal = false) "Pump for boiler" annotation (Placement(
        transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-110,-210})));

  Buildings.Fluid.Sensors.TemperatureTwoPort senTBoiLvg(redeclare package
      Medium = Medium "Water", m_flow_nominal=m_flow_nominal_gas)
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-110,-170})));

  Buildings.Fluid.Actuators.Valves.ThreeWayLinear valBoi(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_gas,
    dpValve_nominal(displayUnit="Pa") = 4000,
    dpFixed_nominal={4000,4000},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Entering)
                          "Three-way valve for boiler" annotation (Placement(
        transformation(
        extent={{-10,-10},{10,10}},
        rotation=270,
        origin={-70,-130})));

  Buildings.Fluid.MixingVolumes.MixingVolume loa(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    T_start=TLoaMin,
    m_flow_nominal=m_flow_nominal_system,
    V=200,
    nPorts=3) "Heat load"              annotation (Placement(transformation(
        extent={{10,10},{-10,-10}},
        rotation=180,
        origin={10,310})));

  Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow preHea
    "Prescribed heat flow rate for process load"
    annotation (Placement(transformation(extent={{-40,320},{-20,340}})));

  Buildings.Fluid.FixedResistances.Junction jun4(redeclare package Medium =
        Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Entering)
    annotation (Placement(transformation(extent={{-10,-10},{10,10}},
        rotation=0,
        origin={-110,70})));

  Buildings.Fluid.FixedResistances.Junction jun5(redeclare package Medium =
        Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Leaving)
    annotation (Placement(transformation(extent={{10,-10},{-10,10}},
        rotation=0,
        origin={-70,-90})));

  Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor TTanTop(
    T(final unit="K",
      displayUnit="degC")) "Temperature at the top of the tank"
    annotation (Placement(transformation(extent={{60,0},{80,20}})));

  Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor TTanBot(
    T(final unit="K",
      displayUnit="degC")) "Temperature at the bottom of the tank"
    annotation (Placement(transformation(extent={{60,-40},{80,-20}})));

  Buildings.Fluid.Sources.Boundary_pT bouHeaWat(redeclare package Medium =
        Medium "Water", nPorts=1)
    "Pressure boundary condition representing the expansion vessel" annotation
    (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=180,
        origin={-250,-244})));

  Modelica.Blocks.Sources.Constant setpointConHp(k(
      final unit="K",
      displayUnit="degC") = 365.25)
    "Temperature setpoint temperature for the water leaving the heat pump on the condenser side"
    annotation (Placement(transformation(extent={{-240,-220},{-260,-200}})));

  Buildings.Fluid.FixedResistances.Junction jun6(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving,
    portFlowDirection_3 = Modelica.Fluid.Types.PortFlowDirection.Entering)
    annotation (Placement(transformation(extent={{-10,10},{10,-10}},
        rotation=90,
        origin={-10,70})));

  Buildings.Fluid.FixedResistances.Junction jun7(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.FixedInitial,
    m_flow_nominal=m_flow_nominal_system*{1,1,1},
    dp_nominal={0,0,0},
    portFlowDirection_1 = Modelica.Fluid.Types.PortFlowDirection.Entering,
    portFlowDirection_2 = Modelica.Fluid.Types.PortFlowDirection.Leaving)
    annotation (Placement(transformation(extent={{10,10},{-10,-10}},
        rotation=0,
        origin={-10,-90})));

  Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor TLoa(
    T(final unit="K",
      displayUnit="degC")) "Temperature of the load"
    annotation (Placement(transformation(extent={{40,320},{60,340}})));

  Modelica.Blocks.Math.Division division
    annotation (Placement(transformation(extent={{-380,-300},{-360,-280}})));

  Modelica.Blocks.Sources.Constant const9(k=-4184*4)
    annotation (Placement(transformation(extent={{-420,-320},{-400,-300}})));

  Buildings.Fluid.HeatExchangers.ConstantEffectiveness hex(
    redeclare package Medium1 = Medium "Water",
    redeclare package Medium2 = Medium "Water",
    m1_flow_nominal=m_flow_nominal_system,
    m2_flow_nominal=m_flow_nominal_system,
    show_T=true,
    dp1_nominal=8000,
    dp2_nominal=24000,
    eps=(90 - 70)/(90 - 65),
    allowFlowReversal1 = false,
    allowFlowReversal2 = false) "Heat exchanger"
           annotation (Placement(transformation(extent={{20,230},{0,250}})));

  Buildings.Fluid.Sources.Boundary_pT bou3(redeclare package Medium =
        Medium "Water", nPorts=1)
    "Pressure boundary condition representing the expansion vessel"
    annotation (Placement(transformation(extent={{-10,-10},{10,10}},
        rotation=180,
        origin={70,300})));

  Buildings.Fluid.Movers.FlowControlled_m_flow pumLoaSec(
    redeclare package Medium = Medium "Water",
    energyDynamics=Modelica.Fluid.Types.Dynamics.SteadyState,
    nominalValuesDefineDefaultPressureCurve=true,
    use_riseTime= true,
    inputType=Buildings.Fluid.Types.InputType.Continuous,
    m_flow_nominal=dat.QLoa_flow_nominal/4184/dTLoa,
    constantMassFlowRate=dat.QLoa_flow_nominal/4184/dTLoa)
    "Pump to provide the load on the secondary side" annotation (Placement(
        transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-10,270})));

  Buildings.Electrical.DC.Storage.Battery     bat(
    etaCha=0.95,
    etaDis=0.95,                                  EMax=dat.EBat, V_nominal=480)
    "Battery"
    annotation (Placement(transformation(extent={{-340,160},{-320,180}})));

  Buildings.Electrical.DC.Sources.ConstantVoltage    sou(V=480)
                                                               "Voltage source"
    annotation (Placement(transformation(extent={{-10,-10},{10,10}},
        origin={-410,170})));

  Modelica.Electrical.Analog.Basic.Ground grid
    annotation (Placement(transformation(extent={{-440,140},{-420,160}})));

  Buildings.Electrical.DC.Sensors.GeneralizedSensor powSen "Power sensor"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=0,
        origin={-370,170})));

  Modelica.Blocks.Sources.Ramp ramp(
    height=8,
    duration(displayUnit="d") = 345600,
    offset=8 + 273.15,
    startTime(displayUnit="d") = 432000)
    annotation (Placement(transformation(extent={{-400,-400},{-380,-380}})));
  Buildings.Fluid.Sources.Boundary_pT sinNet(redeclare package Medium =
        Medium "Water", nPorts=1)
    "Water coming from the evaporator side of the hp going back to the network"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-290,-370})));
  Buildings.Controls.OBC.CDL.Reals.Hysteresis hys1(uLow=10 + 273.15, uHigh=90
         + 273.15)
    annotation (Placement(transformation(extent={{160,100},{180,120}})));
  Buildings.Electrical.DC.Loads.Conductor con(
    V_nominal=480,
    mode=Buildings.Electrical.Types.Load.VariableZ_P_input)
    "Electrical conductor"
    annotation (Placement(transformation(extent={{-360,120},{-380,140}})));
  Buildings.Controls.OBC.CDL.Reals.MultiplyByParameter gai(k=-1)
    annotation (Placement(transformation(extent={{-10,-10},{10,10}},
        rotation=90,
        origin={-490,90})));
  Modelica.Blocks.Sources.Constant setpointBoi(k(
      final unit="K",
      displayUnit="degC") = 365.25)
    "Temperature setpoint for the water leaving the boiler"
    annotation (Placement(transformation(extent={{-180,-340},{-160,-320}})));
  Buildings.Controls.OBC.CDL.Reals.PID conPIDBoi(
    Ti=100,
    u_s(final unit="K", displayUnit="degC"),
    u_m(final unit="K", displayUnit="degC"),
    k=0.2)
    annotation (Placement(transformation(extent={{-140,-340},{-120,-320}})));
  Modelica.Blocks.Math.Min min1
    annotation (Placement(transformation(extent={{-100,-330},{-80,-310}})));
  Modelica.Blocks.Sources.Constant setpointLoaPriLvg(k(
      final unit="K",
      displayUnit="degC") = 343.15)
    annotation (Placement(transformation(origin={-60,-80},     extent = {{-140, 240}, {-120, 260}})));
  Buildings.Controls.OBC.CDL.Reals.PIDWithReset conPIDPri_m_flow(
    k = 0.1,
    Ti = 10,
    u_s(final unit = "K", displayUnit = "degC"),
    u_m(final unit = "K", displayUnit = "degC"),
    yMin = 0.2, y_reset = 0.2) "Mass flow rate controller" annotation(
    Placement(transformation(origin={-60,-80},     extent = {{-100, 240}, {-80, 260}})));
  Buildings.Fluid.Sensors.TemperatureTwoPort senTLoaPriLvg(redeclare package
      Medium = Medium "Water", m_flow_nominal=
        m_flow_nominal_system)
    "Load water temperature entering the primary side of the heat exchanger"
    annotation (Placement(transformation(
        extent={{-10,10},{10,-10}},
        rotation=270,
        origin={30,190})));
  Modelica.Blocks.Continuous.Integrator ECon(y(final unit="J", displayUnit=
          "kWh"))          "Heat pump condenser energy"
    annotation (Placement(transformation(extent={{480,120},{500,140}})));
  Modelica.Blocks.Sources.RealExpression QCon_flow(y(final unit="W") = heaPum.QCon_flow)
    "Heat pump condenser heat flow rate"
    annotation (Placement(transformation(extent={{440,120},{460,140}})));
  Modelica.Blocks.Continuous.Integrator EElec(y(final unit="J", displayUnit=
          "kWh")) "Heat pump condenser energy"
    annotation (Placement(transformation(extent={{480,360},{500,380}})));
  Modelica.Blocks.Sources.RealExpression Pelec(y(final unit="W") = powSen.P)
    "Heat pump electricity consumption"
    annotation (Placement(transformation(origin={0,46},    extent = {{280, 320}, {300, 340}})));
  Modelica.Blocks.Sources.RealExpression Pfuel(y(final unit="W") = boi.QFue_flow)
    "Boiler fuel consumption"
    annotation (Placement(transformation(extent={{380,240},{400,260}})));
  Modelica.Blocks.Math.Gain gas_co2(k=1/1000/3600*0.202)
    annotation (Placement(transformation(extent={{440,240},{460,260}})));
  Modelica.Blocks.Math.Gain hp_elec_to_kWh(k=1/1000/3600)
    annotation (Placement(transformation(extent={{360,340},{380,360}})));
  Modelica.Blocks.Continuous.Integrator elec_co2_sum
    "Heat pump co2 content total"
    annotation (Placement(transformation(extent={{480,320},{500,340}})));
  Modelica.Blocks.Math.Product elec_co2
    annotation (Placement(transformation(extent={{440,320},{460,340}})));
  Modelica.Blocks.Sources.CombiTimeTable elec_co2_price(
    tableOnFile=true,
    tableName="tab1",
    fileName=ModelicaServices.ExternalReferences.loadResource(
        "modelica://IndustrialPilot/Resources/Data/data_elec.txt"),
    columns=2:3)
    annotation (Placement(transformation(extent={{360,300},{380,320}})));
  Modelica.Blocks.Math.Product elec_price
    annotation (Placement(transformation(extent={{440,280},{460,300}})));
  Modelica.Blocks.Continuous.Integrator elec_cost_sum
    "Heat pump electricity price total"
    annotation (Placement(transformation(extent={{480,280},{500,300}})));
  Modelica.Blocks.Continuous.Integrator gas_co2_sum
    "Boiler gas co2 content total"
    annotation (Placement(transformation(extent={{480,240},{500,260}})));
  Modelica.Blocks.Continuous.Integrator gas_cost_sum "Boiler gas price total"
    annotation (Placement(transformation(extent={{480,200},{500,220}})));
  Modelica.Blocks.Math.Gain gas_cost(k=1/1000/3600*0.039)
    annotation (Placement(transformation(extent={{440,200},{460,220}})));
  Modelica.Blocks.Math.MultiSum multiSum(nu=1)
    annotation (Placement(transformation(extent={{-460,40},{-480,60}})));
  Modelica.Blocks.Continuous.Integrator EFuel(y(final unit="J", displayUnit=
          "kWh"))          "Heat pump condenser energy"
    annotation (Placement(transformation(extent={{480,160},{500,180}})));
  Modelica.Blocks.Sources.RealExpression Php(y(final unit="W") = heaPum.P)
    "Heat pump electricity consumption"
    annotation (Placement(transformation(extent={{440,80},{460,100}})));
  Modelica.Blocks.Continuous.Integrator EHp(y(final unit="J", displayUnit="kWh"))
    "Heat pump condenser energy"
    annotation (Placement(transformation(extent={{480,80},{500,100}})));
  Buildings.HeatTransfer.Sources.FixedTemperature TAmb(T=291.15)
    "Ambient temperature in boiler room"
    annotation (Placement(transformation(extent={{-60,0},{-40,20}})));
  Buildings.Controls.OBC.CDL.Logical.Sources.Pulse loaOn(
    period = 86400,
    shift = 8*3600)
    "Load signal, outputs true if load is on"  annotation(
    Placement(transformation(origin={-110,330},    extent = {{-10, -10}, {10, 10}})));
  Buildings.Controls.OBC.CDL.Conversions.BooleanToReal heaLoa(
    realTrue = -dat.QLoa_flow_nominal)
    "Heat load" annotation(
    Placement(transformation(origin={-70,330},    extent = {{-10, -10}, {10, 10}})));
  Buildings.Controls.OBC.CDL.Conversions.BooleanToReal secPumSig(
    realTrue = dat.QLoa_flow_nominal/4184/dTLoa)
    "Mass flow rate setpoint for secondary pump" annotation(
    Placement(transformation(origin={-50,270},    extent={{-10,-10},{10,10}})));
  Modelica.Blocks.Math.Gain mPumPriSet_flow(k = dat.QLoa_flow_nominal/4184/dTLoa) "Mass flow set point" annotation(
    Placement(transformation(origin={-480,-20},    extent = {{420, 180}, {440, 200}})));
  Buildings.Controls.OBC.CDL.Reals.Switch swiPum "Switch to switch pump on and off" annotation(
    Placement(transformation(origin={-90,170},    extent = {{-10, -10}, {10, 10}})));
  Modelica.Blocks.Sources.Constant zer(k= 0) "Zero output signal" annotation(
    Placement(transformation(origin={0,-20},    extent = {{-140, 240}, {-120, 260}})));
  Buildings.Fluid.Sensors.EnthalpyFlowRate senEntTanTop(redeclare package
      Medium = Buildings.Media.Water "Water", m_flow_nominal=12) annotation (
      Placement(transformation(
        extent={{-10,10},{10,-10}},
        rotation=90,
        origin={-10,30})));
  Buildings.Fluid.Sensors.EnthalpyFlowRate senEntTanBot(redeclare package
      Medium = Buildings.Media.Water "Water", m_flow_nominal=12) annotation (
      Placement(transformation(
        extent={{-10,10},{10,-10}},
        rotation=90,
        origin={-10,-50})));
  Modelica.Blocks.Math.Add QTan(k2=-1)
    annotation (Placement(transformation(extent={{60,-100},{80,-80}})));
  Modelica.Blocks.Sources.RealExpression Qprod_disp(y=Qprod)
    annotation (Placement(transformation(extent={{440,40},{460,60}})));
  Buildings.BoundaryConditions.SolarIrradiation.DiffusePerez HDifTil(til=
        0.34906585039887, azi=-0.78539816339745)
                           "Diffuse irradiation on tilted surface"
    annotation (Placement(transformation(extent={{-380,280},{-360,300}})));
  Buildings.BoundaryConditions.SolarIrradiation.DirectTiltedSurface HDirTil(til=
        0.34906585039887, azi=-0.78539816339745)
                           "Direct irradiation on tilted surface"
    annotation (Placement(transformation(extent={{-380,240},{-360,260}})));
  Buildings.BoundaryConditions.WeatherData.ReaderTMY3 weaDat(filNam=
        ModelicaServices.ExternalReferences.loadResource(
        "modelica://IndustrialPilot/Resources/weatherdata/USA_CA_Sacramento.Metro.AP.724839_TMY3.mos"),
      computeWetBulbTemperature=false)
    annotation (Placement(transformation(extent={{-420,280},{-400,300}})));
  Modelica.Blocks.Math.Add G "Total irradiation on tilted surface"
    annotation (Placement(transformation(extent={{-340,260},{-320,280}})));
  Buildings.Electrical.DC.Sources.PVSimple     pv(
    A=dat.surPv,
    fAct=0.9,
    eta=0.19,
    V_nominal=480)
    "PV module"
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        origin={-330,130})));
  Modelica.Blocks.Math.Max PeleGri "Electricity from the grid"
    annotation (Placement(transformation(extent={{320,360},{340,380}})));
  Modelica.Blocks.Sources.Constant const(k=0)
    annotation (Placement(transformation(extent={{280,340},{300,360}})));
  Buildings.Controls.OBC.CDL.Logical.And and3
    annotation (Placement(transformation(origin={0,20},     extent = {{200, 100}, {220, 120}})));
  Buildings.Controls.OBC.CDL.Logical.Or loaCirOn "Output true if the load circuit should operate" annotation(
    Placement(transformation(origin={50,120},   extent = {{180, 40}, {200, 60}})));
  Buildings.Controls.OBC.CDL.Logical.TrueDelay truDel(delayTime=60)   annotation(
    Placement(transformation(origin={-90,270},    extent = {{-10, -10}, {10, 10}})));
  Buildings.Controls.OBC.CDL.Logical.Not not1
    annotation (Placement(transformation(extent={{140,330},{160,350}})));
  Buildings.Controls.OBC.CDL.Reals.Hysteresis hys(uLow=TLoaMin, uHigh=TLoaMax)
    annotation (Placement(transformation(extent={{100,330},{120,350}})));
equation
  Qprod = QTan.y + heaPum.QCon_flow + boi.QWat_flow;
  connect(valLoaPri.port_2, pumLoaPri.port_a) annotation(
    Line(points={{-10,140},{-10,160}},      color = {0, 127, 255}));
  connect(pumLoaPri.port_b, senTLoaPriEnt.port_a) annotation(
    Line(points={{-10,180},{-10,200}},      color = {0, 127, 255}));
  connect(setpointConLvg.y, conPIDHp.u_s) annotation(
    Line(points={{-399,-110},{-382,-110}},    color = {0, 0, 127}));
  connect(setpointLoaEnt.y, conPIDLoa.u_s) annotation(
    Line(points={{-179,130},{-162,130}},      color = {0, 0, 127}));
  connect(setpointBoiLvg.y, conPIDBoiLvg.u_s) annotation(
    Line(points={{-179,-110},{-162,-110}},    color = {0, 0, 127}));
  connect(pumEva.port_a, senTEvaEnt.port_b) annotation(
    Line(points={{-330,-300},{-330,-320}},      color = {0, 127, 255}));
  connect(senTEvaEnt.port_a, souNet.ports[1]) annotation(
    Line(points={{-330,-340},{-330,-360}},      color = {0, 127, 255}));
  connect(pumCon.port_b, senTConLvg.port_a) annotation(
    Line(points={{-330,-200},{-330,-180}},      color = {0, 127, 255}));
  connect(pumEva.port_b, heaPum.port_a2) annotation(
    Line(points={{-330,-280},{-330,-256},{-320,-256}},        color = {0, 127, 255}));
  connect(heaPum.port_b2, senTEvaLvg.port_a) annotation(
    Line(points={{-300,-256},{-290,-256},{-290,-320}},        color = {0, 127, 255}));
  connect(pumCon.port_a, heaPum.port_b1) annotation(
    Line(points={{-330,-220},{-330,-244},{-320,-244}},        color = {0, 127, 255}));
  connect(pumBoi.port_b, senTBoiLvg.port_a) annotation(
    Line(points={{-110,-200},{-110,-180}},      color = {0, 127, 255}));
  connect(pumBoi.port_a, boi.port_b) annotation(
    Line(points={{-110,-220},{-110,-250},{-100,-250}},        color = {0, 127, 255}));
  connect(valLoaPri.port_3, jun2.port_3) annotation(
    Line(points={{0,130},{20,130}},      color = {0, 127, 255}));
  connect(preHea.port, loa.heatPort) annotation(
    Line(points={{-20,330},{-12,330},{-12,310},{0,310}},          color = {191, 0, 0}));
  connect(conPIDHp.u_m, senTConLvg.T) annotation(
    Line(points={{-370,-122},{-370,-170},{-341,-170}},     color = {0, 0, 127}));
  connect(senTBoiLvg.T, conPIDBoiLvg.u_m) annotation(
    Line(points={{-121,-170},{-150,-170},{-150,-122}},     color = {0, 0, 127}));
  connect(conPIDLoa.y, valLoaPri.y) annotation(
    Line(points={{-138,130},{-22,130}},      color = {0, 0, 127}));
  connect(senTLoaPriEnt.T, conPIDLoa.u_m) annotation(
    Line(points={{-21,210},{-212,210},{-212,104},{-150,104},{-150,118}},         color = {0, 0, 127}));
  connect(heaPum.port_a1, bouHeaWat.ports[1]) annotation(
    Line(points={{-300,-244},{-260,-244}},      color = {0, 127, 255}));
  connect(setpointConHp.y, heaPum.TSet) annotation(
    Line(points={{-261,-210},{-280,-210},{-280,-241},{-298,-241}},          color = {0, 0, 127}));
  connect(jun3.port_3, valBoi.port_3) annotation(
    Line(points={{-100,-130},{-80,-130}},    color = {0, 127, 255}));
  connect(jun4.port_3, jun3.port_2) annotation(
    Line(points={{-110,60},{-110,-120}},     color = {0, 127, 255}));
  connect(jun3.port_1, senTBoiLvg.port_b) annotation(
    Line(points={{-110,-140},{-110,-160}},    color = {0, 127, 255}));
  connect(jun5.port_3, valBoi.port_1) annotation(
    Line(points={{-70,-100},{-70,-120}},    color = {0, 127, 255}));
  connect(conPIDBoiLvg.y, valBoi.y) annotation(
    Line(points={{-138,-110},{-48,-110},{-48,-130},{-58,-130}},      color = {0, 0, 127}));
  connect(valBoi.port_2, boi.port_a) annotation(
    Line(points={{-70,-140},{-70,-250},{-80,-250}},       color = {0, 127, 255}));
  connect(jun1.port_1, senTConLvg.port_b) annotation(
    Line(points={{-330,-140},{-330,-160}},    color = {0, 127, 255}));
  connect(heaPum.port_a1, valHp.port_2) annotation(
    Line(points={{-300,-244},{-290,-244},{-290,-140}},       color = {0, 127, 255}));
  connect(jun1.port_2, jun4.port_1) annotation(
    Line(points={{-330,-120},{-330,70},{-120,70}},       color = {0, 127, 255}));
  connect(jun5.port_2, valHp.port_1) annotation(
    Line(points={{-80,-90},{-80,-92},{-290,-92},{-290,-120}},
                                                          color = {0, 127, 255}));
  connect(jun1.port_3, valHp.port_3) annotation(
    Line(points={{-320,-130},{-300,-130}},    color = {0, 127, 255}));
  connect(conPIDHp.y, valHp.y) annotation(
    Line(points={{-358,-110},{-268,-110},{-268,-130},{-278,-130}},      color = {0, 0, 127}));
  connect(jun6.port_2, valLoaPri.port_1) annotation(
    Line(points={{-10,80},{-10,120}},      color = {0, 127, 255}));
  connect(jun6.port_3, jun4.port_2) annotation(
    Line(points={{-20,70},{-100,70}},      color = {0, 127, 255}));
  connect(jun2.port_2, jun7.port_1) annotation(
    Line(points={{30,120},{30,-90},{0,-90}},        color = {0, 127, 255}));
  connect(jun7.port_2, jun5.port_1) annotation(
    Line(points={{-20,-90},{-60,-90}},      color = {0, 127, 255}));
  connect(tan.heaPorVol[8], TTanBot.port) annotation(
    Line(points={{-10,-9.85},{-10,-14},{40,-14},{40,-30},{60,-30}},
                                                                 color = {191, 0, 0}));
  connect(tan.heaPorVol[1], TTanTop.port) annotation(
    Line(points={{-10,-10.27},{-10,-14},{40,-14},{40,10},{60,10}}, color = {191, 0, 0}));
  connect(loa.heatPort, TLoa.port) annotation(
    Line(points={{0,310},{-12,310},{-12,330},{40,330}},          color = {191, 0, 0}));
  connect(const9.y, division.u2) annotation(
    Line(points={{-399,-310},{-390,-310},{-390,-296},{-382,-296}},          color = {0, 0, 127}));
  connect(division.y, pumEva.m_flow_in) annotation(
    Line(points={{-359,-290},{-342,-290}},      color = {0, 0, 127}));
  connect(heaPum.QEva_flow, division.u1) annotation(
    Line(points={{-321,-259},{-390,-259},{-390,-284},{-382,-284}},          color = {0, 0, 127}));
  connect(pumLoaSec.port_b, loa.ports[1]) annotation(
    Line(points={{-10,280},{-10,300},{8.66667,300}},        color = {0, 127, 255}));
  connect(loa.ports[2], bou3.ports[1]) annotation(
    Line(points={{10,300},{60,300}},      color = {0, 127, 255}));
  connect(bat.terminal, powSen.terminal_p) annotation(
    Line(points={{-340,170},{-360,170}},      color = {0, 0, 255}, smooth = Smooth.None));
  connect(powSen.terminal_n, sou.terminal) annotation(
    Line(points={{-380,170},{-400,170}},      color = {0, 0, 255}, smooth = Smooth.None));
  connect(sou.n, grid.p) annotation(
    Line(points={{-420,170},{-430,170},{-430,160}},        color = {0, 0, 255}, smooth = Smooth.None));
  connect(ramp.y, souNet.T_in) annotation(
    Line(points={{-379,-390},{-334,-390},{-334,-382}},        color = {0, 0, 127}));
  connect(senTEvaLvg.port_b, sinNet.ports[1]) annotation(
    Line(points={{-290,-340},{-290,-360}},      color = {0, 127, 255}));
  connect(loa.ports[3], hex.port_a1) annotation(
    Line(points={{11.3333,300},{30,300},{30,246},{20,246}},          color = {0, 127, 255}));
  connect(hex.port_b1, pumLoaSec.port_a) annotation(
    Line(points={{0,246},{-10,246},{-10,260}},        color = {0, 127, 255}));
  connect(senTLoaPriEnt.port_b, hex.port_a2) annotation(
    Line(points={{-10,220},{-10,234},{0,234}},        color = {0, 127, 255}));
  connect(TTanBot.T, hys1.u) annotation(
    Line(points={{81,-30},{150,-30},{150,110},{158,110}},    color = {0, 0, 127}));
  connect(bat.terminal, con.terminal) annotation(
    Line(points={{-340,170},{-354,170},{-354,130},{-360,130}},          color = {0, 0, 255}));
  connect(gai.y, con.Pow) annotation(
    Line(points={{-490,102},{-490,130},{-380,130}},       color = {0, 0, 127}));
  connect(setpointBoi.y, conPIDBoi.u_s) annotation(
    Line(points={{-159,-330},{-142,-330}},      color = {0, 0, 127}));
  connect(boi.T, conPIDBoi.u_m) annotation(
    Line(points={{-101,-242},{-190,-242},{-190,-350},{-130,-350},{-130,-342}},            color = {0, 0, 127}));
  connect(conPIDBoi.y, min1.u2) annotation(
    Line(points={{-118,-330},{-112,-330},{-112,-326},{-102,-326}},          color = {0, 0, 127}));
  connect(min1.y, boi.y) annotation(
    Line(points={{-79,-320},{-60,-320},{-60,-242},{-78,-242}},          color = {0, 0, 127}));
  connect(setpointLoaPriLvg.y, conPIDPri_m_flow.u_s) annotation(
    Line(points={{-179,170},{-162,170}},      color = {0, 0, 127}));
  connect(hex.port_b2, senTLoaPriLvg.port_a) annotation(
    Line(points={{20,234},{30,234},{30,200}},        color = {0, 127, 255}));
  connect(senTLoaPriLvg.port_b, jun2.port_1) annotation(
    Line(points={{30,180},{30,140}},      color = {0, 127, 255}));
  connect(conPIDPri_m_flow.u_m, senTLoaPriLvg.T) annotation(
    Line(points={{-150,158},{-149.75,158},{-149.75,150},{14,150},{14,190},{19,
          190}},                                                                                      color = {0, 0, 127}));
  connect(QCon_flow.y, ECon.u) annotation(
    Line(points={{461,130},{478,130}},      color = {0, 0, 127}));
  connect(Pfuel.y, gas_co2.u) annotation(
    Line(points={{401,250},{438,250}},      color = {0, 0, 127}));
  connect(hp_elec_to_kWh.y, elec_co2.u1) annotation(
    Line(points={{381,350},{420,350},{420,336},{438,336}},          color = {0, 0, 127}));
  connect(elec_co2_price.y[1], elec_co2.u2) annotation(
    Line(points={{381,310},{400,310},{400,324},{438,324}},          color = {0, 0, 127}));
  connect(hp_elec_to_kWh.y, elec_price.u1) annotation(
    Line(points={{381,350},{420,350},{420,296},{438,296}},          color = {0, 0, 127}));
  connect(elec_co2_price.y[2], elec_price.u2) annotation(
    Line(points={{381,310},{400,310},{400,284},{438,284}},          color = {0, 0, 127}));
  connect(elec_co2.y, elec_co2_sum.u) annotation(
    Line(points={{461,330},{478,330}},      color = {0, 0, 127}));
  connect(elec_price.y, elec_cost_sum.u) annotation(
    Line(points={{461,290},{478,290}},      color = {0, 0, 127}));
  connect(gas_co2.y, gas_co2_sum.u) annotation(
    Line(points={{461,250},{478,250}},      color = {0, 0, 127}));
  connect(Pfuel.y, gas_cost.u) annotation(
    Line(points={{401,250},{420,250},{420,210},{438,210}},          color = {0, 0, 127}));
  connect(gas_cost.y, gas_cost_sum.u) annotation(
    Line(points={{461,210},{478,210}},      color = {0, 0, 127}));
  connect(Pfuel.y, EFuel.u) annotation(
    Line(points={{401,250},{420,250},{420,170},{478,170}},          color = {0, 0, 127}));
  connect(Php.y, EHp.u) annotation(
    Line(points={{461,90},{478,90}},      color = {0, 0, 127}));
  connect(TAmb.port, tan.heaPorBot) annotation(
    Line(points={{-40,10},{8,10},{8,-20},{-8,-20},{-8,-17.4}},                       color = {191, 0, 0}));
  connect(TAmb.port, tan.heaPorSid) annotation(
    Line(points={{-40,10},{8,10},{8,-10},{-4.4,-10}},                                                  color = {191, 0, 0}));
  connect(TAmb.port, tan.heaPorTop) annotation(
    Line(points={{-40,10},{-4,10},{-4,4},{-8,4},{-8,-2.6}},                color = {191, 0, 0}));
  connect(heaLoa.y, preHea.Q_flow) annotation(
    Line(points={{-58,330},{-40,330}},      color = {0, 0, 127}));
  connect(loaOn.y, heaLoa.u) annotation(
    Line(points={{-98,330},{-82,330}},      color = {255, 0, 255}));
  connect(secPumSig.y, pumLoaSec.m_flow_in) annotation(
    Line(points={{-38,270},{-22,270}},                  color = {0, 0, 127}));
  connect(mPumPriSet_flow.y, pumLoaPri.m_flow_in) annotation(
    Line(points={{-39,170},{-22,170}},      color = {0, 0, 127}));
  connect(swiPum.y, mPumPriSet_flow.u) annotation(
    Line(points={{-78,170},{-62,170}},      color = {0, 0, 127}));
  connect(zer.y, swiPum.u3) annotation(
    Line(points={{-119,230},{-110.5,230},{-110.5,162},{-102,162}},          color = {0, 0, 127}));
  connect(jun6.port_1, senEntTanTop.port_b)
    annotation (Line(points={{-10,60},{-10,40}}, color={0,127,255}));
  connect(senEntTanTop.port_a, tan.port_a)
    annotation (Line(points={{-10,20},{-10,0}}, color={0,127,255}));
  connect(tan.port_b, senEntTanBot.port_b)
    annotation (Line(points={{-10,-20},{-10,-40}}, color={0,127,255}));
  connect(senEntTanBot.port_a, jun7.port_3)
    annotation (Line(points={{-10,-60},{-10,-80}}, color={0,127,255}));
  connect(senEntTanTop.H_flow, QTan.u1) annotation (Line(points={{1,30},{20,30},
          {20,-84},{58,-84}}, color={0,0,127}));
  connect(senEntTanBot.H_flow, QTan.u2) annotation (Line(points={{1,-50},{10,
          -50},{10,-96},{58,-96}}, color={0,0,127}));
  connect(heaPum.P, multiSum.u[1]) annotation (Line(points={{-321,-250},{-440,
          -250},{-440,50},{-460,50}}, color={0,0,127}));
  connect(weaDat.weaBus,HDifTil. weaBus) annotation (Line(
      points={{-400,290},{-380,290}},
      color={255,204,51},
      thickness=0.5,
      smooth=Smooth.None));
  connect(weaDat.weaBus,HDirTil. weaBus) annotation (Line(
      points={{-400,290},{-390,290},{-390,250},{-380,250}},
      color={255,204,51},
      thickness=0.5,
      smooth=Smooth.None));
  connect(HDifTil.H,G. u1) annotation (Line(
      points={{-359,290},{-352,290},{-352,276},{-342,276}},
      color={0,0,127},
      smooth=Smooth.None));
  connect(HDirTil.H,G. u2) annotation (Line(
      points={{-359,250},{-352,250},{-352,264},{-342,264}},
      color={0,0,127},
      smooth=Smooth.None));
  connect(G.y,pv. G) annotation (Line(
      points={{-319,270},{-300,270},{-300,152},{-330,152},{-330,142}},
      color={0,0,127},
      smooth=Smooth.None));
  connect(bat.terminal, pv.terminal) annotation (Line(points={{-340,170},{-346,
          170},{-346,130},{-340,130}}, color={0,0,255}));
  connect(Pelec.y, PeleGri.u1)
    annotation (Line(points={{301,376},{318,376}}, color={0,0,127}));
  connect(const.y, PeleGri.u2) annotation (Line(points={{301,350},{310,350},{
          310,364},{318,364}}, color={0,0,127}));
  connect(PeleGri.y, EElec.u)
    annotation (Line(points={{341,370},{478,370}}, color={0,0,127}));
  connect(PeleGri.y, hp_elec_to_kWh.u) annotation (Line(points={{341,370},{350,
          370},{350,350},{358,350}}, color={0,0,127}));
  connect(not1.y,and3. u1) annotation(
    Line(points={{162,340},{172,340},{172,130},{198,130}},        color = {255, 0, 255}));
  connect(hys1.y,and3. u2) annotation(
    Line(points={{182,110},{184,110},{184,122},{198,122}},
                                          color = {255, 0, 255}));
  connect(and3.y,loaCirOn. u2) annotation(
    Line(points={{222,130},{226,130},{226,162},{228,162}},        color = {255, 0, 255}));
  connect(loaOn.y,loaCirOn. u1) annotation (Line(points={{-98,330},{-92,330},{
          -92,290},{50,290},{50,170},{228,170}},   color={255,0,255}));
  connect(truDel.u,loaCirOn. y) annotation(
    Line(points={{-102,270},{-170,270},{-170,360},{260,360},{260,170},{252,170}},             color = {255, 0, 255}));
  connect(truDel.y, secPumSig.u) annotation(
    Line(points={{-78,270},{-62,270}},      color = {255, 0, 255}));
  connect(hys.y,not1. u) annotation(
    Line(points={{122,340},{138,340}},      color = {255, 0, 255}));
  connect(TLoa.T,hys. u) annotation(
    Line(points={{61,330},{88,330},{88,340},{98,340}},
                                          color = {0, 0, 127}));
  connect(loaCirOn.y, conPIDPri_m_flow.trigger) annotation (Line(points={{252,
          170},{260,170},{260,360},{-170,360},{-170,150},{-156,150},{-156,158}},
        color={255,0,255}));
  connect(loaCirOn.y, swiPum.u2) annotation (Line(points={{252,170},{260,170},{
          260,360},{-170,360},{-170,190},{-120,190},{-120,170},{-102,170}},
        color={255,0,255}));
  connect(conPIDPri_m_flow.y, swiPum.u1) annotation (Line(points={{-138,170},{
          -128,170},{-128,178},{-102,178}}, color={0,0,127}));
  annotation (
    Icon(
      coordinateSystem(preserveAspectRatio=false,
        extent={{-100,-100},{100,100}})),
    Diagram(
        coordinateSystem(preserveAspectRatio = false,
        extent={{-520,-400},{520,400}})),
    experiment(
      StopTime=172800,
      Interval=60,
      Tolerance=1e-06,
      __Dymola_Algorithm="Dassl"),
    Documentation(info="<html>
<p><b>Generic plant model.</b> The plant provides heating to the secondary side via a heat exchanger.</p>
<p>- <b>Heat production</b>: The heating production comes from the heat pump and/or the boiler. </p>
<p>- <b>Storage</b>: There are an electric storage (battery) and a water storage</p>
<p>- <b>Demand</b>: The demand is switching on/off, via <i>loaOn</i>. The demand is on from 8AM to 8PM.</p>
<p>- <b>Electicity</b>: The electricity is either imported from the grid or locally produced via PV. The PV production depends on the weather file for Sacramento, which is an input via <i>weaDat</i>. The hourly cost of electricity and the co2 content are inputs files via <i>elec_co2_price</i>. The cost of electricity comes from CalFlexHub, and the CO2 content from the <i>Cambium 2023</i> database.</p>
<p>The capacities of the different components (heat pump, boiler, water storage, battery, PV) are defined in <i>dat</i></p>
<p>The controls are to ensure the respect of the nominal temperatures leaving the evaporator and condenser in the heat pump (92&deg;C), leaving the boiler (92&deg;C), entering the heat exchanger (90&deg;C) </p>
<h4>References</h4>
<ul>
<li><a href=\"https://energyplus.net/weather-location/north_and_central_america_wmo_region_4/USA/CA/USA_CA_Sacramento.Metro.AP.724839_TMY3\">EnergyPlus weather file</a> </li>
<li><a href=\"https://github.com/LBNL-ETA/CalFlexHub\">CalFlexHub</a> </li>
<li><a href=\"https://www.nrel.gov/analysis/cambium\">Cambium 2023</a> </li>
</ul>
<p align=\"center\"><br><br><br><img src=\"modelica://IndustrialPilot/Resources/Images/Examples/plant.svg\" alt=\"System schematics\"/> </p>
</html>"));
end Plant_generic;
