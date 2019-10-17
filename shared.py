""" Constants """

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, ENERGY_KILO_WATT_HOUR, CONF_PROTOCOL

import hekrapi.helpers as hh

DOMAIN = "hekr"

PROTOCOL_DEFINITIONS = hh.load_protocol_definitions()

CONF_DEVICE_ID = CONF_DEVICE_ID
CONF_CONTROL_KEY = "control_key"
CONF_HOST = CONF_HOST
CONF_PROTOCOL = CONF_PROTOCOL
CONF_SCAN_INTERVAL = CONF_SCAN_INTERVAL
CONF_APPLICATION_ID = "application_id"

DEVICE_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_CONTROL_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=10000): cv.port,
    vol.Required(CONF_PROTOCOL): vol.All(cv.string, vol.In(list(PROTOCOL_DEFINITIONS.keys()))),
    vol.Optional(CONF_SCAN_INTERVAL, default=15): cv.time_period,
    vol.Optional(CONF_APPLICATION_ID, default="test"): cv.string,
})

SUPPORTED_SENSOR_PROTOCOLS = {
    "power_meter": {
        "split_sensors": {
            "meter": {"name": "Power Meter", "icon":"mdi:counter", "attributes": ["total_energy_consumed", "phase_count", "switch_state", "warning_battery", "delay_enabled", "delay_timer"]},
            "voltage": {"name": "Voltage", "icon":"mdi:alpha-v-circle", "attributes": ["mean_voltage", "max_voltage", "min_voltage", "current_frequency", "warning_voltage"]},
            "current": {"name": "Current", "icon":"mdi:alpha-i-circle", "attributes": ["total_current", "current_1", "current_2", "current_3", "max_current", "current_frequency", "warning_current"]},
            "power_factor": {"name": "Power Factor", "icon":"mdi:speedometer", "attributes": ["total_power_factor", "power_factor_1", "power_factor_2", "power_factor_3"]},
            "active_power": {"name": "Active Power", "icon":"mdi:flash", "attributes": ["total_active_power", "active_power_1", "active_power_2", "active_power_3"]},
            "reactive_power": {"name": "Reactive Power", "icon":"mdi:flash-outline", "attributes": ["total_reactive_power", "reactive_power_1", "reactive_power_2", "reactive_power_3"]}
        },
        "update_commands": ["queryData"], # Should be: queryDev, queryData; but timeouts are an ass
        "primary_attribute": {
            "name": "total_energy_consumed",
            "unit_measurement": ENERGY_KILO_WATT_HOUR,
        }
    }
}