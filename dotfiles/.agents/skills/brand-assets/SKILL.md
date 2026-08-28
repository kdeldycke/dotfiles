---
name: brand-assets
description: Create project logo and banner SVGs, then export them to light and dark PNG variants. Use when you design a logo or banner, or regenerate the PNGs from their SVG source files.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
argument-hint: '[path/to/assets or SVG file]'
---

# Project Logo and Banner Assets

Create, maintain, and export project logo and banner assets as SVGs with light/dark PNG variants.

The Sphinx side of the convention (`html_logo`, `html_favicon`, `ogp_image` paths and the rules around them) lives in `.claude/agents/sphinx-docs.md` § `docs/conf.py` hygiene › Theme assets and OpenGraph. When this skill writes a new asset path into `docs/conf.py`, follow the canonical paths defined there: `assets/logo-square.svg`, `assets/favicon.svg`, `assets/banner-social-light.png`.

## Asset variants

Every project produces four SVG variants, each with light and dark PNG exports:

1. **Favicon** (`favicon.svg`): The project icon only, no text, no margins. Tight-cropped to the icon's bounding box. Used as `html_favicon` in Sphinx and as the browser tab icon. Transparent background. Does not need PNG exports (browsers handle SVG favicons natively). If the mark itself is theme-invariant (flat, unoutlined — see "Isometric / faceted marks" below), the same source also serves any platform app-icon bundle (`.ico`, `.icns`, a build tool's icon input) with a single rendering: a browser tab and a dock are surfaces with no theme this script can query, and a mark with no outline needs no dark variant to stay legible on either.

2. **Square logo** (`logo-square.svg`): The project icon with the project name centered below it. Used as the Sphinx sidebar logo (`html_logo`). Transparent background. The viewBox is taller than the icon to accommodate the text below.

3. **Banner** (`logo-banner.svg`): Horizontal layout with the icon on the left, project name and tagline to the right. Transparent background. Used in the GitHub readme.

4. **Social banner** (`banner-{style}.svg`): Same layout as the banner but with a decorative opaque background (e.g., marble veins, gradients, wave patterns). Used for OpenGraph/social previews. Opaque background.

Each SVG produces two PNGs: `{name}-light.png` and `{name}-dark.png`. The favicon is SVG-only (no PNG exports needed).

## Incremental mode

When base SVGs already exist (at least a square logo or banner), skip any interactive menu and proceed directly:

1. Scan the assets directory for existing SVGs and PNGs.
2. Compare against the four expected variants and their PNG exports.
3. Fill every gap: create missing SVGs (favicon from the icon, social banner from the banner), generate missing PNGs, and rename misnamed files to match the naming conventions below.
4. Wire any new assets into `docs/conf.py` if not already configured.

Only ask the user a question when the gap analysis is genuinely ambiguous (multiple competing icon sources, unclear which element is the project icon).

## Redesigning an existing mark

Revising the *treatment* of a mark that already has SVG sources — outlined vs flat, how many shading planes, how a cutout gets painted — is a different exercise from Design exploration below, which assumes no SVG exists yet. It still deserves the same breadth before committing to a direction, and it must be judged on both themes at once: a treatment that reads fine on white can fail outright on near-black (see "Isometric / faceted marks" below for why an outlined mark is especially prone to this).

Render a contact sheet of candidates, each shown on **both** light and dark backgrounds side by side, plus small thumbnails (16/24/32/48px) next to the full-size renders. Reviewing every candidate at working size and at icon size in one image is what catches a treatment that reads well full-size and turns to mush at 16px, or that loses a plane's contrast on one theme while looking fine on the other — a theme-specific failure is easy to miss when a candidate is only ever shown on the theme you happen to be looking at. Ten to fourteen candidates is a reasonable spread per round; expect two rounds in practice, one for the coarse direction and a second to refine the winner's remaining open question (how a void or cutout inside the mark gets treated, for instance).

Once a direction is picked, "Isometric / faceted marks" below covers the specific techniques — flat plane shading, a computed midpoint color, painting a void behind a cutout, keeping a terminal rendition in sync — that this kind of redesign usually needs.

