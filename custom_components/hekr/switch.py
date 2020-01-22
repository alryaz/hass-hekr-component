"""Support for Hekr sensors."""
import logging
from typing import Any, Optional

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice, DOMAIN as PLATFORM_DOMAIN

from .const import PROTOCOL_CMD_TURN_ON, PROTOCOL_CMD_TURN_OFF
from .sensor import HekrEntity, create_platform_basics

_LOGGER = logging.getLogger(__name__)


class HekrSwitch(HekrEntity, SwitchDevice):
    @property
    def is_on(self) -> bool:
        return self._attributes['switch_state']

    def turn_on(self, **kwargs: Any) -> None:
        self._exec_protocol_command(PROTOCOL_CMD_TURN_ON)

    def turn_off(self, **kwargs: Any) -> None:
        self._exec_protocol_command(PROTOCOL_CMD_TURN_OFF)

    @property
    def unique_id(self) -> Optional[str]:
        return '_'.join((self._device_id, PLATFORM_DOMAIN, self._ent_type))


PLATFORM_SCHEMA, async_setup_platform, async_setup_entry = create_platform_basics(
    logger=_LOGGER,
    entity_domain=PLATFORM_DOMAIN,
    entity_factory=HekrSwitch,
    base_schema=PLATFORM_SCHEMA,
)
