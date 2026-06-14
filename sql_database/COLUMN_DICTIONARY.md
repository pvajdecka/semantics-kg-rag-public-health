# Final SQL Table Column Dictionary

Final table: `fact_infectious_disease_cases_enriched`

This table is the only fact table the answer-generation backend should use for the current RAG vs KG-RAG comparison. Every row comes from the complete infectious-disease source CSV, enriched with MKN-10-CZ and age-group metadata.

| Column | Type | Meaning | Source / derivation | Query use |
| --- | --- | --- | --- | --- |
| `fact_id` | BIGINT | Stable surrogate key for one final fact row. | Generated from infectious source row order. | Row traceability only. |
| `source_dataset` | VARCHAR | Source fact dataset name. | Constant `infectious_diseases`. | Future multi-fact-table routing. |
| `source_row_id` | BIGINT | One-based source CSV row number. | Generated from `data/raw/infectious_diseases.csv`. | Traceability to raw data. |
| `report_year` | INTEGER | Year when the case was reported. | `rok`. | Time filter/grouping. |
| `report_month` | INTEGER | Month when the case was reported, 1-12. | `mesic`. | Seasonality or month filtering. |
| `period_yyyymm` | INTEGER | Compact month key. | `report_year * 100 + report_month`. | Month-level sorting/filtering. |
| `date_grain` | VARCHAR | Temporal grain of the fact row. | Constant `month`. | Prevents day-level or patient-level misinterpretation. |
| `region_code` | VARCHAR | Official Czech regional code. | `kraj_kod`. | Exact region filters. |
| `region_name_cs` | VARCHAR | Czech region label. | `kraj_nazev`. | Display and grouping label. |
| `diagnosis_code` | VARCHAR | Three-character diagnosis code in the infectious table. | `diagnoza`. | Main disease filter. |
| `diagnosis_name_cs` | VARCHAR | Czech diagnosis label in the infectious table. | `diagnoza_nazev`. | Display label. |
| `mkn_code` | VARCHAR | Matching official MKN-10-CZ code. | `mkn10_cz.kod`, exact join to `diagnosis_code`. | Code-list traceability. |
| `mkn_code_with_dot` | VARCHAR | Official dotted code form. | `mkn10_cz.kod_tecka`. | Display or official-code export. |
| `mkn_name_cs` | VARCHAR | Official MKN-10-CZ diagnosis label. | `mkn10_cz.nazev`. | Terminology validation. |
| `mkn_iri` | VARCHAR | Official MKN code IRI. | `mkn10_cz.kod_IRI`. | Semantic traceability. |
| `mkn_block_code` | VARCHAR | Derived MKN block/range, for example `A00-A09`. | Configured MKN block ranges. | Primary KG-RAG disease-family filter. |
| `mkn_block_name_cs` | VARCHAR | Czech block label. | Configured MKN block ranges. | Display disease-family scope. |
| `mkn_block_source` | VARCHAR | Provenance for block assignment. | Generated note; source CSV has chapters but no block column. | Methodology transparency. |
| `mkn_chapter_range` | VARCHAR | MKN chapter range, for example `A00-B99`. | `mkn10_cz.kod_kapitola_rozsah`. | Higher-level grouping. |
| `mkn_chapter_number` | VARCHAR | MKN chapter number, for example `I.`. | `mkn10_cz.kod_kapitola_cislo`. | Display chapter ID. |
| `mkn_chapter_name_cs` | VARCHAR | Czech MKN chapter label. | `mkn10_cz.nazev_kapitola`. | Display chapter context. |
| `has_mkn_match` | BOOLEAN | Whether the diagnosis matched MKN-10-CZ. | Derived from MKN join. | Quality-control filter. |
| `age_group_code` | VARCHAR | Official NZIS age-group code. | `vek_kod`. | Exact age filters. |
| `age_group_name_cs` | VARCHAR | Czech age-group label. | `vek_nazev`. | Display/grouping label. |
| `age_from_inclusive` | INTEGER | Lower age bound. | `age_groups.vek_od_vcetne`. | Informal age normalization. |
| `age_to_inclusive` | INTEGER | Upper age bound. | `age_groups.vek_do_vcetne`. | Informal age normalization. |
| `has_age_group_match` | BOOLEAN | Whether age group matched official code list. | Derived from age-group join. | Quality-control filter. |
| `sex_code` | VARCHAR | Source sex category. | `pohlavi`; values `M`, `Z`. | Sex filter/grouping. |
| `sex_name_cs` | VARCHAR | Czech sex label. | `M -> muž`, `Z -> žena`. | Display label. |
| `ews_code` | INTEGER | EWS source value. | `EWS`. | Retained source dimension; do not interpret clinically here. |
| `reported_case_count` | BIGINT | Reported case-count measure. | `pocet_pripadu`. | Main measure: always aggregate with `SUM(reported_case_count)`. |

Important: `reported_case_count` is a reported aggregate table measure. It is not a unique-patient count, prevalence, incidence, or treatment/clinical evidence.

Query-specific concepts such as Moravia, Prague, children, and seniors are intentionally not stored as boolean columns. They should be represented in generated SQL, for example `region_code IN (...)`, `region_code = 'CZ010'`, `age_to_inclusive <= 14`, or `age_from_inclusive >= 65`.
