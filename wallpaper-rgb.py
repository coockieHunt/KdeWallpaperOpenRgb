import colorsys
import random
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

WALL_DIR = Path("/mnt/perso/Images/walpaper")
INTERVAL = 3000 # default 3000 for 5 minutes
OPENRGB_SERVER = "127.0.0.1:6742"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Log a message with a timestamp.
def log(message):
    prefix = f"[{time.strftime('%H:%M:%S')}] "
    message = " ".join(str(message).split())
    sys.stdout.write(prefix + message + "\r\n")
    sys.stdout.flush()

# Run a command log (parser fix for logging error or stair logging)
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

    log("OpenRGB server not running: starting...")
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

    raise SystemExit("OpenRGB server is unavailable; wallpaper was not changed.")


# Find the dominant color in an image (ai-coded).
def dominant_color(path):
    image = Image.open(path).convert("RGB").resize((64, 64))
    palette = image.quantize(colors=12).convert("RGB")
    colors = palette.getcolors()
    if not colors:
        raise ValueError(f"not color found {path}")

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

# Set the wallpaper.
def set_wallpapers(image_path):
    result = run(["plasma-apply-wallpaperimage", str(image_path)])
    if result.returncode:
        raise SystemExit("wallpaper not set skipping led")
    log("Wallpaper set.")


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

# main loop
def main():
    log("Starting")
    log(f"img folder: {WALL_DIR}")

    last_image = None
    current_rgb = None

    ensure_openrgb_server()

    while True:
        images = [
            path for path in WALL_DIR.rglob("*")
            if path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not images:
            raise SystemExit("not found img in folder")

        candidates = [path for path in images if path != last_image]
        image_path = random.choice(candidates or images)
        last_image = image_path

        new_rgb = dominant_color(image_path)
        red, green, blue = new_rgb
        log(f"{image_path.name} — LED #{red:02X}{green:02X}{blue:02X}")

        set_wallpapers(image_path)
        transition_color(current_rgb, new_rgb)
        current_rgb = new_rgb

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()