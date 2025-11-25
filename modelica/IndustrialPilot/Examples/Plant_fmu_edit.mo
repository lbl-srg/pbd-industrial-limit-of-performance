within IndustrialPilot.Examples;
model Plant_fmu_edit
  extends BaseClasses.Plant_generic(dat(
      QCon_flow_nominal(displayUnit="kW") = 862200,
      QGas_flow_nominal(displayUnit="kW") = 9800,
      ETan(displayUnit="Wh") = 6.9053292e9,
      EBat=4.04928e9,
      surPv=1706.85));
  Modelica.Blocks.Interfaces.RealInput pumhea(final unit="kg/s")
    annotation (Placement(transformation(extent = {{-560, -30}, {-520, 10}}), iconTransformation(extent = {{-560, -30}, {-520, 10}})));
  Modelica.Blocks.Interfaces.RealInput pumboi(final unit="kg/s")
    annotation (Placement(transformation(extent={{-560,-72},{-520,-32}})));
  Modelica.Blocks.Interfaces.RealInput Pcharge
    annotation (Placement(transformation(extent={{-560,-110},{-520,-70}})));
  Modelica.Blocks.Interfaces.RealOutput costtot
    annotation (Placement(transformation(extent={{520,-10},{540,10}})));
  Modelica.Blocks.Interfaces.RealOutput yqprod(final quantity="Power", final unit="W")
    annotation (Placement(transformation(extent={{520,-50},{540,-30}})));
  Modelica.Blocks.Math.Add add
    annotation (Placement(transformation(extent={{520,260},{540,280}})));
  Modelica.Blocks.Interfaces.RealOutput tbot annotation(
    Placement(transformation(origin={530,-390},   extent = {{-10, -10}, {10, 10}}), iconTransformation(origin={530,-390},   extent = {{-10, -10}, {10, 10}})));
  Modelica.Blocks.Interfaces.RealOutput ttop annotation(
    Placement(transformation(origin={530,-350},  extent = {{-10, -10}, {10, 10}}), iconTransformation(origin={530,-350},  extent = {{-10, -10}, {10, 10}})));
  Modelica.Blocks.Interfaces.RealOutput tload annotation(
    Placement(transformation(origin={530,-310},  extent = {{-10, -10}, {10, 10}}), iconTransformation(origin={530,-310},  extent = {{-10, -10}, {10, 10}})));
  Modelica.Blocks.Interfaces.RealOutput pulse annotation(
    Placement(transformation(origin={530,-270},   extent = {{-10, -10}, {10, 10}}), iconTransformation(origin={530,-270},   extent = {{-10, -10}, {10, 10}})));
  Modelica.Blocks.Interfaces.RealOutput soc annotation(
    Placement(transformation(origin={530,-190},    extent = {{-10, -10}, {10, 10}}), iconTransformation(origin={530,-190},    extent = {{-10, -10}, {10, 10}})));
  Modelica.Blocks.Interfaces.RealOutput pvp annotation(
    Placement(transformation(origin={530,-230},    extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-280, 130}, extent = {{-10, -10}, {10, 10}})));
equation
  connect(multiSum.y, gai.u) annotation (Line(points={{-481.7,50},{-490,50},{
          -490,78}}, color={0,0,127}));
  connect(pumhea, pumCon.m_flow_in) annotation (Line(points={{-540,-10},{-470,
          -10},{-470,-210},{-342,-210}}, color={0,0,127}));
  connect(pumboi, pumBoi.m_flow_in) annotation (Line(points={{-540,-52},{-480,
          -52},{-480,-190},{-140,-190},{-140,-210},{-122,-210}}, color={0,0,127}));
  connect(gas_cost_sum.y, add.u2) annotation (Line(points={{501,210},{510,210},
          {510,264},{518,264}}, color={0,0,127}));
  connect(elec_cost_sum.y, add.u1) annotation (Line(points={{501,290},{510,290},
          {510,276},{518,276}}, color={0,0,127}));
  connect(add.y, costtot) annotation (Line(points={{541,270},{550,270},{550,20},
          {510,20},{510,0},{530,0}}, color={0,0,127}));
  connect(Qprod_disp.y, yqprod) annotation (Line(points={{461,50},{480,50},{480,
          -40},{530,-40}}, color={0,0,127}));
  connect(pumboi, min1.u1) annotation (Line(points={{-540,-52},{-480,-52},{-480,
          -270},{-110,-270},{-110,-314},{-102,-314}}, color={0,0,127}));
  connect(TTanBot.T, tbot) annotation(
    Line(points={{81,-30},{220,-30},{220,-390},{530,-390}},
                                                       color = {0, 0, 127}));
  connect(TTanTop.T, ttop) annotation(
    Line(points={{81,10},{260,10},{260,-350},{530,-350}},
                                                    color = {0, 0, 127}));
  connect(TLoa.T, tload) annotation(
    Line(points={{61,330},{88,330},{88,220},{280,220},{280,-310},{530,-310}},
                                                     color = {0, 0, 127}));
  connect(heaLoa.y, pulse) annotation(
    Line(points={{-58,330},{-48,330},{-48,380},{270,380},{270,288},{300,288},{300,
          -270},{530,-270}},                            color = {0, 0, 127}));
  connect(bat.SOC, soc) annotation(
    Line(points={{-319,176},{-280,176},{-280,52},{340,52},{340,-190},{530,-190}},
                                                           color = {0, 0, 127}));
  connect(pv.P, pvp) annotation(
    Line(points={{-319,137},{-290,137},{-290,48},{320,48},{320,-230},{530,-230}},
                                              color = {0, 0, 127}));

  connect(Pcharge, bat.P) annotation (Line(points={{-540,-90},{-510,-90},{-510,
          190},{-330,190},{-330,180}}, color={0,0,127}));
annotation(
    experiment(
      StopTime=172800,
      Interval=59.9999616,
      Tolerance=1e-08,
      __Dymola_Algorithm="Dassl"));
end Plant_fmu_edit;
