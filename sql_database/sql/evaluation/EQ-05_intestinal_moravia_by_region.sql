SELECT
  region_code,
  region_name_cs,
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count
FROM fact_infectious_disease_cases_enriched
WHERE mkn_block_code = 'A00-A09'
  AND region_code IN ('CZ064', 'CZ071', 'CZ072', 'CZ080')
GROUP BY region_code, region_name_cs
ORDER BY reported_case_count DESC, region_code;
