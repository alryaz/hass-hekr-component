"""Support for Hekr sensors."""
import asyncio
import logging
from typing import Optional, List, Set

from hekrapi.device import Device, DeviceResponseState
from hekrapi.exceptions import HekrAPIException
from homeassistant.const import (
    STATE_UNKNOWN, ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON, ATTR_NAME,
    CONF_SCAN_INTERVAL, STATE_OK, CONF_SENSORS
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .shared import (DOMAIN,
                     CONF_DEVICE_ID, CONF_PROTOCOL, CONF_CONTROL_KEY, CONF_APPLICATION_ID, CONF_HOST, CONF_PORT,
                     CONF_NAME, CONF_DEFAULT_SENSORS,
                     ATTR_MONITORED_ATTRIBUTES, ATTR_STATE_ATTRIBUTE, CONF_UPDATE_COMMANDS,
                     SENSOR_PLATFORM_SCHEMA, CONF_FUNC_FILTER_ATTRIBUTES,
                     CONF_PROTOCOL_DEFINITION)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up platform."""

    protocol = config.get(CONF_PROTOCOL)
    device_id = config.get(CONF_DEVICE_ID)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    sensors = config.get(CONF_SENSORS, protocol.get(CONF_DEFAULT_SENSORS, list(protocol[CONF_SENSORS].keys())))
    sensors = sensors if isinstance(sensors, list) else [sensors]

    try:
        hekr_device = Device(
            device_id=device_id,
            control_key=config.get(CONF_CONTROL_KEY),
            application_id=config.get(CONF_APPLICATION_ID),
            host=host,
            port=port,
            protocol=protocol[CONF_PROTOCOL_DEFINITION]
        )

        _LOGGER.debug('open local socket')
        await hekr_device.open_socket_local()

        _LOGGER.debug('init authenticate')
        await hekr_device.authenticate()

        default_name = 'Hekr Device {}:{}'.format(host, port)
        name = config.get(CONF_NAME, default_name)

        _LOGGER.debug('Using sensor groups for monitoring: %s', sensors)
        entities = [
            HekrSensor(
                name=name + ' - ' + definition.get(ATTR_NAME, group.capitalize()),
                sensor_type=group,
                icon=definition.get(ATTR_ICON),
                unit_of_measurement=definition.get(ATTR_UNIT_OF_MEASUREMENT)
            )
            for group, definition in protocol[CONF_SENSORS].items()
            if group in sensors
        ]

        data = HekrData(
            hass=hass,
            entities=entities,
            hekr_device=hekr_device,
            protocol=protocol
        )

        _LOGGER.debug('async add entities')
        async_add_entities(entities)

        _LOGGER.debug('Updating platform for the first time')
        await data.async_update()

        _LOGGER.debug('Setting up platform to update every %d seconds', scan_interval.seconds)
        async_track_time_interval(hass, data.async_update, scan_interval)

    except Exception as e:
        _LOGGER.exception('Failed to initialize platform [%s]: %s', DOMAIN, str(e))
        raise PlatformNotReady


class HekrSensor(Entity):
    def __init__(self,
                 name: str = None,
                 sensor_type: str = None,
                 icon: str = None,
                 unit_of_measurement: str = None):
        self.sensor_type = sensor_type
        self._name = name
        self._device_state_attributes = {}
        self._available = False
        self._icon = icon
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self._attributes = None

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def name(self) -> str:
        """Return the display name of this entity."""
        return self._name

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._unit_of_measurement

    @property
    def device_state_attributes(self) -> Optional[dict]:
        return self._attributes


class HekrData:
    def __init__(self,
                 hass: HomeAssistantType,
                 hekr_device: Device,
                 entities: List[HekrSensor],
                 protocol: dict):
        self.hass = hass
        self.hekr_device = hekr_device
        self.protocol = protocol
        self.device_data = {}
        self.entities = entities

    @property
    def sensor_update_commands(self) -> Set[str]:
        update_commands = []
        for entity in self.entities:
            update_commands.extend(self.protocol[CONF_SENSORS][entity.sensor_type].get(CONF_UPDATE_COMMANDS))
        return set(update_commands)

    async def async_propagate(self, disabled: bool = False, dont_update_hass: bool = False) -> None:
        tasks = []
        _LOGGER.debug('data to propagate: %s', self.device_data)
        for entity in self.entities:
            new_attributes = None
            new_available = False
            new_state = STATE_UNKNOWN
            state_attr = None

            if not disabled:
                ''' Enable all sensor entities and update data '''
                new_available = True

                sensor_group = self.protocol[CONF_SENSORS].get(entity.sensor_type)
                monitored_attributes = sensor_group.get(ATTR_MONITORED_ATTRIBUTES)
                state_attr = sensor_group.get(ATTR_STATE_ATTRIBUTE, None)

                if state_attr in self.device_data:
                    new_state = self.device_data[state_attr]
                else:
                    new_state = STATE_OK

                if isinstance(monitored_attributes, list):
                    new_attributes = {
                        key: value
                        for key, value in self.device_data.items()
                        if key in monitored_attributes
                    }

                elif monitored_attributes:
                    new_attributes = self.device_data.copy()
                    if state_attr and state_attr in new_attributes:
                        del new_attributes[state_attr]

            should_update = False
            if new_available != entity.available:
                entity._available = new_available
                should_update = True

            if new_attributes is not None and entity.device_state_attributes != new_attributes:
                entity._attributes = new_attributes
                should_update = True

            if entity.state != new_state:
                entity._state = new_state
                should_update = True

            _LOGGER.debug('device %s, sensor_type: %s, state_attr: %s', entity, entity.sensor_type, state_attr)
            _LOGGER.debug('device %s, state: %s, attrs: %s, avail: %s',
                          entity, new_state, new_attributes, new_available)

            if not dont_update_hass and should_update:
                tasks.append(entity.async_update_ha_state())

        if tasks:
            _LOGGER.debug('%d update tasks scheduled', len(tasks))
            await asyncio.wait(tasks)

    async def async_update(self, *_, dont_update_hass: bool = False) -> None:
        try:
            _LOGGER.debug('Executing heartbeat during update')
            (state, _, _) = await self.hekr_device.heartbeat()

            if state != DeviceResponseState.SUCCESS:
                _LOGGER.error('Error while updating data: heartbeat could not execute for device %s', self.hekr_device)
                raise PlatformNotReady

            _LOGGER.debug('Updating data')
            new_data = {}

            for command in self.sensor_update_commands:
                _LOGGER.debug('Executing Hekr command "%s"', command)
                while True:
                    state, action, data = await self.hekr_device.command(command)

                    # @TODO: this is a workaround, and should not be here. not even sure if it works
                    if action == 'heartbeatResp':
                        _LOGGER.warning('Heartbeat response caught after executing command')
                    else:
                        break

                if state == DeviceResponseState.SUCCESS and isinstance(data, tuple):
                    _LOGGER.debug('Update for command "%s" complete: action %s, data %s', command, action, data)
                    new_data.update(data[1])
                else:
                    _LOGGER.error('Update for command "%s" failed: action %s, data %s', command, action, data)

                await asyncio.sleep(2)

            filter_func = self.protocol.get(CONF_FUNC_FILTER_ATTRIBUTES)
            if callable(filter_func):
                new_data = filter_func(new_data)

            self.device_data.update(new_data)

            _LOGGER.debug('Propagating data updates')
            await self.async_propagate(disabled=False, dont_update_hass=dont_update_hass)

        except HekrAPIException:
            _LOGGER.exception('Hekr API failed to sync')
            await self.async_propagate(disabled=True, dont_update_hass=dont_update_hass)

        except Exception:
            _LOGGER.exception('Exception occurred during device update')
            raise PlatformNotReady
