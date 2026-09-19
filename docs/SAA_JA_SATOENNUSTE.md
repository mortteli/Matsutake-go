# Matsutake, sää ja satovuosi

Perustiedot lajista ja suunnitelma siitä, miten toteutuneista sääharavainnoista
saisi paikallisen satoennusteen tähän sovellukseen. Tämä dokumentti on
taustatyö ja suunnitelma — sovellukseen ei muutu mitään ennen kuin vaiheet
alla on ajettu ja niiden tulos on nähty.

Liittyy dokumenttiin [HABITAT_MODEL_PLAN.md](HABITAT_MODEL_PLAN.md), jonka
avoimissa kohdissa (§11) lukee "phenology layer" — tämä on sen suunnitelma.

---

## 0. Lyhyt vastaus

1. **Heimo.** Kantasienet → helttasienet (Agaricales) → **valmuskat**
   (*Tricholoma*, heimo Tricholomataceae), ryhmä *Tricholoma* sect. *Caligata*.
   Euroopan "tuoksuvalmuska" kuvattiin aikanaan omaksi lajikseen
   *T. nauseosum*, mutta ITS-sekvensointi osoitti sen samaksi lajiksi kuin
   japanilainen *T. matsutake* (Bergius & Danell 2000).
2. **Isäntäpuu.** Kyllä, **ektomykorritsasieni eli juurisieni** — ei lahottaja.
   Pohjois-Euroopassa käytännössä **männyn** seuralainen kuivilla hiekka- ja
   jäkäläkankailla. Suomalainen kanta muodostaa laboratoriossa mykorritsan
   *sekä männyn että kuusen* kanssa (Vaario ym. 2010), ja kenttähavaintoja on
   myös kuusen läheltä, mutta sadot tulevat männiköistä. Kartan ehto "vain
   vähän kuusta" ei siis ole isäntäpuuehto vaan **kasvupaikkaehto**: kuusi
   kertoo tuoreesta kankaasta, paksusta humuksesta ja varjosta, eli siitä
   mitä matsutake ei siedä.
3. **Kanttarelli** on vertailukohtana aito monen isännän laji: kuusi, koivu
   *ja* mänty käyvät, mistä sekametsäkokemus tulee. Matsutake on kapea.
4. **Se "tasaisen kostea kesä + sateinen syksy" -sääntö pätee vain osittain.**
   Se on lahottajasienen logiikka: karikkeen kosteus rajoittaa rihmaston
   kasvua. Matsutaken rihmasto saa hiilensä elävältä männyltä, ja laji on
   erikoistunut **kuivaan, karuun, vettä läpäisevään** maahan. Suomen ainoa
   pitkä seuranta (Vaario ym. 2015, Etelä-Suomi 2008–2013) löysi, että
   **suuri sato liittyi keskimääräiseen sademäärään** (90–110 % pitkän ajan
   keskiarvosta) ennen ensimmäistä satoa — ei siis "mitä sateisempi sen
   parempi".
5. **Lämpötila on ilmeisesti tärkeämpi kuin sade.** Japanissa itiöemäaiheet
   lähtevät liikkeelle kun maan lämpötila laskee syksyllä ~19 °C:een
   (17,5–19 °C alueesta riippuen, alin itiöemöinnin lämpötila ~12 °C).
   Japanilaisessa shiro-seurannassa esikauden lämpötila selitti sekä
   rihmastopatjan laajenemisen että itiöemien määrän paremmin kuin sade.
   Vaario ym. eivät Suomessa löytäneet kynnysmaalämpötilaa sadon *alulle*,
   mutta maan lämpötila ennusti kauden *loppumista*, ja myöhäinen aloitus tai
   korkea maalämpötila ennen ensisatoa lyhensi kautta.
6. **Suomen satokausi** on heinäkuun lopusta lokakuun alkuun, painopiste
   elo–syyskuussa; sovelluksen omat havainnot (1990→, paikannus ≤ 10 km)
   jakautuvat 07/08/09/10 = 2 / 107 / 100 / 5. Vuosivaihtelu on suurta:
   hyvää vuotta voi seurata useampi laiha.
