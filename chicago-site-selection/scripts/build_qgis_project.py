"""
build_qgis_project.py
=======================
PyQGIS — assemble the full QGIS .qgz project from scratch.

USAGE (inside QGIS):
    1. Run scripts/data_pipeline.py and scripts/analysis.py first
    2. Open QGIS Desktop (≥ 3.28 LTR)
    3. Plugins → Python Console → Show Editor
    4. Open this file in the editor and click Run

Or from the command line:
    qgis --code scripts/build_qgis_project.py

WHAT IT BUILDS:
    • A QGIS project with EPSG:3435 (NAD83 / IL East ftUS) as the project CRS
    • 8 layers, properly symbolized:
        - Study boundary               (transparent fill, 1.4 mm outline)
        - Community areas              (categorized by 'side')
        - Suitability tracts           (graduated by suitability_pct, RdYlBu_r)
        - Hot spot tracts              (categorized by gi_class — ArcGIS-style bins)
        - CTA 'L' rail stops           (red circle markers + labels)
        - Foot-traffic POI             (small grey points, 30% opacity)
        - Competitor cafes             (cross markers, accent color)
        - Top-10 candidate sites       (numbered red circles + labels)
    • 4 print layouts (A3 portrait, 297 × 420 mm):
        - 01 Overview
        - 02 Suitability
        - 03 Hot Spots (Gi*)
        - 04 Top-10 Sites
    • Saves the project as project/site_selection.qgz

Author: portfolio piece
"""

from __future__ import annotations

from pathlib import Path

# --- PyQGIS imports ------------------------------------------------------
# These imports only resolve inside a QGIS-bundled Python interpreter.
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, QgsLayerTreeGroup,
    QgsSymbol, QgsSimpleFillSymbolLayer, QgsSimpleLineSymbolLayer, QgsSimpleMarkerSymbolLayer,
    QgsRendererCategory, QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsClassificationQuantile,
    QgsRendererRangeLabelFormat, QgsStyle, QgsGradientColorRamp,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
    QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel,
    QgsLayoutItemLegend, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
    QgsLayoutSize, QgsUnitTypes, QgsLayoutPoint, QgsRectangle,
    QgsLayoutItemPage, QgsLayoutMeasurement, QgsLegendStyle,
    QgsLayerTree,
)
from qgis.PyQt.QtCore import QSize, QSizeF, QPointF
from qgis.PyQt.QtGui import QColor, QFont

# ------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROJECT_DIR = ROOT / "project"
PROJECT_DIR.mkdir(exist_ok=True)
PROJECT_PATH = PROJECT_DIR / "site_selection.qgz"

PROJECT_CRS = "EPSG:3435"  # NAD83 / Illinois East (ftUS)

# Brand colors
INK    = QColor("#1c1c1c")
ACCENT = QColor("#c8423a")
BG     = QColor("#f4f1ec")


# =================== HELPERS ============================================

