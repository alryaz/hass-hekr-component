# HomeAssistant Hekr Devices Integration
[![GitHub Page](https://img.shields.io/badge/GitHub-alryaz%2Fhass--hekr--component-blue)](https://github.com/alryaz/hass-hekr-component)
[![Donate Yandex](https://img.shields.io/badge/Donate-Yandex-red.svg)](https://money.yandex.ru/to/410012369233217)
[![Donate PayPal](https://img.shields.io/badge/Donate-Paypal-blueviolet.svg)](https://www.paypal.me/alryaz)
{% set mainline_ver = 'v0.2.1' %}{% set mainline_num_ver = mainline_ver.replace("v", "").replace(".", "") | int %}{%- set features = {
    'v0.2.0': 'Accounts support (devices accessible both via local and cloud endpoints)',
    'v0.1.6': 'Thai, Dutch, Farsi languages support',
    'v0.1.5': 'Automatic reconnection on socket close',
    'v0.1.3': 'Configuration via HomeAssistant UI',
    'v0.1.0': 'Non-blocking listeners for device responses',
}-%}{%- set breaking_changes = {
    'v0.2.0': [
        ['Platform setups are no longer supported. Unfortunately, this is a trade-off for supporting accounts.',
        'When you update to the latest version, a persistent notification will appear containing necessary',
        'YAML configuration that you can add to your configuration.yaml file.'],
        ['Config entry management mechanism vastly overhauled. While this should not influence',
        'existing setups, it is advised to keep a backup of `core.config_entries` on update.'],
        ['From now on, entries created within interface **will override** YAML configuration. This is done',
         'to facilitate capability of removing YAML entry live and replacing it with different config.']
    ]
} -%}
{% if installed %}{% if version_installed == "master" %}
#### Breaking changes: master
This branch may be unstable, as it contains commits not tested beforehand.  
Please, do not use this branch in production environments.
{% else %}{% set num_ver = version_installed.replace("v", "").replace(".","") | int %}{% if num_ver == mainline_num_ver %}
#### ✔ You are using mainline version{% else %}
#### 🚨 You are using an outdated release of Hekr component{% if num_ver < 20 %}
{% set print_header = True %}{% for ver, changes in breaking_changes.items() %}{% set ver = ver.replace("v", "").replace(".","") | int %}{% if num_ver < ver %}{% if print_header %}
##### Breaking changes (`{{ version_installed }}` -> `{{ mainline_ver }}`){% set print_header = False %}{% endif %}{% for change in changes %}
{{ '- '+change.pop(0) }}{% for changeline in change %}
{{ '  '+changeline }}{% endfor %}{% endfor %}{% endif %}{% endfor %}

##### Bug fixes (`{{ version_installed }}` -> `{{ mainline_ver }}`){% if num_ver == 20 %}
- Fixed adding local devices when `name` parameter has not been set{% endif %}{% if num_ver < 20 %}
- Configuration entries do not block new ones after removal{% endif %}{% if num_ver < 16 %}
- Switches state update fix {% endif %}{% endif %}{% endif %}

##### Features{% for ver, text in features.items() %}{% set feature_ver = ver.replace("v", "").replace(".", "") | int %}
- {% if num_ver < feature_ver %}**{% endif %}`{{ ver }}` {% if num_ver < feature_ver %}NEW** {% endif %}{{ text }}{% endfor %}

Please, report all issues to the [project's GitHub issues](https://github.com/alryaz/hass-hekr-component/issues).
{% endif %}{% else %}
## Features{% for ver, text in features.items() %}
- {{ text }} _(supported since `{{ ver }}`)_{% endfor %}
{% endif %}
## Screenshots
#### Device with `power_meter` protocol
![Loaded badges for power meter protocol](https://raw.githubusercontent.com/alryaz/hass-hekr-component/master/images/power_meter/badges.png)
## Configuration
### _Option A:_ Using integrations dialog:
Go to _HomeAssistant_'s `Settings` / `Integrations` menu and add (`+` button) the `Hekr` integration.  
From there you can create both device and account entries.
 
### _Option B:_ Using `configuration.yaml`
Modify the following examples accordingly and put the configuration into your `configuration.yaml` file.  

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