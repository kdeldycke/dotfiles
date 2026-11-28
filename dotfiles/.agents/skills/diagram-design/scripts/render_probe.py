#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Render an HTML page in headless Chromium at several widths, in both themes.

Saves a screenshot of each render, and prints the boxes that overlap and any
horizontal overflow. Exits with 1 when a render has either. The page is copied,
with a probe script and a `<base>` that points at its own folder, into the output
folder: the page's folder gets no file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CHROMIUM = os.environ.get(
    "CHROMIUM", "/Applications/Chromium.app/Contents/MacOS/Chromium"
)
WIDTHS = [1200, 1366, 1440, 1512, 1600, 1680, 1728, 1760, 1920]

PROBE = """<script>
setTimeout(() => {
  const boxes = [...document.querySelectorAll(BOXES)]
    .map((el) => [el, el.getBoundingClientRect()])
    .filter(([, r]) => r.width && r.height);
  const name = (el) =>
    el.dataset.node || el.id || el.textContent.trim().slice(0, 24);
  const overlaps = [];
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const [a, p] = boxes[i], [b, q] = boxes[j];
      if (a.contains(b) || b.contains(a)) continue;
      const hit = p.left < q.right && q.left < p.right
        && p.top < q.bottom && q.top < p.bottom;
      if (hit) overlaps.push(`${name(a)} / ${name(b)}`);
    }
  }
  const mode = MODE ? document.querySelector(MODE)?.className : null;
  const overflow = document.documentElement.scrollWidth - innerWidth;
  const result = {overflow, mode, boxes: boxes.length, overlaps};
  console.log("PROBE " + JSON.stringify(result));
}, 1500);
</script>"""


def render(copy: Path, shot: Path, width: int, height: int, setting: int) -> str:
    """Render the copy once, and return Chromium's log, which holds the probe's line."""
    run = subprocess.run(
        [
            CHROMIUM,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--blink-settings=preferredColorScheme={setting}",
            f"--user-data-dir={shot.parent / 'profile'}",
            f"--window-size={width},{height}",
            "--virtual-time-budget=5000",
            "--enable-logging=stderr",
            "--v=0",
            f"--screenshot={shot}",
            copy.as_uri(),
        ],
        capture_output=True,
        text=True,
        encoding="UTF-8",
        timeout=120,
        check=False,
    )
    return run.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("page", type=Path)
    parser.add_argument(
        "--boxes", default=".node", help="selector of the boxes that must not overlap"
    )
    parser.add_argument(
        "--mode", default="", help="selector of the element whose classes name the mode"
    )
    parser.add_argument("--widths", type=int, nargs="+", default=WIDTHS)
    parser.add_argument("--height", type=int, default=2400)
    parser.add_argument(
        "--out", type=Path, required=True, help="folder for the copy and screenshots"
    )
    args = parser.parse_args()

    page = args.page.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    source = page.read_text(encoding="UTF-8")
    probe = PROBE.replace("BOXES", json.dumps(args.boxes))
    probe = probe.replace("MODE", json.dumps(args.mode))
    base = f'<head><base href="{page.parent.as_uri()}/">'
    source = re.sub(r"<head>", base, source, count=1)
    copy = args.out / f"{page.stem}-probe.html"
    copy.write_text(source.replace("</body>", probe + "</body>"), encoding="UTF-8")

    failed = False
    for theme, setting in (("light", 1), ("dark", 0)):
        for width in args.widths:
            shot = args.out / f"{page.stem}-{theme}-{width}.png"
            log = render(copy, shot, width, args.height, setting)
            found = re.search(r'PROBE (\{.*\})", source', log)
            if not found:
                print(f"{theme} {width}: no probe result")
                failed = True
                continue
            result = json.loads(found.group(1))
            failed |= bool(result["overlaps"] or result["overflow"] > 0)
            print(
                f"{theme} {width}: mode {result['mode']}, {result['boxes']} boxes, "
                f"overflow {result['overflow']}px, "
                f"overlaps {result['overlaps'] or 'none'}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
