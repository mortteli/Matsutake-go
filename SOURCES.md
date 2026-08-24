# Lähdetutkimus: mihin Matsutake GO:n ehdot perustuvat?

Tämä dokumentti käy läpi, mitä julkaistu kirjallisuus sanoo tuoksuvalmuskan
(_Tricholoma matsutake_) kasvupaikkavaatimuksista Fennoskandiassa, ja vertaa
sitä siihen, mitä `index.html` tällä hetkellä suodattaa. Tarkoitus on tehdä
sovelluksen oletusarvot jäljitettäviksi ja merkitä näkyviin ne kohdat, joissa
kartta menee kirjallisuuden edelle tai ohi.

Kaikki väitteet on numeroitu lähdeluetteloon (`[L1]`…`[L10]`) alimpana.
Haut tehty 2026-08-23.

---

## 1. Mitä sovellus tällä hetkellä väittää

`index.html`-tiedoston oletusasetukset (`const settings`, rivi ~300) ja
info-paneelin teksti:

| # | Ehto | Oletus | MVMI-taso |
|---|---|---|---|
| E1 | Kasvupaikka kuiva kangas (CT) tai karukkokangas (ClT); kuivahko kangas (VT) valinnainen | luokat {5, 6}, VT pois päältä | `kasvupaikka_1923` |
| E2 | Kivennäismaa, ei suota | päätyyppi = 1 | `paatyyppi_1923` |
| E3 | Puuston ikä | ≥ 60 v (säädin 40–120) | `ika_1923` |
| E4 | Mäntytilavuus | ≥ 20 m³/ha (säädin 0–120) | `manty_1923` |
| E5 | *(tekstissä, ei suodattimena)* "jäkäläiset, valoisat ja hieman rinteiset paikat ovat parhaita" | — | napautustarkastelu / DEM |
| E6 | *(tekstissä)* "mitä pohjoisempana, sitä varmempi" | — | — |
| E7 | *(tekstissä)* satokausi: P-Suomi elo–syyskuu, E-Suomi syys–lokakuun alku | — | — |

---

## 2. Todistusaineisto ehdoittain

### 2.1 Isäntäpuu ja puulajijakauma

Fennoskandiassa laji on käytännössä männyn seuralainen. Ruotsissa Risbergin
72 tuoksuvalmuskametsikön aineistossa mänty muodosti **97 % pohjapinta-alasta
pohjoisessa ja 94 % etelässä**; 36:ssa 62:sta pohjoisesta kohteesta ei ollut
lainkaan muuta puulajia, ja lopuissa kuusta tai lehtipuuta oli 0,4–17,8 %
(vain neljässä yli 10 %) `[L2]`. IUCN:n arvioinnin mukaan laji on Euroopassa
mykorritsallinen nimenomaan _Pinus sylvestris_ -männyn kanssa `[L3]`.

**Mutta:** Suomessa on kuvattu myös **kuusibiotooppi**. Palmén erottaa
nimenomaisesti kaksi elinympäristöä, "the dry pine forest biotope" ja
"a spruce forest biotope", ja huomauttaa että geofysikaalinen kartoitusmenetelmä
löytää vain ensimmäisen `[L1]`. Vaarion tutkimusryhmän tuottoisin eteläsuomalainen
seurantakohde Nuuksiossa (60°18′16″N, 24°31′10″E, 100 × 135 m) oli
**_Pinus sylvestris_-, _Picea abies_- ja _Betula pendula_ -sekametsikkö**, jossa
kertyi 17 itiöemää 2008 ja 67 itiöemää 2009 `[L4]`. Suomalainen kanta muodosti
laboratoriossa Hartigin verkon sekä männylle että kuuselle, japanilainen kanta
vain männylle `[L7]`.

> **Seuraus kartalle:** E4 (mäntyä ≥ 20 m³/ha) + E1 (kuiva/karukkokangas) sulkee
> kuusibiotoopin rakenteellisesti pois. Se on tietoinen rajaus, ei virhe — mutta
> se kannattaa sanoa ääneen: Etelä-Suomen tunnetuimmat esiintymät eivät
> välttämättä näy kartalla lainkaan.

