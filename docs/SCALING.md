# Scaling review: 10, 100, 1000 concurrent users

What this app would need to serve 10, 100 and 1000 people at once, what breaks first, and what a
paywall would require. Written against the code as it stands, alongside
[DATA_PIPELINE_REVIEW.md](DATA_PIPELINE_REVIEW.md), which fixed the *per-session* request storms;
this document is about the *per-user* multiplication that those fixes do not address.

> **What is measured and what is not.** Luke's concurrency header was read live on 2026-09-17.
> Repository and raster sizes, and every licence count in §5, were computed from the files in this
> repo. The per-session Luke request count is the measurement already recorded in
> DATA_PIPELINE_REVIEW.md. **Per-session bandwidth, and therefore every monthly total derived from
> it, is an estimate, not a measurement** — the real figure depends on how far a user pans and is
> worth measuring in devtools before anyone signs a hosting contract. Third-party pricing and
> GitHub's published limits are from documentation, not from an invoice; re-check both before
> committing.

---

## 1. The structural fact

The app has two data paths, and only one of them scales.

| Path | What | Per-user cost | Shared between users? |
|---|---|---|---|
| **Baked** | `prob_*.tif`, `cut_*.tif` range reads off static hosting | bandwidth only | ✅ CDN-cacheable |
| **Live** | Luke WMS, Metsäkeskus WFS, Nominatim, Open-Meteo | ~269 requests per short session | ❌ nothing shared |

Every viewer re-asks Luke's GeoServer the identical question. User #1000 panning over Tampere
triggers the same five `GetMap` calls user #1 just made a second earlier. Nothing is amortised, and
no amount of client-side queueing changes that — `lukeGate` bounds what *one browser* opens, which
is exactly the right thing for one user and no help at all for a thousand.

DATA_PIPELINE_REVIEW.md brought a session from 435 requests to 269 and peak concurrency from 153 to
5. That work stands. But 269 × 1000 users is still 269 000 requests, and the fix for *that* is not a
smaller number per session — it is not sending the request at all.

---

## 2. Luke is the first bottleneck, and it arrives before you expect

The header is live and still exactly what `index.html:550` says it is:

```
x-concurrent-limit-user: 6
x-concurrent-requests-user: 1
x-control-flow-delay-ms: 0
```

Two distinct problems.

### 2a. Aggregate throughput

269 Luke requests for a load, four pans and one tap. A real five-minute session with a few taps is
400–800. At 1000 concurrent users that is on the order of **1000 req/s sustained** against one
public GeoServer, which is provisioned for agency and research use rather than for being a
consumer app's tile backend. Somewhere around **100 concurrent** this app becomes that instance's
largest single consumer, and the consequence at that point is a conversation with Luke, not an
HTTP 429.

This is a courtesy and continuity problem more than a legal one. The MVMI data is CC BY 4.0 and
commercial use is fine (§5). Serving it from *their* hardware, per user, forever, is the part that
does not scale — and it is not a dependency worth building a paid product on regardless of whether
anyone objects.

### 2b. `limit-user: 6` is per IP, and Finnish carriers use CGNAT

This is the one that bites quietly, and it is worth one test to confirm.

The limit is almost certainly keyed on IP — the service is unauthenticated, so there is nothing
else to key on. Finnish mobile operators put many subscribers behind a shared public address
(CGNAT). This app is mobile-first. So a few dozen users on one carrier egress IP **collectively**
get 6 slots, while each browser independently keeps 5 in flight (`LUKE_PAR = 5`, `index.html:552`).
The app's core assumption — that its budget is its own — stops holding.

*Confirming it:* two clients behind one NAT, both panning, watching
`x-concurrent-requests-user` climb past one client's share. Until someone does that, treat this
section as reasoned rather than established.

### 2c. What starvation does to correctness

When Luke throttles, the failure is silent and lands in the result sheet. `index.html:1787-1792`:

```js
const probeValues = (layer, values, ll) =>
  probe(layer, maskValues(layer, values), ll).catch(() => null);
```

`readClass` (`index.html:1795`) then returns `null` from `indexOf(true) === -1`, and a throttled
probe is indistinguishable from a forest that genuinely fails the condition. The tap sheet says
*this is not a matsutake spot* with the same confidence either way.

