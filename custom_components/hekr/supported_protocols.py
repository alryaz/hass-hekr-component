"""Supported protocols for Hekr devices."""

__all__ = [
    "SUPPORTED_PROTOCOLS",
    "POWER_METER",
]

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.components.switch import DEVICE_CLASS_SWITCH
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    STATE_OFF,
    STATE_OK,
    STATE_ON,
    STATE_PROBLEM,
)

from hekrapi.protocols.power_meter import (
    CurrentWarning,
    PROTOCOL as PROTOCOL_POWER_METER,
    PowerSupplyWarning,
    VoltageWarning,
)
from hekrapi.protocols.power_socket import PROTOCOL as PROTOCOL_POWER_SOCKET
from .const import (
    ATTR_MONITORED,
    PROTOCOL_CMD_RECEIVE,
    PROTOCOL_CMD_TURN_OFF,
    PROTOCOL_CMD_TURN_ON,
    PROTOCOL_CMD_UPDATE,
    PROTOCOL_DEFAULT,
    PROTOCOL_DEFINITION,
    PROTOCOL_FILTER,
    PROTOCOL_MANUFACTURER,
    PROTOCOL_MODEL,
    PROTOCOL_NAME,
    PROTOCOL_PORT,
    PROTOCOL_SENSORS,
    PROTOCOL_SWITCHES,
)


def power_meter_attribute_filter(attributes: dict) -> dict:
    if "current_energy_consumption" in attributes:
        attributes["current_energy_consumption"] = round(
            attributes["current_energy_consumption"] * 1000, 1
        )

    if "total_active_power" in attributes:
        attributes["total_active_power"] = round(attributes["total_active_power"] * 1000, 1)

    # filter attributes by phase count
    if "phase_count" in attributes:
        attributes = {
            attribute: value
            for attribute, value in attributes.items()
            if not (attribute[-2:] == "_" and attribute[-1:].isnumeric())
            or int(attribute[-1:]) <= attributes["phase_count"]
        }

    # get mean current
    if "current_1" in attributes:
        currents = [
            value for attribute, value in attributes.items() if attribute[:-1] == "current_"
        ]
        total_current = sum(currents)
        attributes["mean_current"] = round(float(total_current) / len(currents), 3)
        attributes["total_current"] = total_current

    # get mean voltages
    if "voltage_1" in attributes:
        voltages = [
            value
            for attribute, value in attributes.items()
            if attribute[:-1] == "voltage_" and value
        ]
        attributes["mean_voltage"] = round(float(sum(voltages)) / len(voltages), 1)

    # detect state of the device
    attributes["state"] = STATE_OK
    if "warning_voltage" in attributes:
        if attributes["warning_voltage"] != VoltageWarning.OK:
            attributes["state"] = STATE_PROBLEM
        attributes["warning_voltage"] = attributes["warning_voltage"].name.lower()

    if "warning_battery" in attributes:
        if attributes["warning_battery"] != PowerSupplyWarning.OK:
            attributes["state"] = STATE_PROBLEM
        attributes["warning_battery"] = attributes["warning_battery"].name.lower()

    if "warning_current" in attributes:
        if attributes["warning_current"] != CurrentWarning.OK:
            attributes["state"] = STATE_PROBLEM
        attributes["warning_current"] = attributes["warning_current"].name.lower()

    # process switch state
    if "switch_state" in attributes:
        attributes["switch_state"] = STATE_ON if attributes["switch_state"] else STATE_OFF

    return attributes


