"""Support for Hekr sensors."""

__all__ = [
    'PLATFORM_SCHEMA',
    'async_setup_platform',
    'async_setup_entry',
    'HekrSensor',
]

import logging
from functools import partial

from homeassistant.components.sensor import PLATFORM_SCHEMA, DOMAIN as PLATFORM_DOMAIN

from .base_platform import HekrEntity, base_async_setup_entry, base_async_setup_platform

_LOGGER = logging.getLogger(__name__)

async_setup_platform = partial(base_async_setup_platform, PLATFORM_DOMAIN, HekrEntity, logger=_LOGGER)
async_setup_entry = partial(base_async_setup_entry, PLATFORM_DOMAIN, HekrEntity, logger=_LOGGER)