### 2.2 Kasvupaikan viljavuus

Risbergin ruotsalaisaineiston kasvillisuustyypit (n = 62, Pohjois-Ruotsi) `[L2]`:

| Ruotsalainen tyyppi | Suomalainen vastine (n. ottaen) | Kohteita |
|---|---|---|
| Lavtyp | karukkokangas ClT | 12 |
| Lavrik typ | kuiva kangas CT | 23 |
| Lingon | kuivahko kangas VT | 18 |
| Kråkbär/ljung | (variksenmarja-kanerva) | 8 |
| Blåbär | tuore kangas MT | 1 |

Risberg itse tiivistää: **85 % pohjoisista metsiköistä oli puolukkamailla tai
karummilla** ("på lingonmarker eller magrare"). Ståndortsindex oli 14–21 m,
eli karuja kasvupaikkoja. 56 kohdetta 62:sta luokiteltiin kuiviksi
(pohjavesi yli 2 m syvyydessä) `[L2]`. IUCN kuvaa elinympäristön Pohjois-Euroopassa
"dry, often lichen-dominated, sandy pine forests" ja "nutrient poor forests with
little litter accumulation" `[L3]`.

> **Seuraus kartalle:** sovelluksen oletus {CT, ClT} kattaa Risbergin aineistosta
> noin **56 %** (12 + 23 / 62). Kun kuivahko kangas (VT) otetaan mukaan, kattavuus
> nousee **85 %:iin**. Tämä on vahvin yksittäinen argumentti sille, että
> `chkKuivahko` kannattaisi olla **oletuksena päällä**, ei pois.

### 2.3 Maaperä ja emäkallio

- Sedimenttimaat: 58 kohdetta 62:sta Pohjois-Ruotsissa oli **jäätikköjoki- tai
  jokisedimentillä, pääosin hiekalla** `[L2]`.
- **Kalliomaat**: loput 4 pohjoista kohdetta olivat graniittisia kalliomaita, ja
  **eteläisistä kohteista 9/10 oli kalliomaata** (hällmark); kymmenes oli
  merenrantadyynimännikkö `[L2]`.
- Palmén: Skandinaviassa laji kasvaa runsaimmin niukkaravinteisissa
  mäntymetsissä, joissa on hiekkaa; yleisin suotuisan maaperän mineraali on
  **kalimaasälpä (KAlSi₃O₈)**, ja "Tricholoma matsutake will not grow in clayey
  soils" `[L1]`.
- Orgaaninen kerros on ohut: Lapissa "usually only some centimeters in
  thickness", mikä erottaa Fennoskandian osasta Japanin kasvupaikoista, joissa
  paksu karike vaurioittaa itiöemiä niiden työntyessä pintaan `[L1]`.

> **Seuraus kartalle:** MVMI:n kasvupaikkaluokka **7 = kalliomaat ja hietikot**
> `[L9]` on nyt suodatettu kokonaan pois. Risbergin eteläisen Ruotsin aineiston
> perusteella se on siellä *päähabitaatti*. Suomessa vastaavia karuja kallio- ja
> harjumänniköitä on runsaasti. Luokka 7 kannattaisi lisätä valinnaiseksi
> ruksiksi `chkKuivahko`-tyyliin. Huomaa että luokka 7 voi olla myös kitu- tai
> joutomaata `[L9]`, jolloin puustotunnukset ovat epävarmempia.

### 2.4 Puuston ikä ja puujatkumo

Tämä on aineiston vahvin numeerinen tulos `[L2]`:

| | Pohjois-Ruotsi (n=62) | Etelä-Ruotsi (n=10) |
|---|---|---|
| Metsikön keski-ikä | **115 v** (51–213) | **148 v** (105–178) |
| Vanhimman puun ikä (ka.) | 175 v (62–356) | 205 v (125–305) |

