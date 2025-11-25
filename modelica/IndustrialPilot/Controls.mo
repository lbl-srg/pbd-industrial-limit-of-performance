within IndustrialPilot;
package Controls "Control models not present neither in Modelica nor Buildings libraries"
  extends Modelica.Icons.Package;
  model onoff_tank
    extends Modelica.Blocks.Icons.BooleanBlock;
      parameter Modelica.Units.SI.Temperature TBot = 92 + 273.15
      "Temperature setpoint - bottom of the tank";

    parameter Modelica.Units.SI.Temperature Hys = 2
      "Temperature setpoint - bottom of the tank";

    Modelica.Blocks.Interfaces.RealInput T_bottom
      annotation (Placement(transformation(                   extent={{-140,70},{-100,
              110}}),                                                                             iconTransformation(                   extent={{-140,60},
              {-100,100}})));
    Modelica.Blocks.Interfaces.BooleanInput ChaHeaPum
      annotation (Placement(transformation(extent={{-140,-50},{-100,-10}})));
    Modelica.Blocks.Interfaces.BooleanInput load_on
      annotation (Placement(transformation(extent={{-140,10},{-100,50}})));
    Modelica.Blocks.Interfaces.BooleanInput ChaBoi
      annotation (Placement(transformation(extent={{-140,-110},{-100,-70}})));
    Modelica.Blocks.MathBoolean.Or orHeaPum(nu=3)
      annotation (Placement(transformation(extent={{60,0},{80,20}})));
    Modelica.Blocks.MathBoolean.Or orBoi(nu=4)
      annotation (Placement(transformation(extent={{60,-60},{80,-40}})));
    Modelica.Blocks.Interfaces.BooleanOutput yHeaPum
      annotation (Placement(transformation(extent={{100,20},{120,40}})));
    Modelica.Blocks.Interfaces.BooleanOutput yBoi
      annotation (Placement(transformation(extent={{100,-40},{120,-20}})));
    Buildings.Controls.OBC.CDL.Reals.Hysteresis hys(uLow=TBot - Hys, uHigh=TBot,
      pre_y_start=true)
      annotation (Placement(transformation(extent={{-80,80},{-60,100}})));
    Buildings.Controls.OBC.CDL.Logical.And and2
      annotation (Placement(transformation(extent={{0,-40},{20,-20}})));
    Buildings.Controls.OBC.CDL.Logical.And and1
      annotation (Placement(transformation(extent={{0,-100},{20,-80}})));
    Modelica.Blocks.Logical.Not not1
      annotation (Placement(transformation(extent={{-40,80},{-20,100}})));
    Modelica.Blocks.Sources.BooleanExpression booleanExpression(y=time < 8*3600)
      annotation (Placement(transformation(extent={{-40,32},{-20,52}})));
    Buildings.Controls.OBC.CDL.Logical.And and3
      annotation (Placement(transformation(extent={{0,40},{20,60}})));
  equation
    connect(orHeaPum.y, yHeaPum)
      annotation (Line(points={{81.5,10},{96,10},{96,30},{110,30}},
                                                    color={255,0,255}));
    connect(orBoi.y, yBoi)
      annotation (Line(points={{81.5,-50},{96,-50},{96,-30},{110,-30}},
                                                      color={255,0,255}));
    connect(T_bottom, hys.u)
      annotation (Line(points={{-120,90},{-82,90}}, color={0,0,127},
        pattern=LinePattern.Dash));
    connect(ChaHeaPum, and2.u2) annotation (Line(points={{-120,-30},{-40,-30},{
            -40,-38},{-2,-38}},
                             color={255,0,255},
        pattern=LinePattern.Dash));
    connect(ChaBoi, and1.u2) annotation (Line(points={{-120,-90},{-40,-90},{-40,
            -98},{-2,-98}},
                        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(and1.y, orBoi.u[1]) annotation (Line(points={{22,-90},{50,-90},{50,
            -52.625},{60,-52.625}},
                          color={255,0,255},
        pattern=LinePattern.Dash));
    connect(hys.y, not1.u) annotation (Line(
        points={{-58,90},{-42,90}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(load_on, orHeaPum.u[1]) annotation (Line(
        points={{-120,30},{-80,30},{-80,7.66667},{60,7.66667}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(load_on, orBoi.u[2]) annotation (Line(
        points={{-120,30},{-80,30},{-80,-50.875},{60,-50.875}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(not1.y, and2.u1) annotation (Line(
        points={{-19,90},{-10,90},{-10,-30},{-2,-30}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(not1.y, and1.u1) annotation (Line(
        points={{-19,90},{-10,90},{-10,-90},{-2,-90}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(and2.y, orHeaPum.u[2]) annotation (Line(
        points={{22,-30},{52,-30},{52,10},{60,10}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(and1.y, orBoi.u[3]) annotation (Line(
        points={{22,-90},{50,-90},{50,-49.125},{60,-49.125}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(not1.y, and3.u1) annotation (Line(
        points={{-19,90},{-10,90},{-10,50},{-2,50}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(booleanExpression.y, and3.u2)
      annotation (Line(points={{-19,42},{-2,42}}, color={255,0,255}));
    connect(and3.y, orHeaPum.u[3]) annotation (Line(
        points={{22,50},{40,50},{40,12.3333},{60,12.3333}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    connect(and3.y, orBoi.u[4]) annotation (Line(
        points={{22,50},{40,50},{40,-47.375},{60,-47.375}},
        color={255,0,255},
        pattern=LinePattern.Dash));
    annotation (Icon(coordinateSystem(preserveAspectRatio=false)), Diagram(
          coordinateSystem(preserveAspectRatio=false)),
      Documentation(info="<html>
<p>The inputs are:</p>
<p>- T_bottom, the bottom temperature of the tank</p>
<p>- load_on: boolean, when the load on the secondary side is on, requiring heating to be delivered</p>
<p>- ChaHeaPum: boolean signal indicating it is the optimal time to use the heat pump to charge the tank</p>
<p>- ChaBoi: boolean signal indicating it is the optimal time to use the boiler to charge the tank</p>
<p><br>The heat pump and the boiler start charging at the beginning of the simulation and for 8 hours up until T_bottom &gt; TBot</p>
<p>The heat pump is on when ChaHeaPum is True and T_bottom &lt; TBot</p>
<p>The boiler charges is on  ChaBoi is True and T_bottom &lt; TBot</p>
</html>"));
  end onoff_tank;

  model charge_discharge_soc
    extends Modelica.Blocks.Icons.Block;

    Modelica.Blocks.Interfaces.RealInput soc
      annotation (Placement(transformation(extent={{-140,70},{-100,110}})));
    Modelica.Blocks.Interfaces.RealInput soc_setpoint
      annotation (Placement(transformation(extent={{-140,30},{-100,70}})));
    Modelica.Blocks.Interfaces.RealOutput y
      annotation (Placement(transformation(extent={{100,-10},{120,10}})));
    Modelica.Blocks.Interfaces.RealInput P_discharge
      annotation (Placement(transformation(extent={{-140,-110},{-100,-70}})));
    Modelica.Blocks.Logical.Switch chaSwi "Switch to charge battery"
      annotation (Placement(transformation(extent={{20,-10},{40,10}})));
    Modelica.Blocks.Sources.Constant POff(k=0) "Off power"
      annotation (Placement(transformation(extent={{-80,-40},{-60,-20}})));
    Modelica.Blocks.Logical.Switch disSwi "Switch to discharge battery"
      annotation (Placement(transformation(extent={{20,-76},{40,-56}})));
    Modelica.Blocks.Math.Add3 add3_1
      annotation (Placement(transformation(extent={{60,-10},{80,10}})));
    Modelica.Blocks.Interfaces.RealInput P_charge
      annotation (Placement(transformation(extent={{-140,-70},{-100,-30}})));
    Buildings.Controls.OBC.CDL.Reals.Hysteresis chaHys(uLow=0.00001,
                                                               uHigh=0.05)
      annotation (Placement(transformation(extent={{-40,-10},{-20,10}})));
    Modelica.Blocks.Math.Add add1(k1=-1)
      annotation (Placement(transformation(extent={{-80,-10},{-60,10}})));
    Buildings.Controls.OBC.CDL.Reals.Hysteresis disHys(uLow=0, uHigh=0.05)
      annotation (Placement(transformation(extent={{-40,-76},{-20,-56}})));
    Modelica.Blocks.Math.Add add2(k2=-1)
      annotation (Placement(transformation(extent={{-80,-76},{-60,-56}})));
    Modelica.Blocks.Interfaces.RealInput P_pv
      annotation (Placement(transformation(extent={{-140,-30},{-100,10}})));
    Buildings.Controls.OBC.CDL.Reals.LessThreshold lesThr(t=0.995, h=0.004)
      annotation (Placement(transformation(extent={{-80,50},{-60,70}})));
    Modelica.Blocks.Logical.Switch chaSwi1
                                          "Switch to charge battery"
      annotation (Placement(transformation(extent={{20,60},{40,80}})));
    Modelica.Blocks.Math.Add add3
      annotation (Placement(transformation(extent={{-80,-100},{-60,-80}})));
    Modelica.Blocks.Math.Max max1
      annotation (Placement(transformation(extent={{-40,80},{-20,100}})));
    Modelica.Blocks.Logical.And and1
      annotation (Placement(transformation(extent={{-30,50},{-10,70}})));
    Modelica.Blocks.Logical.Nor nor
      annotation (Placement(transformation(extent={{-76,20},{-56,40}})));
  equation
    connect(POff.y, disSwi.u3) annotation (Line(points={{-59,-30},{10,-30},{10,
            -74},{18,-74}},
                      color={0,0,127}));
    connect(POff.y, chaSwi.u3) annotation (Line(points={{-59,-30},{10,-30},{10,
            -8},{18,-8}},
                     color={0,0,127}));
    connect(add3_1.y, y)
      annotation (Line(points={{81,0},{110,0}}, color={0,0,127}));
    connect(chaHys.y, chaSwi.u2)
      annotation (Line(points={{-18,0},{18,0}},   color={255,0,255}));
    connect(soc, add1.u1) annotation (Line(points={{-120,90},{-92,90},{-92,6},{
            -82,6}},   color={0,0,127}));
    connect(soc_setpoint, add1.u2) annotation (Line(points={{-120,50},{-90,50},
            {-90,-6},{-82,-6}}, color={0,0,127}));
    connect(add1.y, chaHys.u)
      annotation (Line(points={{-59,0},{-42,0}},   color={0,0,127}));
    connect(soc, add2.u1) annotation (Line(points={{-120,90},{-92,90},{-92,-60},
            {-82,-60}}, color={0,0,127}));
    connect(soc_setpoint, add2.u2) annotation (Line(points={{-120,50},{-90,50},
            {-90,-72},{-82,-72}}, color={0,0,127}));
    connect(add2.y, disHys.u)
      annotation (Line(points={{-59,-66},{-42,-66}}, color={0,0,127}));
    connect(disHys.y, disSwi.u2)
      annotation (Line(points={{-18,-66},{18,-66}}, color={255,0,255}));
    connect(soc, lesThr.u) annotation (Line(points={{-120,90},{-92,90},{-92,60},
            {-82,60}}, color={0,0,127}));
    connect(POff.y, chaSwi1.u3) annotation (Line(points={{-59,-30},{10,-30},{10,
            62},{18,62}},
                      color={0,0,127}));
    connect(chaSwi1.y, add3_1.u1) annotation (Line(points={{41,70},{54,70},{54,
            8},{58,8}}, color={0,0,127}));
    connect(chaSwi.y, add3_1.u2) annotation (Line(points={{41,0},{58,0}},
                     color={0,0,127}));
    connect(disSwi.y, add3_1.u3) annotation (Line(points={{41,-66},{50,-66},{50,
            -8},{58,-8}}, color={0,0,127}));
    connect(P_charge, chaSwi.u1) annotation (Line(points={{-120,-50},{0,-50},{0,
            8},{18,8}},        color={0,0,127}));
    connect(P_discharge, add3.u2) annotation (Line(points={{-120,-90},{-94,-90},
            {-94,-96},{-82,-96}},
                                color={0,0,127}));
    connect(P_pv, add3.u1) annotation (Line(points={{-120,-10},{-94,-10},{-94,
            -84},{-82,-84}},
                           color={0,0,127}));
    connect(add3.y, max1.u1) annotation (Line(points={{-59,-90},{-50,-90},{-50,
            -78},{-88,-78},{-88,96},{-42,96}},
                       color={0,0,127}));
    connect(POff.y, max1.u2) annotation (Line(points={{-59,-30},{-50,-30},{-50,
            84},{-42,84}}, color={0,0,127}));
    connect(and1.y, chaSwi1.u2) annotation (Line(points={{-9,60},{0,60},{0,70},
            {18,70}}, color={255,0,255}));
    connect(lesThr.y, and1.u1)
      annotation (Line(points={{-58,60},{-32,60}}, color={255,0,255}));
    connect(max1.y, chaSwi1.u1) annotation (Line(points={{-19,90},{0,90},{0,78},
            {18,78}}, color={0,0,127}));
    connect(add3.y, disSwi.u1) annotation (Line(points={{-59,-90},{6,-90},{6,
            -58},{18,-58}}, color={0,0,127}));
    connect(chaHys.y, nor.u1) annotation (Line(points={{-18,0},{-10,0},{-10,16},
            {-86,16},{-86,30},{-78,30}}, color={255,0,255}));
    connect(disHys.y, nor.u2) annotation (Line(points={{-18,-66},{-12,-66},{-12,
            -46},{-84,-46},{-84,22},{-78,22}}, color={255,0,255}));
    connect(nor.y, and1.u2) annotation (Line(points={{-55,30},{-40,30},{-40,52},
            {-32,52}}, color={255,0,255}));
    annotation (Icon(coordinateSystem(preserveAspectRatio=false)), Diagram(
          coordinateSystem(preserveAspectRatio=false)),
      Documentation(info="<html>
<p>Controller that outputs the charging/discharging power for the battery.</p>
<p>The inputs are:</p>
<p>- <i>soc</i>: the actual state-of-charge of the battery</p>
<p>- <i>soc_setpoint</i>: the setpoint for the state-of-charge of the battery</p>
<p>- <i>P_pv</i>: The electric production from the the PV</p>
<p>- <i>P_charge</i>: the electricity power to charge the battery. </p>
<p>- <i>P_discharge</i>: the electricity consumption from the plant</p>
<p>The output is <i>y</i>, which is the power signal of charging/dischaging of the battery (in W)</p>
<p><br><br>There are three cases:</p>
<p>- <i>soc = soc_setpoint</i>: the battery is idle, there is no active charging/discharging signal. The battery can still be charged by the &quot;free&quot; electricity from the PV. The power delivered to the battery from the PV is P_pv - P_discharge as the PV first compensates the discharge power, and then is power remains, it goes to the baterry</p>
<p>- <i>soc &lt; soc_setpoint</i>: The battery needs to charge to reach soc_setpoint. The charging electric power is equal to P_charge. (To be noted, the charging of the battery will come from both the grid and the PV (P_grid = P_charge - (PV production - Plant electricity power) ) )</p>
<p>- <i>soc &gt; soc_setpoint</i>: The battery needs to discharge to reach soc_setpoint. The discharging electric power is equal to P_discharge - P_pv, as the battery only covers the part of the electric consumption not covered by the PV production. </p>
<p><i>chaHys</i> and <i>disHys</i> avoid simultaneous charging and discharging</p>
</html>"));
  end charge_discharge_soc;

  model charge_input
    extends Modelica.Blocks.Icons.Block;
    Real soc_switch;
    Modelica.Blocks.Interfaces.RealInput signal
      annotation (Placement(transformation(extent={{-140,-20},{-100,20}})));
    Modelica.Blocks.Interfaces.RealInput soc
      annotation (Placement(transformation(extent={{-140,50},{-100,90}})));
    Modelica.Blocks.Interfaces.RealOutput soc_setpoint
      annotation (Placement(transformation(extent={{100,-10},{120,10}})));
    Modelica.Blocks.Math.RealToInteger realToInteger
      annotation (Placement(transformation(extent={{-60,-10},{-40,10}})));
    Modelica.Blocks.Sources.RealExpression realExpression(y=soc_switch)
      annotation (Placement(transformation(extent={{20,-10},{40,10}})));
  equation
    when realToInteger.y == 2 then
      soc_switch = soc;
    end when;
    if realToInteger.y == 2 then
      if der(soc) >= 0 then
        soc_setpoint = max(soc_switch,soc);
      else
        soc_setpoint = soc_switch;
      end if;
    else
      soc_setpoint = signal;
    end if;
    connect(signal, realToInteger.u)
      annotation (Line(points={{-120,0},{-62,0}}, color={0,0,127}));
    annotation (Icon(coordinateSystem(preserveAspectRatio=false)), Diagram(
          coordinateSystem(preserveAspectRatio=false)),
      Documentation(info="<html>
<p>The <i>signal </i>input takes 3 values:</p>
<p>- 0 when discharging</p>
<p>- 1 when charging</p>
<p>- 2 when standby</p>
<p><br>When discharging or charging, <i>soc_setpoint</i> takes the values 0 or 1 respectively. When on standby, <i>soc_setpoint</i> takes the value of <i>soc</i>.</p>
</html>"));
  end charge_input;

end Controls;
