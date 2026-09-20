# 🍄 Matsutake GO

Mobiilikäyttöön tehty karttasovellus, joka näyttää **sienten potentiaaliset
kasvupaikat koko Suomessa** — samaan tyyliin kuin Mustikka GO ja muut
marjakartat.

Oikean yläkulman napista valitaan, **mitä sientä metsästetään**. Jokaisella
lajilla on oma ekologiaan perustuva suodattimensa, mutta sama kartta, samat
värit ja sama napautustarkastelu.

| Sieni | Mitä kartta etsii | Aineistotasot |
|---|---|---|
| 🍄 **Matsutake** (tuoksuvalmuska, _Tricholoma matsutake_) | kuiva / kuivahko kangas / karukkokangas · kivennäismaa · vanha puusto · mäntyä · **vain vähän kuusta** · harva, valoisa latvusto | `kasvupaikka`, `paatyyppi`, `ika`, `manty`, `kuusi`, `latvuspeitto` |
| 🌰 **Herkkutatti** (_Boletus edulis_) | tuore / lehtomainen kangas · kivennäismaa · runsaasti kuusta · tiheä latvusto | `kasvupaikka`, `paatyyppi`, `ika`, `kuusi` (tai `manty`), `latvuspeitto` |
| 🌼 **Kanttarelli** (keltavahvero, _Cantharellus cibarius_) | tuore / lehtomainen / kuivahko kangas · kivennäismaa · **runsaspuustoinen** (≥ 150 m³/ha) · puolivarjoinen latvusto · valinnaisesti vain kuusivaltaiset | `kasvupaikka`, `paatyyppi`, `ika`, `tilavuus`, `latvuspeitto`, (`kuusi`) |
| 🎺 **Suppilovahvero** (_Craterellus tubaeformis_) | tuore / lehtomainen kangas · kivennäismaa **tai korpi** · runsaasti kuusta · tiheä latvusto · iäkäs puusto | `kasvupaikka`, `paatyyppi`, `ika`, `kuusi`, `latvuspeitto` |
| ☂️ **Ukonsieni** (_Macrolepiota procera_) | lehto / lehtomainen kangas · kivennäismaa · puoliavoin, valoisa puusto | `kasvupaikka`, `paatyyppi`, `latvuspeitto`, `lehtip_latvuspeitto` |

Kaikki tasot ovat Luken monilähteisen VMI:n 16 m rasteriaineistoa
(inventointi 2019–2023). Jokaisen lajin rajat ovat säädettävissä livenä
🗺️-napin takaa; asetukset ja valittu laji muistetaan selaimessa.

### Hakatut kuviot

Luken aineisto on tilannekuva. Vuoden 2021 jälkeen hakattu kuvio lukee siinä yhä
sinä metsänä joka siinä oli ennen koneita — ja koska uudistushakkuu kohdistuu
nimenomaan vanhaan puustoon, virhe osuu pahimmin sinne missä kartta on
varmimmillaan. Korjaus haetaan Suomen metsäkeskuksen avoimesta rajapinnasta, ja
sen kaksi aineistoa pidetään tarkasti erillään:

| Aineisto | Mitä se kertoo | Miten sitä käytetään |
|---|---|---|
| **Metsävarakuviot** (`stand`) | mitä maastossa **on**. Metsäkeskus päivittää kuviot ensisijaisesti hakkuukoneen omasta mittauksesta (ajankohta, hakkuutapa, koneen GPS-jäljestä muodostettu rajaus) | kehitysluokat A0/S0/T1/T2 **poistetaan** kartalta |
| **Metsänkäyttöilmoitukset** (`forestusedeclaration`) | mitä joku **aikoo**. Tehdään ≥ 10 vrk ennen hakkuuta, voimassa 3 vuotta, eikä ilmoitettua hakkuuta ole velvoite tehdä | **ei poista mitään** — näkyy vain napautustiedoissa ja 🪵-aputasolla |

