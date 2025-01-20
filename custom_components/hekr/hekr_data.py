import asyncio
import logging
from datetime import timedelta
from functools import partial

try:
    from typing import TYPE_CHECKING, Dict, Union, List, Callable, Optional, Set, Tuple, NoReturn
except ImportError:
    from typing import TYPE_CHECKING, Dict, Union, List, Callable, Optional, Set, Tuple

    NoReturn = None

from hekrapi import (
    Device,
    DeviceID,
    DeviceResponseState,
    ACTION_COMMAND_RESPONSE,
    ACTION_DEVICE_MESSAGE,
    LocalConnector,
    HekrAPIException,
)
from hekrapi.account import Account
from homeassistant import config_entries
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    CONF_PROTOCOL,
    CONF_HOST,
    CONF_DEVICE_ID,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_CUSTOMIZE,
    CONF_TIMEOUT,
)
from homeassistant.helpers.event import async_track_time_interval, async_track_point_in_time
from homeassistant.helpers.typing import homeassistant.core.HomeAssistant, ConfigType
from homeassistant.util.dt import now

from custom_components.hekr.supported_protocols import SUPPORTED_PROTOCOLS
from custom_components.hekr.const import (
    DOMAIN,
    DEFAULT_USE_MODEL_FROM_PROTOCOL,
    PROTOCOL_FILTER,
    CONF_DOMAINS,
    CONF_APPLICATION_ID,
    DEFAULT_APPLICATION_ID,
    CONF_CONTROL_KEY,
    PROTOCOL_DEFINITION,
    PROTOCOL_PORT,
    CONF_ACCOUNT,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    PROTOCOL_MODEL,
    PROTOCOL_MANUFACTURER,
    PROTOCOL_NAME,
    CONF_DEVICE,
    CONF_TOKEN_UPDATE_INTERVAL,
    DEFAULT_NAME_DEVICE,
    DEFAULT_TIMEOUT,
)

if TYPE_CHECKING:
    # noinspection PyProtectedMember
    from hekrapi.device import _BaseConnector
    from hekrapi.command import Command
    from homeassistant.core import Event
    from homeassistant.helpers.device_registry import DeviceRegistry, DeviceEntry
    from custom_components.hekr.base_platform import HekrEntity

_LOGGER = logging.getLogger(__name__)

AnyDeviceIdentifier = Union[DeviceID, Device]
Username = str


class FrameNumber(object):
    pass


