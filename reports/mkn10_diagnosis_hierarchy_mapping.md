# MKN-10-CZ hierarchy mapping for infectious-disease diagnoses

Generated: 2026-06-13T11:26:29+00:00

Tento report mapuje každý kód `diagnoza` z tabuľky infekčných nemocí na český názov diagnózy, blok a kapitolu MKN-10-CZ.

## Dôležité zistenie

Otvorený číselník ÚZIS `Otevrena-data-OIS-12-03-ciselnik-mkn-10-cz.csv` obsahuje:

- `kod`, `kod_tecka`, `nazev` pre diagnózu,
- `kod_kapitola_rozsah`, `kod_kapitola_cislo`, `nazev_kapitola` pre kapitolu.

V tomto CSV/metadátach **nie je samostatný stĺpec pre blok** typu `blok_kod` alebo `blok_nazev`. Preto sú hodnoty `blok_kod` a `blok_nazev` v tomto artefakte vytvorené ako odvodená MKN-10 hierarchická vrstva podľa blokových rozsahov. Diagnóza a kapitola sú priamo z ÚZIS CSV; blok je transparentne označený v stĺpci `blok_source`.

## Vytvorené súbory

- `outputs/mkn10_diagnosis_hierarchy_mapping.csv`
- `outputs/mkn10_diagnosis_hierarchy_mapping.json`
- `outputs/mkn10_block_summary_for_infectious_diseases.csv`

## Kontrola pokrytia

- Počet diagnóz v tabuľke infekčných nemocí: 114
- Diagnózy namapované na ÚZIS MKN-10-CZ `kod`: 114
- Diagnózy bez MKN mapovania: 0
- Diagnózy bez odvodeného bloku: 0

## Súhrn podľa blokov

| Kapitola | Blok | Název bloku | Počet diagnóz | Počet případů celkem |
| --- | --- | --- | --- | --- |
| I. | A00-A09 | Střevní infekční nemoci | 9 | 362877 |
| I. | A20-A28 | Některé bakteriální zoonózy | 5 | 1058 |
| I. | A30-A49 | Jiné bakteriální nemoci | 11 | 103373 |
| I. | A50-A64 | Infekce přenášené převážně pohlavním stykem | 3 | 16079 |
| I. | A65-A69 | Jiné spirochetové nemoci | 1 | 37573 |
| I. | A70-A74 | Jiné nemoci způsobené chlamydiemi | 2 | 150 |
| I. | A75-A79 | Rickettsiózy | 3 | 54 |
| I. | A80-A89 | Virové infekce centrální nervové soustavy | 7 | 7737 |
| I. | A92-A99 | Virové horečky a virové hemoragické horečky přenášené členovci | 6 | 640 |
| I. | B00-B09 | Virové infekce charakterizované postižením kůže a sliznice | 9 | 344853 |
| I. | B15-B19 | Virová hepatitida | 5 | 19491 |
| I. | B25-B34 | Jiné virové nemoci | 5 | 14347 |
| I. | B35-B49 | Mykózy | 5 | 3493 |
| I. | B50-B64 | Protozoární nemoci | 9 | 1044 |
| I. | B65-B83 | Helmintózy – hlístové nemoci | 14 | 8551 |
| I. | B85-B89 | Zavšivení‚ akarióza a jiná napadení | 3 | 48512 |
| I. | B95-B98 | Bakteriální‚ virová a jiná infekční agens | 2 | 318 |
| I. | B99 | Jiné infekční nemoci | 1 | 9 |
| VI. | G00-G09 | Zánětlivé nemoci centrální nervové soustavy | 1 | 732 |
| VI. | G50-G59 | Onemocnění nervů‚ nervových kořenů a pletení | 1 | 43 |
| VI. | G60-G64 | Polyneuropatie a jiné nemoci periferní nervové soustavy | 1 | 4 |
| X. | J00-J06 | Akutní infekce horních dýchacích cest | 1 | 1 |
| X. | J09-J18 | Chřipka a zánět plic (pneumonie) | 8 | 18934 |
| XX. | W50-W64 | Vystavení životným mechanickým silám | 2 | 7573 |

## Ukážka mapovania