Ero ei ole muodollisuus. Pirkanmaalla mitattuna vuoden 2021 jälkeen ilmoitetuista
uudistushakkuista 57 % on kuviotiedon mukaan nyt aukeaa tai taimikkoa — mutta
36 % on yhä pystyssä olevaa varttunutta metsää. Ilmoituksen perusteella
poistaminen pyyhkisi siis reilun kolmanneksen kohteista turhaan. Kasvatushakkuun
ilmoituksista vain 6 % osuu nuoreen kuvioon, joten harvennukset jätetään kokonaan
huomiotta: harvennettu metsä on yhä metsä.

Kuviotieto kattaa vain yksityismetsät, joten valtion ja yhtiöiden mailla korjaus
ei toimi. Malli itse on ennallaan — vika ei ole mallissa vaan sen lähtöaineiston
iässä, joten korjaus tehdään vasta pisteytyksen jälkeen, samaan tapaan kuin
`ml/plan/pick_sites.py` soveltaa poissulkumaskinsa. Korjauksen voi kytkeä pois
🗺️-valikosta.

Korjaus tulee kahta reittiä. **Sääntötaso ja napautustiedot** hakevat sen
suoraan Metsäkeskuksen rajapinnasta, jolloin se on aina tuore eikä vaadi
julkaisua. **Todennäköisyyskartta** tarvitsee sen valmiiksi laskettuna, jotta
värit ovat oikein jo ennen napautusta: `ml/ingest/fetch_harvests.py` lataa
maakunnittaiset GeoPackage-paketit ja rasteroi ne samaan ruudukkoon
mallirasterin kanssa (`data/matsutake/cut_*.tif`, 9 osaa, 66 MB). Sovellus
lukee ne mallirasterin rinnalla toisena kaistana. Napautettaessa elävä
rajapinta voittaa aina; julkaistua tasoa käytetään vain kun yhteyttä ei saada,
ja silloin se myös sanotaan ääneen.

Koko maan ajossa aineistoon kertyi 1 796 598 aukeaa tai taimikkokuviota ja
710 531 vuoden 2021 jälkeen ilmoitettua uudistushakkuuta. Kartan värittämistä
ruuduista Etelä-Suomessa noin 13 % osuu hakattuun maahan — enemmän kuin
metsäpinta-alasta keskimäärin, juuri siksi että malli suosii vanhaa männikköä
ja uudistushakkuu kohdistuu samaan puustoon.

### Miksi juuri nämä ehdot

- **Matsutake** kasvaa vanhoissa männiköissä kuivilla ja karuilla kankailla.
  Jäkäläisyys korreloi vahvasti karukko-/kuivan kankaan kanssa, joten
  jäkäläkankaat tulevat mukaan kasvupaikkaluokkien kautta. Luken
  kasvupaikkateema luokittaa kuitenkin puolet tunnetuista kasvupaikoista
  *kuivahkoksi* kankaaksi ja vain joka kahdeksannen *kuivaksi*, joten kuivahko
  on oletuksena mukana. Lisäksi vaaditaan **vähäkuusisuus** (kuusta ≤ 20 m³/ha):
  laji karttaa kuusikoita selvästi. Puusto on myös rajattu **harvaksi**
  (latvuspeitto enintään 60 %, säädettävissä) — havaintoaineistossa 70 % tunnetuista
  löydöistä on tiheydeltään tätä harvempaa metsää, vain 19 % muista
  sienihavainnoista, ja Suomessa tehty ainoa kenttätutkimus (Vaario ym. 2015)
  löysi parhaat sadot 41–60-vuotiaista, verrattain avoimista männiköistä eikä
  tiiviistä talousmetsästä. Havaintoaineiston perusteella tärkein vielä
  puuttuva tekijä on hiekkainen/harjumaaperä — sitä varten on tekeillä
  havainnoista opetettu todennäköisyyskartta, ks.
  [docs/HABITAT_MODEL_PLAN.md](docs/HABITAT_MODEL_PLAN.md).
- **Herkkutatti** on kuusen (myös männyn ja koivun) sienijuurikumppani ja
  suosii tuoreita kankaita, joilla maassa on neulaskariketta ja vain ohut
  sammalpeite. Siksi ehtoina ovat kuusitilavuus *ja* tiheä latvuspeitto —
  parhaat kohdat ovat näiden kuvioiden reunoilla ja polkujen varsilla.
  Suokuviot on rajattu pois.
