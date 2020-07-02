"""Config flow for Hekr."""
import logging
from typing import Optional, Dict, Any

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_USERNAME
from homeassistant.helpers import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


ConfigFlowCommandType = Dict[str, Any]


@config_entries.HANDLERS.register(DOMAIN)
class HekrFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for Hekr config entries."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, user_input: Optional[ConfigType] = None) -> ConfigFlowCommandType:
        """
        Step IMPORT. Import configuration from YAML
        Save only setup type and identifier (`username` for accounts, `device_id` for devices).
        The rest of configuration is picked up at runtime from a `HekrData` object.
        :param user_input: Imported configuration
        :return: Config flow command
        """
        if user_input is None:
            _LOGGER.error('Called import step without configuration')
            return self.async_abort("empty_configuration_import")

        # Detect setup type based on available keys
        config_key = CONF_DEVICE_ID if CONF_DEVICE_ID in user_input else CONF_USERNAME

        _LOGGER.debug("Creating config entry: %s" % config_key)
        # Finalize with entry creation
        return self.async_create_entry(
            title='Hekr: %s' % (user_input[config_key], ),
            data={config_key: user_input[config_key]}
        )
