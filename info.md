# HomeAssistant Hekr Devices Integration
[![GitHub Page](https://img.shields.io/badge/GitHub-alryaz%2Fhass--hekr--component-blue)](https://github.com/alryaz/hass-hekr-component)
[![Donate Yandex](https://img.shields.io/badge/Donate-Yandex-red.svg)](https://money.yandex.ru/to/410012369233217)
[![Donate PayPal](https://img.shields.io/badge/Donate-Paypal-blueviolet.svg)](https://www.paypal.me/alryaz)

{% if installed %}

{% if version_installed == "master" %}

#### Breaking changes: master
This branch may be unstable, as it contains commits not tested beforehand.  
Please, do not use this branch in production environments.

{% elif version_installed.replace("v", "").replace(".","") | int < 20  %}

#### Breaking changes: >= 0.2.0
- Platform setups are no longer supported. Unfortunately, this is a trade-off for supporting accounts.
  When you update to the latest version, a persistent notification will appear containing necessary
  YAML configuration that you can add to your configuration.yaml file.
- Config entry management mechanism vastly overhauled. While this should not influence
  existing setups, it is advised to keep a backup of `core.config_entries` on update.
- From now on, entries created within interface **will override** YAML configuration. This is done
  to facilitate capability of removing YAML entry live and replacing it with different config.
  
{% else %}

#### Mainline version :smile:

{% endif %}

Please, report all issues to the [project's GitHub issues](https://github.com/alryaz/hass-hekr-component/issues).

{% else %}

## Screenshots
#### Device with `power_meter` protocol
![Loaded badges for power meter protocol](https://raw.githubusercontent.com/alryaz/hass-hekr-component/master/images/power_meter/badges.png)

{% endif %}


## Configuration
### _Option A:_ Using integrations dialog:
Go to _HomeAssistant_'s `Settings` / `Integrations` menu and add (`+` button) the `Hekr` integration.  
From there you can create both device and account entries.
 
### _Option B:_ Using `configuration.yaml`
Modify the following example accordingly and put the configuration into your `configuration.yaml` file.  
, as well as multiple accounts: `[hekr->accounts]`.

#### Device configuration
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

#### Account configuration
Multiple accounts can be added under `[hekr->devices]`.
```yaml
hekr:
  accounts:
    - username: [USERNAME]
      password: [PASSWORD]
```

## Supported protocols
### _Smart Power Meter_ (`power_meter`)
__Sensors__: `general`, `detailed`, `status`, `current_consumption`, `total_consumption`, `voltage`, `current`,
             `power_factor`, `active_power`, `reactive_power`   
__Switches__: `main_power`