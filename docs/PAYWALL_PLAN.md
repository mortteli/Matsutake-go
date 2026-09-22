# Paywall plan

How to charge for the model layer without breaking the licences it is built on, and in which order
to do the work. Builds on [SCALING.md](SCALING.md) §5–8 and [DATA_LICENSES.md](../DATA_LICENSES.md),
re-checked against the code as it stands after the ES-module split and the Swedish pilot.

> **What changed since SCALING.md was written.** Its line references point at the old single-file
> `index.html`; the code now lives in `js/`. Item 2 of its recommended order is **done** —
> `data/terrain/dem_64m_*.tif` and `terrain_meta.json` are published, so Open-Meteo is fallback
> only. The shipped Finnish head is now `mlp+lgbm` (`prob_meta.json`), not `lgbm`, so §5's
> baseline table has to be re-read from the current `ml/models/matsutake/report.json` before the
> comparison in Phase 0 means anything. Everything else in §5 still holds: the Finnish map is
> CC BY-NC, the probe failure is still silent (`js/inspect.js:36-40`), and OSM, OpenTopoMap, Esri
> and Nominatim are still in the request path (`js/maplayer.js:11-15`, `js/search.js:76`,
> `js/nearby.js:424`).

---

## 1. What is sold, and what stays free

The thing worth paying for is the one thing nobody else has: the trained probability map. The rule
layer is Luke's public data composited in the browser, and the findings are public GBIF/FinBIF
records — anyone can see both elsewhere, and charging for them would be charging for other
people's open data.

| | Free | Paid |
|---|---|---|
| Rule layer (Luke masks, live sliders) | ✅ | ✅ |
| Tap sheet: site class, ground, metrics, slope, harvest | ✅ | ✅ |
| Findings layer, seasonality chart | ✅ (commercially usable records only, §3c) | ✅ |
| Search, GPS, "lähellä sinua" | ✅ | ✅ |
| **🧠 Model layer, Finland, 16 m** | coarse preview (§4d) | ✅ full resolution |
| **Model score in the tap sheet** (`readProb`, `js/inspect.js:128`) | — | ✅ |
| **Sweden pilot** (`data/matsutake_se/`) | — | ✅ |

This split has a convenient property: the paid surface is exactly the **baked, static, range-read
path** — the one SCALING.md §1 says scales. Every paid byte is a COG range read off object storage.
The free surface is the live path, which is the one that costs Luke and Metsäkeskus (§6).

**Recommendation on price shape: a season pass, not a subscription.** Matsutake is a six-to-eight
week season (`js/seasonality.js` draws it). A monthly subscription either churns in October or
bills people through the winter for a map they cannot use; both generate refund requests. One
payment, valid until 31 December of the season it was bought in, matches how the app is used.
Stripe Checkout handles this as a one-off `payment` session with no subscription machinery at all.

---

## 2. Phase 0 — the gate: can the model be sold at all

**Nothing below is worth building until this passes.** Same conclusion as SCALING.md §8 item 1.

### 2a. Finland: retrain without CC BY-NC records

1. Add a second predicate next to `redistributable()` in `ml/ingest/fetch_observations.py:113`:

   ```python
   def commercial_ok(lic):
       """Records a paid product may train on: CC0 / CC BY only."""
       return "NC" not in (lic or "").upper()
   ```

   Match on the substring, not the URL — GBIF spells it `by-nc/4.0/legalcode`, FinBIF
   `intellectualRightsCC-BY-NC-4.0` (SCALING.md §5).
2. Apply it behind a flag (`--commercial`) at dataset build time, not at fetch time, so one fetch
   serves both builds and `observations.csv` stays the full record.
3. Write the commercial model to its own directory (`ml/models/matsutake_commercial/`) so the
   CC BY-NC model and its report stay intact for comparison.
4. Compare fold-by-fold against the **current** `report.json`, judging on the spread in
   `oof_scores.csv`, not one decimal of AUC. SCALING.md measured the cost at −9 % fine presences
   and −23 % target-group background; widen the `bg_fungi` query to win the background back.

**Pass bar:** still clearly above `rule_new_default` (0.741 AUC / 0.129 PR-AUC). The product's
claim is that the model beats the rules; if the CC BY-only model does not, there is nothing to
charge for and the plan stops here.

### 2b. Sweden: nearly free

The Swedish records are CC0 5479 / CC BY 14 / **CC BY-NC 8** (DATA_LICENSES.md). Dropping 8 of
5501 is noise; rerun and ship. The environmental inputs are CC0, CC BY 4.0 SE or "Open data" with
no stated constraint — **read the SLU forest-map and SGU terms once for commercial use before
launch**; "open data" is not a licence name and SWEDEN_DATA.md does not quote one.

### 2c. Licence the paid output as proprietary, not CC BY

