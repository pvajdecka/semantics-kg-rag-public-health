# Data profile: Hospitalization cases in acute and intensive care

Generated: 2026-06-13T09:01:38+00:00

Public-health aggregated data should not be used for clinical treatment recommendations or causal claims.

- Source URL: https://data.mzcr.cz/data/distribuce/421/Otevrena-data-NR-23-01-hospitalizacni-pripady-akutni-intezivni-pece.csv.gz
- Local file: `data/raw/hospitalization.csv`
- Shape: 1418107 rows x 28 columns
- Encoding/separator: utf-8-sig / ,
- Duplicate row count: 4205
- Memory usage bytes: 445397546

## Columns

`rok`, `pohlavi`, `vek_kod`, `kraj_pacient`, `ZDG`, `operace`, `umrti`, `pocet_hosp`, `OD_ARO_JIP`, `OD_JIP`, `OD_ARO`, `OD_JIP1`, `OD_JIP2`, `OD_JIP3`, `OD_JIP4`, `OD_JIP5`, `OD_JIP6`, `OD_JIP7`, `OD_JIP8`, `OD_JIP9`, `OD_JIP10`, `OD_ARO1`, `OD_ARO2`, `OD_ARO3`, `OD_ARO4`, `OD_ARO5`, `OD_ARO6`, `OD_ARO7`

## Missing values

| Column | Missing count | Missing % |
| --- | --- | --- |
| rok | 0 | 0.0 |
| pohlavi | 0 | 0.0 |
| vek_kod | 0 | 0.0 |
| kraj_pacient | 0 | 0.0 |
| ZDG | 0 | 0.0 |
| operace | 0 | 0.0 |
| umrti | 0 | 0.0 |
| pocet_hosp | 0 | 0.0 |
| OD_ARO_JIP | 0 | 0.0 |
| OD_JIP | 0 | 0.0 |
| OD_ARO | 0 | 0.0 |
| OD_JIP1 | 0 | 0.0 |
| OD_JIP2 | 0 | 0.0 |
| OD_JIP3 | 0 | 0.0 |
| OD_JIP4 | 0 | 0.0 |
| OD_JIP5 | 0 | 0.0 |
| OD_JIP6 | 0 | 0.0 |
| OD_JIP7 | 0 | 0.0 |
| OD_JIP8 | 0 | 0.0 |
| OD_JIP9 | 0 | 0.0 |
| OD_JIP10 | 0 | 0.0 |
| OD_ARO1 | 0 | 0.0 |
| OD_ARO2 | 0 | 0.0 |
| OD_ARO3 | 0 | 0.0 |
| OD_ARO4 | 0 | 0.0 |
| OD_ARO5 | 0 | 0.0 |
| OD_ARO6 | 0 | 0.0 |
| OD_ARO7 | 0 | 0.0 |

## Categorical-looking columns

| Column | Unique | Code-like | Label-like | Diacritics | Examples |
| --- | --- | --- | --- | --- | --- |
| rok | 15 | True | False | False | 2010, 2011, 2012, 2013, 2014 |
| pohlavi | 2 | True | False | False | 1, 2 |
| vek_kod | 21 | True | False | False | 66000004, 66005009, 66010014, 66015019, 66020024 |
| kraj_pacient | 15 | True | False | False | CZ010, CZ020, CZ031, CZ032, CZ041 |
| ZDG | 1567 | True | False | False | A02, A04, A05, A08, A09 |
| operace | 2 | True | False | False | 0, 1 |
| umrti | 2 | True | False | False | 0, 1 |
| pocet_hosp | 430 | True | False | False | 1, 2, 28, 18, 54 |
| OD_ARO | 676 | True | False | False | 0, 8, 2, 4, 1 |
| OD_JIP1 | 233 | True | False | False | 0, 58, 4, 7, 44 |
| OD_JIP2 | 279 | True | False | False | 0, 2, 7, 1, 6 |
| OD_JIP3 | 288 | True | False | False | 0, 1, 2, 7, 3 |
| OD_JIP4 | 426 | True | False | False | 0, 1, 3, 5, 7 |
| OD_JIP5 | 214 | True | False | False | 0, 1, 11, 100, 30 |
| OD_JIP6 | 337 | True | False | False | 13, 8, 1, 55, 29 |
| OD_JIP7 | 506 | True | False | False | 0, 4, 1, 6, 2 |
| OD_JIP8 | 828 | True | False | False | 0, 4, 3, 22, 5 |
| OD_JIP9 | 163 | True | False | False | 0, 3, 4, 16, 1 |
| OD_JIP10 | 93 | True | False | False | 0, 7, 1, 2, 5 |
| OD_ARO1 | 110 | True | False | False | 0, 3, 1, 2, 4 |
| OD_ARO2 | 153 | True | False | False | 0, 3, 2, 4, 1 |
| OD_ARO3 | 227 | True | False | False | 0, 1, 5, 2, 4 |
| OD_ARO4 | 200 | True | False | False | 0, 8, 2, 4, 1 |
| OD_ARO5 | 68 | True | False | False | 0, 19, 30, 4, 15 |
| OD_ARO6 | 198 | True | False | False | 0, 2, 5, 1, 10 |
| OD_ARO7 | 568 | True | False | False | 0, 98, 1, 2, 910 |

