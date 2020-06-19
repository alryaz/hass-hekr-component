""" Basic Hekr protocol implementation based on Wisen app. """

__all__ = [
    'async_setup',
    'async_setup_entry',
    'async_unload_entry',
    'async_remove_entry',
    'CONFIG_SCHEMA',
]

__title__ = 'HomeAssistant Hekr Component'
__version__ = '0.2.2'
__author__ = 'Alexander Ryazanov <alryaz@xavux.com>'

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from hekrapi.exceptions import HekrAPIException, AuthenticationFailedException
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_DEVICE_ID
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, CONF_DEVICES, CONF_ACCOUNTS, CONF_USE_MODEL_FROM_PROTOCOL, CONF_DEVICE, CONF_ACCOUNT
from .schemas import CONFIG_SCHEMA
from .supported_protocols import SUPPORTED_PROTOCOLS

if TYPE_CHECKING:
    from hekrapi.device import Device
    from .base_platform import HekrEntity
    from .hekr_data import HekrData

_LOGGER = logging.getLogger(__name__)


@callback
def _find_existing_entry(hass: HomeAssistantType, setup_type: str, item_id: str) \
        -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    item_id_key = CONF_DEVICE_ID if setup_type == CONF_DEVICE else CONF_USERNAME
    for config_entry in existing_entries:
        if setup_type in config_entry.data and config_entry.data[setup_type][item_id_key] == item_id:
            return config_entry


