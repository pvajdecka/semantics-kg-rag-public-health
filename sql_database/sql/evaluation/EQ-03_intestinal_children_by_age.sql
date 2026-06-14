SELECT
  age_group_code,
  age_group_name_cs,
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count
FROM fact_infectious_disease_cases_enriched
WHERE mkn_block_code = 'A00-A09'
  AND age_to_inclusive <= 14
GROUP BY age_group_code, age_group_name_cs, age_from_inclusive
ORDER BY reported_case_count DESC, age_from_inclusive;
