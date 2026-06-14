# Research questions and exact evaluation queries

Generated: 2026-06-13T12:27:59+00:00

Finálna evaluácia používa skutočné české dotazy posielané modelom a očakáva presné SQL/rendered-table výstupy.

## Three Research Questions

| ID | Research question | Evaluation queries | Why important |
| --- | --- | --- | --- |
| RQ-1 | Does KG-RAG improve exact diagnosis-code recall over standard RAG for Czech disease-family queries whose table labels do not all share the user’s wording? | EQ-01, EQ-07 | This is the core scientific claim: KG hierarchy expansion should recover codes that pure retrieval may miss. |
| RQ-2 | Does KG-RAG improve typed analytical-scope construction for SQL/table answers involving informal Czech time, age, and region expressions? | EQ-02, EQ-03, EQ-04, EQ-05, EQ-06 | The demo will answer through SQL/rendered tables, so the system must recover the exact scope before aggregation. |
| RQ-3 | Can KG-RAG preserve or improve precision and provenance while increasing recall, especially for absent hierarchy members and lexical outsiders? | EQ-01, EQ-07, EQ-08, EQ-09, EQ-10 | A top demo paper needs to show KG expansion is controlled, inspectable, and not just broader retrieval. |

## Evaluation Query Set

| ID | Czech query | English translation | Primary metric |
| --- | --- | --- | --- |
| EQ-01 | Porovnej střevní infekční nemoci v České republice podle diagnózy. | Compare intestinal infectious diseases in the Czech Republic by diagnosis. | exact diagnosis-code recall and weighted recall by pocet_pripadu |
| EQ-02 | Porovnej střevní infekční nemoci v letech 2020 and 2023 | Compare intestinal infectious diseases in years 2020 and 2023. | year recall + diagnosis-code recall |
| EQ-03 | Porovnej střevní infekční nemoci u dětí podle věkové skupiny. | Compare intestinal infectious diseases in children by age group. | official age-group recall |
| EQ-04 | Porovnej střevní infekční nemoci u seniorů 65+ podle věkové skupiny. | Compare intestinal infectious diseases in seniors 65+ by age group. | official age-group recall |
| EQ-05 | Porovnej střevní infekční nemoci na Moravě podle kraje. | Compare intestinal infectious diseases in Moravia by region. | region alias recall |
| EQ-06 | Kolik případů střevních infekčních nemocí bylo v Praze? | How many cases of intestinal infectious diseases were in Prague? | official region value accuracy |
| EQ-07 | Porovnej virové infekce kůže a sliznic podle diagnózy. | Compare viral infections of skin and mucous membranes by diagnosis. | exact diagnosis-code recall |
| EQ-08 | Porovnej virové hepatitidy podle diagnózy. | Compare viral hepatitis by diagnosis. | control-case recall / no-regression |
| EQ-09 | Porovnej pneumonie podle diagnózy. | Compare pneumonia by diagnosis. | synonym robustness + code recall |
| EQ-10 | Porovnej pneumonie podle kraje. | Compare pneumonia by region. | diagnosis-code recall + region aggregation correctness |

Full gold answers are in `reports/kg_rag_evaluation_questions.md` and `outputs/kg_rag_evaluation_queries.json`.