- **Kanttarelli** on kuusen, koivun ja männyn sienijuurikumppani ja viihtyy
  kosteahkoilla sammalpohjaisilla tuoreilla kankailla, myös kuivahkoilla.
  Isäntäpuuehto oli pitkään unioni — kuusta, koivua **tai** mäntyä riittävästi —
  kunnes se mitattiin 393:a havaintoa ja yhtä montaa 2–5 km päässä olevaa
  metsäpistettä vasten: unioni päästi läpi 94 % havainnoista mutta myös 77 %
  verrokista, ja koivu erotteli niistä kolmesta jopa hiukan väärään suuntaan
  (41 % havainnoista, 43 % verrokista). OR-ehdon valikoivuuden määrää sen heikoin
  jäsen, joten unioni on korvattu **koko puuston tilavuudella** (≥ 150 m³/ha),
  joka on ainoa yksittäinen taso, joka sekä erottelee että on ilmaistavissa
  kartan maskeina. Laji on silti yleislaji ja sen kartta väljin — erityisesti
  Etelä-Suomessa, missä metsä on jo valmiiksi tätä tuuheampaa. Aidosti kiristävä
  säädin on **Vain kuusivaltaiset**. Koko mittaus:
  [docs/SPECIES_FILTER_kanttarelli.md](docs/SPECIES_FILTER_kanttarelli.md).
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
| 🍄 Matsutake, + latvuspeitto ≤ 60 %* | — | — | — |
| 🌼 Kanttarelli (mitattu sittemmin uudelleen, ks. alla) | 72 % | 11 % | 6,5× |
| 🎺 Suppilovahvero | 51 % | 9 % | 5,8× |
| 🌰 Herkkutatti (vertailukohta, ennallaan) | 19 % | 2 % | 8,3× |

Matsutaken luvut perustuvat 104 GBIF-havaintoon (tarkkuus ≤ 250 m) ja 300
satunnaiseen metsäpisteeseen, jotka luettiin suoraan Luken MVMI-rastereista
(ks. `docs/HABITAT_MODEL_PLAN.md`). Vanha "kuiva kangas" -oletus hukkasi yli
90 % tunnetuista löytöpaikoista.

\* Latvuspeitto-ehto (2026-09-20, ks. `docs/HABITAT_MODEL_PLAN.md` §12) ei vielä ole tämän
taulukon omalla 45 havainnon / 45 verrokkipisteen menetelmällä mitattu — rivi jätetty auki kunnes
se ajetaan. Samalla 104 GBIF-havainnon aineistolla mitattu, hieman erilaisin oheisehdoin (sääntö
D `docs/HABITAT_MODEL_PLAN.md` §4.2), latvuspeitto ≤ 60 % pudotti löytöosuuden 48 %:sta 45 %:iin.

Suppilovahverolla puuston ikä erottelee aidosti, joten oletusikä on 60 v — se
puolittaa värjätyn pinta-alan osuvuuden kärsimättä.

#### Kanttarelli, mitattuna uudelleen

Kanttarellin rivi yllä on jätetty näkyviin, mutta se on vanhentunut. Laji
mitattiin uudelleen isommalla aineistolla — **393 havaintoa ja 373
kohdistettua verrokkipistettä** 45:n ja 45:n sijaan — ja luvut näyttävät
toisenlaisilta:

| Kanttarelli | Havainnoista | Verrokista | Suhde | Metsämaasta värittyy |
|---|---|---|---|---|
| vanhat oletukset (isäntäpuu-unioni) | 65 % | 44 % | 1,5× | 30 % |
| **uudet oletukset** (tilavuus ≥ 150 m³/ha) | 60 % | 37 % | **1,6×** | **18 %** |
| uudet + *Vain kuusivaltaiset* | 32 % | 14 % | **2,3×** | 9 % |

Ero aiempaan 6,5×:ään tulee osin **verrokin rajauksesta**: nyt verrokkipisteet
on rajattu metsämaalle, koska kartan käyttäjä valitsee metsän ja metsän eikä
metsän ja järven väliltä. Rajaamattomana sama vanha suodatin saisi 2,8×.
Rajaus selittää osan erosta, otoskoko (45 vs. 393) oletettavasti loput.

