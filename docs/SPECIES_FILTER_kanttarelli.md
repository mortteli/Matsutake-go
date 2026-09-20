# Kanttarellin suodatin, mitattuna

Kanttarellin ehdot olivat sovelluksen heikoimmat, ja sovellus sanoi sen itsekin ääneen:
laji on yleislaji, kartta värittää eteläisessä Suomessa neljänneksen metsistä, ja tietosivu
kehotti kiristämään säätimiä — antamatta säädintä, joka olisi aidosti kiristänyt.

Tämä dokumentti on se mittaus, jota kehotus kaipasi: mitä kanttarellihavainnot erottaa
viereisestä metsästä, mitä ei erota, ja mitä ehdoille sen perusteella tehtiin.

## Menetelmä

Sama idea kuin muidenkin lajien oletusrajoissa (README, "Mistä oletusrajat tulevat"), mutta
suuremmalla aineistolla ja kolmella verrokkijoukolla yhden sijaan.

| Joukko | n | Mistä |
|---|---|---|
| **havainnot** | 393 | GBIF, *Cantharellus cibarius*, Suomi, paikannustarkkuus ≤ 100 m, 2010– |
| **verrokki (kohdistettu)** | 373 | satunnainen metsämaapiste 2–5 km havainnosta — sama seutu, eri metsä |
| **verrokki (sienestäjät)** | 428 | muita sienihavaintoja elo–syyskuulta: missä poimijat oikeasti kulkevat |
| **verrokki (satunnainen)** | 452 | tasajakauma metsämaalta koko maasta — paljonko karttaa väritetään |

GBIF antoi 2 747 tietuetta, joista 1 276 täytti tarkkuus- ja vuosiehdon. Niistä pidettiin yksi
per 100 m ruutu (1 227), koska samaa apajaa käydään kirjaamassa vuosi toisensa jälkeen eikä
yksi paikka saa äänestää monta kertaa; otokseen arvottiin 500, joista 393 osui metsämaalle.

Kaikki pisteet luettiin MVMI:n 2023-kierroksesta suoraan Paitulin GeoTIFF-tiedostoista
(`ml/core/grid.py`:n `luke_url`), samoista tasoista jotka kartta kysyy WMS:ltä.

**Kolme verrokkia, koska ne vastaavat eri kysymykseen.** Kohdistettu verrokki kertoo, erottaako
suodatin kanttarellimetsän *naapurimetsästä* — se on rehellisin mitta, koska se ei palkitse
suodatinta siitä, että havainnot ovat etelässä ja asutuksen lähellä. Sienestäjäverrokki kysyy,
löytääkö suodatin kanttarellimetsää vai pelkkää *helppopääsyistä* metsää. Satunnaisverrokki ei
mittaa osuvuutta lainkaan vaan pinta-alaa: kuinka suuri osa metsämaasta värittyy.

> **Verrokin rajaus ratkaisee luvun.** Metsämaalle rajattuna vanhat oletukset saavat
> kohdistettua verrokkia vastaan kertoimen 1,5×. Jos verrokkipisteitä ei rajata metsämaalle —
> jolloin järvi, pelto ja piha lasketaan "verrokiksi, jonka suodatin hylkäsi" — sama suodatin
> saa 2,8×. Tässä on rajattu, koska kartan käyttäjä ei ole valitsemassa metsän ja järven vaan
> metsän ja metsän väliltä. README:n aiempi 6,5× on mitattu 45 havainnolla ja 45
> verrokkipisteellä; rajaus selittää osan erosta, otoskoko oletettavasti loput.

## Mikä erottaa, mikä ei

Yksittäiset ehdot, koko maa. "osuvuus" = havainnot ÷ kohdistettu verrokki.

| Ehto | havainnoista | kohdistetusta verrokista | osuvuus |
|---|---|---|---|
| kasvupaikka 2–4 | 92 % | 91 % | **1,01×** |
| kivennäismaa | 97 % | 88 % | 1,11× |
| latvuspeitto ≥ 55 % | 81 % | 70 % | 1,15× |
| isäntäpuu-unioni ≥ 40 m³/ha *(vanha)* | 94 % | 77 % | 1,22× |
| ikä ≥ 40 v | 83 % | 64 % | 1,29× |
| **koivua ≥ 20 m³/ha** | 41 % | 43 % | **0,95×** |
| tilavuus ≥ 150 m³/ha | 68 % | 46 % | 1,50× |
| kuusta ≥ 70 m³/ha | 44 % | 28 % | 1,60× |
| **kuusta ≥ 110 m³/ha** | 34 % | 16 % | **2,19×** |

