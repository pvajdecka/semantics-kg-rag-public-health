# Data inventory

Generated: 2026-06-13T09:01:38+00:00

This inventory records acquisition and profiling status for the Czech public-health open-data sources used in the exploratory SEMANTiCS demo preparation.

Public-health aggregated data should not be used for clinical treatment recommendations or causal claims.

## Loaded datasets

| Dataset | Source URL | Local file | Shape | Encoding | Separator |
| --- | --- | --- | --- | --- | --- |
| infectious_diseases | https://datanzis.uzis.gov.cz/data/NR-27-ISIN/NR-27-01/Otevrena-data-NR-27-01-infekcni-nemoci.csv | data/raw/infectious_diseases.csv | 272858 x 11 | utf-8-sig | , |
| age_groups | https://datanzis.uzis.gov.cz/data/OIS-12-CIS/OIS-12-01/Otevrena-data-OIS-12-01-ciselnik-vekove-skupiny.csv | data/raw/age_groups.csv | 228 x 8 | utf-8-sig | , |
| mkn10_cz | https://data.mzcr.cz/data/distribuce/463/Otevrena-data-OIS-12-03-ciselnik-mkn-10-cz.csv | data/raw/mkn10_cz.csv | 39136 x 12 | utf-8-sig | , |
| hospitalization | https://data.mzcr.cz/data/distribuce/421/Otevrena-data-NR-23-01-hospitalizacni-pripady-akutni-intezivni-pece.csv.gz | data/raw/hospitalization.csv | 1418107 x 28 | utf-8-sig | , |

## Download records

```json
{
  "infectious_diseases": {
    "csv": {
      "url": "https://datanzis.uzis.gov.cz/data/NR-27-ISIN/NR-27-01/Otevrena-data-NR-27-01-infekcni-nemoci.csv",
      "local_path": "data/raw/infectious_diseases.csv",
      "downloaded_at": "2026-06-13T09:00:19+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 30181795,
      "sha256": "0af9f9f99ac37a4f38f790c8939696bb2eb80b9db1f83b6ef5e432ec3f8594a2"
    },
    "metadata": {
      "url": "https://datanzis.uzis.gov.cz/data/NR-27-ISIN/NR-27-01/Otevrena-data-NR-27-01-infekcni-nemoci.csv-metadata.json",
      "local_path": "data/metadata/infectious_diseases.metadata.json",
      "downloaded_at": "2026-06-13T09:00:19+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 4088,
      "sha256": "1fa7372b4bf4f9f6672b9f54478f3b06bfd42fdf00d663e3373082476ade4fc6"
    }
  },
  "age_groups": {
    "csv": {
      "url": "https://datanzis.uzis.gov.cz/data/OIS-12-CIS/OIS-12-01/Otevrena-data-OIS-12-01-ciselnik-vekove-skupiny.csv",
      "local_path": "data/raw/age_groups.csv",
      "downloaded_at": "2026-06-13T09:00:27+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 42252,
      "sha256": "b5059ceffa0fba951a12f99816ead2014fdb041c00bff5e251f997d474259ef2"
    },
    "metadata": {
      "url": "https://datanzis.uzis.gov.cz/data/OIS-12-CIS/OIS-12-01/Otevrena-data-OIS-12-01-ciselnik-vekove-skupiny.csv-metadata.json",
      "local_path": "data/metadata/age_groups.metadata.json",
      "downloaded_at": "2026-06-13T09:00:27+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 3172,
      "sha256": "f80d46cf1dbcc61627d983ad5566610e01ad98dccb1e5fff54974ff2c1dfd56d"
    }
  },
  "mkn10_cz": {
    "csv": {
      "url": "https://data.mzcr.cz/data/distribuce/463/Otevrena-data-OIS-12-03-ciselnik-mkn-10-cz.csv",
      "local_path": "data/raw/mkn10_cz.csv",
      "downloaded_at": "2026-06-13T09:00:27+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 13989166,
      "sha256": "f2b3ecf958844d93f4e65a1445261ffef1aa58572aa38f908da6cba488b3fc0e"
    },
    "metadata": {
      "url": "https://data.mzcr.cz/data/schemata/463/Otevrena-data-OIS-12-03-ciselnik-mkn-10-cz.csv-metadata.json",
      "local_path": "data/metadata/mkn10_cz.metadata.json",
      "downloaded_at": "2026-06-13T09:00:27+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 4388,
      "sha256": "442d30c59c64a88ee9e1c211aadf84e752d4ef784eaa4dd657d9f6b30a766a95"
    }
  },
  "hospitalization": {
    "csv": {
      "url": "https://data.mzcr.cz/data/distribuce/421/Otevrena-data-NR-23-01-hospitalizacni-pripady-akutni-intezivni-pece.csv.gz",
      "local_path": "data/raw/hospitalization.csv",
      "downloaded_at": "2026-06-13T09:00:30+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 110888129,
      "sha256": "e260456f35da6f624211b102358ab8af336a17d7594ef976edb89215527c7d1b"
    },
    "metadata": {
      "url": "https://data.mzcr.cz/data/schemata/421/Otevrena-data-NR-23-01-hospitalizacni-pripady-akutni-intezivni-pece.csv-metadata.json",
      "local_path": "data/metadata/hospitalization.metadata.json",
      "downloaded_at": "2026-06-13T09:00:30+00:00",
      "status": "cached",
      "warnings": [],
      "bytes": 8541,
      "sha256": "25b0c57d2c80a0ef7ab2c8312be7d3361237a33cb9677b763a5e0f8fc408fd1d"
    }
  },
  "samples": {
    "infectious_diseases": {
      "path": "data/samples/infectious_diseases_sample.csv",
      "rows": 10000
    },
    "age_groups": {
      "path": "data/samples/age_groups_sample.csv",
      "rows": 228
    },
    "mkn10_cz": {
      "path": "data/samples/mkn10_cz_sample.csv",
      "rows": 10000
    },
    "hospitalization": {
      "path": "data/samples/hospitalization_sample.csv",
      "rows": 10000
    }
  }
}
```

## Failed or skipped datasets

No failed datasets.

## Discovered web-page links

The full machine-readable discovery output is saved in `data/metadata/discovered_links.json`.

### mkn10_cz

- CSV links discovered: 2
- JSON links discovered: 1
- metadata links discovered: 1
- PDF/methodology links discovered: 1

### hospitalization

- CSV links discovered: 2
- JSON links discovered: 1
- metadata links discovered: 1
- PDF/methodology links discovered: 1