7. **Ajettu.** Kohdat 1–6 ovat kirjallisuutta; §4 on sitä mitä tämän repon oma aineisto
   sanoo, kun 210 päivättyä löytöä ajetaan FMI:n päivittäisiä hiloja vasten. Lyhyesti:
   **edeltävän 60 vrk:n sade erottaa löytövuoden** samasta paikasta ja päivästä muina
   vuosina (z = 6,8; ristiinvalidoitu sijoitus 0,66, kun 0,50 on arvaus), eikä se selity
   keruuaktiivisuudella eikä toistu löydön jälkeisellä sateella. Syksyn jäähtyminen ei
   erotu, ja lämpötilan vaikutus osoittautui pitkälti 45 vuoden trendiksi.
8. **Ennustettavuus.** Tämän aineiston varassa realistinen tavoite ei ole
   "montako kiloa" vaan **kauden ajoitus ja vuoden otollisuus suhteessa
   paikan omaan ilmastoon** — ja sekin varauksella, koska GBIF-havainto on
   esiintymä, ei satomäärä (ks. §5).

---

## 1. Laji ja sen kumppanuus

### 1.1 Sijoitus

| | |
|---|---|
| Heimo | Tricholomataceae (valmuskat) |
| Suku | *Tricholoma*, sect. *Caligata* ("caligatum-kompleksi", 9–10 lajia maailmassa) |
| Laji | *Tricholoma matsutake* (Ito & Imai) Singer |
| Synonyymi | *T. nauseosum* — eurooppalainen nimi, sama laji (Bergius & Danell 2000) |
| Suomeksi | tuoksuvalmuska |

### 1.2 Mykorritsa

Matsutake on **ektomykorritsasieni**: se kietoo männyn hienojuuren
sienivaippaan ja työntää rihmoja solujen väliin (Hartigin verkko), vaihtaa
puulle vettä ja ravinteita sokeria vastaan. Kolme seurausta, jotka kaikki
näkyvät kartassa ja sään tulkinnassa:

- **Puu on pakollinen.** Ei vanhaa mäntyä → ei matsutakea, vaikka maaperä ja
  sää olisivat täydelliset. Siksi hakkuukorjaus on niin olennainen.
- **Hiili ei tule sateesta.** Kesän sade ei "ruoki" rihmastoa samalla tavalla
  kuin lahottajaa; se vaikuttaa veden kautta — ja liika vesi karulla
  hiekkakankaalla on lähinnä kilpailijoiden ja tiheän kasvillisuuden etu.
- **Rihmasto on monivuotinen ja hidas.** *Shiro* on juurten ja maahiukkasten
  ympärille kasvanut valkoinen rihmastopatja, joka laajenee mitatusti noin
  **0,17 m vuodessa** ja tuottaa itiöemät reunavyöhykkeelleen. Paikka on
  siis sama vuodesta toiseen — hyvä uutinen kartalle, ja se selittää miksi
  vanha tarkka koordinaatti on yhä vihje, jos metsä on pystyssä.

### 1.3 Miksi mänty eikä kuusi

Vaario ym. (2010) saivat suomalaisen kannan muodostamaan mykorritsan sekä
männyn että kuusen taimille laboratoriossa, ja Suomen Luonnon jutuissa laji
mainitaan "männyn ja kuusen seuralaisena". Pohjois-Euroopan **tuottavat**
esiintymät ovat silti poikkeuksetta kuivia, usein jäkäläisiä hiekkamänniköitä
harjuilla ja jokivarsien lajittuneilla mailla, vanhaa ja harvaa puustoa, ohut
humus. Käytännön tulkinta: kuusi ei ole myrkkyä, mutta kuusikko on.

### 1.4 Vertailu sovelluksen muihin lajeihin

