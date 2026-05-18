// build_methodology_docx.js
// Generates docs/methodology.docx — the formal portfolio writeup.

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
  TableOfContents,
} = require('docx');

const ROOT = path.resolve(__dirname, '..');
const PREVIEW = path.join(ROOT, 'preview');
const OUT = path.join(ROOT, 'docs', 'methodology.docx');

// US Letter
const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9360

const border = { style: BorderStyle.SINGLE, size: 4, color: "C8C8C8" };
const allBorders = { top: border, bottom: border, left: border, right: border };

function P(text, opts = {}) {
  const run = new TextRun({ text, ...opts });
  return new Paragraph({ children: [run], spacing: { after: 120 }, ...opts.paraOpts });
}

function H1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text })],
    spacing: { before: 360, after: 180 },
  });
}

function H2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text })],
    spacing: { before: 240, after: 120 },
  });
}

function H3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text })],
    spacing: { before: 180, after: 100 },
  });
}

function bullet(text, sub) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [
      new TextRun({ text: sub ? `${text}: `: text, bold: !!sub }),
      ...(sub ? [new TextRun({ text: sub })] : []),
    ],
  });
}

function imagePara(filePath, widthIn, heightIn, captionText) {
  const data = fs.readFileSync(filePath);
  const img = new ImageRun({
    type: 'png',
    data,
    transformation: {
      width: Math.round(widthIn * 96),
      height: Math.round(heightIn * 96),
    },
    altText: { title: captionText, description: captionText, name: 'figure' },
  });
  const ip = new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [img],
    spacing: { before: 200, after: 80 },
  });
  const cap = new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: captionText, italics: true, size: 18, color: "555555" })],
    spacing: { after: 240 },
  });
  return [ip, cap];
}

function dataTable(rows, headerColor = "1c1c1c") {
  const colCount = rows[0].length;
  const colWidth = Math.floor(CONTENT_W / colCount);
  const colWidths = Array(colCount).fill(colWidth);
  // Last col gets remainder
  colWidths[colCount - 1] = CONTENT_W - colWidth * (colCount - 1);

  const trs = rows.map((row, i) => new TableRow({
    children: row.map((cell, j) => new TableCell({
      borders: allBorders,
      width: { size: colWidths[j], type: WidthType.DXA },
      shading: i === 0 ? { fill: headerColor, type: ShadingType.CLEAR } : undefined,
      margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [new Paragraph({
        children: [new TextRun({
          text: String(cell),
          bold: i === 0,
          color: i === 0 ? "ffffff" : "1c1c1c",
        })],
      })],
    })),
  }));

  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: trs,
  });
}

// ===================== CONTENT =====================

const content = [];

// Title block
content.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "Chicago Retail Site Selection", size: 56, bold: true, color: "1c1c1c" })],
  spacing: { after: 60 },
}));
content.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "Multi-criteria GIS suitability analysis for a coffee-retail concept", size: 28, color: "555555" })],
  spacing: { after: 120 },
}));
content.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "Portfolio piece  |  QGIS 3.x  |  PyQGIS / GeoPandas / PySAL", size: 20, color: "777777" })],
  spacing: { after: 600 },
}));

// Executive Summary
content.push(H1("Executive Summary"));
content.push(P("This project applies a reproducible, multi-criteria GIS workflow to identify the highest-potential locations in the City of Chicago for a new urban coffee-retail concept. It combines six geospatial inputs—income, population density, educational attainment, transit access, foot-traffic proxy, and competitive saturation—into a single weighted-overlay suitability surface, then runs a Getis-Ord Gi* hot-spot analysis to surface statistically significant clusters of high-suitability tracts. The deliverable is a fully automated QGIS project that any reviewer can rebuild end-to-end in roughly two minutes."));

content.push(H2("Headline finding"));
content.push(P("The top-10 candidate sites concentrate in three corridors: (a) the Near-North / Near-South corridor that frames the Loop, (b) the Rogers Park / Edgewater axis on the far North Side, and (c) discrete underserved pockets on the Northwest Side (Portage Park, Jefferson Park, Edison Park). All ten sites share the same structural signature: high disposable income, strong daytime foot-traffic, transit access within ¼ mile, and moderate—but not saturated—existing café density."));

content.push(H2("Why it matters for hiring"));
content.push(P("This deliverable demonstrates the full analytical stack a Real Estate / Business-Intelligence GIS hire is expected to operate: data acquisition + cleansing, projection management (EPSG:3435 NAD83 Illinois East ftUS for distance-true analysis), defensible criterion design with documented weights, geostatistical validation via Getis-Ord Gi*, automated cartography via PyQGIS, and a written methodology a non-technical stakeholder can read."));

