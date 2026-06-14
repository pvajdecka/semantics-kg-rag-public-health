# Evaluační dotazy pro finální demo KG-RAG vs RAG

Generated: 2026-06-13T12:27:59+00:00

Toto sú **skutočné dotazy**, ktoré sa majú posielať modelom. Nie sú to meta-otázky o tom, čo má systém zahrnúť. Ku každému dotazu je uvedený presný očakávaný výstup ako SQL/rendered-table odpoveď.

Poznámka: používame názov `pocet_pripadu` z dát. Neinterpretovať automaticky ako unikátnych pacientov, prevalenciu ani incidenciu.

## Tri hlavné výskumné otázky

| ID | Research question | Evaluation queries | Metrics |
| --- | --- | --- | --- |
| RQ-1 | Does KG-RAG improve exact diagnosis-code recall over standard RAG for Czech disease-family queries whose table labels do not all share the user’s wording? | EQ-01, EQ-07 | exact code-set recall, weighted recall by pocet_pripadu, false-positive code rate |
| RQ-2 | Does KG-RAG improve typed analytical-scope construction for SQL/table answers involving informal Czech time, age, and region expressions? | EQ-02, EQ-03, EQ-04, EQ-05, EQ-06 | year recall, age-group recall, region-value recall, measure identification accuracy |
| RQ-3 | Can KG-RAG preserve or improve precision and provenance while increasing recall, especially for absent hierarchy members and lexical outsiders? | EQ-01, EQ-07, EQ-08, EQ-09, EQ-10 | coverage-status accuracy, provenance completeness, no-regression on control cases |

## Prehľad evaluačných dotazov

| ID | Dotaz poslaný modelu | English translation |
| --- | --- | --- |
| EQ-01 | Porovnej střevní infekční nemoci v České republice podle diagnózy. | Compare intestinal infectious diseases in the Czech Republic by diagnosis. |
| EQ-02 | Porovnej střevní infekční nemoci v letech 2020 and 2023 | Compare intestinal infectious diseases in years 2020 and 2023. |
| EQ-03 | Porovnej střevní infekční nemoci u dětí podle věkové skupiny. | Compare intestinal infectious diseases in children by age group. |
| EQ-04 | Porovnej střevní infekční nemoci u seniorů 65+ podle věkové skupiny. | Compare intestinal infectious diseases in seniors 65+ by age group. |
| EQ-05 | Porovnej střevní infekční nemoci na Moravě podle kraje. | Compare intestinal infectious diseases in Moravia by region. |
| EQ-06 | Kolik případů střevních infekčních nemocí bylo v Praze? | How many cases of intestinal infectious diseases were in Prague? |
| EQ-07 | Porovnej virové infekce kůže a sliznic podle diagnózy. | Compare viral infections of skin and mucous membranes by diagnosis. |
| EQ-08 | Porovnej virové hepatitidy podle diagnózy. | Compare viral hepatitis by diagnosis. |
| EQ-09 | Porovnej pneumonie podle diagnózy. | Compare pneumonia by diagnosis. |
| EQ-10 | Porovnej pneumonie podle kraje. | Compare pneumonia by region. |

## EQ-01: Porovnej střevní infekční nemoci v České republice podle diagnózy.

**English:** Compare intestinal infectious diseases in the Czech Republic by diagnosis.

**Intent:** group disease-family A00-A09 to table-present A01-A09 and aggregate by diagnosis

**Expected SQL shape:** `SELECT diagnoza, diagnoza_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('A01',...,'A09') GROUP BY diagnoza, diagnoza_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "diagnosis_codes": [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09"
  ],
  "mkn_group": "A00-A09",
  "mkn_relevant_absent_codes": [
    "A00"
  ],
  "measure": "pocet_pripadu"
}
```

**Expected rendered table:**

| diagnoza | diagnoza_nazev | pocet_pripadu |
| --- | --- | --- |
| A04 | Jiné bakteriální střevní infekce | 196550 |
| A02 | Jiné infekce způsobené salmonelami | 73222 |
| A08 | Střevní infekce viry a jinými určenými mikroorganismy | 69601 |
| A09 | Jiná gastroenteritida a kolitida infekčního a NS původu | 21048 |
| A03 | Shigelóza | 867 |
| A05 | Jiné bakteriální intoxikace – otravy, přenesené potravou | 789 |
| A07 | Jiné protozoární střevní nemoci | 704 |
| A06 | Amébóza | 69 |
| A01 | Břišní tyfus a paratyfus | 27 |

