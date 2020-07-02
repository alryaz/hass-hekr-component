"""Initialize Hekr component"""

__all__ = [
    # Home Assistant required exports
    "CONFIG_SCHEMA",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",

    # Internal component exports
    "DEFAULT_NAME_FORMAT",
    "DEFAULT_TIMEOUT",
    "DATA_DEVICES",
    "DATA_ACCOUNTS",
    "DATA_ACCOUNTS_CONFIG",
    "DATA_DEVICES_CONFIG",
    "DATA_UPDATERS",
    "DATA_ACCOUNT_LISTENERS",
    "DATA_DEVICE_LISTENERS"
]

import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Tuple, Union, Set

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from hekrapi.enums import DeviceResponseState
from hekrapi.exceptions import ConnectorAuthenticationError, HekrAPIException, ConnectorError, AccountException
from hekrapi.types import DeviceID
from homeassistant import config_entries
from homeassistant.const import CONF_PROTOCOL, CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT, \
    CONF_HOST, CONF_PORT, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import ConfigType
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

from .const import DOMAIN, CONF_DEVICE_ID, CONF_CONTROL_KEY, CONF_DEVICES, AccountUsername, ListContentType, \
    DEFAULT_NAME_FORMAT, DEFAULT_TIMEOUT, DATA_ACCOUNTS, DATA_DEVICES, DATA_UPDATERS, CancellationCall, \
    DATA_DEVICE_LISTENERS, DATA_ACCOUNT_LISTENERS, DATA_ACCOUNTS_CONFIG, DATA_DEVICES_CONFIG, \
    DATA_DEVICE_ENTITIES, DEFAULT_SCAN_INTERVAL
from .supported_protocols import (
    SUPPORTED_PROTOCOLS,
    ALL_SUPPORTED_DOMAINS,
    SupportedProtocolType,
    get_supported_id_by_definition
)

if TYPE_CHECKING:
    from hekrapi.connector import DirectConnector, CloudConnector
    from hekrapi.device import Device
    from hekrapi.account import Account
    from .base_platform import HekrEntity
    from .supported_protocols import CommandCall
    from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


def list_set_validator(value: List[ListContentType]) -> Set[ListContentType]:
    """Convert list to set, and check whether all values are unique"""
    value_set = set(value)

    if len(value_set) != len(value):
        # Case: List contains non-unique values
        temp_set, errors = set(), list()
        for i, v in enumerate(value):
            if v in temp_set:
                errors.append(vol.Invalid('duplicate entity type', path=[i]))
            else:
                temp_set.add(v)

        if len(errors) == 1:
            # Sub-case: Only one error, raise one error
            raise errors[0]

        # Sub-case: Multiple errors, raise error wrapper
        raise vol.MultipleInvalid(errors)

    # Case: List does contains only unique values, return converted set
    return value_set


def protocol_validator(value: str) -> SupportedProtocolType:
    if value not in SUPPORTED_PROTOCOLS:
        # Case: Protocol is not supported, raise error
        raise vol.Invalid('unsupported protocol "%s"' % value)

    # Case: Protocol is supported, return supported protocol
    return SUPPORTED_PROTOCOLS[value]


