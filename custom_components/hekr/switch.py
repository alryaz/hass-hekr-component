"""Support for Hekr sensors."""
import logging
from typing import Any, Optional

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice, DOMAIN as PLATFORM_DOMAIN, \
    ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH
from homeassistant.const import STATE_ON

from .const import PROTOCOL_CMD_TURN_ON, PROTOCOL_CMD_TURN_OFF
from .sensor import HekrEntity, create_platform_basics

_LOGGER = logging.getLogger(__name__)


class HekrSwitch(HekrEntity, SwitchDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_power_w = None
        self._today_energy_kwh = None

    @property
    def is_on(self) -> bool:
        return self.state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        self.execute_protocol_command(PROTOCOL_CMD_TURN_ON)

    def turn_off(self, **kwargs: Any) -> None:
        self.execute_protocol_command(PROTOCOL_CMD_TURN_OFF)

    async def handle_data_update(self, data):
        power_attr = self._config.get(ATTR_CURRENT_POWER_W)
        if power_attr is not None:
            self._current_power_w = data.get(power_attr)

        today_energy_attr = self._config.get(ATTR_TODAY_ENERGY_KWH)
        if today_energy_attr is not None:
            self._today_energy_kwh = data.get(today_energy_attr)

        await super().handle_data_update(data)

    @property
    def current_power_w(self):
        return self._current_power_w

    @property
    def today_energy_kwh(self):
        return self._today_energy_kwh

    @property
    def unique_id(self) -> Optional[str]:
        return '_'.join((self._device_id, PLATFORM_DOMAIN, self._ent_type))


PLATFORM_SCHEMA, async_setup_platform, async_setup_entry = create_platform_basics(
    logger=_LOGGER,
    entity_domain=PLATFORM_DOMAIN,
    entity_factory=HekrSwitch,
    base_schema=PLATFORM_SCHEMA,
)
