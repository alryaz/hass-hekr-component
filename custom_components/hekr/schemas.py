"""Dedicate schema generation."""

__all__ = [
    "BASE_DEVICE_SCHEMA",
    "BASE_PLATFORM_SCHEMA",
    "BASE_VALIDATOR_DOMAINS",
    "CONFIG_SCHEMA",
    "CUSTOMIZE_SCHEMA",
    "test_for_list_correspondence",
]

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (
    CONF_NAME,
    CONF_SWITCHES,
    CONF_SCAN_INTERVAL,
    CONF_DEVICE_ID,
    CONF_PROTOCOL,
    CONF_HOST,
    CONF_PORT,
    CONF_SENSORS,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_CUSTOMIZE,
    CONF_TIMEOUT,
)

from .const import (
    CONF_CONTROL_KEY,
    CONF_APPLICATION_ID,
    DEFAULT_APPLICATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CONF_DEVICES,
    CONF_USE_MODEL_FROM_PROTOCOL,
    DEFAULT_USE_MODEL_FROM_PROTOCOL,
    CONF_DOMAINS,
    CONF_ACCOUNTS,
    CONF_DUMP_DEVICE_CREDENTIALS,
    CONF_TOKEN_UPDATE_INTERVAL,
)
from .supported_protocols import SUPPORTED_PROTOCOLS


def test_for_list_correspondence(config_key: str, protocol_key: str):
    def validator(values):
        param_val = values.get(config_key)
        if param_val is None or isinstance(param_val, bool):
            return values
        avail_val = set(SUPPORTED_PROTOCOLS[values.get(CONF_PROTOCOL)][protocol_key].keys())
        invalid_val = set(param_val) - avail_val
        if invalid_val:
            return vol.Invalid(
                message=config_key.capitalize() + " types (%s) are invalid", path=[config_key]
            )
        return values

    return validator


BASE_DEVICE_SCHEMA = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SENSORS): vol.Any(bool, vol.All(cv.ensure_list, [cv.string])),
    vol.Optional(CONF_SWITCHES): vol.Any(bool, vol.All(cv.ensure_list, [cv.string])),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.time_period, cv.positive_timedelta
    ),
}

CUSTOMIZE_SCHEMA = vol.Any(
    False,
    vol.Schema(BASE_DEVICE_SCHEMA).extend(
        {vol.Optional(CONF_PROTOCOL): vol.In(SUPPORTED_PROTOCOLS.keys())}
    ),
)

BASE_VALIDATOR_DOMAINS = [
    test_for_list_correspondence(config_key, protocol_key)
    for config_key, (entity_domain, protocol_key) in CONF_DOMAINS.items()
]

BASE_PLATFORM_SCHEMA = {
    **BASE_DEVICE_SCHEMA,
    # Required keys on direct control
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Optional(CONF_CONTROL_KEY): cv.string,
    vol.Required(CONF_PROTOCOL): vol.In(SUPPORTED_PROTOCOLS.keys()),
    # Optional attributes
    vol.Optional(CONF_APPLICATION_ID, default=DEFAULT_APPLICATION_ID): cv.string,
    # Local authentication
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.positive_int,
    # Base timeout
    vol.Optional(CONF_TIMEOUT, default=5.0): vol.All(vol.Coerce(float), vol.Range(min=0)),
}

DEVICE_SCHEMA = vol.All(BASE_PLATFORM_SCHEMA, *BASE_VALIDATOR_DOMAINS)

ACCOUNT_SCHEMA = {
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_APPLICATION_ID, default=DEFAULT_APPLICATION_ID): cv.string,
    vol.Optional(CONF_DUMP_DEVICE_CREDENTIALS, default=False): cv.boolean,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.time_period, cv.positive_timedelta
    ),
    vol.Optional(CONF_TOKEN_UPDATE_INTERVAL): cv.time_period,
    vol.Optional(CONF_TIMEOUT, default=5.0): vol.All(vol.Coerce(float), vol.Range(min=0)),
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(
                CONF_USE_MODEL_FROM_PROTOCOL, default=DEFAULT_USE_MODEL_FROM_PROTOCOL
            ): cv.boolean,
            vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
            vol.Optional(CONF_ACCOUNTS): vol.All(cv.ensure_list, [ACCOUNT_SCHEMA]),
            vol.Optional(CONF_CUSTOMIZE): {cv.string: CUSTOMIZE_SCHEMA},
        }
    },
    extra=vol.ALLOW_EXTRA,
)