DATA_PIPELINE_REVIEW.md called this "a correctness bug wearing a performance costume". The
concurrency half was fixed; this half was not, and it is precisely the half that only manifests
under load — the worst possible property for a bug to have. **Fix it before there is load, not
after**: distinguish "probe failed" from "condition not met", and let the sheet say so.

---

## 3. Metsäkeskus: widely used, but not this way

`avoin.metsakeskus.fi` is the national open forest data service, CC BY 4.0, and it is in genuinely
broad use — forest management associations, wood procurement at the large forest companies,
planning software, municipalities. Nothing about depending on it is exotic.

But note *how* the heavy consumers use it: the **bulk province GeoPackage downloads**, which is
exactly what `ml/fetch_harvests.py` already does. The WFS is the interactive front door, sized for
someone inspecting a few stands, not for continuous per-user streaming.

At 1.47 MB per 10 km `stand` cell (`MK_KIND`, `index.html:617`), 1000 users crossing into new
cells is hundreds of MB/s of egress off their server. That is not fair use under any reading.

**The good news: the correct pattern is already implemented here.** `cut_*.tif` is baked from the
bulk route and read as the model raster's second band. The live WFS is a freshness refinement on top
of a baked layer that already works. For a scaled deployment, that refinement becomes opt-in:

- Drop the live WFS from the tile path entirely (`MK_MINZOOM` gating stops mattering when there are
  no requests to gate).
- Keep `mkAt` on **tap only** — two small point queries per tap is fair use indefinitely, and it
  preserves the "live data wins, baked layer is announced as stale" behaviour the README documents.
- Re-run `fetch_harvests.py` monthly in CI so the baked layer does not drift.

---

## 4. Verdict per tier

### 10 concurrent — works today

~30 req/s peak to Luke, a handful of WFS cells, GitHub Pages bandwidth nowhere near its limit.
Nothing to do. Ship it.

### 100 concurrent — a caching proxy, roughly a weekend

The cheap 80 % fix. Put a CDN of your own in front of `kartta.luke.fi`. `SLD_BODY` travels in the
GET query string (`index.html:507`), so every mask URL is deterministic and cacheable.

The leverage comes from defaults: most users never touch the sliders, so **100 users on default
settings collapse to ~1 origin fetch per (tile, layer)**. Cache hit rate degrades for users who
tune, but tuned requests are a small minority of total traffic. The same proxy fronts the WFS cell
fetches.

This also resolves §2b: Luke sees one well-behaved client instead of an IP-sharing crowd.

GitHub Pages is finished at this tier — see §6.

### 1000 concurrent — the live path has to go

Not a caching tweak; an architecture change. Three moves, in order of payoff:

**1. Bake the raw MVMI bands, composite in the browser.** The important one. Instead of five
`GetMap` per tile per user, ship the eight layers in `LAYER` (`index.html:397-406`) as quantised
single-byte tiles or COGs, and perform the threshold AND in JS where the canvas composite already
happens.

The live sliders are the *only* reason the masks are server-side today. Moving the comparison
client-side keeps them working exactly as they are, serves all five species from one dataset, and
removes Luke from the request path entirely. Expect ~2–3 GB for Finland at 16 m (the single-band
`prob` set is 366 MB with aggressive quantisation) — irrelevant on object storage, and irrelevant
in transfer when served as tiles, since a user only ever fetches what is on screen.

**2. Drop the live WFS** per §3.

**3. Publish `data/terrain/`.** `ml/export_terrain.py` and the app-side reader (`readSlope`,
`readBlockAt`) both already exist. One pipeline run deletes the Open-Meteo dependency and closes the
last gap in "works offline once cached". Cheapest item on this list by a wide margin.

After those three, 1000 concurrent is **purely a bandwidth-and-CDN problem** — the easiest kind of
scaling there is, because what remains is a static SPA with no server-side state at all.

---

## 5. The paywall blocker that is not infrastructure

This is the finding that matters most, and it is a licence question rather than a capacity one.

From [DATA_LICENSES.md](../DATA_LICENSES.md):

> `data/matsutake/prob_*.tif`, `prob_meta.json` — **CC BY-NC 4.0** … non-commercial because
> CC BY-NC observation records contributed to training