| Laji | Elintapa | Isäntä | Sään logiikka |
|---|---|---|---|
| Matsutake | ektomykorritsa | mänty (kuusi mahdollinen) | kuiva karu maa; **normaali** sade riittää, syksyn jäähtyminen laukaisee |
| Herkkutatti | ektomykorritsa | kuusi, mänty, koivu | kostea loppukesä + lämmin jakso |
| Kanttarelli | ektomykorritsa | kuusi, koivu, mänty (laaja) | tasainen kosteus, sammalpohja ei saa kuivua |
| Suppilovahvero | ektomykorritsa | kuusi, kostea korpi | myöhäinen, sateinen syksy |
| Ukonsieni | **lahottaja** | ei isäntäpuuta | tässä se klassinen "kostea kesä → rihmasto, sateinen syksy → itiöemät" pätee parhaiten |

---

## 2. Mitä hyvä satovuosi vaatii

### 2.1 Mitä tutkimus sanoo

**Suomi — Vaario ym. 2015** (Scand. J. For. Res. 30:259–265, seuranta 2008–2013,
Etelä-Suomi):
- sato heinäkuun puolivälistä syyskuun puoliväliin, ajoitus ja määrä vaihtelevat
  vuosittain paljon;
- **90–110 % pitkän ajan keskisademäärästä ennen ensisatoa → suuri sato**;
- **ei** kynnysmaalämpötilaa sadon alulle, mutta maalämpötila seuraa kauden
  päättymistä;
- myöhäinen aloitus tai korkea maalämpötila ennen ensisatoa → lyhyempi kausi.

**Japani/Kiina:**
- itiöemäaiheiden muodostus kun maan lämpötila laskee ~19 °C:een (17,5–19 °C),
  alin itiöemöinnin lämpötila ~12 °C;
- vuorokauden lämpötilavaihtelu edistää itiöemöintiä;
- Heilongjiang: hyvä sato odotettavissa kun maan lämpötila (10 cm) on 16–19 °C
  ja **70–100 mm sadetta noin 10 kuurossa** heinäkuun lopun ja elokuun alun
  välillä;
- shiro-seuranta männikössä: **esikauden lämpötila > sade** sekä laajenemisen
  että itiöemämäärän selittäjänä (sateen pudottaminen mallista paransi AIC:ta).

**Yleinen sienisatotutkimus** (Välimeri, Espanja; Keski-Eurooppa) löytää
toistuvasti kesän ja syksyn sateen tärkeimmäksi yksittäiseksi selittäjäksi.
Se on hyvä muistutus siitä, että matsutaken poikkeus on nimenomaan
**kasvupaikkakohtainen**: karulla hiekalla vesi ei ole sama rajoite kuin
tuoreella kankaalla, ja liika vesi voi jopa haitata.

### 2.2 Työhypoteesi Suomen oloihin (testattavat muuttujat)

Järjestys on se, jossa niitä kannattaa kokeilla — kärki ensin:

| # | Muuttuja | Ikkuna | Odotettu muoto |
|---|---|---|---|
| 1 | Sade suhteessa paikan omaan normaaliin | 60 vrk ennen ensisatoa | **kupera** (optimi ~100 %), ei monotoninen |
| 2 | Vuorokauden keskilämpötilan lasku | elo–syyskuu | laukaisee kauden; kumulatiivinen "jäähtymissumma" 15 °C alapuolella |
| 3 | Kuivuusjakso loppukesällä | pisin < 1 mm jakso 15.6.–15.8. | haitallinen, kynnys todennäköisesti olemassa |
| 4 | Lämpösumma (dd > 5 °C) 1.5. alkaen | kauteen asti | ajoituksen selittäjä (aikaisempi pohjoisessa) |
| 5 | Vuorokauden lämpötilavaihtelu | elokuu | positiivinen |
| 6 | Edellisen talven lumen sulamispäivä | — | heikko, mutta halpa testata |
| 7 | Paikallinen topografinen kosteus (DTW/TWI) | staattinen | **muuntaa** hilan sateen paikalliseksi vedeksi |

Muuttuja 7 on vastaus siihen, että sateessa on paikallista vaihtelua ja että
vesi kulkee muutakin kautta kuin suoraan taivaalta: 10 km:n hila ei näe
yksittäistä kuuroa eikä rinteen alapuolista vajoveden kertymistä, mutta
korkeusmallista laskettu kosteusindeksi näkee sen *suhteellisen* eron ilman
mitään uutta aineistoa. Yhdistelmä "hila-anomalia × paikallinen kosteusluokka"
on realistinen ensimmäinen askel; fysikaalinen maankosteusmalli (Syken WSFS)
on vasta sen jälkeen.

