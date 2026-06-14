# Diagnosis and Filter Evaluation

Generated: 2026-06-14T01:38:02.481310+00:00

This folder evaluates the current evaluation-question set from `outputs/kg_rag_evaluation_queries.json` against live outputs from `/api/ai/query` at `http://127.0.0.1:8767`.

Diagnosis precision/recall/F1 compares predicted `diagnosis_code` filters with the gold diagnosis scope. When an evaluation item defines a diagnosis range such as `A00-A09`, `B00-B09`, `B15-B19`, or `J12-J18`, the gold set is resolved through DuckDB by intersecting that range with diagnosis codes present in `fact_infectious_disease_cases_enriched`. Other filter gold values come from the current JSON gold scope and DuckDB label lookups.

The all-filters score is binary per question and method: `1` means every expected filter column has exactly the expected values and no unexpected filter column is present; `0` means at least one filter column is missing, extra, or has wrong values. This checks filter semantics rather than literal SQL formatting.

Predicted filters are parsed from SQL `WHERE` clauses first. If an expected filter column is not explicit in `WHERE` but appears in the returned result rows, the scorer uses the distinct returned row values for that expected column. Unused retrieval candidates are not counted as applied filters.

## Diagnosis Totals

| Method | Macro P | Macro R | Macro F1 | Micro P | Micro R | Micro F1 | Exact diagnoses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RAG | 0.720 | 0.476 | 0.567 | 0.720 | 0.439 | 0.545 | 1/10 |
| KG-RAG | 1.000 | 0.889 | 0.921 | 1.000 | 0.878 | 0.935 | 8/10 |

## All Filters Total

| Method | Correct / total | Accuracy |
| --- | --- | --- |
| RAG | 1/10 | 0.100 |
| KG-RAG | 6/10 | 0.600 |

## Diagnosis Metrics by Question

| ID | Method | P | R | F1 | Exact | Predicted diagnosis codes |
| --- | --- | --- | --- | --- | --- | --- |
| EQ-01 | RAG | 0.600 | 0.333 | 0.429 | 0 | A04 A07 A08 A48 B99 |
| EQ-01 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | A01 A02 A03 A04 A05 A06 A07 A08 A09 |
| EQ-02 | RAG | 0.600 | 0.333 | 0.429 | 0 | A04 A07 A08 A48 B99 |
| EQ-02 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | A01 A02 A03 A04 A05 A06 A07 A08 A09 |
| EQ-03 | RAG | 0.600 | 0.333 | 0.429 | 0 | A04 A07 A08 A48 B99 |
| EQ-03 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | A01 A02 A03 A04 A05 A06 A07 A08 A09 |
| EQ-04 | RAG | 0.600 | 0.333 | 0.429 | 0 | A04 A07 A08 A48 B99 |
| EQ-04 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | A01 A02 A03 A04 A05 A06 A07 A08 A09 |
| EQ-05 | RAG | 0.600 | 0.333 | 0.429 | 0 | A04 A07 A08 A48 B99 |
| EQ-05 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | A01 A02 A03 A04 A05 A06 A07 A08 A09 |
| EQ-06 | RAG | 0.600 | 0.333 | 0.429 | 0 | A04 A07 A08 A48 J15 |
| EQ-06 | KG-RAG | 1.000 | 0.556 | 0.714 | 0 | A04 A05 A06 A07 A08 |
| EQ-07 | RAG | 0.600 | 0.333 | 0.429 | 0 | A08 A81 B07 B08 B09 |
| EQ-07 | KG-RAG | 1.000 | 0.333 | 0.500 | 0 | B07 B08 B09 |
| EQ-08 | RAG | 1.000 | 1.000 | 1.000 | 1 | B15 B16 B17 B18 B19 |
| EQ-08 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | B15 B16 B17 B18 B19 |
| EQ-09 | RAG | 1.000 | 0.714 | 0.833 | 0 | J12 J15 J16 J17 J18 |
| EQ-09 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | J12 J13 J14 J15 J16 J17 J18 |
| EQ-10 | RAG | 1.000 | 0.714 | 0.833 | 0 | J12 J15 J16 J17 J18 |
| EQ-10 | KG-RAG | 1.000 | 1.000 | 1.000 | 1 | J12 J13 J14 J15 J16 J17 J18 |