Niistä 14 metsiköstä, joissa sekä keski-ikä että vanhin puu jäivät alle 100
vuoden, 12:lle voitiin vanhoista ilmakuvista varmistaa katkeamaton puujatkumo.
Yhteensä **70/72 metsiköllä oli varmuudella puujatkumo** `[L2]`. IUCN toteaa
lajin esiintyvän "preferentially … in old-growth forests, especially in
northern Fennoscandia", ja nimeää suurimmaksi uhaksi vanhojen männiköiden
avohakkuun `[L3]`.

Risbergin oma käytännön ohje esiintymien etsijälle, tärkeysjärjestyksessä:

> "Jordmån/växtsamhälle (sand/lingon eller fattigare) > breddgrad (>65º) >
> beståndsålder (>50 år)" `[L2]`

Huom. kaksi tarkennusta:

1. **Itiöemien runsaus ei korreloinut metsän iän kanssa** — runsaita esiintymiä
   löytyi kaikista ikäluokista, myös nuorimmista `[L2]`. Ikä on siis
   *läsnäolon* ennuste, ei *sadon* ennuste.
2. Japanissa kuva on toinen: 41 vuoden seurannassa (_Pinus densiflora_, Nagano)
   hoidetun koealan huippusato 2 536 itiöemää/ha saavutettiin, kun isäntäpuut
   olivat noin **57–72-vuotiaita** `[L8]`. Eri mäntylaji, eri ilmasto ja
   intensiivinen hoito (harvennus 3 700 → 1 925 runkoa/ha, karikkeenpoisto), joten
   lukua ei voi siirtää sellaisenaan Suomeen — mutta se muistuttaa, ettei "mitä
   vanhempi sen parempi" ole universaali laki.

> **Seuraus kartalle:** ≥ 60 v on **puolustettavissa alarajana** (Risbergin
> minimi oli 51 v ja hänen suosituksensa > 50 v). Se ei kuitenkaan kuvaa
> tyypillistä esiintymää: mediaanikohde on 100–150-vuotias. Säätimen voisi
> ankkuroida näkyvästi tähän, esim. merkinnällä "60 v = alaraja, 100 v = tyypillinen".

### 2.5 Puuston tiheys ja latvuspeittävyys

Sovelluksen infoteksti sanoo "valoisat" paikat parhaiksi, ja README puhuu
"vanhoista ja harvoista puustoista". **Ruotsalaisaineisto ei tue tätä.**
Risberg vertasi tuoksuvalmuskametsiköiden massaslutenhetia
Riksskogstaxeringenin vastaaviin (kuivat maat, lav/lavrik/lingon, SI 14–21) ja
tulos oli päinvastainen kuin oletettiin:

> "Det går inte att se att goliatmusseron föredrar något mer öppna skogar,
> vilket var en teori. … De bestånd jag undersökte finns snarare till något
> större andel i de högre slutenhetsklasserna" `[L2]`

Hän pitää tulosta itsekin yllättävänä ja epäilee metodieroa; otos etelässä oli
vain 10 kohdetta. IUCN puolestaan kuvaa Itä-Aasian kasvupaikat "fairly open"
`[L3]`, ja Japanin pitkäaikaiskokeessa harvennus paransi satoa selvästi `[L8]`.

> **Seuraus kartalle:** "valoisat paikat" on rehellisintä merkitä
> **epävarmaksi** — se on Aasian metsänhoidosta ja kansanperinteestä, ei
> pohjoismaisesta aineistosta. Latvuspeittävyys on MVMI:ssä olemassa
> (`latvuspeittavyys_*`), joten sitä *voisi* kokeilla suodattimena, mutta
> kirjallisuus ei kerro mihin raja pitäisi vetää.

### 2.6 Aluskasvillisuus ja karike

Vaario ym. inventoivat eteläsuomalaisella tuottoisalla kohteella 15 ruutua,
joissa itiöemiä oli muodostunut peräkkäisinä vuosina, ja 15 verrokkiruutua
ilman itiöemiä. Itiöemäruuduilla **kokonaiskasvipeite oli selvästi pienempi ja
karikepeite hieman suurempi**; karikkeesta peräisin oleva hiili tulkittiin
myönteiseksi tekijäksi, mikä varmistettiin in vitro `[L6]`. Japanin
41-vuotisseurannassa hoitamattoman koealan orgaaninen kerros oli 2021 mennessä
**1,4-kertainen** hoidettuun verrattuna, ja sato pienempi `[L8]`.

