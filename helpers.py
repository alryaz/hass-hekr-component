"""Some helpers"""

def power_meter_attribute_filter(attributes:dict) -> dict:
    consumption = round(attributes.get("current_energy_consumption", 0) * 1000, 1)
    attributes["current_energy_consumption"] = consumption

    if "phase_count" in attributes:
        attributes = {
            attribute: value
            for attribute, value in attributes.items()
            if not (
                attribute[-2:-1] == '_'
                and attribute[-1:].isnumeric()
            )
            or int(attribute[-1:]) <= attributes['phase_count']
        }
    
    attributes['total_current'] = sum([
        value for attribute, value in attributes.items()
        if attribute[:-2] == "current"
    ])
    voltages = [
        value for attribute, value in attributes.items()
        if attribute[:-2] == "voltage" and value
    ]
    attributes['mean_voltage'] = float(sum(voltages))/len(voltages)
    
    return attributes
            