# MooresCloud Holiday – Home Assistant Integration

A custom integration that lets Home Assistant control the [MooresCloud Holiday](http://www.moorescloud.com/) light strip (50 individually-addressable WS2812 RGB globes) over its built-in IoTAS REST API.

---

## Features

| Feature | Notes |
|---|---|
| On / Off | All globes on or off |
| RGB colour | Applied to all 50 globes simultaneously |
| Brightness | Scales the chosen colour |
| Effects | Gradient Warm, Gradient Cool, Rainbow, Candle |
| `set_pattern` service | Set each of the 50 globes to a different colour |
| Developer Mode switch | Toggle the Holiday's SSH/developer mode |

---

## Requirements

- Home Assistant 2024.1 or later
- MooresCloud Holiday on the same LAN (reachable by hostname or IP)
- The Holiday's web interface running on port 80 (default)

---

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → *Custom repositories*
2. Add this repo URL and select **Integration**
3. Search for "MooresCloud Holiday" and install
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/moorescloud_holiday/` directory into your
   `<config>/custom_components/` folder.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **MooresCloud Holiday**
3. Enter:
   - **Hostname or IP** – e.g. `holiday-ab1c2d` or `192.168.1.42`
   - **Port** – leave as `80` unless you've changed it
   - **Name** – friendly name shown in HA

The integration will ping the device; if it can't connect it will show an error.

---

## Usage

### Standard light controls

The Holiday appears as a standard HA light entity. You can:

```yaml
# Turn on to a solid red at 50% brightness
service: light.turn_on
target:
  entity_id: light.holiday
data:
  rgb_color: [255, 0, 0]
  brightness: 128
```

```yaml
# Activate the Rainbow effect
service: light.turn_on
target:
  entity_id: light.holiday
data:
  effect: Rainbow
```

Available effects: `Gradient Warm`, `Gradient Cool`, `Rainbow`, `Candle`

The integration also exposes a **Developer Mode** switch for the device. This
controls the Holiday's SSH/developer mode and should normally remain off.

### set_pattern service

Set every globe individually with the `moorescloud_holiday.set_pattern` service:

```yaml
service: moorescloud_holiday.set_pattern
target:
  entity_id: light.holiday
data:
  lights:
    - "#ff0000"   # globe 1 – red
    - "#00ff00"   # globe 2 – green
    - "#0000ff"   # globe 3 – blue
    # ... up to 50 entries; shorter lists are padded with black
```

### Automation example – turn on at sunset

```yaml
automation:
  trigger:
    platform: sun
    event: sunset
  action:
    service: light.turn_on
    target:
      entity_id: light.holiday
    data:
      effect: Gradient Warm
      brightness: 200
```

---

## API notes

The integration uses the Holiday's **IoTAS REST API** (not the UDP Secret API):

| Endpoint | Method | Purpose |
|---|---|---|
| `/iotas/0.1/device/moorescloud.holiday/localhost/setlights` | PUT | Set each globe individually |
| `/iotas/0.1/device/moorescloud.holiday/localhost/gradient` | PUT | Fade across the string |

The Holiday must be on the same network as Home Assistant and accessible via HTTP on port 80.

---

## Troubleshooting

**"Cannot connect" during setup**
- Ping the Holiday from your HA host: `ping yourholidayname`
- Check the Holiday is powered on and connected to Wi-Fi
- Try using the IP address instead of the hostname

**Lights don't respond after setup**
- Check `Settings → System → Logs` for errors from `moorescloud_holiday`
- Ensure nothing else is sending conflicting commands to the Holiday

**Effects look wrong / stuttery**
- The gradient endpoints on the Holiday do not cancel previous gradients. Use solid-colour `set_lights` calls (what the `Rainbow` / `Candle` effects do) for instant updates.

---

## Licence

MIT
