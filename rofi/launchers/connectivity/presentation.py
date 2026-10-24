"""Compact, user-facing connection labels; no networking side effects.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""


def connected_text(count):
    return "Devices unavailable" if count is None else f"{count} connected"


def security_text(kind):
    return {"open": "Open", "wpa-psk": "Secured", "sae": "WPA3", "enterprise": "Enterprise", "owe": "Enhanced open", "wep": "Legacy WEP"}.get(kind, "Secured")


def client_name(entry):
    name = entry.get("name")
    if name and name != "Connected device":
        return name
    return entry.get("ip") or "Device · " + entry["mac"][-5:].upper()


def signal_icon(signal):
    level = "none" if signal is None else "excellent" if signal >= -50 else "good" if signal >= -60 else "ok" if signal >= -70 else "weak"
    return f"network-wireless-signal-{level}-symbolic"


def elapsed_text(seconds):
    minutes, seconds = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m" if minutes else f"{seconds}s"
