within IndustrialPilot.Examples;
package Data
extends Modelica.Icons.Package;

  record Design
    extends Modelica.Icons.Record;
    parameter Modelica.Units.SI.HeatFlowRate QCon_flow_nominal
      "Heat pump condenser capacity";
    parameter Modelica.Units.SI.HeatFlowRate QGas_flow_nominal
      "Gas boiler capacity";
    parameter Modelica.Units.SI.Energy ETan
      "Energy content of the tank";
    parameter Modelica.Units.SI.Energy EBat
      "Battery electrical storage";
    parameter Modelica.Units.SI.HeatFlowRate QLoa_flow_nominal
      "Maximum heat load of process";
    parameter Modelica.Units.SI.Area surPv
      "PV surface";
      annotation(
      defaultComponentName = "dat",
      defaultComponentPrefixes = "parameter");

  end Design;
end Data;