def add_vector(uri_path: Path, layer_name: str, gpkg_layer: str) -> QgsVectorLayer:
    """Load a GeoPackage layer into the project, reproject to project CRS."""
    uri = f"{uri_path}|layername={gpkg_layer}"
    lyr = QgsVectorLayer(uri, layer_name, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Failed to load {uri}")
    QgsProject.instance().addMapLayer(lyr)
    return lyr


def simple_fill(color: str, outline_color: str = "#ffffff", outline_w: float = 0.2) -> QgsSymbol:
    sym = QgsSymbol.defaultSymbol(2)  # 2 = polygon geometry
    sym.deleteSymbolLayer(0)
    fill = QgsSimpleFillSymbolLayer(QColor(color))
    fill.setStrokeColor(QColor(outline_color))
    fill.setStrokeWidth(outline_w)
    sym.appendSymbolLayer(fill)
    return sym


def transparent_outline(outline_color: str, w: float = 1.4) -> QgsSymbol:
    sym = QgsSymbol.defaultSymbol(2)
    sym.deleteSymbolLayer(0)
    fill = QgsSimpleFillSymbolLayer(QColor(0, 0, 0, 0))
    fill.setStrokeColor(QColor(outline_color))
    fill.setStrokeWidth(w)
    sym.appendSymbolLayer(fill)
    return sym


def simple_marker(color: str, size: float = 2.6, outline_color: str = "#ffffff",
                  outline_w: float = 0.4, shape: str = "circle") -> QgsSymbol:
    sym = QgsSymbol.defaultSymbol(0)  # 0 = point
    sym.deleteSymbolLayer(0)
    m = QgsSimpleMarkerSymbolLayer()
    m.setColor(QColor(color))
    m.setSize(size)
    m.setStrokeColor(QColor(outline_color))
    m.setStrokeWidth(outline_w)
    m.setShape(QgsSimpleMarkerSymbolLayer.Circle if shape == "circle" else QgsSimpleMarkerSymbolLayer.Cross2)
    sym.appendSymbolLayer(m)
    return sym


# =================== SYMBOLOGY ==========================================

def style_community_areas(lyr: QgsVectorLayer):
    side_colors = {
        "North":   "#d8e5c8",
        "Central": "#e9c9b1",
        "South":   "#c4d6e0",
        "West":    "#dccfe0",
    }
    cats = []
    for side, col in side_colors.items():
        sym = simple_fill(col, outline_color="#ffffff", outline_w=0.3)
        cats.append(QgsRendererCategory(side, sym, side))
    renderer = QgsCategorizedSymbolRenderer("side", cats)
    lyr.setRenderer(renderer)
    lyr.setOpacity(0.85)
    lyr.triggerRepaint()


def style_boundary(lyr: QgsVectorLayer):
    lyr.setRenderer(_renderer_single(transparent_outline("#1c1c1c", 1.4)))
    lyr.triggerRepaint()


def _renderer_single(symbol):
    from qgis.core import QgsSingleSymbolRenderer
    return QgsSingleSymbolRenderer(symbol)


def style_suitability(lyr: QgsVectorLayer):
    """Graduated: 7 quantile classes, custom diverging ramp."""
    colors = ["#1a4561", "#3d8095", "#8fc1a9", "#cce0c2",
              "#f6e0a6", "#e89c5a", "#c8423a"]
    n = len(colors)
    # Compute breaks manually via quantile of the attribute
    vals = sorted([f["suitability_pct"] for f in lyr.getFeatures()])
    if not vals:
        return
    qs = [vals[int((i + 1) / n * (len(vals) - 1))] for i in range(n)]
    prev_lo = min(vals)
    ranges = []
    for i in range(n):
        hi = qs[i] if i < n - 1 else max(vals)
        sym = simple_fill(colors[i], outline_color="#ffffff", outline_w=0.05)
        ranges.append(QgsRendererRange(prev_lo, hi, sym, f"{prev_lo:.0f}–{hi:.0f}"))
        prev_lo = hi
    renderer = QgsGraduatedSymbolRenderer("suitability_pct", ranges)
    lyr.setRenderer(renderer)
    lyr.triggerRepaint()


def style_hotspots(lyr: QgsVectorLayer):
    cls_colors = {
        "Hot (99%)":     "#a32118",
        "Hot (95%)":     "#d6604d",
        "Hot (90%)":     "#f4a582",
        "Not significant": "#ececec",
        "Cold (90%)":    "#92c5de",
        "Cold (95%)":    "#4393c3",
        "Cold (99%)":    "#2166ac",
    }
    cats = []
    for cls, col in cls_colors.items():
        sym = simple_fill(col, outline_color="#ffffff", outline_w=0.05)
        cats.append(QgsRendererCategory(cls, sym, cls))
    renderer = QgsCategorizedSymbolRenderer("gi_class", cats)
    lyr.setRenderer(renderer)
    lyr.triggerRepaint()


def style_cta_stops(lyr: QgsVectorLayer):
    lyr.setRenderer(_renderer_single(
        simple_marker("#c8423a", size=2.4, outline_color="#ffffff", outline_w=0.4)
    ))
    # Labels
    s = QgsPalLayerSettings()
    s.fieldName = "station_name"
    fmt = QgsTextFormat()
    f = QFont("DejaVu Sans", 7)
    f.setBold(True)
    fmt.setFont(f)
    fmt.setColor(INK)
    s.setFormat(fmt)
    s.placement = QgsPalLayerSettings.AroundPoint
    lyr.setLabelsEnabled(True)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(s))
    lyr.triggerRepaint()