**The model layer — the part people would pay for — is currently licensed non-commercially.** A
paywall is commercial use. DATA_LICENSES.md already states the remedy:

> To publish the derived layers under plain CC BY 4.0, re-run the pipeline with the CC BY-NC
> records removed (`ml/fetch_observations.py` — filter on the `license` column).

### What the "NC filter" actually means

There is already a licence filter in the pipeline, and it is **not** the one needed here.
`redistributable()` (`ml/fetch_observations.py:81`) asks *may this record live in a public
repository*:

```python
def redistributable(lic):
    """Records we may keep in a public repository: CC0 / CC BY / CC BY-NC. All-rights-reserved and
    share-alike records are dropped entirely (not used for training either)."""
    l = (lic or "").upper()
    return not ("ARR" in l or "-SA" in l or "SA-4" in l)
```

It drops all-rights-reserved and share-alike, and **deliberately keeps CC BY-NC** — because
redistributing an NC record in a public repo is fine. Commercial *use* is the separate question,
and nothing in the pipeline asks it today.

The NC filter is therefore a second, stricter predicate — roughly `"NC" not in license.upper()` —
applied for a commercial build. Two records' `license` fields spell it differently, so match on the
substring rather than on exact URLs:

```
http://creativecommons.org/licenses/by-nc/4.0/legalcode     (GBIF)
http://tun.fi/MZ.intellectualRightsCC-BY-NC-4.0             (FinBIF)
```

### What it costs — measured, not estimated

The raw fetch files hold 49 NC presences and 784 NC background records, but most of those never
reach training: `build_dataset.py` drops anything with coordinate uncertainty over 1000 m first. The
figures that matter are the ones that survive into `dataset.csv`:

| | now | after NC filter | change |
|---|---|---|---|
| **Fine presences** (unc ≤ 250 m, weight 1.0) — the `n_presence` in `prob_meta.json` | **109** | **99** | **−10 (−9.2 %)** |
| All presence rows (incl. coarse, weight 0.3) | 250 | 239 | −11 |
| Presence effective weight | 151.3 | 141.0 | −6.8 % |
| Target-group background (`bg_fungi`) | 2 587 | 2 003 | **−584 (−22.6 %)** |
| Random background (`bg_random`) | 3 000 | 3 000 | unchanged |

So the real cost is **9 % of the presences and 23 % of the target-group background** — materially
smaller than the raw 49/445 suggests, and plausibly survivable. The background loss is the larger
proportion, but background is the more replaceable half: it can be topped up by widening the
`bg_fungi` query, which the presences cannot.

### The measurement to run first

Re-run the pipeline with the NC predicate applied and compare against this baseline, from
`ml/models/matsutake/report.json` (the shipped head is `lgbm`, per `prob_meta.json`):

| head | auc_vs_fungi | prauc_vs_fungi | recall@5 | boyce |
|---|---|---|---|---|
| **lgbm (shipped)** | **0.880** | **0.401** | **0.615** | **0.911** |
| maxent | 0.889 | 0.419 | 0.661 | 0.908 |
| mlp | 0.883 | 0.345 | 0.670 | 0.812 |
| rule_new_default (for scale) | 0.741 | 0.129 | 0.394 | 0.506 |

With 99 presences the cross-validated numbers will be noisy; judge on the fold spread in
`oof_scores.csv`, not on a single decimal place of AUC. The bar is not "identical" but "still far
enough above `rule_new_default` to be worth charging for" — the model's whole claim is that it
beats the rule layer, and that gap (0.880 vs 0.741 AUC, 0.401 vs 0.129 PR-AUC) is wide enough to
absorb some loss.

**Run this before any infrastructure work.** If the CC BY-only model holds up, the paywall is clean
and everything else in this document is plumbing. If it does not, that changes the product, and no
amount of hosting decisions will fix it.

### Three smaller commercial-use blockers

| Dependency | Problem | Fix |
|---|---|---|
| `tile.openstreetmap.org` (`index.html:1306`) | tile policy is modest, non-commercial use | **MML Maastokartta** — free API key, CC BY 4.0, Finland-only, and better cartography for this use case anyway |
| `server.arcgisonline.com` (`index.html:1310`) | keyless Esri REST endpoint, not licensed for this | MML orthophotos, or a paid provider |
| `nominatim.openstreetmap.org` (`index.html:2100, 2537`) | absolute max 1 req/s *app-wide*, no heavy or commercial use | MML geocoding API, or self-hosted Photon (the Finland extract is small) |