**Why KG-RAG matters:** Main recall test: KG-RAG can expand the group to A00-A09, intersect with table evidence, and retrieve all A01-A09.

**Standard RAG risk:** May retrieve only labels containing střev: A04, A07, A08 and outsider B81; may miss A01, A02, A03, A05, A06, A09.

**Primary metric:** exact diagnosis-code recall and weighted recall by pocet_pripadu

## EQ-02: Porovnej střevní infekční nemoci v letech 2020 and 2023

**English:** Compare intestinal infectious diseases in years 2020 and 2023.

**Intent:** filter years to 2020 and 2023 and aggregate A01-A09 by rok

**Expected SQL shape:** `SELECT rok, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('A01',...,'A09') AND rok IN (2020,2023) GROUP BY rok ORDER BY rok`

**Gold scope:**

```json
{
  "diagnosis_codes": [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09"
  ],
  "years": [
    2020,
    2023
  ],
  "measure": "pocet_pripadu",
  "total": 78145
}
```

**Expected rendered table:**

| rok | pocet_pripadu |
| --- | --- |
| 2020 | 39245 |
| 2023 | 38900 |

**Why KG-RAG matters:** Tests explicit year filtering plus disease-family expansion.

**Standard RAG risk:** May retrieve a partial diagnosis set or fail to apply both explicit year filters.

**Primary metric:** year recall + diagnosis-code recall

## EQ-03: Porovnej střevní infekční nemoci u dětí podle věkové skupiny.

**English:** Compare intestinal infectious diseases in children by age group.

**Intent:** map děti to official age groups and aggregate A01-A09

**Expected SQL shape:** `SELECT vek_kod, vek_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('A01',...,'A09') AND vek_kod IN (...) GROUP BY vek_kod, vek_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "diagnosis_codes": [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09"
  ],
  "age_groups": [
    "66000000",
    "66001004",
    "66005009",
    "66010014"
  ],
  "age_labels": [
    "0 let",
    "1–4 roky",
    "5–9 let",
    "10–14 let"
  ],
  "total": 169571
}
```

**Expected rendered table:**

| vek_kod | vek_nazev | pocet_pripadu |
| --- | --- | --- |
| 66001004 | 1–4 roky | 81910 |
| 66005009 | 5–9 let | 38254 |
| 66000000 | 0 let | 25078 |
| 66010014 | 10–14 let | 24329 |

**Why KG-RAG matters:** Tests informal age concept normalization.

**Standard RAG risk:** The table does not contain the literal value děti; standard RAG may not infer all official age groups.

**Primary metric:** official age-group recall

## EQ-04: Porovnej střevní infekční nemoci u seniorů 65+ podle věkové skupiny.

**English:** Compare intestinal infectious diseases in seniors 65+ by age group.

**Intent:** map senioři 65+ to official age groups and aggregate A01-A09

**Expected SQL shape:** `SELECT vek_kod, vek_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('A01',...,'A09') AND vek_kod IN (...) GROUP BY vek_kod, vek_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "diagnosis_codes": [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09"
  ],
  "age_groups": [
    "66065069",
    "66070074",
    "66075999"
  ],
  "age_labels": [
    "65–69 let",
    "70–74 let",
    "75+ let"
  ],
  "total": 72416
}
```

**Expected rendered table:**

| vek_kod | vek_nazev | pocet_pripadu |
| --- | --- | --- |
| 66075999 | 75+ let | 44997 |
| 66070074 | 70–74 let | 15122 |
| 66065069 | 65–69 let | 12297 |

**Why KG-RAG matters:** Tests interval semantics from the age-group code list.

**Standard RAG risk:** May use only 75+ or miss 65-69 and 70-74.

**Primary metric:** official age-group recall

## EQ-05: Porovnej střevní infekční nemoci na Moravě podle kraje.

**English:** Compare intestinal infectious diseases in Moravia by region.

**Intent:** map Morava to selected official region labels and aggregate A01-A09

