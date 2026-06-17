from __future__ import annotations

import json


def main() -> None:
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

    st.set_page_config(page_title="Zycus Support AI", layout="wide")
    st.title("Zycus Support AI")

    settings = load_settings()

    tab_health, tab_triage, tab_brief, tab_eval = st.tabs(
        ["Data Health", "Ticket Triage", "TAM Account Brief", "Evaluation"]
    )

    # ── Tab 1: Data Health ─────────────────────────────────────────────────────
    with tab_health:
        st.header("Data Health")
        health = dataset_health(settings.data_dir)
        if not health.ready_for_account_briefs:
            st.warning(
                "Data files are missing or empty. Account-brief commands will report "
                "precondition failures. No data is fabricated.\n\n"
                f"Expected paths: `{health.accounts_path}`, `{health.tickets_path}`"
            )
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Accounts")
            st.metric("Exists", "Yes" if health.accounts_exists else "No")
            st.metric("Records", health.accounts_count)
            st.metric("Bytes", health.accounts_bytes)
            if health.accounts_error:
                st.error(f"Error: {health.accounts_error}")
        with col2:
            st.subheader("Tickets")
            st.metric("Exists", "Yes" if health.tickets_exists else "No")
            st.metric("Records", health.tickets_count)
            st.metric("Bytes", health.tickets_bytes)
            if health.tickets_error:
                st.error(f"Error: {health.tickets_error}")
        with st.expander("Raw health JSON"):
            st.json(health.model_dump())

    # ── Tab 2: Ticket Triage ───────────────────────────────────────────────────
    with tab_triage:
        st.header("Ticket Triage")
        subject = st.text_input("Subject", placeholder="e.g. SSO login failing for all users")
        body = st.text_area("Body", placeholder="Describe the issue in detail…", height=120)
        if st.button("Triage ticket", key="triage_btn"):
            if not subject and not body:
                st.warning("Please enter a subject or body.")
            else:
                with st.spinner("Triaging…"):
                    result = triage_ticket(
                        {"subject": subject, "body": body},
                        kb_dir=settings.kb_dir,
                        settings=settings,
                    )
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Urgency", result.urgency_tier)
                col_b.metric("Category", result.issue_category)
                col_c.metric("Confidence", f"{result.confidence:.0%}")
                st.markdown(f"**Product area:** {result.product_area}")
                st.markdown(f"**Recommended team:** {result.recommended_team}")
                st.markdown(f"**Reasoning:** {result.reasoning}")
                if result.known_issue_match:
                    st.info(f"Known issue match: `{result.known_issue_match}`")
                if result.relevant_docs:
                    with st.expander(f"Relevant KB docs ({len(result.relevant_docs)})"):
                        for doc in result.relevant_docs:
                            st.markdown(f"- **{doc.title}** (score {doc.score:.2f}) — {doc.snippet}")
                st.subheader("Draft first response")
                st.text_area("Draft", value=result.draft_response, height=150, disabled=True)

    # ── Tab 3: TAM Account Brief ───────────────────────────────────────────────
    with tab_brief:
        st.header("TAM Account Brief")
        account_id = st.text_input("Account ID", placeholder="e.g. ACC-001")
        if st.button("Generate brief", key="brief_btn"):
            if not account_id.strip():
                st.warning("Please enter an account ID.")
            else:
                with st.spinner("Generating brief…"):
                    try:
                        brief = generate_account_brief(
                            account_id.strip(),
                            data_dir=settings.data_dir,
                            settings=settings,
                        )
                        st.subheader("Executive Summary")
                        st.write(brief.executive_summary)

                        st.subheader("Open Risks & Flagged Issues")
                        if brief.open_risks_and_flagged_issues:
                            for flag in brief.open_risks_and_flagged_issues:
                                st.markdown(f"- {flag}")
                        else:
                            st.success("No risk signals detected in the last 90 days.")

                        st.subheader("Recommended Talking Points")
                        for point in brief.recommended_talking_points:
                            st.markdown(f"- {point}")

                        with st.expander("Source ticket IDs"):
                            st.write(brief.source_ticket_ids or ["(none)"])

                    except AccountDataUnavailable as exc:
                        st.error(f"Data unavailable: {exc}")
                    except AccountNotFound as exc:
                        st.warning(f"Account not found: {exc}")

    # ── Tab 4: Evaluation ──────────────────────────────────────────────────────
    with tab_eval:
        st.header("Evaluation Harness")
        if st.button("Run evaluations", key="eval_btn"):
            with st.spinner("Running evals…"):
                results = run_all_evals(
                    data_dir=settings.data_dir,
                    kb_dir=settings.kb_dir,
                )
            summary = results["summary"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total cases", summary["total"])
            c2.metric("Passed", summary["passed"])
            c3.metric("Failed", summary["failed"])
            c4.metric("Pass rate", f"{summary['pass_rate']:.0%}")

            st.subheader("Results table")
            all_cases = results["triage"] + results["account_brief"]
            import pandas as pd

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
            st.dataframe(df, use_container_width=True)

            with st.expander("Markdown report"):
                st.markdown(render_markdown_report(results))


if __name__ == "__main__":
    main()
