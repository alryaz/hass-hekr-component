"""Support for Hekr sensors."""
import asyncio
import logging
import threading
from typing import Optional, List, Set

from hekrapi.device import Device, DeviceResponseState
from hekrapi.exceptions import HekrAPIException
from homeassistant.const import (
    STATE_UNKNOWN, ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON, ATTR_NAME,
    CONF_SCAN_INTERVAL, STATE_OK, CONF_SENSORS
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval, async_call_later
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


class DeviceThreadedListener(threading.Thread):
    """
    This interfaces with the lirc daemon to read IR commands.
    When using lirc in blocking mode, sometimes repeated commands get produced
    in the next read of a command so we use a thread here to just wait
    around until a non-empty response is obtained from lirc.
    """

    def __init__(self, data, hass):
        """Construct a LIRC interface object."""
        threading.Thread.__init__(self)
        self.daemon = True
        self.stopped = threading.Event()
        self.hass = hass
        self.data = data

    def run(self):
        """Run the loop of the LIRC interface thread."""
        _LOGGER.debug("Hekr interface thread started")
        while not self.stopped.isSet():
            state, action, data = asyncio.run_coroutine_threadsafe(self.data.hekr_device.read_response(), self.hass.loop).result()
            if state == DeviceResponseState.WAIT_NEXT:
                _LOGGER.debug('Skipping command %s  %s  %s' % (state, action, data))
            elif DeviceResponseState.SUCCESS:
                if action == 'devSend':
                    command, attributes, _ = data
                    _LOGGER.debug('Received devSend for command %s with data %s' % (command, attributes))
                    self.data.device_data.update(attributes)
            elif DeviceResponseState.FAILURE:
                _LOGGER.error('Error while executing command %s  %s' % (action, data))
            else:
                _LOGGER.warning('Unknown response received: %s  %s  %s' % (state, action, data))


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

        _LOGGER.debug('Starting listener for %s' % str(hekr_device))
        self.listener = DeviceThreadedListener(self, hass)
        self.listener.start()

    @property
    def sensor_update_commands(self) -> Set[str]:
        update_commands = []
        for entity in self.entities:
            update_commands.extend(self.protocol[CONF_SENSORS][entity.sensor_type].get(CONF_UPDATE_COMMANDS))
        return set(update_commands)

    async def async_propagate(self, device_data, disabled: bool = False, dont_update_hass: bool = False) -> None:
        tasks = []
        _LOGGER.debug('data to propagate: %s', device_data)
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

                if state_attr in device_data:
                    new_state = device_data[state_attr]
                else:
                    new_state = STATE_OK

                if isinstance(monitored_attributes, list):
                    new_attributes = {
                        key: value
                        for key, value in device_data.items()
                        if key in monitored_attributes
                    }

                elif monitored_attributes:
                    new_attributes = device_data.copy()
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
        if self.device_data:
            filter_func = self.protocol.get(CONF_FUNC_FILTER_ATTRIBUTES)
            if callable(filter_func):
                self.device_data = filter_func(self.device_data)

            await self.async_propagate(self.device_data, disabled=False, dont_update_hass=False)
            self.device_data = {}
        else:
            await self.async_propagate({}, disabled=True, dont_update_hass=False)

        try:
            _LOGGER.debug('Executing heartbeat during update')
            await self.hekr_device.heartbeat()

            _LOGGER.debug('Updating data')
            for command in self.sensor_update_commands:
                await asyncio.sleep(1)
                _LOGGER.debug('Executing Hekr command "%s"', command)
                await self.hekr_device.command(command)

        except Exception:
            _LOGGER.exception('Exception occurred during device update')
            raise PlatformNotReady
