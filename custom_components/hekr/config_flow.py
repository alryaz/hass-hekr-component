"""Config flow for Hekr."""
import logging
from datetime import timedelta
from typing import Optional, Dict, Tuple

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL, CONF_DEVICE_ID, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.helpers import ConfigType

from .const import DOMAIN, PROTOCOL_NAME, CONF_DEVICE, CONF_ACCOUNT, DEFAULT_NAME_DEVICE, PROTOCOL_PORT, CONF_DOMAINS
from .schemas import USER_INPUT_DEVICE_SCHEMA, USER_INPUT_ADDITIONAL_SCHEMA
from .supported_protocols import SUPPORTED_PROTOCOLS

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class HekrFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for Hekr config entries."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    prefix_dynamic_config = "additional_"

    def __init__(self):
        """Instantiate config flow."""
        self._current_type = None
        self._current_config = None

    @property
    def flow_is_import(self):
        return self.context['source'] == config_entries.SOURCE_IMPORT

    def __getattr__(self, item: str):
        if item.startswith('async_step_' + self.prefix_dynamic_config):
            config_key = item[22:]
            if config_key in CONF_DOMAINS:
                return lambda *args, **kwargs: self._additional_config_step(config_key, *args, **kwargs)

        raise AttributeError("Could not find attribute with name %s" % item)

    async def _additional_config_step(self, config_key: str, user_input=None):
        entity_domain, protocol_key = CONF_DOMAINS[config_key]

        protocol_id, protocol = self._current_protocol
        if protocol_id is None:
            _LOGGER.warning('Flow error due to protocol')
            return self.async_abort(reason="protocol_not_set")

        if self.context.get('source') == config_entries.SOURCE_IMPORT:
            self._current_config[config_key] = None
        else:
            if user_input is None:
                return self.async_show_form(step_id=self.prefix_dynamic_config + config_key,
                                            data_schema=USER_INPUT_ADDITIONAL_SCHEMA(protocol_id, protocol_key),
                                            description_placeholders={
                                                "entity_domain": entity_domain,
                                                "name": self._current_config[CONF_NAME],
                                                "protocol_name": protocol.get(PROTOCOL_NAME, protocol_id)
                                            })

            prefix_len = len(protocol_id) + 1
            selected_sensors = [option[prefix_len:] for option in user_input if user_input[option] is True]
            self._current_config[config_key] = selected_sensors or False

        return await self._get_next_additional_step()

    async def _get_next_additional_step(self):
        protocol_id, protocol = self._current_protocol
        for conf_key, (entity_domain, protocol_key) in CONF_DOMAINS.items():
            if protocol_key not in protocol:
                continue

            if conf_key not in self._current_config:
                step_attr = 'async_step_' + self.prefix_dynamic_config + conf_key
                _LOGGER.debug('next additional step: %s' % step_attr)
                _LOGGER.debug('current_config: %s' % self._current_config)
                return await getattr(self, step_attr)()

        return await self._create_entry(self._current_config)

    @property
    def _current_protocol(self) -> Tuple[Optional[str], Optional[Dict]]:
        if self._current_config is not None:
            protocol_id = self._current_config[CONF_PROTOCOL]
            return protocol_id, SUPPORTED_PROTOCOLS[protocol_id]
        return None, None

    # Initial step for user interaction
    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if user_input is None:
            # @TODO: this is a placeholder for future account integration
            _LOGGER.debug('Initialized user step')
        _LOGGER.debug('Transition: user step -> local step')
        return await self.async_step_device()

    # Device setup
    async def async_step_device(self, user_input=None):
        self._current_type = CONF_DEVICE

        if user_input is None:
            return self.async_show_form(step_id="device", data_schema=USER_INPUT_DEVICE_SCHEMA)

        if await self._check_device_exists(user_input[CONF_DEVICE_ID]):
            _LOGGER.info('Device with config %s already exists, not adding' % user_input)
            return self.async_abort(reason="device_already_exists")

        protocol_id = user_input[CONF_PROTOCOL]
        if protocol_id not in SUPPORTED_PROTOCOLS:
            _LOGGER.warning('Unsupported protocol "%s" provided during config for device "%s".'
                            % (user_input[CONF_DEVICE_ID], protocol_id))
            return self.async_show_form(step_id="device", data_schema=USER_INPUT_DEVICE_SCHEMA, errors={
                "base": "unsupported_protocol"
            })
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        if not user_input.get(CONF_PORT) and protocol.get(PROTOCOL_PORT) is None:
            _LOGGER.warning('No port provided for device %s; protocol %s does not define default port.'
                            % (user_input[CONF_DEVICE_ID], protocol_id))
            return self.async_show_form(step_id="device", data_schema=USER_INPUT_DEVICE_SCHEMA, errors={
                "base": "protocol_no_port"
            })

        if not user_input.get(CONF_NAME):
            user_input[CONF_NAME] = DEFAULT_NAME_DEVICE.format(
                host=user_input[CONF_HOST],
                device_id=user_input[CONF_DEVICE_ID],
                protocol_name=protocol.get(PROTOCOL_NAME, protocol_id)
            )

        scan_interval = user_input.get(CONF_SCAN_INTERVAL)
        if scan_interval is not None and isinstance(scan_interval, timedelta):
            user_input[CONF_SCAN_INTERVAL] = scan_interval.seconds

        self._current_config = user_input

        return await self._get_next_additional_step()

    # Finalize entry creation
    async def _create_entry(self, config: ConfigType):
        config[CONF_NAME] = config.get(CONF_NAME, config.get(CONF_DEVICE_ID))
        _LOGGER.debug('Creating entry: %s' % config)

        save_config = {**config}

        if self._current_type == CONF_DEVICE:
            if await self._check_device_exists(save_config[CONF_DEVICE_ID]):
                _LOGGER.info('Device with config %s already exists, not adding' % save_config)
                return self.async_abort(reason="device_already_exists")

            _LOGGER.debug('Device entry: %s' % save_config)

            return self.async_create_entry(
                title='Hekr: ' + save_config[CONF_NAME],
                data={CONF_DEVICE: save_config},
            )

        return self.async_abort(reason="unknown_config_type")

    async def _check_device_exists(self, device_id: str):
        current_entries = self._async_current_entries()
        for config_entry in current_entries:
            device_cfg = config_entry.data.get(CONF_DEVICE)
            if device_cfg is not None and device_cfg.get(CONF_DEVICE_ID) == device_id:
                return True

        return False

    async def async_step_import(self, user_input: Optional[ConfigType] = None):
        """Handle flow start from existing config section."""
        if user_input is None:
            return

        config_type = CONF_DEVICE if CONF_DEVICE in user_input else CONF_ACCOUNT
        item_config = user_input[config_type]
        _LOGGER.debug('Initiating config flow for import: %s' % item_config)
        return await (self.async_step_device(item_config) if config_type == CONF_DEVICE
                      else self.async_step_account(item_config))
