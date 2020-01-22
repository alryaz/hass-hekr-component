"""Support for Hekr sensors."""
import logging
from collections import OrderedDict
from datetime import timedelta
from typing import Optional, TYPE_CHECKING, Dict, Any, Union, List, Type

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.binary_sensor.device_condition import DEVICE_CLASS_NONE
from homeassistant.components.sensor import PLATFORM_SCHEMA, DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import (
    STATE_UNKNOWN, STATE_OK, CONF_PROTOCOL,
    CONF_NAME, ATTR_NAME, ATTR_ICON, ATTR_STATE, ATTR_UNIT_OF_MEASUREMENT, CONF_SCAN_INTERVAL,
    ATTR_DEVICE_CLASS, CONF_HOST, CONF_DEVICE_ID)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

from . import HekrData
from .const import DOMAIN, PROTOCOL_DEFAULT, PROTOCOL_CMD_UPDATE, ATTR_MONITORED, \
    DEFAULT_SCAN_INTERVAL, PROTOCOL_CMD_RECEIVE, CONF_DEVICE, CONF_ACCOUNT, CONF_DOMAINS, DEFAULT_NAME_DEVICE, \
    PROTOCOL_NAME
from .schemas import BASE_PLATFORM_SCHEMA, exclusive_auth_methods, test_for_list_correspondence
from .supported_protocols import SUPPORTED_PROTOCOLS

if TYPE_CHECKING:
    from hekrapi import Device

_LOGGER = logging.getLogger(__name__)


