""" Constants """

import voluptuous as vol
from datetime import timedelta
from pydoc import locate

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_DEVICE_ID, CONF_HOST, CONF_PORT, CONF_NAME, CONF_PROTOCOL,
    ENERGY_KILO_WATT_HOUR, POWER_WATT, ATTR_ICON, ATTR_NAME,
    CONF_SENSORS, CONF_UNIT_OF_MEASUREMENT, CONF_SCAN_INTERVAL)

from hekrapi.protocol import Protocol
from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from hekrapi.protocols.power_meter import PROTOCOL as PROTOCOL_POWER_METER

if __name__ == '__main__':
    power_meter_attribute_filter = lambda x: x
else:
    from .helpers import power_meter_attribute_filter

DOMAIN = "hekr"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

DEFAULT_SENSOR_ICON = "mdi:flash"
DEFAULT_QUERY_COMMAND = "queryDev"

UNIT_VOLTAGE = "V"
UNIT_CURRENT = "A"
UNIT_ENERGY_CONSUMED = ENERGY_KILO_WATT_HOUR
UNIT_POWER_FACTOR = None
UNIT_POWER_ACTIVE = POWER_WATT
UNIT_POWER_REACTIVE = "kVa"
UNIT_CURRENT_CONSUMPTION = 'W'

CONF_DEVICE_ID = CONF_DEVICE_ID
CONF_CONTROL_KEY = "control_key"
CONF_APPLICATION_ID = "application_id"
CONF_UPDATE_COMMANDS = "update_commands"
CONF_PROTOCOL_DEFINITION = "protocol_definition"
CONF_COMMAND_ID = "command_id"
CONF_ARGUMENTS = "arguments"
CONF_BYTE_LENGTH = "byte_length"
CONF_VARIABLE = "variable"
CONF_MULTIPLIER = "multiplier"
CONF_DECIMALS = "decimals"
CONF_FRAME_TYPE = "frame_type"
CONF_RESPONSE_COMMAND_ID = "response_command_id"
CONF_VALUE_MIN = "value_min"
CONF_VALUE_MAX = "value_max"
CONF_TYPE_INPUT = "type_input"
CONF_TYPE_OUTPUT = "type_output"
CONF_FUNC_FILTER_ATTRIBUTES = "attribute_filter_function"
CONF_DEFAULT_SENSORS = "default_group"

ATTR_STATE_ATTRIBUTE = "state_attribute"
ATTR_MONITORED_ATTRIBUTES = "monitored_attributes"
ATTR_NAME = ATTR_NAME
ATTR_ICON = ATTR_ICON

MONITORED_CONDITIONS_ALL = "all"

SENSOR_GROUP_SCHEMA = vol.Schema({
    vol.Optional(ATTR_STATE_ATTRIBUTE, default=None): cv.string,
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_ICON, default=DEFAULT_SENSOR_ICON): cv.icon,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.Any(cv.string, None),
    vol.Optional(ATTR_MONITORED_ATTRIBUTES, default=False): vol.Any([cv.string], cv.boolean),
    vol.Optional(CONF_UPDATE_COMMANDS, default=None): vol.All(cv.ensure_list, [cv.string]),
})

# Protocol definition schema (example below)
SUPPORTED_PROTOCOL_SCHEMA = vol.Schema({
    # @TODO: add file loading for CONF_PROTOCOL_DEFINITION
    vol.Required(CONF_PROTOCOL_DEFINITION): Protocol,
    vol.Optional(CONF_FUNC_FILTER_ATTRIBUTES): callable,
    vol.Optional(CONF_DEFAULT_SENSORS, default=None): cv.ensure_list,
    vol.Optional(CONF_SENSORS, default=None): {cv.string: SENSOR_GROUP_SCHEMA}
})

