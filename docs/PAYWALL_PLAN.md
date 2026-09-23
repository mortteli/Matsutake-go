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
| Findings layer, seasonality chart | ✅ (commercially usable records only, §3d) | ✅ |
| Search, GPS, "lähellä sinua" | ✅ | ✅ |
| **🧠 Model layer, Finland, 16 m** | coarse preview (§4d) | ✅ full resolution |
| **Model score in the tap sheet** (`readProb`, `js/inspect.js:128`) | — | ✅ |
| **Sweden pilot** (`data/matsutake_se/`) | — | ✅ |

This split has a convenient property: the paid surface is exactly the **baked, static, range-read
path** — the one SCALING.md §1 says scales. Every paid byte is a COG range read off object storage.
The free surface is the live path, which is the one that costs Luke and Metsäkeskus (§6).

### Price shape: monthly + yearly subscriptions, with codes

Decided: **monthly and yearly subscriptions**, off-season discounts, and limited early-bird codes
that give free access for a while. All of it is Stripe configuration, not code:

| Offer | Stripe object | Notes |
|---|---|---|
| Monthly | `Price`, `recurring.interval = month` | Priced so the yearly is obviously better: expect people to subscribe in August and cancel in October — the season is 6–8 weeks (`js/seasonality.js`) |
| Yearly | `Price`, `recurring.interval = year` | The one that earns. Once there are several countries the seasons stop lining up (Australia's autumn is March–May), which makes the yearly easier to sell |
| Off-season discount | `Coupon` (e.g. 30 % off, `duration: once`) that the Worker attaches at checkout between set dates | Aimed at the yearly: "buy next season now, cheaper" |
| Early bird, free for N months | `Coupon` 100 % off, `duration: repeating`, `duration_in_months: N`, exposed as a `PromotionCode` with `max_redemptions` and `expires_at` | Stripe counts the redemptions and enforces the limit and expiry — no table of our own |
| Free trial (optional) | `subscription_data.trial_period_days` | |

With `payment_method_collection: "if_required"` a zero-euro checkout (100 % code) does not ask for
a card, so an early-bird user gets in with just an email. When the free months end without a card,
the subscription lapses to `past_due`/`canceled` and access stops on its own — Stripe sends the
"add a card" email if that is turned on.

Cancelling, changing card, switching monthly → yearly and downloading receipts are all the
**Stripe Customer Portal**, a hosted page one API call away. There is no billing UI to build.

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

### 3a. Licence status of every external service the app uses today

Checked 2026-09-23 against each provider's published terms. "Data licence" and "service terms" are
different questions: CC BY 4.0 data can be used commercially, but the *server* it comes from can
still be a free public service with fair-use limits.

| Service | Where | Data licence | Commercial use of the service | Verdict |
|---|---|---|---|---|
| **Luke MVMI WMS** (`kartta.luke.fi`) | rule layer, tap probes | CC BY 4.0 | ✅ allowed, free, no key | **Keep.** Attribution already shown. Load is the risk, not the licence (§6) |
| **Metsäkeskus WFS** (`avoin.metsakeskus.fi`) | harvests | CC BY 4.0 | ✅ allowed, free | **Keep.** Tap-only at scale (SCALING.md §3) |
| **MML elevation** (baked into `data/terrain/`) | slope | CC BY 4.0 | ✅ | **Keep** |
| **GBIF / FinBIF** | build time only | per record | ✅ for CC0 / CC BY records | **Keep**, with the NC filter (§2a, §3d) |
| **Open-Meteo** (`api.open-meteo.com`) | slope fallback | CC BY 4.0 data | ❌ *"You may only use the free API services for non-commercial purposes."* Paid plans (API key, `customer-api.open-meteo.com`) allow it | **Remove the fallback** in the commercial build — Finland and Sweden have baked terrain. Bake terrain for each new country instead of paying |
| **OSM tiles** (`tile.openstreetmap.org`) | basemap | ODbL | ⚠️ allowed, but no SLA: *"access may be withdrawn at any point: you may no longer be able to serve your paying customers"*; offline/bulk features forbidden | **Replace** |
| **OpenTopoMap** | basemap | CC BY-SA 3.0 | ⚠️ allowed if the volunteer server is not loaded heavily; no uptime guarantee | **Replace** |
| **Esri World Imagery** (`server.arcgisonline.com`) | satellite | Esri terms | ❌ legacy keyless endpoint is for licensed ArcGIS users; not for commercial use this way | **Replace** — the only one of the three basemaps that is a clear violation |
| **Nominatim** (`nominatim.openstreetmap.org`) | search, nearby names | ODbL | ⚠️ allowed at max 1 req/s *for the whole app*, and *"you must not implement [auto-complete] on the client side"* — the 600 ms debounced search-while-typing is close to that line | **Replace** — 1 req/s total cannot serve a paying user base |
| **GitHub Pages** | hosting | — | ⚠️ not meant for sites whose main purpose is commercial transactions or SaaS | **Move** to Cloudflare Pages (§4) |
| Leaflet, georaster, georaster-layer-for-leaflet | `vendor/` | BSD-2 / Apache-2.0 / MIT | ✅ | **Keep** — permissive, just keep the licence files |

So the licence problems are concentrated in exactly two places: **the basemaps + geocoder** (§3b)
and **the CC BY-NC observation records** (§2a, §3d). Every forest-data source is clean.

### 3b. Basemap and geocoding: MapTiler vs Stadia Maps

Both are global, both cover Japan and Australia, both need a paid plan for commercial use (neither
free tier allows it). Prices from their pricing pages, 2026-09-23, in USD:

| | **MapTiler Flex** | **Stadia Starter** | **Stadia Standard** |
|---|---|---|---|
| Price | $30/month | $20/month | $80/month |
| Included | 25 000 map sessions, 500 000 API requests, 3 000 search sessions | 1 000 000 credits | 7 500 000 credits |
| Overage | $2.50 / 1 000 sessions | $0.03 / 1 000 credits | $0.02 / 1 000 credits |
| How a map is billed | **per session** with the Leaflet plugin: *"any user interactions like panning, zooming … are included within a single session"*; per tile (1 request each) with plain XYZ tiles | per tile, 1 credit each | per tile, 1 credit |
| Satellite | ✅ on Flex | ❌ | ✅, 4 credits a tile |
| Geocoding | included (search sessions) | 20 credits a request | 20 credits a request |
| Outdoor/topo style with contours | ✅ Outdoor, Topo | ✅ Stadia Outdoors, Stamen Terrain | same |
| Company | Swiss (Zurich) — EU-adequate for GDPR | US | US |

**What that costs this app.** A session here is panning-heavy — call it ~200 basemap tiles
(an estimate; measure it in devtools like SCALING.md says for bandwidth).

| Sessions / month | MapTiler Flex (per session) | Stadia Starter (no satellite) | Stadia Standard (with satellite) |
|---|---|---|---|
| 5 000 | $30 | $20 | $80 |
| 25 000 | $30 | ~$140 | $80 |
| 100 000 | ~$220 | ~$590 | ~$330 |

Basemap only; searches come on top — MapTiler's 3 000 included search sessions, then $2.50 per
1 000, versus 20 credits a request on Stadia (the nearby list's three reverse lookups alone are 60
credits a scan).

Stadia is cheaper only while the app is small *and* without satellite. Per-tile billing punishes
exactly what this app's users do — pan around a forest for ten minutes — whereas a MapTiler session
costs the same however much they pan.

**Recommendation: MapTiler**, via the `@maptiler/leaflet-maptilersdk` plugin so billing is per
session. Satellite and geocoding are on the entry plan, costs are predictable, and it is a European
company. Two things to prototype before committing:

1. The plugin renders the basemap with MapLibre (vector) *inside* Leaflet. Check that
   `SpotLayer`'s canvas composite and `GeoRasterLayer` still draw on top correctly, and that it
   is not noticeably heavier on an old phone. If it is, plain raster tiles still work — billed
   per request at $0.15 / 1 000 beyond the 500 000 included — and that is the fallback.
2. Check the Outdoor style is readable under the orange/green overlays; the current OSM look is
   what users know.

The API key is visible in the browser, as every tile key is: restrict it by HTTP referrer to the
production domain in MapTiler's dashboard.

MML Maastokartta (free API key, CC BY 4.0) can stay as an optional **extra** layer for Finland —
it is better cartography there — but not as the base the app depends on.

### 3c. Fix the silent probe failure

`js/inspect.js:36-40` still turns a throttled probe into `null`, which the sheet reads as "condition
not met". A paying customer who is told *not a matsutake spot* because Luke was busy has a
legitimate complaint. Distinguish *failed* from *false* and let the sheet say "tietoa ei saatu".
Small, and SCALING.md §2c already says do it before there is load.

### 3d. Findings layer: drop CC BY-NC records from the commercial build

`data/*/observations.json` carries NC records: 49 of 455 matsutake, **794 of 2747 kanttarelli**
(mostly iNaturalist). Displaying them on a commercial site is commercial use. Filter them in
`ml/export/export_observations.py` with the same `commercial_ok()` predicate. The kanttarelli loss
(29 %) is visible on the map and in the seasonality chart; accept it, or ask iNaturalist observers
nothing — there is no per-record relicensing route at that scale.

---

## 4. Phase 2 — architecture

```
            ┌─────────────── one site: shroomify.com (or similar) ───────────────┐
browser ──▶ │ Cloudflare Pages   index.html, js/, vendor/, free data/            │
            │ Worker route       /data/paid/<region>/* → cookie check → R2 range │
            │                    /api/checkout, /api/webhook, /api/login,        │
            │                    /api/portal                                     │
            └────────────────────────────────────────────────────────────────────┘
                     │                    │                     │            │
                Cloudflare R2        Workers KV              Stripe       mail sender
             commercial COGs    sub:<email>, login     subscriptions,    magic links
             per region          tokens (TTL)          codes, portal
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
- A small account row in the settings sheet (`js/ui.js`): *Tilaa* / *Kirjaudu* / *Tilaukseni* (valid until …, from
  a small `/api/me` call — the cookies are HttpOnly, so JS cannot read them).
- `js/state.js`: nothing. Entitlement lives in an HttpOnly cookie, never in `localStorage`.

### 4c. Accounts without passwords: the email is the username

**The account is the email address, and the proof of owning it is a link sent to it** — the same
login many apps use ("magic link"). No password is ever stored, so there is no password reset,
no hashing, and no leaked-password risk.

**Stripe is the database of who has paid.** A subscription's status (`active`, `trialing`,
`past_due`, `canceled`) and `current_period_end` live in Stripe; Stripe also knows the customer's
email. Our own storage is only a fast copy of that, kept in Workers KV:

```
KV  sub:<email>  →  { customer: "cus_…", status: "active", until: 1788220800 }
```

It is written only by the Stripe webhook (`customer.subscription.created/updated/deleted`), so it
is never the source of truth and can be rebuilt from Stripe at any time. That is the whole
"database": one small record per paying customer. (If you later want login history, per-country
plans or referral counts, Cloudflare D1 — SQLite at the edge — is the next step; nothing here
needs it yet.)

**Two cookies**, both `HttpOnly; Secure; SameSite=Lax`, signed by the Worker:

| Cookie | Lifetime | Holds | Checked |
|---|---|---|---|
| `session` | 90 days, renewed on use | the email | only when `access` has expired |
| `access` | 24 hours | email + `until` | on every paid range read, signature only (≈1 ms, no KV) |

The flows:

1. **Subscribe.** `/api/checkout` → Stripe Checkout (email, card or a code). Stripe redirects to
   `/?checkout={CHECKOUT_SESSION_ID}`; the Worker confirms it with Stripe and sets both cookies.
   The user is logged in without ever having "registered".
2. **Every paid request.** Valid `access` → serve. Expired `access` but valid `session` → the Worker
   reads `sub:<email>` from KV once, and if the subscription is still active issues a new
   `access` silently. The user never sees it. This is also what makes a **cancellation take
   effect within a day** without us revoking anything: the next refresh finds `canceled`.
3. **Cookie gone** (new phone, cleared browser, 90 days unused). The app shows **Kirjaudu** → the
   user types their email → the Worker emails a one-time link (valid 15 min, single use, stored in
   KV with a TTL) → clicking it sets both cookies. If that email has no active subscription, the
   link still logs them in and the app offers the plans.
4. **Manage.** *Tilaukseni* → `/api/portal` → Stripe Customer Portal for that customer.

Needs one transactional mail sender for the links (Resend, Postmark or Amazon SES — cents per
thousand at this volume). Passkeys can be added later on top of the same `session` cookie; they
are nice, not needed.

**Account sharing.** One login used on many phones is the cost of having no passwords. Cap it
cheaply if it ever matters: keep the last few `session` ids per email in KV and drop the oldest
when a new device logs in.

**Every paid range read** verifies `access`, then serves from the Cache API if present, else
`R2.get(key, { range })` → 206. Auth runs *before* the cache, so cached bytes are never served to an
unpaid request.

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

- **Business identity and VAT.** Decided: sold through the existing company, which handles VAT.
  Two things to confirm with whoever does its books: digital services to consumers in *other*
  EU countries are taxed at the buyer's rate via **OSS** once EU cross-border sales pass €10 000 a
  year; and selling to consumers outside the EU (Sweden is EU; Japan, Australia are not) can
  require registering for their consumption tax on digital services. **Stripe Tax** calculates
  the right rate per buyer and warns when a country's threshold is near — turn it on from day
  one so prices are shown VAT-inclusive correctly everywhere.
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

## 7. More countries

Sweden ships in the paid tier at launch — presented honestly as the Västerbotten pilot area, not as
"Sweden", until the national raster exists. After that the plan is more countries (Japan,
Australia, China and others). What that means for the paywall:

- **One subscription covers every region.** Per-country plans multiply Stripe prices and confuse
  the offer; the Worker only checks "is this subscription active", never "for which country".
  A per-region `prob_meta.json` under `/data/paid/<region>/` already fits how
  `js/problayer.js` loads regions (one `prob_meta.json` per region), so a new country is a new
  folder in R2 plus an entry in the region list — no auth change.
- **Each country repeats Phase 0.** Its observation records and environmental layers need the same
  commercial-use check as §2a–2b before its map goes behind the paywall. That is the real cost of a
  new country, not the hosting.
- **The basemap is already global** (§3b), which is why MML is not the base any more.
- **The free rule layer is Finland-only.** It is Luke's MVMI; other countries get the model layer
  and findings, not the live sliders. Say so on the region's info page.
- **China is a different kind of project.** Publishing maps of China is regulated (map review and
  approval), coordinates there are offset (GCJ-02) so WGS84 overlays land in the wrong place on
  Chinese basemaps, and foreign web services are often unreachable there. Treat it as its own
  investigation, not a data pipeline run. Japan and Australia have no comparable obstacle.

---

## 8. Domain and hosting costs

**Domain.** `shroomify.com` or similar is fine for a multi-country product — better than a
Finnish-only name. Before buying, search for existing apps and trademarks with the same name; a
name clash is far more expensive to fix after launch.

What matters technically: **the domain's DNS must be on Cloudflare** for the Worker to run on a
route of the same site (§4a). You can register the domain anywhere and point its nameservers to
Cloudflare (free plan). Check what the Zoner price is for: if €5/month or €25/year is *web hosting*,
it is not needed — Cloudflare Pages hosts the app. If it is the domain registration itself, it is
fine; a `.com` usually renews for around €10–15 a year, and Cloudflare Registrar sells at cost if
you would rather keep everything in one place. Check the **renewal** price, not the first-year one.

**Running costs, early on.** Every paid range read is a Worker request, and panning makes dozens.
The Workers free tier (100 000 requests a day) will run out with a few hundred active users; the
Workers paid plan (about $5 a month, 10 million requests included) is the realistic baseline.
R2 storage for a few GB is cents, egress is free. Add the map provider's plan and the mail sender.

---

## 9. Order of work and timing

Today is late September 2026 — the season is ending. The realistic launch is **before the 2027
season, i.e. by mid-July 2027**, which leaves the whole winter and makes Phase 0 unhurried.
Early-bird codes can go out in spring for testing.

| # | Phase | Size | Gate / done when |
|---|---|---|---|
| 0a | CC BY-only retrain, Finland (§2a) | 1–2 days | beats `rule_new_default` clearly on fold spread — **go / no-go** |
| 0b | Drop 8 NC records, Sweden; read SLU/SGU terms (§2b) | ½ day | terms permit commercial use |
| 0c | Relicense commercial output as proprietary (§2c) | ½ day | DATA_LICENSES.md updated |
| 1 | MapTiler basemap + geocoder, drop Open-Meteo fallback, probe fix, NC-free findings (§3) | 3–4 days | no OSM/OpenTopoMap/Esri/Nominatim/Open-Meteo requests in devtools |
| 2 | Domain on Cloudflare, Pages + R2 + Worker, cookie check, free preview (§4, §8) | 3–5 days | paid COG returns 401 without cookie, 206 with |
| 3 | Subscriptions, codes, webhook → KV, magic-link login, portal, account row (§1, §4c) | 4–5 days | test mode: subscribe, log in on a second device by email, cancel → access gone within a day; a 100 % code works without a card |
| 4 | ToS, privacy, Stripe Tax, withdrawal checkbox (§5) | 1–2 days | pages live, checkout compliant |
| 5 | Luke caching proxy (§6) | ~2 days | default-settings tiles served from cache |
| — | **Launch** | | by mid-July 2027 |

Phase 1 is worth doing even if Phase 0 fails.

---

## 10. Decisions

Made:

- **Monthly + yearly subscriptions**, off-season discount, limited early-bird codes (§1).
- **Passwordless login by email**, Stripe as the record of who has paid (§4c).
- **Sweden in the paid tier** at launch, labelled as the pilot area (§7).
- **Global basemap provider**, not MML, because of the multi-country plan (§3b).
- **Own company handles VAT**; Stripe Tax for per-country rates (§5).

Still open:

1. **Prices**, and the monthly/yearly ratio. Anchor against what a day's fuel and a wasted drive
   cost, not against app-store prices.
2. **Map provider** — recommended: MapTiler Flex via the Leaflet plugin, after the prototype in §3b.
3. **Domain** — `shroomify.com` or similar, after a name/trademark search (§8).
4. **Early-bird size** — how many codes, how many free months.
