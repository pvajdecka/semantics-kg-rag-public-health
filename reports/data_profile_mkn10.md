# Data profile: MKN-10-CZ code list

Generated: 2026-06-13T09:01:38+00:00

Public-health aggregated data should not be used for clinical treatment recommendations or causal claims.

- Source URL: https://data.mzcr.cz/data/distribuce/463/Otevrena-data-OIS-12-03-ciselnik-mkn-10-cz.csv
- Local file: `data/raw/mkn10_cz.csv`
- Shape: 39136 rows x 12 columns
- Encoding/separator: utf-8-sig / ,
- Duplicate row count: 0
- Memory usage bytes: 43937038

## Columns

`ciselnik`, `ciselnik_kod`, `ciselnik_nazev`, `kod_IRI`, `kod`, `kod_tecka`, `nazev`, `kod_kapitola_rozsah`, `kod_kapitola_cislo`, `nazev_kapitola`, `platnost_od`, `platnost_do`

## Missing values

| Column | Missing count | Missing % |
| --- | --- | --- |
| ciselnik | 0 | 0.0 |
| ciselnik_kod | 0 | 0.0 |
| ciselnik_nazev | 0 | 0.0 |
| kod_IRI | 0 | 0.0 |
| kod | 0 | 0.0 |
| kod_tecka | 0 | 0.0 |
| nazev | 0 | 0.0 |
| kod_kapitola_rozsah | 0 | 0.0 |
| kod_kapitola_cislo | 0 | 0.0 |
| nazev_kapitola | 0 | 0.0 |
| platnost_od | 0 | 0.0 |
| platnost_do | 38769 | 99.062 |

## Categorical-looking columns

| Column | Unique | Code-like | Label-like | Diacritics | Examples |
| --- | --- | --- | --- | --- | --- |
| ciselnik | 1 | False | False | False | https://mkn10.uzis.cz/prohlizec |
| ciselnik_kod | 1 | True | False | False | CIS003 |
| ciselnik_nazev | 1 | False | True | True | Číselník položek české verze 10. revize Mezinárodní klasifikace nemocí (MKN-10-CZ) |
| kod_IRI | 39076 | True | False | False | https://mkn10.uzis.cz/prohlizec/A00, https://mkn10.uzis.cz/prohlizec/A00.0, https://mkn10.uzis.cz/prohlizec/A00.1, https://mkn10.uzis.cz/prohlizec/A00.9, https://mkn10.uzis.cz/prohlizec/A01 |
| kod | 39076 | True | False | False | A00, A000, A001, A009, A01 |
| kod_tecka | 39076 | True | False | False | A00, A00.0, A00.1, A00.9, A01 |
| nazev | 39068 | False | True | True | Cholera, Cholera‚ původce: Vibrio cholerae 01‚ biotyp cholerae, Cholera‚ původce: Vibrio cholerae 01‚ biotyp el Tor, Cholera NS, Břišní tyfus a paratyfus |
| kod_kapitola_rozsah | 22 | True | False | False | A00-B99, C00-D48, D49-D89, E00-E90, F00-F99 |
| kod_kapitola_cislo | 22 | True | False | False | I., II., III., IV., V. |
| nazev_kapitola | 22 | False | True | True | Některé infekční a parazitární nemoci, Novotvary, Nemoci krve a krvetvorných orgánů a některé poruchy imunity, Nemoci endokrinní‚ výživy a přeměny látek, Poruchy duševní a poruchy chování |
| platnost_od | 14 | True | False | False | 1994-01-01, 2009-01-01, 2021-01-01, 2022-01-01, 2012-01-01 |
| platnost_do | 11 | True | False | False | 2020-12-31, 2021-01-31, 2008-12-31, 2011-12-31, 2022-12-31 |

## Numeric-looking columns

No numeric-looking columns detected.

## Time columns

```json
{}
```

## Warnings

No profile warnings.

## Dataset-specific analysis

```json
{
  "detected_code_column": "ciselnik_kod",
  "detected_label_column": "ciselnik_nazev",
  "infectious_diagnosis_code_column": "diagnoza",
  "code_coverage_against_infectious_diseases": {
    "source_column": "diagnoza",
    "codelist_code_column": "ciselnik_kod",
    "source_code_count": 114,
    "codelist_code_count": 1,
    "unmatched_source_codes": [
      "A01",
      "A02",
      "A03",
      "A04",
      "A05",
      "A06",
      "A07",
      "A08",
      "A09",
      "A21",
      "A23",
      "A26",
      "A27",
      "A28",
      "A32",
      "A35",
      "A36",
      "A37",
      "A38",
      "A39",
      "A40",
      "A41",
      "A42",
      "A46",
      "A48",
      "A56",
      "A59",
      "A63",
      "A69",
      "A70",
      "A74",
      "A77",
      "A78",
      "A79",
      "A81",
      "A83",
      "A84",
      "A86",
      "A87",
      "A88",
      "A89",
      "A92",
      "A93",
      "A94",
      "A95",
      "A97",
      "A98",
      "B00",
      "B01",
      "B02",
      "B04",
      "B05",
      "B06",
      "B07",
      "B08",
      "B09",
      "B15",
      "B16",
      "B17",
      "B18",
      "B19",
      "B25",
      "B26",
      "B27",
      "B30",
      "B33",
      "B35",
      "B36",
      "B37",
      "B45",
      "B48",
      "B50",
      "B51",
      "B52",
      "B53",
      "B54",
      "B55",
      "B58",
      "B59",
      "B60",
      "B65",
      "B67",
      "B68",
      "B69",
      "B70",
      "B71",
      "B75",
      "B76",
      "B77",
      "B78",
      "B79",
      "B80",
      "B81",
      "B83",
      "B85",
      "B86",
      "B88",
      "B95",
      "B96",
      "B99",
      "G00",
      "G51",
      "G61",
      "J04",
      "J10",
      "J12",
      "J13",
      "J14",
      "J15",
      "J16",
      "J17",
      "J18",
      "W54",
      "W55"
    ],
    "codelist_codes_not_used_in_source": [
      "CIS003"
    ],
    "matched_code_count": 0
  },
  "possible_hierarchy_columns": [
    "kod_kapitola_rozsah",
    "kod_kapitola_cislo",
    "nazev_kapitola"
  ],
  "exploratory_counts_by_first_hierarchy_column": [
    {
      "kod_kapitola_rozsah": NaN,
      "pocet_pripadu": 997446
    }
  ],
  "usefulness_assessment": [
    "MKN-10-CZ is a plausible normalization/hierarchy source if infectious diagnosis codes match.",
    "Hierarchy should be used experimentally for retrieval/scope expansion, not asserted as a final contribution yet.",
    "Unmatched codes require manual inspection before any graph or recall evaluation."
  ]
}
```
