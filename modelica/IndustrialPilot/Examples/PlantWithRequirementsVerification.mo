within IndustrialPilot.Examples;
model PlantWithRequirementsVerification
  "Plant model with requirement verification"
  extends Plant(
    senTEvaEnt(T_start=281.15),
    pumEva(T_start=281.15),
    heaPum(T2_start=277.15),
    senTEvaLvg(T_start=277.15));
  inner Modelica_Requirements.Verify.PrintViolations printViolations
    "Print requirement verification"
    annotation (Placement(transformation(extent={{500,40},{520,60}})));
  Requirements.WithinBand reqWitBan(
    name="Supply temperature",
    text="T-O-2.3: Supply temperature out of range.",
    delayTime(displayUnit="min") = 300,
    u_max(
      final unit="K",
      displayUnit="degC") = 363.65,
    u_min(
      final unit="K",
      displayUnit="degC") = 362.65,
    u(final unit="K", displayUnit="degC"),
    witBan(u(final unit="K", displayUnit="degC")), use_activeInput = true)
    annotation (Placement(transformation(origin = {0, 10}, extent = {{460, 18}, {480, 38}})));
  Requirements.MinimumDuration reqHeaPumOn(
    name="Heat pump",
    text="T-O-2.5: Heat pump must operate at least 30 min.",
    durationMin(displayUnit="min") = 1800) "Requirement for heat pump on"
    annotation (Placement(transformation(extent={{460,-140},{480,-120}})));
  Requirements.MinimumDuration reqGasOn(
    name="Gas",
    text="T-O-2.5: Gas furnace must operate at least 15 min.",
    durationMin(displayUnit="min") = 900) "Requirement for gas furnace on"
    annotation (Placement(transformation(extent={{460,-218},{480,-198}})));

  Requirements.GreaterEqual reqGasFurLea(
    name="Gas",
    text="T-O-2.7: Gas furnace leaving water temperature must not exceed 95 degC")
    "Requirement for gas furnace leaving water temperature"
    annotation (Placement(transformation(extent={{460,-100},{480,-80}})));
  Modelica.Blocks.Sources.Constant con95(k(
      final unit="K",
      displayUnit="degC") = 368.15) "Constant that outputs 95 degC"
    annotation (Placement(transformation(origin = {0, -22}, extent = {{400, -58}, {420, -38}})));
  Requirements.GreaterEqual reqHeaPumConLea(
    name="Heat pump",
    text="T-O-2.7: Heat pump condenser leaving water temperature must not exceed 95 degC")
    "Requirement for heat pump condenser leaving water temperature"
    annotation (Placement(transformation(extent={{460,-60},{480,-40}})));
  Requirements.MinimumDuration reqHeaPumOff(
    name="Heat pump",
    text="T-O-2.5: Heat pump must be off for at least 10 min.",
    durationMin(displayUnit="min") = 600) "Requirement for heat pump off"
    annotation (Placement(transformation(extent={{460,-180},{480,-160}})));
  Buildings.Controls.OBC.CDL.Logical.Not heaPumOff
    "Outputs true if heat pump is off"
    annotation (Placement(transformation(origin = {100, -38}, extent = {{300, -142}, {320, -122}})));
  Requirements.WithinBand reqHeaPumEvaTemDif(
    name="Heat pump",
    text="T-O-2.8: Heat pump evaporator temperature difference must be 4 K +/- 0.25 K.",
    use_activeInput=true,
    delayTime(displayUnit="min") = 300,
    u_max(
      final unit="K",
      displayUnit="K") = 4.25,
    u_min(
      final unit="K",
      displayUnit="K") = 3.75,
    u(final unit="K", displayUnit="K"),
    witBan(u(final unit="K")))
    "Requirment for heat pump evaporator temperature difference"
    annotation (Placement(transformation(extent={{460,-258},{480,-238}})));
  Buildings.Controls.OBC.CDL.Reals.Subtract dTHeaPumEva
    "Temperature difference heat pump evaporator circuit"
    annotation (Placement(transformation(origin={120,20},   extent = {{260, -260}, {280, -240}})));
  Requirements.StableContinuousSignal reqStaLoaVal(name="Supply temperature",
      text="T-O-2.10: All control valves must be stable")
    "Requirements to verify stability of control valve at load"
    annotation (Placement(transformation(origin = {0, -8}, extent = {{460, -22}, {480, -2}})));
  Requirements.StableContinuousSignal reqStaValGas(name="Gas", text=
        "T-O-2.10: All control valves must be stable")
    "Requirements to verify stability of control valve at gas boiler"
    annotation (Placement(transformation(extent={{462,-298},{482,-278}})));
  Requirements.StableContinuousSignal reqStaValHeaPum(
    name="Heat pump",
    text="T-O-2.10: All control valves must be stable")
    "Requirements to verify stability of control valve at heat pump"
    annotation (Placement(transformation(extent={{460,-340},{480,-320}})));
  IndustrialPilot.Requirements.GreaterEqual reqLoaRetTem(name = "Return water temperature", text = "T-O-2.4: Return water temperature from process load heat exchanger must be at least 69 degC while the process is active", use_activeInput = true) "Requirement for load return water temperature" annotation(
    Placement(transformation(origin = {0, 60}, extent = {{460, -60}, {480, -40}})));
  Modelica.Blocks.Sources.Constant con69(
    k(unit="K", displayUnit="degC") = 342.15) "Constant that outputs 69 degC" annotation(
    Placement(transformation(origin = {-20, 117}, extent = {{400, -58}, {420, -38}})));