# Predefined protocol support
POWER_METER = {
    PROTOCOL_NAME: "Power Meter",
    PROTOCOL_MODEL: "DDS238-4 W",
    PROTOCOL_MANUFACTURER: "HIKING (TOMZN)",
    PROTOCOL_PORT: 10000,
    PROTOCOL_DEFINITION: PROTOCOL_POWER_METER,
    PROTOCOL_FILTER: power_meter_attribute_filter,
    PROTOCOL_SENSORS: {
        "general": {
            ATTR_NAME: "General Information",
            ATTR_ICON: "mdi:eye",
            ATTR_STATE: "state",
            ATTR_MONITORED: True,
            PROTOCOL_CMD_UPDATE: "queryDev",
            PROTOCOL_CMD_RECEIVE: "reportDev",
            PROTOCOL_DEFAULT: False,
        },
        "detailed": {
            ATTR_NAME: "Detailed Information",
            ATTR_ICON: "mdi:eye-settings",
            ATTR_STATE: "state",
            ATTR_MONITORED: True,
            PROTOCOL_CMD_UPDATE: "queryData",
            PROTOCOL_CMD_RECEIVE: "reportData",
            PROTOCOL_DEFAULT: False,
        },
        # queryDev-related sensors
        "status": {
            ATTR_NAME: "Status",
            ATTR_ICON: {
                STATE_PROBLEM: "mdi:alert",
                STATE_OK: "mdi:check-circle",
                PROTOCOL_DEFAULT: "mdi:help-circle",
            },
            ATTR_STATE: "state",
            ATTR_MONITORED: [
                "phase_count",
                "warning_voltage",
                "warning_current",
                "warning_battery",
            ],
            PROTOCOL_CMD_UPDATE: "queryDev",
            PROTOCOL_CMD_RECEIVE: "reportDev",
            PROTOCOL_DEFAULT: True,
        },
        "current_consumption": {
            ATTR_NAME: "Current Consumption",
            ATTR_ICON: "mdi:gauge",
            ATTR_STATE: "current_energy_consumption",
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            PROTOCOL_CMD_UPDATE: "queryDev",
            PROTOCOL_CMD_RECEIVE: "reportDev",
            PROTOCOL_DEFAULT: True,
        },
        "total_consumption": {
            ATTR_NAME: "Total Consumption",
            ATTR_ICON: "mdi:sigma",
            ATTR_STATE: "total_energy_consumed",
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
            ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            PROTOCOL_CMD_UPDATE: "queryDev",
            PROTOCOL_CMD_RECEIVE: "reportDev",
            PROTOCOL_DEFAULT: True,
        },
        # queryData-related sensors
        "voltage": {
            ATTR_NAME: "Mean Voltage",
            ATTR_ICON: "mdi:alpha-v-circle",
            ATTR_STATE: "mean_voltage",
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_VOLTAGE,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_MONITORED: [
                "voltage_1",
                "voltage_2",
                "voltage_3",
                "current_frequency",
            ],
            PROTOCOL_CMD_UPDATE: "queryData",
            PROTOCOL_CMD_RECEIVE: "reportData",
            PROTOCOL_DEFAULT: False,
        },
        "current": {
            ATTR_NAME: "Total Current",
            ATTR_ICON: "mdi:alpha-i-circle",
            ATTR_STATE: "total_current",
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_MONITORED: [
                "mean_current",
                "current_1",
                "current_2",
                "current_3",
                "current_frequency",
            ],
            PROTOCOL_CMD_UPDATE: "queryData",
            PROTOCOL_CMD_RECEIVE: "reportData",
            PROTOCOL_DEFAULT: False,
        },
        "power_factor": {
            ATTR_NAME: "Power Factor",
            ATTR_ICON: "mdi:speedometer",
            ATTR_STATE: "total_power_factor",
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER_FACTOR,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_MONITORED: ["power_factor_1", "power_factor_2", "power_factor_3"],
            PROTOCOL_CMD_UPDATE: "queryData",
            PROTOCOL_CMD_RECEIVE: "reportData",
            PROTOCOL_DEFAULT: False,
        },
        "active_power": {
            ATTR_NAME: "Active Power",
            ATTR_ICON: "mdi:flash",
            ATTR_STATE: "total_active_power",
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_MONITORED: ["active_power_1", "active_power_2", "active_power_3"],
            PROTOCOL_CMD_UPDATE: "queryData",
            PROTOCOL_CMD_RECEIVE: "reportData",
            PROTOCOL_DEFAULT: False,
        },
        "reactive_power": {
            ATTR_NAME: "Reactive Power",
            ATTR_ICON: "mdi:flash-outline",
            ATTR_STATE: "total_reactive_power",
            ATTR_UNIT_OF_MEASUREMENT: "kVar",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_MONITORED: [
                "reactive_power_1",
                "reactive_power_2",
                "reactive_power_3",
            ],
            PROTOCOL_CMD_UPDATE: "queryData",
            PROTOCOL_CMD_RECEIVE: "reportData",
            PROTOCOL_DEFAULT: False,
        },
    },
    PROTOCOL_SWITCHES: {
        "main_power": {
            ATTR_NAME: "Main Power",
            ATTR_ICON: {
                STATE_ON: "mdi:electric-switch-closed",
                PROTOCOL_DEFAULT: "mdi:electric-switch",
            },
            ATTR_STATE: "switch_state",
            ATTR_DEVICE_CLASS: DEVICE_CLASS_SWITCH,
            PROTOCOL_CMD_UPDATE: "queryDev",
            PROTOCOL_CMD_RECEIVE: "reportDev",
            PROTOCOL_CMD_TURN_ON: ("setSw", {"switch_state": True}),
            PROTOCOL_CMD_TURN_OFF: ("setSw", {"switch_state": False}),
            PROTOCOL_DEFAULT: True,
        }
    },
}


def power_socket_attribute_filter(attributes: dict) -> dict:
    if "power" in attributes:
        attributes["power"] = STATE_ON if attributes["power"] else STATE_OFF

    return attributes


POWER_SOCKET = {
    PROTOCOL_NAME: "Power Socket",
    PROTOCOL_PORT: 10000,
    PROTOCOL_DEFINITION: PROTOCOL_POWER_SOCKET,
    PROTOCOL_FILTER: power_socket_attribute_filter,
    PROTOCOL_SWITCHES: {
        "main_power": {
            ATTR_NAME: "Main Power",
            ATTR_ICON: {
                STATE_ON: "hass:power-plug",
                PROTOCOL_DEFAULT: "hass:power-plug-off",
            },
            ATTR_STATE: "power",
            ATTR_DEVICE_CLASS: DEVICE_CLASS_SWITCH,
            PROTOCOL_CMD_UPDATE: "Quary",
            PROTOCOL_CMD_RECEIVE: "Report",
            PROTOCOL_CMD_TURN_ON: ("SetPower", {"power": True}),
            PROTOCOL_CMD_TURN_OFF: ("SetPower", {"power": False}),
            PROTOCOL_DEFAULT: True,
        }
    },
}

SUPPORTED_PROTOCOLS = {
    "power_meter": POWER_METER,
    "power_socket": POWER_SOCKET,
}
