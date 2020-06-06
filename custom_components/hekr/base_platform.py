"""Base code to generate other platforms."""

__all__ = [
    'HekrEntity',
    'create_platform_basics',
]

import asyncio
from collections import OrderedDict
from datetime import timedelta
from typing import Optional, TYPE_CHECKING, Dict, Any, Union, List, Type

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.binary_sensor.device_condition import DEVICE_CLASS_NONE
from homeassistant.const import (
    STATE_UNKNOWN, STATE_OK, CONF_PROTOCOL,
    CONF_NAME, ATTR_NAME, ATTR_ICON, ATTR_STATE, ATTR_UNIT_OF_MEASUREMENT, CONF_SCAN_INTERVAL,
    ATTR_DEVICE_CLASS, CONF_DEVICE_ID, CONF_USERNAME, CONF_PLATFORM)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

from . import _LOGGER
from .const import DOMAIN, PROTOCOL_DEFAULT, PROTOCOL_CMD_UPDATE, ATTR_MONITORED, \
    DEFAULT_SCAN_INTERVAL, PROTOCOL_CMD_RECEIVE, CONF_DEVICE, CONF_ACCOUNT, CONF_DOMAINS
from .schemas import BASE_PLATFORM_SCHEMA, test_for_list_correspondence
from .supported_protocols import SUPPORTED_PROTOCOLS

if TYPE_CHECKING:
    from .hekr_data import HekrData
    from hekrapi import MessageID, CommandData, logging


class HekrEntity(Entity):
    def __init__(self, device_id: str, ent_type: str, name: str, config: Dict, update_interval: timedelta,
                 init_enable: bool):
        super().__init__()
        _LOGGER.debug('Creating %s[%s] entity for device with ID "%s"' % (self.__class__.__name__, ent_type, device_id))
        self._device_id = device_id
        self._ent_type = ent_type
        self._name = name
        self._config = config
        self._update_interval = update_interval
        self._init_enable = init_enable

        self._attributes = None
        self._available = False
        self._state = STATE_UNKNOWN

    def __hash__(self):
        return hash(self.unique_id)

    @property
    def _data(self) -> 'HekrData':
        return self.hass.data[DOMAIN]

    async def async_added_to_hass(self) -> None:
        _LOGGER.debug('Entity %s added to HASS! Setting up callbacks.' % self)
        device_entities = self._data.device_entities.setdefault(self._device_id, [])
        device_entities.append(self)
        self._data.refresh_connections()

    async def async_will_remove_from_hass(self) -> None:
        _LOGGER.debug('Entity %s removed from HomeAssistant' % self)
        device_entities = self._data.device_entities.get(self._device_id)
        if device_entities:
            device_entities.remove(self)
            self._data.refresh_connections()

    @classmethod
    def create_entities(cls: Type['HekrEntity'], device_id: str, name: str,
                        types: Optional[Union[bool, str, List[str]]],
                        configs: Dict[str, dict], update_interval: timedelta):
        if types is True:
            init_enable = dict.fromkeys(configs.keys(), True)
        else:
            init_enable = dict.fromkeys(configs.keys(), False)
            if types is not False:
                if not types:
                    # empty types `str`/`list` or `None` is provided, therefore everything default should be added
                    enabled_types = [
                        ent_type
                        for ent_type, config in configs.items()
                        if config.get(PROTOCOL_DEFAULT) is True
                    ]
                else:
                    if isinstance(types, str):
                        # convert single type definition to list
                        types = [types]
                    # check types
                    enabled_types = set(types)
                    invalid_types = enabled_types - init_enable.keys()

                    if invalid_types:
                        raise ValueError('Invalid sensor types: %s' % ', '.join(invalid_types))

                init_enable.update(dict.fromkeys(enabled_types, True))

        _LOGGER.debug('Create entities for device ID "%s" with name "%s" with initial states: %s'
                      % (device_id, name, init_enable))

        return [cls(
            device_id=device_id,
            name=name + ' ' + configs[ent_type].get(ATTR_NAME, ent_type),
            ent_type=ent_type,
            config=configs[ent_type],
            update_interval=update_interval,
            init_enable=enabled
        ) for ent_type, enabled in init_enable.items()]

    async def handle_data_update(self, data: 'CommandData') -> None:
        """
        Handle data updates for the entity.
        Updates are handled by generated updaters via HekrData class. The :func:`HekrEntity.handle_data_update` method
        handles incoming data response
        :param data: Incoming data dictionary
        :type data: Dict[str, Any]
        """
        _LOGGER.debug('Handling data update for %s entity [%s] with data: %s' % (
            self.__class__.__name__,
            self.entity_id,
            data,
        ))

        state_key = self._config.get(ATTR_STATE)
        if state_key:
            if state_key in data:
                state = data[state_key]
            else:
                _LOGGER.error('State "%s" for entity type "%s" not found in received data (%s)!'
                              % (state_key, self._ent_type, data))
                state = STATE_UNKNOWN
        else:
            state = STATE_OK

        additional_keys = self._config.get(ATTR_MONITORED)
        attributes = None
        if additional_keys is True:
            attributes = OrderedDict()
            for attribute in sorted(data):
                if state_key is None or attribute != state_key:
                    attributes[attribute] = data[attribute]

        elif additional_keys is not None:
            attributes = OrderedDict()
            for attribute in sorted(additional_keys):
                if attribute in data:
                    attributes[attribute] = data[attribute]
                else:
                    _LOGGER.warning('Attribute "%s" for entity type "%s" not found in received data (%s)!'
                                    % (attribute, self._ent_type, data))
                    attributes[attribute] = STATE_UNKNOWN

        if attributes != self._attributes or state != self._state or not self._available:
            self._available = True
            self._state = state
            self._attributes = attributes
            await self.async_update_ha_state(force_refresh=True)

    def execute_protocol_command(self, protocol_command: Union[str, 'CommandData']) -> Union[bool, 'MessageID']:
        command = self._config.get(protocol_command)
        if command is not None:
            arguments = None
            if isinstance(command, tuple):
                command, arguments = command

            return asyncio.run_coroutine_threadsafe(
                self._data.devices[self._device_id].command(command, arguments),
                self.hass.loop
            ).result()
        else:
            _LOGGER.error('%s attempted to execute unknown protocol command: %s' % (self, protocol_command))
            return False

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
        icon = self._config.get(ATTR_ICON)
        if isinstance(icon, dict):
            return icon.get(self._state, icon.get(PROTOCOL_DEFAULT))
        return icon

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
        return self._data.get_device_info_dict(self._device_id)

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._init_enable