Kaksi tulosta muuttivat ehtoja: **kasvupaikkaluokka ei erottele kanttarellia
käytännössä lainkaan** (92 % havainnoista, 91 % verrokista), ja **koivu
isäntäpuuna erottelee hienoisesti väärään suuntaan** (41 % vs. 43 %). Koska
OR-ehdon valikoivuuden määrää sen heikoin jäsen, kolmen puulajin unioni oli
suodattimen löysin kohta. Sen tilalla on nyt koko puuston tilavuus.

Säätimistä mitattiin samalla koko matka, ja tulos oikaisee tämän dokumentin
aiempaa väitettä: **kiristäminen ei romahduta osuvuutta vaan parantaa sitä**,
joten rivi "6,5× → 3,5×" on poistettu. Vanha isäntäpuusäädin ei myöskään ollut
rikki — se oli *tasannetta* koko alaosaltaan (0, 20 ja 40 antoivat saman
kartan), ja vanha oletus istui keskellä sitä. Samalla löytöosuudella vanha ja
uusi säädin ovat tasoissa (isäntäpuu 120 → 40 % / 1,75×, tilavuus 200 → 40 % /
1,72×), joten parannus on oletuksen sijainti eikä vipu itse.

Tehokkain säädin ei ole kumpikaan niistä vaan **puuston ikä**: 60 v antaa 1,9×
ja 80 v 2,4×. Se lukee nyt säätimen vihjeessä, koska sitä ei voi arvata.

Rehellisyyden nimissä: **oletusten parannus on vaatimaton ja se tulee pääosin
Keski- ja Pohjois-Suomesta.** Etelä-Suomessa valtaosa metsästä ylittää
150 m³/ha jo valmiiksi, joten 20 km:n ruutu Nuuksion yllä värittyy vanhoilla
oletuksilla 44-prosenttisesti ja uusilla 43-prosenttisesti. Se ehto, joka
etelässä aidosti kiristää, on kuusivaltaisuus (2,3×) — ja se maksaa yli puolet
löydöistä, joten se on säädin eikä oletus. Yleislajin karttaa ei saa yhtä
aikaa kapeaksi ja rehelliseksi.

> **Huom:** parhaat ukonsienipaikat — pientareet, hakamaat, pihat ja niityt —
> eivät ole metsävara-aineistossa lainkaan. Kartta antaa suunnan; etsi
> pinkkien kuvioiden reunoja.

## Ominaisuudet

- 🍄 **Lajivalitsin** oikeassa yläkulmassa: pieni modaali, josta laji vaihtuu
  yhdellä napautuksella. Kartan otsikko, selite ja tietosivu vaihtuvat mukana.
- 🔎 **Haku**: paikannimet ja osoitteet (Nominatim / OpenStreetMap) sekä
  koordinaatit joko asteina tai ETRS-TM35FIN-metreinä.
- 📍 **Lähellä sinua**: tyhjä hakukenttä näyttää kolme lähintä käymisen arvoista
  kuviota — ks. alla. Sijaintilupaa ei tarvita: ilman sitä lista etsii kartan
  keskipisteen ympäriltä, eli siitä mitä ruudulla juuri nyt katsoo, ja seuraa
  karttaa kun sitä siirtää. Sijainnin voi ottaa käyttöön listan alta. Heti kun alat
  kirjoittaa, lista väistyy hakutulosten tieltä.
- 📍 **GPS-piste** joka seuraa laitteen sijaintia (seuranta katkeaa kun karttaa
  raahaa, palaa päälle napista)
- 🗺️ **Sienitaso**: 3–5 WMS-rasterimaskia yhdistetään selaimessa
  canvas-kompositiolla → näkyviin jäävät vain ruudut, joissa kaikki ehdot
  täyttyvät. Suodattimet säädettävissä livenä.
- 🔎 **Napauta karttaa** → paikan kasvupaikka, maapohja, valitun lajin
  mittarit, rinteen jyrkkyys ja suunta, alue-arvio sekä kokonaisarvio +
  navigointilinkki.
- 🍄 **Sienihavainnot**: GBIF/Lajitietokeskus-löydöt omana tasonaan, luokiteltuna
  sen mukaan kuinka tarkasti ne on paikannettu ja onko metsä niiden jälkeen vaihtunut
  — 445 matsutakelle ja 2 747 kanttarellille, ks. alla.
