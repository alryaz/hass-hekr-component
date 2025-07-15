# ⚠️ THIS PROJECT IS LOOKING FOR A MAINTAINER ⚠️

I no longer posess means to test this component on newer Home Assistant versions as I have re-flashed the only Hekr device I had, and the other blew up spectacularly.

Unless someone wants to lease a constant VPN with a connection to a device, I (@alryaz) will be unable to support this project further.

Please, raise an issue to ask for maintainersihp transfer.

# Home Assistant Hekr Integration 
> Home Assistant implementation of Hekr API communicator
>
> [![hacs_badge](https://img.shields.io/badge/HACS-Default-green.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
> [![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
> [![Maintenance](https://img.shields.io/badge/Maintained%3F-bugfixes%20only-yellow.svg?style=for-the-badge)](https://github.com/alryaz/hass-hekr-component-component/graphs/commit-activity)

> 💵 **Donation options to support development**  
> [![Donate using YooMoney](https://img.shields.io/badge/YooMoney-8B3FFD.svg?style=for-the-badge)](https://yoomoney.ru/to/410012369233217)
> [![Donate using Tinkoff](https://img.shields.io/badge/Tinkoff-F8D81C.svg?style=for-the-badge)](https://www.tinkoff.ru/cf/3g8f1RTkf5G)
> [![Donate using Sberbank](https://img.shields.io/badge/Сбербанк-green.svg?style=for-the-badge)](https://www.sberbank.com/ru/person/dl/jc?linkname=3pDgknI7FY3z7tJnN)
> [![Donate using DonationAlerts](https://img.shields.io/badge/DonationAlerts-fbaf2b.svg?style=for-the-badge)](https://www.donationalerts.com/r/alryaz)
>
> 💬 **Technical Support**  
> [![Telegram Group](https://img.shields.io/endpoint?url=https%3A%2F%2Ftg.sumanjay.workers.dev%2Falryaz_ha_addons&style=for-the-badge)](https://telegram.dog/alryaz_ha_addons)  
> **Warning:** The group is primarily oriented toward Russian users, however do not hesitate to join and ask questions in English, to which I usually reply in a timely manner.

> [!WARNING]
> **THIS PROJECT IS HIGHLY WORK-IN-PROGRESS**  
> Things are subject to change drastically until at least two to three different Hekr implementations are discovered and
> added to the integration as well as the parent python module. Please, read release notes carefully before installing
> or upgrading. __I am not responsible for damaging your devices in any way!__

> [!NOTE]
> This module **does not** yet support _Elro Connects_, however work has been done to make a testing implementation.
> Testers with _Elro K1_ gateways are needed. Please, contact me via e-mail 
> <[alryaz@xavux.com](mailto:alryaz@xavux.com?subject=Elro%20Connects%20Integration)>.


## Contribution
If you found yourself using Wisen application with any of your Smart Home devices, contact me via
e-mail <[alryaz@xavux.com](mailto:alryaz@xavux.com?subject=Hekr%20for%20HomeAssistant%20Contribution)>.
The process of adding new devices is not yet completely formalized, the milestone is set for a release-candidate version.

Check original repository with HekrAPI bindings: [hekrapi-python: Hekr protocol bindings for Python](https://github.com/alryaz/hekrapi-python)

You can also help with translating this component. Fork this repository, make changes to preferred language files in
`custom_components/hekr/translations`, remove the `_remove_me_after_making_translations_or_everything_will_be_replaced`
translation key, and submit a pull request. Alternatively you can send a translation file directly through one of the
communication channels listed at the end of this page.

## Installation

### Home Assistant Community Store

> 🎉  **Recommended installation method.**

[![Open your Home Assistant and open the repository inside Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alryaz&repository=hass-hekr-component&category=integration)

<details>
  <summary>Manually (if the button above doesn't work)</summary>
  To install and set up the integration, follow these steps:
  <ol>
    <li>Install HACS (<a href="https://hacs.xyz/docs/installation/installation/" target="_blank">installation guide on the official website</a>).</li>
    <li>Add the repository to the list of custom repositories:
      <ol>
        <li>Open the main page of <i>HACS</i>.</li>
        <li>Go to the <i>Integrations</i> section.</li>
        <li>Click on the three dots in the upper right corner (additional menu).</li>
        <li>Select <i>Custom repositories</i>.</li>
        <li>Paste into the input field: <code>https://github.com/alryaz/hass-hekr-component</code></li>
        <li>In the dropdown, select <i>Integration</i>.</li>
        <li>Click <i>Add</i>.</li>
      </ol>
    </li>
    <li>Search for <b>Hekr</b> in the integrations search.</li>
    <li>Install the latest version of the component by clicking the <code>Install</code> button.</li>
    <li>Restart the <i>Home Assistant</i> server.</li>
  </ol>
</details>

### Installation from Archive

> ⚠️ **Warning!** This option is **<ins>not recommended</ins>** due to
> the difficulty of keeping the installed integration up to date.

1. Download the [archive with the latest version of the integration](https://github.com/alryaz/hass-hekr-component/releases/latest/download/hekr.zip)
2. Create the folder `custom_components` inside your Home Assistant configuration folder (if it doesn't exist)
3. Create the folder `hekr` inside the `custom_components` folder
4. Extract the contents of the downloaded archive into the `hekr` folder
5. Restart the _Home Assistant_ server

## Supported protocols

- [Power meter protocol](#power_meter_protocol): `power_meter`
- [Power socket protocol](#power_socket_protocol): `power_socket`

## Power meter protocol: `power_meter`
<a name="power_meter_protocol">

![Loaded badges for power meter protocol](https://raw.githubusercontent.com/alryaz/hass-hekr-component-component/master/images/power_meter/badges.png)

_(more screenshots available at: [images/power_meter](images/power_meter))_

### Supported devices
- HIKING DDS238-4W

### Example configuration
```yaml
hekr:
  devices:
    - host: home-power-meter.lan
      device_id: ESP_2M_AABBCCDDEEFF
      control_key: 202cb962ac59075b964b07152d234b70
      protocol: power_meter
      sensors:
        - general
        - detailed
      switches: main_power
```

In this state, the plugin will generate three sensors, all obtained via a single `queryDev` command.
These sensors are:
- `status` - **Status** (whether device reports any kind of errors)
- `current_consumption` - **Current Consumption** (current power consumption in *W*, phase attributes in *kW*)
- `total_consumption` - **Total Consumption** (total energy consumption in *kW/h*).

Also the following sensors are available, but not enabled by default (as they increase the amount of requests required
to poll the device, leading to infrequent, but possible timeouts):
- `general` - **General Information** (spews out all data available from `queryDev` command)
- `detailed` - **Detailed Information** (spews out all data available from `queryData` command)
- `voltage` - **Voltage** (voltage for every available phase, also mean voltage)
- `current` - **Current** (current for every available phase, also mean current)
- `power_factor` - **Power Factor**
- `active_power` - **Active Power**
- `reactive_power` - **Reactive Power**

Recent release added support for switches, but so far there is only one supported:
- `main_power` - **Main Power** (toggles relay power on and off) 

#### Custom sensors, set polling interval and name
```yaml
hekr:
  devices:
    - device_id: ESP_2M_AABBCCDDEEFF
      host: home-power-meter.lan
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

#### Enable `main_power` switch, do not add any sensors
```yaml
hekr:
  devices:
    - device_id: ESP_2M_AABBCCDDEEFF
      host: home-power-meter.lan
      control_key: 202cb962ac59075b964b07152d234b70
      scan_interval:
        seconds: 15
      protocol: power_meter
      sensors: false
      switches:
        - main_power
```

## Power socket protocol: `power_socket`
<a name="power_socket_protocol">

![Loaded switches for power socket protocol](https://raw.githubusercontent.com/alryaz/hass-hekr-component-component/master/images/power_socket/switches.png)

**[Device](https://raw.githubusercontent.com/alryaz/hass-hekr-component-component/master/images/power_socket/device.jpg) | [Board picture](https://raw.githubusercontent.com/alryaz/hass-hekr-component-component/master/images/power_socket/board.jpg)**
<!--_(more screenshots available at: [images/power_socket](images/power_socket))_-->

### Supported devices
- SK-B-03/16A/EU
- 7h sevenON elec
- Sockets that identify themselves as CZ-05

### Example configuration
```yaml
hekr:
  devices:
    - host: tv-power-socket.lan
      device_id: ESP_2M_AABBCCDDEEFF
      control_key: 202cb962ac59075b964b07152d234b70
      protocol: power_socket
```

In this state, the component will generate a single switch (`main_power`) obtained via a
single `Quary` command.

<!-- Unfortunately, they named it Quary, not Query, and I'm equally irked by this -->

## Fetching `device_id` and `control_key` for local setup
The following steps (evidently) assume you already paired target device using Wisen.

### _Integrations_ menu
The easiest way to accomplish this is to begin an integration flow with `account` setup type.

Tick the box `Create notification with device info` during setup, and a persistent notification
will appear containing compatible YAML config.

### _Wisen_ application   (Only Android ! Doesn't work with Apple App anymore)
To obtain `device_id` and `control_key`:
- Open _Wisen_ application
- Open sidebar menu (on the left)
- Select _Management_ menu entry
- Select your device
- Tap device icon at the top 5 times
- A toast notification will appear

### HttpCanary (packet sniffing, Android)
The following tutorial is left for educational purposes / explanation on how protocol decoding was done.

##### Pre-requisites:
- An android device with working Wi-Fi
- Installed _HttpCanary_ application ([Google Play Store link](https://play.google.com/store/apps/details?id=com.guoshi.httpcanary&hl=ru))
- Installed and configured _Wisen_ application ([Google Play Store link](https://play.google.com/store/apps/details?id=me.hekr.hummingbird))
- Configured target device via Wisen application
- Non-isolated access point to communicate with target device

##### Capturing instructions:
1. Open _HttpCanary_ application, and do the following:
   1. ___(required)___ Accept VPN configuration and ___(optional)___ install root certificate
   1. Open `Target Apps` from the side menu
   1. Tap `+` in the top right corner
   1. Search for `Wisen` in the search box, and select _Wisen_ from search results 
   1. Go back to the main screen; you will see _Wisen_'s icon with `Tap the floating button to start capture` text under
      it appear in the middle of your screen. __!!! DO NOT START CAPTURE YET !!!__
1. Force-close and re-open _Wisen_ application, and do the following:
   1. Open `Settings` from the side menu
   1. Open `LAN settings` submenu
   1. Flick the switch to ___on___ position
1. Go back to the _HttpCanary_ application, and start listening by pressing button in the bottom left corner; you will
   now observe `Capturing...` as well as possibly some of cloud Wisen's requests appear on screen; should they not
   appear, go back to _Wisen_ and open up your device from the grid of available devices. After than, enough requests
   will be made to successfully extract needed data.
1. Look for requests with of `WebSocket` type, or `UDP` type to port `10000`. Once you found at least one, open it and
   look for messages containing `ctrlKey` (=`control_key`) and `devTid` (=`device_id`).
   An example response would look something like this, mind the linebreaks:
   ```js
   {
     "msgId": 7,
     "action": "devSend",
     "params": {
       "devTid": "ESP_2M_AABBCCDDEEFF", // This will be your `device_id`
       "appTid": [],
       "subDevTid": null,
       "ctrlKey": "202cb962ac59075b964b07152d234b70", // This will be your `control_key`
       // more data...
     },
     // more data...
   }
   ```
1. __Congratulations, you're ready!__ You can proceed by using any of the configuration methods described above to add
   your device to HomeAssistant.
 
## Author

👤 **Alexander Ryazanov (@alryaz)**

* Github: [@alryaz](https://github.com/alryaz)
* Telegram: [@alryaz](https://t.me/alryaz)
* E-Mail: [alryaz@xavux.com](mailto:alryaz@xavux.com?subject=Hekr%20Component)

Give a ⭐ if this project helped you!

