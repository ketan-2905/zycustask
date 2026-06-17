# Graph Report - support_ai  (2026-06-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 78 nodes · 174 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 70% EXTRACTED · 30% INFERRED · 0% AMBIGUOUS · INFERRED: 52 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]

## God Nodes (most connected - your core abstractions)
1. `triage_ticket()` - 14 edges
2. `Settings` - 10 edges
3. `RetrievalMatch` - 9 edges
4. `load_tickets()` - 8 edges
5. `load_accounts()` - 7 edges
6. `TicketInput` - 7 edges
7. `TriageOutput` - 7 edges
8. `load_knowledge_docs()` - 6 edges
9. `retrieve_docs()` - 6 edges
10. `LLMClient` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Settings`  [INFERRED]
  llm_client.py → config.py
- `LLMClient` --uses--> `Settings`  [INFERRED]
  llm_client.py → config.py
- `LLMUnavailable` --uses--> `Settings`  [INFERRED]
  llm_client.py → config.py
- `TicketInput` --uses--> `Settings`  [INFERRED]
  triage.py → config.py
- `Any` --uses--> `Settings`  [INFERRED]
  triage.py → config.py

## Import Cycles
- None detected.

## Communities (9 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.22
Nodes (7): LLMClient, LLMUnavailable, Settings, Any, redact_pii(), redact_record(), RuntimeError

### Community 1 - "Community 1"
Cohesion: 0.39
Nodes (11): coerce_records(), dataset_health(), extract_first(), get_account_by_id(), get_tickets_for_account(), load_accounts(), load_json_file(), load_tickets() (+3 more)

### Community 2 - "Community 2"
Cohesion: 0.24
Nodes (10): clamp_score(), clip_text(), dedupe_keep_order(), normalise_text(), Any, sorted_dict(), stable_json(), tokenize() (+2 more)

### Community 3 - "Community 3"
Cohesion: 0.38
Nodes (10): BaseModel, DataHealth, LoadedAccount, LoadedTicket, AccountBrief, DataHealth, EvalCaseResult, KnowledgeDoc (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.39
Nodes (8): build_doc_id(), extract_category(), extract_title(), lexical_score(), load_knowledge_docs(), RetrievalMatch, retrieve_docs(), KnowledgeDoc

### Community 5 - "Community 5"
Cohesion: 0.47
Nodes (8): draft_first_response(), infer_issue_category(), infer_product_area(), infer_urgency_tier(), recommend_team(), _signal_hits(), triage_ticket(), TriageOutput

### Community 6 - "Community 6"
Cohesion: 0.50
Nodes (8): RetrievalMatch, TicketInput, TriageOutput, TicketInput, normalize_ticket_input(), Any, RetrievalMatch, Settings

## Knowledge Gaps
- **2 isolated node(s):** `T`, `Any`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `triage_ticket()` connect `Community 5` to `Community 2`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.247) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 7` to `Community 0`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Why does `stable_hash()` connect `Community 1` to `Community 2`, `Community 4`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `triage_ticket()` (e.g. with `load_settings()` and `clamp_score()`) actually correct?**
  _`triage_ticket()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Settings` (e.g. with `LLMClient` and `LLMUnavailable`) actually correct?**
  _`Settings` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `RetrievalMatch` (e.g. with `RetrievalMatch` and `KnowledgeDoc`) actually correct?**
  _`RetrievalMatch` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `T`, `Any` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._