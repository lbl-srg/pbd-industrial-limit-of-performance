within IndustrialPilot.Examples;
model Plant
  extends BaseClasses.Plant_generic(dat(
      QCon_flow_nominal(displayUnit="kW") = 862200,
      QGas_flow_nominal(displayUnit="kW") = 9800,
      ETan(displayUnit="Wh") = 6.9053292e9,
      EBat=4.04928e9,
      surPv=1706.85));
  parameter Boolean useBoi=false
    "Set to true to enable boiler in model, or to false to permanently disable it";
  Modelica.Blocks.Math.BooleanToReal switch_pumCon(realTrue=dat.QCon_flow_nominal
        /4184/dTLoa)
    "Switch to activate the pump associated to the condenser of the heat pump"
    annotation (Placement(transformation(extent={{-380,-220},{-360,-200}})));
  Modelica.Blocks.Math.BooleanToReal switch_pumBoi(realTrue=dat.QGas_flow_nominal
        /4184/dTLoa)
    "Switch to activate the pump associated to the boiler"
    annotation (Placement(transformation(extent={{-160,-220},{-140,-200}})));
  Modelica.Blocks.Math.BooleanToReal Boiler_on "Switch to turn on the boiler"
    annotation (Placement(transformation(extent={{-160,-300},{-140,-280}})));
  Buildings.Controls.OBC.CDL.Logical.TrueFalseHold holdHeaPum(trueHoldDuration(
        displayUnit="min") = 1800, falseHoldDuration(displayUnit="min") = 600)
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=0,
        origin={290,-28})));
  Buildings.Controls.OBC.CDL.Logical.TrueFalseHold holdBoi(trueHoldDuration(
        displayUnit="min") = 900, falseHoldDuration(displayUnit="min") = 0)
    annotation (Placement(transformation(
        extent={{-10,-10},{10,10}},
        rotation=0,
        origin={292,-72})));
  Modelica.Blocks.Sources.CombiTimeTable charge(
    tableOnFile=true,
    tableName="tab1",
    fileName=ModelicaServices.ExternalReferences.loadResource(
        "modelica://IndustrialPilot/Resources/Data/sch_battery_tank_ele.txt"),
    columns=2:4,
    smoothness=Modelica.Blocks.Types.Smoothness.ConstantSegments)
    annotation (Placement(transformation(extent={{-500,300},{-480,320}})));
  Modelica.Blocks.Math.RealToBoolean booHeaPum
    annotation (Placement(transformation(extent={{-440,320},{-420,340}})));
  Controls.charge_input charge_input
    annotation (Placement(transformation(extent={{-460,260},{-440,280}})));

  Modelica.Blocks.Math.RealToBoolean booBoi
    annotation (Placement(transformation(extent={{-440,360},{-420,380}})));
  Controls.onoff_tank onoff_tank
    annotation (Placement(transformation(extent={{180,-40},{200,-20}})));
  Controls.charge_discharge_soc     charge_discharge_soc
    annotation (Placement(transformation(extent={{-400,200},{-380,220}})));
  Modelica.Blocks.Sources.Constant P_charge(k=400000)
    annotation (Placement(transformation(extent={{-460,220},{-440,240}})));
  Buildings.Controls.OBC.CDL.Logical.Sources.Constant boiEna(final k=useBoi)
    "Set to true to enable a boiler, or to false to remove the boiler permanently"
    annotation (Placement(transformation(extent={{280,-120},{300,-100}})));
  Buildings.Controls.OBC.CDL.Logical.And boiDis
    "Boolean and to enable or disable boiler"
    annotation (Placement(transformation(extent={{340,-80},{360,-60}})));

