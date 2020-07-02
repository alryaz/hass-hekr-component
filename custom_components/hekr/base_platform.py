"""Base code to generate other platforms."""

__all__ = [
    'HekrEntity',
    'base_async_setup_entry',
    'base_async_setup_platform',
]

import logging
from asyncio import run_coroutine_threadsafe
from typing import Optional, TYPE_CHECKING, Dict, Any, Type, Sequence, Callable, Set, List, Mapping

from homeassistant import config_entries
from homeassistant.const import (
    STATE_UNKNOWN, CONF_PROTOCOL,
    CONF_NAME, CONF_DEVICE_ID)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

from . import get_config_helper, DEFAULT_NAME_FORMAT
from .const import DOMAIN, CONF_DEVICES, DATA_DEVICE_ENTITIES, DATA_DEVICES, DATA_ACCOUNTS
from .supported_protocols import (
    SUPPORTED_PROTOCOLS,
    SupportedProtocolType,
    get_supported_id_by_definition,
    CommandCall
)

if TYPE_CHECKING:
    from logging import Logger
    from hekrapi.types import DeviceID
    from .supported_protocols import _EntityConfig, _ToggleConfig
    from hekrapi.account import Account
    from hekrapi.device import Device

HekrEntityType = Type['HekrEntity']
AddEntitiesCallback = Callable[[Sequence['HekrEntity']], Any]

_LOGGER = logging.getLogger(__name__)


def create_entities(entity_domain: str, entity_factory: Type['HekrEntity'],
                    device_id: 'DeviceID', supported_protocol: SupportedProtocolType,
                    base_config: ConfigType, logger: Optional['Logger'] = _LOGGER) -> Optional[List['HekrEntity']]:
    """
    Setup entities for device.
    :param entity_domain: Entity domain
    :param entity_factory: Entity class
    :param device_id: Device ID to set up domain for
    :param supported_protocol: Supported protocol definition
    :param base_config: Entity configuration (compliant with `ENTITY_CONFIG_BASE` schema)
    :param logger: (optional) Output messages to given logger (default: this module's logger)
    """
    configured_types: Optional[Set[str]] = base_config.get(entity_domain)
    available_types = supported_protocol.get_domain_configs(entity_domain)

    if not available_types:
        logger.warning("Protocol '%s' does not support '%s' entity domain" % (supported_protocol.name, entity_domain))
        return

    if configured_types is True:
        # Case: Use all types for entity domain
        enabled_types = dict.fromkeys(available_types.keys(), True)
    else:
        enabled_types = dict.fromkeys(available_types.keys(), False)

        # (configured_types is False) Case: Do not use entity domain
        if configured_types is not False:
            if configured_types is None:
                # Case: Use default types for entity domain
                configured_types = {
                    ent_type
                    for ent_type, ent_config in available_types.items()
                    if ent_config.default is True
                }

            # Case: Use specified types for entity domain
            enabled_types.update(dict.fromkeys(configured_types, True))

    logger.debug('Create entities for device ID "%s" with initial states: %s' % (device_id, enabled_types))

    name_format = base_config.get(CONF_NAME, supported_protocol.name_format or DEFAULT_NAME_FORMAT)
    return [entity_factory(
        device_id=device_id,
        supported_protocol=supported_protocol,
        ent_type=ent_type,
        name_format=name_format,
        init_enable=init_enable,
        entity_domain=entity_domain,
    ) for ent_type, init_enable in enabled_types.items()]


async def base_async_setup_entry(entity_domain: str, entity_factory: HekrEntityType,
                                 hass: HomeAssistantType, config_entry: config_entries.ConfigEntry,
                                 async_add_devices: AddEntitiesCallback,
                                 logger: Optional['Logger'] = _LOGGER) -> bool:
    id_attr, conf = get_config_helper(hass, config_entry)
    identifier = conf[id_attr]

    if id_attr == CONF_DEVICE_ID:
        supported_protocol: SupportedProtocolType = conf[CONF_PROTOCOL]

        new_entities = create_entities(
            entity_domain=entity_domain,
            entity_factory=entity_factory,
            device_id=identifier,
            supported_protocol=supported_protocol,
            base_config=conf,
            logger=logger,
        )
        if new_entities is None:
            return False

        setup_entities = new_entities

    else:
        account: 'Account' = hass.data[DATA_ACCOUNTS][identifier]
        setup_entities: List[HekrEntity] = list()

        for device_id, device in account.devices.items():
            logger.debug("Setting up domain '%s' for device '%s'"
                         % (entity_domain, device_id))
            device_config = conf.get(CONF_DEVICES, {}).get(device_id, {})
            supported_protocol = SUPPORTED_PROTOCOLS[get_supported_id_by_definition(device.protocol)]
            new_entities = create_entities(
                entity_domain=entity_domain,
                entity_factory=entity_factory,
                device_id=device_id,
                supported_protocol=supported_protocol,
                base_config=device_config,
                logger=logger
            )

            if new_entities is None:
                return False

            setup_entities.extend(new_entities)

    logger.debug("Adding new entities under domain '%s': %s" % (entity_domain, ', '.join(map(str, setup_entities))))
    async_add_devices(setup_entities)

    return True