async def _setup_entity(logger: 'logging.Logger', hass: HomeAssistantType, async_add_entities, config: ConfigType,
                        protocol_key: str, config_key: str, entity_domain: str,
                        entity_factory: Type['HekrEntity']):
    from hekrapi import HekrAPIException

    protocol_id = config.get(CONF_PROTOCOL)
    protocol = SUPPORTED_PROTOCOLS[protocol_id]

    if protocol_key is not None and protocol_key not in protocol:
        logger.error('Protocol "%s" does not support [%s] component, and therefore cannot be set up.'
                     % (entity_domain, protocol_id))
        return False

    try:
        device_id = config[CONF_DEVICE_ID]

        hekr_data: 'HekrData' = hass.data[DOMAIN]
        device = hekr_data.devices[device_id]

        update_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if isinstance(update_interval, int):
            update_interval = timedelta(seconds=update_interval)

        entities = entity_factory.create_entities(
            device_id=device_id,
            name=config[CONF_NAME],
            types=config.get(config_key),
            configs=protocol[protocol_key],
            update_interval=update_interval,
        )

        if entities is None:
            logger.warning('No entities added for device with ID "%s"' % device.device_id)
            return False

        _LOGGER.debug('Prepared entities: %s' % ', '.join([entity.name for entity in entities]))

        async_add_entities(entities)
        logger.debug('Adding %s(-s) complete on device with ID "%s"' % (entity_domain, device.device_id))

        return True

    except HekrAPIException as e:
        logger.exception('%s configuration failed due to API error: %s' % (entity_domain.capitalize(), e))
    except ValueError as e:
        logger.exception('%s configuration failed: %s' % (entity_domain.capitalize(), e))

    return False


