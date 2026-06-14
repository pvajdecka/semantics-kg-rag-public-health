# Data profile: NZIS age-group code list

Generated: 2026-06-13T09:01:38+00:00

Public-health aggregated data should not be used for clinical treatment recommendations or causal claims.

- Source URL: https://datanzis.uzis.gov.cz/data/OIS-12-CIS/OIS-12-01/Otevrena-data-OIS-12-01-ciselnik-vekove-skupiny.csv
- Local file: `data/raw/age_groups.csv`
- Shape: 228 rows x 8 columns
- Encoding/separator: utf-8-sig / ,
- Duplicate row count: 0
- Memory usage bytes: 137269

## Columns

`ciselnik`, `ciselnik_kod`, `ciselnik_nazev`, `vek_IRI`, `vek_kod`, `vek_nazev`, `vek_od_vcetne`, `vek_do_vcetne`

## Missing values

| Column | Missing count | Missing % |
| --- | --- | --- |
| ciselnik | 0 | 0.0 |
| ciselnik_kod | 0 | 0.0 |
| ciselnik_nazev | 0 | 0.0 |
| vek_IRI | 0 | 0.0 |
| vek_kod | 0 | 0.0 |
| vek_nazev | 0 | 0.0 |
| vek_od_vcetne | 2 | 0.877 |
| vek_do_vcetne | 2 | 0.877 |

## Categorical-looking columns

| Column | Unique | Code-like | Label-like | Diacritics | Examples |
| --- | --- | --- | --- | --- | --- |
| ciselnik | 1 | False | True | True | https://data.mzd.gov.cz/data/číselníky/CIS001 |
| ciselnik_kod | 1 | True | False | False | CIS001 |
| ciselnik_nazev | 1 | False | True | True | Číselník věkových skupin NZIS |
| vek_IRI | 228 | False | True | True | https://data.mzd.gov.cz/data/číselníky/CIS001/66000000, https://data.mzd.gov.cz/data/číselníky/CIS001/66000001, https://data.mzd.gov.cz/data/číselníky/CIS001/66000003, https://data.mzd.gov.cz/data/číselníky/CIS001/66000004, https://data.mzd.gov.cz/data/číselníky/CIS001/66000009 |
| vek_nazev | 228 | False | True | True | 0 let, 1 rok a méně, 3 roky a méně, 4 roky a méně, 9 let a méně |

## Numeric-looking columns

| Column | Min | Max | Mean | Median | Sum | Zeros | Negative |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vek_kod | 66000000.0 | 70002000.0 | 66086141.711 | 66050052.0 | 15067640310.0 | 0 | 0 |
| vek_od_vcetne | 0.0 | 120.0 | 51.367 | 49.5 | 11609.0 | 13 | 0 |
| vek_do_vcetne | 0.0 | 999.0 | 125.265 | 59.0 | 28310.0 | 1 | 0 |

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
  "detected_label_column": "ciselnik",
  "infectious_age_group_code_column": "vek_kod",
  "code_coverage_against_infectious_diseases": {
    "source_column": "vek_kod",
    "codelist_code_column": "ciselnik_kod",
    "source_code_count": 17,
    "codelist_code_count": 1,
    "unmatched_source_codes": [
      "66000000",
      "66001004",
      "66005009",
      "66010014",
      "66015019",
      "66020024",
      "66025029",
      "66030034",
      "66035039",
      "66040044",
      "66045049",
      "66050054",
      "66055059",
      "66060064",
      "66065069",
      "66070074",
      "66075999"
    ],
    "codelist_codes_not_used_in_source": [
      "CIS001"
    ],
    "matched_code_count": 0
  },
  "usefulness_assessment": [
    "Useful for interpreting official age-group categories if codes match.",
    "Useful for normalization from informal terms such as children or elderly only after explicit mapping rules are added.",
    "Future semantic modelling should keep code and Czech label mappings inspectable."
  ]
}
```