def style_competitors(lyr: QgsVectorLayer):
    lyr.setRenderer(_renderer_single(
        simple_marker("#444444", size=1.6, outline_color="#ffffff", outline_w=0.2, shape="cross")
    ))
    lyr.setOpacity(0.6)
    lyr.triggerRepaint()


def style_poi(lyr: QgsVectorLayer):
    lyr.setRenderer(_renderer_single(
        simple_marker("#666666", size=0.6, outline_color="#666666", outline_w=0.0)
    ))
    lyr.setOpacity(0.35)
    lyr.triggerRepaint()


def style_top_sites(lyr: QgsVectorLayer):
    lyr.setRenderer(_renderer_single(
        simple_marker("#c8423a", size=6.5, outline_color="#1c1c1c", outline_w=0.6)
    ))
    # Numbered labels
    s = QgsPalLayerSettings()
    s.fieldName = "rank"
    fmt = QgsTextFormat()
    f = QFont("DejaVu Sans", 9)
    f.setBold(True)
    fmt.setFont(f)
    fmt.setColor(QColor("#ffffff"))
    s.setFormat(fmt)
    s.placement = QgsPalLayerSettings.OverPoint
    lyr.setLabelsEnabled(True)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(s))
    lyr.triggerRepaint()


# =================== LAYOUTS ============================================

