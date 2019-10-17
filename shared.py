""" Constants """

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_DEVICE_ID, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_PROTOCOL, CONF_NAME,
    ENERGY_KILO_WATT_HOUR, POWER_WATT, ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON, ATTR_NAME)

from .hekrapi.protocol import load_protocol_definitions
from .helpers import power_meter_attribute_filter

DOMAIN = "hekr"

PROTOCOL_DEFINITIONS = load_protocol_definitions()

DEFAULT_SENSOR_ICON = "mdi:flash"
DEFAULT_QUERY_COMMAND = "queryDev"

UNIT_VOLTAGE = "V"
UNIT_CURRENT = "A"
UNIT_ENERGY_CONSUMED = ENERGY_KILO_WATT_HOUR
UNIT_POWER_FACTOR = None
UNIT_POWER_ACTIVE = POWER_WATT
UNIT_POWER_REACTIVE = "kVa"

CONF_DEVICE_ID = CONF_DEVICE_ID
CONF_CONTROL_KEY = "control_key"
CONF_HOST = CONF_HOST
CONF_PROTOCOL = CONF_PROTOCOL
CONF_SCAN_INTERVAL = CONF_SCAN_INTERVAL
CONF_APPLICATION_ID = "application_id"
CONF_NAME = CONF_NAME

ATTR_STATE_ATTRIBUTE = "state_attribute"
ATTR_MONITORED_ATTRIBUTES = "monitored_attributes"
ATTR_UPDATE_COMMANDS = "update_commands"
ATTR_SENSOR_GROUPS = "sensor_groups"
ATTR_NAME = ATTR_NAME
ATTR_ICON = ATTR_ICON
ATTR_FUNC_FILTER_ATTRIBUTES = "attribute_filter_function"

DEVICE_CONFIG_FIELDS = {
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_CONTROL_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=10000): cv.port,
    vol.Required(CONF_PROTOCOL): vol.All(cv.string, vol.In(list(PROTOCOL_DEFINITIONS.keys()))),
    vol.Optional(CONF_SCAN_INTERVAL, default=15): cv.time_period,
    vol.Optional(CONF_APPLICATION_ID, default="test"): cv.string,
    vol.Optional(CONF_NAME): cv.string,
}
DEVICE_CONFIG_SCHEMA = vol.Schema(DEVICE_CONFIG_FIELDS)

MONITORED_CONDITIONS_ALL = "all"

SUPPORTED_SENSOR_PROTOCOLS = {
    "power_meter": {
        ATTR_SENSOR_GROUPS: {
            "total_consumption": {
                ATTR_NAME: "Total Consumption", ATTR_ICON:"mdi:counter",
                ATTR_STATE_ATTRIBUTE: "total_energy_consumed", ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
                ATTR_MONITORED_ATTRIBUTES: [],
            },
            "meter": {
                ATTR_NAME: "Meter", ATTR_ICON:"mdi:switch", 
                ATTR_STATE_ATTRIBUTE: "switch_state", ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_MONITORED_ATTRIBUTES: ["phase_count", "warning_battery", "delay_enabled", "delay_timer"],
            },
            "voltage": {
                ATTR_NAME: "Voltage", ATTR_ICON:"mdi:alpha-v-circle",
                ATTR_STATE_ATTRIBUTE: "mean_voltage", ATTR_UNIT_OF_MEASUREMENT: UNIT_VOLTAGE,
                ATTR_MONITORED_ATTRIBUTES: ["voltage_1", "voltage_2", "voltage_3", "max_voltage", "min_voltage", "current_frequency", "warning_voltage"]
            },
            "current": {
                ATTR_NAME: "Current", ATTR_ICON:"mdi:alpha-i-circle",
                ATTR_STATE_ATTRIBUTE: "total_current", ATTR_UNIT_OF_MEASUREMENT: UNIT_CURRENT,
                ATTR_MONITORED_ATTRIBUTES: ["current_1", "current_2", "current_3", "max_current", "current_frequency", "warning_current"]
            },
            "power_factor": {
                ATTR_NAME: "Power Factor", ATTR_ICON:"mdi:speedometer",
                ATTR_STATE_ATTRIBUTE: "total_power_factor", ATTR_UNIT_OF_MEASUREMENT: UNIT_POWER_FACTOR,
                ATTR_MONITORED_ATTRIBUTES: ["power_factor_1", "power_factor_2", "power_factor_3"]
            },
            "active_power": {
                ATTR_NAME: "Active Power", ATTR_ICON:"mdi:flash",
                ATTR_STATE_ATTRIBUTE: "current_energy_consumption", ATTR_UNIT_OF_MEASUREMENT: UNIT_POWER_ACTIVE,
                ATTR_MONITORED_ATTRIBUTES: ["active_power_1", "active_power_2", "active_power_3"]
            },
            "reactive_power": {
                ATTR_NAME: "Reactive Power", ATTR_ICON:"mdi:flash-outline",
                ATTR_STATE_ATTRIBUTE: "total_reactive_power", ATTR_UNIT_OF_MEASUREMENT: UNIT_POWER_REACTIVE,
                ATTR_MONITORED_ATTRIBUTES: ["reactive_power_1", "reactive_power_2", "reactive_power_3"]
            }
        },
        ATTR_UPDATE_COMMANDS: ["queryDev", "queryData"], # Should be: queryDev, queryData; but timeouts are an ass
        ATTR_STATE_ATTRIBUTE: "total_energy_consumed",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_FUNC_FILTER_ATTRIBUTES: power_meter_attribute_filter,
    }
}