# Predefined protocol support
SUPPORTED_SENSOR_PROTOCOLS = {
    "power_meter": {
        CONF_PROTOCOL_DEFINITION: PROTOCOL_POWER_METER,
        CONF_FUNC_FILTER_ATTRIBUTES: power_meter_attribute_filter,
        CONF_DEFAULT_SENSORS: ["total_consumption", "status", "current_consumption"],
        CONF_SENSORS: {
            # queryDev-related sensors
            "status": {
                ATTR_NAME: "Status", ATTR_ICON: 'mdi:counter',
                ATTR_STATE_ATTRIBUTE: "state",
                ATTR_MONITORED_ATTRIBUTES: ["phase_count", "warning_voltage" , "warning_current", "warning_battery"],
                CONF_UPDATE_COMMANDS: ['queryDev'],
            },
            "current_consumption": {
                ATTR_NAME: "Current Consumption", ATTR_ICON: 'mdi:counter',
                ATTR_STATE_ATTRIBUTE: "current_energy_consumption", CONF_UNIT_OF_MEASUREMENT: UNIT_CURRENT_CONSUMPTION,
                ATTR_MONITORED_ATTRIBUTES: False,
                CONF_UPDATE_COMMANDS: ['queryDev'],
            },
            "total_consumption": {
                ATTR_NAME: "Total Consumption", ATTR_ICON: "mdi:counter",
                ATTR_STATE_ATTRIBUTE: "total_energy_consumed", CONF_UNIT_OF_MEASUREMENT: UNIT_ENERGY_CONSUMED,
                ATTR_MONITORED_ATTRIBUTES: False,
                CONF_UPDATE_COMMANDS: ['queryDev'],  # by protocol definition, this can also be fetched via queryData
            },
            # queryData-related sensors
            "voltage": {
                ATTR_NAME: "Voltage", ATTR_ICON: "mdi:alpha-v-circle",
                ATTR_STATE_ATTRIBUTE: "mean_voltage", CONF_UNIT_OF_MEASUREMENT: UNIT_VOLTAGE,
                ATTR_MONITORED_ATTRIBUTES: ["voltage_1", "voltage_2", "voltage_3", "max_voltage", "min_voltage",
                                            "current_frequency"],
                CONF_UPDATE_COMMANDS: ['queryData'],
            },
            "current": {
                ATTR_NAME: "Current", ATTR_ICON: "mdi:alpha-i-circle",
                ATTR_STATE_ATTRIBUTE: "total_current", CONF_UNIT_OF_MEASUREMENT: UNIT_CURRENT,
                ATTR_MONITORED_ATTRIBUTES: ["current_1", "current_2", "current_3", "max_current", "current_frequency"],
                CONF_UPDATE_COMMANDS: ['queryData'],
            },
            "power_factor": {
                ATTR_NAME: "Power Factor", ATTR_ICON: "mdi:speedometer",
                ATTR_STATE_ATTRIBUTE: "total_power_factor", CONF_UNIT_OF_MEASUREMENT: UNIT_POWER_FACTOR,
                ATTR_MONITORED_ATTRIBUTES: ["power_factor_1", "power_factor_2", "power_factor_3"],
                CONF_UPDATE_COMMANDS: ['queryData'],
            },
            "active_power": {
                ATTR_NAME: "Active Power", ATTR_ICON: "mdi:flash",
                ATTR_STATE_ATTRIBUTE: "current_energy_consumption", CONF_UNIT_OF_MEASUREMENT: UNIT_POWER_ACTIVE,
                ATTR_MONITORED_ATTRIBUTES: ["active_power_1", "active_power_2", "active_power_3"],
                CONF_UPDATE_COMMANDS: ['queryData'],
            },
            "reactive_power": {
                ATTR_NAME: "Reactive Power", ATTR_ICON: "mdi:flash-outline",
                ATTR_STATE_ATTRIBUTE: "total_reactive_power", CONF_UNIT_OF_MEASUREMENT: UNIT_POWER_REACTIVE,
                ATTR_MONITORED_ATTRIBUTES: ["reactive_power_1", "reactive_power_2", "reactive_power_3"],
                CONF_UPDATE_COMMANDS: ['queryData'],
            }
        },
    }
}

PROTOCOL_REQUIREMENT = vol.Any(
    vol.All(
        cv.string,
        vol.In(SUPPORTED_SENSOR_PROTOCOLS),
        vol.Coerce(lambda v: SUPPORTED_SENSOR_PROTOCOLS[v])
    ),
    SUPPORTED_PROTOCOL_SCHEMA
)

DEVICE_SCHEMA_DICT = {
    # @TODO: add file loading for CONF_PROTOCOL
    vol.Required(CONF_PROTOCOL): PROTOCOL_REQUIREMENT,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_CONTROL_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=10000): cv.port,
    vol.Optional(CONF_APPLICATION_ID, default="test"): cv.string,
}


SENSOR_PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA\
    .extend(DEVICE_SCHEMA_DICT)\
    .extend({
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=MIN_TIME_BETWEEN_UPDATES): cv.time_period,
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [cv.string]),  # @TODO: add sensor group existence verification
        vol.Required(CONF_PROTOCOL): vol.All(
            PROTOCOL_REQUIREMENT
        ),
    })


if __name__ == '__main__':
    from json import  dumps
    base_platform = {
        'platform': DOMAIN,
        'device_id': 'test',
        'control_key': 'test',
        'host': 'test',
    }
    for name, definition in SUPPORTED_SENSOR_PROTOCOLS.items():
        print(dumps(SENSOR_PLATFORM_SCHEMA({**base_platform, 'protocol': name}), indent=2, default=str))
        print(dumps(SENSOR_PLATFORM_SCHEMA({**base_platform, 'protocol': definition}), indent=2, default=str))
        #if isinstance(definition[CONF_PROTOCOL_DEFINITION], Protocol):
        #    definition[CONF_PROTOCOL_DEFINITION].print_definition()
