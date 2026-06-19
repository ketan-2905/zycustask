"""Streamlit UI for Zycus Support AI.

Entry point: streamlit run support_ai/ui.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── Path fix: ensure project root is on sys.path so `support_ai` is importable
# whether the app is run locally (python -m streamlit run support_ai/ui.py)
# or on Streamlit Cloud (where CWD may not be on PYTHONPATH).
_ROOT = Path(__file__).resolve().parent.parent  # …/zycustask/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:  # noqa: PLR0912, PLR0915  (many branches/statements by design)
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

    # ── Page config ────────────────────────────────────────────────────────────
    st.set_page_config(
        page_title="Zycus Support AI",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── Custom CSS ─────────────────────────────────────────────────────────────
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Dark gradient background */
        .stApp {
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
        }

        /* Hero header */
        .hero-header {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        }
        .hero-header h1 {
            color: white !important;
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
        }
        .hero-header p {
            color: rgba(255,255,255,0.85) !important;
            font-size: 1rem !important;
            margin: 0.4rem 0 0 !important;
        }

        /* Cards */
        .card {
            background: rgba(255, 255, 255, 0.07);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 24px rgba(0,0,0,0.2);
        }

        /* Badge chips */
        .badge {
            display: inline-block;
            padding: 0.2rem 0.75rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.04em;
        }
        .badge-p1 { background: #ff4757; color: white; }
        .badge-p2 { background: #ff6b35; color: white; }
        .badge-p3 { background: #ffa502; color: #1a1a1a; }
        .badge-p4 { background: #2ed573; color: #1a1a1a; }
        .badge-info { background: #5352ed; color: white; }

        /* Result metric cards */
        .result-card {
            background: rgba(102, 126, 234, 0.15);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
        }
        .result-card .label {
            font-size: 0.75rem;
            font-weight: 500;
            color: rgba(255,255,255,0.6);
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .result-card .value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #a78bfa;
            margin-top: 0.25rem;
        }

        /* Draft response box */
        .draft-box {
            background: rgba(0,0,0,0.3);
            border-left: 4px solid #667eea;
            border-radius: 0 10px 10px 0;
            padding: 1.2rem 1.5rem;
            color: rgba(255,255,255,0.9);
            font-size: 0.95rem;
            line-height: 1.7;
            white-space: pre-wrap;
        }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 0.35rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 9px !important;
            font-weight: 500 !important;
            color: rgba(255,255,255,0.7) !important;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(90deg, #667eea, #764ba2) !important;
            color: white !important;
        }

        /* Buttons */
        .stButton > button {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.8rem !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.35) !important;
        }
        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.55) !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: rgba(15, 12, 41, 0.95) !important;
            border-right: 1px solid rgba(255,255,255,0.08) !important;
        }

        /* Inputs */
        .stTextInput input, .stTextArea textarea {
            background: rgba(255,255,255,0.07) !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-radius: 10px !important;
            color: white !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #667eea !important;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.25) !important;
        }

        /* Metrics */
        [data-testid="metric-container"] {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 1rem;
        }
        [data-testid="stMetricLabel"] { color: rgba(255,255,255,0.65) !important; }
        [data-testid="stMetricValue"] { color: #a78bfa !important; }

        /* Section dividers */
        .section-title {
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: rgba(255,255,255,0.4);
            margin: 1.2rem 0 0.6rem;
        }

        /* Dataframe */
        .stDataFrame { border-radius: 12px; overflow: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Hero header ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="hero-header">
          <h1>🤖 Zycus Support AI</h1>
          <p>AI-powered ticket triage · TAM account briefs · Evaluation harness</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    settings = load_settings()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.markdown(f"**LLM Provider:** `{settings.llm_provider}`")
        st.markdown(f"**Data Dir:** `{settings.data_dir}`")
        st.markdown(f"**KB Dir:** `{settings.kb_dir}`")
        st.markdown(f"**App Env:** `{settings.app_env}`")
        st.markdown("---")
        st.markdown("### 📚 Quick links")
        st.markdown("- [README](https://github.com/ketan-2905/zycustask/blob/main/README.md)")
        st.markdown("- [Design Note](https://github.com/ketan-2905/zycustask/blob/main/DESIGN_NOTE.md)")
        st.markdown("---")
        st.caption("All responses are fully deterministic by default (LLM_PROVIDER=none).")

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_health, tab_triage, tab_brief, tab_eval = st.tabs(
        ["🏥 Data Health", "🎫 Ticket Triage", "📊 Account Brief", "🧪 Evaluation"]
    )

    # ── Tab 1: Data Health ─────────────────────────────────────────────────────
    with tab_health:
        st.markdown("### Data & Knowledge-Base Health")
        health = dataset_health(settings.data_dir)

        overall_ok = health.ready_for_account_briefs
        if overall_ok:
            st.success("✅ Data files are present and ready.")
        else:
            st.warning(
                "⚠️ Data files are missing or empty. Account-brief and triage will still work "
                "using deterministic rules, but account-specific briefs need starter data.\n\n"
                f"Expected: `{health.accounts_path}`, `{health.tickets_path}`"
            )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 👥 Accounts dataset")
            c1a, c1b, c1c = st.columns(3)
            c1a.metric("Exists", "✓" if health.accounts_exists else "✗")
            c1b.metric("Records", health.accounts_count)
            c1c.metric("Bytes", health.accounts_bytes)
            if health.accounts_error:
                st.error(f"Error: {health.accounts_error}")
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 🎫 Tickets dataset")
            c2a, c2b, c2c = st.columns(3)
            c2a.metric("Exists", "✓" if health.tickets_exists else "✗")
            c2b.metric("Records", health.tickets_count)
            c2c.metric("Bytes", health.tickets_bytes)
            if health.tickets_error:
                st.error(f"Error: {health.tickets_error}")
            st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("🔍 Raw health JSON"):
            st.json(health.model_dump())

    # ── Tab 2: Ticket Triage ───────────────────────────────────────────────────
    with tab_triage:
        st.markdown("### Triage a Support Ticket")
        st.caption(
            "Enter a ticket subject and body. The engine classifies category, urgency, "
            "routes to the right team, and drafts a first response — all without an LLM."
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

        col_presets, _ = st.columns([3, 1])
        with col_presets:
            preset = st.selectbox(
                "Quick presets",
                [
                    "— pick a demo ticket —",
                    "P1 Outage: Production system down for all users",
                    "Billing: Invoice charged twice this cycle",
                    "SSO: SAML login broken for all users",
                    "API: Webhook endpoint returning 500 errors",
                    "How-to: How do I configure SSO?",
                ],
                label_visibility="collapsed",
            )

        if preset and preset != "— pick a demo ticket —":
            _demos = {
                "P1 Outage: Production system down for all users": (
                    "Production system down",
                    "Complete outage for all users in production. System is down and data loss is occurring.",
                ),
                "Billing: Invoice charged twice this cycle": (
                    "Invoice is incorrect",
                    "We were charged twice for our subscription this billing cycle.",
                ),
                "SSO: SAML login broken for all users": (
                    "SSO login broken",
                    "Users cannot authenticate via SAML SSO since this morning. All production users affected.",
                ),
                "API: Webhook endpoint returning 500 errors": (
                    "Webhook failing",
                    "Our webhook endpoint is returning 500 on every POST payload. Integration is broken.",
                ),
                "How-to: How do I configure SSO?": (
                    "How to configure SSO",
                    "I have a question about how to set up SAML SSO. Need documentation or a guide.",
                ),
            }
            _subj, _body = _demos[preset]
            subject = _subj
            body = _body

        if st.button("🚀 Triage ticket", key="triage_btn"):
            if not subject and not body:
                st.warning("Please enter a subject or body.")
            else:
                with st.spinner("Analysing ticket…"):
                    result = triage_ticket(
                        {"subject": subject, "body": body},
                        kb_dir=settings.kb_dir,
                        settings=settings,
                    )

                st.markdown("---")
                st.markdown("#### 📋 Triage Result")

                # Priority badge colours
                _badge_class = {
                    "P1": "badge-p1",
                    "P2": "badge-p2",
                    "P3": "badge-p3",
                    "P4": "badge-p4",
                }.get(result.urgency_tier, "badge-info")

                st.markdown(
                    f'<span class="badge {_badge_class}">{result.urgency_tier} — {result.urgency_tier}</span>',
                    unsafe_allow_html=True,
                )

                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("🚨 Urgency", result.urgency_tier)
                col_b.metric("🏷️ Category", result.issue_category.replace("_", " ").title())
                col_c.metric("📐 Confidence", f"{result.confidence:.0%}")
                col_d.metric("🏢 Product Area", result.product_area.title())

                st.markdown(
                    f'<div class="card">'
                    f'<div class="section-title">Recommended Team</div>'
                    f'<div style="font-size:1.15rem;font-weight:600;color:#a78bfa;">🏆 {result.recommended_team}</div>'
                    f'<div class="section-title" style="margin-top:1rem;">Reasoning</div>'
                    f'<div style="color:rgba(255,255,255,0.8);font-size:0.9rem;">{result.reasoning}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if result.known_issue_match:
                    st.info(f"🔗 Known issue match: `{result.known_issue_match}`")

                if result.relevant_docs:
                    with st.expander(f"📚 Relevant KB docs ({len(result.relevant_docs)})"):
                        for doc in result.relevant_docs:
                            st.markdown(
                                f"- **{doc.title}** — score `{doc.score:.2f}`  \n  {doc.snippet}"
                            )

                st.markdown("#### ✉️ Draft First Response")
                st.markdown(
                    f'<div class="draft-box">{result.draft_response}</div>',
                    unsafe_allow_html=True,
                )

    # ── Tab 3: TAM Account Brief ───────────────────────────────────────────────
    with tab_brief:
        st.markdown("### TAM Account Brief Generator")
        st.caption(
            "Generate an executive-ready account brief with risk flags and talking points. "
            "Requires the starter data files (`data/accounts.json`, `data/tickets.json`)."
        )

        account_id = st.text_input("Account ID", placeholder="e.g. ACC-001")

        if st.button("📊 Generate brief", key="brief_btn"):
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

                        st.markdown("---")
                        st.markdown(
                            f'<div class="card">'
                            f'<div style="font-size:0.75rem;font-weight:600;text-transform:uppercase;'
                            f'letter-spacing:0.1em;color:rgba(255,255,255,0.5);">Account</div>'
                            f'<div style="font-size:1.5rem;font-weight:700;color:white;">'
                            f'{account_id.strip()}</div>'
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                        st.markdown("#### 📝 Executive Summary")
                        st.markdown(
                            f'<div class="draft-box">{brief.executive_summary}</div>',
                            unsafe_allow_html=True,
                        )

                        st.markdown("#### ⚠️ Open Risks & Flagged Issues")
                        if brief.open_risks_and_flagged_issues:
                            for flag in brief.open_risks_and_flagged_issues:
                                st.markdown(f"- {flag}")
                        else:
                            st.success("✅ No risk signals detected in the last 90 days.")

                        st.markdown("#### 💡 Recommended Talking Points")
                        for i, point in enumerate(brief.recommended_talking_points, 1):
                            st.markdown(f"**{i}.** {point}")

                        with st.expander("🔖 Source ticket IDs"):
                            if brief.source_ticket_ids:
                                st.write(brief.source_ticket_ids)
                            else:
                                st.caption("No source tickets found.")

                        if hasattr(brief, "deterministic") and brief.deterministic:
                            st.caption("✓ This brief was generated deterministically (no LLM).")

                    except AccountDataUnavailable as exc:
                        st.error(
                            f"⚠️ **Data unavailable:** {exc}\n\n"
                            "Add `data/accounts.json` and `data/tickets.json` to enable account briefs."
                        )
                    except AccountNotFound as exc:
                        st.warning(f"🔍 **Account not found:** `{account_id.strip()}` — {exc}")

    # ── Tab 4: Evaluation ──────────────────────────────────────────────────────
    with tab_eval:
        st.markdown("### Evaluation Harness")
        st.caption(
            "Runs the built-in eval suite across triage and account-brief tasks. "
            "Triage cases are fully deterministic; account-brief cases require starter data."
        )

        if st.button("▶️ Run evaluations", key="eval_btn"):
            with st.spinner("Running evaluation suite…"):
                results = run_all_evals(
                    data_dir=settings.data_dir,
                    kb_dir=settings.kb_dir,
                )

            summary = results["summary"]
            pass_rate = summary["pass_rate"]

            # Summary metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📦 Total cases", summary["total"])
            c2.metric("✅ Passed", summary["passed"])
            c3.metric("❌ Failed", summary["failed"])
            c4.metric(
                "📈 Pass rate",
                f"{pass_rate:.0%}",
                delta=f"{pass_rate - 0.5:.0%} vs 50% baseline",
            )

            # Colour-coded pass-rate bar
            _colour = "#2ed573" if pass_rate >= 0.7 else "#ffa502" if pass_rate >= 0.5 else "#ff4757"
            st.markdown(
                f'<div style="background:rgba(255,255,255,0.08);border-radius:999px;height:10px;margin:0.5rem 0 1rem;">'
                f'<div style="background:{_colour};width:{pass_rate:.0%};border-radius:999px;height:10px;'
                f'transition:width 0.6s ease;"></div></div>',
                unsafe_allow_html=True,
            )

            # Results table
            st.markdown("#### 📋 Results table")
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
            st.dataframe(df, use_container_width=True)

            with st.expander("📄 Markdown report"):
                st.markdown(render_markdown_report(results))

            with st.expander("🔩 Raw JSON"):
                st.json(results)


if __name__ == "__main__":
    main()
