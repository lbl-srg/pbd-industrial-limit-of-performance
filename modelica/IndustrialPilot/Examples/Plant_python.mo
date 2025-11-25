within IndustrialPilot.Examples;
model Plant_python
  extends BaseClasses.Plant_generic(
  heaPum(allowFlowReversal1=true,
           etaCarnot_nominal=0.6824),
    pumLoaPri(allowFlowReversal=true),
    pumBoi(allowFlowReversal=true),
    boi(allowFlowReversal=true),
    pumCon(allowFlowReversal=true));
  Buildings.Utilities.IO.Python_3_8.Real_Real pyt(
    samplePeriod=900,
    moduleName="modelica_optim",
    functionName="test",
    nDblWri=2,
    nDblRea=3,
    passPythonObject=true)
    annotation (Placement(transformation(extent={{-540,-340},{-520,-320}})));
  Buildings.Controls.OBC.CDL.Logical.Not not1
    annotation (Placement(transformation(extent={{120,300},{140,320}})));
  Buildings.Controls.OBC.CDL.Reals.Hysteresis hys(uLow=TLoaMin, uHigh=TLoaMax)
    annotation (Placement(transformation(extent={{80,300},{100,320}})));
equation
  connect(pyt.yR[1], pumCon.m_flow_in) annotation (Line(points={{-519,-330.333},
          {-460,-330.333},{-460,-210},{-342,-210}},
                                               color={0,0,127}));
  connect(pyt.yR[2], pumBoi.m_flow_in) annotation (Line(points={{-519,-330},{
          -200,-330},{-200,-210},{-122,-210}}, color={0,0,127}));
  connect(pyt.yR[3], charge_discharge_soc.soc_setpoint) annotation (Line(points={{-519,
          -329.667},{-510,-329.667},{-510,250},{-400,250},{-400,215},{-382,215}},
        color={0,0,127}));
  connect(pyt.yR[2], min1.u1) annotation (Line(points={{-519,-330},{-200,-330},
          {-200,-314},{-102,-314}}, color={0,0,127}));
  connect(TTanBot.T, pyt.uR[1]) annotation (Line(points={{81,-30},{100,-30},{
          100,-352},{-550,-352},{-550,-330.5},{-542,-330.5}},
                                                      color={0,0,127}));
  connect(TLoa.T, pyt.uR[2]) annotation (Line(points={{61,330},{68,330},{68,328},
          {250,328},{250,-352},{-550,-352},{-550,-329.5},{-542,-329.5}}, color=
          {0,0,127}));
  connect(gai.u, multiSum.y) annotation (Line(points={{-490,78},{-490,50},{
          -481.7,50}}, color={0,0,127}));
  connect(conPIDPri_m_flow.y, swiPum.u1) annotation(
    Line(points={{-138,170},{-120,170},{-120,178},{-102,178}},          color = {0, 0, 127}));
  connect(hys.y,not1. u)
    annotation (Line(points={{102,310},{118,310}},  color={255,0,255}));
  connect(TLoa.T, hys.u)
    annotation (Line(points={{61,330},{70,330},{70,310},{78,310}},
                                                 color={0,0,127}));
end Plant_python;
