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
  puuttuvat tekijät ovat hiekkainen/harjumaaperä ja puuston harvuus — niitä
  varten on tekeillä havainnoista opetettu todennäköisyyskartta, ks.
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
- 🔎 **Haku**: paikannimet ja osoitteet (Nominatim / OpenStreetMap) sekä
  koordinaatit joko asteina tai ETRS-TM35FIN-metreinä.
- 📍 **Lähellä sinua**: kun sijainti on sallittu, tyhjä hakukenttä näyttää kolme
  lähintä käymisen arvoista kuviota — ks. alla. Heti kun alat kirjoittaa, lista
  väistyy hakutulosten tieltä.
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

### Mikä on "kuvio" ja milloin se on käymisen arvoinen

**Lähellä sinua** -lista tekee rasterista paikkoja. Se hakee samat maskit kerran
25 km säteeltä (yksi kuva ehtoa kohden, 32 m ruutu — sama tulos kuin 16 m:llä,
neljäsosa datasta), yhdistää ne kuten karttataso, ja etsii yhtenäiset kuviot.
**Kuvio on yksi yhtenäinen sienimetsä:** 8-naapuruudessa kiinni oleva alue,
jossa kaikki lajin ehdot täyttyvät, ja joka läpäisee kaksi kynnystä:

| | | |
|---|---|---|
| **≥ 5 ha** | n. 225 × 225 m | Noin 2 ha tunnissa haravoiden tämä on parin tunnin metsä — retki, ei tienvarsipysähdys. |
| **ydin ≥ 80 m** | löydyttävä piste 40 m:n päästä lähimmästä ei-kelpaavasta ruudusta | Pudottaa hakkuuaukon tai rannan reunaa kiertävän yhden ruudun nauhan, jota kertyy 5 ha mutta joka ei ole missään kohtaa metsää. |

Maski **suljetaan ensin yhdellä ruudulla** (morfologinen sulkeminen). MVMI
luokittaa jokaisen 16 m ruudun erikseen, joten neljän–viiden ehdon leikkaus
hajottaa metsän hauliksi: Tampereen ympäriltä matsutake-maski peittää 0,77 %
maasta mutta hajoaa 11 599 palaseen, joista suurin on 6 ha — ilman sulkemista
lista jäisi lajilla aina tyhjäksi. Kaksi kelpaavaa ruutua 32 m päässä toisistaan
ovat metsässä kulkijalle sama metsä. Pinta-ala lasketaan silti **vain aidosti
kelpaavista ruuduista**, joten hehtaarit eivät kasva umpeen kurotusta maasta.

Kuviot pannaan järjestykseen suhteella `pinta-ala / (1 + km/5)` — hehtaarit
painavat puolet 5 km:n päässä — ja peräkkäisten valintojen välille vaaditaan
2,5 km, jotta kolme ehdotusta ovat kolme eri metsää. Osoitettu piste on kuvion
**syvin ruutu**, ei painopiste: se on varmasti kuvion sisällä ja se on myös se
kohta, jossa kannattaa seistä. Sama valinta tehdään `ml/pick_sites.py`:ssä.

Uuden sienen lisääminen on yksi merkintä `SPECIES`-taulukkoon `index.html`:ssä:
laji kuvaa suodattimensa (`conditions`), hyväksymänsä maapohjat (`mainTypes`),
säätimensä (`controls`), mittarinsa (`metrics`) ja tekstinsä — käyttöliittymä
rakentuu niistä.

## Todennäköisyyskartta (🧠)

🗺️-valikon **Todennäköisyyskartta** on havainnoista opetettu malli
(gradient boosting, LightGBM), joka antaa jokaiselle 16 m ruudulle arvion siitä,
kuinka matsutaken tunnettujen löytöpaikkojen kaltainen se on. Malli yhdistää Luken
metsätiedot, MML:n korkeusmallin (rinne, suunta, harjanne), GTK:n maaperä- ja
harjukartan sekä Ilmatieteen laitoksen lämpösumman.

Säädin *Näytä parhaat X % metsämaasta* valitsee kynnyksen, ja se kannattaa vetää
alas: kartta on tehty luettavaksi kärjestään. Ristiinvalidoituna (25 km alueblokit,
arviointi vain ≤ 250 m tarkkuuden havainnoilla) asetukset tarkoittavat tätä:

| Kartta värittää | Tunnetuista löydöistä mukana | Sienihavaintopaikoista matsutakea | Osuvuus vs. satunnainen metsä |
|---|---|---|---|
| parhaat 0,25 % | 14 % | 72 % | 59× |
| parhaat 0,5 % | 23 % | 66 % | 48× |
| parhaat 1 % | 31 % | 52 % | 31× |
| parhaat 2 % | 41 % | 41 % | 21× |
| parhaat 5 % | 61 % | 30 % | 12× |
| parhaat 15 % | 79 % | 13 % | 5× |

Kolmas sarake on se, joka kertoo kannattaako ajaa: kun kartan värillä olevalta
alueelta on ylipäätään ilmoitettu sieni, kuinka usein se on matsutake. Vanha
sääntökartta ylsi 5 %:n kohdalla 16 %:iin löydöistä.

Kartta kattaa metsämaan parhaan 15 %:n; sen ulkopuolella malli ei piirrä mitään.
Miksi malliperhe on juuri tämä ja mitä vertailu antoi:
[docs/MODEL_CHOICE_matsutake.md](docs/MODEL_CHOICE_matsutake.md). Menetelmä, aineisto
ja tarkkuusluvut: [docs/HABITAT_MODEL_PLAN.md](docs/HABITAT_MODEL_PLAN.md) ja
[docs/MODEL_REPORT_matsutake.md](docs/MODEL_REPORT_matsutake.md); koodi ja
data kansiossa [`ml/`](ml/README.md).

**Retkisuunnittelu.** `ml/pick_sites.py` tekee kartasta lyhyen listan: se rajaa
suojelu- ja puolustusvoimien alueet, rakennusten lähistön ja isojen teiden
päästökäytävät pois, vaatii että paikalle pääsee autolla kävelymatkan päähän, ja
järjestää loput kuviot sen mukaan miten hyvä niiden *huonoin* neljännes on.
Aineisto siihen haetaan OpenStreetMapista (`ml/fetch_osm.py`).

## Aineistot ja lisenssit

- Metsävaratiedot: Luonnonvarakeskus (Luke), monilähteisen valtakunnan metsien
  inventoinnin (MVMI) karttatasot 2023, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Korkeustiedot: [Open-Meteo](https://open-meteo.com/) (Copernicus GLO-90 DEM)
- Suodattimien virittämiseen käytetty havaintoaineisto: [GBIF](https://www.gbif.org/)
  / Suomen Lajitietokeskus (ei osa sovellusta — käytetty vain oletusrajojen tarkistukseen)
- Taustakartat: © OpenStreetMap-tekijät, © OpenTopoMap (CC-BY-SA), © Esri
- Paikkahaku: [Nominatim](https://nominatim.openstreetmap.org/) / OpenStreetMap (ODbL)
- Retkisuunnittelun rajaukset (suojelualueet, rakennukset, tiet): OpenStreetMap (ODbL)
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
