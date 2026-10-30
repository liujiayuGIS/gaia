# GeoAgent Studio v0.2 design

Audience: GIS researchers and analysts. Primary job: inspect data, run traceable spatial workflows, compose publication maps.

Palette: deep ocean #10283e; instrument slate #243d54; mineral blue #3c83b7; glacier #e9f0f6; paper white #ffffff; amber #d89a54.
Typography: Avenir Next (interface on macOS), system CJK fallback, tabular numerals for values. Comfortable 13px controls and 15px chat text.
Layout: slim application rail; layered data tree and import inbox; large central map with contextual toolbar and bottom attribute dock; separate agent panel. Switch the central workspace between map and actual print layout. Left alignment for commands and data. The map is the dominant visual, without a marketing hero or decorative statistics.
Distinctive elements: oceanographic instrument palette, restrained glass on the floating map toolbar, cartographic coordinate grid, rigorous use of whitespace. Three geometry glyphs and raster swatches encode real content. Runtime trace is a readable operations ledger, not raw JSON by default.
Review against brief: eliminate the previous pale green palette and tiny control text. Avoid all-cap labels, generic numbered suggestion cards, uniform rounded cards, bright neon on black, and unrelated dashboard metrics. Export controls operate on real backend cartography. The layout preview is an actual SVG from the same renderer as the exported map.