## Design exploration

When creating assets for a new project with no existing SVGs, start with a broad exploration phase to find a visual direction before refining.

### Phase 1: Generate candidates

Prompt pattern:

> Create several PNG versions of \{base-svg} but with different abstract backgrounds (curvy, bitmap, slopes, splines, gradients, noise, halftone, topographic, marble, waves, geometric, etc). Generate 30 of them, all singularly different, so I can choose a direction. Place them in \{assets-dir}.

Use `rsvg-convert` or a Python script (Pillow) to composite the base SVG over programmatically generated backgrounds. Number each output `banner-{nn}-{descriptor}.png` (e.g., `banner-12-wind-lines.png`, `banner-27-marble-veins.png`).

### Phase 2: Pick a direction

The user reviews the candidates and picks one or more to refine. Delete the rest.

### Phase 3: Refine to SVG

Recreate the chosen design as a clean, hand-authored SVG:

- Use CSS classes for all themed colors (no inline `style` attributes).
- Keep the SVG source in light-mode only (no `@media` queries).
- Trace decorative elements from the raster reference if needed (see "Reverse-engineering raster to SVG" below).

## Naming conventions

- `{name}.svg` is the canonical source (always renders in light mode).
- `{name}-light.png` is the light-theme PNG export.
- `{name}-dark.png` is the dark-theme PNG export.

## Color themes

SVGs use CSS classes for themed properties (fills, strokes). To export a themed PNG:

1. Read the SVG and identify all CSS classes and their light-mode values.
2. Build a replacement `<style>` block with dark-mode colors swapped in.
3. Write a temporary SVG with the baked style.
4. Convert to PNG with `rsvg-convert`.
5. Delete the temporary SVG.