def entity_type_validator(value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate entity type keys against given protocol"""
    protocol: Optional[SupportedProtocolType] = value.get(CONF_PROTOCOL)

    if protocol is None:
        # Case: Protocol is not set, entity types are not allowed

        configured_domains = value.keys() & ALL_SUPPORTED_DOMAINS
        if configured_domains:
            # Sub-case: Entity types are provided
            raise vol.MultipleInvalid(errors=[
                vol.Invalid('provided domain configuration with no protocol', path=[domain])
                for domain in configured_domains
            ])

        # Sub-case: Entity types are not provided
        return value

    supported_domains = protocol.get_supported_domains()

    # Case: Protocol is set, entity types are allowed from corresponding types in supported protocol
    errors = []
    for domain in ALL_SUPPORTED_DOMAINS:
        setup_entity_types: Optional[Union[bool, List[str]]] = value.get(domain)
        if setup_entity_types is None:
            # Sub-case: Entity types not provided for domain (protocol support not required)
            continue

        if domain not in supported_domains:
            # Sub-case: Entity types provided, protocol does not support domain
            errors.append(vol.Invalid("entity domain '%s' not supported in protocol" % (domain, ),
                                      path=[domain]))
            continue

        if isinstance(setup_entity_types, bool):
            # Sub-case: All entity types for domain enabled/disabled
            continue

        bad_entity_types = set(setup_entity_types) - protocol.get_domain_types(domain)
        if bad_entity_types:
            # Sub-case: Entity types provided, protocol does not support some entity types
            for bad_entity_type in bad_entity_types:
                bad_index = setup_entity_types.index(bad_entity_type)
                errors.append(vol.Invalid("entity type '%s' not found in protocol" % (bad_entity_type, ),
                                          path=[domain, bad_index]))
            continue

    if len(errors) == 1:
        # Case: Only one error, raise one error
        raise errors[0]
    elif len(errors) > 1:
        # Case: Multiple errors, raise error wrapper
        raise vol.MultipleInvalid(errors)

    # Case: No errors, value is valid
    return value


not_empty_list = vol.All(cv.ensure_list, vol.Length(min=1))
not_empty_list.__doc__ = "Not empty list validator"

ENTITY_CONFIG_BASE = vol.Schema({
    # (optional) Direct connection host
    # True = Use direct connection with host from device info
    # False = Use cloud connection
    # None = Detect direct connection
    # string = Use direct connection with specified host
    vol.Optional(CONF_HOST): vol.All(cv.boolean, cv.string),

    # (optional) Direct connection port
    # None = Use default settings
    # integer = When direct connection is used, use specified port
    vol.Optional(CONF_PORT): cv.port,

    # (optional) Protocol
    # None = When cloud connection is used, detect automatically
    # string = Use specified protocol (do not check compatibility) and provided entity types
    vol.Optional(CONF_PROTOCOL): protocol_validator,

    # (optional) Name format
    # UNDEFINED = Use default name format in entity name formatting
    # string = Use specified name format in entity name formatting
    vol.Optional(CONF_NAME, default=DEFAULT_NAME_FORMAT): cv.string_with_no_html,

    # (optional) Scan interval
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(cv.time_period, cv.positive_timedelta),

    # Per-domain entity types configuration
    **{
        # (optional) Entity domain configuration
        # None = Use default types for entity domain
        # True = Use all types for entity domain
        # False = Do not use entity domain
        # list(string) = Use specified types for entity domain
        vol.Optional(domain): vol.Any(
            cv.boolean,
            vol.All(
                not_empty_list,
                [cv.string],
                list_set_validator
            )
        )
        for domain in ALL_SUPPORTED_DOMAINS
    }
})

DEVICE_CONFIG_SCHEMA = vol.All(
    ENTITY_CONFIG_BASE.extend({
        # (required) Device ID
        vol.Required(CONF_DEVICE_ID): cv.string_with_no_html,

        # (required) Control key
        vol.Required(CONF_CONTROL_KEY): cv.string,

        # (required) Direct connection host
        vol.Required(CONF_HOST): cv.string_with_no_html,

        # (optional) Direct connection port
        # None = Use default protocol port
        # integer = Use specified port
        vol.Optional(CONF_PORT): cv.port,

        # (optional) Timeout on communication basics
        # None = Use default timeout (5 seconds) on every request
        # timedelta = Use specified timeout on every request
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(cv.time_period, cv.positive_timedelta),
    }),
    entity_type_validator
)


def remove_device_validator(value: Any) -> bool:
    """Validate whether device is disabled for account"""
    value = cv.boolean(value)
    if value is True:
        raise vol.Invalid("can only disable device")
    return False


ACCOUNT_CONFIG_SCHEMA = vol.Schema({
    # (required) Account username
    vol.Required(CONF_USERNAME): cv.string,

    # (required) Account password
    vol.Required(CONF_PASSWORD): cv.string,

    # (optional) Devices configuration (and blacklist)
    # device_id =>
    #   None = Add device if supported
    #   False = Exclude device from adding
    #   ENTITY_CONFIG_BASE = Add device if supported, according to provided configuration
    vol.Optional(CONF_DEVICES): vol.All(
        {cv.string_with_no_html: vol.Any(remove_device_validator, ENTITY_CONFIG_BASE)},
        vol.Length(min=1)
    ),

    # (optional) Account exchange timeout
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(cv.time_period, cv.positive_timedelta),
})

VALIDATE_SCHEMA = vol.Any(DEVICE_CONFIG_SCHEMA, ACCOUNT_CONFIG_SCHEMA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [VALIDATE_SCHEMA]),
}, extra=vol.ALLOW_EXTRA)


@callback
@bind_hass
def _find_existing_entry(hass: HomeAssistantType, config_key: str, identifier: str) \
        -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    if existing_entries:
        for config_entry in existing_entries:
            if config_entry.data.get(config_key) == identifier:
                return config_entry


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Setup routine for Hekr component"""
    # Initialize data holders
    hass.data[DATA_ACCOUNTS]: Dict[AccountUsername, 'Account'] = dict()
    hass.data[DATA_DEVICES]: Dict[DeviceID, 'Device'] = dict()
    hass.data[DATA_UPDATERS]: Dict[DeviceID, 'asyncio.Task'] = dict()
    hass.data[DATA_DEVICE_LISTENERS]: Dict[DeviceID, 'asyncio.Task'] = dict()
    hass.data[DATA_ACCOUNT_LISTENERS]: Dict[AccountUsername, 'asyncio.Task'] = dict()
    hass.data[DATA_DEVICE_ENTITIES]: Dict[DeviceID, List['HekrEntity']] = dict()

    # Process YAML config
    domain_config: Optional[List[Dict[str, Any]]] = config.get(DOMAIN)

    if not domain_config:
        return True

    accounts_config: Dict[str, Dict[str, Any]] = dict()
    devices_config: Dict[str, Dict[str, Any]] = dict()

    for conf in domain_config:
        if CONF_USERNAME in conf:
            config_key = CONF_USERNAME
            destination = accounts_config
        else:
            config_key = CONF_DEVICE_ID
            destination = devices_config

        identifier = conf[config_key]
        logging_key = (config_key, identifier)

        existing_entry = _find_existing_entry(hass, config_key, identifier)
        if existing_entry is not None:
            if existing_entry.source == config_entries.SOURCE_IMPORT:
                destination[identifier] = conf
                _LOGGER.debug('Not creating new entry for %s "%s" because it already exists' % logging_key)
            else:
                _LOGGER.warning('Configuration for %s "%s" is overridden by another config entry' % logging_key)
            continue

        destination[identifier] = conf
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                handler=DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=conf
            )
        )

    if accounts_config:
        hass.data[DATA_ACCOUNTS_CONFIG] = accounts_config
    if devices_config:
        hass.data[DATA_DEVICES_CONFIG] = devices_config

    return True


