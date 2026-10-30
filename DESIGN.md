---
name: "GAIA"
description: "Geospatial Artificial Intelligence Assistant · 地理空间人工智能助手盖亚"
colors:
  accent-default: "#087f79"
  accent-ink-default: "#ffffff"
  accent-ink-bright: "#17212b"
  map-ground-default: "#e8eeed"
  workspace-light: "#f1f4f3"
  pane-light: "#ffffff"
  border-light: "#cbd4d1"
  border-soft-light: "#e5eae8"
  ink-light: "#243530"
  muted-light: "#63736d"
  input-light: "#fbfcfb"
  control-light: "#f5f7f6"
  hover-light: "#edf2f0"
  paper-ground-light: "#dce2df"
  danger-light: "#a43a2c"
  workspace-dark: "#151d23"
  pane-dark: "#202b33"
  border-dark: "#4c5d65"
  border-soft-dark: "#35454e"
  ink-dark: "#edf4f1"
  muted-dark: "#adbfba"
  input-dark: "#1a252d"
  control-dark: "#293941"
  hover-dark: "#31434b"
  paper-ground-dark: "#172128"
  danger-dark: "#f2a096"
  print-paper: "#ffffff"
typography:
  brand:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "20px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "0.6px"
  dialog-title:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "18px"
    fontWeight: 500
    lineHeight: 1.5
  welcome-title:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "16px"
    fontWeight: 550
    lineHeight: 1.5
  assistant-title:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.5
  pane-title:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  assistant-body:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.9
  label:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
  metadata:
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.5
  code:
    fontFamily: "'SFMono-Regular', Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  segment: "6px"
  field: "7px"
  control: "8px"
  composer: "12px"
  panel: "13px"
  dialog: "16px"
spacing:
  segment-inset: "3px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent-default}"
    textColor: "{colors.accent-ink-default}"
    rounded: "{rounded.control}"
    padding: "5px 9px"
  button-secondary:
    backgroundColor: "{colors.control-light}"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.control}"
    padding: "5px 9px"
  button-secondary-dark:
    backgroundColor: "{colors.control-dark}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.control}"
    padding: "5px 9px"
  button-icon:
    backgroundColor: "transparent"
    rounded: "{rounded.control}"
    padding: "4px"
  field:
    backgroundColor: "{colors.input-light}"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.field}"
    padding: "5px 7px"
  field-dark:
    backgroundColor: "{colors.input-dark}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.field}"
    padding: "5px 7px"
  switch:
    backgroundColor: "{colors.workspace-light}"
    rounded: "{rounded.control}"
    padding: "3px"
    height: "30px"
  switch-selected:
    backgroundColor: "{colors.pane-light}"
    rounded: "{rounded.segment}"
    padding: "2px 12px"
  context-nav:
    backgroundColor: "{colors.pane-light}"
    padding: "5px 6px"
    height: "42px"
  pane:
    backgroundColor: "{colors.pane-light}"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.panel}"
  pane-dark:
    backgroundColor: "{colors.pane-dark}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.panel}"
  assistant-composer:
    backgroundColor: "{colors.input-light}"
    rounded: "{rounded.composer}"
    padding: "11px"
  assistant-composer-dark:
    backgroundColor: "{colors.input-dark}"
    rounded: "{rounded.composer}"
    padding: "11px"
---

# Design System: GAIA

## Overview

**Creative North Star: "The GAIA Workspace"**

GAIA uses its supplied navy-and-mint orbital G identity inside a quiet, rounded GIS workspace. Neutral daylight and slate surfaces support precise controls, readable data and a central map or print document. The confirmed direction replaces the earlier vendor imitation with GAIA's own identity.

The interface is compact and operational. Boundaries are fine strokes; selection is a restrained tint; segmented controls change context without becoming a ribbon. The desktop assistant remains an independent surface at the right while contextual tools occupy the left.

**Key Characteristics:**

- User-supplied orbital G identity, preserved unchanged.
- Daylight and slate themes with a user-configurable accent.
- Rounded, finely bordered operational surfaces.
- Concentrated map/document workspace with an independent assistant.
- Explicit full-width pane navigation on narrow screens.