equation


  connect(switch_pumBoi.y, pumBoi.m_flow_in) annotation(
    Line(points={{-139,-210},{-122,-210}},      color = {0, 0, 127}));
  connect(Boiler_on.y, min1.u1) annotation(
    Line(points={{-139,-290},{-112,-290},{-112,-314},{-102,-314}},                        color = {0, 0, 127}));
  connect(gai.u, multiSum.y) annotation(
    Line(points={{-490,78},{-490,50},{-481.7,50}},        color = {0, 0, 127}));
  connect(switch_pumCon.y, pumCon.m_flow_in) annotation(
    Line(points={{-359,-210},{-342,-210}},      color = {0, 0, 127}));
  connect(holdHeaPum.y, switch_pumCon.u) annotation (Line(points={{302,-28},{400,
          -28},{400,-410},{-450,-410},{-450,-210},{-382,-210}},
                                                          color={255,0,255}));
  connect(charge.y[2], booHeaPum.u)
    annotation (Line(points={{-479,310},{-470,310},{-470,330},{-442,330}},
                                                     color={0,0,127}));
  connect(bat.SOC, charge_input.soc) annotation (Line(points={{-319,176},{-312,
          176},{-312,310},{-466,310},{-466,277},{-462,277}}, color={0,0,127}));
  connect(charge.y[1], charge_input.signal) annotation (Line(points={{-479,310},
          {-470,310},{-470,270},{-462,270}}, color={0,0,127}));
  connect(charge.y[3], booBoi.u) annotation (Line(points={{-479,310},{-470,310},
          {-470,370},{-442,370}}, color={0,0,127}));
  connect(onoff_tank.yHeaPum, holdHeaPum.u) annotation (Line(points={{201,-27},{
          278,-27},{278,-28}},  color={255,0,255}));
  connect(onoff_tank.yBoi, holdBoi.u) annotation (Line(points={{201,-33},{260,-33},
          {260,-72},{280,-72}},
                           color={255,0,255}));
  connect(TTanBot.T, onoff_tank.T_bottom) annotation (Line(points={{81,-30},{
          150,-30},{150,-22},{178,-22}}, color={0,0,127}));
  connect(booHeaPum.y, onoff_tank.ChaHeaPum) annotation (Line(points={{-419,330},
          {-240,330},{-240,90},{140,90},{140,-33},{178,-33}},
                                            color={255,0,255}));
  connect(booBoi.y, onoff_tank.ChaBoi) annotation (Line(points={{-419,370},{132,
          370},{132,-39},{178,-39}},
                           color={255,0,255}));
  connect(loaOn.y, onoff_tank.load_on) annotation (Line(points={{-98,330},{-92,
          330},{-92,290},{50,290},{50,170},{100,170},{100,-27},{178,-27}},
        color={255,0,255}));
  connect(charge_discharge_soc.y, bat.P) annotation(
    Line(points={{-379,210},{-330,210},{-330,180}},        color = {0, 0, 127}));
  connect(gai.y,charge_discharge_soc. P_discharge) annotation(
    Line(points={{-490,102},{-490,201},{-402,201}},       color = {0, 0, 127}));
  connect(P_charge.y,charge_discharge_soc. P_charge) annotation(
    Line(points={{-439,230},{-430,230},{-430,205},{-402,205}},          color = {0, 0, 127}));
  connect(pv.P,charge_discharge_soc. P_pv) annotation (Line(points={{-319,137},
          {-290,137},{-290,232},{-412,232},{-412,209},{-402,209}}, color={0,0,
          127}));
  connect(charge_input.soc_setpoint, charge_discharge_soc.soc_setpoint)
    annotation (Line(points={{-439,270},{-420,270},{-420,215},{-402,215}},
        color={0,0,127}));
  connect(bat.SOC, charge_discharge_soc.soc) annotation (Line(points={{-319,176},
          {-312,176},{-312,228},{-406,228},{-406,219},{-402,219}}, color={0,0,
          127}));
  connect(holdBoi.y, boiDis.u1) annotation (Line(points={{304,-72},{320,-72},{320,
          -70},{338,-70}}, color={255,0,255}));
  connect(boiDis.y, Boiler_on.u) annotation (Line(points={{362,-70},{380,-70},{380,
          -370},{-200,-370},{-200,-290},{-162,-290}}, color={255,0,255}));
  connect(boiEna.y, boiDis.u2) annotation (Line(points={{302,-110},{320,-110},{320,
          -78},{338,-78}}, color={255,0,255}));
  connect(switch_pumBoi.u, boiDis.y) annotation (Line(points={{-162,-210},{-200,
          -210},{-200,-370},{380,-370},{380,-70},{362,-70}}, color={255,0,255}));
  annotation (experiment(
      StopTime=31536000,
      Interval=600,
      Tolerance=1e-06,
      __Dymola_Algorithm="Dassl"), Documentation(info="<html>
<p>Extends <a href=\"modelica://IndustrialPilot.BaseClasses.Plant_generic\">IndustrialPilot.BaseClasses.Plant_generic</a></p>
<p>Model with basic controls: the heat pump and the boiler are on and the water storage is discharging when there is heating demand from the secondary side. </p>
<p>The heat pump or the boiler are on also when there is no demand from the secondary side to charge the water storage, reading the input from <i>charge</i>, that sends a signal either to the heat pump of the boiler and for the state of charge of the battery</p>
</html>"),
    Diagram(coordinateSystem(extent={{-520,-420},{520,400}})),
    Icon(coordinateSystem(extent={{-100,-100},{100,100}})));
end Plant;