> **Seuraus kartalle:** aluskasvillisuuden peittävyyttä ja humuskerroksen
> paksuutta **ei ole MVMI:ssä**, eikä muutakaan valtakunnallista rasteria näistä
> ole tiedossa. Tämä jää maastossa tarkistettavaksi. Nykyinen infoteksti
> ("maastossa ratkaisee lopulta jäkälä, maasto ja tuuri") on tältä osin oikein.

### 2.7 Rinne ja ilmansuunta

Tässä sovellus on **ristiriidassa lähteiden kanssa**. Infotekstin mukaan
"hieman rinteiset" paikat ovat parhaita ja napautustarkastelu laskee
"pohjoisuusarvion".

- Ruotsissa esiintymät ovat **tasaisilla tai pienipiirteisesti kumpuilevilla
  jäätikköjokisedimenteillä**, 0–450 m mpy. Risberg kirjoittaa suoraan, että
  Aasian jyrkät rinteet johtuvat siitä, että metsä siellä yksinkertaisesti
  *on* rinteillä `[L2]`.
- IUCN kuvaa Itä-Aasian metsiköt "fairly open, and often **south-west-facing**"
  `[L3]` — eli vastakkaiseen suuntaan kuin sovelluksen pohjoisuusarvio.
- Suomalaisissa populaarilähteissä toistuu maininta pohjoisrinteistä, mutta
  **en löytänyt sille vertaisarvioitua lähdettä** (ks. §5).

> **Seuraus kartalle:** rinne- ja pohjoisuusarvio kannattaa joko poistaa
> arviosta tai merkitä selvästi "ei lähdetukea Fennoskandiassa". Se on
> tällä hetkellä kartan heikoimmin perusteltu ehto.

### 2.8 Maantieteellinen jakauma

Suomen Lajitietokeskuksen (FinBIF) havaintoaineistossa lajilla MX.72541 on
**401 havaintoyksikköä**, jotka jakautuvat 19 eliömaakuntaan `[L10]`:

| Eliömaakunta | Havaintoja | | Eliömaakunta | Havaintoja |
|---|---|---|---|---|
| Inarin Lappi | 74 | | Etelä-Häme | 17 |
| Oulun Pohjanmaa | 40 | | Pohjois-Savo | 16 |
| Perä-Pohjanmaa | 40 | | Etelä-Savo | 12 |
| Kainuu | 32 | | Satakunta | 10 |
| Uusimaa | 31 | | Keski-Pohjanmaa | 9 |
| Koillismaa | 30 | | Kittilän Lappi | 8 |
| Varsinais-Suomi | 26 | | Etelä-Karjala | 5 |
| Pohjois-Karjala | 25 | | Pohjois-Häme | 2 |
| Sompion Lappi | 19 | | Ahvenanmaa, Etelä-Pohjanmaa | 1 kumpikin |

Painopiste on selvästi pohjoisessa (Lappi + Koillismaa + Kainuu + Pohjanmaa
≈ 250/398), mikä tukee infotekstin väitettä E6 ja Risbergin leveysaste-kriteeriä
(> 65°) `[L2]`. Silti Uusimaa (31) ja Varsinais-Suomi (26) ovat kärkikymmenikössä
— osin havainnointiaktiivisuuden vinouma, osin todellinen eteläinen
kalliomaa- ja kuusibiotooppi.

Huomaa myös, ettei "pohjoinen on parempi" ole tällä hetkellä kartalla millään
tavalla näkyvissä: pinkki pikseli Uudellamaalla ja Inarissa näyttävät
identtisiltä. Leveysasteen mukainen sävytys olisi halpa ja lähteillä
perusteltu lisäys.

### 2.9 Satokausi

