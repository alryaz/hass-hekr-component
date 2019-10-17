"""Support for Hekr sensors."""
import logging

from time import sleep
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.const import CONF_DEVICES, CONF_DEVICE_ID, STATE_UNKNOWN

from hekrapi.device import Device as HekrDevice

import shared as sh

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus binary sensor based on config_entry."""

    local_devices = hass.data[sh.DOMAIN][entry.entry_id][CONF_DEVICES]

    import hekrapi.helpers as hh

    # Local caching
    loaded_protocols = []

    entities = []
    for device_config in local_devices:
        device_id = device_config.get(sh.CONF_DEVICE_ID)
        protocol_name = device_config.get(sh.CONF_PROTOCOL)
        if protocol_name not in sh.SUPPORTED_SENSOR_PROTOCOLS:
            _LOGGER.error('Protocol "%s" not supported for entity ID "%s"', protocol_name, device_id)
            continue

        _LOGGER.debug('Setting up protocol "%s" with entity ID "%s', protocol_name, device_id)

        if protocol_name not in loaded_protocols:
            loaded_protocols[protocol_name] = hh.load_protocol_definition(protocol_name)
        
        _LOGGER.debug('Protocol "%s" loaded', protocol_name)
        
        entities.append(HekrSensor(entry_id=entry.entry_id, device=HekrDevice(
            device_id = device_config.get(sh.CONF_DEVICE_ID),
            control_key = device_config.get(sh.CONF_CONTROL_KEY),
            application_id = device_config.get(sh.CONF_APPLICATION_ID),
            address = device_config.get(sh.CONF_HOST),
            port = device_config.get(sh.CONF_PORT),
            device_protocol = loaded_protocols[protocol_name]
        )))

        _LOGGER('Hekr device object created for entity ID "%s"', device_id)
    
    if entities:
        async_add_entities(entities)
    
    return True

class HekrSensor(Entity):
    def __init__(self, device:HekrDevice, entry_id:str):
        self.hekr_device = device
        self.entry_id = entry_id

        self.support = sh.SUPPORTED_SENSOR_PROTOCOLS[self.hekr_device.device_protocol.name]
        
        self._device_state_attributes = {}

    async def async_update(self):
        update_commands = self.support.get('update_commands', ['queryDev'])

        new_data = {}
        for command in update_commands:
            new_data.update(self.hekr_device.command(command))
        
        self._device_state_attributes = new_data
        return True

    @property
    def unique_id(self):
        """Get unique ID."""
        return self.hekr_device.device_id

    @property
    def name(self):
        """Return the display name of this entity."""
        return self.hekr_device.name
    
    @property
    def state(self):
        return self.device_state_attributes.get(self.support.primary_attribute["name"], STATE_UNKNOWN)

    @property
    def unit_of_measurement(self):
        return self.support.primaray_attribute.get("unit_of_measurement", None)

    @property
    def device_state_attributes(self):
        attr = self._device_state_attributes.copy()
        attr.update(super().device_state_attributes)
        return attr

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (sh.DOMAIN, self.entry_id, self.hekr_device.device_id)
            },
            "name": self.hekr_device.name,
            "manufacturer": "Hekr",
            "model": self.hekr_device.device_protocol.name,
            "sw_version": "unknown",
        }