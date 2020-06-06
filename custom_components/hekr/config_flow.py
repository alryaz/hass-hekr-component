"""Config flow for Hekr."""
import logging
from datetime import timedelta
from typing import Optional, Dict, Tuple

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL, CONF_DEVICE_ID, CONF_NAME, CONF_SCAN_INTERVAL, \
    CONF_TYPE, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import ConfigType

from .const import DOMAIN, PROTOCOL_NAME, CONF_DEVICE, CONF_ACCOUNT, DEFAULT_NAME_DEVICE, PROTOCOL_PORT, CONF_DOMAINS, \
    CONF_CONTROL_KEY, DEFAULT_SCAN_INTERVAL, PROTOCOL_DEFAULT, CONF_DUMP_DEVICE_CREDENTIALS, PROTOCOL_DEFINITION
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
        self._devices_info = None

        import voluptuous as vol
        from collections import OrderedDict

        schema_user = OrderedDict()
        schema_user[vol.Required(CONF_TYPE)] = vol.In([CONF_DEVICE, CONF_ACCOUNT])
        self.schema_user = vol.Schema(schema_user)

        schema_device = OrderedDict()
        schema_device[vol.Required(CONF_NAME)] = str
        schema_device[vol.Required(CONF_DEVICE_ID)] = str
        schema_device[vol.Required(CONF_CONTROL_KEY)] = str
        schema_device[vol.Required(CONF_HOST)] = str
        schema_device[vol.Required(CONF_PROTOCOL)] = vol.In({
            p_id: p_def.get(PROTOCOL_NAME, p_id)
            for p_id, p_def in SUPPORTED_PROTOCOLS.items()
        })
        schema_device[vol.Optional(CONF_PORT)] = str
        schema_device[vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL.seconds)] = int
        self.schema_device = vol.Schema(schema_device)

        self.schema_additional = lambda protocol_id, protocol_key: vol.Schema({
            vol.Optional(protocol_id + '_' + ent_type, default=ent_config.get(PROTOCOL_DEFAULT)): bool
            for ent_type, ent_config in SUPPORTED_PROTOCOLS[protocol_id][protocol_key].items()
        })

        schema_account = OrderedDict()
        schema_account[vol.Required(CONF_USERNAME)] = str
        schema_account[vol.Required(CONF_PASSWORD)] = str
        schema_account[vol.Optional(CONF_DUMP_DEVICE_CREDENTIALS, default=False)] = bool
        self.schema_account = vol.Schema(schema_account)

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
                                            data_schema=self.schema_additional(protocol_id, protocol_key),
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
                return await getattr(self, step_attr)()

        return await self._create_entry(self._current_config, setup_type=CONF_DEVICE)

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
            return self.async_show_form(step_id="user", data_schema=self.schema_user)
        
        if user_input[CONF_TYPE] == CONF_ACCOUNT:
            return await self.async_step_account()
        return await self.async_step_device()

    # Device setup
    async def async_step_device(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="device", data_schema=self.schema_device_SCHEMA)

        if await self._check_entry_exists(user_input[CONF_DEVICE_ID], CONF_DEVICE):
            _LOGGER.info('Device with config %s already exists, not adding' % user_input)
            return self.async_abort(reason="device_already_exists")

        protocol_id = user_input[CONF_PROTOCOL]
        if protocol_id not in SUPPORTED_PROTOCOLS:
            _LOGGER.warning('Unsupported protocol "%s" provided during config for device "%s".'
                            % (user_input[CONF_DEVICE_ID], protocol_id))
            return self.async_show_form(step_id="device", data_schema=self.schema_device, errors={
                "base": "unsupported_protocol"
            })
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        if not user_input.get(CONF_PORT) and protocol.get(PROTOCOL_PORT) is None:
            _LOGGER.warning('No port provided for device %s; protocol %s does not define default port.'
                            % (user_input[CONF_DEVICE_ID], protocol_id))
            return self.async_show_form(step_id="device", data_schema=self.schema_device, errors={
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

    # Account setup
    async def async_step_account(self, user_input=None):
        self._current_type = CONF_ACCOUNT

        if user_input is None:
            return self.async_show_form(step_id="account", data_schema=self.schema_account)

        if await self._check_entry_exists(user_input[CONF_USERNAME], CONF_ACCOUNT):
            _LOGGER.info('Account with username "%s" already exists, not adding.' % user_input[CONF_USERNAME])
            return self.async_abort(reason="account_already_exists")

        from hekrapi.exceptions import HekrAPIException
        from hekrapi.account import Account

        try:
            account = Account(username=user_input[CONF_USERNAME], password=user_input[CONF_PASSWORD])
            await account.authenticate()
            devices_info = await account.get_devices()
        except HekrAPIException:
            return self.async_abort(reason="account_invalid_credentials")

        if user_input[CONF_DUMP_DEVICE_CREDENTIALS]:
            _LOGGER.debug('Selected account credentials dump')
            del user_input[CONF_DUMP_DEVICE_CREDENTIALS]

            supported_protocols = {
                protocol_id: protocol[PROTOCOL_DEFINITION]
                for protocol_id, protocol in SUPPORTED_PROTOCOLS.items()
            }
            supported_protocols_vals = list(supported_protocols.values())
            supported_protocols_keys = list(supported_protocols.keys())

            await account.update_devices(
                devices_info,
                protocols=supported_protocols_vals
            )
            placeholder_text = 'hekr:\n  devices:\n' + '\n\n'.join([
                f"  - {CONF_DEVICE_ID}: {d.device_id}\n"
                f"    {CONF_NAME}: {d.device_name}\n"
                f"    {CONF_CONTROL_KEY}: {d.control_key}\n"
                f"    {CONF_HOST}: {d.lan_address}\n"
                f"    {CONF_PROTOCOL}: {supported_protocols_keys[supported_protocols_vals.index(d.protocol)]}\n"
                f"    # device is {'online' if d.is_online else 'offline'}\n"
                for device_id, d in self._checked_account.devices.items()
                if d.protocol in supported_protocols_vals
            ])

            self.hass.services.async_call('persistent_notification', 'create', {
                'title': 'Hekr: Configurations (%s)' % user_input[CONF_USERNAME],
                'message': 'Device configurations for YAML:\n```\n'+placeholder_text
            })

        del account

        return await self._create_entry(user_input, CONF_ACCOUNT)

    # Finalize entry creation
    async def _create_entry(self, config: ConfigType, setup_type: str, from_import: bool = False):
        _LOGGER.debug('Creating entry: %s' % config)

        save_config = {**config}

        if setup_type == CONF_DEVICE:
            if await self._check_entry_exists(config[CONF_DEVICE_ID], CONF_DEVICE):
                _LOGGER.info('Device with config %s already exists, not adding' % save_config)
                return self.async_abort(reason="device_already_exists")

            config_name = config.get(CONF_NAME, config.get(CONF_DEVICE_ID))
            if from_import:
                save_config = {CONF_DEVICE_ID: config[CONF_DEVICE_ID]}
            else:
                save_config[CONF_DEVICE][CONF_NAME] = config_name

            _LOGGER.debug('Device entry: %s' % save_config)

            return self.async_create_entry(
                title=config_name,
                data={CONF_DEVICE: save_config},
            )

        elif setup_type == CONF_ACCOUNT:
            if await self._check_entry_exists(config[CONF_USERNAME], CONF_ACCOUNT):
                _LOGGER.info('Account with config %s already exists, not adding' % save_config)
                return self.async_abort(reason="account_already_exists")

            _LOGGER.debug('Account entry: %s' % save_config)

            if from_import:
                save_config = {CONF_USERNAME: config[CONF_USERNAME]}

            return self.async_create_entry(
                title=save_config[CONF_USERNAME],
                data={CONF_ACCOUNT: save_config},
            )

        _LOGGER.error('Unknown config type in configuration: %s' % config)
        return self.async_abort(reason="unknown_config_type")

    async def _check_entry_exists(self, item_id: str, setup_type: str):
        item_id_key = CONF_DEVICE_ID if setup_type == CONF_DEVICE else CONF_ACCOUNT
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            cfg = config_entry.data.get(setup_type)
            if cfg is not None and cfg.get(item_id_key) == item_id:
                return True

        return False

    async def async_step_import(self, user_input: Optional[ConfigType] = None):
        """Handle flow start from existing config section."""
        if user_input is None:
            return False

        setup_type = CONF_DEVICE if CONF_DEVICE in user_input else CONF_ACCOUNT

        _LOGGER.debug('Importing config entry for %s' % setup_type)

        return await self._create_entry(user_input[setup_type], setup_type, from_import=True)