- 📊 **Satokausikaavio** ℹ️-sivulla: samat havainnot viikoittaisena pylväskuvana kolmelta
  leveyspiirivyöhykkeeltä (Lappi, Kainuu ja Pohjois-Pohjanmaa, Itä- ja Etelä-Suomi) — näkee
  yhdellä silmäyksellä missä kohtaa kautta juuri nyt ollaan. Kuva piirtyy sille lajille joka
  on valittuna, ja lajit näyttävät eri asiaa: matsutakella kausi on kapea ja pohjoinen
  huipentuu ensin, kanttarellilla etelän kausi on selvästi pitkäjaksoisempi eikä
  pohjoinen käy edellä.
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

**Lähellä sinua** -lista tekee rasterista paikkoja. Kiintopiste on GPS-sijainti
jos sellainen on, muuten kartan keskipiste. Lista hakee samat maskit kerran
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
kohta, jossa kannattaa seistä. Sama valinta tehdään `ml/plan/pick_sites.py`:ssä.

Uuden sienen lisääminen on yksi merkintä `SPECIES`-taulukkoon `index.html`:ssä:
laji kuvaa suodattimensa (`conditions`), hyväksymänsä maapohjat (`mainTypes`),
säätimensä (`controls`), mittarinsa (`metrics`) ja tekstinsä — käyttöliittymä
rakentuu niistä.

## Todennäköisyyskartta (🧠)

🗺️-valikon **Todennäköisyyskartta** on havainnoista opetettu malli
(neuroverkon ja gradient boostingin keskiarvo), joka antaa jokaiselle 16 m ruudulle arvion siitä,
kuinka matsutaken tunnettujen löytöpaikkojen kaltainen se on. Malli yhdistää Luken
metsätiedot, MML:n korkeusmallin (rinne, suunta, harjanne), GTK:n maaperä- ja
harjukartan sekä Ilmatieteen laitoksen lämpösumman.

Säädin *Näytä parhaat X % metsämaasta* valitsee kynnyksen, ja se kannattaa vetää
alas: kartta on tehty luettavaksi kärjestään. Ristiinvalidoituna (25 km alueblokit,
arviointi vain ≤ 250 m tarkkuuden havainnoilla) asetukset tarkoittavat tätä:

| Kartta värittää | Tunnetuista löydöistä mukana | Sienihavaintopaikoista matsutakea | Osuvuus vs. satunnainen metsä |
|---|---|---|---|
| parhaat 0,25 % | 10 % | 52 % | 39× |
| parhaat 0,5 % | 18 % | 53 % | 36× |
| parhaat 1 % | 30 % | 52 % | 30× |
| parhaat 2 % | 38 % | 37 % | 19× |
| parhaat 5 % | 56 % | 25 % | 11× |
| parhaat 15 % | 82 % | 12 % | 5× |

Kolmas sarake on se, joka kertoo kannattaako ajaa: kun kartan värillä olevalta
alueelta on ylipäätään ilmoitettu sieni, kuinka usein se on matsutake. Vanha
sääntökartta ylsi 5 %:n kohdalla 15 %:iin löydöistä.

Luvut ovat tiukimmassa päässä matalampia kuin aiemmassa julkaisussa (0,25 %:n
kohdalla 72 % → 52 %), väljässä päässä korkeampia (15 %:n kohdalla 79 % → 82 %).
Vertailu ei ole suoraviivainen: samalla kun malliperhe vaihtui, havaintoaineisto
päivittyi, joten arviointijoukko ei ole sama. 0,25 %:n siivuun osuu vain reilu
kymmenen löytöä, joten pari siirtynyttä havaintoa heiluttaa sen lukua kymmenen
prosenttiyksikköä; väljemmät rivit lepäävät selvästi useamman löydön varassa ja
ovat siksi ne, joita kannattaa verrata. Saman aineiston sisällä mitattuna uusi
malliperhe voitti vanhan kaikilla mittareilla Boyce-indeksiä lukuun ottamatta
([docs/MODEL_CHOICE_matsutake.md](docs/MODEL_CHOICE_matsutake.md)).

