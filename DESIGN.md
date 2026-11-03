---
name: GAIA Atlas / Folio
description: Map-first spatial analysis with a dedicated assistant and an editable
  native print page.
colors:
  accent-default: '#087f79'
  accent-ink-default: '#ffffff'
  accent-ink-dark: '#17212b'
  workspace-light: '#f3f6f7'
  pane-light: '#ffffff'
  ink-light: '#172f40'
  muted-light: '#5d7281'
  border-light: '#d6e1e7'
  border-soft-light: '#e8eef2'
  input-light: '#f8fafc'
  control-light: '#f1f5f7'
  hover-light: '#eaf1f4'
  paper-ground-light: '#e8ecf3'
  workspace-dark: '#152432'
  pane-dark: '#1c3040'
  ink-dark: '#edf4f8'
  muted-dark: '#b1c3cf'
  border-dark: '#3f596b'
  border-soft-dark: '#30495b'
  input-dark: '#172b3b'
  control-dark: '#253f51'
  hover-dark: '#304c60'
  paper-ground-dark: '#192d3d'
  print-paper: '#ffffff'
  map-ground-default: '#e8eeed'
  map-ground-dark-default: '#142938'
typography:
  brand:
    fontFamily: '-apple-system, BlinkMacSystemFont, ''PingFang SC'', ''Segoe UI'',
      ''Microsoft YaHei UI'', ''Noto Sans CJK SC'', sans-serif'
    fontSize: 24px
    fontWeight: 650
    letterSpacing: -0.7px
  assistant-title:
    fontFamily: '-apple-system, BlinkMacSystemFont, ''PingFang SC'', ''Segoe UI'',
      ''Microsoft YaHei UI'', ''Noto Sans CJK SC'', sans-serif'
    fontSize: 17px
    fontWeight: 650
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, ''PingFang SC'', ''Segoe UI'',
      ''Microsoft YaHei UI'', ''Noto Sans CJK SC'', sans-serif'
    fontSize: 14px
    lineHeight: 1.5
  assistant-body:
    fontFamily: '-apple-system, BlinkMacSystemFont, ''PingFang SC'', ''Segoe UI'',
      ''Microsoft YaHei UI'', ''Noto Sans CJK SC'', sans-serif'
    fontSize: 14px
    lineHeight: 1.95
  control:
    fontFamily: '-apple-system, BlinkMacSystemFont, ''PingFang SC'', ''Segoe UI'',
      ''Microsoft YaHei UI'', ''Noto Sans CJK SC'', sans-serif'
    fontSize: 12px
  metadata:
    fontFamily: '-apple-system, BlinkMacSystemFont, ''PingFang SC'', ''Segoe UI'',
      ''Microsoft YaHei UI'', ''Noto Sans CJK SC'', sans-serif'
    fontSize: 11px
rounded:
  field: 8px
  control: 9px
  artifact: 11px
  composer: 14px
  floating-surface: 16px
  dialog: 18px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  floating-inset: 18px
  xl: 20px
  xxl: 24px
components:
  button-primary:
    backgroundColor: '{colors.accent-default}'
    textColor: '{colors.accent-ink-default}'
    rounded: '{rounded.control}'
    height: 34px
  assistant-composer:
    backgroundColor: '{colors.input-light}'
    rounded: '{rounded.composer}'
    padding: 12px
  floating-palette:
    backgroundColor: color-mix(in srgb, var(--pane) 95%, transparent)
    rounded: '{rounded.floating-surface}'
    width: 268px
---

# GAIA Atlas / Folio

## Overview

The user's approved composition is A for the main map, C for print editing, and B's process drawer integrated into A. This replaces the previous boxed three-column workspace. Preserve the supplied orbital-G image and its provenance; the model-generated comps are references, never interface pixels or geographic evidence.

## Colors

The light workspace uses silver-white surfaces and deep petrol text. The dark interface uses mineral blue surfaces and warm white text. One configurable accent identifies primary actions and selection. Geographic symbology and print paper retain their independent colors.

**Independent color rule.** Workspace accent changes never recolor geographic data. With the default map background, dark UI substitutes the recorded dark canvas ground; user-selected map backgrounds are retained.

**Readable action rule.** `accentInk` computes relative luminance and compares white against #17212b, selecting whichever yields the greater contrast. Small accent text uses the existing adaptive `--accent-ui` mix. Do not restore the earlier fixed 0.38 luminance threshold.

## Typography

The operational UI uses the native system / PingFang / Segoe UI / Microsoft YaHei UI / Noto CJK stack in frontmatter. Main copy and assistant responses are 14px; assistant prose has 1.95 line height. Controls are 12px and supporting metadata 11px. The GAIA wordmark is 24px at weight 650; the assistant title is 17px at weight 650. The map or document, rather than decorative display typography, leads the interface. Appearance offers system, Chinese sans and Chinese serif font stacks through --ui-font, saved in the existing browser preference. Print text uses the actual QGIS font database independently; auto chooses an installed Chinese family, and title/legend/scale have individual overrides. Native font weight, size, color and italic properties persist with the layout. Style controls use two-column north glyph previews and five terrain ramp swatches with selected borders; no decorative imagery is added to the map.

## Layout

A 62px project header and 25px status strip enclose the workspace. Map mode has a full map and a separate assistant column (`clamp(350px, 27vw, 430px)`, 450px from 1750px). The 268px palette floats 18px from the map's top-left. The floating action bar is centered in the remaining map area; native navigation and supplementary map actions sit at the right edge.

