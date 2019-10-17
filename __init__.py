""" Basic Hekr protocol implementation based on Wisen app. """

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, \
    CONF_PASSWORD, CONF_DEVICES

from homeassistant.components.sensor import PLATFORM_SCHEMA

import hekrapi

import shared as sh

REQUIREMENTS = ['python-hekr']

_LOGGER = logging.getLogger(__name__)

DOMAIN = sh.DOMAIN

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list, [sh.DEVICE_CONFIG_SCHEMA])
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the NHC2 CoCo component."""
    conf = config.get(DOMAIN)

    if conf is None:
        return True

    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    devices = conf.get(CONF_DEVICES)

    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
        data={CONF_USERNAME: username,
              CONF_PASSWORD: password,
              CONF_DEVICES: devices}
    ))

    return True


async def async_setup_entry(hass, entry):
    """Create a NHC2 gateway."""

    # @TODO: create a real entry that supports username/password
    if not entry.data[CONF_DEVICES]:
        return True

    dev_reg = await hass.helpers.device_registry.async_get_registry()

    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, "default")
        },
        manufacturer = "Hekr",
        name = "Hekr Cloud Gateway",
        model = "Web application interface",
        sw_version = "unknown"
    )
    
    for entry in entry.data[CONF_DEVICES]:

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry,
                'sensor'
            )
        )

    return True