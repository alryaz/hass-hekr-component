from collections import OrderedDict

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_NAME, CONF_SWITCHES, CONF_SCAN_INTERVAL, CONF_DEVICE_ID, CONF_PROTOCOL, \
    CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_SENSORS

from .const import CONF_CONTROL_KEY, CONF_APPLICATION_ID, DEFAULT_APPLICATION_ID, CONF_CLOUD_HOST, DEFAULT_CLOUD_HOST, \
    CONF_CLOUD_PORT, DEFAULT_CLOUD_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN, CONF_DEVICES, CONF_USE_MODEL_FROM_PROTOCOL, \
    DEFAULT_USE_MODEL_FROM_PROTOCOL, CONF_DOMAINS, PROTOCOL_DEFAULT, PROTOCOL_NAME
from .supported_protocols import SUPPORTED_PROTOCOLS


def exclusive_auth_methods(schema: dict):
    host = schema.get(CONF_HOST)
    token = schema.get(CONF_TOKEN)
    if host is None:
        if token is None:
            raise vol.Invalid('Neither method of authentication (local nor cloud) is provided.')
        return schema
    elif token is not None:
        raise vol.Invalid('Both methods of authentication are provided, while only one at once is supported (for now).')
    return schema


def test_for_list_correspondence(config_key: str, protocol_key: str):
    def validator(values):
        param_val = values.get(config_key)
        if param_val is None or isinstance(param_val, bool):
            return values
        avail_val = set(SUPPORTED_PROTOCOLS[values.get(CONF_PROTOCOL)][protocol_key].keys())
        invalid_val = set(param_val) - avail_val
        if invalid_val:
            return vol.Invalid(
                message=config_key.capitalize() + ' types (%s) are invalid',
                path=[config_key]
            )
        return values

    return validator

BASE_DEVICE_SCHEMA = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SENSORS): vol.Any(bool, vol.All(cv.ensure_list, [cv.string])),
    vol.Optional(CONF_SWITCHES): vol.Any(bool, vol.All(cv.ensure_list, [cv.string])),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
}

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

    # Cloud authentication
    vol.Optional(CONF_TOKEN): cv.string,
    vol.Optional(CONF_CLOUD_HOST, default=DEFAULT_CLOUD_HOST): cv.string,
    vol.Optional(CONF_CLOUD_PORT, default=DEFAULT_CLOUD_PORT): cv.positive_int,
}

DEVICE_SCHEMA = vol.All(BASE_PLATFORM_SCHEMA, exclusive_auth_methods, *BASE_VALIDATOR_DOMAINS)

USER_INPUT_DEVICE = OrderedDict()
USER_INPUT_DEVICE[vol.Required(CONF_NAME)] = str
USER_INPUT_DEVICE[vol.Required(CONF_DEVICE_ID)] = str
USER_INPUT_DEVICE[vol.Required(CONF_CONTROL_KEY)] = str
USER_INPUT_DEVICE[vol.Required(CONF_HOST)] = str
USER_INPUT_DEVICE[vol.Required(CONF_PROTOCOL)] = vol.In({
    p_id: p_def.get(PROTOCOL_NAME, p_id)
    for p_id, p_def in SUPPORTED_PROTOCOLS.items()
})
USER_INPUT_DEVICE[vol.Optional(CONF_PORT)] = str
USER_INPUT_DEVICE[vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL.seconds)] = int

USER_INPUT_DEVICE_SCHEMA = vol.Schema(USER_INPUT_DEVICE)

USER_INPUT_ADDITIONAL = lambda protocol_id, protocol_key: {
    vol.Optional(protocol_id + '_' + ent_type, default=ent_config.get(PROTOCOL_DEFAULT)): bool
    for ent_type, ent_config in SUPPORTED_PROTOCOLS[protocol_id][protocol_key].items()
}
USER_INPUT_ADDITIONAL_SCHEMA = lambda *args, **kwargs: vol.Schema(USER_INPUT_ADDITIONAL(*args, **kwargs))

# ACCOUNT_SCHEMA = {
#     vol.Optional(CONF_NAME, default=DEFAULT_NAME_ACCOUNT): cv.string,
#     vol.Required(CONF_TOKEN): cv.string,
#     vol.Optional(CONF_APPLICATION_ID, default=DEFAULT_APPLICATION_ID): cv.string,
#     vol.Optional(CONF_CUSTOMIZE): vol.Any(False, {cv.string: BASE_DEVICE_SCHEMA})
# }

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        vol.Optional(CONF_USE_MODEL_FROM_PROTOCOL, default=DEFAULT_USE_MODEL_FROM_PROTOCOL): cv.boolean,
        vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
        # vol.Optional(CONF_ACCOUNTS): vol.All(cv.ensure_list, [ACCOUNT_SCHEMA])
    }
}, extra=vol.ALLOW_EXTRA)
