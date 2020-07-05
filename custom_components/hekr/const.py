""" Constants """

from datetime import timedelta
from typing import Tuple, Optional, Union, Dict, Any, TYPE_CHECKING, Sequence, Mapping, TypeVar, Callable

from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.const import CONF_DEVICE_ID, ENERGY_KILO_WATT_HOUR, POWER_WATT, ATTR_ICON, ATTR_NAME, CONF_SENSORS, \
    CONF_SWITCHES

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from hekrapi.types import DeviceID
    # noinspection PyUnresolvedReferences
    from .supported_protocols import CommandCall

DOMAIN = "hekr"

# Domain data holders
DATA_DEVICES = DOMAIN + "_devices"
DATA_ACCOUNTS = DOMAIN + "_accounts"
DATA_ACCOUNTS_CONFIG = DOMAIN + "_accounts_config"
DATA_DEVICES_CONFIG = DOMAIN + "_devices_config"
DATA_UPDATERS = DOMAIN + "_updaters"
DATA_DEVICE_LISTENERS = DOMAIN + "_device_listeners"
DATA_ACCOUNT_LISTENERS = DOMAIN + "_account_listeners"
DATA_DEVICE_ENTITIES = DOMAIN + "_device_entities"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_NAME_DEVICE = 'Hekr {device_id} {entity_type}'
DEFAULT_SENSOR_ICON = "mdi:flash"
DEFAULT_SWITCH_ICON = "mdi:switch"
DEFAULT_QUERY_COMMAND = "queryDev"
DEFAULT_APPLICATION_ID = "hass_hekr_python"
DEFAULT_CLOUD_HOST = "fra-hub.hekreu.me"
DEFAULT_CLOUD_PORT = 186
DEFAULT_USE_MODEL_FROM_PROTOCOL = True
DEFAULT_SLEEP_INTERVAL = 4
DEFAULT_TIMEOUT = timedelta(seconds=5)
DEFAULT_NAME_FORMAT = "Hekr {device_id} {ent_name}"
DEFAULT_RESTART_DELAY = 15

UNIT_VOLTAGE = "V"
UNIT_CURRENT = "A"
UNIT_ENERGY_CONSUMED = ENERGY_KILO_WATT_HOUR
UNIT_POWER_FACTOR = None
UNIT_POWER_ACTIVE = POWER_WATT
UNIT_POWER_REACTIVE = "kVa"
UNIT_CURRENT_CONSUMPTION = "W"

CONF_DEVICE_ID = CONF_DEVICE_ID
CONF_CONTROL_KEY = "control_key"
CONF_APPLICATION_ID = "application_id"
CONF_CLOUD_HOST = "cloud_host"
CONF_CLOUD_PORT = "cloud_port"
CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
CONF_DEVICE = "device"
CONF_DEVICES = "devices"
CONF_USE_MODEL_FROM_PROTOCOL = "use_model_from_protocol"
CONF_DUMP_DEVICE_CREDENTIALS = "dump_device_credentials"
CONF_TOKEN_UPDATE_INTERVAL = "token_update_interval"
CONF_NETWORK = "network"
CONF_EXPECTED_TYPE = "_expected_type"
CONF_DETECTED_TYPE = "_detected_type"

PROTOCOL_NAME = "name"
PROTOCOL_MODEL = "model"
PROTOCOL_MANUFACTURER = "manufacturer"
PROTOCOL_PORT = "port"
PROTOCOL_DETECTION = "detection"
PROTOCOL_DEFINITION = "definition"
PROTOCOL_FILTER = "filter"
PROTOCOL_SENSORS = "sensors"
PROTOCOL_DEFAULT = "default"
PROTOCOL_CMD_UPDATE = "update_command"
PROTOCOL_CMD_RECEIVE = "receive_command"
PROTOCOL_CMD_TURN_ON = "turn_on_command"
PROTOCOL_CMD_TURN_OFF = "turn_off_command"
PROTOCOL_SWITCHES = "switches"
PROTOCOL_STATUS = "status"

ATTR_STATE_ATTRIBUTE = "state_attribute"
ATTR_MONITORED = "monitored_attributes"
ATTR_NAME = ATTR_NAME
ATTR_ICON = ATTR_ICON

MONITORED_CONDITIONS_ALL = "all"

CONF_DOMAINS = {
    CONF_SENSORS: (DOMAIN_SENSOR, PROTOCOL_SENSORS),
    CONF_SWITCHES: (DOMAIN_SWITCH, PROTOCOL_SWITCHES),
}

# Config data type
AccountUsername = str
YAMLConfigKeyType = Union[
    Tuple[AccountUsername, Optional['DeviceID']],
    Tuple[Optional['DeviceID'], AccountUsername]
]
YAMLConfigDataType = Dict[str, Any]
ConfigDataType = Dict[YAMLConfigKeyType, Dict[str, Any]]
AttributesType = Union[bool, Sequence[str], Mapping[str, str]]
CancellationCall = Callable[[], Any]
ListContentType = TypeVar('ListContentType')
AnyCommand = Union[int, 'Command', 'CommandCall']