"""
analysis.py
=============
Chicago Retail Site Selection — Multi-Criteria Suitability + Hot Spot Analysis

Pipeline:
    1. Load all input layers from ../data/*.gpkg
    2. Compute per-tract criteria:
         - INCOME      : median household income (higher = better)
         - DENSITY     : population density per sq mi (higher = better)
         - EDUCATION   : % adults w/ Bachelor's+ (higher = better)
         - TRANSIT     : inverse distance to nearest CTA 'L' stop (closer = better)
         - FOOT_TRAFFIC: count of POI within 0.25 mi (higher = better)
         - COMPETITION : distance to nearest competitor (farther = better,
                         but penalized if TOO far → market validation signal)
    3. Min-max normalize each criterion → [0, 1]
    4. Weighted overlay with documented weights
    5. Getis-Ord Gi* hot spot analysis on suitability score
    6. Identify top 10 candidate sites

Outputs (to ../data/results.gpkg):
    tracts_scored    Tracts w/ all criterion scores, weights, suitability
    top_sites        Top-10 candidate tracts (point at centroid)
    hotspots         Statistically significant hot/cold clusters

Author: portfolio piece
"""

from __future__ import annotations

import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from libpysal.weights import KNN
from esda.getisord import G_Local
from shapely.geometry import Point

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WGS84 = "EPSG:4326"
IL_EAST = "EPSG:3435"

# Documented criterion weights (must sum to 1.0).
# These reflect a typical retail-coffee site-selection model:
#   - foot traffic & density are top signals
#   - income & education capture purchasing power for premium product
#   - transit access is the urban-mobility factor
#   - competition is included with a moderate weight (we want SOME nearby
#     activity but not direct saturation)
WEIGHTS = {
    "income":       0.18,
    "density":      0.20,
    "education":    0.12,
    "transit":      0.18,
    "foot_traffic": 0.22,
    "competition":  0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def load_inputs():
    tracts = gpd.read_file(DATA_DIR / "tracts.gpkg", layer="tracts")
    stops  = gpd.read_file(DATA_DIR / "cta_rail_stops.gpkg", layer="cta_rail_stops")
    comps  = gpd.read_file(DATA_DIR / "competitor_cafes.gpkg", layer="competitor_cafes")
    poi    = gpd.read_file(DATA_DIR / "foot_traffic_poi.gpkg", layer="foot_traffic_poi")
    return tracts, stops, comps, poi


def project_all(layers):
    return [g.to_crs(IL_EAST) for g in layers]


def minmax(s: pd.Series) -> pd.Series:
    """Min-max normalize to [0, 1]."""
    rng = s.max() - s.min()
    if rng == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.min()) / rng


def compute_criteria(tracts, stops, comps, poi):
    """Add raw criterion columns to tracts (projected)."""
    centroids = tracts.geometry.centroid

    # ---- TRANSIT: distance (ft) to nearest CTA stop ----
    stops_sindex = stops.sindex
    transit_dist = []
    for c in centroids:
        # nearest_geometry via sindex
        idx = list(stops_sindex.nearest(c, return_all=False))[1]
        nearest = stops.geometry.iloc[idx[0]] if hasattr(idx, "__len__") else stops.geometry.iloc[idx]
        transit_dist.append(c.distance(nearest))
    tracts["dist_to_cta_ft"] = transit_dist

    # ---- COMPETITION: distance (ft) to nearest competitor cafe ----
    comps_sindex = comps.sindex
    comp_dist = []
    for c in centroids:
        idx = list(comps_sindex.nearest(c, return_all=False))[1]
        nearest = comps.geometry.iloc[idx[0]] if hasattr(idx, "__len__") else comps.geometry.iloc[idx]
        comp_dist.append(c.distance(nearest))
    tracts["dist_to_competitor_ft"] = comp_dist

    # ---- FOOT TRAFFIC: POI count within 0.25 mi (1320 ft) of centroid ----
    buf = centroids.buffer(1320)
    buf_gdf = gpd.GeoDataFrame({"_i": range(len(buf))}, geometry=buf.values, crs=IL_EAST)
    joined = gpd.sjoin(poi, buf_gdf, how="inner", predicate="intersects")
    counts = joined.groupby("_i").size()
    tracts["poi_count_qmile"] = tracts.index.map(lambda i: int(counts.get(i, 0)))

    return tracts


