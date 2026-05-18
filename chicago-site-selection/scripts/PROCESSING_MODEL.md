# QGIS Processing Model — Site Selection Chain

This file documents the equivalent QGIS Model Builder graph for the
analysis pipeline. The PyQGIS script (`build_qgis_project.py`) is the
canonical executable form; this Model Builder representation is the
graphical equivalent for the QGIS Processing Toolbox.

## How to build the model in QGIS

1. **Processing → Toolbox → Models → Create new model…**
2. Drag in the **inputs** listed below from the left panel
3. Drag in the **algorithms** listed below and wire them together
4. Save as `processing/site_selection.model3`

## Inputs (top of the model)

| Name              | Type            | Source layer                          |
|-------------------|-----------------|---------------------------------------|
| `tracts`          | Vector polygon  | data/tracts.gpkg \| layer=tracts      |
| `cta_stops`       | Vector point    | data/cta_rail_stops.gpkg              |
| `competitor_cafes`| Vector point    | data/competitor_cafes.gpkg            |
| `poi`             | Vector point    | data/foot_traffic_poi.gpkg            |

## Algorithm chain

```
INPUT tracts ──► [1] Reproject layer (EPSG:3435)    ──► tracts_ft
INPUT cta_stops ─► [2] Reproject layer (EPSG:3435)  ──► stops_ft
INPUT competitor_cafes ─► [3] Reproject (EPSG:3435) ──► cafes_ft
INPUT poi ──► [4] Reproject layer (EPSG:3435)       ──► poi_ft

tracts_ft, stops_ft     ──► [5] Distance to nearest hub (line to hub)
                              field_name = "dist_to_cta_ft"
                              hub_field = "station_name"

→ [6] Distance to nearest hub (competitor cafes)
       field_name = "dist_to_competitor_ft"

→ [7] Centroids (polygon → point)             ──► tract_centroids
tract_centroids ──► [8] Buffer (1320 ft)      ──► centroid_buffers
centroid_buffers, poi_ft ──► [9] Count points in polygon
       field_name = "poi_count_qmile"

→ [10] Field calculator: score_income       = scale_linear("median_hh_income", min, max, 0, 1)
→ [11] Field calculator: score_density      = scale_linear("pop_density_sqmi", 0, 35000, 0, 1)
→ [12] Field calculator: score_education    = scale_linear("pct_bachelors_plus", 0, 100, 0, 1)
→ [13] Field calculator: score_transit      = scale_linear(1/(1 + "dist_to_cta_ft"/5280), …)
→ [14] Field calculator: score_foot_traffic = scale_linear("poi_count_qmile", 0, 60, 0, 1)
→ [15] Field calculator: score_competition  = exp(-((("dist_to_competitor_ft"/5280) - 0.4)^2) / (2*0.5^2))

→ [16] Field calculator: suitability =
         0.18 * "score_income"
       + 0.20 * "score_density"
       + 0.12 * "score_education"
       + 0.18 * "score_transit"
       + 0.22 * "score_foot_traffic"
       + 0.10 * "score_competition"

→ [17] Field calculator: suitability_pct = "suitability" * 100

→ OUTPUT tracts_scored.gpkg
```

## Hot-spot extension

QGIS native processing does not ship a Gi* algorithm out of the box (it
exists in the *Hotspot Analysis* plugin and the *PySAL Processing* plugin).
For a fully native workflow, run the Gi* step from Python (`analysis.py`)
and ingest the resulting `gi_class` field back into the model.

If you have the *PySAL Processing* plugin installed:

```
tracts_scored ──► [18] PySAL: Local Getis-Ord (G*)
                   weights = KNN (k=8)
                   permutations = 999
                   output_field = "gi_z", "gi_p"
                ──► OUTPUT hotspots.gpkg
```

## Why PyQGIS instead of a .model3 file

The Model Builder graph is excellent for reviewers who prefer visual
pipelines, but it serializes to a brittle XML format that is sensitive to
QGIS version drift. The PyQGIS script in `build_qgis_project.py` is the
canonical implementation: it builds the project, the symbology, *and* the
print layouts in one pass, and is version-stable from QGIS 3.16 onward.
