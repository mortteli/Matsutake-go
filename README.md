# 🍄 Matsutake GO

Mobiilikäyttöön tehty karttasovellus, joka näyttää **sienten potentiaaliset
kasvupaikat koko Suomessa** — samaan tyyliin kuin Mustikka GO ja muut
marjakartat.

Oikean yläkulman napista valitaan, **mitä sientä metsästetään**. Jokaisella
lajilla on oma ekologiaan perustuva suodattimensa, mutta sama kartta, samat
värit ja sama napautustarkastelu.

| Sieni | Mitä kartta etsii | Aineistotasot |
|---|---|---|
| 🍄 **Matsutake** (tuoksuvalmuska, _Tricholoma matsutake_) | kuiva / kuivahko kangas / karukkokangas · kivennäismaa · vanha puusto · mäntyä · **vain vähän kuusta** | `kasvupaikka`, `paatyyppi`, `ika`, `manty`, `kuusi` |
| 🌰 **Herkkutatti** (_Boletus edulis_) | tuore / lehtomainen kangas · kivennäismaa · runsaasti kuusta · tiheä latvusto | `kasvupaikka`, `paatyyppi`, `ika`, `kuusi` (tai `manty`), `latvuspeitto` |
| 🌼 **Kanttarelli** (keltavahvero, _Cantharellus cibarius_) | tuore / lehtomainen / kuivahko kangas · kivennäismaa · kuusta, koivua **tai** mäntyä · puolivarjoinen latvusto | `kasvupaikka`, `paatyyppi`, `ika`, `kuusi`/`koivu`/`manty`, `latvuspeitto` |
| 🎺 **Suppilovahvero** (_Craterellus tubaeformis_) | tuore / lehtomainen kangas · kivennäismaa **tai korpi** · runsaasti kuusta · tiheä latvusto · iäkäs puusto | `kasvupaikka`, `paatyyppi`, `ika`, `kuusi`, `latvuspeitto` |
| ☂️ **Ukonsieni** (_Macrolepiota procera_) | lehto / lehtomainen kangas · kivennäismaa · puoliavoin, valoisa puusto | `kasvupaikka`, `paatyyppi`, `latvuspeitto`, `lehtip_latvuspeitto` |

Kaikki tasot ovat Luken monilähteisen VMI:n 16 m rasteriaineistoa
(inventointi 2019–2023). Jokaisen lajin rajat ovat säädettävissä livenä
🗺️-napin takaa; asetukset ja valittu laji muistetaan selaimessa.

### Miksi juuri nämä ehdot