---

## 3. Aineistot

Kaikki alla oleva on avointa ja CC BY 4.0 -tyyppistä, ja `ml/licenses.py`
osaa jo kirjata FMI:n lähteeksi (staattiset normaalit ovat jo käytössä).

| Lähde | Mitä | Erotuskyky | Kattavuus | Tila |
|---|---|---|---|---|
| FMI päivähilat, `ilmatiede/10km_daily_precipitation/geotiff/rrday_YYYY.tif` | vuorokauden sademäärä | 10 km, ETRS-TM35FIN | **1961–2025** | ✅ **käytössä**, `ml/ingest/weather_daily.py` |
| FMI `…/10km_daily_mean_temperature/geotiff/tday_YYYY.tif` | vrk keskilämpötila | 10 km | 1961–2025 | ✅ **käytössä** |
| FMI `…/10km_daily_minimum_/maximum_temperature/`, `…_snow/`, `…_radiation/` | min/max, lumensyvyys, säteily | 10 km | 1961–2025 | ✅ saatavilla |
| FMI 1 km kuukausihilat `kk_sade_1x1/`, `kk_lampo_1x1/` | kk-sade ja -lämpö | **1 km** | 1961–2013 | ✅ paras paikallistarkkuus, mutta päättyy 2013 |
| FMI avoin WFS `fmi::observations::weather::daily::simple` (`rrday`, `tday`) | asemahavainnot | pistemäinen | reaaliaikainen | ✅ **käytössä**, `ml/export/season_status.py` — ainoa reitti kuluvaan kauteen (hilat laahaavat vuoden) |
| FMI 10 km kk-normaalit (jo repossa) | lämpösumma, vuosisade 1991–2020 | 10 km | staattinen | ✅ käytössä mallissa |
| Luke DTW-kosteusindeksi (opendata.luke.fi) | topografinen märkyys | **2 m** | koko maa | ⬜ lataamatta |
| MML korkeusmalli 10 m (jo käytössä) | TWI itse laskettuna | 10 m | koko maa | ✅ pipeline lukee jo |
| Syke WSFS / vesistömallijärjestelmä | mallinnettu maankosteus, lumi, valunta | valuma-alue | reaaliaikainen | ⬜ selvitettävä rajapinta |
| Metsäkeskus korjuukelpoisuus / kosteusindeksimosaiikki | maaston kantavuus = märkyys | 16 m / 2 m | yksityismetsät | ⬜ vaihtoehto Luken DTW:lle |
| ERA5-Land (Copernicus) | tunnittainen sää, maankosteus | 9 km | 1950→ | ⚠️ tässä ympäristössä rajoitettu, vertailukäyttöön |

**Havaintoaineisto** (`data/matsutake/observations.json`, 455 tietuetta) sään
liittämisen näkökulmasta — huomaa että 10 km:n säähilalle paikannustarkkuus
**≤ 10 km riittää**, joten käytettävä otos on paljon suurempi kuin mallin
16 m:n opetusotos:

| Osajoukko (päivämäärä tarkkana) | n | vuosia 1990→ |
|---|---|---|
| paikannus ≤ 250 m (mallin opetusotos) | 116 | 22 |
| ≤ 1 km | 260 | 32 |
| ≤ 10 km (säähilalle riittävä) | **301** | **32** |
| joista 1990→ | 214 | 22 vuotta, joissa ≥ 3 havaintoa |

---

## 4. Tulokset — ensimmäinen ajo

Ajettu 19.9.2026. Koodi: `ml/ingest/weather_daily.py`, `ml/dataset/build_weather_dataset.py`,
`ml/train/train_weather.py`. Täydet luvut: [MODEL_REPORT_weather.md](MODEL_REPORT_weather.md).