DATA_LICENSES.md ends with *"to publish the derived layers under plain CC BY 4.0, re-run the
pipeline with the CC BY-NC records removed"*. That is the right remedy for the public repo and
**the wrong one for a paywall**: CC BY lets any paying customer re-host the file for free,
legally. CC BY inputs do not force the output to be CC BY — they require attribution, which the
app already gives. The commercial map is therefore:

- © the project, all rights reserved, access under the terms of service;
- with the existing attribution line for every CC BY source kept on the layer.

Update that sentence in `DATA_LICENSES.md` / `ml/licenses.py:155` when the commercial build lands.

---

## 3. Phase 1 — make the free surface commercially clean

Once anything is sold, the whole site is a commercial service — including its free tier. These are
needed regardless of how the paywall is built.

### 3a. Basemaps and geocoding → MML

| Now | Problem | Replace with |
|---|---|---|
| `tile.openstreetmap.org` (`js/maplayer.js:11`) | tile policy: no heavy/commercial use | MML Maastokartta (WMTS, free API key, CC BY 4.0) |
| `tile.opentopomap.org` (`js/maplayer.js:13`) | volunteer server, same concern | MML Maastokartta already has contours; drop the layer |
| `server.arcgisonline.com` (`js/maplayer.js:15`) | keyless endpoint, not licensed for this | MML Ortokuva |
| `nominatim.openstreetmap.org` (`js/search.js:76`, `js/nearby.js:424`) | 1 req/s app-wide, no commercial use | MML geocoding API, or self-hosted Photon on the Finland extract |

Sweden needs its own basemap for the pilot area (Lantmäteriet, free account) or a paid provider;
MML does not cover it.

### 3b. Fix the silent probe failure

`js/inspect.js:36-40` still turns a throttled probe into `null`, which the sheet reads as "condition
not met". A paying customer who is told *not a matsutake spot* because Luke was busy has a
legitimate complaint. Distinguish *failed* from *false* and let the sheet say "tietoa ei saatu".
Small, and SCALING.md §2c already says do it before there is load.

### 3c. Findings layer: drop CC BY-NC records from the commercial build

`data/*/observations.json` carries NC records: 49 of 455 matsutake, **794 of 2747 kanttarelli**
(mostly iNaturalist). Displaying them on a commercial site is commercial use. Filter them in
`ml/export/export_observations.py` with the same `commercial_ok()` predicate. The kanttarelli loss
(29 %) is visible on the map and in the seasonality chart; accept it, or ask iNaturalist observers
nothing — there is no per-record relicensing route at that scale.

---

## 4. Phase 2 — architecture

```
            ┌─────────────── one site: matsutake.<domain> ───────────────┐
browser ──▶ │ Cloudflare Pages   index.html, js/, vendor/, free data/    │
            │ Worker route       /data/paid/*  → cookie check → R2 range │
            │                    /api/checkout, /api/webhook, /api/login │
            └────────────────────────────────────────────────────────────┘
                     │                    │                    │
                Cloudflare R2        Workers KV            Stripe
             commercial COGs     email → paid_until      Checkout, one-off
```

### 4a. Same origin, so the cookie just works

SCALING.md §7 suggests `credentials: 'include'` plus CORS on the bucket. Simpler: put the Worker
on a **route of the app's own domain**. The paid COGs are then same-origin, the browser sends the
session cookie on every range read with no fetch options, and `georaster`'s plain URL loading
(`js/problayer.js:353`, `new URL(f.url, location.href)`) needs no change at all. No CORS, no
preflight on every range request.

### 4b. The client change is mostly a meta change

The raster URLs already come from `prob_meta.json` (`meta.files[].url`), so moving the paid parts
means the commercial `prob_meta.json` lists `/data/paid/matsutake/prob_…tif` instead of
`data/matsutake/…`. The code that has to change:

- `js/problayer.js:56` (`fetch` of the meta) and `:356` (`Promise.all` over the rasters): a 401 or
  403 must become an upsell sheet, not a generic failure.
- `js/inspect.js:128`: `readProb` on a free session skips the request instead of catching a 401.
- A small account row in the settings sheet (`js/ui.js`): *Osta kausipassi* / *Palauta ostos* /
  *Voimassa 31.12.2027 asti*.
- `js/state.js`: nothing. Entitlement lives in an HttpOnly cookie, never in `localStorage`.

### 4c. Entitlement without passwords

1. **Buy.** `/api/checkout` creates a Stripe Checkout session (one-off, `customer_email`
   collected). On success Stripe redirects to `/?paid={CHECKOUT_SESSION_ID}`.
2. **Unlock this device.** The Worker retrieves the session from Stripe, confirms `paid`, writes
   `email → paid_until` to KV, and sets a signed cookie (HS256 JWT, `exp = paid_until`,
   `HttpOnly; Secure; SameSite=Lax`). The webhook (`checkout.session.completed`) writes the same KV
   row, so a closed tab never loses a purchase.
3. **Another device, or cleared cookies.** *Palauta ostos* → email → one-time magic link (needs a
   transactional mail sender; Resend or Postmark) → same cookie.
