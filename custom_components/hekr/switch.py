"""Support for Hekr switches."""

__all__ = [
    "PLATFORM_SCHEMA",
    "async_setup_platform",
    "async_setup_entry",
    "HekrSwitch",
]

import logging
from typing import Any, Optional

from homeassistant.components.switch import PLATFORM_SCHEMA, DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import STATE_ON, STATE_OFF

from homeassistant.components.switch import SwitchEntity

from .base_platform import HekrEntity, create_platform_basics
from .const import PROTOCOL_CMD_TURN_ON, PROTOCOL_CMD_TURN_OFF

_LOGGER = logging.getLogger(__name__)


class HekrSwitch(HekrEntity, SwitchEntity):
    @property
    def is_on(self) -> bool:
        return self.state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        self._state = STATE_ON
        self.execute_protocol_command(PROTOCOL_CMD_TURN_ON)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        self._state = STATE_OFF
        self.execute_protocol_command(PROTOCOL_CMD_TURN_OFF)
        self.schedule_update_ha_state()

    @property
    def unique_id(self) -> Optional[str]:
        return "_".join((self._device_id, PLATFORM_DOMAIN, self._ent_type))


PLATFORM_SCHEMA, async_setup_platform, async_setup_entry = create_platform_basics(
    logger=_LOGGER,
    entity_domain=PLATFORM_DOMAIN,
    entity_factory=HekrSwitch,
    base_schema=PLATFORM_SCHEMA,
)
