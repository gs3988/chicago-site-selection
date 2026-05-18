# Live Data Sources

All synthetic layers in this project are stand-ins for authoritative
real-world sources. This file documents the exact endpoints used by
`scripts/data_pipeline.py --live` mode.

## Chicago Open Data Portal (Socrata)

| Layer              | Dataset ID  | Endpoint                                                              |
|--------------------|-------------|------------------------------------------------------------------------|
| Community areas    | cauq-8yn6   | https://data.cityofchicago.org/api/geospatial/cauq-8yn6?method=export&format=GeoJSON |
| CTA 'L' stops      | 8mj8-j3c4   | https://data.cityofchicago.org/api/geospatial/8mj8-j3c4?method=export&format=GeoJSON |
| CTA bus stops      | qs84-j7wh   | https://data.cityofchicago.org/api/geospatial/qs84-j7wh?method=export&format=GeoJSON |
| Business licenses  | r5kz-chrr   | https://data.cityofchicago.org/resource/r5kz-chrr.json                |
| Zoning districts   | dj47-wfun   | https://data.cityofchicago.org/api/geospatial/dj47-wfun?method=export&format=GeoJSON |

For competitor cafes, filter `business_licenses` by:
```
license_description = 'Retail Food Establishment'
AND business_activity ILIKE '%coffee%' OR doing_business_as_name ILIKE '%coffee%'
```

## U.S. Census Bureau

| Layer              | Source                                                                  |
|--------------------|-------------------------------------------------------------------------|
| Census tracts 2023 | https://www2.census.gov/geo/tiger/TIGER2023/TRACT/tl_2023_17_tract.zip  |
| ACS 5-yr 2022      | https://api.census.gov/data/2022/acs/acs5                                |

ACS variables used:
- `B19013_001E` — median household income
- `B01003_001E` — total population
- `B25077_001E` — median home value
- `B15003_022E + B15003_023E + B15003_024E + B15003_025E` — Bachelor's+ count
- `B15003_001E` — denominator for educational attainment

Cook County filter: `state=17&county=031`.

## OpenStreetMap (POI / foot-traffic)

Overpass API query for amenity-based POIs within Chicago bounding box:

```
[out:json][timeout:300];
(
  node["amenity"~"restaurant|cafe|fast_food|bar|pub|bank|pharmacy"](41.644,-87.940,42.023,-87.524);
  node["shop"](41.644,-87.940,42.023,-87.524);
  node["office"](41.644,-87.940,42.023,-87.524);
);
out body;
```

Endpoint: https://overpass-api.de/api/interpreter

## API key requirements

- **Chicago Open Data**: no key required for moderate volume; register an
  app token (`X-App-Token` header) for >1k req/hr.
- **U.S. Census**: free API key from https://api.census.gov/data/key_signup.html
- **OpenStreetMap Overpass**: no key, respect rate limits (1 query / sec).

## Switching modes

In `scripts/data_pipeline.py`, comment out the `synthesize_*` calls in
`main()` and uncomment the corresponding live fetches. The downstream
analysis (`analysis.py`) is data-source-agnostic — it reads from the same
GeoPackage layer names regardless.