# noinspection PyUnusedLocal
async def base_async_setup_platform(entity_domain: str, entity_factory: HekrEntityType,
                                    hass: HomeAssistantType, config: ConfigType,
                                    async_add_entities: AddEntitiesCallback,
                                    logger: Optional['Logger'] = _LOGGER) -> bool:
    pass


class HekrEntity(Entity):
    def __init__(self,
                 device_id: str,
                 supported_protocol: SupportedProtocolType,
                 ent_type: str,
                 name_format: Optional[str],
                 init_enable: bool,
                 entity_domain: str):
        super().__init__()
        self._device_id = device_id
        self._supported_protocol = supported_protocol
        self._ent_type = ent_type
        self._init_enable = init_enable
        self._name = name_format.format(
            device_id=device_id,
            ent_type=ent_type,
            ent_name=self.entity_config.name,
            proto_name=supported_protocol.name,
        )
        self._entity_domain = entity_domain

        self._attributes = None
        self._available = False
        self._state = STATE_UNKNOWN

    @property
    def hekr_device(self) -> 'Device':
        """Hekr device shortcut getter"""
        return self.hass.data[DATA_DEVICES][self._device_id]

    @property
    def entity_config(self) -> '_EntityConfig':
        """Entity config shortcut getter"""
        return getattr(self._supported_protocol, self._ent_type)

    async def async_added_to_hass(self) -> None:
        """Attach entity to Hekr device entities"""
        _LOGGER.debug("Added entity '%s' for device with ID '%s' to Home Assistant"
                      % (self, self._device_id))
        entities: List[HekrEntity] = self.hass.data[DATA_DEVICE_ENTITIES].setdefault(self._device_id, list())
        entities.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Detach entity from Hekr device entities"""
        _LOGGER.debug("Will remove entity '%s' for device with ID '%s' from Home Assistant"
                      % (self, self._device_id))
        entities: List[HekrEntity] = self.hass.data[DATA_DEVICE_ENTITIES].get(self._device_id)
        if entities is not None and self in entities:
            entities.remove(self)

    def handle_data_update(self, filtered_attributes: Dict[str, Any]) -> None:
        """
        Handle data updates for the entity.
        :param filtered_attributes: Filtered attributes
        """
        state, attributes = self.entity_config.get_state_with_attributes(filtered_attributes)

        should_update = False
        if not self._available:
            self._available = True
            should_update = True

        if attributes != self._attributes or state != self._state:
            self._state = state
            self._attributes = attributes
            should_update = True

        if should_update:
            self.async_schedule_update_ha_state(force_refresh=False)

    def _sync_execute_command(self, command: 'CommandCall'):
        """
        Execute command synchronously from command call definition.
        :param command: Command call definition
        :param with_read: Read after execution
        :return:
        """
        if not isinstance(command, CommandCall):
            raise TypeError

        _LOGGER.debug("Executing protocol command: %s")

        return run_coroutine_threadsafe(
            self.hekr_device.command(
                command=command.command_id,
                arguments=command.arguments,
                with_read=False
            ),
            self.hass.loop
        ).result()

    @property
    def should_poll(self) -> bool:
        """
        Checks whether polling is required for this entity.
        See :func:`HekrEntity.handle_data_update` for more info on updates.
        """
        return False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def icon(self) -> Optional[str]:
        """Return icon for this entity."""
        return self.entity_config.get_icon(self._state)

    @property
    def name(self) -> str:
        """Return the display name of this entity."""
        return self._name

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self.entity_config.unit_of_measurement

    @property
    def device_state_attributes(self) -> Optional[dict]:
        return self._attributes

    @property
    def unique_id(self) -> Optional[str]:
        return '_'.join([self._device_id, self._entity_domain, self._ent_type])

    @property
    def device_class(self) -> Optional[str]:
        """Return device class of this entity."""
        return self.entity_config.device_class

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        device_id = self._device_id
        device: 'Device' = self.hass.data[DATA_DEVICES][device_id]

        protocol_id = get_supported_id_by_definition(device.protocol)
        supported_protocol = SUPPORTED_PROTOCOLS[protocol_id]

        attrs = dict()
        attrs['identifiers'] = {(DOMAIN, device.device_id)}

        d_model = supported_protocol.model or protocol_id
        d_name = supported_protocol.name or device_id
        d_manufacturer = supported_protocol.manufacturer or 'Hekr'

        info = device.device_info
        if info is None:
            # Only happens in direct connections
            attrs['manufacturer'] = d_manufacturer
            attrs['model'] = d_model
            attrs['name'] = d_name
        else:
            attrs['name'] = info.name or d_name
            attrs['sw_version'] = info.firmware_version
            attrs['model'] = d_model if supported_protocol.force_model else (info.product_name or d_model)
            attrs['manufacturer'] = d_manufacturer

        attrs['connections'] = set()

        return attrs

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._init_enable


class HekrToggleEntity(HekrEntity):
    @property
    def entity_config(self) -> '_ToggleConfig':
        """
        Get entity config from supported protocol.
        :return:
        """
        return getattr(self._supported_protocol, self._ent_type)