## All Filters by Question

| ID | Method | Correct | Missing columns | Unexpected columns | Mismatched columns |
| --- | --- | --- | --- | --- | --- |
| EQ-01 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["A01", "A02", "A03", "A05", "A06", "A09"], "unexpected": ["A48", "B99"]}} |
| EQ-01 | KG-RAG | 1 | - | - | - |
| EQ-02 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["A01", "A02", "A03", "A05", "A06", "A09"], "unexpected": ["A48", "B99"]}} |
| EQ-02 | KG-RAG | 1 | - | - | - |
| EQ-03 | RAG | 0 | - | - | {"age_group_name_cs": {"missing": ["0 let", "10–14 let", "5–9 let"], "unexpected": []}, "diagnosis_code": {"missing": ["A01", "A02", "A03", "A05", "A06", "A09"], "unexpected": ["A48", "B99"]}} |
| EQ-03 | KG-RAG | 0 | - | - | {"age_group_name_cs": {"missing": [], "unexpected": ["15–19 let", "20–24 let", "25–29 let", "30–34 let", "35–39 let", "40–44 let", "45–49 let", "50–54 let", "55–59 let", "60–64 let", "65–69 let", "70–74 let", "75+ let"]}} |
| EQ-04 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["A01", "A02", "A03", "A05", "A06", "A09"], "unexpected": ["A48", "B99"]}} |
| EQ-04 | KG-RAG | 1 | - | - | - |
| EQ-05 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["A01", "A02", "A03", "A05", "A06", "A09"], "unexpected": ["A48", "B99"]}, "region_name_cs": {"missing": ["Jihomoravský kraj", "Olomoucký kraj", "Zlínský kraj"], "unexpected": []}} |
| EQ-05 | KG-RAG | 0 | - | - | {"region_name_cs": {"missing": [], "unexpected": ["Hl. m. Praha", "Jihočeský kraj", "Karlovarský kraj", "Kraj Vysočina", "Královéhradecký kraj", "Liberecký kraj", "Pardubický kraj", "Plzeňský kraj", "Středočeský kraj", "neuvedeno", "Ústecký kraj"]}} |
| EQ-06 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["A01", "A02", "A03", "A05", "A06", "A09"], "unexpected": ["A48", "J15"]}} |
| EQ-06 | KG-RAG | 0 | - | - | {"diagnosis_code": {"missing": ["A01", "A02", "A03", "A09"], "unexpected": []}} |
| EQ-07 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["B00", "B01", "B02", "B04", "B05", "B06"], "unexpected": ["A08", "A81"]}} |
| EQ-07 | KG-RAG | 0 | - | - | {"diagnosis_code": {"missing": ["B00", "B01", "B02", "B04", "B05", "B06"], "unexpected": []}} |
| EQ-08 | RAG | 1 | - | - | - |
| EQ-08 | KG-RAG | 1 | - | - | - |
| EQ-09 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["J13", "J14"], "unexpected": []}} |
| EQ-09 | KG-RAG | 1 | - | - | - |
| EQ-10 | RAG | 0 | - | - | {"diagnosis_code": {"missing": ["J13", "J14"], "unexpected": []}} |
| EQ-10 | KG-RAG | 1 | - | - | - |

## Files

- `raw_results.json`: raw API responses for both methods.
- `diagnosis_metrics.csv`: per-question diagnosis precision, recall, F1, TP/FP/FN.
- `filter_metrics.csv`: per-question binary complete-filter comparison.
- `evaluation_summary.json`: aggregate metrics plus resolved gold filters.
- `run_evaluation.py`: reproducible runner.
