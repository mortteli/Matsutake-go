/** Saved spots: localStorage-backed, with GPX export for a handheld GPS. */

const KEY = 'mg.waypoints';

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); }
  catch { return []; }
}

function write(list) {
  localStorage.setItem(KEY, JSON.stringify(list));
}

export function all() { return read(); }

export function has(id) { return read().some((w) => w.id === id); }

export function add(wp) {
  const list = read();
  if (list.some((w) => w.id === wp.id)) return list;
  list.unshift({ ...wp, savedAt: new Date().toISOString() });
  write(list);
  return list;
}

export function remove(id) {
  const list = read().filter((w) => w.id !== id);
  write(list);
  return list;
}

export function toggle(wp) {
  return has(wp.id) ? (remove(wp.id), false) : (add(wp), true);
}

export function clear() { write([]); }

const esc = (s) => String(s).replace(/[<>&'"]/g, (c) =>
  ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;' }[c]));

export function toGpx() {
  const list = read();
  const pts = list.map((w) => {
    const desc = [
      `Pisteet: ${w.score}`,
      w.fertilityName ? `Kasvupaikka: ${w.fertilityName}` : null,
      w.age != null ? `Ikä: ${w.age} v` : null,
      w.slope != null ? `Rinne: ${w.slope.toFixed(1)}°` : null,
    ].filter(Boolean).join(' | ');
    return `  <wpt lat="${w.lat.toFixed(6)}" lon="${w.lon.toFixed(6)}">
    <name>${esc(w.name)}</name>
    <desc>${esc(desc)}</desc>
    <sym>Flag, Blue</sym>
    <time>${w.savedAt}</time>
  </wpt>`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Matsutake Go" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>Matsutake Go — tallennetut kohteet</name><time>${new Date().toISOString()}</time></metadata>
${pts}
</gpx>`;
}

/** Offer the GPX as a download, falling back to the share sheet on iOS. */
export async function exportGpx() {
  const list = read();
  if (!list.length) return false;
  const xml = toGpx();
  const file = new File([xml], 'matsutake-go.gpx', { type: 'application/gpx+xml' });

  if (navigator.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file], title: 'Matsutake Go' }); return true; }
    catch (e) { if (e.name === 'AbortError') return true; }
  }

  const url = URL.createObjectURL(new Blob([xml], { type: 'application/gpx+xml' }));
  const a = document.createElement('a');
  a.href = url; a.download = 'matsutake-go.gpx';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  return true;
}
