disposition: ship

Reviewed inline against real rendered Chrome and native PDF captures. The local Impeccable engine is unavailable; no external design review is claimed.

Mode: Operate. Existing approved Atlas/Folio composition and independent assistant are retained. This change adds cartographic choices within the selected element/page panels, and improves typography without changing the approved arrangement.

Persistence: DESIGN.md and design.json record the system/CJK stack, browser font preference and independent actual QGIS font database. The user guide documents manual and explicit offline commands, plugin requirements and limits. Capture sidecars record real Census/USGS data and source provenance.

Fidelity: north.png shows four distinct selectable vector glyphs with a visible selected border, paired with the actual native north element. typography.png shows Songti selected and rendered in the page title, with native weight/size metadata verified. terrain.png shows the selected ramp on a real DEM; verified-map.png is an independent Poppler rendering of the downloaded PDF, including the changed north arrow, scale and title. mobile-styles.png shows reachable controls without horizontal overflow. A dark panel was also captured and checked in outputs/layout-styles.

Ceiling: this delivers the advertised style choices, not the full QGIS layout property editor. Available scale styles are filtered by the real renderer registry; unsupported styles fail instead of silently falling back. Fonts are installed-family choices; no font installation is performed. Free-form model interpretation requires a configured provider; no paid external model call was made during this verification.

Material fixes: corrected Qt5 QFontDatabase access, native stepped/hollow style identifiers, preserved scale ground distance across unit changes, reduced scale label clutter, kept per-element font changes from overwriting other elements, and made offline unknown styles report that they were not recognized. Browser screenshots wait for the actual new native element images.

Evidence: result.json. Backend regression: 132 passed / 8 optional tests skipped. Native style suite: 17 passed including every advertised scale renderer, PDF output, actual font family/weight/size and QGZ save/reopen. Browser style and preference checks passed with zero page errors. Existing released desktop installers are not rebuilt by this change.