The implementation is the visual authority; this is a code-led system with no approved image comp. Product direction is recorded in `PRODUCT.md`, and the current workbench composition remains scoped by `.impeccable/briefs/workbench.md`. This document records the finished replacement system rather than the superseded reproduction.

The application image is `frontend/public/gaia-icon.png`. Its adjacent `gaia-icon.png.json` records the original user-supplied file (`codex-clipboard-b098bbba-eff1-4eda-b222-1eb5b254f928.png`, supplied 2026-10-31) and the explicit instruction to use the unchanged image as the application icon. The header presents it at 42px square on desktop and 36px square on narrow screens. Geographic imagery belongs to actual data and native map content, not to brand decoration.

## Colors

A muted green daylight palette and cool slate dark palette frame a configurable accent. Frontmatter tokens ending in `-light` or `-dark` are the corresponding CSS theme values; the `-default` values are initial appearance choices, not restrictions on user customization.

### Primary

- **GAIA Teal** (`accent-default`): the initial action color. The same chosen accent supplies primary buttons, selection outlines, checkboxes and layout handles.
- **Adaptive Action Ink** (`accent-ink-default`, `accent-ink-bright`): primary button text is computed from the chosen accent, not fixed for every palette.
- **Orbital Navy and Mint**: belong to the supplied raster identity. Do not infer replacement CSS brand colors from the image or recolor it when the accent changes.

### Neutral

- **Daylight Workspace / Slate Workspace** (`workspace-*`): application ground, grouping and the header.
- **Daylight Pane / Slate Pane** (`pane-*`): working surfaces, tool panels, dialogs and the assistant.
- **Fine Boundary / Soft Boundary** (`border-*`, `border-soft-*`): panel outlines and internal dividers respectively.
- **Primary Ink / Supporting Ink** (`ink-*`, `muted-*`): operational copy and subordinate metadata.
- **Field / Control / Hover** (`input-*`, `control-*`, `hover-*`): editable fields, resting secondary controls and hover feedback.
- **Paper Surround** (`paper-ground-*`): the print editor's surrounding work area. **Print Paper** (`print-paper`) remains white in both themes.
- **Map Ground** (`map-ground-default`): the initial configurable map background; it is independent of theme changes.

### Semantic

- **Error Ink** (`danger-light`, `danger-dark`): failures, required marks and connection errors use the active theme's error token.

### Derived appearance

The runtime sets `--accent`, `--accent-ink`, `--accent-ui` and `--map-ground` on the workbench. `--accent-ink` uses WCAG relative luminance of the selected accent: above 0.38 it uses the dark action ink, otherwise white. In dark mode, `--accent-ui` mixes the selected accent at 65% with white; in light mode, a bright accent is mixed at 50% with `#17302a`, otherwise the chosen accent is used directly. Links and small selected labels use `--accent-ui`.

Selection backgrounds mix the chosen accent into the active pane at 13% in light mode and 20% in dark mode. These are derived CSS expressions, documented in the sidecar, rather than independent fixed palette colors. The appearance preferences persist in the browser. Map feature styling remains separately authored.

**The Independent Color Rule.** Changing the workspace accent must not recolor geographic symbology or the white print page.

## Typography

**UI Font:** Segoe UI, with Apple system, PingFang SC, Microsoft YaHei and generic sans-serif fallbacks, exactly as recorded in frontmatter. **Code Font:** SFMono-Regular, Consolas and monospace. The brand wordmark uses the UI stack as an identity label; the workspace has no editorial display-face system.

The scale favors compact, familiar operational text. General body copy uses a 1.5 line height; assistant responses use a more open 1.9 line height. There is no decorative uppercase label convention.

### Hierarchy

- **Brand:** 20px, weight 650, 1.2 line height and 0.6px tracking; 18px on narrow screens.
- **Dialog title:** 18px, weight 500.
- **Welcome title:** 16px, weight 550; 14px in the compact desktop range.
- **Assistant title:** 15px, weight 600.
- **Pane title:** 13px, weight 600; general body is 13px, weight 400.
- **Assistant body:** 12px, weight 400, line height 1.9; tool/help copy also commonly uses 12px.
- **Labels:** 11px; metadata uses 10px. Dense rulers, status text and run footers use 9px only for supporting information.
- **Code:** 11px with 1.65 line height in the editor; trace/preformatted text uses 1.6. Numerical layout fields use tabular figures.

## Layout