Kaksi tulosta kannattaa lukea kahdesti.

**Kasvupaikkaluokka ei erottele kanttarellia lainkaan.** Se oli suodattimen ensimmäinen ehto, ja
se päästää läpi 92 % havainnoista ja 91 % verrokkipisteistä — eli suunnilleen kaiken metsämaan.
Muilla lajeilla ehto tekee työtä; tällä se on koriste.

**Koivu on isäntäpuuna hieman verrokkien puolella** (41 % vs. 43 %). Se ei tarkoita, etteikö
kanttarelli olisi koivun kumppani — se on — vaan ettei koivun määrä erottele kanttarellimetsää
muusta metsästä. Unionissa tällä on tavallista pahempi seuraus: **OR päästää solun läpi heti kun
yksi jäsen päästää**, joten unionin valikoivuuden määrää sen heikoin jäsen. Kolmen puulajin
unioni ≥ 40 m³/ha päästi läpi 94 % havainnoista ja 77 % verrokista.

## Mitä tilalle

Unionin ja tiheän latvuspeiton tilalle **koko puuston tilavuus** — ainoa yksittäinen taso, joka
sekä erottelee että on ilmaistavissa kartan maskeina (maskit ovat tasokohtaisia raja-arvoja,
joten `kuusi + mänty ≥ X` ei ole ilmaistavissa, `tilavuus ≥ X` on).

| | havainnoista | kohdistettu | sienestäjät | satunnainen (= ala) | osuvuus |
|---|---|---|---|---|---|
| vanhat oletukset | 65 % | 44 % | 49 % | 30 % | 1,49× |
| **uudet oletukset** | 60 % | 37 % | 40 % | **18 %** | **1,62×** |
| uudet + *Vain kuusivaltaiset* | 32 % | 14 % | 20 % | 9 % | **2,32×** |

Uudet oletukset: kasvupaikka 2–4 · kivennäismaa · ikä ≥ 40 v · latvuspeitto ≥ 40 % ·
**tilavuus ≥ 150 m³/ha**. Latvuspeiton oletus laskettiin 55 %:sta 40 %:iin, koska tilavuusehdon
rinnalla se ei enää karsi mitään (luvut ovat identtiset sen kanssa ja ilman) — säädin jää
paikalleen niille, jotka laskevat tilavuusrajaa.

### Ja se mitä tämä *ei* korjaa

Etelä-Suomi on lajin ydinaluetta ja siellä valtaosa metsästä ylittää 150 m³/ha jo valmiiksi.
Eteläisillä pisteillä (lat < 62°, 286 havaintoa) erikseen mitattuna:

| | havainnoista | kohdistettu | sienestäjät | osuvuus |
|---|---|---|---|---|
| vanhat oletukset | 67 % | 47 % | 60 % | 1,44× |
| uudet oletukset | 64 % | 42 % | 57 % | 1,52× |
| *Vain kuusivaltaiset* | 36 % | 15 % | 25 % | **2,31×** |

20 km:n ruutu Nuuksion yllä värittyy vanhoilla oletuksilla 44-prosenttisesti ja uusilla
43-prosenttisesti. **Oletusten parannus on siis todellinen mutta vaatimaton, ja se tulee
pääosin Keski- ja Pohjois-Suomesta.** Se ehto, joka Etelä-Suomessa aidosti kiristää, on
kuusivaltaisuus — ja se maksaa reilusti yli puolet löydöistä, joten se on säädin eikä oletus.
Tämä sanotaan myös lajin tietosivulla: yleislajin karttaa ei saa yhtä aikaa kapeaksi ja
rehelliseksi.

## Tekevätkö säätimet mitään? — säädinkäyrät

Tietosivu kehotti ennen kiristämään säätimiä, ja README väitti että kiristäminen romahduttaa
osuvuuden (6,5× → 3,5×). Kumpaakaan ei ollut mitattu. Tässä on jokaisen säätimen koko matka,
muut ehdot oletuksissaan. "osuvuus" = havainnot ÷ kohdistettu verrokki.

**Vanha isäntäpuusäädin** (muut ehdot vanhoissa oletuksissaan):