- **Matsutake** kasvaa vanhoissa männiköissä kuivilla ja karuilla kankailla.
  Jäkäläisyys korreloi vahvasti karukko-/kuivan kankaan kanssa, joten
  jäkäläkankaat tulevat mukaan kasvupaikkaluokkien kautta. Luken
  kasvupaikkateema luokittaa kuitenkin puolet tunnetuista kasvupaikoista
  *kuivahkoksi* kankaaksi ja vain joka kahdeksannen *kuivaksi*, joten kuivahko
  on oletuksena mukana. Lisäksi vaaditaan **vähäkuusisuus** (kuusta ≤ 20 m³/ha):
  laji karttaa kuusikoita selvästi. Havaintoaineiston perusteella tärkeimmät
  puuttuvat tekijät ovat hiekkainen/harjumaaperä ja puuston harvuus — ne ovat
  mukana havainnoista opetetussa todennäköisyyskartassa (🧠), ks.
  [Todennäköisyyskartta](#todennäköisyyskartta-) ja
  [docs/HABITAT_MODEL_PLAN.md](docs/HABITAT_MODEL_PLAN.md).
- **Herkkutatti** on kuusen (myös männyn ja koivun) sienijuurikumppani ja
  suosii tuoreita kankaita, joilla maassa on neulaskariketta ja vain ohut
  sammalpeite. Siksi ehtoina ovat kuusitilavuus *ja* tiheä latvuspeitto —
  parhaat kohdat ovat näiden kuvioiden reunoilla ja polkujen varsilla.
  Suokuviot on rajattu pois.
- **Kanttarelli** on kuusen, koivun ja männyn sienijuurikumppani ja viihtyy
  kosteahkoilla sammalpohjaisilla tuoreilla kankailla, myös kuivahkoilla.
  Isäntäpuuehto on unioni — **kuusta, koivua tai mäntyä** riittävästi — ja
  latvuspeitto pidetään puolivarjoisana, jotta sammal ei kuivu. Laji on
  yleislaji, joten sen kartta on väljin: ks. alla oleva viritysosio.
- **Suppilovahvero** on ainoa laji, joka **hyväksyy suokuviot**: korpi on sen
  tyypillistä maastoa. Ehtoina ovat kostea kuusivaltainen kangas tai korpi,
  tiheä latvuspeitto ja iäkäs puusto (lahopuuta maassa). Kartta ei näe pieniä
  notkoja, joten kulje pinkkien kuvioiden sisällä alaspäin.
- **Ukonsieni** on lahottaja, joka viihtyy ravinteisella maalla ruohoisissa
  ja valoisissa paikoissa. Ehtoina ovat lehto/lehtomainen kangas ja
  **puoliavoin latvuspeitto** (10 % … valittu yläraja) — täysin paljas
  hakkuuaukko rajautuu pois. Laji harvinaistuu nopeasti pohjoiseen, joten
  karttaa ei piirretä 66,5° N pohjoispuolelle.

### Mistä oletusrajat tulevat

Uusien lajien oletusrajat on valittu havaintoaineistoa vasten, ei pelkän
silmämäärän perusteella. Kummallekin lajille poimittiin GBIF:stä 45
suomalaista havaintoa (paikannustarkkuus ≤ 100 m, 2010–2026) ja verrokiksi
yhtä monta satunnaispistettä 2–5 km päästä samoilta seuduilta; molemmista
luettiin samat MVMI-tasot, joita kartta käyttää.

| Laji | Havainnoista suodattimen läpi | Verrokkipisteistä | Suhde |
|---|---|---|---|
| 🍄 Matsutake, vanhat oletukset (kuiva kangas) | 9 % | 0 % | — |
| 🍄 Matsutake, uudet oletukset (kuivahko mukana, vähän kuusta) | 48 % | 7 % | 7× |
| 🌼 Kanttarelli | 72 % | 11 % | 6,5× |
| 🎺 Suppilovahvero | 51 % | 9 % | 5,8× |
| 🌰 Herkkutatti (vertailukohta, ennallaan) | 19 % | 2 % | 8,3× |

Matsutaken luvut perustuvat 104 GBIF-havaintoon (tarkkuus ≤ 250 m) ja 300
satunnaiseen metsäpisteeseen, jotka luettiin suoraan Luken MVMI-rastereista
(ks. `docs/HABITAT_MODEL_PLAN.md`). Vanha "kuiva kangas" -oletus hukkasi yli
90 % tunnetuista löytöpaikoista.

Kanttarellin ehtoja kiristämällä kartta kyllä pienenee, mutta osuvuus suhteessa
verrokkiin romahtaa (6,5× → 3,5×): laji ei yksinkertaisesti ole kovin tarkka
kasvupaikastaan, joten oletukset on jätetty väljiksi ja loput jätetty
säätimille. Suppilovahverolla puuston ikä sen sijaan erottelee aidosti, joten
oletusikä on 60 v — se puolittaa värjätyn pinta-alan osuvuuden kärsimättä.

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
- 🧠 **Todennäköisyyskartta**: havainnoista opetettu neuroverkko 16 m ruuduilla,
  luettuna suoraan staattisista Cloud-Optimised GeoTIFF -tiedostoista. Säädin
  valitsee, kuinka suuri osa metsämaasta väritetään.
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
python3 serve.py 8000
# avaa http://localhost:8000
```

> Käytä `serve.py`:tä, älä `python3 -m http.server`:iä: todennäköisyyskartta luetaan
> GeoTIFF-tiedostoista HTTP range -pyynnöillä, joita Pythonin oletuspalvelin ei tue —
> silloin mallitaso jää tyhjäksi. GitHub Pages tukee range-pyyntöjä.

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
laji kuvaa suodattimensa (`conditions`), hyväksymänsä maapohjat (`mainTypes`),
säätimensä (`controls`), mittarinsa (`metrics`) ja tekstinsä — käyttöliittymä
rakentuu niistä.

## Todennäköisyyskartta (🧠)

🗺️-valikon **Todennäköisyyskartta** on havainnoista opetettu neuroverkko, joka
antaa jokaiselle 16 m ruudulle arvion siitä, kuinka matsutaken tunnettujen
löytöpaikkojen kaltainen se on. Ristiinvalidoituna (25 km alueblokit, arviointi
vain ≤ 250 m tarkkuuden havainnoilla) kartta sisältää **66 % tunnetuista
löydöistä metsämaan parhaassa 5 %:ssa** ja 80 % parhaassa 10 %:ssa; vanha
sääntökartta ylsi 16 %:iin. Säädin *Näytä parhaat X % metsämaasta* valitsee
kynnyksen: pienempi prosentti = tiukempi kartta. Kartta kattaa metsämaan
parhaan 25 %:n; sen ulkopuolella malli ei piirrä mitään.

### Mikä malli kartalla on

Julkaistu kartta on **viiden MLP-verkon ensemble**: sama arkkitehtuuri
(1 piilokerros, 32 neuronia, dropout 0,4, weight decay 0,01, lr 0,003) opetettuna
ristiinvalidoinnin viiteen lohkojakoon, ja ennuste on niiden sigmoidien
keskiarvo (`ml/models/matsutake/mlp_fold0..4.pt`, ajo `ml/predict.py`).
Hyperparametrit on valittu sisäkkäisellä ristiinvalidoinnilla, ei silmämääräisesti.

- **Piirteet (62 kpl):** MVMI:n puusto- ja kasvupaikkatiedot, niiden 3×3 ja 9×9
  naapurustokeskiarvot, MML:n 10 m korkeusmallista rinne, suunta, TPI ja
  reliefi, GTK:n maaperä- ja jäätikkömuodostumaluokat (myös osuuksina
  naapurustossa) sekä Ilmatieteen laitoksen lämpösumma ja sademäärä.
- **Opetusaineisto:** 250 havaintoa — 109 tarkkaa (≤ 250 m) ja 141 karkeampaa
  (250 m – 1 km), jotka opettavat painolla 0,3 piirteet epävarmuusympyrän yli
  keskiarvoistettuina eivätkä koskaan ole arvioinnissa mukana — vasten 3000
  satunnaista metsämaapistettä ja 2587 muun sienen havaintopaikkaa.
  Jälkimmäinen tausta on havainnointiharhan korjaus: se kertoo, missä ihmiset
  ylipäätään käyvät etsimässä.
- **Miksi juuri MLP:** samoilla lohkoilla ajettiin myös MaxEnt, GAM,
  ridge-logit, LightGBM ja XGBoost. Erot ovat pieniä (AUC 0,87–0,89), mutta
  MLP ja MaxEnt ovat parhaat sillä mittarilla, joka tässä ratkaisee: osumat
  metsämaan parhaassa 5 %:ssa (0,66). Rank-keskiarvoistettu `mlp+lgbm+maxent`
  on aavistuksen tarkempi (AUC 0,894 vs. 0,881), mutta kartalle päätyi pelkkä
  verkko — `predict.py` ajaa vain verkon painot, joten ensemble vaatisi myös
  puumallien ajamisen koko Suomen yli.
- **Mikä aineisto ratkaisee:** ablaatioissa maaperä on tärkein lisäaineisto
  (PR-AUC 0,37 → 0,25 ilman sitä), naapurustopiirteet toiseksi tärkein
  (0,30); ilmastomuuttujien poisto ei muuta tulosta käytännössä lainkaan.
  Karkeat havainnot kannattaa pitää mukana: ilman niitä verkon osuvuus
  metsämaan parhaassa 5 %:ssa putoaa 0,66 → 0,57.

### Julkaistut tiedostot

`data/matsutake/` sisältää yhdeksän Cloud-Optimised GeoTIFF -palaa (yhteensä
466 MB, EPSG:3067, 16 m). Pikselin arvo on mallin pistemäärä × 100 ja 255
tarkoittaa "ei metsävaratietoa". Metsämaan parhaan 25 %:n ulkopuolelle jäävät
ruudut on tallennettu nollana ja loput kvantisoitu kahden välein, mikä
puolittaa tiedostokoon ilman näkyvää eroa kartalla. `prob_meta.json` kertoo
palojen rajat, pistemäärien kvantiilit ja mallin tarkkuusluvut; selain lataa
HTTP range -pyynnöillä vain näkyvän alueen.

> **Selaintuki:** mallitaso vaatii uudehkon selaimen (Chrome/Edge 73+,
> Safari 12.1+, Firefox 63+): GeoTIFF-kirjastot käyttävät ES2019-syntaksia ja
> mm. `Object.fromEntries`-funktiota. Vanhemmissa selaimissa — esimerkiksi
> autojen sisäänrakennetuissa — sovellus ja sääntötasot toimivat normaalisti,
> mutta mallitaso jää piirtymättä ja näyttää ilmoituksen
> "Todennäköisyyskarttaa ei voitu ladata".

Menetelmä, aineisto ja tarkkuusluvut: [docs/HABITAT_MODEL_PLAN.md](docs/HABITAT_MODEL_PLAN.md) ja
[docs/MODEL_REPORT_matsutake.md](docs/MODEL_REPORT_matsutake.md); koodi ja
data kansiossa [`ml/`](ml/README.md).

## Aineistot ja lisenssit

- Metsävaratiedot: Luonnonvarakeskus (Luke), monilähteisen valtakunnan metsien
  inventoinnin (MVMI) karttatasot 2023, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Korkeustiedot: [Open-Meteo](https://open-meteo.com/) (Copernicus GLO-90 DEM)
- Suodattimien virittämiseen käytetty havaintoaineisto: [GBIF](https://www.gbif.org/)
  / Suomen Lajitietokeskus (ei osa sovellusta — käytetty vain oletusrajojen tarkistukseen)
- Taustakartat: © OpenStreetMap-tekijät, © OpenTopoMap (CC-BY-SA), © Esri
- Karttakirjasto: [Leaflet](https://leafletjs.com/)

- Havaintoaineisto mallin opetukseen: GBIF ja Suomen Lajitietokeskus (FinBIF) —
  tietuekohtaiset lisenssit (CC0 / CC BY / CC BY-NC) on kirjattu
  `ml/data/matsutake/observations.csv`-tiedostoon; kaikki oikeudet pidättävät ja
  share-alike-tietueet on jätetty pois. Koko erittely: [DATA_LICENSES.md](DATA_LICENSES.md).
- Maaperä: Geologian tutkimuskeskus (GTK), Maaperä 1:200 000 ja jäätikkösyntyiset
  muodostumat, CC BY 4.0. Korkeusmalli 10 m: Maanmittauslaitos, CC BY 4.0.
  Ilmastonormaalit: Ilmatieteen laitos, CC BY 4.0.
- Johdettu todennäköisyyskartta ja mallin painot: CC BY-NC 4.0 (opetusaineistossa
  on CC BY-NC-tietueita).
- Sovelluksen koodi: [MIT](LICENSE). Kirjastot: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

**Vastuuvapaus:** kartta on tilastollinen arvio metsän rakenteesta, ei
sienihavaintoja. Tarkista aina tunnistus itse, kunnioita luonnonsuojelualueiden
sääntöjä ja jokamiehenoikeuksia.
