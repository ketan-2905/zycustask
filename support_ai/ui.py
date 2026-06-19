"""Streamlit UI for Zycus Support AI.

Entry point: streamlit run support_ai/ui.py

No unsafe_allow_html is used — all styling is done via native Streamlit
components and .streamlit/config.toml so the app renders correctly on
Streamlit Cloud without raw HTML leaking into the page.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── Ensure project root is on sys.path so `support_ai` is importable on Cloud
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    import pandas as pd
    import streamlit as st

    from support_ai.account_brief import (
        AccountDataUnavailable,
        AccountNotFound,
        generate_account_brief,
    )
    from support_ai.config import load_settings
    from support_ai.data_loader import dataset_health
    from support_ai.evals import render_markdown_report, run_all_evals
    from support_ai.triage import triage_ticket

    # ── Page config ─────────────────────────────────────────────────────────
    st.set_page_config(
        page_title="Zycus Support AI",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    settings = load_settings()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("🤖 Zycus Support AI")
        st.caption("AI-powered ticket triage · TAM account briefs · Evaluation harness")
        st.divider()
        st.markdown("### ⚙️ Configuration")
        st.markdown(f"**LLM Provider:** `{settings.llm_provider}`")
        st.markdown(f"**Data Dir:** `{settings.data_dir}`")
        st.markdown(f"**KB Dir:** `{settings.kb_dir}`")
        st.markdown(f"**App Env:** `{settings.app_env}`")
        st.divider()
        st.markdown("### 📚 Links")
        st.markdown("[📖 README](https://github.com/ketan-2905/zycustask/blob/main/README.md)")
        st.markdown("[🏗️ Design Note](https://github.com/ketan-2905/zycustask/blob/main/DESIGN_NOTE.md)")
        st.divider()
        st.caption("All responses are fully deterministic by default (LLM_PROVIDER=none).")

    # ── Main title ───────────────────────────────────────────────────────────
    st.title("🤖 Zycus Support AI")
    st.caption("AI-powered ticket triage · TAM account briefs · Evaluation harness")
    st.divider()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_health, tab_triage, tab_brief, tab_eval = st.tabs(
        ["🏥 Data Health", "🎫 Ticket Triage", "📊 Account Brief", "🧪 Evaluation"]
    )

    # ════════════════════════════════════════════════════════════════════════
    # Tab 1 – Data Health
    # ════════════════════════════════════════════════════════════════════════
    with tab_health:
        st.header("Data & Knowledge-Base Health")
        health = dataset_health(settings.data_dir)

        if health.ready_for_account_briefs:
            st.success("✅ Data files are present and ready for account briefs.")
        else:
            st.warning(
                "⚠️ Data files are missing or empty. Ticket triage still works with "
                "deterministic rules, but account-specific briefs need starter data.\n\n"
                f"Expected paths: `{health.accounts_path}` · `{health.tickets_path}`"
            )

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("👥 Accounts dataset")
            a1, a2, a3 = st.columns(3)
            a1.metric("Exists", "✓" if health.accounts_exists else "✗")
            a2.metric("Records", health.accounts_count)
            a3.metric("Bytes", health.accounts_bytes)
            if health.accounts_error:
                st.error(f"Error: {health.accounts_error}")

        with col2:
            st.subheader("🎫 Tickets dataset")
            b1, b2, b3 = st.columns(3)
            b1.metric("Exists", "✓" if health.tickets_exists else "✗")
            b2.metric("Records", health.tickets_count)
            b3.metric("Bytes", health.tickets_bytes)
            if health.tickets_error:
                st.error(f"Error: {health.tickets_error}")

        with st.expander("🔍 Raw health JSON"):
            st.json(health.model_dump())

    # ════════════════════════════════════════════════════════════════════════
    # Tab 2 – Ticket Triage
    # ════════════════════════════════════════════════════════════════════════
    with tab_triage:
        st.header("Triage a Support Ticket")
        st.caption(
            "The engine classifies category, urgency, routes to the right team, and drafts a "
            "first response — all deterministically, no LLM required."
        )

        subject = st.text_input(
            "Subject",
            placeholder="e.g. SSO login failing for all production users",
        )
        body = st.text_area(
            "Body / Description",
            placeholder="Describe the issue in detail…",
            height=130,
        )

        if st.button("🚀 Triage ticket", key="triage_btn", use_container_width=False):
            if not subject.strip() and not body.strip():
                st.warning("Please enter a subject or body before triaging.")
            else:
                with st.spinner("Analysing ticket…"):
                    result = triage_ticket(
                        {"subject": subject, "body": body},
                        kb_dir=settings.kb_dir,
                        settings=settings,
                    )

                st.divider()
                st.subheader("📋 Triage Result")

                # Priority label mapping
                _priority_labels = {
                    "P1": "🔴 P1 — Critical",
                    "P2": "🟠 P2 — High",
                    "P3": "🟡 P3 — Medium",
                    "P4": "🟢 P4 — Low",
                }
                priority_label = _priority_labels.get(result.urgency_tier, result.urgency_tier)

                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("🚨 Priority", priority_label)
                col_b.metric("🏷️ Category", result.issue_category.replace("_", " ").title())
                col_c.metric("📐 Confidence", f"{result.confidence:.0%}")
                col_d.metric("🏢 Product Area", result.product_area.replace("_", " ").title())

                st.info(f"**🏆 Recommended Team:** {result.recommended_team}")

                with st.expander("🧠 Reasoning", expanded=True):
                    st.write(result.reasoning)

                if result.known_issue_match:
                    st.success(f"🔗 Known issue match: `{result.known_issue_match}`")

                if result.relevant_docs:
                    with st.expander(f"📚 Relevant KB docs ({len(result.relevant_docs)})"):
                        for doc in result.relevant_docs:
                            st.markdown(
                                f"**{doc.title}** — score `{doc.score:.2f}`  \n{doc.snippet}"
                            )

                st.subheader("✉️ Draft First Response")
                st.text_area(
                    "Draft (read-only)",
                    value=result.draft_response,
                    height=160,
                    disabled=True,
                    label_visibility="collapsed",
                )

    # ════════════════════════════════════════════════════════════════════════
    # Tab 3 – TAM Account Brief
    # ════════════════════════════════════════════════════════════════════════
    with tab_brief:
        st.header("TAM Account Brief Generator")
        st.caption(
            "Generate an executive-ready brief with risk flags and talking points. "
            "Requires `data/accounts.json` and `data/tickets.json`."
        )

        account_id = st.text_input("Account ID", placeholder="e.g. ACC-001")

        if st.button("📊 Generate brief", key="brief_btn"):
            if not account_id.strip():
                st.warning("Please enter an account ID.")
            else:
                with st.spinner("Generating account brief…"):
                    try:
                        brief = generate_account_brief(
                            account_id.strip(),
                            data_dir=settings.data_dir,
                            settings=settings,
                        )

                        st.divider()
                        st.subheader(f"📋 Brief — {account_id.strip()}")

                        st.subheader("📝 Executive Summary")
                        st.info(brief.executive_summary or "_No summary available._")

                        st.subheader("⚠️ Open Risks & Flagged Issues")
                        if brief.open_risks_and_flagged_issues:
                            for flag in brief.open_risks_and_flagged_issues:
                                st.warning(f"• {flag}")
                        else:
                            st.success("✅ No risk signals detected in the last 90 days.")

                        st.subheader("💡 Recommended Talking Points")
                        for i, point in enumerate(brief.recommended_talking_points, 1):
                            st.markdown(f"**{i}.** {point}")

                        with st.expander("🔖 Source ticket IDs"):
                            if brief.source_ticket_ids:
                                for tid in brief.source_ticket_ids:
                                    st.markdown(f"- `{tid}`")
                            else:
                                st.caption("No source tickets referenced.")

                        if getattr(brief, "deterministic", False):
                            st.caption("✓ Generated deterministically — no LLM was called.")

                    except AccountDataUnavailable as exc:
                        st.error(
                            f"**Data unavailable:** {exc}\n\n"
                            "Add `data/accounts.json` and `data/tickets.json` to enable "
                            "account briefs."
                        )
                    except AccountNotFound as exc:
                        st.warning(
                            f"**Account not found:** `{account_id.strip()}`\n\n{exc}"
                        )

    # ════════════════════════════════════════════════════════════════════════
    # Tab 4 – Evaluation
    # ════════════════════════════════════════════════════════════════════════
    with tab_eval:
        st.header("Evaluation Harness")
        st.caption(
            "Runs the built-in eval suite across triage and account-brief tasks. "
            "Triage cases are fully deterministic; account-brief cases need starter data."
        )

        if st.button("▶️ Run evaluations", key="eval_btn"):
            with st.spinner("Running evaluation suite — this may take a few seconds…"):
                results = run_all_evals(
                    data_dir=settings.data_dir,
                    kb_dir=settings.kb_dir,
                )

            summary = results["summary"]
            pass_rate = summary["pass_rate"]

            st.divider()
            st.subheader("📈 Summary")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📦 Total cases", summary["total"])
            c2.metric("✅ Passed", summary["passed"])
            c3.metric("❌ Failed", summary["failed"])
            c4.metric("📈 Pass rate", f"{pass_rate:.0%}")

            # Progress bar (native)
            st.progress(pass_rate, text=f"Pass rate: {pass_rate:.0%}")

            if pass_rate >= 0.7:
                st.success(f"✅ Pass rate {pass_rate:.0%} — above 70% threshold.")
            elif pass_rate >= 0.5:
                st.warning(f"⚠️ Pass rate {pass_rate:.0%} — below 70% threshold.")
            else:
                st.error(f"❌ Pass rate {pass_rate:.0%} — significant failures detected.")

            # Results table
            st.subheader("📋 Results table")
            all_cases = results["triage"] + results["account_brief"]
            df = pd.DataFrame(
                [
                    {
                        "Task": r["task"],
                        "Case ID": r["case_id"],
                        "Pass": "✓" if r["passed"] else "✗",
                        "Score": f"{r['quality_score']:.2f}",
                        "Reasons": "; ".join(r["reasons"]),
                    }
                    for r in all_cases
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            with st.expander("📄 Markdown report"):
                st.markdown(render_markdown_report(results))

            with st.expander("🔩 Raw JSON output"):
                st.json(results)


if __name__ == "__main__":
    main()