async def async_setup(hass: HomeAssistantType, yaml_config):
    """Set up cloud authenticators from config."""
    domain_config = yaml_config.get(DOMAIN)
    if not domain_config:
        return True

    from .hekr_data import HekrData

    hekr_data: 'HekrData' = HekrData(hass)
    hekr_data.use_model_from_protocol = domain_config[CONF_USE_MODEL_FROM_PROTOCOL]

    hass.data[DOMAIN] = hekr_data

    devices_config = domain_config.get(CONF_DEVICES)
    if devices_config:

        for device_cfg in devices_config:

            device_id = device_cfg.get(CONF_DEVICE_ID)

            _LOGGER.debug('Device "%s" entry from YAML' % device_id)

            existing_entry = _find_existing_entry(hass, CONF_DEVICE, device_id)
            if existing_entry:
                if existing_entry.source == config_entries.SOURCE_IMPORT:
                    hekr_data.devices_config_yaml[device_id] = device_cfg
                    _LOGGER.debug('Skipping existing import binding')
                else:
                    _LOGGER.warning('YAML config for device %s is overridden by another config entry!' % device_id)
                continue

            if device_id in hekr_data.devices_config_yaml:
                _LOGGER.warning('Device with ID "%s" set up multiple times. Check your configuration.' % device_id)
                continue

            _LOGGER.debug('Adding device entry with ID "%s"' % device_id)

            hekr_data.devices_config_yaml[device_id] = device_cfg
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={CONF_DEVICE: device_cfg},
                )
            )

    accounts_config = domain_config.get(CONF_ACCOUNTS)
    if accounts_config:

        for account_cfg in accounts_config:

            account_id = account_cfg.get(CONF_USERNAME)

            _LOGGER.debug('Account "%s" entry from YAML' % account_id)

            existing_entry = _find_existing_entry(hass, CONF_ACCOUNT, account_id)
            if existing_entry:
                if existing_entry.source == config_entries.SOURCE_IMPORT:
                    hekr_data.accounts_config_yaml[account_id] = account_cfg
                    _LOGGER.debug('Skipping existing import binding')
                else:
                    _LOGGER.warning('YAML config for device %s is overridden by another config entry!' % account_id)
                continue

            if account_id in hekr_data.accounts_config_yaml:
                _LOGGER.warning('Account "%s" set up multiple times. Check your configuration.' % account_id)
                continue
            
            _LOGGER.debug('Adding account entry with username "%s"' % account_id)

            hekr_data.accounts_config_yaml[account_id] = account_cfg
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={CONF_ACCOUNT: account_cfg},
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry):
    conf = config_entry.data

    hekr_data: 'HekrData' = hass.data.get(DOMAIN)
    if hekr_data is None:
        from .hekr_data import HekrData

        hekr_data = HekrData(hass)
        hass.data[DOMAIN] = hekr_data

    try:
        existing_entries = hass.config_entries.async_entries(DOMAIN)

        if CONF_DEVICE in conf:

            device_cfg = conf[CONF_DEVICE]
            device_id = device_cfg[CONF_DEVICE_ID]

            if config_entry.source == config_entries.SOURCE_IMPORT:
                device_cfg = hekr_data.devices_config_yaml.get(device_id)
                if not device_cfg:
                    _LOGGER.info('Removing entry %s after removal from YAML configuration.' % config_entry.entry_id)
                    hass.async_create_task(
                        hass.config_entries.async_remove(config_entry.entry_id)
                    )
                    return False

            for other_config_entry in existing_entries:
                if other_config_entry.entry_id == config_entry.entry_id:
                    continue

                other_conf = other_config_entry.data
                if CONF_ACCOUNT in other_conf:
                    account_id = other_conf[CONF_ACCOUNT][CONF_USERNAME]
                    account_devices = hekr_data.get_account_devices(account_id)
                    if device_id in account_devices:
                        _LOGGER.info('Detected local config override for device "%s" with account "%s" set up'
                                     % (device_id, account_id))

                        cancel_cloud_listener = True
                        for other_device_id in account_devices.keys():
                            if other_device_id != device_id:
                                _LOGGER.debug('Detected other devices on account "%s", will not cancel listener.'
                                              % account_id)
                                cancel_cloud_listener = False
                                break

                        if cancel_cloud_listener:
                            device: Optional['Device'] = hekr_data.devices.get(device_id)
                            if device and device.connector:
                                if device.connector.listener and device.connector.listener.is_running:
                                    device.connector.listener.stop()

                                await device.close_connection()

                            del device

            _LOGGER.debug('Setting up config entry for device with ID "%s"' % device_id)

            device = hekr_data.create_local_device(device_cfg)
            await device.open_connection()
            hekr_data.refresh_connections()

            # await hekr_data.create_device_registry_entry(device, config_entry.entry_id)

            hekr_data.setup_entities(config_entry)

            _LOGGER.debug('Successfully set up device with ID "%s"' % device_id)
            return True

        elif CONF_ACCOUNT in conf:
            account_cfg = conf[CONF_ACCOUNT]
            account_id = account_cfg.get(CONF_USERNAME)

            if config_entry.source == config_entries.SOURCE_IMPORT:
                account_cfg = hekr_data.accounts_config_yaml.get(account_id)
                if account_cfg is None:
                    _LOGGER.info('Removing entry %s after removal from YAML configuration.' % config_entry.entry_id)
                    hass.async_create_task(
                        hass.config_entries.async_remove(config_entry.entry_id)
                    )
                    return False

            hekr_data.create_account(account_cfg)
            added_devices = await hekr_data.update_account(account_id)

            if not added_devices:
                _LOGGER.warning('No devices found in account "%s". Not adding.' % account_id)
                await hekr_data.cleanup_account(account_id)
                return False

            _LOGGER.debug('Successfully set up account with username "%s"' % account_id)

            hekr_data.setup_entities(config_entry)

        else:
            _LOGGER.error('Unknown configuration format for entry ID %s, must remove' % config_entry.entry_id)
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
            return False

    except AuthenticationFailedException:
        _LOGGER.exception('Failed to authenticate and update devices from account. Maybe password is invalid?')
        return False

    except HekrAPIException:
        _LOGGER.exception("API exception while setting up config entry %s" % config_entry.entry_id)
        return False

    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry):
    _LOGGER.debug('Unloading Hekr config entry with ID "%s"' % config_entry.entry_id)

    hekr_data: 'HekrData' = hass.data[DOMAIN]

    try:
        await asyncio.wait(hekr_data.unload_entities(config_entry))

        devices_to_unload = hekr_data.collect_devices_for_entry(config_entry)

        for device_id in devices_to_unload:
            _LOGGER.debug('Unloaded device from data: %s' % device_id)
            # await hekr_data.delete_device_registry_entry(device_id)
            await hekr_data.cleanup_device(device_id, with_refresh=False)

        hekr_data.refresh_connections()

        if CONF_ACCOUNT in config_entry.data:
            account_id = config_entry.data[CONF_ACCOUNT][CONF_USERNAME]
            await hekr_data.cleanup_account(account_id)

    except HekrAPIException:
        _LOGGER.exception('Exception occurred while unloading entry %s' % config_entry.entry_id)

    return True