Vaario ym. seurasivat itiöemien muodostusta eteläsuomalaisella kohteella
2008–2013 ja raportoivat sadon ajoittuvan **heinäkuun puolivälistä syyskuun
puoliväliin** `[L5]`. He eivät löytäneet selkeää korrelaatiota sateeseen, mutta
keskimääräinen sademäärä (90–110 % pitkän ajan keskiarvosta) ennen ensimmäistä
itiöemää oli tärkeä; maaperän lämpötilalle ei löytynyt kynnysarvoa, mutta
korkea maaperälämpötila ennen ensimmäistä satoa ennakoi lyhyempää satokautta
`[L5]`.

> **Seuraus kartalle:** infotekstin "Etelä-Suomi: syyskuu – lokakuun alku"
> vaikuttaa **liian myöhäiseltä ja liian kapealta** ainoan julkaistun
> eteläsuomalaisen seurannan perusteella. Heinäkuun loppu kannattaa ottaa
> mukaan.

---

## 3. Aineiston tarkkuus — tärkein varaus

Luken MVMI-tuotekuvaus antaa kuva-alkiotason keskivirheet `[L9]`
(ES = Etelä-Suomi, PS = Pohjois-Suomi, kiv = kivennäismaa):

| Teema | ES/kiv | PS/kiv | Yksikkö | Sovelluksen kynnys |
|---|---|---|---|---|
| Puuston ikä | **32** | **49** | v | 60 v |
| Mäntytilavuus (kaikki puutavaralajit) | **63** | **41** | m³/ha | 20 m³/ha |

Eli **yhden 16 m pikselin ikävirhe on samaa suuruusluokkaa kuin koko
kynnysarvo**, ja mäntytilavuuden virhe on eteläisessä Suomessa kolminkertainen
kynnykseen nähden. Luokkamuuttujat eivät ole parempia:

- Kasvupaikkateema: **noin 50 %** kuva-alkioista saa saman luokan kuin VMI:n
  maastoluokitus. Luke nimeää eron olevan yleisin juuri "karuilla
  kasvupaikoilla, karukkokankailla" — eli täsmälleen niissä luokissa, joiden
  varaan tämä kartta rakentuu. Ero on tosin useimmiten vain yhden luokan
  suuruinen `[L9]`.
- Päätyyppi (kangas/korpi/räme/avosuo): luokka oikein **84 %**:lla
  kuva-alkioista; kankaiksi luokitelluista **95 %** on maastossakin kangasta
  `[L9]`.
- Luke korostaa, että aluetason pinta-alaestimaattien virheet ovat näitä
  pienempiä `[L9]`.

> **Seuraus kartalle:** yksittäinen värillinen pikseli on kohinaa. **Rypäs**
> värillistä pikseliä on signaali. Tämä kannattaa sanoa infotekstissä suoraan, ja
> se on myös hyvä argumentti sille, että kasvupaikkaluokan yhden luokan
> löysääminen (VT mukaan) ei ole "huijaamista" vaan aineiston epävarmuuden
> huomioimista. Vaihtoehtoisesti kompositiovaiheeseen voisi lisätä
> naapurustoenemmistön (esim. vaadi että ≥ 5/9 naapuripikseliä täyttää ehdot).

Yksi rakenteellinen tarkennus: kasvupaikkaluokat 1–6 tarkoittavat
kivennäismailla lehtoa … karukkokangasta, mutta **soilla samat numerot
tarkoittavat soiden viljavuusluokkia** (1 = lehtomaiset ja lettosuot … 6 =
rahkaiset suot) `[L9]`. Sovellus tekee tässä oikein vaatiessaan
`paatyyppi = 1` — ilman sitä rahkaiset suot (kasvupaikka 6) valuisivat mukaan
karukkokankaina.

---

## 4. Yhteenveto: ehto kerrallaan

