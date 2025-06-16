"""Config flow for Hekr."""

import logging
from typing import Optional, Dict, Tuple, Any

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    PROTOCOL_NAME,
    CONF_DEVICE,
    CONF_ACCOUNT,
    DEFAULT_NAME_DEVICE,
    PROTOCOL_PORT,
    CONF_DOMAINS,
    CONF_CONTROL_KEY,
    DEFAULT_SCAN_INTERVAL,
    PROTOCOL_DEFAULT,
    CONF_DUMP_DEVICE_CREDENTIALS,
    PROTOCOL_DEFINITION,
)
from .supported_protocols import SUPPORTED_PROTOCOLS

_LOGGER = logging.getLogger(__name__)

ConfigFlowCommandType = Dict[str, Any]


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
        schema_device[vol.Optional(CONF_NAME)] = str
        schema_device[vol.Required(CONF_DEVICE_ID)] = str
        schema_device[vol.Required(CONF_CONTROL_KEY)] = str
        schema_device[vol.Required(CONF_HOST)] = str
        schema_device[vol.Required(CONF_PROTOCOL)] = vol.In(
            {
                p_id: p_def.get(PROTOCOL_NAME, p_id)
                for p_id, p_def in SUPPORTED_PROTOCOLS.items()
            }
        )
        schema_device[vol.Optional(CONF_PORT)] = str
        schema_device[
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL.seconds)
        ] = int
        self.schema_device = vol.Schema(schema_device)

        self.schema_additional = lambda protocol_id, protocol_key: vol.Schema(
            {
                vol.Optional(
                    protocol_id + "_" + ent_type,
                    default=ent_config.get(PROTOCOL_DEFAULT),
                ): bool
                for ent_type, ent_config in SUPPORTED_PROTOCOLS[protocol_id][
                    protocol_key
                ].items()
            }
        )

        schema_account = OrderedDict()
        schema_account[vol.Required(CONF_USERNAME)] = str
        schema_account[vol.Required(CONF_PASSWORD)] = str
        schema_account[vol.Optional(CONF_DUMP_DEVICE_CREDENTIALS, default=False)] = bool
        self.schema_account = vol.Schema(schema_account)

    def __getattr__(self, item: str) -> Any:
        """
        Process dynamic configuration steps.
        When an `async_step_<dynamic_prefix>*` attribute is accessed, return a lambda to perform the
        necessary configuration step.
        :param item: Attribute
        :return:
        """
        if item.startswith("async_step_" + self.prefix_dynamic_config):
            config_key = item[22:]
            if config_key in CONF_DOMAINS:
                return lambda *args, **kwargs: self._additional_config_step(
                    config_key, *args, **kwargs
                )

        raise AttributeError("Could not find attribute with name %s" % item)

    async def _additional_config_step(
        self, config_key: str, user_input=None
    ) -> ConfigFlowCommandType:
        """
        Process additional config step.
        :param config_key: Configuration key (set from __getattr__)
        :param user_input: Input from Home Assistant form
        :return: Config flow command
        """
        entity_domain, protocol_key = CONF_DOMAINS[config_key]

        protocol_id, protocol = self._current_protocol
        if protocol_id is None:
            _LOGGER.warning("Flow error due to protocol")
            return self.async_abort(reason="protocol_not_set")

        if user_input is None:
            _LOGGER.debug("Showing form for %s" % entity_domain)
            return self.async_show_form(
                step_id=self.prefix_dynamic_config + config_key,
                data_schema=self.schema_additional(protocol_id, protocol_key),
                description_placeholders={
                    "entity_domain": entity_domain,
                    "device_name": self._current_config[CONF_NAME],
                    "protocol_name": protocol.get(PROTOCOL_NAME) or protocol_id,
                },
            )

        # Retrieve list of selected items for platform
        prefix_len = len(protocol_id) + 1
        selected_items = [
            option[prefix_len:] for option in user_input if user_input[option] is True
        ]

        # Save selected platform items to current configuration
        self._current_config[config_key] = selected_items or False

        return await self._get_next_additional_step()

    async def _get_next_additional_step(self) -> Dict[str, Any]:
        """
        Retrieve next additional step for given configuration.
        :return: Config flow command
        """
        protocol_id, protocol = self._current_protocol
        for conf_key, (entity_domain, protocol_key) in CONF_DOMAINS.items():
            if protocol_key not in protocol:
                continue

            if conf_key not in self._current_config:
                step_attr = "async_step_" + self.prefix_dynamic_config + conf_key
                return await getattr(self, step_attr)()

        return await self._create_entry(self._current_config, setup_type=CONF_DEVICE)

    async def _create_entry(
        self, config: ConfigType, setup_type: str, from_import: bool = False
    ):
        _LOGGER.debug("Creating entry: %s" % config)

        save_config = {**config}

        if setup_type == CONF_DEVICE:
            if await self._check_entry_exists(config[CONF_DEVICE_ID], CONF_DEVICE):
                _LOGGER.info(
                    "Device with config %s already exists, not adding" % save_config
                )
                return self.async_abort(reason="device_already_exists")

            config_name = config.get(CONF_NAME, config.get(CONF_DEVICE_ID))
            if from_import:
                save_config = {CONF_DEVICE_ID: config[CONF_DEVICE_ID]}
            else:
                save_config[CONF_NAME] = config_name

            _LOGGER.debug("Device entry: %s" % save_config)

            return self.async_create_entry(
                title=config_name,
                data={CONF_DEVICE: save_config},
            )

        elif setup_type == CONF_ACCOUNT:
            if await self._check_entry_exists(config[CONF_USERNAME], CONF_ACCOUNT):
                _LOGGER.info(
                    "Account with config %s already exists, not adding" % save_config
                )
                return self.async_abort(reason="account_already_exists")

            _LOGGER.debug("Account entry: %s" % save_config)

            if from_import:
                save_config = {CONF_USERNAME: config[CONF_USERNAME]}

            return self.async_create_entry(
                title=save_config[CONF_USERNAME],
                data={CONF_ACCOUNT: save_config},
            )

        _LOGGER.error("Unknown config type in configuration: %s" % config)
        return self.async_abort(reason="unknown_config_type")

    async def _check_entry_exists(self, item_id: str, setup_type: str):
        item_id_key = CONF_DEVICE_ID if setup_type == CONF_DEVICE else CONF_USERNAME
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            cfg = config_entry.data.get(setup_type)
            if cfg is not None and cfg.get(item_id_key) == item_id:
                return True

        return False

    @property
    def _current_protocol(self) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Return current protocol ID and its internal component definition.
        :return: Tuple[Protocol ID, Internal definition]
        """
        if self._current_config is not None:
            protocol_id = self._current_config[CONF_PROTOCOL]
            return protocol_id, SUPPORTED_PROTOCOLS[protocol_id]
        return None, None

    async def async_step_user(self, user_input=None):
        """
        Step 1. Show scenario selection
        :param user_input: (optional) User input from Home Assistant form
        :return: Config flow command
        """
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.schema_user)

        if user_input[CONF_TYPE] == CONF_ACCOUNT:
            return await self.async_step_account()

        return await self.async_step_device()

    async def async_step_device(self, user_input=None) -> Dict[str, Any]:
        """
        Step 2. Device configuration scenario
        :param user_input: (optional) User input from Home Assistant form
        :return: Config flow command
        """

        # Show form on no input
        if user_input is None:
            return self.async_show_form(
                step_id="device", data_schema=self.schema_device
            )

        device_id = user_input[CONF_DEVICE_ID]

        # Check if entry with given device ID already exists
        if await self._check_entry_exists(device_id, CONF_DEVICE):
            _LOGGER.info(
                "Device with config %s already exists, not adding" % user_input
            )
            return self.async_abort(reason="device_already_exists")

        # Check whether specified protocol is under the supported list
        protocol_id = user_input[CONF_PROTOCOL]
        if protocol_id not in SUPPORTED_PROTOCOLS:
            _LOGGER.warning(
                'Unsupported protocol "%s" provided during config for device "%s".'
                % (user_input[CONF_DEVICE_ID], protocol_id)
            )
            return self.async_show_form(
                step_id="device",
                data_schema=self.schema_device,
                errors={CONF_PROTOCOL: "protocol_unsupported"},
            )

        # Retrieve necessary protocol information
        protocol = SUPPORTED_PROTOCOLS[protocol_id]
        protocol_name = protocol.get(PROTOCOL_NAME, protocol_id)

        # Check whether user didn't provide a port, and query the protocol for one instead
        if not user_input.get(CONF_PORT) and protocol.get(PROTOCOL_PORT) is None:
            _LOGGER.warning(
                "No port provided for device %s; protocol %s does not define default port."
                % (user_input[CONF_DEVICE_ID], protocol_id)
            )
            return self.async_show_form(
                step_id="device",
                data_schema=self.schema_device,
                errors={CONF_PORT: "protocol_no_port"},
            )

        # Generate default name for device if none provided
        if not user_input.get(CONF_NAME):
            user_input[CONF_NAME] = DEFAULT_NAME_DEVICE.format(
                host=user_input[CONF_HOST],
                device_id=device_id,
                protocol_name=protocol_name,
            )

        # Save current config state
        self._current_config = user_input

        return await self._get_next_additional_step()

    async def async_step_account(self, user_input=None):
        """
        Step 2. Account setup scenario
        :param self:
        :param user_input:
        :return:
        """
        if user_input is None:
            return self.async_show_form(
                step_id="account", data_schema=self.schema_account
            )

        if await self._check_entry_exists(user_input[CONF_USERNAME], CONF_ACCOUNT):
            _LOGGER.info(
                'Account with username "%s" already exists, not adding.'
                % user_input[CONF_USERNAME]
            )
            return self.async_abort(reason="account_already_exists")

        from hekrapi.exceptions import HekrAPIException, AuthenticationFailedException
        from hekrapi.account import Account

        username = user_input[CONF_USERNAME]

        try:
            account = Account(username=username, password=user_input[CONF_PASSWORD])

            await account.authenticate()
            devices_info = await account.get_devices()

        except AuthenticationFailedException:
            return self.async_show_form(
                step_id="account",
                data_schema=self.schema_account,
                errors={
                    "base": "account_invalid_credentials",
                },
            )

        except HekrAPIException as e:
            return self.async_abort(
                reason="unknown_error",
                description_placeholders={
                    "class": e.__class__.__name__,
                    "content": str(e),
                },
            )

        if user_input[CONF_DUMP_DEVICE_CREDENTIALS]:
            # Clean user_input to prevent credentials dumping directive from saving to config
            _LOGGER.debug("Selected account credentials dump")
            del user_input[CONF_DUMP_DEVICE_CREDENTIALS]

            # Get all supported protocols
            supported_protocols = {
                protocol_id: protocol[PROTOCOL_DEFINITION]
                for protocol_id, protocol in SUPPORTED_PROTOCOLS.items()
            }

            # Create list for matching
            supported_protocols_vals = list(supported_protocols.values())

            # Update devices from account (match them with supported protocols)
            await account.update_devices(
                devices_info, protocols=supported_protocols_vals
            )

            if account.devices:
                # Create list for looking up protocol ID's
                supported_protocols_keys = list(supported_protocols.keys())

                # Generate placeholder for every device
                placeholder_text = "hekr:\n  devices:\n" + "\n\n".join(
                    [
                        f"  - {CONF_DEVICE_ID}: {d.device_id}\n"
                        f"    {CONF_NAME}: {d.device_name}\n"
                        f"    {CONF_CONTROL_KEY}: {d.control_key}\n"
                        f"    {CONF_HOST}: {d.lan_address}\n"
                        f"    {CONF_PROTOCOL}: {supported_protocols_keys[supported_protocols_vals.index(d.protocol)]}\n"
                        f"    # device is {'online' if d.is_online else 'offline'}\n"
                        for device_id, d in account.devices.items()
                        if d.protocol in supported_protocols_vals
                    ]
                )

                # Dump a log message with configuration
                _LOGGER.info(
                    f'Hekr Account with username "{username}" yielded {len(account.devices)} devices. '
                    f"The following configuration was prepared for you to insert into `configuration.yaml`:"
                    f"\n\n" + placeholder_text
                )

                # Prepare message with Markdown syntax
                notification_message = (
                    "Device configurations for YAML:\n```yaml\n"
                    + placeholder_text
                    + "```"
                )

            else:
                # Devices not found, notify user about it
                notification_message = (
                    "Devices for current account not found. Configuration is kept "
                    "for future use, however to retrieve device configuration "
                    "after adding a device to your account, you will have to"
                    "re-run account configuration again."
                )

            # Create notification for retrieved devices state
            from homeassistant.components import persistent_notification

            # @TODO: this is a deprecated service call
            await self.hass.services.async_call(
                persistent_notification.DOMAIN,
                persistent_notification.SERVICE_CREATE,
                {
                    persistent_notification.ATTR_TITLE: f"Hekr: Configurations ({username})",
                    persistent_notification.ATTR_NOTIFICATION_ID: f"hekr_device_config_{username}",
                    persistent_notification.ATTR_MESSAGE: notification_message,
                },
                blocking=True,
                limit=None,
            )

        # Account cleanup
        del account

        # Finalize with entry creation
        return await self._create_entry(user_input, CONF_ACCOUNT)

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> ConfigFlowCommandType:
        """
        Step IMPORT. Import configuration from YAML
        Save only setup type and identifier (`username` for accounts, `device_id` for devices).
        The rest of configuration is picked up at runtime from a `HekrData` object.
        :param user_input: Imported configuration
        :return: Config flow command
        """
        if user_input is None:
            _LOGGER.error("Called import step without configuration")
            return self.async_abort("empty_configuration_import")

        # Detect setup type based on available keys
        setup_type = CONF_DEVICE if CONF_DEVICE in user_input else CONF_ACCOUNT

        _LOGGER.debug("Importing config entry for %s" % setup_type)

        # Finalize with entry creation
        return await self._create_entry(
            user_input[setup_type], setup_type, from_import=True
        )
