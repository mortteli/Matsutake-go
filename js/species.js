import { AGE_STEPS, BIGVOL_STEPS, COVER_STEPS, LAYER, MATSU_MAX_COVER, MAX_SPRUCE, MIN_COVER, VOL_STEPS } from "./constants.js";
import { helperLayer } from "./maplayer.js";
import { maskMin, maskRange, maskValues } from "./wms.js";

/* ================= species registry =================
   Each species turns its user settings into
     · `conditions`: AND-groups of masks (members of a group are OR'd),
     · `mainTypes`:  the accepted `paatyyppi` classes (mineral soil, mire), and
     · `metrics`:    the same thresholds re-expressed for the tap readout.
   Adding a mushroom means adding one entry here — nothing else. */
export const cond = (layer, sld) => ({ layer, sld });

export const SPECIES = [
{
  key: "matsutake",
  emoji: "🍄",
  name: "Matsutake",
  latin: "Tricholoma matsutake",
  tagline: "vanha kuiva mäntykangas",
  legend: "matsutake-tyypin metsä",
  primeSite: 5,
  verdicts: {
    hit: "Lupaava matsutake-paikka!",
    hitAlt: "Lupaava paikka (karu kangas)",
    stand: "Oikea metsätyyppi — puusto ei täytä ehtoja",
    miss: "Ei matsutake-tyyppiä",
  },
  // defaults checked against 104 GBIF finds (≤ 100 m accuracy): "kuivahko" on and
  // "little spruce" lift the share of known finds inside the map from 9 % to ~48 %
  // while the map still covers only ~7 % of forest land — see docs/HABITAT_MODEL_PLAN.md
  defaults: { minAge: 60, minPine: 20, maxCover: MATSU_MAX_COVER, kuivahko: true, karukko: true, lowSpruce: true },
  controls: [
    { type: "range", key: "minAge",  label: "Puuston ikä vähintään", min: 40, max: 120, step: 5, unit: " v" },
    { type: "range", key: "minPine", label: "Mäntyä vähintään",      min: 0,  max: 120, step: 5, unit: " m³/ha" },
    { type: "range", key: "maxCover", label: "Latvuspeitto enintään", hint: "avoin, valoisa mäntymetsä — tiheä talousmetsä ei kelpaa", min: 30, max: 100, step: 5, unit: " %" },
    { type: "toggle", key: "kuivahko",  label: "Myös kuivahko kangas", hint: "puolukkatyyppi — puolet havainnoista on täällä" },
    { type: "toggle", key: "karukko",   label: "Myös karukkokangas",   hint: "jäkäläkankaat mukaan" },
    { type: "toggle", key: "lowSpruce", label: "Vain vähäkuusiset",     hint: "kuusta enintään " + MAX_SPRUCE + " m³/ha — matsutake karttaa kuusikoita" },
  ],
  siteClasses: c => [5].concat(c.kuivahko ? [4] : [], c.karukko ? [6] : []),
  mainTypes: () => [1], // kivennäismaa
  conditions(c) {
    const g = [
      [cond(LAYER.site, maskValues(LAYER.site, this.siteClasses(c)))],
      [cond(LAYER.main, maskValues(LAYER.main, this.mainTypes(c)))],
      [cond(LAYER.age,  maskMin(LAYER.age, c.minAge))],
    ];
    if (c.minPine > 0) g.push([cond(LAYER.pine, maskMin(LAYER.pine, c.minPine))]);
    if (c.lowSpruce) g.push([cond(LAYER.spruce, maskRange(LAYER.spruce, -1, MAX_SPRUCE))]);
    if (c.maxCover < 100) g.push([cond(LAYER.cover, maskRange(LAYER.cover, -1, c.maxCover))]);
    return g;
  },
  metrics(c) {
    return [
      { label: "Puuston ikä", dir: "min",   limit: c.minAge,    unit: "v",     steps: AGE_STEPS, any: [{ layer: LAYER.age }] },
      { label: "Mäntyä",      dir: "min",   limit: c.minPine,   unit: "m³/ha", steps: VOL_STEPS, any: [{ layer: LAYER.pine }] },
      { label: "Kuusta",      dir: "range", lo: -1, limit: MAX_SPRUCE, unit: "m³/ha", steps: VOL_STEPS, any: [{ layer: LAYER.spruce }], soft: !c.lowSpruce },
      { label: "Latvuspeitto", dir: "range", lo: -1, limit: c.maxCover, unit: "%", steps: COVER_STEPS, any: [{ layer: LAYER.cover }], soft: c.maxCover >= 100 },
    ];
  },
  helpers: [
    { label: "Kuiva kangas (kaikki iät)", make: () => helperLayer(LAYER.site, maskValues(LAYER.site, [5], "#ff9d2e")) },
    { label: "Vanha metsä (kaikki tyypit)", make: () => helperLayer(LAYER.age, maskMin(LAYER.age, 60, "#2e86ff")) },
    { label: "Harva puusto (latvuspeitto ≤ " + MATSU_MAX_COVER + " %)", make: () => helperLayer(LAYER.cover, maskRange(LAYER.cover, -1, MATSU_MAX_COVER, "#2e86ff")) },
  ],
  // observation-trained probability layer (ml/), see docs/HABITAT_MODEL_PLAN.md
  model: "data/matsutake/prob_meta.json",
  // the GBIF/FinBIF finds that train it, plotted as their own map layer
  findings: "data/matsutake/observations.json",
  slopeGood: s => s.deg >= 2,
  region: lat => lat >= 66 ? "Lappi — paras alue 🌟" :
                 lat >= 64 ? "pohjoinen — hyvä alue" :
                 lat >= 62 ? "keskimaa — mahdollinen" : "etelä — harvinaisempi",
  info:
    '<h2>🍄 Matsutake eli tuoksuvalmuska</h2>' +
    '<p><b>Tricholoma matsutake</b> kasvaa Suomessa vanhoissa männiköissä kuivilla ja ' +
    'karuilla kankailla. Kartan pinkit alueet ovat metsiä, joissa <b>kaikki</b> valitut ehdot täyttyvät:</p>' +
    '<p>✔️ kasvupaikka on <b>kuiva tai kuivahko kangas</b> (kanerva-/puolukkatyyppi) tai karukkokangas — kivennäismaalla<br>' +
    '✔️ puusto on vanhaa (oletus ≥ 60 v)<br>✔️ mäntyä on riittävästi<br>' +
    '✔️ kuusta on vain vähän — matsutake karttaa kuusikoita<br>' +
    '✔️ latvuspeitto on harva (oletus enintään ' + MATSU_MAX_COVER + ' %) — avoin, valoisa metsä, ei tiivis talousmäntykkö</p>' +
    '<p>Tunnetuista havainnoista puolet on Luken aineistossa <i>kuivahkoa</i> kangasta ja vain joka ' +
    'kahdeksas <i>kuivaa</i>, joten kuivahko on oletuksena mukana. Parhaat paikat ovat hiekkaisia ' +
    'harjuja ja rinteiden yläosia — <b>maaperä ei ole vielä kartassa</b>, joten suosi harjumaastoa.</p>' +
    '<p>Jäkäläiset, valoisat ja hieman rinteiset paikat ovat parhaita: latvuspeitto ≤ 50 % löytyy ' +
    '70 %:sta tunnetuista havainnoista, vain 19 %:sta muista sienihavainnoista, joten harvuus on nyt ' +
    'omana säätimenään — tarkista rinne napauttamalla karttaa. Mitä pohjoisempana, sitä varmempi ' +
    'esiintyminen: Lappi ja Koillismaa ovat Suomen parasta matsutake-aluetta, mutta lajia löytyy ' +
    'karuilta mäntykankailta koko maasta.</p>' +
    '<h3>Satokausi</h3>' +
    '<p>Pohjois-Suomi: elokuun loppu – syyskuu.<br>Etelä-Suomi: syyskuu – lokakuun alku.<br>' +
    'Itiöemät kasvavat usein puoliksi maan/jäkälän alla — katso kohoumia!</p>',
},
{
  key: "herkkutatti",
  emoji: "🌰",
  name: "Herkkutatti",
  latin: "Boletus edulis",
  tagline: "tuore kuusikangas",
  legend: "herkkutattimetsä",
  primeSite: 3,
  verdicts: {
    hit: "Lupaava herkkutattimetsä!",
    hitAlt: "Lupaava paikka (muu kangastyyppi)",
    stand: "Oikea kasvupaikka — puusto ei täytä ehtoja",
    miss: "Ei herkkutattityyppiä",
  },
  defaults: { minAge: 45, minSpruce: 130, minCover: 75, lehtomainen: true, kuivahko: false, pineToo: false },
  controls: [
    { type: "range", key: "minSpruce", label: "Kuusta vähintään",      min: 0,  max: 200, step: 10, unit: " m³/ha" },
    { type: "range", key: "minCover",  label: "Latvuspeitto vähintään", hint: "tiheä varjoisa kuusikko, ohut sammalpeite", min: 0, max: 90, step: 5, unit: " %" },
    { type: "range", key: "minAge",    label: "Puuston ikä vähintään", min: 20, max: 120, step: 5, unit: " v" },
    { type: "toggle", key: "lehtomainen", label: "Myös lehtomainen kangas", hint: "ravinteikkaampi käenkaali–mustikkatyyppi" },
    { type: "toggle", key: "kuivahko",    label: "Myös kuivahko kangas",    hint: "puolukkatyypin männiköt mukaan" },
    { type: "toggle", key: "pineToo",     label: "Myös männiköt",           hint: "mänty kelpaa kuusen sijaan isäntäpuuksi" },
  ],
  siteClasses: c => [3].concat(c.lehtomainen ? [2] : [], c.kuivahko ? [4] : []),
  mainTypes: () => [1], // kivennäismaa
  conditions(c) {
    const g = [
      [cond(LAYER.site, maskValues(LAYER.site, this.siteClasses(c)))],
      [cond(LAYER.main, maskValues(LAYER.main, this.mainTypes(c)))],
      [cond(LAYER.age,  maskMin(LAYER.age, c.minAge))],
    ];
    if (c.minCover > 0) g.push([cond(LAYER.cover, maskMin(LAYER.cover, c.minCover))]);
    if (c.minSpruce > 0) {
      const host = [cond(LAYER.spruce, maskMin(LAYER.spruce, c.minSpruce))];
      if (c.pineToo) host.push(cond(LAYER.pine, maskMin(LAYER.pine, c.minSpruce)));
      g.push(host);
    }
    return g;
  },
  metrics(c) {
    const host = [{ layer: LAYER.spruce, label: "Kuusta" }];
    if (c.pineToo) host.push({ layer: LAYER.pine, label: "Mäntyä" });
    return [
      { label: "Puuston ikä",  dir: "min", limit: c.minAge,    unit: "v",     steps: AGE_STEPS,   any: [{ layer: LAYER.age }] },
      { label: "Kuusta",       dir: "min", limit: c.minSpruce, unit: "m³/ha", steps: BIGVOL_STEPS, any: host },
      { label: "Latvuspeitto", dir: "min", limit: c.minCover,  unit: "%",     steps: COVER_STEPS, any: [{ layer: LAYER.cover }] },
    ];
  },
  helpers: [
    { label: "Kuusivaltainen metsä", make: () => helperLayer(LAYER.spruce, maskMin(LAYER.spruce, 60, "#2e86ff")) },
    { label: "Tuore kangas (kaikki iät)", make: () => helperLayer(LAYER.site, maskValues(LAYER.site, [3], "#ff9d2e")) },
  ],
  slopeGood: null,
  region: lat => lat >= 68 ? "pohjoisin Lappi — harvinainen" :
                 lat >= 65 ? "pohjoinen — mahdollinen" :
                 "etelä ja keskiosa — parasta aluetta 🌟",
  info:
    '<h2>🌰 Herkkutatti</h2>' +
    '<p><b>Boletus edulis</b> on kuusen sienijuurikumppani — myös männyn ja koivun. ' +
    'Parhaat paikat ovat tuoreet ja lehtomaiset kangasmetsät, joissa maassa on ' +
    'neulaskariketta ja vain ohut sammalpeite. Kartan pinkit alueet täyttävät <b>kaikki</b> valitut ehdot:</p>' +
    '<p>✔️ kasvupaikka on <b>tuore kangas</b> (mustikkatyyppi) tai lehtomainen kangas — kivennäismaalla<br>' +
    '✔️ kuusta on riittävästi (tai mäntyä, jos "myös männiköt" on päällä)<br>' +
    '✔️ puusto on vähintään valitun ikäistä</p>' +
    '<p>Tähyile <b>kuusikoiden reunoja, polkujen ja metsäautoteiden varsia sekä harventamattomia ' +
    'istutuskuusikoita</b> — ensiharvennus vähentää tattisatoa selvästi. Herkkutatti karttaa soita ja ' +
    'märkiä painanteita, joten suokuviot on rajattu pois.</p>' +
    '<h3>Satokausi</h3>' +
    '<p>Heinäkuun lopusta lokakuulle, runsaimmin elo–syyskuussa. ' +
    'Sateisina kesinä ensimmäiset voi löytää jo kesäkuussa.</p>' +
    '<h3>Levinneisyys</h3>' +
    '<p>Lähes koko maassa; yleisin Etelä- ja Keski-Suomessa, pohjoisimmassa Lapissa harvinainen.</p>',
},
{
  key: "kanttarelli",
  emoji: "🌼",
  name: "Kanttarelli",
  latin: "Cantharellus cibarius",
  tagline: "sammalinen tuore kangas",
  legend: "kanttarellimaasto",
  primeSite: 3,
  verdicts: {
    hit: "Lupaava kanttarellimaasto!",
    hitAlt: "Lupaava paikka (muu kangastyyppi)",
    stand: "Oikea kasvupaikka — puusto ei täytä ehtoja",
    miss: "Ei kanttarellityyppiä",
  },
  defaults: { minAge: 40, minHost: 40, minCover: 55, lehtomainen: true, kuivahko: true, korpi: false, pineToo: true },
  controls: [
    { type: "range", key: "minHost",  label: "Isäntäpuuta vähintään", hint: "kuusta, koivua tai mäntyä — mikä tahansa niistä riittää", min: 0, max: 150, step: 10, unit: " m³/ha" },
    { type: "range", key: "minCover", label: "Latvuspeitto vähintään", hint: "puolivarjo pitää sammalpohjan kosteana", min: 0, max: 90, step: 5, unit: " %" },
    { type: "range", key: "minAge",   label: "Puuston ikä vähintään", min: 20, max: 120, step: 5, unit: " v" },
    { type: "toggle", key: "lehtomainen", label: "Myös lehtomainen kangas", hint: "ravinteikkaampi käenkaali–mustikkatyyppi" },
    { type: "toggle", key: "kuivahko",    label: "Myös kuivahko kangas",    hint: "puolukkatyypin männiköt ja koivikot mukaan" },
    { type: "toggle", key: "korpi",       label: "Myös korvet",             hint: "kosteat korpikuviot ja ojanvarret mukaan" },
    { type: "toggle", key: "pineToo",     label: "Mänty kelpaa isäntäpuuksi", hint: "kanttarelli on myös männyn kumppani" },
  ],
  siteClasses: c => [3].concat(c.lehtomainen ? [2] : [], c.kuivahko ? [4] : []),
  mainTypes: c => c.korpi ? [1, 2] : [1],
  hostLayers(c) {
    const h = [{ layer: LAYER.spruce, label: "Kuusta" }, { layer: LAYER.birch, label: "Koivua" }];
    if (c.pineToo) h.push({ layer: LAYER.pine, label: "Mäntyä" });
    return h;
  },
  conditions(c) {
    const g = [
      [cond(LAYER.site, maskValues(LAYER.site, this.siteClasses(c)))],
      [cond(LAYER.main, maskValues(LAYER.main, this.mainTypes(c)))],
      [cond(LAYER.age,  maskMin(LAYER.age, c.minAge))],
    ];
    if (c.minCover > 0) g.push([cond(LAYER.cover, maskMin(LAYER.cover, c.minCover))]);
    // isäntäpuu: kuusi tai koivu (tai mänty) riittää — unioni yhden ehdon sisällä
    if (c.minHost > 0)
      g.push(this.hostLayers(c).map(h => cond(h.layer, maskMin(h.layer, c.minHost))));
    return g;
  },
  metrics(c) {
    return [
      { label: "Puuston ikä",   dir: "min", limit: c.minAge,   unit: "v",     steps: AGE_STEPS,   any: [{ layer: LAYER.age }] },
      { label: "Isäntäpuustoa", dir: "min", limit: c.minHost,  unit: "m³/ha", steps: VOL_STEPS,   any: this.hostLayers(c) },
      { label: "Latvuspeitto",  dir: "min", limit: c.minCover, unit: "%",     steps: COVER_STEPS, any: [{ layer: LAYER.cover }] },
    ];
  },
  helpers: [
    { label: "Tuore kangas (kaikki iät)", make: () => helperLayer(LAYER.site, maskValues(LAYER.site, [3], "#ff9d2e")) },
    { label: "Koivikot (koivua ≥ 40 m³/ha)", make: () => helperLayer(LAYER.birch, maskMin(LAYER.birch, 40, "#2e86ff")) },
  ],
  slopeGood: s => s.deg >= 2, // loivat rinteet ja notkelmat pysyvät kosteina
  region: lat => lat >= 68 ? "pohjoisin Lappi — harvempi" :
                 lat >= 65 ? "pohjoinen — hyvä alue" :
                 "etelä ja keskiosa — parasta aluetta 🌟",
  info:
    '<h2>🌼 Kanttarelli eli keltavahvero</h2>' +
    '<p><b>Cantharellus cibarius</b> on kuusen, koivun ja männyn sienijuurikumppani. Se viihtyy ' +
    '<b>kosteahkoissa sammalpohjaisissa kangasmetsissä</b> — mustikkatyypin kuusikoissa ja ' +
    'koivusekametsissä, mielellään polkujen, ojien ja purojen varsilla sekä loivissa rinteissä. ' +
    'Kartan pinkit alueet täyttävät <b>kaikki</b> valitut ehdot:</p>' +
    '<p>✔️ kasvupaikka on <b>tuore kangas</b> (mustikkatyyppi) tai lehtomainen kangas<br>' +
    '✔️ isäntäpuuta on riittävästi: kuusta, koivua <i>tai</i> mäntyä<br>' +
    '✔️ latvuspeitto on vähintään valittu — puolivarjo pitää sammalen kosteana<br>' +
    '✔️ puusto ei ole taimikkoa</p>' +
    '<p><b>Kanttarelli on yleislaji.</b> Se ei ole yhtä tarkka kasvupaikastaan kuin muut tämän ' +
    'sovelluksen sienet, joten kartta värittää eteläisessä Suomessa helposti neljänneksen metsistä. ' +
    'Kiristä säätimiä 🗺️-napista, jos haluat vähemmän mutta varmempia kohteita.</p>' +
    '<p>Kanttarelli kasvaa <b>samoilla paikoilla vuodesta toiseen</b> ja usein tiiviinä ryhminä: ' +
    'kun löydät yhden, tutki muutaman metrin säde ja merkitse paikka muistiin. Keltaiset lakit ' +
    'jäävät helposti sammalen ja varvikon alle — selaa sammalta kepillä.</p>' +
    '<h3>Satokausi</h3>' +
    '<p>Heinäkuusta lokakuulle, runsaimmin elo–syyskuussa. Hyvä sato vaatii kesäsateita.</p>' +
    '<h3>Levinneisyys</h3>' +
    '<p>Koko maassa; runsain Etelä- ja Keski-Suomessa, pohjoisessa harvempi mutta yleinen.</p>',
},
{
  key: "suppilovahvero",
  emoji: "🎺",
  name: "Suppilovahvero",
  latin: "Craterellus tubaeformis",
  tagline: "kostea sammalinen kuusikko",
  legend: "suppilovahveromaasto",
  primeSite: 3,
  verdicts: {
    hit: "Lupaava suppilovahveropaikka!",
    hitAlt: "Lupaava paikka (muu kangastyyppi)",
    stand: "Oikea kasvupaikka — puusto ei täytä ehtoja",
    miss: "Ei suppilovahverotyyppiä",
  },
  defaults: { minAge: 60, minSpruce: 40, minCover: 55, korpi: true, lehtomainen: true, kuivahko: false },
  controls: [
    { type: "range", key: "minSpruce", label: "Kuusta vähintään", min: 0, max: 200, step: 10, unit: " m³/ha" },
    { type: "range", key: "minCover",  label: "Latvuspeitto vähintään", hint: "varjo pitää sammalpohjan kosteana", min: 0, max: 90, step: 5, unit: " %" },
    { type: "range", key: "minAge",    label: "Puuston ikä vähintään", hint: "vanhassa metsässä on lahopuuta", min: 20, max: 140, step: 5, unit: " v" },
    { type: "toggle", key: "korpi",       label: "Myös korvet", hint: "kuusivaltaiset suot ja niiden reunat" },
    { type: "toggle", key: "lehtomainen", label: "Myös lehtomainen kangas", hint: "ravinteikkaampi käenkaali–mustikkatyyppi" },
    { type: "toggle", key: "kuivahko",    label: "Myös kuivahko kangas",    hint: "löyhempi haku (puolukkatyyppi)" },
  ],
  siteClasses: c => [3].concat(c.lehtomainen ? [2] : [], c.kuivahko ? [4] : []),
  mainTypes: c => c.korpi ? [1, 2] : [1],
  conditions(c) {
    const g = [
      [cond(LAYER.site, maskValues(LAYER.site, this.siteClasses(c)))],
      [cond(LAYER.main, maskValues(LAYER.main, this.mainTypes(c)))],
      [cond(LAYER.age,  maskMin(LAYER.age, c.minAge))],
    ];
    if (c.minCover > 0)  g.push([cond(LAYER.cover,  maskMin(LAYER.cover, c.minCover))]);
    if (c.minSpruce > 0) g.push([cond(LAYER.spruce, maskMin(LAYER.spruce, c.minSpruce))]);
    return g;
  },
  metrics(c) {
    return [
      { label: "Puuston ikä",  dir: "min", limit: c.minAge,    unit: "v",     steps: AGE_STEPS,    any: [{ layer: LAYER.age }] },
      { label: "Kuusta",       dir: "min", limit: c.minSpruce, unit: "m³/ha", steps: BIGVOL_STEPS, any: [{ layer: LAYER.spruce }] },
      { label: "Latvuspeitto", dir: "min", limit: c.minCover,  unit: "%",     steps: COVER_STEPS,  any: [{ layer: LAYER.cover }] },
    ];
  },
  helpers: [
    { label: "Korvet (kuusivaltaiset suot)", make: () => helperLayer(LAYER.main, maskValues(LAYER.main, [2], "#ff9d2e")) },
    { label: "Varjoisa metsä (latvuspeitto ≥ 60 %)", make: () => helperLayer(LAYER.cover, maskMin(LAYER.cover, 60, "#2e86ff")) },
  ],
  slopeGood: s => s.deg < 4, // kosteus viipyy tasamaalla ja painanteissa
  region: lat => lat >= 67 ? "Lappi — hyvin harvinainen" :
                 lat >= 65 ? "pohjoinen — harvinaistuu" :
                 "etelä ja keskiosa — parasta aluetta 🌟",
  info:
    '<h2>🎺 Suppilovahvero</h2>' +
    '<p><b>Craterellus tubaeformis</b> on syksyn varmin massasieni. Se kasvaa <b>kosteissa, ' +
    'sammalpohjaisissa kuusikoissa</b> — painanteissa, korpien reunoilla, ojanvarsilla ja ' +
    'lahopuun päällä, usein satojen yksilöiden ryhminä. Kartan pinkit alueet täyttävät ' +
    '<b>kaikki</b> valitut ehdot:</p>' +
    '<p>✔️ kasvupaikka on <b>tuore kangas</b> tai lehtomainen kangas — kivennäismaalla tai korvessa<br>' +
    '✔️ kuusta on riittävästi<br>' +
    '✔️ latvuspeitto on tiheä: varjo pitää sammalen kosteana<br>' +
    '✔️ puusto on iäkästä (oletus ≥ 60 v), jolloin maassa on lahopuuta</p>' +
    '<p>Toisin kuin muut lajit tässä sovelluksessa, suppilovahvero <b>hyväksyy suokuviot</b>: ' +
    'korpi on sille tyypillistä maastoa. Etsi kosteita painanteita ja puronvarsia — kartta ei ' +
    'näe pieniä notkoja, joten kulje pinkkien kuvioiden sisällä alaspäin.</p>' +
    '<h3>Satokausi</h3>' +
    '<p>Syyskuusta marraskuulle. Kestää hallaa ja jatkaa kasvuaan ensilumen jälkeenkin — ' +
    'etelässä sieniä löytää joskus joulukuussa.</p>' +
    '<h3>Levinneisyys</h3>' +
    '<p>Runsain Etelä- ja Keski-Suomen kuusikoissa. Harvinaistuu Oulun pohjoispuolella; ' +
    'pohjoisimmat runsaat esiintymät ovat napapiirin tienoilla, yksittäisiä havaintoja Inaria myöten.</p>',
},
{
  key: "ukonsieni",
  emoji: "☂️",
  name: "Ukonsieni",
  latin: "Macrolepiota procera",
  tagline: "valoisa lehtomainen reuna",
  legend: "ukonsienen tyyppipaikka",
  primeSite: 1,
  maxLat: 66.5, // pohjoisimmat havainnot Perä-Pohjanmaalta
  verdicts: {
    hit: "Lupaava ukonsienipaikka!",
    hitAlt: "Mahdollinen ukonsienipaikka",
    stand: "Oikea kasvupaikka — puusto liian tiheää",
    miss: "Ei ukonsienityyppiä",
  },
  defaults: { maxCover: 40, tuore: false, leafy: false },
  controls: [
    { type: "range", key: "maxCover", label: "Latvuspeitto enintään", hint: "puoliavoin: 10 % … valittu raja", min: 20, max: 90, step: 5, unit: " %" },
    { type: "toggle", key: "tuore", label: "Myös tuore kangas", hint: "löyhempi haku (mustikkatyyppi)" },
    { type: "toggle", key: "leafy", label: "Vain lehtipuuvaltainen", hint: "lehtipuiden latvuspeitto ≥ 20 %" },
  ],
  siteClasses: c => [1, 2].concat(c.tuore ? [3] : []),
  mainTypes: () => [1], // kivennäismaa
  conditions(c) {
    const g = [
      [cond(LAYER.site,  maskValues(LAYER.site, this.siteClasses(c)))],
      [cond(LAYER.main,  maskValues(LAYER.main, this.mainTypes(c)))],
      [cond(LAYER.cover, maskRange(LAYER.cover, MIN_COVER, c.maxCover))],
    ];
    if (c.leafy) g.push([cond(LAYER.bcover, maskMin(LAYER.bcover, 20))]);
    return g;
  },
  metrics(c) {
    return [
      { label: "Latvuspeitto", dir: "range", lo: MIN_COVER, limit: c.maxCover, unit: "%", steps: COVER_STEPS, any: [{ layer: LAYER.cover }] },
      { label: "Lehtipuustoa", dir: "min", limit: 20, unit: "%", steps: COVER_STEPS, any: [{ layer: LAYER.bcover }], soft: !c.leafy },
    ];
  },
  helpers: [
    { label: "Lehdot ja lehtomaiset kankaat", make: () => helperLayer(LAYER.site, maskValues(LAYER.site, [1, 2], "#ff9d2e")) },
    { label: "Aukot ja harva puusto (< 30 %)", make: () => helperLayer(LAYER.cover, maskRange(LAYER.cover, -1, 30, "#2e86ff")) },
  ],
  slopeGood: null,
  region: lat => lat <= 62 ? "Etelä-Suomi — parasta aluetta 🌟" :
                 lat <= 64.5 ? "keskimaa — harvinaisempi" :
                 lat <= 66.5 ? "pohjoinen — hyvin harvinainen" :
                 "Lapin puolella ei havaintoja",
  info:
    '<h2>☂️ Ukonsieni</h2>' +
    '<p><b>Macrolepiota procera</b> ei ole sienijuurisieni vaan lahottaja: se viihtyy ' +
    '<b>ravinteisella maalla ruohoisissa ja valoisissa paikoissa</b> — lehtojen ja lehtomaisten ' +
    'kankaiden reunoilla, metsäniityillä, hakamailla, pientareilla, puutarhoissa ja puistonurmikoilla.</p>' +
    '<p>✔️ kasvupaikka on <b>lehto tai lehtomainen kangas</b> — kivennäismaalla<br>' +
    '✔️ puusto on harvaa tai aukkoista (latvuspeitto enintään valittu raja)<br>' +
    '✔️ halutessasi lisäksi lehtipuuvaltainen</p>' +
    '<p><b>Huom:</b> parhaat ukonsienipaikat — pientareet, hakamaat, pihat ja niityt — eivät ole ' +
    'metsävara-aineistossa lainkaan. Käytä karttaa <b>suunnan</b> antajana ja etsi pinkkien kuvioiden ' +
    '<b>reunoja ja aukkoja</b>, älä niiden keskustaa.</p>' +
    '<h3>Satokausi</h3>' +
    '<p>Elo–syyskuu. Sadon runsaus vaihtelee vuosittain hyvin paljon.</p>' +
    '<h3>Levinneisyys</h3>' +
    '<p>Yleinen Etelä-Suomessa, harvinaistuu nopeasti pohjoiseen; pohjoisimmat havainnot ' +
    'Perä-Pohjanmaalta. Kartta ei siksi piirrä kuvioita 66,5° N pohjoispuolelle.</p>',
},
];