**Expected SQL shape:** `SELECT kraj_kod, kraj_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('A01',...,'A09') AND kraj_nazev IN (...) GROUP BY kraj_kod, kraj_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "diagnosis_codes": [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09"
  ],
  "regions": [
    "Jihomoravský kraj",
    "Moravskoslezský kraj",
    "Olomoucký kraj",
    "Zlínský kraj"
  ],
  "total": 143867
}
```

**Expected rendered table:**

| kraj_kod | kraj_nazev | pocet_pripadu |
| --- | --- | --- |
| CZ080 | Moravskoslezský kraj | 48106 |
| CZ064 | Jihomoravský kraj | 47723 |
| CZ071 | Olomoucký kraj | 24326 |
| CZ072 | Zlínský kraj | 23712 |

**Why KG-RAG matters:** Tests regional alias expansion not present as a literal table value.

**Standard RAG risk:** Morava is not a value in kraj_nazev; standard RAG may fail or choose incomplete regions.

**Primary metric:** region alias recall

## EQ-06: Kolik případů střevních infekčních nemocí bylo v Praze?

**English:** How many cases of intestinal infectious diseases were in Prague?

**Intent:** map Praha to Hl. m. Praha/CZ010 and aggregate A01-A09

**Expected SQL shape:** `SELECT kraj_kod, kraj_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('A01',...,'A09') AND kraj_kod='CZ010' GROUP BY kraj_kod, kraj_nazev`

**Gold scope:**

```json
{
  "diagnosis_codes": [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09"
  ],
  "region_code": "CZ010",
  "region_label": "Hl. m. Praha"
}
```

**Expected rendered table:**

| kraj_kod | kraj_nazev | pocet_pripadu |
| --- | --- | --- |
| CZ010 | Hl. m. Praha | 31351 |

**Why KG-RAG matters:** Tests official-value normalization for a very common user phrase.

**Standard RAG risk:** May search for literal Praha and not preserve official value Hl. m. Praha.

**Primary metric:** official region value accuracy

## EQ-07: Porovnej virové infekce kůže a sliznic podle diagnózy.

**English:** Compare viral infections of skin and mucous membranes by diagnosis.

**Intent:** expand B00-B09, mark B03 absent, aggregate table-present B00,B01,B02,B04-B09

**Expected SQL shape:** `SELECT diagnoza, diagnoza_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('B00','B01','B02','B04','B05','B06','B07','B08','B09') GROUP BY diagnoza, diagnoza_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "mkn_group": "B00-B09",
  "diagnosis_codes": [
    "B00",
    "B01",
    "B02",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B09"
  ],
  "mkn_relevant_absent_codes": [
    "B03"
  ],
  "measure": "pocet_pripadu"
}
```

**Expected rendered table:**

| diagnoza | diagnoza_nazev | pocet_pripadu |
| --- | --- | --- |
| B01 | Plané neštovice [varicella] | 275635 |
| B02 | Pásový opar [herpes zoster] | 39721 |
| B08 | Jiné virové infekce charakterizované postižením kůže a sliznic NJ | 27234 |
| B00 | Infekce virem Herpes simplex | 1119 |
| B05 | Spalničky | 877 |
| B09 | Neurčené virové infekce charakterizované postižením kůže a sliznic | 142 |
| B04 | Opičí neštovice | 110 |
| B07 | Virové bradavice | 13 |
| B06 | Zarděnky [rubeola] | 2 |

**Why KG-RAG matters:** Strong second hierarchy case: literal skin/mucosa finds only B08/B09, but the MKN block covers more codes.

**Standard RAG risk:** May retrieve only B08 and B09 because they contain kůže/sliznic.

**Primary metric:** exact diagnosis-code recall

## EQ-08: Porovnej virové hepatitidy podle diagnózy.

**English:** Compare viral hepatitis by diagnosis.

**Intent:** aggregate B15-B19 by diagnosis

**Expected SQL shape:** `SELECT diagnoza, diagnoza_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('B15','B16','B17','B18','B19') GROUP BY diagnoza, diagnoza_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "mkn_group": "B15-B19",
  "diagnosis_codes": [
    "B15",
    "B16",
    "B17",
    "B18",
    "B19"
  ],
  "measure": "pocet_pripadu"
}
```