class HekrEntity(Entity):
    def __init__(self, device_id: str, ent_type: str, name: str, config: Dict, update_interval: timedelta):
        super().__init__()
        _LOGGER.debug('Creating %s entity for device with ID "%s"' % (self.__class__.__name__, device_id))
        self._device_id = device_id
        self._ent_type = ent_type
        self._name = name
        self._config = config
        self._update_interval = update_interval

        self._attributes = None
        self._available = False
        self._state = STATE_UNKNOWN

    def __hash__(self):
        return hash(self.unique_id)

    async def async_added_to_hass(self) -> None:
        _LOGGER.debug('Entity %s added to HASS! Setting up callbacks.' % self)
        HekrData.get_instance(self.hass).add_entities_for_update(
            device=self._device_id,
            entities=self,
            update_interval=self._update_interval
        )

    @classmethod
    def create_entities(cls: Type['HekrEntity'], device_id: str, name: str, types: Union[str, List[str]],
                        configs: Dict[str, dict], update_interval: timedelta):
        if types is False:
            return None
        if not types:
            types = [ent_type for ent_type, config in configs.items() if config.get(PROTOCOL_DEFAULT) is True]
        else:
            all_types = [ent_type for ent_type, config in configs.items()]
            if types is True:
                types = all_types
            else:
                # check types
                types = set(types)
                invalid_types = types - set(all_types)
                if invalid_types:
                    raise ValueError('Invalid sensor types: %s' % ', '.join(invalid_types))

        _LOGGER.debug('Create "%s" entities for device ID "%s" with name "%s" from configs: %s'
                      % ('", "'.join(types), device_id, name, configs))

        return [cls(
            device_id=device_id,
            name=name + ' ' + configs[ent_type].get(ATTR_NAME, ent_type),
            ent_type=ent_type,
            config=configs[ent_type],
            update_interval=update_interval,
        ) for ent_type in types]

    async def handle_data_update(self, data):
        _LOGGER.debug('Handling data update for %s entity [%s] with data: %s' % (
            self.__class__.__name__,
            self.entity_id,
            data,
        ))

        state_key = self._config.get(ATTR_STATE)
        self._state = data[state_key] if state_key else STATE_OK

        additional_keys = self._config.get(ATTR_MONITORED)
        if additional_keys is True:
            attributes = OrderedDict()
            for attribute in data:
                if state_key is None or attribute != state_key:
                    attributes[attribute] = data[attribute]
            self._attributes = attributes

        elif additional_keys is not None:
            attributes = OrderedDict()
            for attribute in sorted(additional_keys):
                attributes[attribute] = data.get(attribute)
            self._attributes = attributes

        else:
            self._attributes = None

        self._available = True

        await self.async_update_ha_state()

    def _get_hekr_device(self) -> 'Device':
        return self.hass.data[DOMAIN].get_device(self._device_id)

    def _exec_command(self, command, arguments: Optional[dict] = None):
        from asyncio import run_coroutine_threadsafe
        return run_coroutine_threadsafe(self._get_hekr_device().command(command, arguments), self.hass.loop).result()

    def _exec_protocol_command(self, protocol_command):
        command = self._config.get(protocol_command)
        if command is not None:
            arguments = None
            if isinstance(command, tuple):
                command, arguments = command
            return self._exec_command(command, arguments)
        return False

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def icon(self) -> str:
        return self._config.get(ATTR_ICON)

    @property
    def name(self) -> str:
        """Return the display name of this entity."""
        return self._name

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._config.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def device_state_attributes(self) -> Optional[dict]:
        return self._attributes

    @property
    def unique_id(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def command_update(self) -> str:
        return self._config.get(PROTOCOL_CMD_UPDATE)

    @property
    def command_receive(self) -> str:
        command_receive = self._config.get(PROTOCOL_CMD_RECEIVE)
        if command_receive is None:
            return self.command_update
        return command_receive

    @property
    def device_class(self) -> Optional[str]:
        return self._config.get(ATTR_DEVICE_CLASS, DEVICE_CLASS_NONE)

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return {"identifiers": {(DOMAIN, self._device_id)}}


async def _setup_entity(logger: logging.Logger, hass: HomeAssistantType, async_add_entities, config: ConfigType,
                        protocol_key: str, config_key: str, entity_domain: str,
                        entity_factory: Type['HekrEntity']):
    protocol_id = config.get(CONF_PROTOCOL)
    protocol = SUPPORTED_PROTOCOLS[protocol_id]

    if protocol_key is not None and protocol_key not in protocol:
        logger.error('Protocol "%s" does not support "%s" component, and therefore cannot be set up.'
                     % (entity_domain, protocol_id))
        return False

    hekr_data = HekrData.get_instance(hass)
    device = hekr_data.get_add_device(config)

    try:
        entities = entity_factory.create_entities(
            device_id=device.device_id,
            name=config.get(CONF_NAME),
            types=config.get(config_key),
            configs=protocol[protocol_key],
            update_interval=config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        if entities is None:
            logger.warning('No entities added for device with ID "%s"' % device.device_id)
            return False
        _LOGGER.debug('Prepared entities: %s' % ', '.join([entity.name for entity in entities]))

        async_add_entities(entities)
        logger.debug('Adding %s(-s) complete on device with ID "%s"' % (entity_domain, device.device_id))

    except ValueError as e:
        __name__.split('.')[-1].capitalize()
        logger.exception('%s configuration failed: %s' % (entity_domain.capitalize(), e))
        return False

    return True


def create_platform_basics(logger: logging.Logger, entity_domain: str, entity_factory: Type['HekrEntity'],
                           base_schema: vol.Schema):
    if entity_factory is None:
        entity_factory = HekrEntity

    config_key = None
    protocol_key = None
    for conf_key, (ent_domain, proto_key) in CONF_DOMAINS.items():
        if ent_domain == entity_domain:
            config_key = conf_key
            protocol_key = proto_key
            break

    if config_key is None:
        raise ValueError('Entity domain "%s" is not supported for [%s] domain.' % (entity_domain, DOMAIN))

    async def _async_setup_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry, async_add_devices):
        conf = config_entry.data
        config_type = CONF_DEVICE if CONF_DEVICE in conf else CONF_ACCOUNT
        item_config = conf[config_type]

        if config_type == CONF_DEVICE:
            return await _setup_entity(
                logger=logger,
                hass=hass,
                async_add_entities=async_add_devices,
                config=item_config,
                config_key=config_key,
                protocol_key=protocol_key,
                entity_domain=entity_domain,
                entity_factory=entity_factory
            )

        return False

    async def _async_setup_platform(hass: HomeAssistantType, config: ConfigType, async_add_entities, *_):
        if config.get(CONF_NAME) is None:
            protocol = SUPPORTED_PROTOCOLS[config[CONF_PROTOCOL]]
            config[CONF_NAME] = DEFAULT_NAME_DEVICE.format(
                protocol_name=protocol.get(PROTOCOL_NAME),
                host=config.get(CONF_HOST),
                device_id=config.get(CONF_DEVICE_ID),
            )
        return await _setup_entity(
            logger=logger,
            hass=hass,
            async_add_entities=async_add_entities,
            config=config,
            config_key=config_key,
            protocol_key=protocol_key,
            entity_domain=entity_domain,
            entity_factory=entity_factory
        )

    _PLATFORM_SCHEMA = vol.All(
        base_schema.extend(BASE_PLATFORM_SCHEMA),
        exclusive_auth_methods,
        test_for_list_correspondence(config_key, protocol_key)
    )

    return _PLATFORM_SCHEMA, _async_setup_platform, _async_setup_entry


class HekrSensor(HekrEntity):
    @property
    def unique_id(self) -> Optional[str]:
        return '_'.join((self._device_id, PLATFORM_DOMAIN, self._ent_type))


PLATFORM_SCHEMA, async_setup_platform, async_setup_entry = create_platform_basics(
    logger=_LOGGER,
    entity_domain=PLATFORM_DOMAIN,
    entity_factory=HekrSensor,
    base_schema=PLATFORM_SCHEMA
)
