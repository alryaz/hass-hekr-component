"""Supported protocols for Hekr devices."""

__all__ = [
    'SUPPORTED_PROTOCOLS',
    'ALL_SUPPORTED_DOMAINS',
    'SUPPORTED_DEFINITIONS',
    'SupportedProtocol',
    'SupportedProtocolType',
    'get_supported_id_by_definition',
    'CommandCall'
]

from abc import ABC
from typing import Optional, TYPE_CHECKING, Dict, Any, Sequence, Type, Callable, Set, Tuple, Union

from hekrapi.protocols.power_meter import PowerMeterProtocol, PowerSupplyWarning, VoltageWarning, CurrentWarning
from homeassistant.components.switch import ATTR_CURRENT_POWER_W, DEVICE_CLASS_SWITCH
from homeassistant.const import (
    POWER_WATT, ENERGY_KILO_WATT_HOUR,
    STATE_OK, STATE_PROBLEM, STATE_ON, STATE_OFF, DEVICE_CLASS_POWER, STATE_UNKNOWN
)

from .const import AttributesType, AnyCommand

if TYPE_CHECKING:
    from hekrapi.protocol import Protocol, Command
    from hekrapi.connector import Response

SupportedProtocolType = Type['SupportedProtocol']


SUPPORTED_DEFINITIONS: Dict[str, Type['Protocol']] = dict()
SUPPORTED_PROTOCOLS: Dict[str, SupportedProtocolType] = dict()
ALL_SUPPORTED_DOMAINS: Set[str] = set()


def get_supported_id_by_definition(protocol_definition: Type['Protocol']):
    """Helper to get supported protocol ID by its definition"""
    definition_index = list(SUPPORTED_DEFINITIONS.values()).index(protocol_definition)
    return list(SUPPORTED_DEFINITIONS.keys())[definition_index]


def register_supported_protocol(protocol_id: str) -> Callable[[SupportedProtocolType], SupportedProtocolType]:
    """
    Protocol registration class decorator generator
    :param protocol_id: Protocol ID to register
    :return: Class decorator
    """
    if not isinstance(protocol_id, str):
        raise ValueError

    def register_protocol(supported_protocol_class: SupportedProtocolType):
        """
        Register protocol with id '%s'
        Override existing protocol registration if available
        """
        SUPPORTED_DEFINITIONS[protocol_id] = supported_protocol_class.definition
        SUPPORTED_PROTOCOLS[protocol_id] = supported_protocol_class
        ALL_SUPPORTED_DOMAINS.update(supported_protocol_class.get_supported_domains())
        return supported_protocol_class

    register_protocol.__doc__ %= (protocol_id, )

    return register_protocol


class ClassProperty:
    def __init__(self, f: Callable[..., Any]):
        self.f = f

    def __get__(self, instance, owner):
        return self.f(owner)

    def __set__(self, instance, value):
        raise AttributeError


class CommandCall:
    def __new__(cls, command: AnyCommand, *args, **kwargs):
        if isinstance(command, cls.__class__):
            return command
        return super().__new__(cls)

    def __init__(self,
                 command: Union[int, 'Command'],
                 arguments: Optional[Union[Sequence[Any], Dict[str, Any]]] = None):
        if isinstance(command, int):
            if isinstance(arguments, Sequence):
                raise ValueError("arguments cannot be provided as list when command is integer")
            self.command_id: int = command
        else:
            if isinstance(arguments, Sequence):
                arguments = dict(zip([a.name for a in command.arguments], arguments))
            self.command_id: int = command.command_id
        self.arguments = arguments

    def __eq__(self, other):
        if isinstance(other, CommandCall):
            return self.command_id == other.command_id and self.arguments == other.arguments
        return super().__eq__(other)