| Ehto | Lähdetuki | Tuomio | Mitä tehtiin |
|---|---|---|---|
| E1 kuiva + karukkokangas | `[L2]` `[L3]` | **Oikea suunta, liian tiukka** | ✅ Kuivahko kangas (VT) oletuksena päälle → kattavuus 56 % → 85 % `[L2]`; painaa reunaluokkana vähemmän |
| E1b kalliomaat (luokka 7) pois | `[L2]` `[L11]` | **Puuttuva habitaatti** | ✅ Lisätty ydinluokkana, oletuksena päällä |
| E2 kivennäismaa | `[L1]` `[L9]` | **Vahva** | ✅ Säilytetty sellaisenaan |
| E3 ikä ≥ 60 v | `[L2]` `[L3]` | **Puolustettavissa alarajana** | ✅ 60 v säilyi alarajana; iästä tuli portaittainen pisteyttäjä (85 v, 110 v) |
| E4 mänty ≥ 20 m³/ha | ei suoraa lähdettä | **Heikko muotoilu** | ⬜ Jätettiin ennalleen. Mäntyosuus (Ruotsissa 94–97 % pohjapinta-alasta `[L2]`) vaatisi kahden rasterin suhteen, mikä ei taivu maskikompositioon |
| E5 rinne / pohjoisuus | `[L2]` `[L3]` | **Ei lähdetukea, osin ristiriidassa** | ✅ Poistettu pisteytyksestä, jäi neutraaliksi lukemaksi |
| E5b "valoisat" / harva puusto | `[L2]` | **Kirjallisuus sanoo päinvastaista** | ✅ Poistettu README:stä ja infotekstistä |
| E6 pohjoisuus parempi | `[L2]` `[L10]` | **Vahva** | ✅ Ylin luokka (4/4) varattu 63° N:n pohjoispuolelle |
| E7 satokausi | `[L5]` | **Etelä-Suomen ikkuna liian myöhäinen** | ✅ Laajennettu heinäkuun loppuun |
| — kuusibiotooppi | `[L1]` `[L4]` `[L7]` | **Kartan sokea piste** | ⬜ Yhä sokea piste; oma projektinsa |
| — pikselitarkkuus | `[L9]` | **Ei mainita lainkaan** | ✅ Lisätty infopaneeliin ja napautustulokseen |

---

## 5. Mitä ei löytynyt

Rehellisyyden vuoksi — nämä ovat aukkoja, eivät todistettuja negatiivisia:

- **Pohjoisrinteet.** Suomalaisissa populaarilähteissä toistuva maininta
  pohjoisrinteistä ei löytynyt mistään vertaisarvioidusta lähteestä. IUCN:n
  ainoa ilmansuuntamaininta koskee Itä-Aasiaa ja on *lounaaseen* `[L3]`.
- **Numeerinen mäntytilavuuden kynnys.** Mikään lähde ei anna m³/ha-rajaa.
  20 m³/ha on sovelluksen oma valinta ja käytännössä tarkoittaa "täällä on
  mäntyä".
- **Suomalainen paikkatietopohjainen habitaattimalli.** Etsin MVMI- tai
  Metsäkeskus-aineistoon perustuvaa julkaistua tuoksuvalmuskan
  habitaattimallia; sellaista ei löytynyt. Tämä sovellus näyttää olevan
  ensimmäinen laatuaan, mikä on samalla syy suhtautua sen tuloksiin varauksella.
- **Lähteet, joita ei saatu luettua:** arktisetaromit.fi (botti­suojaus),
  laji.fi:n biologiakuvaus (JS-renderöity sivu; havaintodata saatiin API:sta),
  Scandinavian Journal of Forest Research -kokoteksti (HTTP 403 — §2.9 nojaa
  indeksoituun tiivistelmään), Artfakta (ei haettu suoraan).

## 6. Mitä MVMI-aineistosta itsestään mitattiin

Ehtojen virittämiseksi otantana ajettiin WMS:stä 4 km × 4 km ikkunoita
natiivilla 16 m tarkkuudella (4 ikkunaa aluetta kohti) `[L11]`. Tämä oli
tarpeen, koska karkeammalla otannalla GeoServerin uudelleennäytteistys
tasoittaa ääripäät pois — ensimmäinen yritys 750 m/pikseli väitti, ettei
Lapissa ole lainkaan yli 100-vuotiaita metsiä.

**Kasvupaikkaluokkien osuudet kivennäismaalla:**

