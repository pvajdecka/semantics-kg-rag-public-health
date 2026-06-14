SELECT
  diagnosis_code,
  diagnosis_name_cs,
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count
FROM fact_infectious_disease_cases_enriched
WHERE mkn_block_code = 'B00-B09'
GROUP BY diagnosis_code, diagnosis_name_cs
ORDER BY reported_case_count DESC, diagnosis_code;
