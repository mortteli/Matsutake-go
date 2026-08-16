/**
 * Finnish forest-data code lists (Suomen metsäkeskus / metsävaratieto).
 *
 * These are the national classifications used in the open forest data. Only the
 * codes that matter for matsutake habitat are commented in detail.
 */

/** Kasvupaikka / site fertility class. 5 = kuiva kangas is the target. */
export const FERTILITY = {
  1: { fi: 'Lehto',                 en: 'Herb-rich forest',      short: 'Lehto' },
  2: { fi: 'Lehtomainen kangas',    en: 'Herb-rich heath (OMT)', short: 'OMT' },
  3: { fi: 'Tuore kangas',          en: 'Mesic heath (MT)',      short: 'MT' },
  4: { fi: 'Kuivahko kangas',       en: 'Sub-dry heath (VT)',    short: 'VT' },
  5: { fi: 'Kuiva kangas',          en: 'Dry heath (CT)',        short: 'CT' },
  6: { fi: 'Karukkokangas',         en: 'Barren heath (ClT)',    short: 'ClT' },
  7: { fi: 'Kalliomaa tai hietikko',en: 'Rocky or sandy soil',   short: 'Kallio' },
  8: { fi: 'Lakimetsä tai tunturi', en: 'Summit or fell forest', short: 'Laki' },
};

/** Pääpuulaji / main tree species. 1 = mänty (Scots pine) is what matsutake needs. */
export const SPECIES = {
  1:  { fi: 'Mänty',         en: 'Scots pine' },
  2:  { fi: 'Kuusi',         en: 'Norway spruce' },
  3:  { fi: 'Rauduskoivu',   en: 'Silver birch' },
  4:  { fi: 'Hieskoivu',     en: 'Downy birch' },
  5:  { fi: 'Haapa',         en: 'Aspen' },
  6:  { fi: 'Harmaaleppä',   en: 'Grey alder' },
  7:  { fi: 'Tervaleppä',    en: 'Black alder' },
  8:  { fi: 'Muu havupuu',   en: 'Other conifer' },
  9:  { fi: 'Muu lehtipuu',  en: 'Other broadleaf' },
  10: { fi: 'Kontortamänty', en: 'Lodgepole pine' },
  11: { fi: 'Kataja',        en: 'Juniper' },
  12: { fi: 'Kynäjalava',    en: 'European white elm' },
  16: { fi: 'Siperianlehtikuusi', en: 'Siberian larch' },
  19: { fi: 'Muu puulaji',   en: 'Other species' },
  29: { fi: 'Kuusi (siperian)', en: 'Siberian spruce' },
};

/** Kehitysluokka / development class. */
export const DEV_CLASS = {
  A0: { fi: 'Aukea',                    en: 'Open / clear-cut' },
  S0: { fi: 'Siemenpuumetsikkö',        en: 'Seed-tree stand' },
  T1: { fi: 'Taimikko alle 1,3 m',      en: 'Sapling stand < 1.3 m' },
  T2: { fi: 'Taimikko yli 1,3 m',       en: 'Sapling stand > 1.3 m' },
  '02': { fi: 'Nuori kasvatusmetsikkö', en: 'Young thinning stand' },
  '03': { fi: 'Varttunut kasvatusmetsikkö', en: 'Advanced thinning stand' },
  '04': { fi: 'Uudistuskypsä metsikkö',  en: 'Mature stand' },
  '05': { fi: 'Suojuspuumetsikkö',       en: 'Shelterwood stand' },
  Y1: { fi: 'Eri-ikäisrakenteinen',      en: 'Uneven-aged stand' },
};

/** Maalaji / soil type — coarse, sandy and gravelly soils suit matsutake. */
export const SOIL = {
  10: { fi: 'Kivennäismaa, maalajia ei määritetty', en: 'Mineral soil, unspecified' },
  11: { fi: 'Hienojakoinen kivennäismaa', en: 'Fine-grained mineral soil' },
  12: { fi: 'Keskikarkea/karkea kivennäismaa', en: 'Medium/coarse mineral soil', coarse: true },
  13: { fi: 'Kalliomaa',        en: 'Bedrock' },
  14: { fi: 'Kivinen keskikarkea/karkea', en: 'Stony medium/coarse soil', coarse: true },
  15: { fi: 'Hiekkamaa',        en: 'Sandy soil', coarse: true },
  16: { fi: 'Soraa tai moreenia', en: 'Gravel or till', coarse: true },
  60: { fi: 'Turvemaa',         en: 'Peat soil' },
  61: { fi: 'Rahkaturve',       en: 'Sphagnum peat' },
  62: { fi: 'Saraturve',        en: 'Carex peat' },
  63: { fi: 'Puuturve',         en: 'Woody peat' },
};

/** Direction names for aspect, index = round(aspect / 45) % 8. */
export const COMPASS = {
  fi: ['pohjoiseen', 'koilliseen', 'itään', 'kaakkoon', 'etelään', 'lounaaseen', 'länteen', 'luoteeseen'],
  en: ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'],
  abbr: ['P', 'KO', 'I', 'KA', 'E', 'LO', 'L', 'LU'],
};

export function fertilityName(code, lang = 'fi') {
  return FERTILITY[code]?.[lang] ?? (code == null ? '—' : `Koodi ${code}`);
}
export function speciesName(code, lang = 'fi') {
  return SPECIES[code]?.[lang] ?? (code == null ? '—' : `Koodi ${code}`);
}
export function devClassName(code, lang = 'fi') {
  if (code == null) return '—';
  return DEV_CLASS[String(code).trim()]?.[lang] ?? String(code);
}
export function soilName(code, lang = 'fi') {
  return SOIL[code]?.[lang] ?? (code == null ? '—' : `Koodi ${code}`);
}
export function isCoarseSoil(code) {
  return SOIL[code]?.coarse === true;
}
export function aspectName(deg, lang = 'fi') {
  if (deg == null || !isFinite(deg)) return '—';
  const i = Math.round(((deg % 360) + 360) % 360 / 45) % 8;
  return COMPASS[lang === 'en' ? 'en' : 'fi'][i];
}
export function aspectAbbr(deg) {
  if (deg == null || !isFinite(deg)) return '—';
  const i = Math.round(((deg % 360) + 360) % 360 / 45) % 8;
  return COMPASS.abbr[i];
}
