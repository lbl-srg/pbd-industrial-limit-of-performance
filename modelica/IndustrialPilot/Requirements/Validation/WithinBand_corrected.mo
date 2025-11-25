within IndustrialPilot.Requirements.Validation;
model WithinBand_corrected
  extends Modelica.Icons.Example;
  IndustrialPilot.Requirements.WithinBand reqWitBan_modified(
    name="modified",
    u_max=1,
    u_min=-1) annotation (Placement(transformation(extent={{-20,-40},{0,-20}})));
  Buildings_Requirements.WithinBand_old reqWitBan_original(
    name="Original",
    u_max=1,
    u_min=-1) annotation (Placement(transformation(extent={{-20,20},{0,40}})));
  Modelica.Blocks.Sources.Constant const(k=0)
    annotation (Placement(transformation(extent={{-80,-10},{-60,10}})));
equation
  connect(const.y, reqWitBan_original.u) annotation (Line(points={{-59,0},{-40,
          0},{-40,34},{-21,34}}, color={0,0,127}));
  connect(const.y, reqWitBan_modified.u) annotation (Line(points={{-59,0},{-40,
          0},{-40,-26},{-21,-26}}, color={0,0,127}));
end WithinBand_corrected;
