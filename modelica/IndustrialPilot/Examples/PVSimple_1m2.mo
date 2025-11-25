within IndustrialPilot.Examples;
model PVSimple_1m2
  extends Buildings.Electrical.DC.Sources.Examples.PVSimple(
    weaDat(filNam=ModelicaServices.ExternalReferences.loadResource(
          "modelica://IndustrialPilot/Resources/weatherdata/USA_CA_Sacramento.Metro.AP.724839_TMY3.mos")),
    pv(
      A=1,
      fAct=0.9,
      eta=0.19,
      V_nominal=480),
    sou(V=480));
  annotation (experiment(
      StopTime=31536000,
      Interval=3600,
      Tolerance=1e-06,
      __Dymola_Algorithm="Dassl"), Documentation(info="<html>
<p>Model to compute the PV production in W/m2.</p>
</html>"));
end PVSimple_1m2;
