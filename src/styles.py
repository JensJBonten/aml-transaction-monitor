import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1400px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        [data-testid="stMetric"] {
            background: #111A27;
            border: 1px solid #2A394D;
            border-radius: 3px;
            padding: 1rem;
        }

        [data-testid="stMetricLabel"] {
            color: #9CACBF;
        }

        [data-testid="stButton"] {
            margin-bottom: -0.35rem;
        }

        [data-testid="stButton"] > button,
        [data-testid="stButton"] button[data-testid^="stBaseButton"] {
            align-items: center !important;
            justify-content: flex-start !important;
            min-height: 2.75rem !important;
            padding: 0.55rem 0.75rem !important;
            text-align: left !important;
        }

        [data-testid="stButton"] button p {
            line-height: 1.25;
            margin: 0;
            text-align: left !important;
            width: 100%;
            white-space: normal;
        }

        [data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
            border-color: #4A86D4;
            box-shadow: inset 3px 0 0 #8AB4F8;
        }

        .st-key-queue_previous button,
        .st-key-queue_next button {
            justify-content: center !important;
        }

        .st-key-queue_previous button p,
        .st-key-queue_next button p {
            text-align: center !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid #2A394D;
            border-radius: 3px;
        }

        .trm-disclaimer {
            color: #9CACBF;
            font-size: 0.85rem;
            margin-bottom: 1.5rem;
        }

        .trm-summary {
            background: #162438;
            border-left: 4px solid #4A86D4;
            padding: 1rem 1.2rem;
            margin: 1rem 0 1.5rem;
        }

        .trm-summary-title {
            color: #FFFFFF;
            font-weight: 600;
            margin-bottom: 0.3rem;
        }

        .trm-case-summary {
            background: #162438;
            border-left: 4px solid #4A86D4;
            padding: 1rem;
            margin: 0.8rem 0 1.2rem;
        }

        .trm-priority {
            display: inline-block;
            font-weight: 600;
            margin-right: 0.6rem;
        }

        .trm-high {
            color: #FF8178;
        }

        .trm-medium {
            color: #F7C85C;
        }

        .trm-low {
            color: #8EC7A5;
        }

        .trm-score {
            color: #9CACBF;
        }

        .trm-page-count {
            color: #9CACBF;
            padding-top: 0.65rem;
            text-align: center;
        }

        hr {
            border-color: #2A394D;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
