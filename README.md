# 🍄 Matsutake GO

Mobiilikäyttöön tehty karttasovellus, joka näyttää **sienten potentiaaliset
kasvupaikat koko Suomessa** — samaan tyyliin kuin Mustikka GO ja muut
marjakartat.

Oikean yläkulman napista valitaan, **mitä sientä metsästetään**. Jokaisella
lajilla on oma ekologiaan perustuva suodattimensa, mutta sama kartta, samat
värit ja sama napautustarkastelu.

| Sieni | Mitä kartta etsii | Aineistotasot |
|---|---|---|
| 🍄 **Matsutake** (tuoksuvalmuska, _Tricholoma matsutake_) | kuiva kangas / karukkokangas · kivennäismaa · vanha puusto · mäntyä | `kasvupaikka`, `paatyyppi`, `ika`, `manty` |
| 🌰 **Herkkutatti** (_Boletus edulis_) | tuore / lehtomainen kangas · kivennäismaa · runsaasti kuusta · tiheä latvusto | `kasvupaikka`, `paatyyppi`, `ika`, `kuusi` (tai `manty`), `latvuspeitto` |
| ☂️ **Ukonsieni** (_Macrolepiota procera_) | lehto / lehtomainen kangas · kivennäismaa · puoliavoin, valoisa puusto | `kasvupaikka`, `paatyyppi`, `latvuspeitto`, `lehtip_latvuspeitto` |

Kaikki tasot ovat Luken monilähteisen VMI:n 16 m rasteriaineistoa
(inventointi 2019–2023). Jokaisen lajin rajat ovat säädettävissä livenä
🗺️-napin takaa; asetukset ja valittu laji muistetaan selaimessa.

### Miksi juuri nämä ehdot

- **Matsutake** kasvaa vanhoissa männiköissä kuivilla ja karuilla kankailla.
  Jäkäläisyys korreloi vahvasti karukko-/kuivan kankaan kanssa, joten
  jäkäläkankaat tulevat mukaan kasvupaikkaluokkien kautta.
- **Herkkutatti** on kuusen (myös männyn ja koivun) sienijuurikumppani ja
  suosii tuoreita kankaita, joilla maassa on neulaskariketta ja vain ohut
  sammalpeite. Siksi ehtoina ovat kuusitilavuus *ja* tiheä latvuspeitto —
  parhaat kohdat ovat näiden kuvioiden reunoilla ja polkujen varsilla.
  Suokuviot on rajattu pois.
- **Ukonsieni** on lahottaja, joka viihtyy ravinteisella maalla ruohoisissa
  ja valoisissa paikoissa. Ehtoina ovat lehto/lehtomainen kangas ja
  **puoliavoin latvuspeitto** (10 % … valittu yläraja) — täysin paljas
  hakkuuaukko rajautuu pois. Laji harvinaistuu nopeasti pohjoiseen, joten
  karttaa ei piirretä 66,5° N pohjoispuolelle.

> **Huom:** parhaat ukonsienipaikat — pientareet, hakamaat, pihat ja niityt —
> eivät ole metsävara-aineistossa lainkaan. Kartta antaa suunnan; etsi
> pinkkien kuvioiden reunoja.

## Ominaisuudet

- 🍄 **Lajivalitsin** oikeassa yläkulmassa: pieni modaali, josta laji vaihtuu
  yhdellä napautuksella. Kartan otsikko, selite ja tietosivu vaihtuvat mukana.
- 📍 **GPS-piste** joka seuraa laitteen sijaintia (seuranta katkeaa kun karttaa
  raahaa, palaa päälle napista)
- 🗺️ **Sienitaso**: 3–5 WMS-rasterimaskia yhdistetään selaimessa
  canvas-kompositiolla → näkyviin jäävät vain ruudut, joissa kaikki ehdot
  täyttyvät. Suodattimet säädettävissä livenä.
- 🔎 **Napauta karttaa** → paikan kasvupaikka, maapohja, valitun lajin
  mittarit, rinteen jyrkkyys ja suunta, alue-arvio sekä kokonaisarvio +
  navigointilinkki.
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
Sovellus pyytää jokaiselle karttatiilelle yhden binäärimaskin ehtoa kohden
(esim. `kasvupaikka ∈ {5,6}`, `ikä ≥ 60`, `latvuspeitto 10–40`) ja leikkaa ne
yhteen canvasilla (`destination-in`). Saman ehdon vaihtoehdot — esimerkiksi
"kuusta *tai* mäntyä riittävästi" — yhdistetään ensin unionilla
(`source-over`). Napautustarkastelu hakee saman rajapinnan kautta 3×3 px
kuvan ja lukee pikselin läpinäkyvyydestä, täyttyykö ehto.

Uuden sienen lisääminen on yksi merkintä `SPECIES`-taulukkoon `index.html`:ssä:
laji kuvaa suodattimensa (`conditions`), säätimensä (`controls`), mittarinsa
(`metrics`) ja tekstinsä — käyttöliittymä rakentuu niistä.

## Aineistot ja lisenssit

- Metsävaratiedot: Luonnonvarakeskus (Luke), monilähteisen valtakunnan metsien
  inventoinnin (MVMI) karttatasot 2023, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Korkeustiedot: [Open-Meteo](https://open-meteo.com/) (Copernicus GLO-90 DEM)
- Taustakartat: © OpenStreetMap-tekijät, © OpenTopoMap (CC-BY-SA), © Esri
- Karttakirjasto: [Leaflet](https://leafletjs.com/)

**Vastuuvapaus:** kartta on tilastollinen arvio metsän rakenteesta, ei
sienihavaintoja. Tarkista aina tunnistus itse, kunnioita luonnonsuojelualueiden
sääntöjä ja jokamiehenoikeuksia.
