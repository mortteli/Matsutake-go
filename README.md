# 🍄 Matsutake GO

Mobiilikäyttöön tehty karttasovellus, joka näyttää **tuoksuvalmuskan (matsutake,
_Tricholoma matsutake_) potentiaaliset kasvupaikat koko Suomessa** — samaan
tyyliin kuin Mustikka GO ja muut marjakartat.

Värilliset alueet kartalla ovat metsiä, joissa **kaikki** perusehdot täyttyvät
(Luken monilähteisen VMI:n 16 m rasteriaineistosta, inventointi 2019–2023):

| Ehto | Oletus | Aineistotaso |
|---|---|---|
| Kasvupaikka on kuiva kangas, karukkokangas, kalliomaa tai kuivahko kangas | luokat 4–7 | `kasvupaikka_1923` |
| Maapohja on kivennäismaata (ei suota) | luokka 1 | `paatyyppi_1923` |
| Puusto on **vanhaa** | ≥ 60 v (säädettävä 40–120) | `ika_1923` |
| **Mäntyä** on riittävästi | ≥ 20 m³/ha (säädettävä) | `manty_1923` |

**Väri kertoo kuinka vahvasti ehdot täyttyvät.** Kaksi ehdoista on
järjestysasteikollisia, joten kartta ei ole kaksiarvoinen vaan pisteyttää:

| Luokka | Väri | Mitä se tarkoittaa |
|---|---|---|
| 4/4 paras | 🟧 oranssi | ydinkasvupaikka + yli 110 v puusto, 63° N pohjoispuolella |
| 3/4 hyvä | 🟥 punainen | ydinkasvupaikka + yli 85 v, tai reunaluokka + yli 110 v |
| 2/4 kohtalainen | 🟪 magenta | ydinkasvupaikka nuoremmalla puustolla, tai reunaluokka + yli 85 v |
| 1/4 reunatapaus | 🟣 violetti | reunaluokka (kuivahko kangas) + 60–85 v |

Ydinkasvupaikkoja ovat kuiva kangas, karukkokangas ja kalliomaat/hietikot;
reunaluokka on kuivahko kangas. Perustelut ja lähteet: [SOURCES.md](SOURCES.md).
Rinteisyyden voi tarkistaa napauttamalla karttaa (korkeusmalli: Open-Meteo /
Copernicus DEM), mutta sitä **ei pisteytetä** — pohjoismaisessa aineistossa
rinteisyys tai ilmansuunta ei saa tukea.

## Ominaisuudet

- 📍 **GPS-piste** joka seuraa laitteen sijaintia (seuranta katkeaa kun karttaa
  raahaa, palaa päälle napista)
- 🍄 **Matsutake-taso**: neljä WMS-rasterimaskia yhdistetään selaimessa
  canvas-kompositiolla. Kasvupaikka- ja ikämaskit kantavat painon alfakanavassa,
  joten maskien kertolasku antaa suoraan pistemäärän, joka väritetään
  neliportaisella asteikolla. Suodattimet säädettävissä livenä.
- 🔎 **Napauta karttaa** → kokonaisarvio (sama pistemäärä kuin kartalla),
  kasvupaikka, ikä, mäntytilavuus, rinne ja pohjoisuusarvio + navigointilinkki.
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

## Mihin ehdot perustuvat

Kartan suodatinehdot on käyty läpi julkaistua kirjallisuutta vasten
tiedostossa [SOURCES.md](SOURCES.md): mitkä oletusarvot saavat lähdetukea,
mitkä eivät, ja kuinka suuri MVMI-aineiston kuva-alkiotason virhe on
kynnysarvoihin nähden.

## Aineistot ja lisenssit

- Metsävaratiedot: Luonnonvarakeskus (Luke), monilähteisen valtakunnan metsien
  inventoinnin (MVMI) karttatasot 2023, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Korkeustiedot: [Open-Meteo](https://open-meteo.com/) (Copernicus GLO-90 DEM)
- Taustakartat: © OpenStreetMap-tekijät, © OpenTopoMap (CC-BY-SA), © Esri
- Karttakirjasto: [Leaflet](https://leafletjs.com/)

**Vastuuvapaus:** kartta on tilastollinen arvio metsän rakenteesta, ei
sienihavaintoja. Kunnioita luonnonsuojelualueiden sääntöjä ja jokamiehenoikeuksia.
