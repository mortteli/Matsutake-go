/** Tiny two-language string table. Finnish is the default; English is a toggle. */

const STRINGS = {
  fi: {
    'app.tagline': 'Tuoksuvalmuska · Suomi',
    'legend.title': 'Osuvuus',
    'legend.s90': '90+ · huippupaikka',
    'legend.s75': '75–89 · erinomainen',
    'legend.s60': '60–74 · hyvä',
    'legend.s45': '45–59 · mahdollinen',
    'legend.hint': 'Vain kuivat kankaat + vanha mänty näytetään.',
    'cta.scan': 'Etsi tältä alueelta',
    'set.filters': 'Hakuehdot',
    'set.minAge': 'Männikön vähimmäisikä',
    'set.minScore': 'Näytä pisteistä alkaen',
    'set.pineOnly': 'Vain männikkövaltaiset kuviot',
    'set.needSlope': 'Vaadi rinnettä (≥3°)',
    'set.terrain': 'Laske rinne ja ilmansuunta korkeusmallista',
    'set.autoscan': 'Hae automaattisesti karttaa liikuttaessa',
    'set.saved': 'Omat kohteet',
    'set.exportGpx': 'Vie GPX',
    'set.clearWp': 'Tyhjennä',
    'set.data': 'Aineistolähde',
    'set.dataInfo': 'Metsikkökuviot: Suomen metsäkeskuksen avoin metsävaratieto (WFS). Kattaa pääosin yksityismetsät — valtion mailla (Metsähallitus) kuvioita voi puuttua.',
    'set.wfsUrl': 'WFS-osoite',
    'set.layer': 'Kohdetaso',
    'set.test': 'Testaa yhteys',
    'set.reset': 'Palauta oletus',
    'set.proxy': 'CORS-välityspalvelin (valinnainen)',
    'set.mmlKey': 'Maanmittauslaitoksen API-avain (valinnainen)',
    'set.about': 'Tietoa',
    'about.model': 'Pisteytys painottaa: kasvupaikkatyyppi (kuiva kangas), männikön ikä, jäkäläisyys / puuston harvuus, rinteen kaltevuus ja ilmansuunta sekä pohjoisuus. Arvio perustuu paikkatietoon — maastossa ratkaisee silmä.',
    'about.season': 'Sesonki: elokuun lopusta lokakuulle, parhaimmillaan syyskuussa. Etsi jäkäläistä, valoisaa harjun tai kankaan rinnettä ja vanhoja mäntyjä.',
    'ft.4': 'Kuivahko kangas (VT)',
    'ft.5': 'Kuiva kangas (CT)',
    'ft.6': 'Karukkokangas (ClT)',
    'layers.base': 'Pohjakartta',
    'layers.habitat': 'Kasvupaikkataso',

    'part.site': 'Kasvupaikka',
    'part.age': 'Puuston ikä',
    'part.lichen': 'Jäkälä / valoisuus',
    'part.slope': 'Rinne',
    'part.aspect': 'Ilmansuunta',
    'part.north': 'Pohjoisuus',

    'f.type': 'Kasvupaikka',
    'f.species': 'Pääpuulaji',
    'f.age': 'Ikä',
    'f.basal': 'Pohjapinta-ala',
    'f.slope': 'Rinne',
    'f.aspect': 'Rinteen suunta',
    'f.elev': 'Korkeus',
    'f.area': 'Pinta-ala',
    'f.height': 'Keskipituus',
    'f.dev': 'Kehitysluokka',
    'f.soil': 'Maalaji',
    'f.years': 'v',
    'f.flat': 'tasainen',

    'sheet.save': 'Tallenna kohde',
    'sheet.saved': 'Tallennettu',
    'sheet.navigate': 'Navigoi',
    'sheet.raw': 'Kaikki kuviotiedot',
    'sheet.unknown': 'ei tietoa',
    'sheet.estimated': 'arvio',

    'list.title': 'Parhaat näkymässä',
    'list.count': (n) => `${n} kuviota`,
    'list.empty': 'Ei osumia tällä alueella.\nKokeile laajentaa hakuehtoja tai siirry pohjoisemmas — kuivia kankaita on eniten harjuilla ja karuilla mailla.',

    'st.ready': 'Valmis',
    'st.loading': 'Haetaan kuvioita…',
    'st.terrain': 'Lasketaan rinteitä…',
    'st.zoomIn': 'Lähennä karttaa (taso 13+)',
    'st.found': (n, t) => `${n} osumaa${t ? ' (rajattu)' : ''}`,
    'st.none': 'Ei osumia näkymässä',
    'st.error': 'Aineistoa ei saatu',
    'st.offline': 'Ei verkkoyhteyttä',

    'toast.gpsDenied': 'Paikannus estetty. Salli sijainti selaimen asetuksista.',
    'toast.gpsUnavailable': 'Sijaintia ei saatu. Kokeile ulkona avoimella paikalla.',
    'toast.gpsSearching': 'Haetaan GPS-sijaintia…',
    'toast.saved': 'Kohde tallennettu',
    'toast.removed': 'Kohde poistettu',
    'toast.noWaypoints': 'Ei tallennettuja kohteita',
    'toast.terrainOff': 'Korkeusmallia ei saatu — rinnettä ei lasketa.',
    'toast.outsideFinland': 'Aineisto kattaa vain Suomen.',
    'toast.truncated': 'Paljon kuvioita — lähennä nähdäksesi kaikki.',
    'toast.cleared': 'Kohteet tyhjennetty',

    'wp.confirmClear': 'Poistetaanko kaikki tallennetut kohteet?',
  },

  en: {
    'app.tagline': 'Matsutake · Finland',
    'legend.title': 'Match',
    'legend.s90': '90+ · prime spot',
    'legend.s75': '75–89 · excellent',
    'legend.s60': '60–74 · good',
    'legend.s45': '45–59 · possible',
    'legend.hint': 'Only dry heath with old pine is shown.',
    'cta.scan': 'Search this area',
    'set.filters': 'Search criteria',
    'set.minAge': 'Minimum pine age',
    'set.minScore': 'Show from score',
    'set.pineOnly': 'Pine-dominated stands only',
    'set.needSlope': 'Require slope (≥3°)',
    'set.terrain': 'Compute slope and aspect from elevation model',
    'set.autoscan': 'Search automatically when the map moves',
    'set.saved': 'Saved spots',
    'set.exportGpx': 'Export GPX',
    'set.clearWp': 'Clear',
    'set.data': 'Data source',
    'set.dataInfo': 'Forest stands: Finnish Forest Centre open forest data (WFS). Covers mainly privately owned forest — state land (Metsähallitus) may be missing.',
    'set.wfsUrl': 'WFS endpoint',
    'set.layer': 'Layer',
    'set.test': 'Test connection',
    'set.reset': 'Reset to default',
    'set.proxy': 'CORS proxy (optional)',
    'set.mmlKey': 'National Land Survey API key (optional)',
    'set.about': 'About',
    'about.model': 'Scoring weighs site type (dry heath), pine age, lichen cover / openness, slope steepness and aspect, and how far north the stand lies. It is a desk estimate — the forest itself decides.',
    'about.season': 'Season: late August to October, best in September. Look for open, lichen-floored esker or heath slopes with old pines.',
    'ft.4': 'Sub-dry heath (VT)',
    'ft.5': 'Dry heath (CT)',
    'ft.6': 'Barren heath (ClT)',
    'layers.base': 'Base map',
    'layers.habitat': 'Habitat layer',

    'part.site': 'Site type',
    'part.age': 'Stand age',
    'part.lichen': 'Lichen / openness',
    'part.slope': 'Slope',
    'part.aspect': 'Aspect',
    'part.north': 'Northerliness',

    'f.type': 'Site type',
    'f.species': 'Main species',
    'f.age': 'Age',
    'f.basal': 'Basal area',
    'f.slope': 'Slope',
    'f.aspect': 'Facing',
    'f.elev': 'Elevation',
    'f.area': 'Area',
    'f.height': 'Mean height',
    'f.dev': 'Development class',
    'f.soil': 'Soil',
    'f.years': 'yr',
    'f.flat': 'flat',

    'sheet.save': 'Save spot',
    'sheet.saved': 'Saved',
    'sheet.navigate': 'Navigate',
    'sheet.raw': 'All stand attributes',
    'sheet.unknown': 'unknown',
    'sheet.estimated': 'estimate',

    'list.title': 'Best in view',
    'list.count': (n) => `${n} stands`,
    'list.empty': 'No matches in this area.\nWiden the criteria, or move north — dry heaths are commonest on eskers and barren ground.',

    'st.ready': 'Ready',
    'st.loading': 'Loading stands…',
    'st.terrain': 'Computing slopes…',
    'st.zoomIn': 'Zoom in (level 13+)',
    'st.found': (n, t) => `${n} matches${t ? ' (clipped)' : ''}`,
    'st.none': 'No matches in view',
    'st.error': 'Could not load data',
    'st.offline': 'No network connection',

    'toast.gpsDenied': 'Location blocked. Allow it in your browser settings.',
    'toast.gpsUnavailable': 'No location fix. Try outdoors with a clear sky.',
    'toast.gpsSearching': 'Getting GPS fix…',
    'toast.saved': 'Spot saved',
    'toast.removed': 'Spot removed',
    'toast.noWaypoints': 'No saved spots',
    'toast.terrainOff': 'Elevation model unavailable — slope not computed.',
    'toast.outsideFinland': 'The dataset covers Finland only.',
    'toast.truncated': 'Many stands here — zoom in to see them all.',
    'toast.cleared': 'Saved spots cleared',

    'wp.confirmClear': 'Delete all saved spots?',
  },
};

let lang = localStorage.getItem('mg.lang') || 'fi';

export function getLang() { return lang; }

export function setLang(l) {
  lang = l === 'en' ? 'en' : 'fi';
  localStorage.setItem('mg.lang', lang);
  document.documentElement.lang = lang;
  applyStatic();
}

export function t(key, ...args) {
  const v = STRINGS[lang][key] ?? STRINGS.fi[key] ?? key;
  return typeof v === 'function' ? v(...args) : v;
}

/** Refresh every element carrying data-i18n. */
export function applyStatic(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
}
