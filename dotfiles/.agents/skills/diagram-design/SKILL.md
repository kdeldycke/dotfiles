---
name: diagram-design
description: Load at the start of any task whose deliverable is a diagram or a page that draws one, in HTML, SVG or Mermaid, like a network, zone, flow or architecture diagram. Gives the house visual conventions for edges, shared lines, labels, regions, chips, badges and icons, the layout method, and the render checks that keep boxes apart at every window width.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
argument-hint: '[path/to/page.html]'
---

# Diagram design

These rules come from the user's reviews of earlier diagrams. Apply all of them to a new diagram, and check each one before you report the diagram as done.

## Content

- Keep the diagram sparse. Exact values (ports, addresses, SSIDs, versions) go in a table beside it, and the diagram links each box to its row by name. When the user says a diagram is busy, move details to the table first.
- Draw what is allowed. State once, in the legend, that anything without an edge is blocked. Draw a blocked flow only in a diagram that must show blocks, like Mermaid notes: red, with the word "blocked" in its label for readers who cannot tell colors apart.
- An edge joins exactly what its rule joins: a rule for a whole group ends on the group's box, an exception for one member ends on that member's box.
- Rules that are independent stand apart, each on its own edge. Stacked in one column, they read as a sequence of steps.

## Edges

- Each edge runs from a small circle at its source to an arrowhead at its target. Center the circle on the source box's border. The arrowhead's tip touches the target box's border.
- Color each edge by its verdict: green for allowed, grey and dashed for planned or off (dotted in Mermaid), red for blocked where blocks show. Never end an edge in a cross.
- An arrowhead touches the straight part of a border, never a rounded corner. Keep it at least the corner radius plus half the arrowhead's height from the box's top and bottom, or the arrow looks like it floats.
- When an edge crosses one border to reach a box inside it, leave at least 8 pixels between the arrowhead's base and the crossed border.
- Arrows that belong together sit level: an arrow out of a region lines up with the arrow into it from the other side.

## Shared lines and tracks

- The rules that leave one source toward the same group share one line that branches to each target, with a dot at each branch. Draw the line in pieces between branches: a piece that carries planned rules only is dashed. A dot is green where two allowed ways part, and grey where only a planned way leaves the line.
- Hover a source: its whole shared line stays lit, dots included. Hover a target: only its own path stays lit, with no dot, since one path has no branch, and in the style of its rule, so a planned rule's path is dashed up to its source. A redraw keeps the hover state.
- Route edges orthogonally, in a channel between groups. Give each shared line a track: first minimize the verticals that cross another line, then the number of tracks.
- Order the members of a row the same way: try each order, up to 5 members, and keep the one whose lines cross least, then the one with the fewest tracks. A tie keeps the order of the source file.
- Two lines whose spans do not overlap, with at least 10 pixels between them, share one track, so their horizontal parts align. Size the channel from its track count.
- Spread the ports along a box side, ordered by where the other end of each line is.

## Labels

- Put each label beside its branch, near the arrowhead first, then along the branch, then along the shared line. A rule with a line of its own may also take a spot by its circle.
- When no spot is clean, a label breaks onto two lines at its first colon or comma, or steps 12 or 24 pixels further out to clear a line beside its branch.
- Score candidate spots, and take the one that touches the fewest lines, boxes and borders. A label never sits on a region's border, with a margin of 7 pixels.
- Give label text a halo in the page's background color (`paint-order: stroke`), so a line under it does not cut through the glyphs.

## Shapes and regions

- A box is something the reader owns or manages. Something outside, like the internet, is not a box: draw a borderless tint that fades out toward the page's edge and at both ends. Keep its side that faces the arrows sharp, so the arrows touch it.
- A container, like a zone, holds its members as small boxes: a name line, then a detail line.
- A tunnel inside a link is a double-bordered tube inside the link's box. The edge that leaves the tunnel for its far end is a double line in the tube's color, since its traffic stays encrypted until there.
- Planned members get a dashed grey border.
- Sections of one device are split by dotted lines that run from one border to the other, with no margin. Dashed lines mean planned, so they never split sections.

## Text, chips, badges and icons

- A chip (pill) holds a token that recurs across rows or cards, like a network name or a verdict category. Free text stays plain, one note per line, without color.
- A bulleted list inside a box has its bullets on the left edge of the box's heading: draw the bullets with `::before`, with `list-style: none` and no list padding.
- A badge that numbers an open item is a circle, not a pill: in a grid cell, set `justify-self: start` so the cell does not stretch it. Use `font-variant-numeric: tabular-nums`, so the digit sits in the middle.
- Icons carry facts: an SSID, a port, PoE, a tunnel, a WAN, a DNS block. A clock marks a date to renew by, like a key or a certificate that expires. An hourglass marks a time limit, like a voucher's length. Every icon has an entry in the legend.
- Define every color as a token on `:root`, with a dark set, and check both themes.

## Links

- A name elsewhere on the page that also has a box in the diagram, like a network's pill in a card, scrolls to that box on a click and lights it, until the next click or Escape. A hover there would light things out of sight.
- A name of a managed object, like an SSID, a network or a VPN client, links to its settings page in the device's UI, in a new tab, with a dotted underline. Read the routes from the UI's own scripts before you link: never guess a URL. Link to the list page when the edit panel opens through query parameters you cannot test.
- A link that leaves the page ends with an arrow-out-of-a-box icon, drawn by `a[href^="http"]::after` as a mask in `currentColor`.
- A numbered badge is a link to its open item. The item takes a tint while it is the `:target`, and has a `scroll-margin` that brings it to mid-screen.

## Layout

- Lay out by rows or lanes: one container per row, its members placed by script. Put a member over the mean of the members it has rules with, and put members with no rule at the row's end.
- Boxes never overlap, at any window width. Choose the layout by measurement, never by a fixed breakpoint:
  1. Side by side, when every row leaves at least 20 pixels between its boxes.
  2. Else narrowed: each box breaks its detail line after its first colon or comma.
  3. Else stacked: one column, and each channel lists its rules in words.
- Ship the page in the stacked layout, and let the script switch it: without the script, the reader still gets every rule in words.
- Draw once, in the same task as the script loads, then again on `resize` and `document.fonts.ready`. A headless browser can skip `requestAnimationFrame`, so never make the first draw wait for it.

## Choosing a layout

When the user asks for options, or calls a layout busy, build a gallery of at least 20 variants from different placement methods: Graphviz `dot` and `neato` (read positions from `-Tjson`), ELK layered with `INCLUDE_CHILDREN` (child positions are relative to the parent), and hand-placed rows with shared lines. Show each variant with the same content, and let the user choose.

## Checks

Run `scripts/render_probe.py` on the page before you report it:

```bash
uv run --script scripts/render_probe.py {page.html} --boxes '.node' --out {scratch dir}
```

Run it with the sandbox off: Chromium does not start inside the Bash sandbox. It renders the page in headless Chromium at widths from 1200 to 1920 pixels, in light and dark themes, saves a screenshot of each, and prints the layout mode, any pair of overlapping boxes, and any horizontal overflow. Then read the screenshots at the user's likely widths (1440, 1512, 1728) and in dark mode, and hover one member to check what lights up.

Open the page in an installed browser (`open -a Safari {page.html}`). Never publish it to a hosted service when the user keeps its canonical copy elsewhere.
