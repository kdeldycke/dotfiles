---
name: brand-assets
description: Create project logo and banner SVGs, then export them to light and dark PNG variants. Use when you design a logo or banner, or regenerate the PNGs from their SVG source files.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
argument-hint: '[path/to/assets or SVG file]'
---

# Project Logo and Banner Assets

Create, maintain, and export project logo and banner assets as SVGs with light/dark PNG variants.

The Sphinx side of the convention (the `light_logo`/`dark_logo` pair, `html_favicon`, `ogp_image` and the rules around them) lives in `.claude/agents/sphinx-docs.md` § `docs/conf.py` hygiene › Theme assets and OpenGraph. When this skill writes a new asset path into `docs/conf.py`, follow the canonical values defined there, as § Sphinx integration below spells them out.

## Asset variants

Every project produces four SVG variants, each with light and dark PNG exports:

1. **Favicon** (`favicon.svg`): The project icon only, no text, no margins. Tight-cropped to the icon's bounding box. Used as `html_favicon` in Sphinx and as the browser tab icon. Transparent background. Does not need PNG exports (browsers handle SVG favicons natively). If the mark itself is theme-invariant (flat, unoutlined — see "Isometric / faceted marks" below), the same source also serves any platform app-icon bundle (`.ico`, `.icns`, a build tool's icon input) with a single rendering: a browser tab and a dock are surfaces with no theme this script can query, and a mark with no outline needs no dark variant to stay legible on either.

2. **Square logo** (`logo-square.svg`): The project icon with the project name centered below it. Its light and dark PNG exports are the Sphinx sidebar logo pair (`light_logo`/`dark_logo`). Transparent background. Do not add a background `<rect>` to a transparent variant. The viewBox is taller than the icon to accommodate the text below.

3. **Banner** (`logo-banner.svg`): Horizontal layout with the icon on the left, project name and tagline to the right. Transparent background. Used in the GitHub readme.

4. **Social banner** (`banner-social.svg`): Same layout as the banner but with a decorative opaque background (e.g., marble veins, gradients, wave patterns). Used for OpenGraph/social previews. Opaque background. The name says what the file is for, not its style, so a redesign leaves the `ogp_image` and `html_static_path` entries of `docs/conf.py` as they are.

Each SVG produces two PNGs: `{name}-light.png` and `{name}-dark.png`. The favicon is SVG-only (no PNG exports needed).

## Incremental mode

When base SVGs already exist (at least a square logo or banner), skip any interactive menu and proceed directly:

1. Scan the assets directory for existing SVGs and PNGs.
2. Compare against the four expected variants and their PNG exports.
3. Fill every gap: create missing SVGs (favicon from the icon, social banner from the banner), generate missing PNGs, and rename misnamed files to match the names in § Asset variants.
4. Wire any new assets into `docs/conf.py` if not already configured.

Only ask the user a question when the gap analysis is genuinely ambiguous (multiple competing icon sources, unclear which element is the project icon).

## Raster-only marks

A mark that exists only as a raster illustration has no SVG to theme, and an illustration rarely traces cleanly. Keep its PNGs and wire them instead:

- Read the alpha channel before you call a background opaque: the Read tool draws transparent pixels as white.
- A transparent logo that reads on both themes can serve as both `light_logo` and `dark_logo`.
- Point `html_favicon` at the PNG icon, and compose the social card from the banner on an opaque background.

## Redesigning an existing mark

Revising the *treatment* of a mark that already has SVG sources — outlined vs flat, how many shading planes, how a cutout gets painted — is a different exercise from Design exploration below, which assumes no SVG exists yet. It still deserves the same breadth before committing to a direction, and it must be judged on both themes at once: a treatment that reads fine on white can fail outright on near-black (see "Isometric / faceted marks" below for why an outlined mark is especially prone to this).

Render a contact sheet of candidates, each shown on **both** light and dark backgrounds side by side, plus small thumbnails (16/24/32/48px) next to the full-size renders. Reviewing every candidate at working size and at icon size in one image is what catches a treatment that reads well full-size and turns to mush at 16px, or that loses a plane's contrast on one theme while looking fine on the other — a theme-specific failure is easy to miss when a candidate is only ever shown on the theme you happen to be looking at. Ten to fourteen candidates is a reasonable spread per round; expect two rounds in practice, one for the coarse direction and a second to refine the winner's remaining open question (how a void or cutout inside the mark gets treated, for instance).

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
- Trace decorative elements from the raster reference if needed.

## Color themes

