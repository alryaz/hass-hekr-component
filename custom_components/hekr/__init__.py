""" Basic Hekr protocol implementation based on Wisen app. """
import asyncio
import logging
from asyncio import Task
from typing import Optional, Dict, List, Set, TYPE_CHECKING, Union, Callable

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_PROTOCOL, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, \
    EVENT_HOMEASSISTANT_START, CONF_NAME, CONF_SCAN_INTERVAL, CONF_PLATFORM
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

from hekrapi import ACTION_COMMAND_RESPONSE, ACTION_DEVICE_MESSAGE, DeviceResponseState, DeviceID
from hekrapi.device import Device
from hekrapi.exceptions import HekrAPIException
from .const import *
from .schemas import CONFIG_SCHEMA
from .supported_protocols import SUPPORTED_PROTOCOLS

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceRegistry, DeviceEntry
    from hekrapi.device import Device, _BaseConnector
    from .sensor import HekrEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, yaml_config):
    """Set up cloud authenticators from config."""
    domain_config = yaml_config.get(DOMAIN)
    if not domain_config:
        return True

    hekr_data = HekrData.get_instance(hass)
    hekr_data.use_model_from_protocol = domain_config[CONF_USE_MODEL_FROM_PROTOCOL]

    devices_config = domain_config.get(CONF_DEVICES)
    if devices_config:
        for item_config in devices_config:
            _LOGGER.debug('Device entry from YAML: %s' % item_config)

            device_id = item_config.get(CONF_DEVICE_ID)
            if device_id in hekr_data.devices_config:
                _LOGGER.warning('Device with ID "%s" set up multiple times. Please, check your configuration.')
                continue

            _LOGGER.debug('Adding device entry with ID "%s"' % device_id)
            hekr_data.devices_config[device_id] = item_config
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={CONF_DEVICE: item_config},
                )
            )

    accounts_config = domain_config.get(CONF_ACCOUNTS)
    if accounts_config:
        _LOGGER.warning('Accounts are not supported in current release. Please, remove [%s->%s] key from your YAML'
                        'configuration file to avoid further incompatibilities.' % (DOMAIN, CONF_ACCOUNTS))

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry):
    conf = config_entry.data

    hekr_data = HekrData.get_instance(hass)
    hass_devices_config = hekr_data.devices_config

    try:
        if CONF_DEVICE in conf:
            device_cfg = conf[CONF_DEVICE]
            device_id = device_cfg.get(CONF_DEVICE_ID)

            if config_entry.source == config_entries.SOURCE_IMPORT:
                if device_id not in hass_devices_config:
                    _LOGGER.info('Removing entry %s after removal from YAML configuration.' % config_entry.entry_id)
                    hass.async_create_task(
                        hass.config_entries.async_remove(config_entry.entry_id)
                    )
                    return False
            elif device_id in hass_devices_config:
                _LOGGER.warning('Duplicate entry for device "%s" detected. Please, check your integrations.' % device_id)
                return False

            _LOGGER.debug('Setting up config entry for device with ID "%s"' % device_id)
            hekr_data.devices_config[device_id] = device_cfg

            device = await hekr_data.create_connected_device(device_cfg)
            #await hekr_data.create_device_registry_entry(device, config_entry.entry_id)
            hekr_data.setup_entities(config_entry)

            _LOGGER.debug('Successfully set up device with ID "%s"' % device_id)
            return True

    except HekrAPIException:
        _LOGGER.exception("API exception while setting up config entry %s" % config_entry.entry_id)
        return False

    _LOGGER.error('Unknown configuration format for entry ID %s, must remove' % config_entry.entry_id)
    hass.async_create_task(
        hass.config_entries.async_remove(config_entry.entry_id)
    )
    return False


async def async_unload_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry):
    _LOGGER.debug('Unloading Hekr config entry with ID "%s"' % config_entry.entry_id)
    conf = config_entry.data

    hekr_data = HekrData.get_instance(hass)

    try:
        if CONF_DEVICE in conf:
            device_cfg = conf[CONF_DEVICE]
            device_id = device_cfg.get(CONF_DEVICE_ID)

            _LOGGER.debug('Unloaded device ID: %s, device config: %s' % (device_id, device_cfg))

            #await hekr_data.delete_device_registry_entry(device_id)
            await asyncio.wait(hekr_data.unload_entities(config_entry))

            device = hekr_data.devices.pop(device_id)
            if device.connector.listener is not None and device.connector.listener.is_running:
                device.connector.listener.stop()
            await device.connector.close_connection()

            if config_entry.source != config_entries.SOURCE_IMPORT:
                del hekr_data.devices_config[device_id]

    except HekrAPIException:
        _LOGGER.exception('Exception occurred while unloading entry %s' % config_entry.entry_id)

    return True