def make_layout(name: str, title: str, subtitle: str, visible_layers: list[str]) -> QgsPrintLayout:
    project = QgsProject.instance()
    manager = project.layoutManager()
    # If a layout with this name exists, remove first
    existing = manager.layoutByName(name)
    if existing:
        manager.removeLayout(existing)

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(name)

    # A3 portrait = 297 x 420
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(297, 420, QgsUnitTypes.LayoutMillimeters))

    # Title
    title_label = QgsLayoutItemLabel(layout)
    title_label.setText(title)
    f = QFont("DejaVu Sans", 22)
    f.setBold(True)
    title_label.setFont(f)
    title_label.setFontColor(INK)
    title_label.attemptResize(QgsLayoutSize(270, 14, QgsUnitTypes.LayoutMillimeters))
    title_label.attemptMove(QgsLayoutPoint(12, 10, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(title_label)

    # Subtitle
    sub_label = QgsLayoutItemLabel(layout)
    sub_label.setText(subtitle)
    sf = QFont("DejaVu Sans", 10)
    sub_label.setFont(sf)
    sub_label.setFontColor(QColor("#555555"))
    sub_label.attemptResize(QgsLayoutSize(270, 8, QgsUnitTypes.LayoutMillimeters))
    sub_label.attemptMove(QgsLayoutPoint(12, 22, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(sub_label)

    # Map item
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(20, 30, 257, 350)
    map_item.attemptMove(QgsLayoutPoint(12, 32, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(273, 340, QgsUnitTypes.LayoutMillimeters))

    # Filter visible layers
    project_layers = project.mapLayers().values()
    visible = [l for l in project_layers if l.name() in visible_layers]
    map_item.setLayers(visible)
    map_item.setCrs(QgsCoordinateReferenceSystem(PROJECT_CRS))
    # Zoom to first polygon layer extent
    if visible:
        extent = visible[0].extent()
        for l in visible[1:]:
            extent.combineExtentWith(l.extent())
        map_item.zoomToExtent(extent)
    layout.addLayoutItem(map_item)

    # Scale bar
    sb = QgsLayoutItemScaleBar(layout)
    sb.setStyle("Single Box")
    sb.setUnits(QgsUnitTypes.DistanceMiles)
    sb.setNumberOfSegments(2)
    sb.setNumberOfSegmentsLeft(0)
    sb.setUnitsPerSegment(2)
    sb.setUnitLabel("mi")
    sb.setLinkedMap(map_item)
    sb.attemptMove(QgsLayoutPoint(16, 380, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(sb)

    # Legend
    leg = QgsLayoutItemLegend(layout)
    leg.setTitle("Legend")
    leg.setLinkedMap(map_item)
    leg.attemptResize(QgsLayoutSize(80, 70, QgsUnitTypes.LayoutMillimeters))
    leg.attemptMove(QgsLayoutPoint(200, 320, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(leg)

    # Credit
    credit = QgsLayoutItemLabel(layout)
    credit.setText("Chicago Open Data Portal (live) / synthetic mirror (demo)  |  Analysis: weighted overlay + Gi*  |  CRS: NAD83 / IL East (ftUS)")
    cf = QFont("DejaVu Sans", 7)
    credit.setFont(cf)
    credit.setFontColor(QColor("#777777"))
    credit.attemptResize(QgsLayoutSize(270, 5, QgsUnitTypes.LayoutMillimeters))
    credit.attemptMove(QgsLayoutPoint(12, 408, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(credit)

    manager.addLayout(layout)
    return layout


# =================== MAIN ===============================================

def main():
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem(PROJECT_CRS))

    # Load layers (order = draw order, bottom first)
    print("Loading layers...")
    boundary  = add_vector(DATA / "study_boundary.gpkg",   "Study boundary",   "study_boundary")
    community = add_vector(DATA / "community_areas.gpkg",  "Community areas",  "community_areas")
    suit      = add_vector(DATA / "results.gpkg",          "Suitability",      "tracts_scored")
    hot       = add_vector(DATA / "results.gpkg",          "Hot spots (Gi*)",  "hotspots")
    poi       = add_vector(DATA / "foot_traffic_poi.gpkg", "POI (foot traffic)","foot_traffic_poi")
    comps     = add_vector(DATA / "competitor_cafes.gpkg", "Competitor cafes", "competitor_cafes")
    stops     = add_vector(DATA / "cta_rail_stops.gpkg",   "CTA 'L' stops",    "cta_rail_stops")
    top       = add_vector(DATA / "results.gpkg",          "Top-10 sites",     "top_sites")

    print("Applying symbology...")
    style_boundary(boundary)
    style_community_areas(community)
    style_suitability(suit)
    style_hotspots(hot)
    style_poi(poi)
    style_competitors(comps)
    style_cta_stops(stops)
    style_top_sites(top)

    print("Building print layouts...")
    make_layout(
        "01_Overview",
        "Chicago — Study Area Overview",
        "77 community areas | 87 CTA 'L' stations | NAD83 / IL East ftUS",
        ["Study boundary", "Community areas", "CTA 'L' stops"],
    )
    make_layout(
        "02_Suitability",
        "Retail Site Suitability — Coffee Concept",
        "Weighted multi-criteria overlay across tract-equivalents",
        ["Study boundary", "Suitability", "CTA 'L' stops"],
    )
    make_layout(
        "03_HotSpots",
        "Statistical Hot Spot Analysis (Getis-Ord Gi*)",
        "KNN-8 weights | 999 conditional permutations | 90/95/99% CI",
        ["Study boundary", "Hot spots (Gi*)", "CTA 'L' stops"],
    )
    make_layout(
        "04_TopSites",
        "Top-10 Candidate Sites",
        "Ranked by composite suitability score | site = tract centroid",
        ["Study boundary", "Suitability", "CTA 'L' stops", "Top-10 sites"],
    )

    print(f"Saving project → {PROJECT_PATH}")
    project.write(str(PROJECT_PATH))

    print("Done. Open project/site_selection.qgz in QGIS to view + edit.")


if __name__ == "__console__" or __name__ == "__main__":
    main()
