"""Support for Hekr switches."""

__all__ = [
    'PLATFORM_SCHEMA',
    'async_setup_platform',
    'async_setup_entry',
    'HekrSwitch',
]

import logging
from functools import partial
from typing import Any, Dict, Optional, TYPE_CHECKING

from homeassistant.components.switch import PLATFORM_SCHEMA, DOMAIN as PLATFORM_DOMAIN, \
    ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH
from homeassistant.const import STATE_ON, STATE_OFF

from .base_platform import HekrEntity, base_async_setup_platform, base_async_setup_entry

try:
    from homeassistant.components.switch import SwitchDevice
except ImportError:
    from homeassistant.components.switch import SwitchEntity as SwitchDevice

if TYPE_CHECKING:
    from .supported_protocols import SwitchConfig

_LOGGER = logging.getLogger(__name__)


class HekrSwitch(HekrEntity, SwitchDevice):
    _entity_config: 'SwitchConfig' = NotImplemented

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_power_w = None
        self._today_energy_kwh = None

    @property
    def is_on(self) -> bool:
        return self.state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        self._state = STATE_ON
        self._sync_execute_command(self._entity_config.cmd_turn_on)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        self._state = STATE_OFF
        self._sync_execute_command(self._entity_config.cmd_turn_off)
        self.schedule_update_ha_state()

    def handle_data_update(self, filtered_attributes: Dict[str, Any]) -> None:
        self._current_power_w = filtered_attributes.get(ATTR_CURRENT_POWER_W)
        self._today_energy_kwh = filtered_attributes.get(ATTR_TODAY_ENERGY_KWH)

        super().handle_data_update(filtered_attributes)

    @property
    def current_power_w(self) -> Optional[float]:
        return self._current_power_w

    @property
    def today_energy_kwh(self) -> Optional[float]:
        return self._today_energy_kwh


async_setup_platform = partial(base_async_setup_platform, PLATFORM_DOMAIN, HekrSwitch, logger=_LOGGER)
async_setup_entry = partial(base_async_setup_entry, PLATFORM_DOMAIN, HekrSwitch, logger=_LOGGER)