async def _connector_routine(hass: HomeAssistantType,
                             connector: Union['DirectConnector', 'CloudConnector'],
                             logger: 'logging.Logger') -> None:
    _LOGGER.debug("Starting listener on connector: %s" % (connector,))
    async for response in connector.processed_response_listener(
        close_on_exit=True,
        ignore_unknown_devices=True,
        logger=logger,
    ):
        if response.state == DeviceResponseState.SUCCESS:
            if response.device:
                device_id = response.device.device_id
                if response.command is not None:
                    command_id = response.command.command_id
                    device_entities: Optional[List['HekrEntity']] = hass.data[DATA_DEVICE_ENTITIES].get(device_id)
                    if device_entities:
                        protocol = SUPPORTED_PROTOCOLS[get_supported_id_by_definition(response.device.protocol)]
                        filtered_attributes = protocol.attribute_filter(response)

                        updated_entity_ids = []
                        for entity in device_entities:
                            if entity.entity_config.cmd_receive.command_id == command_id:
                                updated_entity_ids.append(entity.entity_id)
                                entity.handle_data_update(filtered_attributes)

                        if updated_entity_ids:
                            logger.debug("Found entities matching receive command ID '%d': %s"
                                         % (command_id, ', '.join(updated_entity_ids)))


async def connector_listener(hass: HomeAssistantType, connector: Union['DirectConnector', 'CloudConnector']) -> None:
    from hekrapi.connector import DirectConnector
    postfix = ('direct' if isinstance(connector, DirectConnector) else 'cloud') + '.' + connector.host
    logger = logging.getLogger(__name__ + '.' + postfix)
    try:
        while True:
            try:
                await _connector_routine(hass, connector, logger)
            except ConnectorError as e:
                logger.error("Error occurred (delaying 5 seconds to restart): %s" % (e, ))
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        logger.debug("Stopping listener gracefully")
    except BaseException as e:
        logger.exception("Error: %s" % (e, ))
        raise


