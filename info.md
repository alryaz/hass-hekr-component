# HomeAssistant Hekr Devices Integration
[GitHub Page](https://github.com/alryaz/hass-hekr-component)

{%- if version_installed == "development" %}

#### You are running a development version!
This is **only** intended for development!  
Please, report all issues to the [project's GitHub issues](https://github.com/alryaz/hass-hekr-component/issues).

{%- elif version_installed.replace("v", "").replace(".","") | int < 20  %}

### !!! BREAKING CHANGES IN >=0.2.0 !!!
- Platform setups are no longer supported. Unfortunately, this is a trade-off for supporting accounts.
  When you update to the latest version, a persistent notification will appear containing necessary
  YAML configuration that you can add to your configuration.yaml file.
- Config entry management mechanism vastly overhauled. While this should not influence
  existing setups, it is advised to keep a backup of `core.config_entries` on update.
- From now on, entries created within interface **will override** YAML configuration. This is done
  to facilitate capability of removing YAML entry live and replacing it with different config.

{%- elif not installed %}

## Screenshots
#### Device with `power_meter` protocol
![](images/power_meter/badges.png)

{% endif -%}

## Configuration
### ...as platforms:
Modify the following example accordingly and put the configuration into your `configuration.yaml` file.  
__Caution:__ when setting up multiple platforms, make sure the base configs are identical.
```yaml
sensor: // `sensor` platform
- platform: hekr
  host: [DEVICE HOSTNAME/IP ADDRESS]
  device_id: [DEVICE ID]
  control_key: [DEVICE CONTROL KEY]
  protocol: [PROTOCOL NAME]
  sensors: [SENSOR SELECTION (OPTIONAL)]
  scan_interval: [POLLING INTERVAL, DEFAULT = 15 SECONDS (OPTIONAL)]

switch: // `switch` platform
- platform: hekr
  host: [DEVICE HOSTNAME/IP ADDRESS]
  device_id: [DEVICE ID]
  control_key: [DEVICE CONTROL KEY]
  protocol: [PROTOCOL NAME]
  switches: [SWITCH SELECTION (OPTIONAL)]
  scan_interval: [POLLING INTERVAL, DEFAULT = 15 SECONDS (OPTIONAL)]
```
### ...via component:
Modify the following example accordingly and put the configuration into your `configuration.yaml` file.  
Multiple devices can be added under `[hekr->devices]`.
```yaml
hekr:
  devices:
    - host: [DEVICE HOSTNAME/IP ADDRESS]
      device_id: [DEVICE ID]
      control_key: [DEVICE CONTROL KEY]
      protocol: [PROTOCOL NAME]
      sensors: [SENSOR SELECTION (OPTIONAL)]
      switches: [SWITCH SELECTION (OPTIONAL)]
      scan_interval: [POLLING INTERVAL, DEFAULT = 15 SECONDS (OPTIONAL)]
```
### ...using integrations dialog:
Go to _HomeAssistant_'s `Settings / Integrations` menu and add (`+` button) the `Hekr Devices` integration.

## Supported protocols
### _Smart Power Meter_ (`power_meter`)
__Sensors__: `general`, `detailed`, `status`, `current_consumption`, `total_consumption`, `voltage`, `current`,
             `power_factor`, `active_power`, `reactive_power`   
__Switches__: `main_power`