| Diagnóza | Název diagnózy MKN | Blok | Název bloku | Kapitola | Název kapitoly | Počet případů |
| --- | --- | --- | --- | --- | --- | --- |
| A01 | Břišní tyfus a paratyfus | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 27 |
| A02 | Jiné infekce způsobené salmonelami | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 73222 |
| A03 | Shigelóza | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 867 |
| A04 | Jiné bakteriální střevní infekce | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 196550 |
| A05 | Jiné bakteriální intoxikace – otravy, přenesené potravou | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 789 |
| A06 | Amébóza | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 69 |
| A07 | Jiné protozoární střevní nemoci | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 704 |
| A08 | Střevní infekce viry a jinými určenými mikroorganismy | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 69601 |
| A09 | Jiná gastroenteritida a kolitida infekčního a NS původu | A00-A09 | Střevní infekční nemoci | I. | Některé infekční a parazitární nemoci | 21048 |
| A21 | Tularemie | A20-A28 | Některé bakteriální zoonózy | I. | Některé infekční a parazitární nemoci | 483 |
| A23 | Brucelóza – vlnivá horečka | A20-A28 | Některé bakteriální zoonózy | I. | Některé infekční a parazitární nemoci | 12 |
| A26 | Červenka – erysipeloid | A20-A28 | Některé bakteriální zoonózy | I. | Některé infekční a parazitární nemoci | 13 |
| A27 | Leptospiróza | A20-A28 | Některé bakteriální zoonózy | I. | Některé infekční a parazitární nemoci | 182 |
| A28 | Další bakteriální zoonózy nezařazené jinde | A20-A28 | Některé bakteriální zoonózy | I. | Některé infekční a parazitární nemoci | 368 |
| A32 | Listerióza [listeriosis] | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 322 |
| A35 | Tetanus jiný | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 3 |
| A36 | Záškrt [diphtheria] | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 128 |
| A37 | Dávivý kašel [pertussis] | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 45898 |
| A38 | Spála [scarlatina] | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 18842 |
| A39 | Meningokokové infekce | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 220 |
| A40 | Streptokoková sepse | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 4213 |
| A41 | Jiná sepse | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 10466 |
| A42 | Aktinomykóza – actinomycosis | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 15 |
| A46 | Růže – erysipel | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 20264 |
| A48 | Jiné bakteriální nemoci nezařazené jinde | A30-A49 | Jiné bakteriální nemoci | I. | Některé infekční a parazitární nemoci | 3002 |
| A56 | Jiná chlamydiová onemocnění přenášená pohlavním stykem | A50-A64 | Infekce přenášené převážně pohlavním stykem | I. | Některé infekční a parazitární nemoci | 15211 |
| A59 | Trichomoniáza | A50-A64 | Infekce přenášené převážně pohlavním stykem | I. | Některé infekční a parazitární nemoci | 410 |
| A63 | Jiné, převážně pohlavním stykem přenášené nemoci nezařazené jinde | A50-A64 | Infekce přenášené převážně pohlavním stykem | I. | Některé infekční a parazitární nemoci | 458 |
| A69 | Jiné spirochetové infekce | A65-A69 | Jiné spirochetové nemoci | I. | Některé infekční a parazitární nemoci | 37573 |
| A70 | Infekce původce: Chlamydia psittaci | A70-A74 | Jiné nemoci způsobené chlamydiemi | I. | Některé infekční a parazitární nemoci | 2 |
| A74 | Jiné nemoci způsobené chlamydiemi | A70-A74 | Jiné nemoci způsobené chlamydiemi | I. | Některé infekční a parazitární nemoci | 148 |
| A77 | Purpurová horečka (rickettsióza přenášená klíštětem) | A75-A79 | Rickettsiózy | I. | Některé infekční a parazitární nemoci | 2 |
| A78 | Q horečka | A75-A79 | Rickettsiózy | I. | Některé infekční a parazitární nemoci | 12 |
| A79 | Jiné rickettsiózy | A75-A79 | Rickettsiózy | I. | Některé infekční a parazitární nemoci | 40 |
| A81 | Atypické virové infekce centrální nervové soustavy | A80-A89 | Virové infekce centrální nervové soustavy | I. | Některé infekční a parazitární nemoci | 170 |
| A83 | Virová encefalitida přenášená komáry | A80-A89 | Virové infekce centrální nervové soustavy | I. | Některé infekční a parazitární nemoci | 1 |
| A84 | Virová encefalitida přenášená klíšťaty | A80-A89 | Virové infekce centrální nervové soustavy | I. | Některé infekční a parazitární nemoci | 5567 |
| A86 | Neurčená virová encefalitida | A80-A89 | Virové infekce centrální nervové soustavy | I. | Některé infekční a parazitární nemoci | 116 |
| A87 | Virová meningitida | A80-A89 | Virové infekce centrální nervové soustavy | I. | Některé infekční a parazitární nemoci | 1856 |
| A88 | Jiné virové infekce centrální nervové soustavy nezařazené jinde | A80-A89 | Virové infekce centrální nervové soustavy | I. | Některé infekční a parazitární nemoci | 3 |

## Prečo je to dobré pre KG-RAG demo

Toto pridáva zaujímavú hierarchiu:

`kapitola -> blok -> diagnóza -> hodnota v tabuľke infekčných nemocí`

Pre hlavný demo prípad to znamená napríklad:

`I. Některé infekční a parazitární nemoci -> A00-A09 Střevní infekční nemoci -> A01-A09 diagnózy v tabuľke`

To je presne štruktúra, ktorú klasický RAG z textových chunkov nemusí kompletne zrekonštruovať, zatiaľ čo KG-RAG ju môže použiť na recall-expanziu pred retrievalom.