| Alue | 4 kuivahko | 5 kuiva | 6 karukko | 7 kalliomaa |
|---|---|---|---|---|
| Lappi | 56,0 % | 35,6 % | 0,0 % | 8,4 % |
| Kainuu / Koillismaa | 90,0 % | 9,9 % | 0,0 % | 0,1 % |
| Etelä-Suomi | 52,3 % | 1,6 % | 0,0 % | 46,1 % |

Kaksi tulosta muuttivat suunnittelua:

1. **Karukkokangas (6) on käytännössä olematon MVMI:ssä** — 0,0 % kaikilla
   kolmella alueella. Sovelluksen "karukkokangas"-kytkin ei siis juuri tee
   mitään. Tämä sopii Luken omaan varaukseen, että luokitusero on yleisin
   juuri karukkokankailla `[L9]`: malli ei käytännössä uskalla antaa
   ääriluokkaa.
2. **Kalliomaat (7) ovat Etelä-Suomessa 46 % kuivasta kivennäismaasta.**
   Yhdessä Risbergin havainnon kanssa (9/10 eteläistä kohdetta hällmarkia
   `[L2]`) tämä teki luokan 7 lisäämisestä selvästi tärkeimmän yksittäisen
   laajennuksen — ilman sitä Etelä-Suomen päähabitaatti puuttuu kartalta.

**Puuston ikä perusehdot täyttävillä ruuduilla** (osuus ehdot täyttävistä):

| Alue | 60–80 v | 80–100 v | 100–120 v | yli 120 v |
|---|---|---|---|---|
| Lappi | 55,3 % | 35,6 % | 8,5 % | 0,5 % |
| Kainuu / Koillismaa | 54,6 % | 28,0 % | 12,5 % | 4,9 % |
| Etelä-Suomi | 42,5 % | 33,8 % | 17,8 % | 6,0 % |

Tämä on syy siihen, miksi pisteytyksen ikäportaat ovat **85 v ja 110 v**
eivätkä kirjallisuuden 115–148 v: MVMI:n ikä on regressioennuste, joka vetää
ääripäät kohti keskiarvoa, joten kentältä mitattuja lukemia ei voi käyttää
kynnyksinä. Portaat on viritetty aineiston omaan jakaumaan niin, että
kaikki neljä väriluokkaa esiintyvät. Väriasteikko koodaa **järjestyksen,
ei vuosilukua**.

Huomaa myös, että ikäjakauma on **vanhin etelässä**. Ilman leveysasteen
huomiointia kartta värittäisi Uudenmaan kirkkaimmin ja Lapin tummimmin —
päinvastoin kuin havainnot jakautuvat `[L10]`. Siksi ylin luokka on varattu
63° N:n pohjoispuolelle: se on kevyin tapa koodata Risbergin järjestys
(maaperä > leveysaste > ikä `[L2]`) hävittämättä eteläisiä esiintymiä,
joita FinBIF:ssä on todellisuudessa yhtä paljon kuin Kainuussa.

## 7. Mahdollinen uusi aineistolähde

Palménin kuvaama menetelmä — **lentogeofysikaalinen gammasäteilykartoitus**,
jossa etsitään korkean ⁴⁰K:n sekä matalan Th:n ja U:n alueita eli
kalimaasälpärikkaita hiekkoja ja moreeneja ohuen orgaanisen kerroksen alla
`[L1]` — on Suomessa periaatteessa saatavilla: GTK:n aerogeofysikaaliset
aineistot kattavat maan. Menetelmällä on lähteen mukaan kaksi rajoitusta:
se löytää vain kuivan mäntybiotoopin, ja paksu orgaaninen kerros peittää
signaalin `[L1]`. Tämä olisi lähtökohtaisesti riippumaton ja kirjallisuudessa
nimenomaisesti tuoksuvalmuskan etsintään ehdotettu lisäkerros nykyisen
MVMI-komposition rinnalle.

---

## Lähteet

**[L1]** Palmén, J. 2016. *Matsutake: mushroom of the year – or millenium?
A Finnish and Scandinavian perspective.* FUNGI Magazine 8(5), Mid-Winter 2016,
s. 40–47. Societas Mycologica Fennica.
<https://www.fungimag.com/winter-2016-articles/LR_V8I5%20Matsutake.pdf>

