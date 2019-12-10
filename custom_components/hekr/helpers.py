"""Some helpers"""

from hekrapi.protocols.power_meter import VoltageWarning, PowerSupplyWarning, CurrentWarning
from homeassistant.const import STATE_OK, STATE_PROBLEM


def power_meter_attribute_filter(attributes:dict) -> dict:
    consumption = round(attributes.get("current_energy_consumption", 0) * 1000, 1)
    attributes["current_energy_consumption"] = consumption

    if "phase_count" in attributes:
        attributes = {
            attribute: value
            for attribute, value in attributes.items()
            if not (
                    attribute[-2:-1] == '_'
                    and attribute[-1:].isnumeric()
            )
               or int(attribute[-1:]) <= attributes['phase_count']
        }

    attributes['total_current'] = sum([
        value for attribute, value in attributes.items()
        if attribute[:-2] == "current"
    ])

    voltages = [
        value for attribute, value in attributes.items()
        if attribute[:-2] == "voltage" and value
    ]
    if voltages:
        attributes['mean_voltage'] = float(sum(voltages))/len(voltages)

    attributes["state"] = STATE_OK
    if "warning_voltage" in attributes:
        if attributes['warning_voltage'] != VoltageWarning.OK:
            attributes["state"] = STATE_PROBLEM
        attributes['warning_voltage'] = attributes['warning_voltage'].name.lower()

    if "warning_battery" in attributes:
        if attributes['warning_battery'] != PowerSupplyWarning.OK:
            attributes["state"] = STATE_PROBLEM
        attributes["warning_battery"] = attributes["warning_battery"].name.lower()

    if "warning_current" in attributes:
        if attributes['warning_current'] != CurrentWarning.OK:
            attributes["state"] = STATE_PROBLEM
        attributes['warning_current'] = attributes['warning_current'].name.lower()

    return attributes