| säädin | havainnoista | verrokista | ala | osuvuus |
|---|---|---|---|---|
| 0 / 20 / **40** *(vanha oletus)* | 65 % | 44 % | 30 % | **1,49×** |
| 60 | 64 % | 41 % | 27 % | 1,55× |
| 80 | 57 % | 37 % | 20 % | 1,56× |
| 100 | 50 % | 29 % | 16 % | 1,75× |
| 120 | 40 % | 23 % | 13 % | 1,75× |
| 150 | 25 % | 14 % | 8 % | 1,83× |

**Uusi tilavuussäädin** (muut ehdot uusissa oletuksissaan):

| säädin | havainnoista | verrokista | ala | osuvuus |
|---|---|---|---|---|
| 0 / 50 | 73 % | 50 % | 43 % | 1,45× |
| 100 | 70 % | 49 % | 34 % | 1,42× |
| **150** *(uusi oletus)* | 60 % | 37 % | 18 % | **1,62×** |
| 200 | 40 % | 23 % | 12 % | 1,72× |
| 250 | 24 % | 13 % | 6 % | **1,94×** |
| 300 | 12 % | 6 % | 4 % | 1,82× |

Kolme johtopäätöstä, joista kaksi oikaisee aiempaa käsitystä.

**1. Vanha säädin ei ollut rikki — sen oletus oli.** Isäntäpuuraja 0, 20 ja 40 antavat täsmälleen
saman kartan: säädin oli tasannetta koko alaosaltaan, ja oletus 40 istui keskellä sitä. Ylöspäin
työnnettynä se kyllä toimi (1,83× arvolla 150). Vika ei siis ollut siinä, ettei säädin tehnyt
mitään, vaan siinä että *oletusasento* ei tehnyt mitään. Uusi säädin on samanmuotoinen —
tasannetta 0–100 — mutta sen oletus on tasanteen yläpuolella.

**2. Kiristäminen ei romahduta osuvuutta, vaan parantaa sitä.** Jokainen säädin nostaa osuvuutta
kiristettäessä. README:n vanha 6,5× → 3,5× ei pidä tällä aineistolla paikkaansa, ja se väite on
poistettu.

**3. Säätimet eivät ole uuden myötä *laadullisesti* tuottavampia.** Samalla
löytöosuudella vanha ja uusi ovat käytännössä tasoissa: isäntäpuu 120 antaa 40 % / 1,75×, tilavuus
200 antaa 40 % / 1,72×. Uusi säädin yltää hieman korkeammalle (1,94× vs. 1,83×) ja sen asteikko on
tulkittavissa (koko puuston m³/ha, ei "kolmen puulajin suurin"), mutta varsinainen parannus on
oletuksen sijainti, ei vipu itse. Näin se on myös sanottu.

### Tehokkain säädin ei ole se, jota vaihdoin

| ikäsäädin (uusilla oletuksilla) | havainnoista | verrokista | ala | osuvuus |
|---|---|---|---|---|
| 0 / 20 | 65 % | 39 % | 19 % | 1,66× |
| **40** *(oletus)* | 60 % | 37 % | 18 % | 1,62× |
| 60 | 42 % | 22 % | 12 % | **1,90×** |
| 80 | 22 % | 9 % | 6 % | **2,36×** |
| 100 | 6 % | 3 % | 2 % | 1,83× |

| latvuspeittosäädin (uusilla oletuksilla) | havainnoista | verrokista | ala | osuvuus |
|---|---|---|---|---|
| 0 / 25 / **40** *(oletus)* | 60 % | 37 % | 18 % | 1,63× |
| 55 | 56 % | 34 % | 17 % | 1,65× |
| 70 | 28 % | 15 % | 10 % | 1,85× |

**Puuston ikä on säätimistä tehokkain** — 60 v antaa 1,90× ja 80 v 2,36×, eli enemmän kuin
tilavuussäädin parhaimmillaan. Siksi säätimen vihje sanoo sen ääneen: se on tieto, jota käyttäjä
ei voi arvata, ja se tekee säätimistä tuottavampia ilman että oletusta muutetaan.