def create_platform_basics(logger: 'logging.Logger', entity_domain: str, entity_factory: Type['HekrEntity'],
                           base_schema: vol.Schema):
    if entity_factory is None:
        entity_factory = HekrEntity

    config_key = None
    protocol_key = None
    for conf_key, (ent_domain, protocol_key) in CONF_DOMAINS.items():
        if ent_domain == entity_domain:
            config_key = conf_key
            protocol_key = protocol_key
            break

    if config_key is None:
        raise ValueError('Entity domain "%s" is not supported for [%s] domain.' % (entity_domain, DOMAIN))

    async def _async_setup_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry, async_add_devices):
        conf = config_entry.data
        config_type = CONF_DEVICE if CONF_DEVICE in conf else CONF_ACCOUNT
        hekr_data: 'HekrData' = hass.data[DOMAIN]
        item_config = conf[config_type]

        if config_type == CONF_DEVICE:
            device_id = item_config[CONF_DEVICE_ID]
            device_cfg = hekr_data.devices_config_entries[device_id]
            _LOGGER.debug('Adding local device %s with config: %s' % (device_id, device_cfg))
            return await _setup_entity(
                logger=logger,
                hass=hass,
                async_add_entities=async_add_devices,
                config=device_cfg,
                config_key=config_key,
                protocol_key=protocol_key,
                entity_domain=entity_domain,
                entity_factory=entity_factory
            )

        elif config_type == CONF_ACCOUNT:
            account_id = item_config[CONF_USERNAME]

            tasks = []
            for device_id, device in hekr_data.get_account_devices(account_id).items():
                device_cfg = hekr_data.devices_config_entries[device_id]
                _LOGGER.debug('Adding device %s for account %s with config: %s' % (device_id, account_id, device_cfg))
                tasks.append(
                    _setup_entity(
                        logger=logger,
                        hass=hass,
                        async_add_entities=async_add_devices,
                        config=device_cfg,
                        config_key=config_key,
                        protocol_key=protocol_key,
                        entity_domain=entity_domain,
                        entity_factory=entity_factory
                    )
                )

            return all(await asyncio.wait(tasks))

        return False

    async def _async_setup_platform(hass: HomeAssistantType, config: ConfigType, *_, **__):
        _LOGGER.error('Platform setup is deprecated! Please, convert your configuration to use component instead of '
                      'platform. A persistent notification will be created with config for your particular device.')

        del config[CONF_PLATFORM]

        from homeassistant.components.persistent_notification import DOMAIN, SERVICE_CREATE, ATTR_TITLE, ATTR_MESSAGE

        def timedelta_str(td: timedelta, offset: str) -> str:
            hours = td.seconds // 3600
            minutes = (td.seconds % 3600) // 60
            seconds = td.seconds % 60

            return offset + ('\n'+offset).join([
                "%s: %s" % replace
                for replace in {
                    "seconds": seconds,
                    "minutes": minutes,
                    "hours": hours,
                    "days": td.days
                }.items()
                if replace[1] != 0
            ])

        conversion_content = '```\nhekr:\n  devices:\n    - '
        default_values = {
            k: k.default()
            for k in BASE_PLATFORM_SCHEMA.keys()
            if not isinstance(k.default, vol.schema_builder.Undefined)
        }
        conversion_content += '\n      '.join([
            '%s: %s' % (k, '\n' + timedelta_str(v, ' '*8) if isinstance(v, timedelta) else v)
            for k, v in config.items()
            if default_values.get(k) != v
        ])
        conversion_content += '\n```'

        hass.async_create_task(
            hass.services.async_call(DOMAIN, SERVICE_CREATE, {
                ATTR_TITLE: 'Hekr device %s' % config[CONF_DEVICE_ID],
                ATTR_MESSAGE: 'Setting up Hekr devices using platforms is no longer supported. Consider switching to '
                              'an integration setup via interface or YAML. To port your platform configuration to the '
                              'new format, an entry has been provided for you to copy:\n' + conversion_content
            })
        )
        return False

    _PLATFORM_SCHEMA = vol.All(
        base_schema.extend(BASE_PLATFORM_SCHEMA),
        test_for_list_correspondence(config_key, protocol_key)
    )

    return _PLATFORM_SCHEMA, _async_setup_platform, _async_setup_entry