**Asetelma.** 210 päivättyä löytöä 150:ssä 10 km:n ruudussa, 1981–2025. Jokainen löytö on
oma vertailujoukkonsa: sama ruutu ja sama kalenteripäivä kaikkina muina vuosina, 9 450
ruutuvuotta yhteensä. Ehdollinen logistinen regressio kysyy vain sitä, mikä erottaa löydön
vuoden saman paikan ja saman päivän muista vuosista — paikka ja vuodenaika putoavat pois
täsmälleen, eivät likimäärin. Validointi jättää vuoden kerrallaan pois, koska toistuva
yksikkö on vuosi eikä löytö.

**1. Edeltävä sade on selvästi vahvin muuttuja.** Löytöä edeltävän 60 vrk:n sade, mitattuna
saman ruudun ja päivän 1991–2020-jakaumaa vasten: **+0,46 log-oddsia keskihajontaa kohti
(z = 6,8)**. Yksin ajettuna se antaa LOYO-sijoituksen **0,643** — eli mallin pisteytys nostaa
löytövuoden 64 %:n kohdalle vertailuvuosien joukossa, kun 0,50 on arvaus. Poutajakson pituus
tekee saman toisin päin (−0,47, z = −5,3).

**2. Ikkunan pituus.** 60 vrk > 90 vrk > 30 vrk > 7 vrk (LOYO 0,643 / 0,606 / 0,600 / 0,564).
Kyse ei siis ole edellisen viikon kuurosta vaan koko loppukesän vesitaseesta — mikä sopii
siihen, että shiro kasvattaa itiöemää viikkoja.

**3. Plasebo pitää.** Löydön **jälkeisten** 30 vrk:n sade: +0,09 (z = 1,3), LOYO 0,526.
Sateella, joka ei ole voinut kasvattaa sientä, ei ole selitysvoimaa. Löydetty signaali ei siis
ole "märät syksyt yleensä".

**4. Keruuaktiivisuus ei selitä sitä.** Vuoden sienihavaintomäärä (GBIF, Suomi, elo–syyskuu)
on itsessään voimakas (+0,45, z = 5,7) — havainto on ihmisen tekemä, ei sienen. Mutta kun
malliin pannaan **saman kuukauden** keruumäärä ja vuositrendi, sade pysyy paikallaan
(**+0,39, z = 4,7**) ja lämpötila romahtaa (+0,13, z = 1,7). Lämpötilan näennäinen vaikutus
oli siis suurelta osin sitä, että sekä lämpötila että kirjaaminen ovat kasvaneet 45 vuodessa.

**5. Suomen "90–110 % normaalista" ei toistu tässä aineistossa.** Osuvuus kasvaa
yksisuuntaisesti kuivasta märkään (0,19× → 0,79× → 0,80× → 1,53× → 1,66×), ja kvadraattinen
sovite kääntyy laskuun vasta **+1,66 keskihajonnalla**. Ristiriita Vaario ym. 2015:n kanssa on
todennäköisesti vasteen ero: he mittasivat kiloja yhdellä tuottavalla paikalla, tämä mittaa
sitä että joku löysi ja kirjasi sienen jossain 10 km:n ruudussa. Kuiva kausi estää molemmat,
märkä kausi voi laskea kiloja mutta silti lisätä löytöjä.

**6. Syksyn jäähtyminen ei erotu.** Päivien määrä, joina 7 vrk:n liukuva keskilämpö on alle
15 °C, on käytännössä nolla­vaikutus (−0,07, z = −2,2 yksin, ~0 muiden kanssa). Tämä on samaa
suuntaa kuin Vaario ym., jotka eivät löytäneet kynnysmaalämpötilaa sadon alulle. Ilmasta
laskettu korvike ei tavoita 19 °C:n maakynnystä, jos sellainen on.

**7. Sama etumerkki pohjoisessa ja etelässä** (+0,37 / +0,49), eli kyse ei ole yhden seudun
ilmiöstä.

**8. Vuositasolla ei näy mitään.** Koko maan vuosittainen löytömäärä korreloi keruumäärän
kanssa (ρ = +0,39, p = 0,016) eikä efortilla korjattu osuus korreloi sateen kanssa lainkaan
(ρ = 0,00). Kysymys on siis osattava kysyä paikan ja päivän sisällä. Tämä on myös syy olla
julkaisematta koko maan "satovuosi-indeksiä".