**Key substitutions on the whole CSS declaration, never on the bare color.** A mark that uses a brand color as a literal fill (a flat isometric plane, an icon's own stroke) and a themed element using the *same* hex (lettering, a caption) look identical to a substitution keyed on the color alone: it has no way to tell "this should flip" from "this should stay put," and repaints both. Key each entry of the substitution map on the full declaration — `.word{fill:#2d2364}` → `.word{fill:#d3d3f6}` — never on `#2d2364` → `#d3d3f6` in isolation, so a class rule the mark itself owns can never match.

Typical light/dark color pairs (Tailwind Slate palette):

| Role       | Light     | Dark      |
| ---------- | --------- | --------- |
| Title text | `#1E293B` | `#F1F5F9` |
| Tagline    | `#64748B` | `#CBD5E1` |
| Background | `#F8FAFC` | `#0F172A` |

## Isometric / faceted marks

A mark built from isometric solids (boxes, cubes, prisms) reads correctly with flat, unoutlined faces — one color per plane the light can catch, and the eye reconstructs the shape from the pattern of values alone, the way a game sprite does. This is the fix when a stroked version of the same mark fails on a dark background: an outline drawn in the dark brand color has nothing to contrast against near-black, so the silhouette dissolves at its edges while anything drawn with a plain *fill* (lettering, other flat elements) stays perfectly legible beside it. If a themed mark loses its edges on one background but not the other, that mismatch is usually the tell that it wants flat shading instead of an outline, not a different dark-mode color for the same stroke.

**Three planes need three values.** A glance at an isometric solid shows at most three faces: one lit from above, and two vertical faces turned away from each other. Two brand colors are not enough on their own for that third plane, and the honest way to produce a third value without expanding the palette is the arithmetic midpoint of the other two, computed per channel and enforced with a test rather than hand-picked:

```python
mid = "#{:02x}{:02x}{:02x}".format(
    *((int(ink[i : i + 2], 16) + int(wash[i : i + 2], 16)) // 2 for i in (1, 3, 5))
)
```

**Discovering which path is which plane.** When the source SVG is already a flat list of `<path>` elements with no naming that says what each one draws, recolor every path a distinct hue (step through HSV, one hue per path index) and render at a readable size. The rainbow render makes the plane each path belongs to obvious at a glance, so the mapping from path index to plane becomes a literal fact to hard-code once, rather than something re-derived by eye on every future edit.

**Filling a void inside the silhouette.** A mark with a cutout (an open lid, a ring) that used to hide the gap behind an outline needs the interior actually painted once the outline is gone, or the void reads as a hole rather than as depth. Compute the interior walls from vertices the exterior geometry already has (the rim of the opening), draw each wall at its full extent, and clip it to the rim polygon with `<clipPath>` — that avoids hand-computing where two walls intersect, since the clip does the trimming for free. Critically, an interior wall is lit as the plane it *faces*, not the plane it sits *behind*: the wall on the far side of a left-facing opening itself faces right, and so takes the right-plane color, mirrored from what a same-side exterior face would show. Getting this backwards makes any object floating inside the void blend into the wall directly behind it on one of its own faces; getting it right guarantees every face of that object lands on the tone opposite whatever sits behind it.

**Keep a terminal or block-character rendition in sync with the same source.** If the project also ships a low-resolution rendition of the mark (half-block terminal art for a CLI's `--version` banner, an ASCII favicon), derive its interior detail from the SVG rather than hand-tuning it: for every grid cell not already covered by the silhouette, test its center point against the source's rim polygon — in the SVG's own coordinate space, not pixel space — with a standard point-in-polygon test, and fill it only when the test passes. Symmetrize by testing a cell together with its mirror (fill both if either passes) rather than trusting the sampling grid to be perfectly centered: a rounding error in the grid math is a far easier way to end up asymmetric than the source geometry itself. This is what keeps two renditions of "the same" mark from drifting into two different designs over time.

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
- When creating new SVGs, take every gray from one Tailwind gray palette, like Slate or Zinc. Keep the palette that the existing marks of the project use.
- On macOS, verify a regenerated SVG by reading its source. `qlmanage -t` can render a stale thumbnail of a file just rewritten, even after `qlmanage -r cache`: use the thumbnail only for layout.

## Sphinx integration

### `docs/conf.py`

Wire the assets into the Furo theme:

```python
html_favicon = "assets/favicon.svg"
html_theme_options = {
    "light_logo": "logo-square-light.png",
    "dark_logo": "logo-square-dark.png",
    "sidebar_hide_name": True,
    # ...
}
ogp_image = "_static/banner-social-light.png"
html_static_path = [
    "_static",
    "assets/banner-social-light.png",
    "assets/logo-square-dark.png",
    "assets/logo-square-light.png",
]
```

- `light_logo`/`dark_logo`: The two PNG exports of the square logo (with project name baked in), which Furo swaps with its own theme toggle. Never set `html_logo` beside them: Furo prefers it, skips the pair, and shows the light-only SVG on the dark theme. Combined with `"sidebar_hide_name": True` to avoid a duplicate auto-generated name below the logo.
- `html_favicon`: Points to the icon-only favicon (no text, tight crop).
- `ogp_image`: The light social banner, served by the site itself so social crawlers can fetch it.
- `html_static_path`: Furo and `sphinxext.opengraph` resolve those three names against `_static/`, so each PNG needs its own entry. Listing `docs/assets/` whole would copy every screenshot along with them.

### Hiding the readme banner in Sphinx

The readme includes a centered banner image (`logo-banner.svg`) for GitHub. When the readme is included in the Sphinx front page via `{include}`, the banner is redundant with the sidebar logo. Hide it with custom CSS:

`docs/_static/custom.css`:

```css
/* Hide the readme banner on the Sphinx front page (logo already in sidebar). */
article p[align="center"]:has(img[alt="Project Name"]) {
    display: none;
}
```

Wire it in `conf.py`, where `_static` already opens the `html_static_path` list above:

```python
html_css_files = ["custom.css"]
```

Replace `"Project Name"` with the actual `alt` text of the banner `<img>` in the readme.
