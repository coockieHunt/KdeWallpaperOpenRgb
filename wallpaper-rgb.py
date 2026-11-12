import colorsys
import os
import random
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
import json

from PIL import Image

# CONFIG
DEFAULTS = {
    "wall_dir": "/mnt/perso/Images/walpaper",
    "interval": 600,
}
OPENRGB_SERVER = "127.0.0.1:6742"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

CONFIG_DIR = Path.home() / ".config" / "wallpaper-rgb"
CONFIG_FILE = CONFIG_DIR / "state.json"
#
# UTILS
#

# Write a timestamped message to standard output.
def log(message):
    prefix = f"[{time.strftime('%H:%M:%S')}] "
    message = " ".join(str(message).split())
    if sys.stdout.isatty() and "NO_COLOR" not in os.environ:
        prefix = f"\033[90m{prefix}\033[0m"
        if message.startswith("ERROR:"):
            message = f"\033[91mERROR:\033[0m{message[6:]}"
        elif message.startswith("WARNING:"):
            message = f"\033[93mWARNING:\033[0m{message[8:]}"
    sys.stdout.write(prefix + message + "\r\n")
    sys.stdout.flush()

# Run a command log (paarser fix for logging error or stair logging)
def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        output = result.stderr or result.stdout
        output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
        error = next((line.strip() for line in output.splitlines()
                      if line.strip() and "OpenRGB --help" not in line),
                     f"exit code {result.returncode}")
        error = error.removeprefix("Error:").strip()
        log(f"ERROR: {error}")
    return result

def ask(name, cur_value):
    quest = input(f"{name}: ({cur_value}) ").strip()  
    if quest == "":
        return cur_value               
    try:
        return type(cur_value)(quest)  
    except ValueError:
        log(f"WARNING: Invalid value; keeping {cur_value}.")
        return cur_value

def configure():
    cfg = loadConfig()
    for key in cfg:                     
        cfg[key] = ask(key, cfg[key])
    save_config(cfg)
    print("Configuration saved.")

#
# OPEN RGB
#

# send commande on openrgb server
def set_color_raw(r, g, b):
    hex_color = f"{r:02X}{g:02X}{b:02X}"
    run([
        "openrgb", "--client", OPENRGB_SERVER, "--device", "0",
        "--mode", "static", "--color", hex_color,
    ])

# loop for rgb values.
def transition_color(start_rgb, end_rgb, duration=2.0, steps=20):
    if not start_rgb:
        set_color_raw(*end_rgb)
        return

    sleep_time = duration / steps

    for i in range(steps + 1):
        progress = i / steps
        rgb = tuple(
            int(start + (end - start) * progress)
            for start, end in zip(start_rgb, end_rgb)
        )
        set_color_raw(*rgb)
        if i < steps:
            time.sleep(sleep_time)


# check if the OpenRGB server is ready
def openrgb_server_ready():
    host, port = OPENRGB_SERVER.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(port)), timeout=1):
            pass
    except OSError:
        return False

    try:
        result = subprocess.run(
            ["openrgb", "--client", OPENRGB_SERVER, "--list-devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return False

    devices = re.findall(r"^\s*\d+:\s+\S", result.stdout, re.MULTILINE)
    return result.returncode == 0 and bool(devices)


# check if openRgb is run
def ensure_openrgb_server():
    attempts = 20
    log("Check OpenRGB server...")
    if openrgb_server_ready():
        log("OpenRGB server is ok")
        return

    log("WARNING: OpenRGB server is not running; attempting to start it...")
    subprocess.Popen(
        ["sudo", "openrgb", "--server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for attempt in range(1, attempts + 1):
        time.sleep(2)
        log(f"Checking OpenRGB server {attempt}/{attempts}...")
        if openrgb_server_ready():
            log("OpenRGB server is ok.")
            return

    raise SystemExit("ERROR: OpenRGB server is unavailable; wallpaper was not changed.")


# Find the dominant color in an image (ai-coded).
def dominant_color(path):
    image = Image.open(path).convert("RGB").resize((64, 64))
    palette = image.quantize(colors=12).convert("RGB")
    colors = palette.getcolors()
    if not colors:
        raise ValueError(f"No colors found in {path}")

    def color_score(color):
        count, rgb = color
        _, saturation, value = colorsys.rgb_to_hsv(
            *(channel / 255 for channel in rgb)
        )
        return count * saturation * value

    visible_colors = []
    for color in colors:
        _, rgb = color
        _, saturation, value = colorsys.rgb_to_hsv(
            *(channel / 255 for channel in rgb)
        )
        if saturation >= 0.15 and value >= 0.12:
            visible_colors.append(color)

    _, rgb = max(visible_colors or colors, key=color_score)
    return rgb

#
# WALLPAPER
#

# Set the wallpaper.
def set_wallpapers(image_path):
    result = run(["plasma-apply-wallpaperimage", str(image_path)])
    if result.returncode:
        raise SystemExit("ERROR: Wallpaper could not be set; skipping LED update.")
    log("Wallpaper set.")


#
# CONFIG
#

# check if config file exist
def checkIfConfigExist():
    if CONFIG_FILE.exists():
        log("Configuration file found.")
    else:
        log("Configuration file not found.")
        createDefaultConfig()
       

# create config file
def createDefaultConfig():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(DEFAULTS, indent=2))
    log("Configuration file created.")

# load config
def loadConfig():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text()))
    except (OSError, ValueError) as error:
        log(f"WARNING: Could not load configuration; using defaults: {error}")
    return cfg

# save config
def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

# 
# MAIN
# 
def main():
    checkIfConfigExist()

    cfg = loadConfig()
    wall_dir = Path(cfg["wall_dir"])

    log("Starting")
    log(f"Image folder: {wall_dir}")

    last_image = None
    current_rgb = None

    ensure_openrgb_server()

    while True:
        images = [
            path for path in wall_dir.rglob("*")
            if path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not images:
            raise SystemExit(f"ERROR: No images found in folder: {wall_dir}")

        candidates = [path for path in images if path != last_image]
        image_path = random.choice(candidates or images)
        last_image = image_path

        new_rgb = dominant_color(image_path)
        red, green, blue = new_rgb
        log(f"{image_path.name} — LED #{red:02X}{green:02X}{blue:02X}")

        set_wallpapers(image_path)
        transition_color(current_rgb, new_rgb)
        current_rgb = new_rgb

        time.sleep(cfg["interval"] )


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "daemon"

    match cmd:
        case "daemon":
            main()
        case "checkConfig":
            checkIfConfigExist()
        case "config":
            configure()
        case _:
            log(f"ERROR: Unknown command: '{cmd}'.")
            print("Available commands: daemon, checkConfig, config.")
            print("Usage: wallpaper-rgb.py [command]")
