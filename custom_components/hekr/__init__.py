""" Basic Hekr protocol implementation based on Wisen app. """
import asyncio
import logging
from asyncio import Task
from typing import Optional, Dict, List, Set, TYPE_CHECKING, Tuple, Union, Callable

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_PROTOCOL, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, \
    EVENT_HOMEASSISTANT_START, CONF_NAME, CONF_SCAN_INTERVAL, CONF_PLATFORM
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

from hekrapi import Listener, ACTION_COMMAND_RESPONSE, ACTION_DEVICE_MESSAGE, DeviceResponseState, DeviceID
from hekrapi.account import Account
from hekrapi.device import Device
from hekrapi.exceptions import HekrAPIException
from .const import *
from .schemas import CONFIG_SCHEMA
from .supported_protocols import SUPPORTED_PROTOCOLS

if TYPE_CHECKING:
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
            if hekr_data.get_device_config(device_id):
                _LOGGER.warning('Device with ID "%s" set up multiple times. Please, check your configuration.')
                continue

            _LOGGER.debug('Adding device entry with ID "%s"' % device_id)
            hekr_data.add_device_config(device_id, item_config)
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


async def async_setup_entry(hass, config_entry: config_entries.ConfigEntry):
    hekr_data = HekrData.get_instance(hass)

    hass_devices_config = hekr_data.devices_config

    conf = config_entry.data
    config_type = CONF_DEVICE if CONF_DEVICE in conf else CONF_ACCOUNT  # @TODO: placeholder solution
    item_config = conf[config_type]

    device_id = item_config.get(CONF_DEVICE_ID)

    if config_entry.source == config_entries.SOURCE_IMPORT:
        # incoming entry is an imported one
        if config_type == CONF_DEVICES and device_id not in hass_devices_config:
            # previously created via YAML config entry is removed from file, remove from storage too
            _LOGGER.info('Removing entry %s after removal from YAML configuration.' % config_entry.entry_id)
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
            return False

    elif config_type == CONF_DEVICES:
        if device_id in hass_devices_config:
            _LOGGER.warning('Duplicate entry for device "%s" detected. Please, check your integrations.' % device_id)
            return False

    try:
        if config_type == CONF_DEVICE:
            _LOGGER.debug('Adding device with config: %s' % item_config)
            hekr_data.add_device_config(device_id, item_config)
            device = hekr_data.get_add_device(item_config)

            await device.connector.open_connection()

            await hekr_data.create_device_registry_entry(config_entry, device)
            await hekr_data.component_setup(config_entry,
                                            sensor=conf.get(CONF_SENSORS),
                                            switch=conf.get(CONF_SWITCHES))
        else:
            _LOGGER.warning('Unknown config: %s' % item_config)
    except HekrAPIException:
        _LOGGER.exception("API exception while setting up config entry %s" % config_entry.entry_id)
        return False

    return True


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

        self.devices: Dict[DeviceID, 'Device'] = dict()
        self.devices_config = dict()
        self.accounts: Dict[str, Account] = dict()
        self.accounts_config = dict()
        self.update_intervals: Dict[DeviceID, Dict[str, timedelta]] = dict()

        self.device_entities: Dict[DeviceID, Dict['HekrEntity', timedelta]] = dict()
        self.current_updaters: Dict[DeviceID, Dict[Tuple[str, timedelta], Callable]] = dict()

        self.hass = hass
        self._listener_tasks: List[Tuple[Listener, Task]] = list()
        self._device_registry: Optional[DeviceRegistry] = None

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

    # HomeAssistant event listeners
    async def homeassistant_start(self, *_):
        pass

    async def homeassistant_stop(self, *_):
        _LOGGER.debug('Hekr system is shutting down')
        for listener, task in self._listener_tasks:
            if listener.is_running:
                _LOGGER.debug('Stopping listener: %s' % listener)
                listener.stop()

        for device in self.devices.values():
            if device.connector.is_connected:
                _LOGGER.debug('Closing connector: %s' % device.connector)
                await device.connector.close_connection()

    async def update_entities_callback(self, hekr_device, message_id, state, action, data):
        if hekr_device and action in (ACTION_COMMAND_RESPONSE, ACTION_DEVICE_MESSAGE) \
                and state == DeviceResponseState.SUCCESS:

            _LOGGER.debug('Received successful response from information command (action: %s) with data: %s'
                          % (action, data))
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
                    _LOGGER.debug('Performing update on %d entities' % len(tasks))
                    await asyncio.wait(tasks)
                    _LOGGER.debug('Update complete!')

    # Setup methods
    async def create_device_registry_entry(self, config_entry: config_entries.ConfigEntry,
                                           device: 'Device'):
        """Create device registry entry for device."""
        device_cfg = config_entry.data[CONF_DEVICE]
        protocol_id = device_cfg.get(CONF_PROTOCOL)
        protocol = SUPPORTED_PROTOCOLS[protocol_id]

        if device.device_info is None:
            model = protocol.get(PROTOCOL_NAME, protocol_id)
            manufacturer = None
            attrs = {
                'connections': set(),
                'name': device_cfg.get(CONF_NAME),
            }
        else:
            model = device.product_name
            manufacturer = None
            attrs = {
                'connections': set(),
                'name': device.device_name,
            }

        if self.use_model_from_protocol:
            model = protocol.get(PROTOCOL_MODEL, model)
            manufacturer = protocol.get(PROTOCOL_MANUFACTURER, manufacturer)
        else:
            model = model or protocol.get(PROTOCOL_MODEL)
            manufacturer = manufacturer or protocol.get(PROTOCOL_MANUFACTURER)

        if self._device_registry is None:
            self._device_registry: Optional[
                DeviceRegistry] = await self.hass.helpers.device_registry.async_get_registry()

        return self._device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, device.device_id)},
            model=model,
            manufacturer=manufacturer,
            **attrs
        )

    async def get_device_from_registry(self, device: Union[DeviceID, 'Device']):
        if self._device_registry is None:
            self._device_registry: Optional[
                DeviceRegistry] = await self.hass.helpers.device_registry.async_get_registry()

        return await self._device_registry.async_get_device({(DOMAIN, device.device_id)})

    async def component_setup(self, config_entry, **kwargs):
        _LOGGER.debug('Setting up components for config entry %s' % config_entry.entry_id)
        set_up_components = []
        for component, to_setup in kwargs.items():
            if to_setup is not False:
                set_up_components.append(component)
                self.hass.async_create_task(
                    self.hass.config_entries.async_forward_entry_setup(config_entry, component)
                )

        _LOGGER.debug('Set up components: %s' % ', '.join(set_up_components))

        return set_up_components

    def get_device_protocol(self, device_id: Union[DeviceID, 'Device']):
        if isinstance(device_id, Device):
            device_id = device_id.device_id
        device_cfg = self.get_device_config(device_id)
        protocol_id = device_cfg.get(CONF_PROTOCOL)
        return SUPPORTED_PROTOCOLS.get(protocol_id)

    def add_entities_for_update(self, device: Union[str, 'Device'], entities: Union['HekrEntity', List['HekrEntity']],
                                update_interval: Optional[timedelta] = None):
        if isinstance(device, str):
            device_id = device
            device = self.get_device(device_id)
        if device is None:
            raise Exception('Device "%s" not found' % device_id)

        if not isinstance(entities, list):
            entities = [entities]

        if update_interval is None:
            update_interval = DEFAULT_SCAN_INTERVAL
        elif isinstance(update_interval, int):
            update_interval = timedelta(seconds=update_interval)
        elif isinstance(update_interval, dict):
            update_interval: timedelta = cv.time_period_dict(update_interval)
        elif not isinstance(update_interval, timedelta):
            raise TypeError('Invalid "update_interval" type: %s' % type(update_interval))

        _LOGGER.debug('Add callback for device %s, entities %s, update_interval %s'
                      % (device, entities, update_interval))

        device_entities = self.device_entities.setdefault(device.device_id, dict())
        device_entities.update({
            entity: update_interval
            for entity in entities
        })

        self.refresh_updaters()

    # Device config management
    def add_device_config(self, device_id: DeviceID, config: dict):
        self.devices_config[device_id] = config

    def get_device_config(self, device_id: DeviceID) -> Optional[dict]:
        return self.devices_config.get(device_id)

    # Device management
    def add_device(self, hekr_device: 'Device', config: Optional[dict] = None):
        if hekr_device.device_id in self.devices:
            raise Exception('Device already added')

        _LOGGER.debug('Adding device: %s' % hekr_device)
        self.devices[hekr_device.device_id] = hekr_device
        hekr_device.add_callback(self.update_entities_callback)

        if config is not None:
            self.add_device_config(hekr_device.device_id, config)

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)

    def get_add_device(self, config: ConfigType) -> Device:
        device_id = config.get(CONF_DEVICE_ID)

        device = self.get_device(device_id)
        if device is not None:
            device_config = self.get_device_config(device_id)

            exclude_compare = [*CONF_DOMAINS.keys(), CONF_SCAN_INTERVAL, CONF_PLATFORM, CONF_NAME]
            invalid_keys = []
            for conf_key in {*device_config.keys(), *config.keys()}:
                if conf_key not in exclude_compare and device_config.get(conf_key) != config.get(conf_key):
                    invalid_keys.append(conf_key)

            if invalid_keys:
                raise Exception("Cannot create device because a similar one exists, but with different configuration on"
                                "keys: %s" % ", ".join(invalid_keys))

        else:
            _LOGGER.debug('Creating device via get_add_device with config: %s' % config)
            protocol_id = config.get(CONF_PROTOCOL)
            protocol = SUPPORTED_PROTOCOLS[protocol_id]

            from hekrapi.device import Device, CloudConnector, LocalConnector

            token = config.get(CONF_TOKEN)
            if token is None:
                connect_port = config.get(CONF_PORT, protocol.get(PROTOCOL_PORT))
                if connect_port is None:
                    raise Exception('Protocol "%s" for device with ID "%s" does not provide default port. Please, '
                                    'configure port manually.' % (protocol_id, device_id))

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
                device_id=device_id,
                control_key=config.get(CONF_CONTROL_KEY),
                protocol=protocol[PROTOCOL_DEFINITION]
            )
            device.connector = connector

            self.add_device(device, config)
            self.refresh_listeners()

        return device

    # Account config management
    def add_account_config(self, token: str, config: dict):
        self.accounts_config[token] = config

    def get_account_config(self, token: str):
        return self.accounts_config.get(token)

    # Account management
    def add_account(self, token: str, account: 'Account', config: Optional[dict] = None):
        self.accounts[token] = account
        if config is not None:
            self.add_account_config(token, config)

    def get_account(self, token: str):
        return self.accounts.get(token)

    # Listener management
    @property
    def active_listeners(self) -> List['Listener']:
        return [listener for listener, task in self._listener_tasks]

    @property
    def required_listeners(self) -> Set['Listener']:
        return set([
            device.connector.get_listener(listener_factory=self.listener_factory)
            for device in self.devices.values()
        ])

    def listener_factory(self, connector: '_BaseConnector'):
        from hekrapi.device import Listener
        return Listener(connector,
                        callback_exec_function=self.hass.add_job,
                        callback_task_function=self.hass.async_create_task)

    def refresh_listeners(self):
        _LOGGER.debug('before refresh listeners %s', self._listener_tasks)
        required_listeners = self.required_listeners
        _LOGGER.debug('required listeners %s', required_listeners)
        existing_listeners = set()
        for lp_pair in self._listener_tasks:
            listener, task = lp_pair
            if listener not in required_listeners:
                _LOGGER.debug('stopping listener %s' % listener)
                listener.stop()
                self._listener_tasks.remove(lp_pair)
            else:
                existing_listeners.add(listener)
                if not listener.is_running:
                    _LOGGER.debug('starting listener %s' % listener)
                    listener.start()

        for listener in (required_listeners - existing_listeners):
            self._listener_tasks.append((listener, listener.start()))

        _LOGGER.debug('after refresh listeners %s', self._listener_tasks)

    # Updater management
    @property
    def required_updaters(self) -> Dict[DeviceID, Dict[str, timedelta]]:
        required_updaters = {}
        for device_id, entities in self.device_entities.items():
            device_updaters = {}
            required_updaters[device_id] = device_updaters
            for entity, update_interval in entities.items():
                update_command = entity.command_update
                current_interval = device_updaters.get(update_command)
                if current_interval is None or current_interval > update_interval:
                    device_updaters[update_command] = update_interval

        return required_updaters

    # noinspection PyTypeChecker
    def _create_updater(self, device_id: DeviceID, command: str, interval: timedelta):
        async def call_command(*_):
            if device_id in self.devices:
                await self.devices[device_id].command(command)

        return async_track_time_interval(
            hass=self.hass,
            action=call_command,
            interval=interval
        )

    def refresh_updaters(self):
        required_updaters = self.required_updaters
        _LOGGER.debug('Required updaters: %s' % required_updaters)
        current_updaters = self.current_updaters
        _LOGGER.debug('Current updaters: %s' % current_updaters)
        device_ids: Set[str] = {*required_updaters.keys(), *current_updaters.keys()}
        for device_id in device_ids:
            _LOGGER.debug('Processing updaters for "%s"' % device_id)
            if device_id in required_updaters and device_id in current_updaters:
                device_required_updaters: Set[Tuple[str, timedelta]] = \
                    {(command, update_interval) for command, update_interval in required_updaters[device_id].items()}
                device_current_updaters: Dict[Tuple[str, timedelta], Callable] = current_updaters[device_id]

                for key in (device_current_updaters.keys() - device_required_updaters):
                    # remove unneeded updaters
                    _LOGGER.debug('Removed updater on %s for cmd %s with interval %s'
                                  % (device_id, key[0], key[1]))
                    device_current_updaters[key]()
                    del device_current_updaters[key]

                for command, update_interval in (device_required_updaters - device_current_updaters.keys()):
                    # add new updaters
                    _LOGGER.debug('Added updater on %s for cmd %s with interval %s'
                                  % (device_id, command, update_interval))

                    # noinspection PyTypeChecker
                    device_current_updaters[(command, update_interval)] = \
                        self._create_updater(device_id, command, update_interval)

            elif device_id in required_updaters:
                current_updaters[device_id] = {
                    (command, update_interval): self._create_updater(device_id, command, update_interval)
                    for command, update_interval in required_updaters[device_id].items()
                }
                _LOGGER.debug('Added %d updaters for device "%s"' % (len(current_updaters[device_id]), device_id))
            else:
                for (command, update_interval), stopper in current_updaters[device_id].items():
                    stopper()
                _LOGGER.debug('Removed %d updaters for device "%s"' % (len(current_updaters[device_id]), device_id))
                del current_updaters[device_id]

        _LOGGER.debug('Refreshed updaters: %s' % self.current_updaters)
