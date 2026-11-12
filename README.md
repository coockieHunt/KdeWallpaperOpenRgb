# KDE Wallpaper + OpenRGB

> A small script for a desktop that likes its colors in sync.
>
> It picks a wallpaper, finds a color in the image, and brings an OpenRGB
> device along for the ride. Made for my setup; a little Linux tinkering may
> be needed to make it feel at home on yours.

## What it does

- Looks for JPG, JPEG, PNG, and WebP images in a wallpaper folder, including its subfolders.
- Picks a random image, avoiding the previous one when possible.
- Applies it as the KDE Plasma wallpaper.
- Extracts a prominent, reasonably vivid color from the image and sets an OpenRGB device to match.
- Fades between colors, then waits before picking the next wallpaper.

## Requirements

- Linux running KDE Plasma
- Python 3.10 or newer
- [Pillow](https://python-pillow.org/)
- OpenRGB and its `openrgb` command-line tool
- An OpenRGB-compatible device

The script uses `plasma-apply-wallpaperimage` to set the wallpaper and connects
to the OpenRGB server at `127.0.0.1:6742`. If the server is not already
available, it tries to start it with `sudo openrgb --server`, which may ask for
your password.

## Install and run

Install the Python dependencies, then start the script:

```bash
python3 -m pip install -r requirements.txt
python3 wallpaper-rgb.py
```

Keep the script running to continue changing wallpapers and colors. Stop it with
`Ctrl+C`.

## Configuration

On first run, the script creates `~/.config/wallpaper-rgb/state.json` with
these default settings:

```json
{
  "wall_dir": "/mnt/perso/Images/walpaper",
  "interval": 600
}
```

- Set `wall_dir` to the folder containing your wallpapers.
- `interval` is in seconds. The default value, `600`, means 10 minutes.
- Change `OPENRGB_SERVER` near the top of `wallpaper-rgb.py` if your server
  uses a different address or port.

Run `python3 wallpaper-rgb.py config` to change the settings interactively.
The script currently controls OpenRGB device `0`. If that is not the device you
want, change the `--device` value in `set_color_raw()` to the device number
shown by `openrgb --list-devices`.

## Troubleshooting

- **No images found:** Check that `wall_dir` exists and contains supported image
  files.
- **Wallpaper does not change:** Make sure you are running KDE Plasma and that
  `plasma-apply-wallpaperimage` is available.
- **OpenRGB is unavailable:** Start the OpenRGB server and check that the
  address in `OPENRGB_SERVER` is reachable. The selected device must be
  supported and available to OpenRGB.

## License

This project is released under the [MIT License](./LICENSE).
