# 🍄 Matsutake GO

Mobiilikäyttöön tehty karttasovellus, joka näyttää **tuoksuvalmuskan (matsutake,
_Tricholoma matsutake_) potentiaaliset kasvupaikat koko Suomessa** — samaan
tyyliin kuin Mustikka GO ja muut marjakartat.

Pinkit alueet kartalla ovat metsiä, joissa **kaikki** ehdot täyttyvät
(Luken monilähteisen VMI:n 16 m rasteriaineistosta, inventointi 2019–2023):

| Ehto | Oletus | Aineistotaso |
|---|---|---|
| Kasvupaikka on **kuiva kangas** (lisäksi valittavissa karukko- ja kuivahko kangas) | luokka 5 (+6) | `kasvupaikka_1923` |
| Maapohja on kivennäismaata (ei suota) | luokka 1 | `paatyyppi_1923` |
| Puusto on **vanhaa** | ≥ 60 v (säädettävä 40–120) | `ika_1923` |
| **Mäntyä** on riittävästi | ≥ 20 m³/ha (säädettävä) | `manty_1923` |

Jäkäläisyys korreloi vahvasti karukko-/kuivan kankaan kanssa, joten
jäkäläkankaat tulevat mukaan kasvupaikkaluokkien kautta. Rinteisyyden voi
tarkistaa paikkakohtaisesti napauttamalla karttaa (korkeusmalli: Open-Meteo /
Copernicus DEM) tai silmäilemällä Maasto-taustakartan korkeuskäyriä.

## Ominaisuudet

- 📍 **GPS-piste** joka seuraa laitteen sijaintia (seuranta katkeaa kun karttaa
  raahaa, palaa päälle napista)
- 🍄 **Matsutake-taso**: neljä WMS-rasterimaskia yhdistetään selaimessa
  canvas-kompositiolla → näkyviin jäävät vain ruudut, joissa kaikki ehdot
  täyttyvät. Suodattimet (ikä, mäntymäärä, kasvupaikkaluokat) säädettävissä
  livenä.
- 🔎 **Napauta karttaa** → paikan kasvupaikka, ikä, mäntytilavuus, rinteen
  jyrkkyys ja suunta, pohjoisuusarvio sekä kokonaisarvio + navigointilinkki.
- 🗺️ Taustakartat: OpenStreetMap, OpenTopoMap (korkeuskäyrät) ja Esri-satelliitti.
- 📲 PWA-manifesti → "Lisää aloitusnäytölle" toimii sovelluksen tavoin.

## Käyttöönotto

Sovellus on yksi staattinen sivu — ei buildia, ei backendia.

**GitHub Pages:** repon asetuksista *Settings → Pages → Deploy from a branch*,
valitse branch ja `/ (root)`. Sovellus aukeaa osoitteessa
`https://<käyttäjä>.github.io/Matsutake-go/`.

> HUOM: GPS vaatii HTTPS-yhteyden (GitHub Pages kelpaa) ja luvan selaimelta.

**Paikallisesti:**

```bash
python3 -m http.server 8000
# avaa http://localhost:8000
```

## Miten se toimii

Luken GeoServer (`kartta.luke.fi/geoserver/MVMI/wms`, CORS auki) tukee
`SLD_BODY`-parametria, jolla rasterin voi uudelleenvärittää pyynnössä.
Sovellus pyytää jokaiselle karttatiilelle neljä binäärimaskia
(esim. `kasvupaikka ∈ {5,6}`, `ikä ≥ 60`) ja leikkaa ne yhteen canvasilla
(`destination-in`). Napautustarkastelu hakee saman rajapinnan kautta 3×3 px
kuvan, jossa rasterin raaka-arvo on koodattu harmaasävyksi (`ramp 0→255`),
ja lukee arvon pikselistä.

## Aineistot ja lisenssit

- Metsävaratiedot: Luonnonvarakeskus (Luke), monilähteisen valtakunnan metsien
  inventoinnin (MVMI) karttatasot 2023, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Korkeustiedot: [Open-Meteo](https://open-meteo.com/) (Copernicus GLO-90 DEM)
- Taustakartat: © OpenStreetMap-tekijät, © OpenTopoMap (CC-BY-SA), © Esri
- Karttakirjasto: [Leaflet](https://leafletjs.com/)

**Vastuuvapaus:** kartta on tilastollinen arvio metsän rakenteesta, ei
sienihavaintoja. Kunnioita luonnonsuojelualueiden sääntöjä ja jokamiehenoikeuksia.
