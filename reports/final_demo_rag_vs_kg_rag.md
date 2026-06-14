# Final demo plan: RAG vs KG-RAG recall comparison

Generated: 2026-06-13T09:57:43+00:00

This report revises the earlier exploratory options into one final demo direction. It is still a design and evaluation plan only: no KG, KG-RAG pipeline, standard RAG pipeline, SQL QA, or final claim has been implemented.

Public-health aggregated data must not be used for clinical treatment recommendations or causal claims. `pocet_pripadu` is treated here as a reported table measure, not as prevalence, incidence, unique-patient count, or causal evidence.


## Final Demo Direction

The final demo should compare **standard RAG** with **KG-RAG** on recall for Czech public-health table exploration. The chosen task is not open-ended medical answering. It is retrieval of the complete, typed analytical scope needed before answering aggregate questions over the infectious-disease table.

The strongest primary case is **group-level retrieval for intestinal infectious diseases**. In MKN-10-CZ, the relevant block-level concept is represented by the A00-A09 diagnosis range. In the infectious-disease table, A01-A09 are present; A00 is present in MKN-10-CZ but has no rows in the infectious table. This gives a concrete gold set of 9 table diagnosis codes for evaluation.

### Why this is the right comparison

- The infectious-disease table has 272,858 rows and 11 columns with diagnosis code, Czech diagnosis label, region, age group, sex, year, month, EWS, and `pocet_pripadu`.
- The MKN-10-CZ code list has 39,136 rows and includes `kod`, `kod_tecka`, `nazev`, `kod_kapitola_rozsah`, `kod_kapitola_cislo`, and `nazev_kapitola`.
- All 114 infectious-disease diagnosis codes match MKN-10-CZ when using `infectious_diseases.diagnoza = mkn10_cz.kod`.
- All 17 infectious age-group codes match the age-group code list when using `infectious_diseases.vek_kod = age_groups.vek_kod`.
- The infectious table spans 2018-2025 (8 years), 15 region categories, 17 age groups, and 2 sex categories.
- A simple Czech lexical retrieval test for the substring `střev` retrieves only 4 diagnosis codes overall and 3 of the 9 A01-A09 gold codes, a direct lexical recall proxy of 33.3%. This is not the final RAG score, but it is strong evidence that value recall is a real risk.

## Standard RAG Architecture

1. Index table-derived text chunks: diagnosis labels, selected rows, profile snippets, metadata snippets, and maybe row-group summaries.
2. For a user question such as "Compare intestinal infections across regions and age groups in recent years," embed the question and retrieve top-k chunks.
3. Ask the LLM to infer the relevant diagnosis values, dimensions, and aggregation from retrieved chunks.
4. Execute or sketch the table query only over values that appeared in the retrieved context.

Expected weakness: the retriever may retrieve labels that literally contain `střevní`, but miss sibling diagnoses such as `A01 Břišní tyfus a paratyfus`, `A02 Jiné infekce způsobené salmonelami`, `A03 Shigelóza`, `A05 Jiné bakteriální intoxikace – otravy, přenesené potravou`, `A06 Amébóza`, or `A09 Jiná gastroenteritida a kolitida infekčního a NS původu`. It also has no explicit obligation to distinguish a missing table code from a relevant MKN code with no rows.

## KG-RAG Architecture

1. Retrieve an initial concept candidate from text: for example "intestinal infections" / "střevní infekce".
2. Link the candidate to typed entities: MKN-10 concept/range A00-A09, diagnosis codes, Czech labels, infectious-disease table values, age groups, regions, time dimensions, and measures.
3. Expand through graph relations before text retrieval:
   - `MKN block/range -> contains diagnosis code`
   - `diagnosis code -> Czech MKN label`
   - `diagnosis code -> infectious table diagnosis value`
   - `age phrase -> age_group code -> age_group label`
   - `region alias -> official region label`
   - `question intent -> required dimensions and measure`
4. Retrieve evidence after expansion, using the typed code set as constraints.
5. Produce an answer plan that exposes the selected scope and measures recall over the code/dimension set before any natural-language summary.

Expected strength: KG-RAG should retrieve all relevant in-table A01-A09 codes for the intestinal-infection group, while standard RAG may retrieve only the labels textually closest to the query. The graph also makes absent-but-relevant codes explicit: A00 exists in MKN-10-CZ but has no rows in the infectious table.


## Primary Gold Case: Intestinal Infectious Diseases

Gold concept: MKN-10-CZ A00-A09 intestinal infectious diseases.

Infectious-table gold codes: A01, A02, A03, A04, A05, A06, A07, A08, A09.

MKN-relevant but absent from infectious table: A00 Cholera.

Total reported table cases for in-table A01-A09 gold codes: 362,877 across 90,061 rows.