AnyDeviceIdentifier = Union[DeviceID, 'Device']
class HekrData:
    @classmethod
    def get_instance(cls, hass):
        hekr_data = hass.data.get(DOMAIN)
        if hekr_data is None:
            hekr_data = cls(hass)
            hass.data[DOMAIN] = hekr_data
        return hekr_data

    def __init__(self, hass: HomeAssistantType):
        if isinstance(hass.data.get(DOMAIN), HekrData):
            raise Exception('One instance of HekrData is already installed')

        self.hass = hass

        self.devices: Dict[DeviceID, 'Device'] = dict()
        self.devices_config: Dict[DeviceID, ConfigType] = dict()
        self.device_entries: Dict[DeviceID, DeviceEntry] = dict()
        self.update_intervals: Dict[DeviceID, Dict[str, timedelta]] = dict()
        self.device_entities: Dict[DeviceID, List['HekrEntity']] = dict()
        self.updaters: Dict[DeviceID, Callable] = dict()

        self.use_model_from_protocol = DEFAULT_USE_MODEL_FROM_PROTOCOL

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.homeassistant_start
        )
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.homeassistant_stop
        )


    # Helper methods (not related to HekrData directly)
    @staticmethod
    def detect_protocol_from_info(device_info) -> Optional[str]:
        for protocol_id, supported_protocol in SUPPORTED_PROTOCOLS:
            if PROTOCOL_DETECTION in supported_protocol:
                if supported_protocol.get(PROTOCOL_DETECTION)(device_info):
                    return protocol_id
            else:
                # @TODO: add more protocol detection algorithms
                continue

        return None

    @staticmethod
    def resolve_device_id(device_id: AnyDeviceIdentifier) -> str:
        if isinstance(device_id, str):
            return device_id
        return device_id.device_id

    def resolve_device(self, device_id: AnyDeviceIdentifier) -> 'Device':
        if isinstance(device_id, str):
            return self.devices[device_id]
        return device_id


    # HomeAssistant event listeners
    async def homeassistant_start(self, *_):
        pass

    async def homeassistant_stop(self, *_):
        _LOGGER.debug('Hekr system is shutting down')
        for device_id, device in self.devices.items():
            connector = device.connector
            listener = connector.listener
            if listener is not None and listener.is_running:
                _LOGGER.debug('Shutting down listener for device ID "%s"' % device_id)
                listener.stop()

            if connector.is_connected:
                _LOGGER.debug('Shutting down connector for device ID "%s"' % device_id)
                await connector.close_connection()

    async def update_entities_callback(self, hekr_device, message_id, state, action, data):
        if hekr_device and action in (ACTION_COMMAND_RESPONSE, ACTION_DEVICE_MESSAGE) \
                and state == DeviceResponseState.SUCCESS:

            _LOGGER.debug('Received response (message ID: %d) from information command (action: %s) with data: %s'
                          % (message_id, action, data))
            command, data, frame_number = data

            update_entities = self.device_entities.get(hekr_device.device_id)

            if update_entities:
                protocol = self.get_device_protocol(device_id=hekr_device.device_id)
                attribute_filter = protocol.get(PROTOCOL_FILTER)
                attributes = attribute_filter(data) if callable(attribute_filter) else data

                tasks = [
                    entity.handle_data_update(attributes)
                    for entity in update_entities
                    if entity.command_receive == command.name
                ]

                if tasks:
                    _LOGGER.debug('Performing update on %d entities for command "%s"' % (len(tasks), command.name))
                    await asyncio.wait(tasks)
                    _LOGGER.debug('Update complete!')
                else:
                    _LOGGER.debug('No updates scheduled for command "%s"' % command.name)


    # Device registry management
    async def get_device_registry_entry(self, device_id: AnyDeviceIdentifier) -> Optional['DeviceEntry']:
        device_id = self.resolve_device_id(device_id)
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        return device_registry.async_get(self.device_entries[device_id])

    async def delete_device_registry_entry(self, device_id: AnyDeviceIdentifier) -> None:
        device_id = self.resolve_device_id(device_id)
        device_registry: DeviceRegistry = await self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_remove_device(self.device_entries[device_id].id)

    def get_device_info_dict(self, device: AnyDeviceIdentifier):
        device = self.resolve_device(device)
        device_cfg = self.devices_config[device.device_id]

        protocol_id = device_cfg.get(CONF_PROTOCOL)
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        attrs = dict()
        attrs['identifiers'] = {(DOMAIN, device.device_id)}

        if device.device_info is None:
            model = protocol.get(PROTOCOL_NAME, protocol_id)
            manufacturer = None
            attrs['connections'] = set()
            attrs['name'] = device_cfg.get(CONF_NAME)
        else:
            model = device.product_name
            manufacturer = None
            attrs['connections'] = set()
            attrs['name'] = device.device_name
            attrs['sw_version'] = device.firmware_version

        if self.use_model_from_protocol:
            attrs['model'] = protocol.get(PROTOCOL_MODEL, model)
            attrs['manufacturer'] = protocol.get(PROTOCOL_MANUFACTURER, manufacturer)
        else:
            attrs['model'] = model or protocol.get(PROTOCOL_MODEL)
            attrs['manufacturer'] = manufacturer or protocol.get(PROTOCOL_MANUFACTURER)

        return attrs

    async def create_device_registry_entry(self, device: 'Device', config_entry_id: str) -> 'DeviceEntry':
        """Create device registry entry for device."""
        attrs = self.get_device_info_dict(device)
        dev_reg: 'DeviceRegistry' = await self.hass.helpers.device_registry.async_get_registry()
        device_entry = dev_reg.async_get_or_create(
            config_entry_id=config_entry_id,
            **attrs
        )

        self.device_entries[device.device_id] = device_entry

        return device_entry

    # Entity management
    def setup_entities(self, config_entry: config_entries.ConfigEntry) -> List[Task]:
        # @TODO: Refactor for CONF_DOMAINS
        _LOGGER.debug('Setting up components for config entry %s' % config_entry.entry_id)
        tasks = []
        for conf_key, (entity_domain, protocol_key) in CONF_DOMAINS.items():
            _LOGGER.debug('Forwarding entry ID %s set up for entity domain %s for'
                          % (config_entry.entry_id, entity_domain))

            tasks.append(self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(config_entry, entity_domain)
            ))

        return tasks

    def unload_entities(self, config_entry: config_entries.ConfigEntry) -> List[Task]:
        _LOGGER.debug('Unloading components for config entry %s' % config_entry.entry_id)
        tasks = []
        for conf_key, (entity_domain, protocol_key) in CONF_DOMAINS.items():
            _LOGGER.debug('Forwarding entry ID %s set up for entity domain %s for'
                          % (config_entry.entry_id, entity_domain))

            tasks.append(self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_unload(config_entry, entity_domain)
            ))

        return tasks

    # Setup methods
    def get_device_protocol(self, device_id: AnyDeviceIdentifier):
        device_id = self.resolve_device_id(device_id)
        protocol_id = self.devices_config[device_id].get(CONF_PROTOCOL)
        return SUPPORTED_PROTOCOLS.get(protocol_id)

    def create_device(self, config: ConfigType) -> 'Device':
        _LOGGER.debug('Creating device via get_add_device with config: %s' % config)
        protocol_id = config.get(CONF_PROTOCOL)
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        from hekrapi.device import Device, CloudConnector, LocalConnector

        token = config.get(CONF_TOKEN)
        if token is None:
            connect_port = config.get(CONF_PORT, protocol.get(PROTOCOL_PORT))
            if connect_port is None:
                raise Exception('Protocol "%s" for device with ID "%s" does not provide default port. Please, '
                                'configure port manually.' % (protocol_id, config.get(CONF_DEVICE_ID)))

            connector = LocalConnector(
                host=config.get(CONF_HOST),
                port=connect_port,
                application_id=config.get(CONF_APPLICATION_ID, DEFAULT_APPLICATION_ID),
            )
        else:
            connector = CloudConnector(
                token=config.get(CONF_TOKEN),
                connect_host=config.get(CONF_CLOUD_HOST, DEFAULT_CLOUD_HOST),
                connect_port=config.get(CONF_CLOUD_PORT, DEFAULT_CLOUD_PORT),
                application_id=config.get(CONF_APPLICATION_ID, DEFAULT_APPLICATION_ID),
            )

        device = Device(
            device_id=config.get(CONF_DEVICE_ID),
            control_key=config.get(CONF_CONTROL_KEY),
            protocol=protocol[PROTOCOL_DEFINITION]
        )
        device.connector = connector
        device.add_callback(self.update_entities_callback)
        self.devices[device.device_id] = device
        self.devices_config[device.device_id] = config

        return device

    def get_create_device(self, config: ConfigType, compare_configs: bool = True) -> 'Device':
        device_id = config.get(CONF_DEVICE_ID)

        device: Optional['Device'] = self.devices.get(device_id)
        if device is None:
            device = self.create_device(config)

        elif compare_configs:
            device_config = self.devices_config[device_id]

            exclude_compare = [*CONF_DOMAINS.keys(), CONF_SCAN_INTERVAL, CONF_PLATFORM, CONF_NAME]
            invalid_keys = []
            for conf_key in {*device_config.keys(), *config.keys()}:
                if conf_key not in exclude_compare and device_config.get(conf_key) != config.get(conf_key):
                    invalid_keys.append(conf_key)

            if invalid_keys:
                raise  Exception("Cannot create device because a similar one exists, but with different configuration on"
                                 "keys: %s" % ", ".join(invalid_keys))

        return device

    async def create_connected_device(self, config: ConfigType) -> 'Device':
        device = self.create_device(config)
        await device.connector.open_connection()
        self.refresh_connections()
        return device

    async def get_create_connected_device(self, config: ConfigType) -> 'Device':
        device = self.get_create_device(config)
        if device.connector.is_connected:
            return device
        await device.connector.open_connection()
        self.refresh_connections()
        return device


    # Updater and listener management
    def _create_updater(self, device_id: DeviceID, commands: Set[str], interval: timedelta):
        async def call_command(*_):
            device = self.devices.get(device_id)
            if device is None:
                _LOGGER.debug('Device with ID "%s" is missing, cannot run updater' % device_id)
                return

            _LOGGER.debug('Running updater for device "%s" with commands: %s' % (device_id, ', '.join(commands)))
            device = self.devices[device_id]
            command_iter = iter(commands)
            first_command = next(command_iter)

            _LOGGER.debug('Running update command: %s' % first_command)
            await device.command(first_command)
            for command in command_iter:
                _LOGGER.debug('Sleeping for %d seconds before running command: %s' % (DEFAULT_SLEEP_INTERVAL, command))
                await asyncio.sleep(DEFAULT_SLEEP_INTERVAL)
                _LOGGER.debug('Running update command: %s' % command)
                await device.command(command)

        len_cmd = len(commands)
        # assumed: 1 second per command, N second(-s) intervals between commands
        min_seconds = len_cmd + (len_cmd - 1) * DEFAULT_SLEEP_INTERVAL
        if interval.seconds < min_seconds:
            _LOGGER.warning('Interval provided for updater (%d seconds) is too low to perform updates! '
                            'Adjusted automatically to %d seconds to prevent hiccups.'
                            % (interval.seconds, min_seconds))
            interval = timedelta(seconds=min_seconds)

        # noinspection PyTypeChecker
        return async_track_time_interval(
            hass=self.hass,
            action=call_command,
            interval=interval
        )

    def _refresh_updaters(self):
        for device_id, entities in self.device_entities.items():
            if device_id in self.updaters:
                # cancel running updater
                self.updaters[device_id]()
                del self.updaters[device_id]

            update_commands = set([entity.command_update for entity in entities])
            if update_commands:
                _LOGGER.debug('Creating updater for device with ID "%s" with commands: %s'
                              % (device_id, ', '.join(update_commands)))
                device_cfg = self.devices_config[device_id]
                interval = device_cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                if isinstance(interval, int):
                    interval = timedelta(seconds=interval)

                self.updaters[device_id] = self._create_updater(
                    device_id=device_id,
                    commands=update_commands,
                    interval=interval,
                )
            else:
                _LOGGER.debug('No updater required for device with ID "%s"' % device_id)

        _LOGGER.debug('Refreshed updaters: %s' % self.updaters)

    def _create_listener(self, connector: '_BaseConnector'):
        from hekrapi.device import Listener
        return Listener(connector,
                        callback_exec_function=self.hass.add_job,
                        callback_task_function=self.hass.async_create_task,
                        auto_reconnect=True)

    def _refresh_listeners(self):
        required_device_ids = self.updaters.keys()
        _LOGGER.debug('Required device IDs for listening: %s' % required_device_ids)
        active_listeners = set()
        required_listeners = set()
        for device_id, device in self.devices.items():
            if device_id in required_device_ids:
                listener = device.connector.get_listener(listener_factory=self._create_listener)
                required_listeners.add(listener)
                if listener.is_running:
                    active_listeners.add(listener)
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