**Kauden tila nyt** (`ml/export/season_status.py`, 19.9.2026, asemadatasta, kauden malli):

| Paikka | 60 vrk sade | % normaalista | Suhteellinen kerroin |
|---|---|---|---|
| Kainuu (64,5 N 27,0 E) | 227 mm | 184 % | 1,7× |
| Itä-Lappi (66,5 N 27,5 E) | 237 mm | 195 % | 1,8× |
| Pohjois-Karjala (62,7 N 29,0 E) | 158 mm | 112 % | 2,4× |
| Nuuksio (60,3 N 24,5 E) | 134 mm | 90 % | 1,3× |

Pohjois-Karjala saa korkeimman kertoimen pienimmällä sateella, koska sen poutajaksot ovat
olleet lyhyitä ja sade osuu lähelle käyrän huippua; Kainuussa ja Lapissa ollaan jo huipun
märällä puolella. Kerroin on *suhde saman paikan normaalivuoteen*, ei todennäköisyys löytää
sieni eikä paikkojen välinen vertailu — Nuuksion 1,3× ei tarkoita että siellä olisi enemmän
matsutakea kuin Kainuussa, päinvastoin.

**Mitä tämä kaikkiaan sanoo.** Sää selittää löytövuotta sen verran, että siitä kannattaa
kertoa käyttäjälle, muttei niin paljon että sillä kannattaisi värittää karttaa: paras LOYO-luku
on 0,662, eli kolmasosa vertailuvuosista menee yhä väärin päin. Hyödyllisin yksittäinen luku on
"60 vrk sade % normaalista" ja sen pari "pisin poutajakso", ja ne ovat molemmat luettavissa
sellaisinaan ilman mallia.

## 5. Suunnitelma

### P0 — havainto × sää -taulukko ✅ ajettu

`ml/ingest/weather_daily.py`: lataa `rrday_YYYY.tif` ja `tday_YYYY.tif`
tarvituille vuosille (vsicurl-luku kuten nykyisessä `climate.py`:ssä), poimi
jokaiselle havainnolle sen 10 km:n solun aikasarja ja laske:

- sade 30 / 60 / 90 vrk ennen havaintopäivää, sekä **prosentteina saman solun
  saman jakson 1991–2020 keskiarvosta**;
- lämpösumma (dd > 5 °C) 1.5. alkaen havaintopäivään;
- elo–syyskuun keskilämpötila ja vrk-vaihtelu;
- ensimmäinen päivä, jona 7 vrk liukuva keskilämpö alittaa 15 / 12 °C
  (ilmalämpötila maalämpötilan korvikkeena; oikea maalämpötila on vain
  asemilta ja liian harvassa);
- pisin poutajakso 15.6.–15.8.;
- lumen sulamispäivä `…_snow`-hilasta.

Ulos `ml/data/weather/obs_weather.csv`. Tämä on itsessään hyödyllinen ja
julkaisukelpoinen taulukko, vaikka mallia ei koskaan tulisi.

### P1 — kuva ennen mallia ✅ korvattu suoralla testillä (§4)

Kolme kuvaajaa, jotka kertovat onko tässä mitään:

1. **Vuositaso.** x = kauden sade % normaalista, y = havaintojen määrä
   vuodessa **suhteutettuna kaikkiin sienihavaintoihin Suomesta samana
   vuonna** (keruuaktiivisuuden normalisointi). Testataan onko käyrä kupera,
   kuten Vaario ym. antaa odottaa.
2. **Ajoitus.** x = lämpösumma tai jäähtymispäivä, y = vuoden mediaanihavainnon
   päivämäärä, väri = leveyspiirivyöhyke (samat kolme kuin ℹ️-sivun
   satokausikaaviossa).
3. **Päivätaso.** Havaintopäivien sade-/lämpöanomaliat vs. saman solun kaikki
   elo–syyskuun päivät — eli "poikkeaako löytöpäivä mitenkään tavallisesta
   päivästä".

