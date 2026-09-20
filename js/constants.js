/* ================= constants ================= */
export const WMS = "https://kartta.luke.fi/geoserver/MVMI/wms";
export const CYCLE = "1923"; // MS-NFI 2019–2023 (published 2023)
// The oldest date from which the 1923 cycle's imagery could already show a change. Everything
// the map draws — rule masks and the model raster alike — describes the forest as it stood
// then, so a stand harvested after this is a guaranteed false positive until Luke publishes
// the next cycle. This is the one date the Metsäkeskus correction below is measured against.
export const MVMI_EFFECTIVE = "2021-01-01";
export const LAYER = {
  site:   "MVMI:kasvupaikka_"           + CYCLE, // 1 lehto … 5 kuiva kangas, 6 karukko
  main:   "MVMI:paatyyppi_"             + CYCLE, // 1 kivennäismaa, 2 korpi, 3 räme, 4 avosuo
  age:    "MVMI:ika_"                   + CYCLE, // vuosina
  pine:   "MVMI:manty_"                 + CYCLE, // m³/ha
  spruce: "MVMI:kuusi_"                 + CYCLE, // m³/ha
  birch:  "MVMI:koivu_"                 + CYCLE, // m³/ha
  vol:    "MVMI:tilavuus_"              + CYCLE, // m³/ha (koko puusto)
  cover:  "MVMI:latvuspeitto_"          + CYCLE, // % (koko puusto)
  bcover: "MVMI:lehtip_latvuspeitto_"   + CYCLE, // % (lehtipuut)
};
export const SITE_NAMES = { 1:"lehto",2:"lehtomainen kangas",3:"tuore kangas",4:"kuivahko kangas",
  5:"kuiva kangas",6:"karukkokangas",7:"kalliomaa/hietikko",8:"lakimetsä/tunturi" };
export const SITE_CANDIDATES = [1,2,3,4,5,6,7,8];
export const MAIN_NAMES = { 1:"kivennäismaa", 2:"korpi", 3:"räme", 4:"avosuo" };
export const MAIN_CANDIDATES = [1,2,3,4];
export const SPOT_COLOR = "#ff2d78";
export const FINDING_COLOR = "#ffd166";
// Ground the map has to give up on. The model raster paints a confirmed clear-cut in this grey
// (problayer.js) and the findings layer paints a find whose stand is gone in the same one, so a
// tapped clear-cut and a tapped observation standing on it read as the same fact.
export const CUT_GREY = "rgba(150,163,155,0.72)";
// A find the evidence cannot settle. Same recipe probColorFn() uses for a declared felling —
// the finding colour washed 45 % toward paper — so "reported but unconfirmed" looks the same
// whether it is a pixel of the model or a point on top of it.
export const FINDING_SUSPECT = "#f6dda2";
// Nothing to say: located too coarsely to sit on a stand, or no forest data under it.
export const FINDING_UNKNOWN = "#8aa192";
export const R3857 = 20037508.342789244;
export const R_EARTH = 6378137;

export const AGE_STEPS    = [20, 40, 60, 80, 100, 130, 170];
export const VOL_STEPS    = [10, 20, 40, 70, 110];
export const BIGVOL_STEPS = [20, 50, 90, 130, 180];
export const TOTVOL_STEPS = [50, 100, 150, 200, 260];
export const COVER_STEPS  = [10, 25, 40, 55, 70, 85];
// below this the pixel is bare ground (fresh clear-cut, field edge), not a
// half-open grassy spot — used as the floor of ukonsieni's canopy band
export const MIN_COVER = 10;
// matsutake avoids spruce stands: 83 % of known finds have less spruce than this,
// against 37 % of other mushroom sites (docs/HABITAT_MODEL_PLAN.md)
export const MAX_SPRUCE = 20;
// matsutake wants light, open pine stands, not dense forestry-grade canopy: 70 % of known finds
// have canopy cover at or below this, against 19 % of other mushroom sites, and it matches the
// already-validated rule E threshold (docs/HABITAT_MODEL_PLAN.md, Vaario et al. 2015 — best
// yields in "moderately open A–B canopy density" 41–60 yr pine stands)
export const MATSU_MAX_COVER = 60;
/* kanttarelli: total standing volume, the one theme that actually tells a chanterelle forest
   from the forest next door. Measured against 393 GBIF finds (accuracy <= 100 m, 2010+, one per
   100 m cell) and 373 random forestry-land points 2-5 km from a find — the same region-matched
   control the other species' defaults were set against, see docs/SPECIES_FILTER_kanttarelli.md.

   The host-volume union this replaces (spruce *or* birch *or* pine >= 40 m³/ha) barely
   discriminated at all: it let 94 % of the finds through and 77 % of the control points with it.
   Birch was the worst of the three — 41 % of finds against 43 % of controls, i.e. very slightly
   *anti*-predictive — and the union's weakest member sets its selectivity, because OR passes a
   cell as soon as any one member does. Total volume at this threshold keeps 60 % of the finds
   while painting 18 % of forestry land nationally, where the old defaults kept 65 % and painted
   30 %; against the matched controls that is 1.62x where the old defaults managed 1.49x.

   Read that national figure with its regional caveat: south of 62 deg N most forest is already
   denser than this, so the painted area there barely moves (a 20 km box over Nuuksio goes from
   44 % to 43 %) and the gain is in the middle and the north. The lever that genuinely tightens
   the south is the spruce toggle below. Saying so in the species' own info text is deliberate —
   a generalist's map cannot be made narrow and honest at the same time. */
