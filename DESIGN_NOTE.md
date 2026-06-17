# Design Note

This note covers the three production concerns most likely to determine whether this system is trustworthy at scale: failure modes, the latency-quality trade-off, and data sensitivity. A final section addresses how the architecture holds up at 10× current ticket volume.

---

## Failure Modes

### 1. Missing or malformed input data

**What breaks:** `accounts.json` or `tickets.json` absent, empty, or containing unexpected field names. The data loader is schema-flexible — it probes a ranked list of candidate field names — but if none match, `account_id` defaults to a hash of the raw record and ticket metadata fields default to empty strings. A brief generated from a zero-field account is structurally valid but analytically worthless.

**Detection:** `GET /data-health` and `cli data-check` surface file existence, byte size, record counts, and parse errors before any downstream call is made. The `ready_for_account_briefs` flag gives a single go/no-go signal.

**Mitigation:** Validate data at ingest time using the health endpoint. Reject uploads that score `ready_for_account_briefs: false`. Add a JSON Schema or Pydantic pre-validation step at the loader boundary so field-mapping failures are explicit errors rather than silent defaults.

---

### 2. Misclassification and over-escalation

**What breaks:** The triage classifier uses keyword signal lists. A ticket containing "production" in a non-urgent context (e.g., "our production team likes the new dashboard") can trigger a P1 classification. Conversely, a genuine P1 phrased unusually ("everything ground to a halt this morning") may land at P3.

**Detection:** The evaluation harness (`triage_adversarial_vague`) tests that a deliberately vague ticket is not escalated to P1. Adding regression cases drawn from historical mis-escalations would tighten this further.

**Mitigation:** Expand signal lists with negation patterns (`not urgent`, `low priority`) and multi-signal AND logic (require two independent signals for P1). A thin LLM confirmation step — enabled only when `LLM_PROVIDER` is set — can be inserted as a second-pass verifier without breaking deterministic-default behaviour.

---

### 3. Retrieval mismatch or stale knowledge base

**What breaks:** Lexical overlap retrieval fails when the ticket uses different terminology from the KB. A ticket about "auth tokens expiring" may not score against a KB article titled "SAML session management". A stale KB (e.g., a resolved outage article left in place) can surface misleading `known_issue_match` results.

**Detection:** `retrieve_docs` returns confidence scores. A low top-score (< 0.15) is a reliable signal that no relevant article was found. The eval harness verifies that missing-KB conditions return `known_issue_match: null` rather than a hallucinated match.

**Mitigation:** Augment lexical scoring with a lightweight TF-IDF or BM25 index (no model weights, still fast). Introduce KB article expiry metadata (`valid_until`) so stale articles are automatically excluded. A KB freshness check can be surfaced in `/data-health`.

---

## Latency vs Quality

The system deliberately chooses local, deterministic processing over LLM chains for its critical path. Lexical retrieval completes in < 5 ms on a 100-article KB; rule-based classification adds < 1 ms. A full `POST /triage` round-trip runs in < 20 ms without I/O contention.

The trade-off: a fine-tuned embedding retriever or LLM-based classifier would catch edge cases the keyword approach misses — at the cost of 200–800 ms latency, an API key, and non-deterministic output. The current design is the right default for an assessment environment where reproducibility and offline operation matter. When LLM quality is needed, the `llm_client.py` adapter is already wired in and activates with a single env-var change.

---

## Data Sensitivity

No ticket content or account data leaves the process unless `LLM_PROVIDER` is set to an external provider. Even then:

- `redact_pii()` strips emails, phone numbers, IPv4 addresses, and long tokens/IDs from all KB snippets and risk-flag quotes before any outgoing call.
- `redact_record()` applies the same rules recursively to the full ticket payload before it reaches `llm_client.generate_json()`.
- The API never exposes Python stack traces in JSON error responses — only user-safe `detail` strings.
- No credentials are logged; `OPENAI_API_KEY` is read from `.env` only and never echoed.

---

## Scaling to 10× Ticket Volume

At 10× volume the two bottlenecks are JSON file I/O and linear account-ticket scans.

**Current:** `load_tickets()` reads and parses the entire `tickets.json` on every request. `get_tickets_for_account()` then performs a full linear scan. At 50 k tickets this is measurable; at 500 k it is unacceptable.

**Mitigations:**

1. **Indexed storage:** Replace flat JSON with SQLite (zero-dependency) or PostgreSQL. A composite index on `(account_id, created_at)` reduces `get_tickets_for_account` from O(n) to O(log n + k).
2. **In-process cache:** An LRU cache keyed on `(data_dir, mtime)` avoids re-parsing unchanged files between requests.
3. **Account-ticket map:** Pre-build a `Dict[account_id, List[ticket_id]]` at startup and refresh on file change, reducing per-request work to a single dict lookup.
4. **Async API:** Switch `account_brief` endpoint to `async def` with `asyncio.to_thread` for file I/O, allowing the FastAPI event loop to serve concurrent requests without blocking.
5. **Horizontal scaling:** The service is stateless (all state is in the data files); adding instances behind a load balancer requires only a shared read-only data volume.
