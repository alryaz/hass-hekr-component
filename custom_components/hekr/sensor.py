"""Support for Hekr sensors."""

__all__ = [
    'PLATFORM_SCHEMA',
    'async_setup_platform',
    'async_setup_entry',
    'HekrSensor',
]

import logging
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.components.sensor import PLATFORM_SCHEMA, DOMAIN as PLATFORM_DOMAIN

from .base_platform import HekrEntity, base_async_setup_entry, base_async_setup_platform

if TYPE_CHECKING:
    from .supported_protocols import SensorConfig

_LOGGER = logging.getLogger(__name__)


class HekrSensor(HekrEntity):
    _entity_config: 'SensorConfig' = NotImplemented


async_setup_platform = partial(base_async_setup_platform, PLATFORM_DOMAIN, HekrSensor, logger=_LOGGER)
async_setup_entry = partial(base_async_setup_entry, PLATFORM_DOMAIN, HekrSensor, logger=_LOGGER)