Kartta kattaa metsämaan parhaan 15 %:n; sen ulkopuolella malli ei piirrä mitään.
Miksi malliperhe on juuri tämä ja mitä vertailu antoi:
[docs/MODEL_CHOICE_matsutake.md](docs/MODEL_CHOICE_matsutake.md). Menetelmä, aineisto
ja tarkkuusluvut: [docs/HABITAT_MODEL_PLAN.md](docs/HABITAT_MODEL_PLAN.md) ja
[docs/MODEL_REPORT_matsutake.md](docs/MODEL_REPORT_matsutake.md); koodi ja
data kansiossa [`ml/`](ml/README.md).

**Retkisuunnittelu.** `ml/plan/pick_sites.py` tekee kartasta lyhyen listan: se rajaa
suojelu- ja puolustusvoimien alueet, rakennusten lähistön ja isojen teiden
päästökäytävät pois, vaatii että paikalle pääsee autolla kävelymatkan päähän, ja
järjestää loput kuviot sen mukaan miten hyvä niiden *huonoin* neljännes on.
Aineisto siihen haetaan OpenStreetMapista (`ml/plan/fetch_osm.py`).

## Sienihavainnot (🍄) — mikä niistä on yhä vihje

Kartalla on GBIF:n ja Lajitietokeskuksen havaintoja kahdelle lajille: **445
matsutake-havaintoa ja 2 747 kanttarellihavaintoa**. Ne eivät ole samanarvoisia,
eikä piste voi näyttää siltä että olisivat: matsutakella kolmannes on
kuntakeskipiste sieni päällä, ja aineisto ulottuu vuoteen 1866, joten moni kuvaa
metsää joka kaadettiin vuosikymmeniä sitten.

Kanttarellilla sama luokittelu on ajettu erikseen: 2 747 havainnosta 1 911 on
paikannettu tarkemmin kuin kilometriin, ja niistä 1 168 seisoo metsässä joka on
kuviotiedon mukaan yhä pystyssä, 310 on epävarmoja, 59 hakattuja ja 372
metsätalousmaan ulkopuolella (pihoja, puistoja, tienvarsia — kanttarelli on
kaupunkilaistenkin sieni). Toisin kuin matsutakella, pisteet eivät juuri kasaudu
päällekkäin: 2 747 tietuetta on 2 567 eri koordinaatissa, joten kartan tiheys on
aitoa levinneisyyttä eikä kuntakeskipistekasoja.

Merkki kertoo kaksi eri asiaa, eikä niitä lasketa yhteen. **Geometria** kertoo
paikannuksen: umpinainen piste on paikannettu tarkemmin kuin 250 m, summittaisen
(≤ 1 km) ympärille piirtyy zoomista 11 alkaen sen todellinen epätarkkuusympyrä, ja
sitä karkeammat eivät ole nastoja lainkaan vaan katkoviivaisia renkaita — yksi per
koordinaatti, koska 105 tietuetta jakaa 29 pistettä ja päällekkäin ladottuina ne
näyttäisivät Lapin parhaalta matsutakemaalta. Napauta karkeaa rengasta, niin sen
oikea ympyrä piirtyy kartalle; 100 km nielee puoli Lappia, ja se on juuri se asia
joka tietueesta pitää tietää.

**Väri** kertoo onko maa yhä sitä mitä se oli löytöhetkellä:

| | | n |
|---|---|---|
| 🟡 keltainen | metsä on yhä pystyssä | 146 |
| 🟡 vaalea | metsä on ehkä muuttunut — osa ympyrästä hakattu, tai kasvupaikkatieto heittää | 63 |
| ⚪ harmaa | hakattu tai vaihtunut — **koordinaatti on yhä hyvä**, lähimetsässä voi olla | 22 |
| ⭕ ontto keltainen | ei metsätalousmaata: hautausmaa, piha, pelto | 27 |
| ⭕ katkoviiva | ei arvioitavissa — paikannus liian karkea | 187 |

Ne 187 ovat portitettuja, eivät arvioituja: 16 m:n ruudun lukeminen ±100 km:n
tarkkuudella paikannetun tietueen alta kuvaisi keskipistettä, ei löytöä. Sama raja
jolla malli päättää mitä se saa oppia.