@bind_hass
async def device_updater(hass: HomeAssistantType, device: 'Device', spread_interval: Optional['timedelta'] = None):
    device_id = device.device_id

    connector = device.direct_connector if device.cloud_connector is None else device.cloud_connector

    if not connector.is_connected:
        _LOGGER.warning("Connector closed, updater not running")
        return

    logger = logging.getLogger(__name__ + '.updater.' + device_id)

    device_entities: Optional[List['HekrEntity']] = hass.data[DATA_DEVICE_ENTITIES].get(device_id)
    if not device_entities:
        _LOGGER.debug("No entities for device with ID '%s' available yet")
        return

    run_commands: List['CommandCall'] = list()
    for entity in device_entities:
        if not entity.enabled:
            continue
        update_command = entity.entity_config.cmd_update
        if update_command not in run_commands:
            run_commands.append(update_command)

    if not run_commands:
        logger.debug('Not running updater without enabled entities')
        return

    log_format = "[%d/%d] Command ID %d, arguments: %s"
    counter = 1
    first_command = run_commands.pop()
    logger.debug(log_format % (counter, len(run_commands)+1, first_command.command_id, first_command.arguments))
    await device.command(first_command.command_id, first_command.arguments, with_read=False)

    if run_commands:
        delay_between = 2 if spread_interval is None else spread_interval.total_seconds() / len(run_commands)
        _LOGGER.debug("Will run commands on device with ID '%s' (delay between each command: %d seconds)"
                      % (device_id, delay_between))

        while run_commands:
            await asyncio.sleep(delay_between)
            next_command = run_commands.pop()
            counter += 1
            _LOGGER.debug(log_format % (counter, len(run_commands)+1, next_command.command_id, next_command.arguments))
            await device.command(next_command.command_id, next_command.arguments, with_read=False)


@callback
@bind_hass
def create_device_updater(hass: HomeAssistantType, device: 'Device', scan_interval: 'timedelta') -> CancellationCall:
    _LOGGER.debug("Creating updater for device with ID '%s' (interval: %s seconds)"
                  % (device.device_id, scan_interval))

    async def wrapper(*_):
        await device_updater(hass, device, scan_interval)

    return async_track_time_interval(hass, wrapper, scan_interval)


