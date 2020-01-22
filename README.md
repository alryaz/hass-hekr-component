
# HomeAssistant Hekr Integration 
> HomeAssistant implementation of Hekr API communicator
>
>[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/alryaz/hass-hekr-component/graphs/commit-activity)

## ❗❗❗ WARNING ❗❗❗
***KNOWN BUG AT LARGE:*** Entities are not deleted after deleting integration.
  
**THIS PROJECT IS HIGHLY _WORK-IN-PROGRESS_!!!**
Things are subject to change drastically until at least two to three different Hekr implementations are discovered and
added to the integration as well as the parent python module. Please, read release notes carefully before installing
or upgrading. __I am not responsible for damaging your devices in any way!__

## Contribution

If you found yourself using Wisen application with any of your Smart Home devices, contact me via
e-mail <alryaz@xavux.com>. The process of adding new devices is not yet completely formalized,
the milestone is set for a release-candidate version.

Check original repository with HekrAPI bindings: [hekrapi-python: Hekr protocol bindings for Python](https://github.com/alryaz/hekrapi-python)

## Example configuration

### Power meter protocol: `power_meter`
#### Configuration via platform
```yaml
sensor:
- platform: hekr
  host: home-power-meter.lan
  device_id: ESP_2M_AABBCCDDEEFF
  control_key: 202cb962ac59075b964b07152d234b70
  protocol: power_meter
```
#### Configuration via component
```yaml
hekr:
  devices:
    - host: home-power-meter.lan
      device_id: ESP_2M_AABBCCDDEEFF
      control_key: 202cb962ac59075b964b07152d234b70
      protocol: power_meter
      sensors: general
      switches: main_power
```

In this state, the plugin will generate three sensors, all obtained via a single `queryDev` command.
These sensors are:
- `status` - **Status** (whether device reports any kind of errors)
- `current_consumption` - **Current Consumption** (current power consumption in *W*)
- `total_consumption` - **Total Consumption** (total energy consumption in *kW*).

Also the following sensors are available, but not enabled by default (as they increase the amount of requests required to poll the device, leading to infrequent, but possible timeouts):

- `general` - **General Information** (spews out all data available from `queryDev` command)
- `detailed` - **Detailed Information** (spews out all data available from `queryData` command)
- `voltage` - **Voltage** (voltage for every available phase, also mean voltage)
- `current` - **Current** (current for every available phase, also mean current)
- `power_factor` - **Power Factor**
- `active_power` - **Active Power**
- `reactive_power` - **Reactive Power**

Recent release added support for switches, but so far there is only one supported:

- `main_power` - **Main Power** (toggles relay power on and off) 

#### Custom sensors, polling interval and name
```yaml
sensor:
- platform: hekr
  host: home-power-meter.lan
  device_id: ESP_2M_AABBCCDDEEFF
  control_key: 202cb962ac59075b964b07152d234b70
  scan_interval:
    seconds: 15
  protocol: power_meter
  sensors:
    - general
    - detailed
    - status
    - current_consumption
    - total_consumption
    - voltage
    - current
    - power_factor
    - active_power
    - reactive_power
```
#### Switches
```yaml
switch:
- platform: hekr
  host: home-power-meter.lan
  device_id: ESP_2M_AABBCCDDEEFF
  control_key: 202cb962ac59075b964b07152d234b70
  protocol: power_meter
  switches: main_power
```
## Author

👤 **Alexander Ryyazanov (@alryaz)**

* Github: [@alryaz](https://github.com/alryaz)
* Telegram: [@alryaz](https://t.me/alryaz)

## Show your support

Give a ⭐ if this project helped you!