**Key substitutions on the whole CSS declaration, never on the bare color.** A mark that uses a brand color as a literal fill (a flat isometric plane, an icon's own stroke) and a themed element using the *same* hex (lettering, a caption) look identical to a substitution keyed on the color alone: it has no way to tell "this should flip" from "this should stay put," and repaints both. Key each entry of the substitution map on the full declaration — `.word{fill:#2d2364}` → `.word{fill:#d3d3f6}` — never on `#2d2364` → `#d3d3f6` in isolation, so a class rule the mark itself owns can never match. This is easy to get away with for a while: an outlined mark that only uses a color for its *stroke* is safe under a bare-color swap, because nothing else in the file happens to share that stroke's exact hex. The moment the mark's faces start declaring that same hex as a literal `fill` (the flat-shading style below), the identical swap starts repainting the mark along with whatever else used to be the only thing carrying that color.

Typical light/dark color pairs (Tailwind Slate palette):

| Role       | Light     | Dark      |
| ---------- | --------- | --------- |
| Frame/ring | `#334155` | `#94A3B8` |
| Handle out | `#334155` | `#94A3B8` |
| Handle in  | `#475569` | `#CBD5E1` |
| Title text | `#1E293B` | `#F1F5F9` |
| Tagline    | `#64748B` | `#CBD5E1` |
| Background | `#F8FAFC` | `#0F172A` |
| Vein light | `#e2e8ef` | `#1a2535` |
| Vein dark  | `#c6cfda` | `#253040` |

## Isometric / faceted marks

A mark built from isometric solids (boxes, cubes, prisms) reads correctly with flat, unoutlined faces — one color per plane the light can catch, and the eye reconstructs the shape from the pattern of values alone, the way a game sprite does. This is the fix when a stroked version of the same mark fails on a dark background: an outline drawn in the dark brand color has nothing to contrast against near-black, so the silhouette dissolves at its edges while anything drawn with a plain *fill* (lettering, other flat elements) stays perfectly legible beside it. If a themed mark loses its edges on one background but not the other, that mismatch is usually the tell that it wants flat shading instead of an outline, not a different dark-mode color for the same stroke.

**Three planes need three values.** A glance at an isometric solid shows at most three faces: one lit from above, and two vertical faces turned away from each other. Two brand colors are not enough on their own for that third plane, and the honest way to produce a third value without expanding the palette is the arithmetic midpoint of the other two, computed per channel and enforced with a test rather than hand-picked:

```python
mid = "#{:02x}{:02x}{:02x}".format(
    *((int(ink[i : i + 2], 16) + int(wash[i : i + 2], 16)) // 2 for i in (1, 3, 5))
)
```

That keeps the palette "two colors and a derivation" instead of three unrelated choices, and a test that recomputes the midpoint from the two brand constants and compares it against the shipped one catches drift the moment someone nudges the third value by eye instead of by formula.

**Discovering which path is which plane.** When the source SVG is already a flat list of `<path>` elements with no naming that says what each one draws, recolor every path a distinct hue (step through HSV, one hue per path index) and render at a readable size. The rainbow render makes the plane each path belongs to obvious at a glance, so the mapping from path index to plane becomes a literal fact to hard-code once, rather than something re-derived by eye on every future edit.

**Filling a void inside the silhouette.** A mark with a cutout (an open lid, a ring) that used to hide the gap behind an outline needs the interior actually painted once the outline is gone, or the void reads as a hole rather than as depth. Compute the interior walls from vertices the exterior geometry already has (the rim of the opening), draw each wall at its full extent, and clip it to the rim polygon with `<clipPath>` — that avoids hand-computing where two walls intersect, since the clip does the trimming for free. Critically, an interior wall is lit as the plane it *faces*, not the plane it sits *behind*: the wall on the far side of a left-facing opening itself faces right, and so takes the right-plane color, mirrored from what a same-side exterior face would show. Getting this backwards makes any object floating inside the void blend into the wall directly behind it on one of its own faces; getting it right guarantees every face of that object lands on the tone opposite whatever sits behind it.

**Keep a terminal or block-character rendition in sync with the same source.** If the project also ships a low-resolution rendition of the mark (half-block terminal art for a CLI's `--version` banner, an ASCII favicon), derive its interior detail from the SVG rather than hand-tuning it: for every grid cell not already covered by the silhouette, test its center point against the source's rim polygon — in the SVG's own coordinate space, not pixel space — with a standard point-in-polygon test, and fill it only when the test passes. Symmetrize by testing a cell together with its mirror (fill both if either passes) rather than trusting the sampling grid to be perfectly centered: a rounding error in the grid math is a far easier way to end up asymmetric than the source geometry itself. This is what keeps two renditions of "the same" mark from drifting into two different designs over time.

## Backgrounds

- **Transparent background** (default for logo-square and logo-banner): Do not add a `<rect>` background. The PNG will have alpha transparency, suitable for overlaying on any surface.
- **Opaque background** (for social banners): The SVG has a background `<rect>` with a `.bg` class. Swap its fill color for the target theme. Both light and dark PNGs get their respective solid background.

## Conversion tool

Use `rsvg-convert` (from librsvg):

```shell-session
$ rsvg-convert -o output.png input.svg
```

If `rsvg-convert` is unavailable, fall back to `inkscape --export-type=png --export-filename=output.png input.svg`.

## Export workflow

1. **Discover SVGs.** If `$ARGUMENTS` is a directory, find all `.svg` files in it. If it's a specific file, use that. Default to `docs/assets/`.

2. **For each SVG**, read it and identify:

   - All CSS classes and their current (light-mode) values.
   - Whether a background `<rect>` with `.bg` class exists (opaque) or not (transparent).

3. **Generate light PNG.** The SVG already has light-mode styles, so convert directly:

   - If transparent: `rsvg-convert -o {name}-light.png {name}.svg`
   - If opaque: convert as-is (the `.bg` rect has the light fill).

4. **Generate dark PNG.** Create a temporary SVG with dark-mode colors:

   - Replace the `<style>` block with dark-mode values.
   - If opaque, the `.bg` fill is swapped to the dark background color.
   - Convert the temp SVG, then delete it.

5. **Report** the generated files and their sizes.

## Rules

- Never modify the source `.svg` files. Only create temporary copies for baking.
- Always clean up temporary SVGs after conversion.
- SVG source files must NOT contain `@media (prefers-color-scheme: dark)` blocks. Light-mode styles are the only styles in the SVG. Dark mode is handled exclusively through baked PNG exports.
- Give every themed element its own explicit class, even one reused nowhere else (lettering, a caption). A migration or bake step that identifies "themed" nodes by stripping inline paint off wrapper `<g>` elements will also strip color from any child that was relying on inherited fill instead of a class of its own, silently turning it black.
- The font stack for text elements is: `'Inter', 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif`.
- When creating new SVGs, use the Tailwind Slate palette for all grays and the same `radialGradient` for the lens glass.

## Sphinx integration

### `docs/conf.py`

Wire the assets into the Furo theme:

```python
html_logo = "assets/logo-square.svg"
html_favicon = "assets/favicon.svg"
html_theme_options = {
    "sidebar_hide_name": True,
    # ...
}
```

- `html_logo`: Points to the square logo (with project name baked in). Combined with `"sidebar_hide_name": True` to avoid a duplicate auto-generated name below the SVG.
- `html_favicon`: Points to the icon-only favicon (no text, tight crop).

### Hiding the readme banner in Sphinx

The readme includes a centered banner image (`logo-banner.svg`) for GitHub. When the readme is included in the Sphinx front page via `{include}`, the banner is redundant with the sidebar logo. Hide it with custom CSS:

`docs/_static/custom.css`:

```css
/* Hide the readme banner on the Sphinx front page (logo already in sidebar). */
article p[align="center"]:has(img[alt="Project Name"]) {
    display: none;
}
```

Wire it in `conf.py`:

```python
html_static_path = ["_static"]
html_css_files = ["custom.css"]
```

Replace `"Project Name"` with the actual `alt` text of the banner `<img>` in the readme.

## Reverse-engineering raster to SVG

When a design exists only as a raster image (PNG/JPEG) and needs to be reproduced as a clean SVG, use pixel analysis to extract geometry and colors.

### General approach

1. **Identify the background color.** Sample pixels in a known empty region. This establishes the threshold for separating foreground elements from background.

2. **Scan for foreground features.** Using Pillow + NumPy, iterate over the image in slices (vertical columns for horizontal features, horizontal rows for vertical features). At each slice, threshold grayscale values to find pixels that differ from the background.

3. **Cluster pixels into distinct elements.** Group adjacent foreground pixels within a slice. A gap larger than 3-5px indicates a separate element. For each cluster, record:

   - Center position (x, y)
   - Thickness (extent of the cluster)
   - Color (sample the middle pixel's RGB)

4. **Trace paths across slices.** Match clusters across adjacent slices by proximity to build continuous paths. Each path becomes a series of (x, y) sample points.

5. **Fit SVG paths.** Convert the sampled points into SVG cubic bezier curves:

   - Use `C` (cubic bezier) for the initial segment.
   - Use `S` (smooth cubic bezier) for continuations. Each `S` needs 4 coordinates (control point + endpoint); fewer causes the path to terminate early.
   - Extend paths past the viewBox edges (e.g., `x=-20` and `x=1300` for a 1280-wide image) so lines reach the borders cleanly.

6. **Assign colors.** Group paths by sampled RGB values. Create CSS classes for each distinct color and assign them to the corresponding paths.

### Practical tips

- **Avoid interference zones.** Skip regions occupied by text or logos when scanning. Sample from clear areas (edges, corners) and interpolate through occluded zones.
- **Loosen thresholds iteratively.** Start with a tight threshold (e.g., grayscale < 225) to find the most prominent features, then widen (< 234) to catch subtler ones.
- **Validate element counts.** Check that the same number of elements appear at multiple x positions. Inconsistencies indicate threshold issues or interference from other content.
- **Check for uniform color.** In many designs, decorative elements share one or two colors. Confirm by sampling at multiple positions before creating unnecessary CSS classes.
- **Anti-aliasing.** Raster lines have soft edges. Measure thickness from the full cluster extent (including semi-transparent edge pixels), but sample color from the cluster center where the pixel is fully opaque.
