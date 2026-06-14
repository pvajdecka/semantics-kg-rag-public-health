WITH latest_year AS (
  SELECT MAX(report_year) AS max_year
  FROM fact_infectious_disease_cases_enriched
)
SELECT
  report_year,
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count
FROM fact_infectious_disease_cases_enriched, latest_year
WHERE mkn_block_code = 'A00-A09'
  AND report_year BETWEEN max_year - 2 AND max_year
GROUP BY report_year
ORDER BY report_year;