## Numeric-looking columns

| Column | Min | Max | Mean | Median | Sum | Zeros | Negative |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rok | 2010.0 | 2024.0 | 2016.847 | 2017.0 | 2860105107.0 | 0 | 0 |
| pohlavi | 1.0 | 2.0 | 1.487 | 1.0 | 2108554.0 | 0 | 0 |
| vek_kod | 66000004.0 | 70001000.0 | 66050215.042 | 66055059.0 | 93666272302727.0 | 0 | 0 |
| operace | 0.0 | 1.0 | 0.452 | 0.0 | 641163.0 | 776944 | 0 |
| umrti | 0.0 | 1.0 | 0.122 | 0.0 | 173418.0 | 1244689 | 0 |
| pocet_hosp | 1.0 | 1191.0 | 3.379 | 1.0 | 4791223.0 | 0 | 0 |
| OD_ARO_JIP | 1.0 | 7588.0 | 14.891 | 5.0 | 21117305.0 | 0 | 0 |
| OD_JIP | 0.0 | 6109.0 | 12.536 | 4.0 | 17777450.0 | 36595 | 0 |
| OD_ARO | 0.0 | 2563.0 | 2.355 | 0.0 | 3339855.0 | 1118431 | 0 |
| OD_JIP1 | 0.0 | 663.0 | 0.19 | 0.0 | 269689.0 | 1411454 | 0 |
| OD_JIP2 | 0.0 | 631.0 | 2.399 | 0.0 | 3401352.0 | 919845 | 0 |
| OD_JIP3 | 0.0 | 1282.0 | 3.081 | 1.0 | 4369471.0 | 702277 | 0 |
| OD_JIP4 | 0.0 | 1497.0 | 4.485 | 1.0 | 6359701.0 | 554707 | 0 |
| OD_JIP5 | 0.0 | 2411.0 | 0.208 | 0.0 | 294717.0 | 1366849 | 0 |
| OD_JIP6 | 0.0 | 1114.0 | 1.044 | 0.0 | 1479975.0 | 1223204 | 0 |
| OD_JIP7 | 0.0 | 3283.0 | 0.262 | 0.0 | 371288.0 | 1410255 | 0 |
| OD_JIP8 | 0.0 | 4262.0 | 0.756 | 0.0 | 1072673.0 | 1404466 | 0 |
| OD_JIP9 | 0.0 | 304.0 | 0.089 | 0.0 | 126602.0 | 1406924 | 0 |
| OD_JIP10 | 0.0 | 196.0 | 0.023 | 0.0 | 31982.0 | 1413859 | 0 |
| OD_ARO1 | 0.0 | 149.0 | 0.279 | 0.0 | 395963.0 | 1323592 | 0 |
| OD_ARO2 | 0.0 | 300.0 | 0.618 | 0.0 | 876086.0 | 1248898 | 0 |
| OD_ARO3 | 0.0 | 618.0 | 1.014 | 0.0 | 1437252.0 | 1191172 | 0 |
| OD_ARO4 | 0.0 | 1469.0 | 0.083 | 0.0 | 117042.0 | 1404756 | 0 |
| OD_ARO5 | 0.0 | 153.0 | 0.015 | 0.0 | 21551.0 | 1414680 | 0 |
| OD_ARO6 | 0.0 | 353.0 | 0.065 | 0.0 | 91820.0 | 1412868 | 0 |
| OD_ARO7 | 0.0 | 2408.0 | 0.282 | 0.0 | 400141.0 | 1411930 | 0 |

## Time columns

```json
{
  "rok": {
    "kind": "year",
    "distinct_values": 15,
    "example_values": [
      "2010",
      "2011",
      "2012",
      "2013",
      "2014",
      "2015",
      "2016",
      "2017",
      "2018",
      "2019",
      "2020",
      "2021",
      "2022",
      "2023",
      "2024"
    ],
    "min": 2010,
    "max": 2024,
    "missing_years_if_obvious": []
  }
}
```

## Warnings

No profile warnings.

## Dataset-specific analysis

```json
{
  "loaded": true,
  "shared_exact_columns_with_infectious_diseases": [
    "pohlavi",
    "rok",
    "vek_kod"
  ],
  "likely_shared_concepts": {
    "diagnosis": [],
    "age": [
      "vek_kod"
    ],
    "year_or_date": [
      "rok"
    ],
    "region": [
      "kraj_pacient"
    ],
    "sex": [
      "pohlavi"
    ]
  },
  "future_extension_assessment": "Potentially useful as a future extension if shared diagnosis, age, region, year, or sex concepts can be validated. It should not be joined in this profiling stage.",
  "risks": [
    "Different analytical grain may make direct comparisons invalid.",
    "Indicators may have different semantics from infectious-disease case counts.",
    "Hospitalization indicators must not be interpreted as treatment-effectiveness evidence without a proper study design.",
    "Cross-table analysis can invite causal misinterpretation if not carefully scoped."
  ]
}
```
