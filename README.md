# SignalRGB Tuya Light Bridge

SignalRGB add-on for the LSC Frameless Ceiling Light RGB+CCT, using the local
Python bridge in the companion project.

## Prerequisite

Run the bridge on the same PC as SignalRGB:

```powershell
py signalrgb_tuya_bridge.py
```

The bridge listens only on `127.0.0.1:8766`. It throttles updates and sends
the resulting colour to Tuya Cloud using the existing local `tinytuya.json`.

## Install

In SignalRGB open Settings → Add-ons → Add-on and paste:

`https://github.com/miraf001/signalrgb-tuya-bridge`

After enabling the add-on, restart or reload SignalRGB. The device should
appear as **Tuya Ceiling Light**. Use the local web controller at
`http://127.0.0.1:8765/` to switch between SignalRGB mode and normal mode.

No Tuya API key, secret, device ID, or local configuration is stored in this
repository.

