# GAIA design references

The user's latest direction is authoritative: a concentrated data/map/assistant workspace, its own supplied icon/name, permanently separate right-side chat, rounded controls and restrained iOS-like context switches. An earlier ArcGIS Pro-like ribbon prototype was explicitly rejected and replaced.

- [Kepler.gl](https://github.com/keplergl/kepler.gl): primary-source reference for a map-first spatial workbench and contextual data configuration.
- [OpenGIS](https://github.com/ATFfang/OpenGIS): primary-source reference for natural-language geospatial task interaction.
- [Impeccable](https://github.com/pbakaus/impeccable) and [Interface Design](https://github.com/Dammyjay93/interface-design): installed design workflow guidance, applied with the existing frontend-design skill. These tools support intentional operational design and independent visual review; they do not dictate a vendor layout.
- [QGIS print layout](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/composer.html): native printing semantics and artifacts.

No external UI code or vendor branding was copied. The GAIA icon was provided by the user and is copied unchanged into `frontend/public/gaia-icon.png`. Its navy/mint artwork is not recolored when the user changes workbench accent.
