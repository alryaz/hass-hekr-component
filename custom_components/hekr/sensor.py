"""Support for Hekr sensors."""
from datetime import timedelta
import logging

from time import sleep

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.const import CONF_DEVICES, CONF_DEVICE_ID, STATE_UNKNOWN, ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON, ATTR_NAME
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import Throttle

from .hekrapi.device import Device as HekrDevice
from .hekrapi.protocol import load_protocol_definition
from .hekrapi.helpers import string_humanize

from .shared import (DOMAIN,
    CONF_DEVICE_ID, CONF_PROTOCOL, CONF_CONTROL_KEY, CONF_APPLICATION_ID, CONF_HOST, CONF_PORT, CONF_NAME,
    SUPPORTED_SENSOR_PROTOCOLS, DEVICE_CONFIG_FIELDS, MONITORED_CONDITIONS_ALL, DEFAULT_SENSOR_ICON, DEFAULT_QUERY_COMMAND,
    ATTR_MONITORED_ATTRIBUTES, ATTR_SENSOR_GROUPS, ATTR_STATE_ATTRIBUTE, ATTR_UPDATE_COMMANDS, ATTR_FUNC_FILTER_ATTRIBUTES)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(DEVICE_CONFIG_FIELDS)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

async def async_setup_platform(hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up platform."""

    protocol_name = config.get(CONF_PROTOCOL)
    device_id = config.get(CONF_DEVICE_ID)

    if protocol_name in SUPPORTED_SENSOR_PROTOCOLS:
        try:
            hekr_device = HekrDevice(
                device_id = device_id,
                control_key = config.get(CONF_CONTROL_KEY),
                application_id = config.get(CONF_APPLICATION_ID),
                address = config.get(CONF_HOST),
                port = config.get(CONF_PORT),
                device_protocol = load_protocol_definition(protocol_name)
            )

            hekr_device.authenticate()

            name = config.get(CONF_NAME)

            data = HekrData(
                hekr_device = hekr_device,
                update_commands = SUPPORTED_SENSOR_PROTOCOLS[protocol_name].get(ATTR_UPDATE_COMMANDS),
                attribute_filter = SUPPORTED_SENSOR_PROTOCOLS[protocol_name].get(ATTR_FUNC_FILTER_ATTRIBUTES)
            )

            await data.async_update()
        except Exception as e:
            _LOGGER.error('Failed to initialize platform [%s]: %s', DOMAIN, str(e))
            raise PlatformNotReady

        if not data.device_data:
            raise PlatformNotReady

        monitored_conditions = SUPPORTED_SENSOR_PROTOCOLS[protocol_name].get(ATTR_SENSOR_GROUPS, None)
        if monitored_conditions:
            _LOGGER.debug('Using additional monitored conditions')
            sensors = [
                HekrSensor(data = data, name = name, monitor_group_name = monitor_group_name)
                for monitor_group_name in monitored_conditions.keys()
            ]
        else:
            _LOGGER.debug('Using wildcard monitored conditions')
            sensors = [HekrSensor(data = data, name = name, monitor_group_name = MONITORED_CONDITIONS_ALL)]

        async_add_entities(sensors)
        return True

    _LOGGER.error('Protocol "%s" not supported for entity ID "%s"', protocol_name, device_id)
    return False

class HekrData:
    def __init__(self, hekr_device: HekrDevice, update_commands: list = [DEFAULT_QUERY_COMMAND], attribute_filter = None):
        self.hekr_device = hekr_device
        self.update_commands = update_commands
        self.device_data = {}
        self.available = True
        self.attribute_filter = attribute_filter

    async def async_update_device_state(self):
        new_data = {}
        for command in self.update_commands:
            result = self.hekr_device.command(command)
            _LOGGER.debug('Update for %s complete: %s', command, str(result))
            new_data.update(result)
        
        if callable(self.attribute_filter):
            new_data = self.attribute_filter(new_data)
        
        self.device_data = new_data
        return True
    
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, reload_socket = False):
        try:
            self.hekr_device.heartbeat()
            await self.async_update_device_state()
        except Exception as e:
            _LOGGER.error('Failed to update ID "%s": %s', self.hekr_device.device_id, str(e))
            _LOGGER.error('Attempting to fix this little mishap')
            try:
                self.hekr_device.authenticate()
                await self.async_update_device_state()
            except Exception as e:
                _LOGGER.error('Reauthentication failed, attempting to reload socket')
                try:
                    self.hekr_device.local_socket = None
                    self.hekr_device.authenticate()
                    await self.async_update_device_state()
                except Exception as e:
                    _LOGGER.error('Unable to update device, disabling for good')
                    self.available = False
                    return False

            _LOGGER.info('Restored connection to device')
            return True

class HekrSensor(Entity):
    def __init__(self, data:HekrData, name:str = None, monitor_group_name:str=MONITORED_CONDITIONS_ALL):
        self.data = data
        self.monitor_group_name = monitor_group_name

        self._name = name
        self._device_state_attributes = {}

    def is_default_sensor(self):
        return self.monitor_group_name == MONITORED_CONDITIONS_ALL or not self.monitor_group_name
    
    async def async_update(self):
        await self.data.async_update()
        _LOGGER.debug('device state attributes for "%s": %s', self.name, self.device_state_attributes)

    @property
    def available(self):
        return self.data.available

    @property
    def monitor_group(self):
        return self.support_definition.get(ATTR_SENSOR_GROUPS, {}).get(self.monitor_group_name, {})

    @property
    def support_definition(self):
        return SUPPORTED_SENSOR_PROTOCOLS[self.data.hekr_device.device_protocol.name]

    @property
    def unique_id(self):
        """Get unique ID."""
        return "{}-{}".format(self.data.hekr_device.device_id, self.monitor_group_name)

    @property
    def icon(self):
        return (DEFAULT_SENSOR_ICON if self.is_default_sensor()
            else self.monitor_group.get(ATTR_ICON, DEFAULT_SENSOR_ICON))

    @property
    def name(self):
        """Return the display name of this entity."""
        base_name = self._name if self._name else self.data.hekr_device.name
        if self.is_default_sensor():
            return base_name
        else:
            return "{} - {}".format(base_name, self.monitor_group.get(ATTR_NAME, string_humanize(self.monitor_group_name)))
    
    @property
    def state(self):
        return self.data.device_data.get(
            self.support_definition.get(ATTR_STATE_ATTRIBUTE, "")
            if self.monitor_group_name == MONITORED_CONDITIONS_ALL
            else self.monitor_group.get(ATTR_STATE_ATTRIBUTE, ""),
            STATE_UNKNOWN
        )

    @property
    def unit_of_measurement(self):
        return (self.support_definition.get(ATTR_UNIT_OF_MEASUREMENT, None)
            if self.monitor_group_name == MONITORED_CONDITIONS_ALL
            else self.monitor_group.get(ATTR_UNIT_OF_MEASUREMENT, None))

    @property
    def device_state_attributes(self):
        self._device_state_attributes = {
            attribute: value for attribute, value in self.data.device_data.items()
            if self.is_default_sensor()
                #and attribute != self.support_definition.get(ATTR_STATE_ATTRIBUTE, None)
            or attribute in self.monitor_group.get(ATTR_MONITORED_ATTRIBUTES, [])
        }
        self._device_state_attributes.update({
            ATTR_UNIT_OF_MEASUREMENT: self.unit_of_measurement,
        })
        return self._device_state_attributes

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (DOMAIN, self.data.hekr_device.device_id, self.monitor_group_name)
            },
            "name": self.name,
            "manufacturer": "Hekr",
            "model": self.data.hekr_device.device_protocol.display_name,
            "sw_version": "unknown",
        }