Jos mikään näistä ei erotu, projekti pysähtyy tähän ja dokumentoidaan
negatiivisena tuloksena. Se on hyväksyttävä lopputulos.

### P2 — malli ✅ ajettu, ks. §4 ja `docs/MODEL_REPORT_weather.md`

Muotoilu, joka kestää n ≈ 200:

- **case-control päivätasolla**: tapaus = (solu, havaintopäivä); kontrolli =
  sama solu, sama kalenteripäivä muina vuosina → vuodenaika ja paikka
  vakioituvat automaattisesti, jäljelle jää *vuoden sää*;
- logistinen regressio tai GAM, **enintään 3–5 muuttujaa**, kupera muoto
  sademuuttujalle sallittuna (neliötermi tai splini);
- validointi **leave-one-year-out**, mittarina kuinka hyvin malli järjestää
  vuodet havaintotiheyden mukaan (Spearman) — ei AUC per havainto, koska
  havainnot eivät ole riippumattomia;
- vertailukohtana tyhmä malli "päivämäärä + leveysaste". Jos sää ei voita
  sitä, sää ei tuo mitään.

LightGBM:ää **ei** tähän: aineisto on liian pieni ja rakenne on tiedossa.

### P3 — karttatuote ⬜ tekemättä

Kaksi erillistä asiaa, joita ei saa sekoittaa samaan väriin:

- **Habitaattikartta** (nykyinen 🧠-taso) vastaa kysymykseen *missä* — se on
  vuodesta riippumaton eikä sen värejä saa muuttaa sään perusteella, tai
  kartan lukeminen menee sekaisin.
- **Kauden tila** vastaa kysymykseen *nyt vai ei* ja kuuluu omaan tasoonsa.
  Koko Suomi 10 km:n hilalla on vain noin 12 000 solua, eli kauden sade- ja
  lämpöanomalia mahtuu muutaman kilotavun JSON-tiedostoon tai pieneen PNG:hen
  — päivitys GitHub Actionilla FMI:n WFS-asemadatasta, ei mitään raskasta.

Käyttöliittymäehdotus, kevyimmästä järeimpään:

1. ℹ️-sivun satokausikaavion viereen **kauden mittari**: "kertynyt sade
   1.7. alkaen: 78 % normaalista · elokuun keskilämpö +1,4 °C" kartan
   keskipisteen solusta. Ei uusia tasoja, ei uutta värilogiikkaa.
2. Napautustietoihin oma rivi samasta datasta ("tässä solussa kauden sade …").
3. Vasta lopuksi oma **sävytaso** (sininen = liian kuiva, valkoinen = normaali,
   ruskea = liian märkä) omana kytkettävänä tasonaan — eli juuri se
   "otollisuusväri", josta kysyit, mutta habitaattikartan *rinnalla* eikä sen
   päälle sotkettuna.

---

## 6. Mitä tämä ei voi kertoa

- **Havainto ei ole sato.** GBIF/Lajitietokeskus kertoo että joku löysi ja
  kirjasi sienen. Määrä riippuu myös siitä kuka oli metsässä, milloin oli
  viikonloppu, ja kirjoittiko lehti matsutakesta sinä syksynä. Siksi kaikki
  vuosivertailu tehdään **suhdelukuna** muihin sienihavaintoihin (sama
  target-group-ajatus kuin habitaattimallin taustapisteissä).
- **n ≈ 200 havaintoa ja ~22 vuotta** on vähän. Kolme säämuuttujaa on jo paljon;
  kymmenen olisi ylisovitusta, joka näyttää kartalla vakuuttavalta ja on väärin.
- **10 km:n hila ei näe kuuroa.** Elokuun sade Suomessa on kuurosadetta:
  naapuriruudussa voi olla 30 mm ja tässä 2 mm. Hila-anomalia kertoo kauden
  yleisen linjan, ei sitä mitä juuri sen harjun päälle satoi.
- **Ilmalämpötila ei ole maalämpötila.** Jäkäläkankaan pintamaa lämpenee ja
  jäähtyy eri tahtiin kuin ilma, ja juuri maalämpötilassa se 19 °C:n kynnys on.
  Ilmalämpötilasta laskettu korvike on korvike.