| Code | Czech label in infectious table | Reported cases |
| --- | --- | --- |
| A04 | Jiné bakteriální střevní infekce | 196550 |
| A02 | Jiné infekce způsobené salmonelami | 73222 |
| A08 | Střevní infekce viry a jinými určenými mikroorganismy | 69601 |
| A09 | Jiná gastroenteritida a kolitida infekčního a NS původu | 21048 |
| A03 | Shigelóza | 867 |
| A05 | Jiné bakteriální intoxikace – otravy, přenesené potravou | 789 |
| A07 | Jiné protozoární střevní nemoci | 704 |
| A06 | Amébóza | 69 |
| A01 | Břišní tyfus a paratyfus | 27 |

### Why this example should succeed

- It has high analytical mass: A01-A09 account for 362,877 reported cases in the loaded infectious-disease table.
- It has enough variety for a real recall test: 9 table codes, multiple labels, 8 years, 15 region categories, 17 age groups, and 2 sex categories.
- It has a clear failure mode for standard RAG: literal `střev` matching finds A04, A07, A08, B81, only 3 of the 9 A01-A09 table gold codes.
- It has a validated semantic bridge: all 114 infectious diagnosis codes match MKN-10-CZ by `diagnoza = kod`.
- It has a useful KG-RAG precision challenge: B81 contains `střevní` but is outside A00-A09, while A00 is in MKN but absent from the table.

## Analytical Follow-up Example

For the high-count intestinal subset A02, A04, A08, and A09, the top age groups are:

| Age group | Reported cases |
| --- | --- |
| 1–4 roky | 81763 |
| 75+ let | 44951 |
| 5–9 let | 37905 |
| 0 let | 25062 |
| 10–14 let | 24045 |

The top regions are:

| Region | Reported cases |
| --- | --- |
| Moravskoslezský kraj | 47860 |
| Jihomoravský kraj | 47565 |
| Středočeský kraj | 40529 |
| Hl. m. Praha | 31018 |
| Jihočeský kraj | 26225 |

These are useful for demo questions after retrieval is evaluated, but they should not be the primary contribution. The primary contribution is retrieval/scope recall.

## Comparison Protocol

1. Build a gold set for each query: diagnosis codes, dimensions, year range, age groups, and region categories.
2. Run standard RAG over the same textual assets available to KG-RAG: table values, row summaries, profiles, metadata, and code-list labels.
3. Run KG-RAG with the same text retriever, but add typed entity linking and graph expansion before evidence retrieval.
4. Compare:
   - diagnosis-code recall@k
   - exact set recall for A01-A09
   - weighted recall by `pocet_pripadu`
   - dimension recall for year, region, age, sex, month, and measure
   - absent-code/coverage-gap detection for A00
   - precision risk from lexical outsiders such as B81
5. Report failures explicitly. If dense RAG retrieves all A01-A09 codes, the paper should shift to explainability, coverage-gap handling, and typed-scope validation rather than claiming a simple recall win.

## Final Evaluation Questions

The evaluation set now contains actual Czech user queries sent to the models, with English translations and exact expected SQL/rendered-table answers. Details are in `reports/kg_rag_evaluation_questions.md` and `outputs/kg_rag_evaluation_queries.json`.

| ID | Czech query | English translation |
| --- | --- | --- |
| EQ-01 | Porovnej střevní infekční nemoci v České republice podle diagnózy. | Compare intestinal infectious diseases in the Czech Republic by diagnosis. |
| EQ-02 | Porovnej střevní infekční nemoci v letech 2020 and 2023 | Compare intestinal infectious diseases in years 2020 and 2023. |
| EQ-03 | Porovnej střevní infekční nemoci u dětí podle věkové skupiny. | Compare intestinal infectious diseases in children by age group. |
| EQ-04 | Porovnej střevní infekční nemoci u seniorů 65+ podle věkové skupiny. | Compare intestinal infectious diseases in seniors 65+ by age group. |
| EQ-05 | Porovnej střevní infekční nemoci na Moravě podle kraje. | Compare intestinal infectious diseases in Moravia by region. |
| EQ-06 | Kolik případů střevních infekčních nemocí bylo v Praze? | How many cases of intestinal infectious diseases were in Prague? |
| EQ-07 | Porovnej virové infekce kůže a sliznic podle diagnózy. | Compare viral infections of skin and mucous membranes by diagnosis. |
| EQ-08 | Porovnej virové hepatitidy podle diagnózy. | Compare viral hepatitis by diagnosis. |
| EQ-09 | Porovnej pneumonie podle diagnózy. | Compare pneumonia by diagnosis. |
| EQ-10 | Porovnej pneumonie podle kraje. | Compare pneumonia by region. |

The three research questions are stored in `outputs/research_questions_final.json` and summarized in `reports/research_opportunity_notes.md`.