**[L2]** Risberg, L. *Goliatmusseron (Tricholoma matsutake) – kräver den en
kontinuitet av träd?* Examensarbete inom Naturresursprogrammet, huhtikuu 2003.
Institutionen för skoglig mykologi och patologi, Sveriges Lantbruksuniversitet,
Uppsala. Ohjaajat Anders Dahlberg, Eric Danell, Johan Nitare.
<https://stud.epsilon.slu.se/12882/1/risberg_l_171121.pdf>
— *Fennoskandian laajin julkaistu kasvupaikka-aineisto: 72 metsikköä (62 Pohjois-Ruotsi, 10 Etelä-Ruotsi).*

**[L3]** IUCN Red List -arviointi, *Tricholoma matsutake*.
<https://redlist.info/iucn/species_view/307044>

**[L4]** Vaario, L.-M. ym. 2011. *Tricholoma matsutake Dominates Diverse
Microbial Communities in Different Forest Soils.* Applied and Environmental
Microbiology 77(24). <https://pmc.ncbi.nlm.nih.gov/articles/PMC3233081>

**[L5]** Vaario, L.-M. ym. 2015. *Fruiting pattern of Tricholoma matsutake in
Southern Finland.* Scandinavian Journal of Forest Research 30(4): 259–265.
doi:10.1080/02827581.2015.1006246 — *kokotekstiä ei saatu (HTTP 403);
viittaukset perustuvat indeksoituun tiivistelmään.*

**[L6]** Vaario, L.-M. ym. 2013. *The influences of litter cover and understorey
vegetation on fruitbody formation of Tricholoma matsutake in southern Finland.*
Applied Soil Ecology 66: 56–60.

**[L7]** Vaario, L.-M. ym. 2010. *Ectomycorrhization of Tricholoma matsutake and
two major conifers in Finland — an assessment of in vitro mycorrhiza formation.*
Mycorrhiza 20(7). doi:10.1007/s00572-010-0304-8
<https://link.springer.com/article/10.1007/s00572-010-0304-8>

**[L8]** *Long-term effects of forest management on the dynamics of Tricholoma
matsutake harvest over 41 years in a Pinus densiflora forest in Nagano
Prefecture, Japan.* Mycoscience 65(6), 2024.
<https://www.jstage.jst.go.jp/article/mycosci/65/6/65_MYC649/_html/-char/en>

**[L9]** Luonnonvarakeskus. *Monilähteisen valtakunnan metsien inventoinnin
(MVMI) kartta-aineisto* — tuotekuvaus (LUKE_vmi2019.pdf): kasvupaikka- ja
päätyyppiluokitukset sekä kuva-alkiotason virhearviot.
<http://geoportal.ymparisto.fi/meta/julkinen/dokumentit/LUKE_vmi2019.pdf>
Aineistokuvaus: <https://opendata.luke.fi/fi/dataset/urn-nbn-fi-fd-849cabd2-0ae5-3455-b6f3-a39086cce33c>

**[L10]** Suomen Lajitietokeskus (FinBIF), taksoni MX.72541 *Tricholoma
matsutake*, havaintomäärät eliömaakunnittain. Haettu API:n kautta 2026-08-23
(`laji.fi/api/taxa/MX.72541`, `laji.fi/api/warehouse/query/unit/count`).
<https://laji.fi/taxon/MX.72541>

**[L11]** Tätä työtä varten tehty otanta Luken MVMI-WMS:stä
(`kartta.luke.fi/geoserver/MVMI/wms`), 4 km × 4 km ikkunat natiivilla 16 m
tarkkuudella, 4 ikkunaa kolmella alueella (Lappi, Kainuu/Koillismaa,
Etelä-Suomi), ajettu 2026-08-24. Ei julkaistu lähde vaan tämän repon oma
mittaus; luvut on tarkoitettu ehtojen virittämiseen, ei tilastolliseksi
estimaatiksi koko maasta.
