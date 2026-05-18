"""
generate_previews.py
=====================
Render print-ready PNG previews of the four core layouts.

These mirror exactly what the PyQGIS build script will produce as QGIS print
layouts. They serve two purposes:
    1. Portfolio screenshots (linkable, shareable, embeddable)
    2. Visual QC of the analysis before opening QGIS

Layouts:
    01_overview.png         Study area + community areas + CTA network
    02_suitability.png      Choropleth of the weighted suitability score
    03_hotspots.png         Getis-Ord Gi* hot/cold clusters
    04_top_sites.png        Top-10 ranked candidate sites on suitability backdrop
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, Normalize
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT  = ROOT / "preview"
OUT.mkdir(exist_ok=True)

# Use a web-mercator projection for clean tile-friendly previews
WEB_MERC = "EPSG:3857"

# Brand-quality colors
BG = "#f4f1ec"
INK = "#1c1c1c"
ACCENT = "#c8423a"
TEAL = "#2a7f7a"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.facecolor": BG,
    "figure.facecolor": BG,
    "savefig.facecolor": BG,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "text.color": INK,
})


def load_all():
    return {
        "boundary":   gpd.read_file(DATA / "study_boundary.gpkg",     layer="study_boundary").to_crs(WEB_MERC),
        "community":  gpd.read_file(DATA / "community_areas.gpkg",    layer="community_areas").to_crs(WEB_MERC),
        "tracts":     gpd.read_file(DATA / "tracts.gpkg",             layer="tracts").to_crs(WEB_MERC),
        "stops":      gpd.read_file(DATA / "cta_rail_stops.gpkg",     layer="cta_rail_stops").to_crs(WEB_MERC),
        "competitors":gpd.read_file(DATA / "competitor_cafes.gpkg",   layer="competitor_cafes").to_crs(WEB_MERC),
        "poi":        gpd.read_file(DATA / "foot_traffic_poi.gpkg",   layer="foot_traffic_poi").to_crs(WEB_MERC),
        "scored":     gpd.read_file(DATA / "results.gpkg",            layer="tracts_scored").to_crs(WEB_MERC),
        "top":        gpd.read_file(DATA / "results.gpkg",            layer="top_sites").to_crs(WEB_MERC),
        "hotspots":   gpd.read_file(DATA / "results.gpkg",            layer="hotspots").to_crs(WEB_MERC),
    }


def setup_axes(ax, boundary):
    minx, miny, maxx, maxy = boundary.total_bounds
    pad = (maxx - minx) * 0.04
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)
    ax.set_aspect("equal")
    ax.set_axis_off()


def title_block(fig, title, subtitle, methods=None):
    fig.text(0.04, 0.965, title, fontsize=22, fontweight="bold", color=INK)
    fig.text(0.04, 0.940, subtitle, fontsize=11, color=INK, alpha=0.75)
    if methods:
        fig.text(0.04, 0.040, methods, fontsize=8, color=INK, alpha=0.65, ha="left", va="bottom")


def add_north_scale(ax, boundary):
    minx, miny, maxx, maxy = boundary.total_bounds
    w = maxx - minx
    h = maxy - miny
    # North arrow
    ax.annotate("N", xy=(maxx - 0.04 * w, maxy - 0.08 * h),
                xytext=(maxx - 0.04 * w, maxy - 0.16 * h),
                arrowprops=dict(facecolor=INK, edgecolor=INK, width=4, headwidth=12),
                ha="center", fontsize=14, fontweight="bold", color=INK)
    # Scale bar (5 km in web-merc — distortion-adjusted, approximate)
    scale_m = 5000 * 1.32  # web-merc latitude correction for ~41.8°
    x0 = minx + 0.04 * w
    y0 = miny + 0.06 * h
    ax.plot([x0, x0 + scale_m], [y0, y0], color=INK, linewidth=3, solid_capstyle="butt")
    ax.text(x0 + scale_m / 2, y0 + 0.012 * h, "5 km", ha="center", fontsize=9, color=INK)


# ---------------------------------------------------------------- LAYOUT 1
def overview_layout(data):
    fig, ax = plt.subplots(figsize=(11, 14))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.06)

    boundary = data["boundary"]
    setup_axes(ax, boundary)

    # Side coloring of community areas
    side_colors = {"North":"#d8e5c8", "Central":"#e9c9b1", "South":"#c4d6e0", "West":"#dccfe0"}
    data["community"]["_c"] = data["community"]["side"].map(side_colors)
    data["community"].plot(ax=ax, color=data["community"]["_c"], edgecolor="white", linewidth=0.6, alpha=0.95)

    boundary.boundary.plot(ax=ax, color=INK, linewidth=1.5)

    # CTA stops
    data["stops"].plot(ax=ax, color=ACCENT, markersize=12, edgecolor="white", linewidth=0.4, zorder=5)

    # Label major community areas
    for _, r in data["community"].iterrows():
        if r["name"] in {"Loop", "Lincoln Park", "Hyde Park", "O'Hare", "Lake View", "Wicker Park",
                          "Englewood", "Pilsen", "Bridgeport", "Beverly", "Rogers Park", "Austin"}:
            c = r.geometry.centroid
            ax.text(c.x, c.y, r["name"], fontsize=7, ha="center", va="center",
                    color=INK, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.65, edgecolor="none"))

    add_north_scale(ax, boundary)

    # Legend
    handles = [mpatches.Patch(facecolor=c, edgecolor="white", label=f"{s} Side") for s, c in side_colors.items()]
    handles.append(Line2D([0], [0], marker="o", color="w", markerfacecolor=ACCENT,
                          markeredgecolor="white", markersize=8, label="CTA 'L' station"))
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.9,
              edgecolor=INK, fontsize=9)

    title_block(fig,
                "Chicago — Study Area Overview",
                "77 community areas | 87 CTA rail stations | Coordinate system: NAD83 / IL East (ftUS)",
                methods="Sources: Chicago Open Data Portal (live-mode), synthetic mirror dataset (demo-mode) | "
                        "Author: portfolio piece | Layout: 1 of 4")
    fig.savefig(OUT / "01_overview.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("  wrote 01_overview.png")


# ---------------------------------------------------------------- LAYOUT 2
def suitability_layout(data):
    fig, ax = plt.subplots(figsize=(11, 14))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.06)

    boundary = data["boundary"]
    setup_axes(ax, boundary)

    cmap = LinearSegmentedColormap.from_list(
        "suit",
        ["#1a4561", "#3d8095", "#8fc1a9", "#f6e0a6", "#e89c5a", "#c8423a"],
    )
    data["scored"].plot(
        ax=ax, column="suitability_pct", cmap=cmap,
        edgecolor="white", linewidth=0.1,
        legend=False, vmin=0, vmax=80,
    )
    boundary.boundary.plot(ax=ax, color=INK, linewidth=1.5)

    # Overlay CTA stations faintly for reference
    data["stops"].plot(ax=ax, color="white", markersize=10, edgecolor=INK, linewidth=0.5, alpha=0.7, zorder=5)

    add_north_scale(ax, boundary)

    # Custom colorbar
    cax = fig.add_axes([0.30, 0.085, 0.40, 0.018])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=Normalize(vmin=0, vmax=80))
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.set_label("Suitability score (%)", fontsize=10)
    cb.outline.set_edgecolor(INK)

    # Weights table inset
    weights_text = (
        "Weighted overlay:\n"
        "  Foot traffic   0.22\n"
        "  Population dens. 0.20\n"
        "  Transit access  0.18\n"
        "  Med. HH income  0.18\n"
        "  Education       0.12\n"
        "  Competition     0.10"
    )
    ax.text(0.022, 0.978, weights_text, transform=ax.transAxes, fontsize=8, va="top", ha="left",
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor=INK, linewidth=0.6))

    n_t = len(data["scored"])
    title_block(fig,
                "Retail Site Suitability — Coffee Concept",
                f"Multi-criteria weighted overlay across {n_t} tract-equivalents | EPSG:3435 analysis",
                methods="Method: min-max normalization → weighted sum. Competition uses Gaussian "
                        "preference centered at 0.4 mi from nearest existing cafe. | Layout: 2 of 4")
    fig.savefig(OUT / "02_suitability.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("  wrote 02_suitability.png")


# ---------------------------------------------------------------- LAYOUT 3
def hotspots_layout(data):
    fig, ax = plt.subplots(figsize=(11, 14))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.06)

    boundary = data["boundary"]
    setup_axes(ax, boundary)

    # Background: light tracts
    data["scored"].plot(ax=ax, color="#ececec", edgecolor="white", linewidth=0.1)

    class_colors = {
        "Hot (99%)":  "#a32118",
        "Hot (95%)":  "#d6604d",
        "Hot (90%)":  "#f4a582",
        "Cold (90%)": "#92c5de",
        "Cold (95%)": "#4393c3",
        "Cold (99%)": "#2166ac",
    }
    for cls, col in class_colors.items():
        sub = data["scored"][data["scored"]["gi_class"] == cls]
        if len(sub):
            sub.plot(ax=ax, color=col, edgecolor="white", linewidth=0.1)

    boundary.boundary.plot(ax=ax, color=INK, linewidth=1.5)

    # Stations as small reference markers
    data["stops"].plot(ax=ax, color=INK, markersize=4, alpha=0.6, zorder=5)

    add_north_scale(ax, boundary)

    handles = [mpatches.Patch(facecolor=c, label=l) for l, c in class_colors.items()]
    handles.append(mpatches.Patch(facecolor="#ececec", label="Not significant"))
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.92,
              edgecolor=INK, fontsize=9, title="Gi* cluster class")

    title_block(fig,
                "Statistical Hot Spot Analysis (Getis-Ord Gi*)",
                "KNN-8 spatial weights | 999 conditional permutations | classes at 90/95/99% CI",
                methods="Hot spots identify statistically significant clusters of high-suitability "
                        "tracts surrounded by other high-suitability tracts (and vice versa for cold). | Layout: 3 of 4")
    fig.savefig(OUT / "03_hotspots.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("  wrote 03_hotspots.png")


# ---------------------------------------------------------------- LAYOUT 4
def top_sites_layout(data):
    fig, ax = plt.subplots(figsize=(11, 14))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.06)

    boundary = data["boundary"]
    setup_axes(ax, boundary)

    cmap = LinearSegmentedColormap.from_list("suit_b", ["#f4f1ec", "#e7d6c2", "#caa57e", "#7a4a2f"])
    data["scored"].plot(ax=ax, column="suitability_pct", cmap=cmap,
                         edgecolor="white", linewidth=0.08, alpha=0.95,
                         vmin=0, vmax=80)
    boundary.boundary.plot(ax=ax, color=INK, linewidth=1.5)

    top = data["top"].copy()
    top["geometry"] = top.geometry  # already point
    # Halo + filled circle
    top.plot(ax=ax, color="white", markersize=320, edgecolor="white", zorder=10)
    top.plot(ax=ax, color=ACCENT, markersize=240, edgecolor=INK, linewidth=1.2, zorder=11)

    for _, r in top.iterrows():
        ax.text(r.geometry.x, r.geometry.y, str(int(r["rank"])),
                fontsize=10, fontweight="bold", color="white",
                ha="center", va="center", zorder=12)

    add_north_scale(ax, boundary)

    # Side panel: ranked table
    rank_text = ["#  Community            Score"]
    rank_text.append("─" * 36)
    for _, r in top.iterrows():
        rank_text.append(f"{int(r['rank']):>2}  {r['community_area'][:18]:<18}  {r['suitability_pct']:>5.1f}%")
    ax.text(0.022, 0.978, "\n".join(rank_text), transform=ax.transAxes,
            fontsize=8.5, va="top", ha="left", family="monospace",
            bbox=dict(boxstyle="round,pad=0.6", facecolor="white", alpha=0.95,
                       edgecolor=INK, linewidth=0.7))

    title_block(fig,
                "Top-10 Candidate Sites — Coffee Retail Concept",
                "Ranked by composite suitability score | site = tract centroid",
                methods="Next-step recommendations: 0.5-mi drive-time isochrone validation, "
                        "parcel-level zoning check (B1/B3), and visit-rate calibration vs. "
                        "Placer.ai or SafeGraph. | Layout: 4 of 4")
    fig.savefig(OUT / "04_top_sites.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("  wrote 04_top_sites.png")


def main():
    print(">> Loading layers...")
    data = load_all()
    print(">> Rendering layouts...")
    overview_layout(data)
    suitability_layout(data)
    hotspots_layout(data)
    top_sites_layout(data)
    print(f"\nDone. Previews in: {OUT}")


if __name__ == "__main__":
    main()