@callback
@bind_hass
def get_config_helper(hass: HomeAssistantType,
                      config_entry: config_entries.ConfigEntry) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Get full configuration for config entry"""
    conf = config_entry.data
    if CONF_DEVICE_ID in conf:
        setup_type = DATA_DEVICES_CONFIG
        id_attr = CONF_DEVICE_ID
    else:
        setup_type = DATA_ACCOUNTS_CONFIG
        id_attr = CONF_USERNAME
    identifier = conf[id_attr]

    if config_entry.source == config_entries.SOURCE_IMPORT:
        import_config = hass.data.get(setup_type, {}).get(identifier)
        if import_config is None:
            return id_attr, None
        return id_attr, {**import_config}
    return id_attr, VALIDATE_SCHEMA(conf)


@bind_hass
async def async_setup_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry) -> bool:
    """Config entry setup"""
    try:
        id_attr, conf = get_config_helper(hass, config_entry)
    except vol.Invalid as e:
        _LOGGER.error('Configuration entry %s could not be set up due to validation error: %s'
                      % (config_entry.entry_id, e))
        return False

    if config_entry.source == config_entries.SOURCE_IMPORT and conf is None:
        _LOGGER.info('Removing config entry %s after removing from YAML configuration'
                     % config_entry.entry_id)
        hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))
        return False

    _LOGGER.debug('Setting up entry %s for %s "%s"' % (config_entry.entry_id, id_attr, conf[id_attr]))

    setup_method = async_setup_device if id_attr == CONF_DEVICE_ID else async_setup_account
    result = await setup_method(hass, conf)

    if result is None:
        _LOGGER.debug("Failed to configure entry '%s'" % (config_entry.entry_id, ))
        return False

    _LOGGER.debug("Config entry '%s' set up successfully, forwarding entry setup" % (config_entry.entry_id, ))
    for domain in result:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry=config_entry,
                domain=domain
            )
        )

    return True


@bind_hass
async def async_setup_device(hass: HomeAssistantType, config: ConfigType) -> Union[bool, Set[str]]:
    """Device setup routine"""
    devices_data = hass.data[DATA_DEVICES]
    device_id = config[CONF_DEVICE_ID]

    if device_id in devices_data:
        _LOGGER.warning("Attempted to add device with ID '%s' multiple times" % (device_id, ))
        return False

    from hekrapi.device import Device

    protocol_id = config[CONF_PROTOCOL]
    supported_protocol = SUPPORTED_PROTOCOLS[protocol_id]
    device_protocol = supported_protocol.definition

    device = Device(
        device_id=device_id,
        control_key=config.get(CONF_CONTROL_KEY),
        protocol=device_protocol
    )
    direct_connector = device.protocol.create_direct_connector(
        host=config[CONF_HOST],
        port=config.get(CONF_PORT),
    )
    device.direct_connector = direct_connector

    try:
        await direct_connector.open_connection()
        await direct_connector.authenticate()

        listener_task = hass.loop.create_task(connector_listener(hass, direct_connector))
        hass.data[DATA_DEVICE_LISTENERS][device_id] = listener_task

        updater_cancel = create_device_updater(hass, device, config[CONF_SCAN_INTERVAL])
        hass.data[DATA_UPDATERS][device_id] = updater_cancel

        devices_data[device_id] = device
        return supported_protocol.get_supported_domains()

    except ConnectionRefusedError:
        _LOGGER.error('Direct connection refused to device with ID %s at host %s, port %d'
                      % (device_id, direct_connector.host, direct_connector.port))
    except ConnectorAuthenticationError:
        _LOGGER.error('Could not authenticate direct connection to device with ID %s'
                      % (device_id,))
    except ConnectionError:
        raise ConfigEntryNotReady('Direct connection to device with ID %s could not be established'
                                  % (device_id,))


@bind_hass
async def async_setup_account(hass: HomeAssistantType, config: ConfigType) -> Optional[Set[str]]:
    """Account setup routine"""
    username = config[CONF_USERNAME]

    if username in hass.data[DATA_ACCOUNTS]:
        _LOGGER.warning("Attempted to add account with username '%s' multiple times" % (username, ))
        return

    from hekrapi.account import Account

    all_required_domains: Set[str] = set()

    account = Account(
        username=username,
        password=config[CONF_PASSWORD],
        timeout=config[CONF_TIMEOUT]
    )

    try:
        await account.authenticate()
        devices_info = await account.get_devices_info()

    except AccountException as e:
        _LOGGER.error("Error: %s" % (e, ))
        raise ConfigEntryNotReady

    try:

        if not devices_info:
            _LOGGER.warning('Account with username %s contains no devices, disabling config entry until restart'
                            % (username, ))
            return

        data_devices = hass.data[DATA_DEVICES]
        account_devices_config: Dict[DeviceID, Dict[str, Any]] = config.get(CONF_DEVICES, {})

        create_devices_info = []
        for device_info in devices_info:
            device_id = device_info.device_id

            existing_device: Optional['Device'] = data_devices.get(device_id)
            if existing_device is not None:
                _LOGGER.info("Encountered device with ID '%s' that has already been set up by a different config entry"
                             % device_id)
            elif account_devices_config.get(device_id) is False:
                _LOGGER.info("Excluded device with ID '%s' from adding per configuration"
                             % device_id)
            else:
                create_devices_info.append(device_info)

        if not create_devices_info:
            _LOGGER.info("No supported/enabled devices found for account with username '%s'"
                         % (username, ))
            return

        definitions_by_id = {
            protocol_id: protocol.definition
            for protocol_id, protocol in SUPPORTED_PROTOCOLS.items()
        }

        new_devices = account.create_devices_from_info(
            create_devices_info,
            protocols=definitions_by_id.values(),
            only_detected=True
        )

        if not new_devices:
            _LOGGER.warning("Could not detect any supported devices in account with username '%s'"
                            % (username, ))
            return

        elif len(new_devices) != len(create_devices_info):
            # Warning: Some devices have not been added, therefore warn user
            unsupported_device_ids = set([
                device_info.device_id
                for device_info in create_devices_info
            ]) - set([
                device.device_id
                for device in new_devices
            ])
            _LOGGER.warning("Some devices in account with username '%s' were not added because they are unsupported. "
                            "Their device IDs are: %s" % (username, ', '.join(unsupported_device_ids)))

        for_listeners = []
        for addr, connector in account.connectors.items():
            try:
                await connector.open_connection()
                await connector.authenticate()
                for_listeners.append(connector)
            except HekrAPIException as e:
                _LOGGER.exception("Exception when initializing connector '%s': %s"
                                  % (connector, e))
                for for_close in account.connectors.values():
                    await for_close.close_connection()
                raise ConfigEntryNotReady()

        hass.data[DATA_ACCOUNTS][username] = account
        hass.data[DATA_ACCOUNT_LISTENERS][username] = [
            hass.loop.create_task(connector_listener(hass, connector))
            for connector in for_listeners
        ]

        data_updaters = hass.data[DATA_UPDATERS]
        for device in new_devices:
            device_id = device.device_id

            supported_protocol = SUPPORTED_PROTOCOLS[get_supported_id_by_definition(device.protocol)]
            all_required_domains.update(supported_protocol.get_supported_domains())
            data_devices[device_id] = device

            scan_interval = account_devices_config.get(device_id, {}).get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            updater_task = create_device_updater(hass, device, scan_interval)
            data_updaters[device_id] = updater_task

        return all_required_domains

    except BaseException as e:
        _LOGGER.exception('Caught error while setting up account: %s' % e)
        raise ConfigEntryNotReady


@bind_hass
async def async_unload_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry):
    id_attr, conf = get_config_helper(hass, config_entry)

    unload_method = async_unload_device if id_attr == CONF_DEVICE_ID else async_unload_account
    unload_domains = await unload_method(hass, conf[id_attr])

    if unload_domains is None:
        return False

    tasks = []
    for domain in unload_domains:
        tasks.append(hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(
                entry=config_entry,
                domain=domain
            )
        ))

    if tasks:
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    _LOGGER.debug("Successfully unloaded entry ID '%s'" % (config_entry.entry_id, ))

    return True


@bind_hass
async def async_unload_device(hass: HomeAssistantType, device_id: DeviceID) -> Optional[Set[str]]:
    """Unload device object and related data"""
    device: Optional['Device'] = hass.data[DATA_DEVICES].pop(device_id, None)
    if device is None:
        _LOGGER.warning("Did not find device with ID '%s'" % (device_id, ))
        return

    updater: 'asyncio.Task' = hass.data[DATA_UPDATERS].pop(device_id)
    updater.cancel()

    listener: Optional['asyncio.Task'] = hass.data[DATA_DEVICE_LISTENERS].pop(device_id, None)
    if listener is not None:
        listener.cancel()

    _LOGGER.debug("Successfully unloaded device with ID '%s'" % (device_id, ))

    return SUPPORTED_PROTOCOLS[get_supported_id_by_definition(device.protocol)].get_supported_domains()


@bind_hass
async def async_unload_account(hass: HomeAssistantType, username: str) -> Union[bool, Set[str]]:
    """Unload account object and related data"""
    account: Optional['Account'] = hass.data[DATA_ACCOUNTS].pop(username, None)
    if account is None:
        _LOGGER.warning("Did not found account with username '%s'" % (username, ))
        return False

    # Cancel active listeners
    listeners: List['asyncio.Task'] = hass.data[DATA_ACCOUNT_LISTENERS].pop(username)
    for listener in listeners:
        listener.cancel()

    # Unload devices for account
    required_domains_for_unload = set()
    tasks = {device_id: async_unload_device(hass, device_id) for device_id in account.devices.keys()}
    if tasks:
        # Gather list of sets of supported entity domains
        unload_results = await asyncio.gather(*tasks.values())
        for device_id, domains in zip(tasks.keys(), unload_results):
            if domains is None:
                _LOGGER.warning("Failed to unload device with ID '%s'" % (device_id, ))
            else:
                # Extend set of loaded entity domains
                required_domains_for_unload.update(domains)
    else:
        _LOGGER.info("No entities to unload for account with username '%s'" % (username, ))

    _LOGGER.debug("Successfully unloaded account with username '%s'" % (username, ))
    return required_domains_for_unload