Loput 258 luetaan yhdeksästä pisteestä epätarkkuusympyrän sisällä. Painavin todiste
on Metsäkeskuksen kuviorekisteri — hakkuukoneen omaa mittausta, ainoa mitattu eikä
arvioitu lähde — ja sen jälkeen kasvuston ikä havainnon omaa vuosilukua vasten: jos
metsikkö on syntynyt löydön jälkeen, puusto on vaihtunut. Kasvupaikan ala- ja
päätyypin muutos inventointien välillä nostaa vain lipun eikä anna tuomiota, koska ne
kuvaavat maaperää eivätkä vaihdu neljässätoista vuodessa muuten kuin ojittamalla —
mikä niiden välillä oikeasti muuttuu, on Luken arvio niistä.

### Milloin — satokausikaavio ℹ️-sivulla

Sama aineisto kertoo myös *milloin*, ja se on ℹ️-sivulla omana kuvanaan: havainnot
ISO-viikoittain, pinottuna kolmeen leveyspiirivyöhykkeeseen. **Lappi**, **Kainuu ja
Pohjois-Pohjanmaa** — Koillismaa mukaan lukien, sillä Kuusamo on Pohjois-Pohjanmaata ja
pelkkä leveyspiirileikkaus veisi sen havainnot Lapin puolelle — ja **Itä- ja Etelä-Suomi**,
eli loput maasta Pohjois-Karjalasta ja Savosta Uudellemaalle ja Varsinais-Suomeen. Rajat
ovat kaksi suoraa maakuntarajojen mukaan: rajalla istuva kunta menee väärälle puolelle,
mutta kuvan asia on vyöhyke eikä raja.

Väri kulkee tummuusjärjestyksessä pohjoisesta etelään, koska järjestys on tässä itse
sanoma: Lapin huippu on aikaisemmin kuin etelän. Napauta pylvästä, niin sen viikon luvut
aukeavat kuvan alle; pystykatkoviiva merkitsee kuluvan viikon, eli sen mihin kohtaan kautta
tämä päivä osuu. Yhteenvetorivit kertovat vyöhykkeen huippuviikon ja välin, jolle puolet
sen havainnoista osuu.

Pylvään korkeus on havaintojen määrä, ei sadon runsaus: siihen vaikuttaa myös se milloin
ihmiset ovat metsässä ja kirjaavat löytönsä, ja kaikki vuosikymmenet 1866:sta alkaen ovat
samassa kuvassa. Tietueet joilla on vain kuukausi tai vuosi eivät mahdu viikkoakselille, ja
akselin päistä on karsittu yksittäiset kaudesta kaukana olevat havainnot — molempien määrä
lukee kuvan alla.

Suodatin *Parhaat vihjeet* jättää näkyviin paikannetut, joiden metsä on yhä
pystyssä tai jotka ovat metsätalousmaan ulkopuolella. Napauta pistettä, niin modaali
kertoo tuomion ja perustelun yhdellä lauseella. Kynnykset ja se mitä tämä **ei** voi
kertoa (harvennusta ei näe mikään, kuviorekisteri kattaa vain yksityismetsät, mikään
ei tarkista lajinmääritystä): [docs/HABITAT_MODEL_PLAN.md](docs/HABITAT_MODEL_PLAN.md),
kohta 9b.

## Aineistot ja lisenssit

- Metsävaratiedot: Luonnonvarakeskus (Luke), monilähteisen valtakunnan metsien
  inventoinnin (MVMI) karttatasot 2023, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Korkeustiedot: Maanmittauslaitoksen 10 m korkeusmalli (CC BY 4.0) valmiiksi
  leivottuna; jos sitä ei ole julkaistu, rinne haetaan
  [Open-Meteosta](https://open-meteo.com/) (Copernicus GLO-90 DEM)
- Havaintoaineisto: [GBIF](https://www.gbif.org/) / Suomen Lajitietokeskus. Matsutakella ja
  kanttarellilla se on myös osa sovellusta (🍄-taso ja satokausikaavio, `data/*/observations.json`);
  muilla lajeilla sitä on käytetty vain oletusrajojen tarkistukseen. Tietuekohtaiset
  lisenssit ja aineistokohtainen attribuutio: [DATA_LICENSES.md](DATA_LICENSES.md)
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
