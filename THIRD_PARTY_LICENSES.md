# Third-party software

Bundled under `vendor/` so that the app works as a static page:

| Library | Version | Licence | Source |
|---|---|---|---|
| Leaflet | 1.9.x | BSD-2-Clause (© Volodymyr Agafonkin) | https://leafletjs.com — `vendor/leaflet/` |
| georaster | 1.6.0 | Apache-2.0 | https://github.com/GeoTIFF/georaster — `vendor/georaster/georaster.LICENSE` |
| georaster-layer-for-leaflet | 3.10.0 | Apache-2.0 | https://github.com/GeoTIFF/georaster-layer-for-leaflet — `vendor/georaster/georaster-layer-for-leaflet.LICENSE` |

georaster bundles geotiff.js (MIT) and proj4js (MIT).

The Python pipeline in `ml/` is not bundled; it depends on numpy, pandas, scipy,
rasterio, pyproj, shapely, scikit-learn, LightGBM, XGBoost and PyTorch, each under
its own permissive licence (BSD/MIT/Apache-2.0), installed from PyPI via
`ml/requirements.txt`.

Map tiles are fetched at run time from OpenStreetMap (ODbL data, © OpenStreetMap
contributors), OpenTopoMap (CC BY-SA 3.0) and Esri World Imagery (Esri terms);
forest masks from Luke's WMS (CC BY 4.0); elevation readouts from Open-Meteo
(CC BY 4.0, Copernicus DEM).