class HekrData:
    def __init__(self, hass: homeassistant.core.HomeAssistant):
        if isinstance(hass.data.get(DOMAIN), HekrData):
            raise Exception("One instance of HekrData is already installed")

        self.hass = hass

        self.devices: Dict[DeviceID, Device] = dict()
        self.devices_config_yaml: Dict[DeviceID, ConfigType] = dict()
        self.devices_config_entries: Dict[DeviceID, ConfigType] = dict()
        self.device_entities: Dict[DeviceID, List["HekrEntity"]] = dict()
        self.device_updaters: Dict[DeviceID, Tuple[Set[str], Callable]] = dict()

        self.accounts: Dict[Username, Account] = dict()
        self.accounts_config_yaml: Dict[Username, ConfigType] = dict()
        self.accounts_config_entries: Dict[Username, ConfigType] = dict()
        self.account_updaters: Dict[Username, Callable] = dict()

        self.use_model_from_protocol = DEFAULT_USE_MODEL_FROM_PROTOCOL

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.callback_homeassistant_start
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.callback_homeassistant_stop)

    # HomeAssistant event callbacks
    async def callback_homeassistant_start(self, event: "Event") -> NoReturn:
        """
        Stub for pre-load events.
        :param event: HomeAssistant start event
        :return:
        """
        pass

    async def callback_homeassistant_stop(self, event: "Event") -> NoReturn:
        """
        Shut down connections on HomeAssistant stop.
        :param event: HomeAssistant stop event
        :return:
        """
        _LOGGER.debug("Hekr system is shutting down")
        for device_id, device in self.devices.items():
            connector = device.connector
            listener = connector.listener
            if listener is not None and listener.is_running:
                _LOGGER.debug('Shutting down listener for device ID "%s"' % device_id)
                listener.stop()

            if connector.is_connected:
                _LOGGER.debug('Shutting down connector for device ID "%s"' % device_id)
                await connector.close_connection()

    async def callback_update_entities(
        self,
        device: Device,
        message_id: int,
        state: DeviceResponseState,
        action: str,
        data: Tuple["Command", Dict, int],
    ) -> NoReturn:
        """
        Callback for Hekr messages on receive. Schedules entities for update once after a message was received.
        :param device: Device message comes from
        :param message_id: Message ID
        :param state: Response state
        :param action: Message type (action)
        :param data: Tuple of executed command, data and frame number
        :return:
        """
        if (
            device
            and action in (ACTION_COMMAND_RESPONSE, ACTION_DEVICE_MESSAGE)
            and state == DeviceResponseState.SUCCESS
        ):

            _LOGGER.debug(
                "Received response (message ID: %d) from information command (action: %s) with data: %s"
                % (message_id, action, data)
            )
            command, data, frame_number = data

            update_entities = self.device_entities.get(device.device_id)

            if not update_entities:
                _LOGGER.info("Device %s does not have any associated entities" % device.device_id)
            else:
                protocol_id = self.devices_config_entries[device.device_id][CONF_PROTOCOL]
                protocol = SUPPORTED_PROTOCOLS[protocol_id]

                attribute_filter = protocol.get(PROTOCOL_FILTER)
                attributes = attribute_filter(data) if callable(attribute_filter) else data

                tasks = [
                    asyncio.create_task(entity.handle_data_update(attributes))
                    for entity in update_entities
                    if entity.command_receive == command.name
                ]

                if tasks:
                    _LOGGER.debug(
                        'Performing update on %d entities for command "%s"'
                        % (len(tasks), command.name)
                    )
                    await asyncio.wait(tasks)
                    _LOGGER.debug("Update complete!")
                else:
                    _LOGGER.debug('No updates scheduled for command "%s"' % command.name)

    # Device registry management
    def get_device_info_dict(self, device_id: DeviceID):
        device = self.devices.get(device_id)
        if not device:
            raise Exception("Device %s not in HekrData registry" % device_id)

        device_cfg = self.devices_config_entries[device.device_id]

        protocol_id = device_cfg.get(CONF_PROTOCOL)
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        attrs = dict()
        attrs["identifiers"] = {(DOMAIN, device.device_id)}

        if device.device_info is None:
            model = protocol.get(PROTOCOL_NAME, protocol_id)
            manufacturer = None
            attrs["connections"] = set()
            attrs["name"] = device_cfg.get(CONF_NAME)
        else:
            model = device.product_name
            manufacturer = None
            attrs["connections"] = set()  # @TODO: physical address
            attrs["name"] = device.device_name
            attrs["sw_version"] = device.firmware_version
            # attrs['hw_version'] = device.hardware_version

        if self.use_model_from_protocol:
            attrs["model"] = protocol.get(PROTOCOL_MODEL, model)
            attrs["manufacturer"] = protocol.get(PROTOCOL_MANUFACTURER, manufacturer)
        else:
            attrs["model"] = model or protocol.get(PROTOCOL_MODEL)
            attrs["manufacturer"] = manufacturer or protocol.get(PROTOCOL_MANUFACTURER)

        return attrs

    async def create_device_registry_entry(
        self, device_id: DeviceID, config_entry_id: str
    ) -> "DeviceEntry":
        """Create device registry entry for device."""
        attrs = self.get_device_info_dict(device_id)
        dev_reg: "DeviceRegistry" = await self.hass.helpers.device_registry.async_get_registry()
        device_entry = dev_reg.async_get_or_create(config_entry_id=config_entry_id, **attrs)

        return device_entry

    # Entity management
    def setup_entities(self, config_entry: config_entries.ConfigEntry) -> List[asyncio.Task]:
        _LOGGER.debug("Setting up components for config entry %s" % config_entry.entry_id)
        tasks = []

        for conf_key, (entity_domain, protocol_key) in CONF_DOMAINS.items():
            _LOGGER.debug(
                "Forwarding entry ID %s set up for entity domain %s for"
                % (config_entry.entry_id, entity_domain)
            )

            tasks.append(
                self.hass.async_create_task(
                    self.hass.config_entries.async_forward_entry_setups(config_entry, entity_domain)
                )
            )

        return tasks

    def collect_devices_for_entry(
        self, config_entry: config_entries.ConfigEntry
    ) -> List[DeviceID]:
        conf = config_entry.data
        devices_for_entry = []

        if CONF_DEVICE in conf:
            device_cfg = conf[CONF_DEVICE]
            device_id = device_cfg[CONF_DEVICE_ID]
            devices_for_entry.append(device_id)

        elif CONF_ACCOUNT in conf:
            account_cfg = conf[CONF_ACCOUNT]
            account_id = account_cfg[CONF_USERNAME]
            devices_for_entry.extend(self.get_account_devices(account_id).keys())

        return devices_for_entry

    def unload_entities(self, config_entry: config_entries.ConfigEntry) -> List[asyncio.Task]:
        _LOGGER.debug("Unloading components for config entry %s" % config_entry.entry_id)
        tasks = []
        for conf_key, (entity_domain, protocol_key) in CONF_DOMAINS.items():
            _LOGGER.debug(
                "Forwarding entry ID %s set up for entity domain %s for"
                % (config_entry.entry_id, entity_domain)
            )

            tasks.append(
                self.hass.async_create_task(
                    self.hass.config_entries.async_forward_entry_unload(
                        config_entry, entity_domain
                    )
                )
            )

        return tasks

    # Device setup methods
    def add_device(self, device: Device, device_cfg: Optional[ConfigType]):
        device.add_callback(self.callback_update_entities)
        self.devices[device.device_id] = device
        self.devices_config_entries[device.device_id] = device_cfg

    def create_local_device(self, device_cfg: ConfigType) -> Device:
        """
        Create device with local connector.
        :param device_cfg: Configuration from which to create the device
        :return: Device object
        """
        _LOGGER.debug("Creating device via get_add_device with config: %s" % device_cfg)
        protocol_id = device_cfg.get(CONF_PROTOCOL)
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        connect_port = device_cfg.get(CONF_PORT, protocol.get(PROTOCOL_PORT))
        if connect_port is None:
            raise Exception(
                'Protocol "%s" for device with ID "%s" does not provide default port. Please, '
                "configure port manually." % (protocol_id, device_cfg.get(CONF_DEVICE_ID))
            )

        connector = LocalConnector(
            host=device_cfg.get(CONF_HOST),
            port=connect_port,
            application_id=device_cfg.get(CONF_APPLICATION_ID, DEFAULT_APPLICATION_ID),
        )
        connector.timeout = device_cfg.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        device_id = device_cfg[CONF_DEVICE_ID]
        device = Device(
            device_id=device_id,
            control_key=device_cfg.get(CONF_CONTROL_KEY),
            protocol=protocol[PROTOCOL_DEFINITION],
        )
        device.connector = connector

        if CONF_NAME not in device_cfg:
            device_cfg[CONF_NAME] = DEFAULT_NAME_DEVICE.format(
                protocol_name=protocol.get(PROTOCOL_NAME, protocol_id), device_id=device_id
            )

        self.add_device(device, device_cfg)

        return device

    # Account setup methods
    def create_account(self, account_cfg: ConfigType) -> Account:
        """
        Create account
        :param account_cfg:
        :return:
        """
        _LOGGER.debug("Creating account with config: %s" % account_cfg)

        from hekrapi.account import Account

        account_id = account_cfg[CONF_USERNAME]

        account = Account(
            username=account_id,
            password=account_cfg[CONF_PASSWORD],
        )
        account.current_time = now

        self.accounts[account_id] = account
        self.accounts_config_entries[account_id] = account_cfg

        return account

    async def update_account(self, account_id: Username) -> bool:
        account_cfg = self.accounts_config_entries[account_id]
        account = self.accounts[account_id]
        customize_cfg = account_cfg.get(CONF_CUSTOMIZE, {})

        protocols = {
            protocol_id: protocol[PROTOCOL_DEFINITION]
            for protocol_id, protocol in SUPPORTED_PROTOCOLS.items()
        }

        await account.authenticate()
        await account.update_devices(
            protocols=protocols.values(),
            with_timeout=account_cfg.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        devices_added = 0
        for device_id, device in account.devices.items():
            if device_id in self.devices:
                _LOGGER.debug("Found existing device %s during account setup" % device_id)
                continue

            new_device_cfg = customize_cfg.get(CONF_CUSTOMIZE, {})
            if new_device_cfg is False:
                _LOGGER.debug("Skipped adding device %s due to customize setting" % device_id)
                continue

            elif CONF_PROTOCOL in new_device_cfg:
                protocol_id = new_device_cfg[CONF_PROTOCOL]
                device.protocol = SUPPORTED_PROTOCOLS[protocol_id][PROTOCOL_DEFINITION]

            elif not device.protocol or device.protocol not in protocols.values():
                _LOGGER.warning(
                    "Device %s does not operate under supported protocol, and therefore will not be added."
                    % device_id
                )
                continue

            else:
                protocol_order_number = list(protocols.values()).index(device.protocol)
                protocol_id = list(protocols.keys())[protocol_order_number]
                new_device_cfg[CONF_PROTOCOL] = protocol_id

                _LOGGER.debug(
                    "Matched discovered device %s to supported protocol %s"
                    % (device_id, protocol_id)
                )

            new_device_cfg[CONF_DEVICE_ID] = device_id
            new_device_cfg[CONF_ACCOUNT] = account_id

            if CONF_NAME not in new_device_cfg:
                new_device_cfg[CONF_NAME] = device.device_name

            _LOGGER.debug("Adding device %s from account %s" % (device, account))

            self.add_device(device, new_device_cfg)

            devices_added += 1

        if not devices_added:
            _LOGGER.warning(
                "Account %s is added with no devices. Please, remove it from configuration if you don't plan on "
                "getting any devices (updated on restart) from it." % account
            )
            return False

        _LOGGER.debug("Added %d devices from account %s" % (devices_added, account_id))

        self.create_account_updater(account_id)

        tasks = [
            asyncio.create_task(connector.open_connection())
            for connector in account.connectors.values()
        ]
        await asyncio.wait(tasks)
        self.refresh_connections()

        return True

    def create_account_updater(self, account_id):
        account = self.accounts[account_id]
        account_cfg = self.accounts_config_entries[account_id]

        if CONF_TOKEN_UPDATE_INTERVAL in account_cfg:
            run_updater_at = now() + account_cfg[CONF_TOKEN_UPDATE_INTERVAL]
        else:
            run_updater_at = account.access_token_expires_at - timedelta(seconds=20)

        self.account_updaters[account_id] = async_track_point_in_time(
            hass=self.hass,
            action=partial(self.update_account_authentication, account_id),
            point_in_time=run_updater_at,
        )

        _LOGGER.debug("Next updater scheduled for account %s: %s" % (account_id, run_updater_at))

    def remove_account_updater(self, account_id):
        if account_id in self.account_updaters:
            self.account_updaters[account_id]()
            del self.account_updaters[account_id]

    async def update_account_authentication(self, account_id, *_):
        _LOGGER.debug("Updating account %s authentication" % account_id)
        account = self.accounts[account_id]

        try:
            await account.refresh_authentication()
        except HekrAPIException:
            _LOGGER.exception("Hekr API exception occurred during account authentication update:")

        _LOGGER.debug("Updating authentication on account %s successful" % account_id)

        self.create_account_updater(account_id)

    def get_account_devices(self, account_id: str) -> Dict[DeviceID, Device]:
        return {
            device_id: self.devices[device_id]
            for device_id, config in self.devices_config_entries.items()
            if config.get(CONF_ACCOUNT) == account_id
        }

    async def cleanup_account(self, account_id: str):
        account = self.accounts.get(account_id)
        if not account:
            # @TODO: better cleanup?
            return True

        self.remove_account_updater(account_id)

        self.accounts.pop(account_id)
        self.accounts_config_entries.pop(account_id)
        # @TODO: remove devices

    async def cleanup_device(self, device_id: str, with_refresh: bool = True):
        device = self.devices.get(device_id)
        if device:
            if device.connector.listener is not None and device.connector.listener.is_running:
                device.connector.listener.stop()
            await device.connector.close_connection()
            del self.devices[device_id]

        if device_id in self.devices_config_entries:
            del self.devices_config_entries[device_id]

        self.remove_device_updater(device_id)

        if with_refresh:
            self.refresh_connections()

    # Updater and listener management
    def _create_updater(
        self, device_id: DeviceID, commands: Set[str], interval: timedelta
    ) -> Callable:
        """
        Create updater for device.
        :param device_id: Device ID to poll
        :param commands: Commands to send on polling
        :param interval: Interval with which to poll
        :return: Updater cancel function
        """

        async def call_command(*_):
            device = self.devices.get(device_id)
            if device is None:
                _LOGGER.debug('Device with ID "%s" is missing, cannot run updater' % device_id)
                return

            _LOGGER.debug(
                'Running updater for device "%s" with commands: %s'
                % (device_id, ", ".join(commands))
            )
            device = self.devices[device_id]
            command_iter = iter(commands)
            first_command = next(command_iter)

            _LOGGER.debug("Running update command: %s" % first_command)
            await device.command(first_command)
            for command in command_iter:
                _LOGGER.debug(
                    "Sleeping for %d seconds before running command: %s"
                    % (DEFAULT_SLEEP_INTERVAL, command)
                )
                await asyncio.sleep(DEFAULT_SLEEP_INTERVAL)
                _LOGGER.debug("Running update command: %s" % command)
                await device.command(command)

        len_cmd = len(commands)
        # assumed: 1 second per command, N second(-s) intervals between commands
        min_seconds = len_cmd + (len_cmd - 1) * DEFAULT_SLEEP_INTERVAL
        if interval.seconds < min_seconds:
            _LOGGER.warning(
                "Interval provided for updater (%d seconds) is too low to perform updates! "
                "Adjusted automatically to %d seconds to prevent hiccups."
                % (interval.seconds, min_seconds)
            )
            interval = timedelta(seconds=min_seconds)

        # noinspection PyTypeChecker
        return async_track_time_interval(hass=self.hass, action=call_command, interval=interval)

    def remove_device_updater(self, device_id: DeviceID):
        if device_id in self.device_updaters:
            self.device_updaters[device_id][1]()
            del self.device_updaters[device_id]

    def _refresh_updaters(self) -> NoReturn:
        """
        Derive required updaters for devices and create new and/or cancel existing.
        :return:
        """
        for device_id, entities in self.device_entities.items():
            update_commands = set([entity.command_update for entity in entities])
            if device_id in self.device_updaters:
                current_update_commands, canceler = self.device_updaters[device_id]
                if not update_commands ^ current_update_commands:
                    _LOGGER.debug("Updater for device %s is fine, not cancelling" % device_id)
                    continue
                canceler()
                del self.device_updaters[device_id]

            if update_commands:
                _LOGGER.debug(
                    'Creating updater for device with ID "%s" with commands: %s'
                    % (device_id, ", ".join(update_commands))
                )
                device_cfg = self.devices_config_entries[device_id]
                interval = device_cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                if isinstance(interval, int):
                    interval = timedelta(seconds=interval)

                self.device_updaters[device_id] = (
                    update_commands,
                    self._create_updater(
                        device_id=device_id,
                        commands=update_commands,
                        interval=interval,
                    ),
                )
            else:
                _LOGGER.debug('No updater required for device with ID "%s"' % device_id)

        _LOGGER.debug("Refreshed updaters: %s" % self.device_updaters)

    def _create_listener(self, connector: "_BaseConnector"):
        from hekrapi.device import Listener

        return Listener(
            connector,
            callback_exec_function=self.hass.add_job,
            callback_task_function=self.hass.async_create_task,
            auto_reconnect=True,
        )

    def _refresh_listeners(self):
        required_device_ids = self.device_updaters.keys()
        _LOGGER.debug("Required device IDs for listening: %s" % required_device_ids)
        active_listeners = set()
        required_listeners = set()
        for device_id, device in self.devices.items():
            if device_id in required_device_ids:
                _LOGGER.debug("Device ID %s is required, adding its listener" % device_id)
                listener = device.connector.get_listener(listener_factory=self._create_listener)
                required_listeners.add(listener)
                if listener.is_running:
                    _LOGGER.debug("Listener for device ID %s is active" % device_id)
                    active_listeners.add(listener)
                else:
                    _LOGGER.debug("Listener for device ID %s is inactive" % device_id)
            else:
                listener = device.connector.listener
                if listener is not None and listener.is_running:
                    active_listeners.add(listener)

        for listener in active_listeners - required_listeners:
            if listener.is_running:
                listener.stop()

        for listener in required_listeners - active_listeners:
            if not listener.is_running:
                listener.start()

    def refresh_connections(self):
        # 1. Refresh updaters
        self._refresh_updaters()
        # 2. Refresh listeners
        self._refresh_listeners()