equation
  connect(reqWitBan.u, senTLoaPriEnt.T) annotation(
    Line(points={{459,42},{340,42},{340,226},{-40,226},{-40,210},{-21,210}},                                    color = {0, 0, 127}));
  connect(con95.y, reqGasFurLea.u_max) annotation(
    Line(points = {{421, -70}, {440, -70}, {440, -84}, {459, -84}}, color = {0, 0, 127}));
  connect(reqGasFurLea.u_min, senTBoiLvg.T) annotation(
    Line(points={{459,-88},{116,-88},{116,-112},{-128,-112},{-128,-170},{-121,-170}},            color = {0, 0, 127}));
  connect(reqHeaPumConLea.u_min, senTConLvg.T) annotation(
    Line(points={{459,-48},{180,-48},{180,-70},{-348,-70},{-348,-170},{-341,-170}},            color = {0, 0, 127}));
  connect(con95.y, reqHeaPumConLea.u_max) annotation(
    Line(points = {{421, -70}, {440, -70}, {440, -44}, {459, -44}}, color = {0, 0, 127}));
  connect(heaPumOff.y, reqHeaPumOff.u) annotation(
    Line(points = {{422, -170}, {458, -170}}, color = {255, 0, 255}));
  connect(senTEvaEnt.T, dTHeaPumEva.u1) annotation(
    Line(points={{-341,-330},{-352,-330},{-352,-400},{350,-400},{350,-224},{378,
          -224}},                                                                                                                              color = {0, 0, 127}));
  connect(senTEvaLvg.T, dTHeaPumEva.u2) annotation(
    Line(points={{-301,-330},{-308,-330},{-308,-392},{360,-392},{360,-236},{378,
          -236}},                                                                                                  color = {0, 0, 127}));
  connect(dTHeaPumEva.y, reqHeaPumEvaTemDif.u) annotation(
    Line(points={{402,-230},{448,-230},{448,-244},{459,-244}},
                                              color = {0, 0, 127}));
  connect(reqStaLoaVal.u, conPIDLoa.y) annotation(
    Line(points={{459,-16},{360,-16},{360,90},{-60,90},{-60,130},{-138,130}},                               color = {0, 0, 127}));
  connect(reqStaValGas.u, conPIDBoi.y) annotation(
    Line(points={{461,-284},{-20,-284},{-20,-340},{-112,-340},{-112,-330},{-118,
          -330}},                                                      color = {0, 0, 127}));
  connect(reqStaValHeaPum.u, conPIDHp.y) annotation(
    Line(points={{459,-326},{440,-326},{440,-380},{-210,-380},{-210,-110},{-358,
          -110}},                                                                                               color = {0, 0, 127}));
  connect(loaOn.y, reqWitBan.active) annotation(
    Line(points={{-98,330},{-92,330},{-92,356},{270,356},{270,34},{458,34}},              color = {255, 0, 255}));
  connect(reqLoaRetTem.u_max, senTLoaPriLvg.T) annotation(
    Line(points={{459,16},{304,16},{304,142},{14,142},{14,190},{19,190}},              color = {0, 0, 127}));
  connect(reqLoaRetTem.active, loaOn.y) annotation(
    Line(points={{458,6},{270,6},{270,356},{-92,356},{-92,330},{-98,330}},              color = {255, 0, 255}));
  connect(reqLoaRetTem.u_min, con69.y) annotation(
    Line(points={{459,12},{410,12},{410,69},{401,69}},          color = {0, 0, 127}));
  connect(holdHeaPum.y, reqHeaPumOn.u) annotation (Line(points={{290,-82},{290,
          -130},{458,-130}}, color={255,0,255}));
  connect(holdHeaPum.y, heaPumOff.u) annotation (Line(points={{290,-82},{290,
          -170},{398,-170}}, color={255,0,255}));
  connect(holdHeaPum.y, reqHeaPumEvaTemDif.active) annotation (Line(points={{
          290,-82},{290,-252},{458,-252}}, color={255,0,255}));
  connect(holdBoi.y, reqGasOn.u) annotation (Line(points={{250,-82},{250,-208},
          {458,-208}}, color={255,0,255}));
  annotation (
    experiment(
      StopTime=172800,
      __Dymola_NumberOfIntervals=500,
      Tolerance=1e-06,
      __Dymola_Algorithm="Radau"),
    Documentation(info="<html>
<p>
Model with requirement verification.
</p>
<p>
This is the same model as
<a href=\"modelica://IndustrialPilot.Examples.Plant\">
IndustrialPilot.Examples.Plant</a>
except that it adds requirements verification.
</p>
</html>", revisions="<html>
<ul>
<li>
December 23, 2024, by Michael Wetter:<br/>
First implementation.
</li>
</html>"));
end PlantWithRequirementsVerification;