export const KANT_MIN_VOL = 150;
// "fewer but surer", the tightening the info text used to promise without a lever that delivered
// it: in the south this holds 36 % of the finds against 15 % of the matched controls — 2.3x,
// where the default manages 1.5x there. Off by default, because the price is the other half of
// the finds, and a spot the map never paints is one the user never hears about.
export const KANT_SPRUCE_DOM = 110;
/* Luke serves the per-species volume themes (manty, kuusi, koivu) as bytes of m³/ha, one raster
   step per m³/ha. `tilavuus` is the whole stand and runs past 500 m³/ha, which a byte does not
   hold, so that one theme is published at half scale: one raster step is 2 m³/ha. Checked
   against the source GeoTIFFs at Paituli over a spread of stands — WMS 15/45/70/95/125/170
   where the GeoTIFF reads 35/91/141/192/255/344 — and confirmed as the app's own masks in
   docs/SPECIES_FILTER_kanttarelli.md. Stands over ~510 m³/ha saturate at 255, which is harmless
   for a "vähintään" mask: a saturated cell is still above every threshold the slider offers.

   Every threshold the user sets is in m³/ha and every probe is in raster steps, so the
   conversion belongs at that boundary and nowhere else. Negatives pass through untouched: a
   range mask's `lo` of -1 is a sentinel meaning "no lower bound", not a measurement. */
export const rasterVol = v => v < 0 ? v : Math.round(v / 2);

/* ================= "lähellä sinua" =================
   A *spot* is one contiguous mushroom forest: an 8-connected patch of 32 m cells where every
   condition of the selected species holds, big enough to be worth the drive and thick enough to
   have an inside. Two numbers carry that judgement, because the rule mask is boolean — unlike the
   model raster ml/pick_sites.py ranks, it has no per-cell quality, so size is the only signal:

     5 ha   ≈ 225 × 225 m. At a scanning pace of about 2 ha an hour that is a two-hour forest,
            a trip rather than a roadside glance. (pick_sites.py allows 1 ha, but only inside an
            already score-filtered set, and only after the exclusion masks.)
     80 m   the patch must hold a point 40 m from any non-matching cell. This is what drops the
            one-cell ribbon along a clearcut edge or a lake shore that totals 5 ha but is never
            more than one tree deep.

   Before any of that the mask is *closed* by one cell. The MVMI classifies each 16 m cell on its
   own, so intersecting four or five thresholds leaves a forest looking like buckshot: around
   Tampere the matsutake mask covers 0.77 % of the land but breaks into 11 599 pieces, the largest
   6 ha, and almost none of them survive the core test. Two qualifying cells 32 m apart are the
   same forest to anyone walking it — which is the definition this feature is built on — so the
   gap between them is filled before the patches are counted. It is the smallest closing there
   is, and area is still counted over *qualifying cells only*, so the hectares never include the
   ground that was bridged. Closing by two cells instead would merge the generalists' maps into
   single region-wide blobs (kanttarelli's largest patch goes from 6 000 ha to 23 000). */
export const NEARBY_CLOSE = 1;         // cells
export const NEARBY_RADIUS_M = 25000;  // 50 km box -> 1563 px per mask, ~190 KB each
export const NEARBY_CELL_M   = 32;     // integer multiple of the 16 m source grid
export const MIN_SPOT_HA     = 5.0;
export const MIN_CORE_M      = 80;     // core diameter, not radius
export const NEARBY_HALF_KM  = 5;      // ranking blend: a forest's hectares count half at 5 km
export const NEARBY_SEP_M    = 2500;   // so the three picks are three forests, not three lobes of one
export const NEARBY_N        = 3;
export const NEARBY_CUT_CHECKS = 40;   // ceiling on candidates verified against Metsäkeskus, so a region
                                // where everything has been cut cannot turn into a request storm
export const FIX_MAX_AGE_MS  = 5 * 60 * 1000;
// How far the map has to travel before a view-anchored list re-scans. One scan is five full-size
// reads off Luke's GeoServer, so it must not follow every nudge of the map; a fifth of the scan
// radius is the point at which the old circle no longer really covers what is on screen.
export const NEARBY_REANCHOR_M = 5000;
// The widest view the map centre still stands for. At country zoom "the middle of the screen" is
// not a place the user picked, so the list asks to be zoomed in rather than scanning Suomussalmi
// because that is where the default view happens to be centred.
export const NEARBY_VIEW_MAX_M = 150000;
export const DIR8 = ["pohjoiseen","koilliseen","itään","kaakkoon","etelään","lounaaseen","länteen","luoteeseen"];