**Expected rendered table:**

| diagnoza | diagnoza_nazev | pocet_pripadu |
| --- | --- | --- |
| B18 | Chronická virová hepatitida | 9835 |
| B15 | Akutní hepatitida A | 4867 |
| B17 | Jiná akutní virová hepatitida | 4486 |
| B16 | Akutní hepatitida B | 301 |
| B19 | Neurčená virová hepatitida | 2 |

**Why KG-RAG matters:** Control case: lexical retrieval should be easier, so KG-RAG should not be artificially advantaged.

**Standard RAG risk:** Likely weaker failure; may still omit rare B19 without hierarchy.

**Primary metric:** control-case recall / no-regression

## EQ-09: Porovnej pneumonie podle diagnózy.

**English:** Compare pneumonia by diagnosis.

**Intent:** aggregate J12-J18 by diagnosis

**Expected SQL shape:** `SELECT diagnoza, diagnoza_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('J12',...,'J18') GROUP BY diagnoza, diagnoza_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "mkn_group": "J12-J18",
  "diagnosis_codes": [
    "J12",
    "J13",
    "J14",
    "J15",
    "J16",
    "J17",
    "J18"
  ],
  "measure": "pocet_pripadu"
}
```

**Expected rendered table:**

| diagnoza | diagnoza_nazev | pocet_pripadu |
| --- | --- | --- |
| J12 | Virový zánět plic (pneumonie) nezařazený jinde | 1238 |
| J13 | Zánět plic‚ původce: Streptococcus pneumoniae | 1091 |
| J15 | Bakteriální zánět plic (pneumonie) nezařazený jinde | 596 |
| J16 | Zánět plic (pneumonie) způsobený jinými infekčními organismy NJ | 135 |
| J17 | Zánět plic (pneumonie) při nemocech zařazených jinde | 87 |
| J14 | Zánět plic‚ původce: Haemophilus influenzae | 48 |
| J18 | Pneumonie‚ původce NS | 2 |

**Why KG-RAG matters:** Tests synonym and block scope: pneumonie/zánět plic should map to J12-J18.

**Standard RAG risk:** May retrieve only labels containing pneumonie and miss zánět plic wording, or add unrelated respiratory codes.

**Primary metric:** synonym robustness + code recall

## EQ-10: Porovnej pneumonie podle kraje.

**English:** Compare pneumonia by region.

**Intent:** expand J12-J18 and aggregate by official region

**Expected SQL shape:** `SELECT kraj_kod, kraj_nazev, SUM(pocet_pripadu) FROM infectious_diseases WHERE diagnoza IN ('J12',...,'J18') GROUP BY kraj_kod, kraj_nazev ORDER BY SUM DESC`

**Gold scope:**

```json
{
  "mkn_group": "J12-J18",
  "diagnosis_codes": [
    "J12",
    "J13",
    "J14",
    "J15",
    "J16",
    "J17",
    "J18"
  ],
  "dimension": "kraj",
  "measure": "pocet_pripadu"
}
```

**Expected rendered table:**

| kraj_kod | kraj_nazev | pocet_pripadu |
| --- | --- | --- |
| CZ064 | Jihomoravský kraj | 1040 |
| CZ041 | Karlovarský kraj | 712 |
| CZ031 | Jihočeský kraj | 383 |
| CZ010 | Hl. m. Praha | 243 |
| CZ020 | Středočeský kraj | 198 |
| CZ052 | Královéhradecký kraj | 163 |
| CZ051 | Liberecký kraj | 140 |
| CZ042 | Ústecký kraj | 121 |
| CZ080 | Moravskoslezský kraj | 75 |
| CZ063 | Kraj Vysočina | 55 |
| CZ032 | Plzeňský kraj | 42 |
| CZ071 | Olomoucký kraj | 16 |
| CZ072 | Zlínský kraj | 7 |
| CZ053 | Pardubický kraj | 2 |

**Why KG-RAG matters:** Turns a disease-family retrieval problem into a rendered table by region, matching the planned SQL/table output mode.

**Standard RAG risk:** May use only one pneumonia code or incomplete region scope.

**Primary metric:** diagnosis-code recall + region aggregation correctness
