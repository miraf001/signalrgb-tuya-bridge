// SignalRGB add-on: Tuya light through the local Python bridge.
// The bridge listens on UDP 127.0.0.1:8766 and expects: TY + R + G + B.
import udp from "@SignalRGB/udp";

var LightingMode = "Canvas";
var forcedColor = "0099ff";
var brightnessScale = "100";

let frameCounter = 0;
let lastRgb = [-1, -1, -1];
let socket;
const FRAME_SKIP = 15; // About 2 updates/sec at SignalRGB's 30 fps tick.
const MIN_DELTA = 3;

export function Name() { return "Tuya Light Bridge"; }
export function Publisher() { return "miraf001"; }
export function Version() { return "0.2.0"; }
export function Type() { return "network"; }
export function ImageUrl() { return "https://assets.signalrgb.com/brands/tuya/logo.png"; }
export function Size() { return [1, 1]; }
export function DefaultPosition() { return [0, 0]; }
export function DefaultScale() { return 1.0; }

export function ControllableParameters() {
    return [
        { property: "LightingMode", group: "lighting", label: "Lighting Mode", type: "combobox", values: ["Canvas", "Forced"], default: "Canvas" },
        { property: "forcedColor", group: "lighting", label: "Forced Color", type: "color", default: "0099ff" },
        { property: "brightnessScale", group: "lighting", label: "Brightness (%)", type: "number", min: "1", max: "100", step: "1", default: "100" },
    ];
}

export function DiscoveryService() {
    const discovery = this;
    this.Initialize = function() {
        service.log("[Tuya] Registering local bridge device");
        discovery.Discovered({ id: "tuya-local-bridge", name: "Tuya Ceiling Light", bridgeHost: "127.0.0.1", bridgePort: 8766 });
    };
    this.Update = function() {
        for (const controller of service.controllers) {
            if (!controller.obj.announced) {
                controller.obj.announced = true;
                service.announceController(controller.obj);
            }
        }
    };
    this.Discovered = function(value) {
        if (service.getController(value.id) === undefined) service.addController(new TuyaBridge(value));
    };
}

class TuyaBridge {
    constructor(value) {
        this.id = value.id;
        this.name = value.name;
        this.bridgeHost = value.bridgeHost;
        this.bridgePort = value.bridgePort;
        this.announced = false;
    }
}

export function Initialize() {
    device.setName(controller.name);
    device.addChannel("Tuya Light", 1);
    socket = udp.createSocket();
    device.log("[Tuya] Initialized local UDP bridge");
}

export function Render() {
    frameCounter++;
    if (frameCounter < FRAME_SKIP) return;
    frameCounter = 0;

    let rgb;
    if (LightingMode === "Forced") rgb = hexToRgb(forcedColor);
    else rgb = averageCanvas();

    const scale = Math.max(0, Math.min(100, parseInt(brightnessScale) || 100)) / 100;
    rgb = rgb.map((value) => Math.round(value * scale));
    if (Math.max(Math.abs(rgb[0] - lastRgb[0]), Math.abs(rgb[1] - lastRgb[1]), Math.abs(rgb[2] - lastRgb[2])) < MIN_DELTA) return;
    lastRgb = rgb;

    socket.write([0x54, 0x59, rgb[0], rgb[1], rgb[2]], controller.bridgeHost, controller.bridgePort);
}

export function Shutdown() {
    if (socket) socket.close();
}

function averageCanvas() {
    const colors = device.channel("Tuya Light").getColors("Inline");
    if (!colors || colors.length < 3) return [0, 0, 0];
    let r = 0, g = 0, b = 0;
    for (let i = 0; i < colors.length; i += 3) {
        r += colors[i] || 0;
        g += colors[i + 1] || 0;
        b += colors[i + 2] || 0;
    }
    const count = Math.max(1, Math.floor(colors.length / 3));
    return [Math.round(r / count), Math.round(g / count), Math.round(b / count)];
}

function hexToRgb(hex) {
    const value = parseInt(String(hex).replace("#", ""), 16) || 0;
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

