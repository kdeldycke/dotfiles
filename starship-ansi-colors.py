# Copyright Kevin Deldycke <kevin@deldycke.com> and contributors.
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

"""Convert all hexadecimal color codes from Starship config to ANSI 8-bits codes.

Starship will render colors as-is. So terminal not supporting 24-bits rendering, like
Apple's ``Terminal.app``, are not capable of rendering colors from presets. This
missing feature is actually discussed upstrean in issue:
https://github.com/starship/starship/issues/5048

In the mean time you can use this script, which replaces all ``#RRGGBB`` strings to
their 8-bits ANSI codes.

The result is printed in the terminal, so you can inspect the results, before
eventually overwriting your config with:

..code:: shell-session

    $ python ./starship-ansi-colors.py >> ~/.config/starship.toml

"""

from __future__ import annotations

import os
import re
from math import floor
from pathlib import Path

# Get current configuration location from environment variable, or get the default.
conf_path = (
    Path(os.environ.get("STARSHIP_CONFIG", "~/.config/starship.toml"))
    .expanduser()
    .absolute()
)
assert conf_path.exists(), f"Configuration not found at {conf_path}"
assert conf_path.is_file(), f"{conf_path} is not a file"

conf = conf_path.read_text()
assert conf, f"{conf_path} is empty"


def hex_to_ansi(hex_str: str) -> str:
    """Convert hexadecimal ``#RRGGBB`` color string to 8 bits integer color code.

    This is a crude quantization based on: https://unix.stackexchange.com/a/269085

    A subtler, more accurate color matching can be performed like ``tmux`` does:
    https://github.com/tmux/tmux/blob/master/colour.c#L45-L88
    """
    hex_str = hex_str.lstrip("#")
    assert len(hex_str) == 6

    red = int(f"0x{hex_str[0:2]}", base=16)
    green = int(f"0x{hex_str[2:4]}", base=16)
    blue = int(f"0x{hex_str[4:6]}", base=16)

    def hex_to_int(h: int) -> int:
        return 0 if h < 75 else floor((h - 35) / 40)

    r2, g2, b2 = map(hex_to_int, (red, green, blue))

    ansi = (r2 * 6 * 6) + (g2 * 6) + b2 + 16

    return str(ansi)


# Locate all hexadecimal notations.
colors = {}
for match in re.finditer(r"#[0-9A-Fa-f]{6}", conf):
    hex_color = match.group()
    if hex_color not in colors:
        colors[hex_color] = hex_to_ansi(hex_color)

# Replace all hexadecimal notations to ANSI integer codes.
new_conf = conf
for hex_str, ansi_code in colors.items():
    new_conf = new_conf.replace(hex_str, ansi_code)

print(new_conf)