- **Shiro on monivuotinen ja oikukas.** Sama paikka voi jäädä satamatta hyvänä
  vuonna. Mikään säämalli ei korjaa sitä.
- **Kuluva kausi** on aina hilan ulkopuolella (hilat päättyvät edelliseen
  vuoteen), joten reaaliaikainen taso nojaa asemadataan ja on siksi
  karkeampi kuin historiallinen analyysi. Se on syytä sanoa käyttäjälle ääneen,
  samaan tapaan kuin hakkuukorjauksen kohdalla tehdään.

---

## 7. Lähteet

Laji ja ekologia:
- Vaario, L.-M., Savonen, E.-M., Peltoniemi, M., Miyazawa, T., Pulkkinen, P. &
  Sarjala, T. 2015. *Fruiting pattern of Tricholoma matsutake in Southern
  Finland.* Scandinavian Journal of Forest Research 30(4): 259–265.
  https://doi.org/10.1080/02827581.2015.1006246
- Vaario, L.-M. ym. 2010. *Ectomycorrhization of Tricholoma matsutake and two
  major conifers in Finland — an assessment of in vitro mycorrhiza formation.*
  Mycorrhiza. https://doi.org/10.1007/s00572-010-0304-8
- Bergius, N. & Danell, E. 2000. *The Swedish matsutake (Tricholoma nauseosum
  syn. T. matsutake): distribution, abundance and ecology.* Scand. J. For. Res.
  15: 318–325. https://doi.org/10.1080/028275800447940
- Yamanaka, K. ym. 2020. *Advances in the cultivation of the highly-prized
  ectomycorrhizal mushroom Tricholoma matsutake.* Mycoscience.
  https://www.sciencedirect.com/science/article/pii/S1340354020300012
  (19 °C:n itiöemäkynnys, shiron rakenne, viljelytutkimuksen tila)
- *Relationship between climate, expansion rate, and fruiting in fairy rings
  ('shiro') of Tricholoma matsutake in a Pinus densiflora forest.* Fungal
  Ecology 2015. https://www.sciencedirect.com/science/article/abs/pii/S1754504815000082
  (laajeneminen 0,17 m/v; lämpötila > sade)
- Tuoksuvalmuska, laji.fi MX.72541: https://laji.fi/taxon/MX.72541 ·
  Arktiset Aromit: https://www.arktisetaromit.fi/fi/sienet/luonnonsienet/tuoksuvalmuska/
- Matsutake Fennoskandiassa, Fungi Magazine 2016:
  https://www.fungimag.com/winter-2016-articles/LR_V8I5%20Matsutake.pdf

Menetelmä (sienisadon sääriippuvuus yleisesti):
- Karavani, A. ym. 2018. *Effect of climatic and soil moisture conditions on
  mushroom productivity…* Agric. For. Meteorol.
  https://www.sciencedirect.com/science/article/abs/pii/S0168192317303441
- Bonet, J. A. ym., sieni­satomallit *Pinus*-metsissä:
  https://link.springer.com/article/10.1186/s40663-019-0211-1

Aineistot:
- FMI:n hila-aineistot (funet/Paituli):
  https://www.nic.funet.fi/index/geodata/ilmatiede/
- FMI avoin data, WFS ja käyttöehdot (CC BY 4.0):
  https://www.ilmatieteenlaitos.fi/avoin-data
- Säähavaintojen hilamuotoiset arvot, avoindata.fi:
  https://www.avoindata.fi/data/fi/dataset/saahavaintojen-hilamuotoiset-kuukausiarvot
- Luke, DTW-kosteusindeksikartat:
  https://opendata.luke.fi/dataset/urn-nbn-fi-att-3403a010-b9d0-4948-8f9f-2bc4ca763897
- Syke, vesistömallijärjestelmä WSFS:
  https://ckan.ymparisto.fi/dataset/vesistomallijarjestelma-wsfs
- Metsäkeskus, metsävaratiedot ja korjuukelpoisuus:
  https://www.metsakeskus.fi/fi/avoin-metsa-ja-luontotieto/metsatietoaineistot/metsavaratiedot