The reusable spatial model is adjacent task surfaces with a dominant document. The workbench fills `100dvh` and prevents body scrolling; each pane scrolls within its own bounded area. Main pane headings and action rows stay outside scrolling content. The observed spacing rhythm uses 4px increments, with 3px insets for segmented controls and component-specific compact adjustments.

For the current workbench, the header is 72px high and the status strip is 24px high. The default desktop grid is `250px minmax(280px, 1fr) 390px`, with 12px gaps and `0 12px 12px` outer padding. The left context has a 42px navigation row above its pane; the document and assistant span both grid rows.

| Viewport | Current workbench composition |
| --- | --- |
| 1600px and above | `270px minmax(360px, 1fr) 420px`; 14px gaps; 16px horizontal workspace padding; 24px header side padding. |
| 1151–1599px | Default three-column grid and 12px gaps. |
| 921–1150px | `220px minmax(240px, 1fr) 330px`; 9px gaps and side padding; compact header spacing. |
| 920px and below | One full-width pane selected by Data & Tools / Map & Layout / GAIA Assistant; the header is 62px high. |

At narrow widths, the pane navigation is a 35px segmented control with a 3px inset, placed above the workspace. Data & Tools retains its contextual navigation; document and assistant each fill the pane area. The project name remains editable while subtitles, secondary header labels, coordinates and engine details recede. Document action rows scroll horizontally when needed. Form content keeps its vertical scroll and two-column field groups where implemented. The assistant composer remains at the bottom of its own pane rather than entering the page scroll.

The document head is 44px on desktop and 42px on narrow screens; its contextual action row is 42px or 39px respectively. Tool fields use `14px 12px` padding. Assistant history uses `18px 16px`; the composer has a 12px surrounding inset. Print editing uses physical millimetres with decimated ruler labels; the rectangular paper can pan and zoom within its scroll region. Attribute tables form an internal bottom dock, 210px initially and 180px at 800px or below.

**The Context Rule.** On desktop, data, tools, formatting and catalog change the left context; they do not replace the assistant at the right.

## Elevation & Depth

The workspace is flat at rest. One-pixel boundaries and theme-specific surface tones separate panes. Small, soft shadows distinguish the selected segment, map caption, print sheet, toast and modal. There is no workspace glass or decorative glow.

### Shadow Vocabulary

- **Caption:** `0 1px 3px #0001`.
- **Selected segment:** `0 1px 3px #0002`.
- **Print sheet:** `0 2px 7px #0003`.
- **Toast:** `0 3px 14px #0003`.
- **Modal:** `0 10px 40px #0003`, with a `#10182066` backdrop.
- **Composer focus:** `0 0 0 2px color-mix(in srgb, var(--accent) 12%, transparent)`, alongside an adaptive accent border. This is interaction feedback rather than decorative elevation.

**The Quiet Surface Rule.** Use borders and tonal separation for workspace panes; reserve shadows for the print sheet, selected segments and overlays.

## Shapes

Soft rectangular controls carry the system. Standard buttons use the control radius; fields use the slightly smaller field radius. Segmented tracks use the control radius and their selected segments the segment radius. Primary document and assistant containers use the panel radius; the contextual navigation and left pane join into one outlined silhouette, rounding only their external corners.

The composer and upload area use the composer radius; dialogs use the dialog radius. Secondary applied shapes include 10px user-message corners, 11px toast corners and 5px layer-symbol corners. Borders are generally 1px. The actual print page and cartographic items retain their authored rectangular geometry; interface rounding does not alter exported geographic content.

## Components

### Buttons

Compact and calm. Standard buttons use `5px 9px` padding, a 32px minimum height and a 6px content gap. Primary buttons use the selected accent and computed action ink at weight 600; hover applies `brightness(.93)` while keeping the accent background. Secondary buttons use the active control surface, fine boundary and hover surface. Header actions are mostly transparent; Save Project is outlined on desktop. Icon controls use 4px padding, with contextual sizes allowed to be smaller than the standard button.

Keyboard focus uses a 2px accent outline with a 2px offset. Disabled buttons use 0.48 opacity and the default cursor. These states apply to both themes; there is no generic animated hover or press transform.

### Segmented Context Switches