Luke MVMI and Metsäkeskus are **CC BY 4.0 — commercial use is permitted** with attribution, which
the app already does correctly (`index.html:1307-1311`). Legally those two are the safest inputs
here. The constraints come from the volunteer-funded infrastructure (OSM, Nominatim) and from the
NC observation records.

---

## 6. GitHub Pages: already at 40 % of the hard limit

```
data/     413 MB      ← GitHub Pages hard limit is 1 GB published site
.git      937 MB
vendor/   1.3 MB      (~1.2 MB JS, ~350 KB gzipped)
index.html 148 KB
```

- `prob_matsutake_16m_21.tif` is 71 MB — under git's 100 MB per-file wall, but not comfortably.
- Publishing `data/terrain/` plus models for the other four species exceeds 1 GB.
- **Bandwidth is the real ceiling.** A session is *estimated* at 3–8 MB (vendor bundle on first
  visit, then COG range reads plus 18 file headers). Against GitHub's 100 GB/month soft cap that is
  roughly **20 000 sessions/month, total**. 1000 concurrent users is on the order of 4M
  sessions/month, or **~20 TB** — over by a factor of ~200.

**And the decisive one: this repository is public and `data/` is in its git history.** A paywall in
front of a public repo is decoration. Moving `data/` to object storage (or a private repo) is step
one of charging anything, and the 937 MB `.git` already carries that history regardless.

GitHub Pages is the right host for a free hobby app at tier 1. It is the wrong host the moment
there is a price.

---

## 7. Hosting: no, Azure is not needed

It stays a web app. Nothing here needs a server or any stateful component.

```
Cloudflare R2        baked tiles + COGs          ← zero egress fees
Cloudflare Worker    JWT check + signed URLs     ← the paywall
Stripe               subscriptions
GitHub Actions       scheduled ml/ pipeline bake
```

Egress dominates the cost of a raster product, and providers differ by orders of magnitude. At the
~20 TB/month that 1000 concurrent implies (an estimate — see the status note):

| | storage | egress | ~monthly |
|---|---|---|---|
| **Cloudflare R2** | ~€0.02/GB | **€0** | **< €10** |
| Azure Blob / S3 | ~€0.02/GB | ~€0.08–0.09/GB | **€1 600–1 800** |

That is not a tuning difference; it is the difference between a viable side project and a bill.
Azure earns a place only if there is already an Azure organisation, a specific EU data-residency
contract, or a GPU retraining need — and even then it would be Azure for the pipeline and R2 for
delivery.

The full bake is also infrequent: MVMI publishes on a multi-year cycle (`CYCLE = "1923"`,
`index.html:391`), so the heavy pipeline run is quarterly at most. GitHub Actions can carry it,
though the 413 MB output against a 14 GB runner is tight enough to check before relying on it; a
spot VM for a few hours is the fallback.

### Paywalling static range-read COGs

The URL cannot be the secret, so use short-lived signed cookies validated at the edge. This works
with `georaster-layer` — it reads through fetch/XHR, so it needs `credentials: 'include'` and
matching CORS on the bucket. Roughly 1 ms of overhead and no architectural change.

---

## 8. Recommended order

1. **Re-run the pipeline with the NC filter and compare `oof_scores.csv` against §5's baseline.**
   Cheap, and it gates whether a paywall is possible at all. Everything below is wasted effort if
   this fails.
2. **Publish `data/terrain/`.** Both sides of the code already exist; one run removes an external
   dependency outright.
3. **Fix the silent probe failure** (`index.html:1787-1792`, §2c) — distinguish a failed probe from
   a failed condition. Do this before there is load.
4. **Swap OSM / Esri / Nominatim → MML.** Better maps for Finland, and it clears three licence
   problems at once.
5. **Move `data/` to R2 behind a Worker.** Lifts the Pages ceiling and makes a real paywall
   possible.
6. **Caching proxy in front of Luke.** Buys 100 concurrent for about a weekend of work.
7. **Bake the MVMI bands, composite client-side.** The large one, needed only for the 1000-user
   tier.

Items 1–3 are worth doing whether or not anyone is ever charged.