def score(tracts):
    """Compute normalized criteria + weighted suitability."""
    df = tracts.copy()

    df["score_income"]    = minmax(df["median_hh_income"])
    df["score_density"]   = minmax(df["pop_density_sqmi"].clip(upper=df["pop_density_sqmi"].quantile(0.98)))
    df["score_education"] = minmax(df["pct_bachelors_plus"])

    # Transit: closer is better → invert (use 1 / (1 + dist_mi))
    dist_mi = df["dist_to_cta_ft"] / 5280
    df["score_transit"]   = minmax(1 / (1 + dist_mi))

    df["score_foot_traffic"] = minmax(df["poi_count_qmile"])

    # Competition: a parabolic preference — best at ~0.4 mi from nearest
    # competitor (validates market, no direct saturation), worse if too
    # close (<0.1 mi) or too isolated (>1.5 mi)
    comp_mi = df["dist_to_competitor_ft"] / 5280
    optimal = 0.4
    raw = np.exp(-((comp_mi - optimal) ** 2) / (2 * 0.5 ** 2))
    df["score_competition"] = minmax(pd.Series(raw, index=df.index))

    # Weighted overlay
    df["suitability"] = (
        WEIGHTS["income"]       * df["score_income"]
      + WEIGHTS["density"]      * df["score_density"]
      + WEIGHTS["education"]    * df["score_education"]
      + WEIGHTS["transit"]      * df["score_transit"]
      + WEIGHTS["foot_traffic"] * df["score_foot_traffic"]
      + WEIGHTS["competition"]  * df["score_competition"]
    )
    df["suitability_pct"] = (df["suitability"] * 100).round(1)
    return df


def hotspot_analysis(tracts_scored):
    """Getis-Ord Gi* on the suitability score using a KNN-8 weights matrix."""
    centroids = tracts_scored.geometry.centroid
    coords = np.column_stack([centroids.x.values, centroids.y.values])
    w = KNN.from_array(coords, k=8)
    w.transform = "r"

    gi = G_Local(tracts_scored["suitability"].values, w, star=True, permutations=999, seed=42)

    out = tracts_scored.copy()
    out["gi_z"] = gi.Zs
    out["gi_p"] = gi.p_sim
    # Classify by permutation p-value + sign of standardized score
    # (ArcGIS-equivalent Gi_Bin scheme: ±3 at 99%, ±2 at 95%, ±1 at 90%)
    def cls(z, p):
        if p > 0.10 or np.isnan(z):
            return "Not significant"
        sign = "Hot" if z > 0 else "Cold"
        if p < 0.01:  ci = "99%"
        elif p < 0.05: ci = "95%"
        else:          ci = "90%"
        return f"{sign} ({ci})"
    out["gi_class"] = [cls(z, p) for z, p in zip(out["gi_z"], out["gi_p"])]
    return out


def top_sites(tracts_scored, n: int = 10):
    """Top-N candidate tracts, returned as centroid points with full attribution."""
    top = tracts_scored.nlargest(n, "suitability").copy().reset_index(drop=True)
    top["rank"] = range(1, len(top) + 1)
    top_pts = gpd.GeoDataFrame(
        top.drop(columns="geometry"),
        geometry=top.geometry.centroid.values,
        crs=tracts_scored.crs,
    )
    cols = [
        "rank", "tract_id", "community_area", "side",
        "median_hh_income", "pop_density_sqmi", "pct_bachelors_plus",
        "poi_count_qmile", "dist_to_cta_ft", "dist_to_competitor_ft",
        "suitability_pct", "geometry",
    ]
    return top_pts[cols]


def main():
    print(">> Loading input layers...")
    tracts, stops, comps, poi = load_inputs()
    print(f"   {len(tracts)} tracts | {len(stops)} CTA stops | {len(comps)} competitors | {len(poi)} POI")

    print(">> Reprojecting to EPSG:3435 (NAD83 / IL East ftUS)...")
    tracts, stops, comps, poi = project_all([tracts, stops, comps, poi])

    print(">> Computing per-tract criteria (transit dist, competition dist, POI count)...")
    tracts = compute_criteria(tracts, stops, comps, poi)

    print(">> Scoring + weighted overlay...")
    scored = score(tracts)
    print(f"   Suitability range: {scored['suitability_pct'].min():.1f}% — {scored['suitability_pct'].max():.1f}%")

    print(">> Getis-Ord Gi* hot spot analysis (KNN-8, 999 permutations)...")
    scored = hotspot_analysis(scored)
    n_hot = (scored["gi_class"].str.startswith("Hot")).sum()
    n_cold = (scored["gi_class"].str.startswith("Cold")).sum()
    print(f"   Hot clusters: {n_hot} tracts | Cold clusters: {n_cold} tracts")

    print(">> Top-10 candidate sites...")
    top = top_sites(scored, n=10)
    for _, r in top.iterrows():
        print(f"   #{int(r['rank']):2d} {r['community_area']:<25s} suitability={r['suitability_pct']:.1f}%")

    # Reproject results back to WGS84 for QGIS-friendly storage
    print(">> Writing results...")
    out = DATA_DIR / "results.gpkg"
    # Remove if exists (rewrite cleanly)
    if out.exists():
        out.unlink()
    scored.to_crs(WGS84).to_file(out, layer="tracts_scored", driver="GPKG")
    top.to_crs(WGS84).to_file(out, layer="top_sites", driver="GPKG")
    # Hotspots layer = just tracts w/ significant Gi*
    sig = scored[scored["gi_class"] != "Not significant"].copy()
    sig.to_crs(WGS84).to_file(out, layer="hotspots", driver="GPKG")

    print(f"\nDone. Results written to {out}")


if __name__ == "__main__":
    main()