class _EntityConfig(ABC):
    """Base entity config holder"""
    entity_domain: str = NotImplemented

    def __init__(self,
                 name: str,
                 cmd_update: AnyCommand,
                 cmd_receive: AnyCommand,
                 arg_state: Optional[str] = None,
                 unit_of_measurement: Optional[str] = None,
                 device_class: Optional[str] = None,
                 icon: Optional[str] = None,
                 state_icons: Optional[Dict[str, str]] = None,
                 default: bool = False,
                 attributes: AttributesType = True):
        self.name: str = name
        self.arg_state: str = arg_state
        self.cmd_update: CommandCall = CommandCall(cmd_update)
        self.cmd_receive: CommandCall = CommandCall(cmd_receive)
        self.default: bool = default
        self.unit_of_measurement: Optional[str] = unit_of_measurement
        self.device_class: Optional[str] = device_class

        self.icon: Optional[str] = icon
        self.state_icons = state_icons
        self._attributes: AttributesType = attributes

    def get_icon(self, from_state: Optional[str] = None) -> Optional[str]:
        """
        Get icon for entity state string.
        :param from_state: (optional) Entity state
        :return: Corresponding state icon | default icon | no icon
        """
        if self.state_icons is not None:
            return self.state_icons.get(from_state, self.icon)
        return self.icon

    def get_state_with_attributes(self, filtered_attributes: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        attributes = self._attributes
        state_key = self.arg_state

        state = STATE_OK if state_key is None else filtered_attributes.get(state_key, STATE_UNKNOWN)

        if attributes is False:
            attributes = None
        if attributes is True:
            attributes = filtered_attributes
        elif isinstance(self._attributes, Sequence):
            attributes = {attr: filtered_attributes.get(attr) for attr in attributes}
        else:
            attributes = {attr: filtered_attributes.get(argument) for attr, argument in attributes.items()}

        attributes.pop(state_key, None)
        return state, attributes


class _ToggleConfig(_EntityConfig, ABC):
    """Base toggle-able entity config holder"""
    def __init__(self, *args, cmd_turn_on: AnyCommand, cmd_turn_off: AnyCommand, **kwargs):
        super().__init__(*args, **kwargs)

        self.cmd_turn_on: CommandCall = CommandCall(cmd_turn_on)
        self.cmd_turn_off: CommandCall = CommandCall(cmd_turn_off)


# Per-domain config
class SensorConfig(_EntityConfig):
    """Sensor configuration"""
    entity_domain = "sensor"


class SwitchConfig(_ToggleConfig):
    """Switch configuration"""
    entity_domain = "switch"


class SupportedProtocol(ABC):
    name: str = NotImplemented
    definition: Type['Protocol'] = NotImplemented

    # optional to implement, values not used if None
    name_format: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None

    force_model: bool = False
    force_manufacturer: bool = False

    @classmethod
    def attribute_filter(cls, response: 'Response') -> Dict[str, Any]:
        """
        Default attribute filter for command responses.
        Override this method in inherent protocols, unless argument conversion is not required.
        :param response: Response from device
        :return: Dictionary of arguments
        """
        return dict(response.arguments)

    @classmethod
    def get_domain_configs(cls, entity_domain: str) -> Dict[str, _EntityConfig]:
        """Get entity configurations for supported domain"""
        return {
            key: config
            for key, config in cls.__dict__.items()
            if isinstance(config, _EntityConfig)
            and config.entity_domain == entity_domain
        }

    @classmethod
    def get_domain_types(cls, entity_domain: str) -> Set[str]:
        """Shortcut operator to get only domain types"""
        return set(cls.get_domain_configs(entity_domain).keys())

    @classmethod
    def get_supported_domains(cls) -> Set[str]:
        """Get set of domains supported by protocol"""
        return set([
            config.entity_domain
            for config in cls.__dict__.values()
            if isinstance(config, _EntityConfig)
        ])


# ###################################
# Define custom supported protocols
# below this line
# ###################################

@register_supported_protocol("power_meter")
class SupportedPowerMeterProtocol(SupportedProtocol):
    definition = PowerMeterProtocol
    model = 'DDS238-4 W'
    manufacturer = 'HIKING (TOMZN)'

    force_manufacturer = True
    force_model = True

    @classmethod
    def attribute_filter(cls, response: 'Response') -> Dict[str, Any]:
        """Attribute filter for power meter protocol"""
        attributes = response.arguments

        # convert total active power to watts from kilowatts
        if "total_active_power" in attributes:
            attributes["total_active_power"] = round(attributes["total_active_power"] * 1000, 1)

        # filter attributes by phase count
        if "phase_count" in attributes:
            phase_count = attributes['phase_count']
            attributes = {
                attribute: value
                for attribute, value in attributes.items()
                if not (attribute[-2:] == '_'
                        and attribute[-1:].isdigit()
                        and int(attribute[-1:]) > phase_count)
            }

        # get mean current
        if "current_1" in attributes:
            currents = [
                value for attribute, value in attributes.items()
                if attribute[:-1] == "current_"
            ]
            total_current = sum(currents)
            attributes['mean_current'] = round(float(total_current) / len(currents), 3)
            attributes['total_current'] = total_current

        # get mean voltages
        if "voltage_1" in attributes:
            voltages = [
                value for attribute, value in attributes.items()
                if attribute[:-1] == "voltage_" and value
            ]
            attributes['mean_voltage'] = round(float(sum(voltages)) / len(voltages), 1)

        # detect state of the device
        attributes["state"] = STATE_OK
        if "warning_voltage" in attributes:
            if attributes['warning_voltage'] != VoltageWarning.OK:
                attributes["state"] = STATE_PROBLEM
            attributes['warning_voltage'] = attributes['warning_voltage'].name.lower()

        if "warning_battery" in attributes:
            if attributes['warning_battery'] != PowerSupplyWarning.OK:
                attributes["state"] = STATE_PROBLEM
            attributes["warning_battery"] = attributes["warning_battery"].name.lower()

        if "warning_current" in attributes:
            if attributes['warning_current'] != CurrentWarning.OK:
                attributes["state"] = STATE_PROBLEM
            attributes['warning_current'] = attributes['warning_current'].name.lower()

        # process switch state
        if "switch_state" in attributes:
            attributes["switch_state"] = STATE_ON if attributes["switch_state"] else STATE_OFF

        return attributes
    
    # Power meter sensors
    # -- queryDev-related sensors
    general = SensorConfig(
        name="General Information",
        icon="mdi:eye",
        arg_state="state",
        cmd_update=PowerMeterProtocol.query_device,
        cmd_receive=PowerMeterProtocol.report_device,
    )
    status = SensorConfig(
        name="Status",
        icon="mdi:help-circle",
        state_icons={STATE_PROBLEM: "mdi:alert", STATE_OK: "mdi:check-circle"},
        arg_state="state",
        attributes=["phase_count", "warning_voltage", "warning_current", "warning_battery"],
        cmd_update=PowerMeterProtocol.query_device,
        cmd_receive=PowerMeterProtocol.report_device,
        default=True
    )
    total_active_power = SensorConfig(
        name="Total Active Power",
        icon="mdi:gauge",
        arg_state="total_active_power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        cmd_update=PowerMeterProtocol.query_device,
        cmd_receive=PowerMeterProtocol.report_device,
        default=True,
    )
    total_consumption = SensorConfig(
        name="Total Consumption", icon="mdi:sigma",
        arg_state="total_energy_consumed",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        cmd_update=PowerMeterProtocol.query_device,
        cmd_receive=PowerMeterProtocol.report_device,
        default=True,
    )

    # -- queryData-related sensors
    detailed = SensorConfig(
        name="Detailed Information",
        icon="mdi:eye-settings",
        arg_state="state",
        cmd_update=PowerMeterProtocol.query_electricity,
        cmd_receive=PowerMeterProtocol.report_electricity,
    )
    voltage = SensorConfig(
        name="Mean Voltage",
        icon="mdi:alpha-v-circle",
        arg_state="mean_voltage",
        unit_of_measurement="V",
        attributes=["voltage_1", "voltage_2", "voltage_3", "current_frequency"],
        cmd_update=PowerMeterProtocol.query_electricity,
        cmd_receive=PowerMeterProtocol.report_electricity,
    )
    current = SensorConfig(
        name="Total Current",
        icon="mdi:alpha-i-circle",
        arg_state="total_current",
        unit_of_measurement="A",
        attributes=["mean_current", "current_1", "current_2", "current_3", "current_frequency"],
        cmd_update=PowerMeterProtocol.query_electricity,
        cmd_receive=PowerMeterProtocol.report_electricity,
    )
    power_factor = SensorConfig(
        name="Power Factor", icon="mdi:speedometer",
        arg_state="total_power_factor",
        attributes=["power_factor_1", "power_factor_2", "power_factor_3"],
        cmd_update=PowerMeterProtocol.query_electricity,
        cmd_receive=PowerMeterProtocol.report_electricity,
    )
    active_power = SensorConfig(
        name="Active Power",
        icon="mdi:flash",
        arg_state="total_active_power",
        unit_of_measurement=POWER_WATT,
        attributes=["active_power_1", "active_power_2", "active_power_3"],
        cmd_update=PowerMeterProtocol.query_electricity,
        cmd_receive=PowerMeterProtocol.report_electricity,
    )
    reactive_power = SensorConfig(
        name="Reactive Power",
        icon="mdi:flash-outline",
        arg_state="total_reactive_power",
        unit_of_measurement="kVa",
        attributes=["reactive_power_1", "reactive_power_2", "reactive_power_3"],
        cmd_update=PowerMeterProtocol.query_electricity,
        cmd_receive=PowerMeterProtocol.report_electricity,
    )

    # Switches
    main_power = SwitchConfig(
        name="Main Power",
        icon="mdi:electric-switch",
        state_icons={STATE_ON: "mdi:electric-switch-closed"},
        arg_state="switch_state",
        device_class=DEVICE_CLASS_SWITCH,
        attributes={ATTR_CURRENT_POWER_W: "current_energy_consumption"},
        cmd_update=PowerMeterProtocol.query_device,
        cmd_receive=PowerMeterProtocol.report_device,
        cmd_turn_on=CommandCall(PowerMeterProtocol.set_switch, [True]),
        cmd_turn_off=CommandCall(PowerMeterProtocol.set_switch, [False]),
    )