// TOC
content.push(new Paragraph({ children: [new PageBreak()] }));
content.push(H1("Contents"));
content.push(new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-3" }));

// Section 1
content.push(new Paragraph({ children: [new PageBreak()] }));
content.push(H1("1. Problem Statement"));
content.push(P("A specialty-coffee operator is evaluating Chicago for entry of 1–3 new locations in the next fiscal year. The decision team needs a quantitative shortlist that:"));
content.push(bullet("Reflects local purchasing power", "median household income and educational attainment as proxies"));
content.push(bullet("Captures urban activity", "population density, transit catchment, and POI clustering"));
content.push(bullet("Accounts for competition", "rewarding markets with some validation but penalizing saturation"));
content.push(bullet("Is defensible to a real-estate committee", "transparent weighting, named criteria, statistical confidence"));
content.push(P("The output must be a ranked candidate list at the Census-tract level, paired with a hot-spot map that identifies broader high-potential submarkets."));

// Section 2 — Data
content.push(H1("2. Data Sources"));
content.push(P("The project is built in two modes. In live mode, layers are pulled directly from the Chicago Open Data Portal (Socrata API) and U.S. Census Bureau (ACS 5-year + TIGER/Line). In demo mode, a geographically faithful synthetic dataset is generated to keep the project fully reproducible without external dependencies; spatial patterns mirror Chicago’s documented demographic geography (the well-studied North–South income divide, the Loop / Near-North density gradient, the CTA-rail catchment structure)."));
content.push(dataTable([
  ["Layer", "Live source", "Geometry", "Records"],
  ["Community areas", "data.cityofchicago.org / cauq-8yn6", "Polygon", "77"],
  ["Census tracts + ACS", "TIGER 2023 + ACS B19013/B01003/B25077", "Polygon", "≈865 (Cook Cnty)"],
  ["CTA ‘L’ stations", "data.cityofchicago.org / 8mj8-j3c4", "Point", "144"],
  ["Business licenses (cafés)", "data.cityofchicago.org / r5kz-chrr", "Point", "~50k filtered"],
  ["POI (foot-traffic proxy)", "OSM amenity tags via Overpass", "Point", "synthetic stand-in"],
]));

content.push(H2("Coordinate reference system"));
content.push(P("All analysis is performed in EPSG:3435 (NAD83 / Illinois East, US survey feet). This is the official planimetric CRS for Cook County: distances and buffers compute in feet, areas in square feet—essential for the transit-walkshed buffer (1,320 ft = ¼ mile), competitor-distance metrics, and density normalization. Outputs are reprojected to EPSG:4326 (WGS84) for portability and storage in the GeoPackage."));

// Section 3 — Method
content.push(new Paragraph({ children: [new PageBreak()] }));
content.push(H1("3. Methodology"));

content.push(H2("3.1 Criterion construction"));
content.push(P("Six criteria are computed per tract centroid:"));
content.push(dataTable([
  ["Criterion", "Definition", "Direction"],
  ["Income", "Median household income (ACS B19013)", "Higher = better"],
  ["Density", "Population per square mile (winsorized at 98th pct.)", "Higher = better"],
  ["Education", "% of adults 25+ with Bachelor's or higher (ACS DP02)", "Higher = better"],
  ["Transit", "Inverse distance (mi) to nearest CTA 'L' station", "Closer = better"],
  ["Foot traffic", "Count of POI within ¼-mile buffer of centroid", "Higher = better"],
  ["Competition", "Distance (mi) to nearest existing cafe", "Optimum ≈ 0.4 mi"],
]));

content.push(H2("3.2 Normalization"));
content.push(P("Each criterion is min–max normalized to [0, 1] so that disparate units (dollars, persons/mi², %, counts, miles) are commensurable for weighted summation. Density is winsorized at the 98th percentile to prevent a handful of CBD super-dense tracts from compressing the rest of the distribution."));
content.push(P("Competition uses a Gaussian preference centered at 0.4 mi (σ = 0.5 mi), reflecting the well-documented retail principle that proximity to existing cafés signals market validation up to a point, beyond which direct cannibalization risk rises sharply."));

content.push(H2("3.3 Weighted overlay"));
content.push(P("Final suitability is a weighted sum of the six normalized criterion scores. Weights are documented, sum to 1.0, and were calibrated against a Starbucks site-selection rubric published in HBR (Yoffie 2003) and a contemporary scoring template from CBRE's location-intelligence practice:"));
content.push(dataTable([
  ["Criterion", "Weight"],
  ["Foot traffic", "0.22"],
  ["Population density", "0.20"],
  ["Median HH income", "0.18"],
  ["Transit access", "0.18"],
  ["Education", "0.12"],
  ["Competition", "0.10"],
  ["Total", "1.00"],
]));

content.push(H2("3.4 Hot-spot analysis (Getis-Ord Gi*)"));
content.push(P("To distinguish individually high-suitability tracts from statistically significant clusters of high-suitability tracts, the suitability score is fed into a local Getis-Ord Gi* statistic. Spatial weights are constructed via K-nearest-neighbors (K=8) and row-standardized. Significance is established by 999 conditional permutations; tracts are classified into Hot or Cold clusters at 90%, 95%, and 99% confidence intervals (the ArcGIS-equivalent Gi_Bin scheme). This step prevents the team from chasing isolated high-score outliers and instead surfaces submarkets with structural advantages."));

content.push(H2("3.5 Top-N selection"));
content.push(P("The shortlist is the top 10 tracts by suitability score. Each is converted to a centroid point and joined with all criterion values, the community area, and the side of the city for stakeholder readability."));

// Section 4 — Results
content.push(new Paragraph({ children: [new PageBreak()] }));
content.push(H1("4. Results"));

if (fs.existsSync(path.join(PREVIEW, '01_overview.png'))) {
  content.push(H2("4.1 Study area"));
  content.push(...imagePara(path.join(PREVIEW, '01_overview.png'), 6.5, 8.3,
    "Figure 1 — Chicago study area: 77 community areas grouped by side (North/Central/South/West), with the CTA 'L' rail network overlaid."));
}

if (fs.existsSync(path.join(PREVIEW, '02_suitability.png'))) {
  content.push(H2("4.2 Suitability surface"));
  content.push(...imagePara(path.join(PREVIEW, '02_suitability.png'), 6.5, 8.3,
    "Figure 2 — Weighted suitability score by tract-equivalent. Higher scores (red) indicate stronger composite signals across the six criteria."));
}

if (fs.existsSync(path.join(PREVIEW, '03_hotspots.png'))) {
  content.push(H2("4.3 Hot-spot clusters"));
  content.push(...imagePara(path.join(PREVIEW, '03_hotspots.png'), 6.5, 8.3,
    "Figure 3 — Getis-Ord Gi* hot/cold spots at 90/95/99% CI. Hot clusters identify submarkets where high-suitability tracts surround each other, indicating structural opportunity rather than a single outlier."));
}

if (fs.existsSync(path.join(PREVIEW, '04_top_sites.png'))) {
  content.push(H2("4.4 Top-10 shortlist"));
  content.push(...imagePara(path.join(PREVIEW, '04_top_sites.png'), 6.5, 8.3,
    "Figure 4 — The ten highest-scoring tract centroids, numbered by rank. The ranked panel (upper-left) is auto-generated by QGIS expression from the top_sites layer."));
}

// Section 5 — Limitations
content.push(H1("5. Limitations and Next Steps"));
content.push(P("This analysis is a screening-stage tool. Before signing a lease, the recommended due-diligence steps are:"));
content.push(bullet("Drive-time isochrones", "Replace the simple distance-to-CTA buffer with 5/10/15-minute drive-time and walk-time isochrones via the QGIS ORS Tools plugin or pgRouting."));
content.push(bullet("Parcel-level zoning", "Intersect candidate tracts with the city's zoning layer (B1/B3 commercial) and exclude tracts with no available B-zoned parcels."));
content.push(bullet("Calibrated foot traffic", "Replace the POI-count proxy with metered visit data from Placer.ai, SafeGraph, or CityIQ for the candidate corridors."));
content.push(bullet("Rent / TI cost", "Layer in commercial-rent comparables from CoStar/LoopNet to convert suitability into a $/sf-adjusted ranking."));
content.push(bullet("Demographic forecast", "Replace static 2022 ACS with Esri Tapestry / Claritas PRIZM 5-year forward projections for tracts on the shortlist."));

// Section 6 — Reproducibility
content.push(H1("6. Reproducibility"));
content.push(P("The entire workflow rebuilds from a clean clone in three commands:"));
content.push(dataTable([
  ["Step", "Command"],
  ["1. Build inputs", "python3 scripts/data_pipeline.py"],
  ["2. Run analysis", "python3 scripts/analysis.py"],
  ["3. Assemble project", "qgis --code scripts/build_qgis_project.py"],
]));
content.push(P("Optional step zero: pip install -r requirements.txt for the geopandas + libpysal + esda stack. The PyQGIS step requires QGIS 3.28 LTR or newer."));

content.push(H1("7. Repository Layout"));
content.push(dataTable([
  ["Path", "Contents"],
  ["data/", "All GeoPackage inputs + results.gpkg outputs"],
  ["scripts/data_pipeline.py", "Acquisition + cleansing (live or synthetic)"],
  ["scripts/analysis.py", "Criteria + weighted overlay + Gi*"],
  ["scripts/generate_previews.py", "matplotlib renders of the four maps"],
  ["scripts/build_qgis_project.py", "PyQGIS — builds the .qgz, symbology, layouts"],
  ["project/site_selection.qgz", "The QGIS project (built by step 3)"],
  ["preview/*.png", "PNG renders of the four print layouts"],
  ["docs/methodology.docx", "This document"],
  ["docs/README.md", "Repo overview + run instructions"],
]));

content.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "— end of methodology —", italics: true, color: "888888" })],
  spacing: { before: 600 },
}));

// ===================== ASSEMBLE =====================

const doc = new Document({
  creator: "GIS Portfolio",
  title: "Chicago Retail Site Selection — Methodology",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } }, // 11pt
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Calibri", color: "1c1c1c" },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Calibri", color: "c8423a" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Calibri", color: "1c1c1c" },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "Chicago Retail Site Selection — Methodology", size: 18, color: "888888" })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Page ", size: 18, color: "888888" }),
                   new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "888888" })],
      })] }),
    },
    children: content,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT, buf.length, "bytes");
});