Ikäoletus jätettiin silti 40 vuoteen. Se ei ole tilastollisesti paras asento — 0 antaa 1,66× ja
40 antaa 1,62×, eli oletus istuu pienessä kuopassa — mutta ero on mittausmelun kokoluokkaa, ja
40 v rajaa pois taimikot, joissa ei kannata kävellä riippumatta siitä mitä luvut sanovat. 60 v
puolestaan pudottaisi löytöosuuden 42 %:iin, mikä on sama vaihtokauppa kuin kuusivaltaisuudella:
säätimen paikka, ei oletuksen.

Latvuspeitto on säätimistä heikoin: se on tasannetta 55:een asti eikä pure ennen 70:tä.
Oletuksen lasku 55:stä 40:een ei siis menetä mitään — luvut ovat identtiset — mutta on rehellistä
sanoa, ettei se myöskään voita mitään.

## Sivulöydös: `tilavuus` on WMS:ssä puoliskaalassa

Luke tarjoaa puulajikohtaiset tilavuustasot (`manty`, `kuusi`, `koivu`) tavuina, yksi
rasteriaskel per m³/ha. `tilavuus` on koko puusto ja ylittää 500 m³/ha, mikä ei tavuun mahdu,
joten **se taso julkaistaan puoliskaalassa: yksi askel on 2 m³/ha.**

Mitattuna GeoTIFF-lähdettä vasten: WMS 15 / 45 / 70 / 95 / 125 / 170 siellä missä GeoTIFF lukee
35 / 91 / 141 / 192 / 255 / 344. `kuusi` sen sijaan vastaa lähdettä yksi yhteen.

Ilman tätä `tilavuus ≥ 150` olisi tarkoittanut 300 m³/ha ja värittänyt Nuuksiosta 1,3 %
44:n sijaan. Muunnos tehdään `rasterVol()`:ssa (`js/constants.js`) täsmälleen siinä kohdassa,
jossa käyttäjän m³/ha muuttuu rasterikyselyksi — sekä maskissa että napautustiedoissa.
Yli ~510 m³/ha kyllästyy arvoon 255, mikä on "vähintään"-maskille vaaratonta.

Tarkistettu 150 satunnaisella näytepisteellä: "WMS sanoo ≥ `rasterVol(150)`" ja "GeoTIFF sanoo
≥ 150 m³/ha" ovat samaa mieltä **150/150**. Sama `kuusi ≥ 110`:lle, 150/150.

Samalla varmistettiin, ettei `maskMin`-maskin 255:n kattoentry katkaise arvoja sen yläpuolelta:
`top=255` ja `top=3000` antavat pikselilleen saman tuloksen. Muiden lajien tilavuusehdot ovat
siis kunnossa.

## Sivuvaikutus: yksi WMS-pyyntö vähemmän per ruutu

Vanha oletus oli 7 tasopyyntöä per karttaruutu (kasvupaikka + päätyyppi + ikä + latvuspeitto +
kolmen puulajin unioni). Uusi on 5, kuusivaltaisuus päällä 6.
`docs/DATA_PIPELINE_REVIEW.md` käyttää juuri tätä 7:ää esimerkkinä hallitsemattomasta
rinnakkaisuudesta; luku pienenee, mutta itse ongelma (pooling puuttuu `SpotLayer.createTile`ssa)
on edelleen auki eikä tämä muutos koske siihen.

## Toistaminen

Mittausskriptit eivät ole repossa: ne ovat kertaluonteinen analyysi, eivät osa julkaisuputkea,
ja ne nojaavat GBIF-hakuun, jonka tulos muuttuu päivittäin. Toistaminen käy näin:

1. Hae havainnot GBIF:stä `taxonKey=5249504`, `country=FI`, `hasCoordinate=true` — sama muoto
   kuin `ml/ingest/fetch_observations.py` käyttää matsutakelle.
2. Suodata `unc_m ≤ 100`, `year ≥ 2010`, yksi per 100 m ruutu.
3. Arvo kohdistetut verrokit: suunta satunnainen, etäisyys 2–5 km, pidä metsämaalle osuneet.
4. Lue tasot `ml/core/mvmi_point.py`:n `PointSampler`illa kierrokselta 2023.
5. Laske jokaiselle ehdolle läpipääsyosuus kussakin joukossa.

Sienestäjäverrokin voi ottaa suoraan `ml/data/matsutake/background_fungi.csv`:stä — siitä on
vain poistettava *Cantharellus cibarius*, jota siellä on, koska tiedosto rakennettiin
matsutakelle ja vain matsutake on siitä suodatettu pois.