The process drawer anchors 18px above the map bottom. A ResizeObserver publishes its actual height, so the layer palette and map scale retain clearance when it expands. Do not hard-code fake progress or precomputed tool stages.

Print mode uses a 248px element sidebar, a flexible page editor and the same independent assistant. The sidebar contains one actual current-page thumbnail and the native element outline, or the selected context form. The page is white on the recorded cool pasteboard and uses physical millimetres; the thumbnail reuses scene element imagery.

At 1050px and below, explicit Data & Tools / Map & Layout / GAIA Assistant navigation selects one full-width surface. The layout export action is sticky at the toolbar right; remaining tools can scroll. At 1051–1250px, the assistant is 350px and the floating palette 238px. Never squeeze all desktop columns into a phone.

## Elevation & Depth

Only the map's floating tools and process drawer use translucent pane color and `backdrop-filter: blur(18px)`. This material lets the map continue underneath actual operational surfaces. Assistant and print sidebar are opaque; there is no whole-application glass effect.

- Floating light surface: `0 6px 26px #193c511a, 0 1px 4px #193c510c`.
- Floating dark surface: `0 8px 30px #07131e40, 0 1px 4px #07131e30`.
- Print page: `0 6px 24px #1d324b1c`.
- Dialog: `0 15px 60px #172f4033`.

## Shapes

Floating map objects use 16px corners; controls use 9px and fields 8px. The composer is 14px, artifact rows 11px, dialogs 18px. Inner operational grouping uses spacing and fine boundaries rather than more cards. The print page and geographic geometry remain rectangular or data-defined.

## Components

### Navigation and search

Map / Print Layout is a native segmented switch. Data / Tools / Format / Catalog lives inside the context palette. Global search opens a native dialog through the header or Cmd/Ctrl+K; it searches actual layer names and algorithm metadata, and selecting an algorithm initializes its parameter form. Visible focus uses a 2px adaptive-accent outline with 3px offset.

### Process drawer

The compact header displays real task status and tool-operation count. Expansion reveals actual started/completed tool events, selected parameters and receipts, output-layer navigation and run-record download. Failure, interruption and missing receipts must not be represented as completion. Drawer selection remains stable while a run updates. Controls retain real keyboard focus.

### Assistant

The assistant is always separate on desktop, with independently scrolling history, a session selector and an anchored composer. Its header uses the original icon at 25px. The composer binds current layer context, supports attachments through the existing import flow and Cmd/Ctrl+Enter submission. Tools, approvals, validation and artifacts retain their existing backend contracts. Avoid enlarging tool JSON into the primary content; details are expandable.

The assistant boundary is a 10px pointer/touch separator with a 3 × 40px rounded grip. Hover, keyboard focus and dragging use the current accent. Width defaults to the responsive design value, can be adjusted from 320–760px, and is clamped to preserve at least 440px of document space plus the visible print sidebar. Persist the requested width per client; narrower windows clamp it without overwriting that preference. Left/Right changes 24px (Shift: 64px), Home/End reaches bounds, double-click/Enter resets, and Escape cancels a gesture. Hide the separator in the existing single-surface navigation at 1050px and below. MapLibre already observes viewport resizing.

Layer deletion is a quiet trash icon in each data row, using muted text until hover/focus. It removes a workspace layer and retains source/recovery data; show an undo action in the existing toast. Keep deletion distinct from the adjacent visibility control and from deleting geographic features. Names, counts, ambiguity, persistence and receipt integrity are execution behavior, not decoration.

Message actions use a quiet 32px rounded icon row beneath each message, with 10px tabular timestamps. User controls align right; answer controls align left and wrap at narrow widths. Copy feedback uses a temporary checkmark only after success. Preserve readable focus, tooltip names and explicit pressed states for ratings. More actions use a native auto popover in the top layer, positioned inside the viewport, with light-dismiss and Escape behavior. Do not put the menu inside a clipped scroll surface.

Assistant Markdown uses the existing 14px body, 18px section headings, 12px monospace code and horizontally scrolling tables. Code blocks have their own copy control, excluded from copied prose. Quote previews and edited-question drafts sit inside the existing composer with a 2px accent boundary. Editing explicitly starts a new task; regenerating an answer is a distinct, read-only operation with no GIS tools. Feedback records user preference about the answer, never spatial correctness. Local speech is optional and must disclose unavailable voices rather than simulating playback.

### Native print editor

The actual QGIS scene supplies movable items and preview imagery. Both horizontal and vertical rulers use real page dimensions. Selected objects retain resize handles, millimetre properties, visibility, lock and undo/redo. Selecting an item opens its properties even when the sidebar was previously collapsed.

### Forms and themes

Inputs use current theme variables, not fixed light fills. Primary text adapts to the chosen accent. Theme preferences persist using the existing appearance key. Standard hover/focus/disabled behavior remains; reduced-motion users receive no ongoing spinner motion. The only new transition is 140ms color/background feedback.

## Do's and Don'ts

- **Do** keep map tools floating in map mode and the print outline opaque in print mode.
- **Do** retain the supplied brand image and actual GIS data, native scenes and execution events.
- **Do** preserve the right-hand assistant when changing tools, settings or formats.
- **Do** keep real map-scale and input-form clearance above the expanded process drawer.
- **Do** test custom accent readability, narrow-screen export and keyboard search.
- **Don't** reintroduce the rejected vendor ribbon or permanent boxed left map column.
- **Don't** render generated concept maps as live geography or fabricate additional print pages.
- **Don't** treat tool success as a substitute for task validation.

Legacy ribbon styles in `style.css` are compatibility residue, not part of the active Atlas system. `atlas.css` is loaded after that file and owns the current workspace composition.