4. **Every paid range read.** Verify the JWT (≈1 ms, no KV lookup), then serve from the Cache API
   if present, else `R2.get(key, { range })` → 206. Auth runs *before* the cache, so cached bytes
   are never served to an unpaid request.

State is one KV key per buyer. There is no database, no user table, no password.

### 4d. The free preview

A paywall that shows nothing sells nothing. Export one extra, heavily downsampled model raster
(e.g. 256 m, top-15 % only) to the free path. It shows *where in Finland* the good ground is, and
is useless for finding a stand — which is exactly the thing being sold. It is one more output from
`ml/export/export_app.py`, and a tile layer that swaps to the paid parts above a zoom threshold.

### 4e. The commercial map never enters git

The repo is public and `data/` is in its history (SCALING.md §6). The CC BY-NC map already there
stays there — it is licensed non-commercially and cannot legally undercut the paid one. But the
**commercial** rasters go straight from the pipeline to R2 (`wrangler r2 object put` in the
Actions job) and are never committed. Add `data/paid/` to `.gitignore` so a local export cannot be
committed by accident.

The code stays MIT. Anyone can rerun the pipeline on the public inputs; what they pay for is not
having to. That is a fine moat for a side project, and pretending otherwise would mean closing the
repo, which buys little.

---

## 5. Phase 3 — legal and commercial minimums

Short list, not legal advice; each is a day or less.

- **Business identity.** Stripe needs a Y-tunnus (a toiminimi is enough).
- **VAT.** Digital services to EU consumers are taxed at the buyer's rate (OSS). Either register
  for OSS and use Stripe Tax, or use a merchant of record (Paddle, Lemon Squeezy) that files it
  instead. **Recommendation: merchant of record** for a seasonal side project — it removes the
  quarterly filings entirely, at a few percent of revenue. The Worker flow in §4c is the same
  either way; only the checkout and webhook calls change.
- **Withdrawal right.** Finnish/EU consumer law gives 14 days on digital content unless the buyer
  expressly consents to immediate delivery and acknowledges losing the right. One checkbox on the
  checkout page.
- **Terms of service.** The model is a probability, not a promise; *jokamiehenoikeus* applies and
  does not cover everything (national parks, restricted areas); the map says nothing about who
  owns the land. A paid product raises expectations the free one never did.
- **Privacy notice.** The only personal data is the buyer's email (KV, Stripe, mail sender). The
  app already keeps GPS in memory only (`js/gps.js:8`); say so.
- **Attribution.** Unchanged: every CC BY source stays credited on the layer and on ℹ️.

---

## 6. What the paywall does *not* fix: the free tier's load

Paying users only add static, CDN-cacheable reads. But a paywall brings marketing, and marketing
brings free users — and every free user runs the live Luke path, ~269 requests a session
(SCALING.md §1–2). The Luke caching proxy (SCALING.md §4, "a weekend") should be ready **before**
the launch push, not after the first complaint. The 1000-user work (baking MVMI bands) stays
conditional on actually getting there.

---

## 7. Order of work and timing

Today is late September 2026 — the season is ending. The realistic launch is **before the 2027
season, i.e. by mid-July 2027**, which leaves the whole winter and makes Phase 0 unhurried.

| # | Phase | Size | Gate / done when |
|---|---|---|---|
| 0a | CC BY-only retrain, Finland (§2a) | 1–2 days | beats `rule_new_default` clearly on fold spread — **go / no-go** |
| 0b | Drop 8 NC records, Sweden; read SLU/SGU terms (§2b) | ½ day | terms permit commercial use |
| 0c | Relicense commercial output as proprietary (§2c) | ½ day | DATA_LICENSES.md updated |
| 1 | MML basemaps + geocoder, probe fix, NC-free findings (§3) | 3–4 days | no OSM/Esri/Nominatim requests in devtools |
| 2 | Cloudflare Pages + R2 + Worker, cookie check, free preview (§4) | 3–5 days | paid COG returns 401 without cookie, 206 with |
| 3 | Checkout, webhook, magic-link restore, account row (§4c) | 3–4 days | test-mode purchase unlocks two devices |
| 4 | ToS, privacy, VAT route, withdrawal checkbox (§5) | 1–2 days | pages live, checkout compliant |
| 5 | Luke caching proxy (§6) | ~2 days | default-settings tiles served from cache |
| — | **Launch** | | by mid-July 2027 |

Phases 1 and 3b's probe fix are worth doing even if Phase 0 fails.

---

## 8. Open decisions

1. **Season pass vs subscription** — recommended: season pass (§1).
2. **Stripe + OSS vs merchant of record** — recommended: merchant of record (§5).
3. **Is Sweden in the paid tier at launch?** It is a 150 × 150 km pilot; selling it as a bonus is
   fine, selling it as "Sweden" is not.
4. **Price.** Not a technical question. Anchor against what a day's gas and a wasted drive cost,
   not against app-store prices.
5. **Domain.** Needed before Phase 2; the cookie scope (§4a) depends on it.