The document switch is 30px high with 3px padding and gaps, a ground-colored track and 24px selected buttons. Buttons use `2px 12px` padding, 11px text, and weight 600 when selected. The selected segment is pane-colored with the selected-segment shadow and adaptive accent text. The narrow-screen top-level navigation follows the same treatment at 35px high. The four-option left navigation instead uses a selection tint inside the pane; it does not add another floating card.

### Cards / Containers

Document and assistant surfaces use a panel-radius outline with no resting shadow. Internal rows use soft boundaries. The assistant header is 46px high on desktop and 44px on narrow screens; ordinary pane titles are 13px and the assistant title is 15px. Containers clip their own scrolling content. Nested information such as tool traces uses a ground-colored surface, a soft border, the control radius and `0 8px` padding.

### Inputs / Fields

Fields use the active input surface, primary ink, fine boundary, field radius, `5px 7px` padding and a 33px minimum height. Labels sit above text/select/number fields with a 5px gap; units are placed at the field's right edge. Native checkboxes are 14px square and remain in horizontal, left-aligned rows with a 7px gap. Algorithm boolean rows have a 30px minimum height and no inherited vertical field-label stack.

Output fields are vertical labeled groups with a 5px gap and 14px bottom separation; the last output label has 8px below it. Errors use the theme's error ink and wrap rather than overflowing the pane. Focus uses the shared outline. The actual disabled-button treatment is recorded above; do not invent a different disabled field treatment.

### Navigation

The left navigation exposes Data, Tools, Format and Catalog with icons and compact 11px labels; the compact desktop range uses 10px labels. Active items use selection tint and adaptive accent text at weight 600. Tool detail tabs use an accent underline. The mobile pane choices are explicit navigation and preserve independent data/tool, document and assistant state. Icons come from the existing Lucide React set; do not substitute text glyphs.

### GAIA Assistant Composer and Runs

The composer is a bordered input-colored container with the composer radius, 11px internal padding and 12px outer inset. A 10px layer-context row is separated from the text entry by a soft rule. The textarea is borderless, transparent, 12px and at least 100px high, increasing to 110px on narrow screens. The 11px send/stop button aligns at the lower right; sending is disabled for an empty task. Focus-within uses adaptive accent and the composer focus ring.

User messages use selection tint with `10px 12px` padding. Responses use the assistant-body role, with tool traces and artifact download rows between them. Run separators use a soft boundary and 20px bottom spacing. Artifact actions use the standard outlined control treatment; the compact footer keeps provenance and run-record access visible.

### Dialogs and Feedback

Native dialogs use a dialog-radius pane, 24px padding on desktop and 20px at narrow widths. Standard width is `min(560px, calc(100vw - 32px))`; wide dialogs use 800px with the same viewport limit. Maximum height is `calc(100dvh - 48px)` with internal scrolling. Escape and native focus behavior are preserved. Toasts use the pane surface, fine boundary and toast shadow, capped at `min(600px, 92vw)`.

The only shared ongoing animation is the 1-second linear loading rotation. `prefers-reduced-motion: reduce` stops that animation and disables smooth scrolling. Do not invent unobserved transition durations or easing curves as system tokens.

## Do's and Don'ts

### Do:

- **Do** preserve the supplied orbital G image and its adjacent provenance file.
- **Do** bind reusable surfaces to the active theme variables and use the derived accent color for small links and selected labels.
- **Do** keep the desktop assistant separate and use the three explicit pane choices at narrow widths.
- **Do** retain horizontal native checkbox rows and clear separation between output labels and fields.
- **Do** keep print paper white and map styling independent of workspace appearance.
- **Do** preserve visible keyboard focus, native dialog behavior and reduced-motion handling.

### Don't:

- **Don't** restore the rejected ArcGIS Pro imitation or its vendor-style ribbon.
- **Don't** use brand artwork as a recolorable workspace accent.
- **Don't** squeeze the three desktop columns into a narrow viewport.
- **Don't** turn settings, tool forms or the catalog into replacements for the desktop conversation.
- **Don't** add decorative glass, glow or hard offset shadows to the operational surfaces.

Inactive legacy ribbon rules and the old schematic colors in appearance thumbnails are not canonized as GAIA identity or reusable theme tokens. They remain in the code outside this documentation-only change; the final active GAIA cascade, supplied image and reviewed operational screens are authoritative.
