SELECT
  COUNT(*) AS fact_rows,
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count,
  MIN(report_year) AS min_report_year,
  MAX(report_year) AS max_report_year,
  COUNT(DISTINCT diagnosis_code) AS diagnosis_count,
  COUNT(DISTINCT region_code) AS region_count,
  COUNT(DISTINCT age_group_code) AS age_group_count
FROM fact_infectious_disease_cases_enriched;
