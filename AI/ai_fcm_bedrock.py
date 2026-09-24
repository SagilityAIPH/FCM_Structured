import json
import os
import re
import time
from io import BytesIO

import fitz  # PyMuPDF
import pandas as pd
import streamlit as st
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# STREAMLIT CONFIG - 70% WIDTH ONLY
# ============================================================

st.set_page_config(
    page_title="AI-FCM Full Text Reasoning",
    page_icon="🧠",
    layout="centered"
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 70vw !important;
            padding-top: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        @media (max-width: 1200px) {
            .block-container {
                max-width: 92vw !important;
            }
        }

        textarea {
            font-size: 13px !important;
            line-height: 1.35 !important;
        }

        .stButton > button {
            width: 100%;
            border-radius: 10px;
            font-weight: 600;
        }

        .stDownloadButton > button {
            width: 100%;
            border-radius: 10px;
            font-weight: 600;
        }

        table {
            width: 100%;
        }

        th, td {
            font-size: 14px !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)



try:
    from .bedrock_core import *
except ImportError:
    from bedrock_core import *

def resolve_bedrock_api_key(manual_key: str = "") -> str:
    """
    Priority:
    1. Key entered in the Streamlit sidebar
    2. OPENAI_API_KEY environment variable
    3. Streamlit secret named OPENAI_API_KEY
    """
    manual_key = (manual_key or "").strip()
    if manual_key:
        return manual_key

    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    try:
        secret_key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        if secret_key:
            return secret_key
    except Exception:
        pass

    return ""


# ============================================================
# UI
# ============================================================

st.title("🧠 AI-FCM Bedrock Extraction")
st.caption(
    "Selectable PDF / DOCX / TXT → extracted text → Amazon Bedrock "
    "(OpenAI-compatible Mantle API) → validated required fields"
)

with st.sidebar:
    st.header("Amazon Bedrock Settings")

    bedrock_region = st.text_input(
        "AWS Region",
        value=os.getenv("AWS_REGION", DEFAULT_BEDROCK_REGION),
        help="Your screenshot shows US East (Ohio), which is us-east-2.",
    ).strip()

    bedrock_model = st.text_input(
        "Model ID",
        value=os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL),
        help="For the Mantle endpoint, gpt-oss-120b uses openai.gpt-oss-120b.",
    ).strip()

    manual_api_key = st.text_input(
        "Bedrock API key",
        value="",
        type="password",
        placeholder="Leave blank to use OPENAI_API_KEY",
        help=(
            "For production, prefer OPENAI_API_KEY in the environment or "
            "Streamlit secrets instead of saving the key in source code."
        ),
    )

    bedrock_api_key = resolve_bedrock_api_key(manual_api_key)
    bedrock_base_url = build_bedrock_base_url(bedrock_region)

    st.caption("Mantle endpoint")
    st.code(bedrock_base_url, language=None)

    if bedrock_api_key:
        if manual_api_key.strip():
            st.success("Bedrock API key entered for this session.")
        else:
            st.success("Bedrock API key found in environment/secrets.")
    else:
        st.warning("No Bedrock API key configured yet.")

    if st.button("Test Bedrock Connection"):
        if not bedrock_region:
            st.error("Enter an AWS region.")
        elif not bedrock_model:
            st.error("Enter a Bedrock model ID.")
        elif not bedrock_api_key:
            st.error("Enter a Bedrock API key or set OPENAI_API_KEY.")
        else:
            try:
                with st.spinner("Testing Bedrock inference access..."):
                    test_client = create_bedrock_client(
                        api_key=bedrock_api_key,
                        base_url=bedrock_base_url,
                    )
                    test_result = test_bedrock_connection(test_client, bedrock_model)

                if "BEDROCK_OK" in test_result.upper():
                    st.success("Bedrock connection and inference are working.")
                else:
                    st.success("Bedrock responded successfully.")
                    st.caption(f"Response: {test_result[:200] or '[empty content]'}")
            except Exception as e:
                st.error(f"Bedrock test failed: {e}")

    st.divider()
    st.subheader("Inference Settings")

    max_tokens = st.number_input(
        "Max output tokens",
        min_value=128,
        max_value=4096,
        value=DEFAULT_MAX_TOKENS,
        step=128,
    )

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=0.5,
        value=DEFAULT_TEMP,
        step=0.05,
    )

    max_doc_chars = st.number_input(
        "Max document characters sent to Bedrock",
        min_value=5000,
        max_value=400000,
        value=DEFAULT_MAX_DOC_CHARS,
        step=5000,
        help=(
            "gpt-oss-120b has a large context window, but keeping a cap avoids "
            "accidentally sending extremely large documents."
        ),
    )

uploaded_file = st.file_uploader(
    "Upload selectable PDF, DOCX, or TXT",
    type=["pdf", "docx", "txt"],
)

if uploaded_file:
    st.subheader("1. Extract Full Document Text")

    if st.button("Extract Full Text"):
        try:
            status = st.empty()

            status.info("Reading document...")
            pages = extract_document_pages(uploaded_file)

            status.info("Building full extracted text...")
            full_text = join_pages(pages)

            text_for_bedrock = full_text

            if len(text_for_bedrock) > int(max_doc_chars):
                text_for_bedrock = text_for_bedrock[: int(max_doc_chars)]
                status.warning(
                    f"Full text has {len(full_text)} characters. "
                    f"Sending first {int(max_doc_chars)} characters based on current setting."
                )
            else:
                status.success(
                    f"Full text extracted. Sending all {len(full_text)} characters to Bedrock."
                )

            st.session_state["pages"] = pages
            st.session_state["full_text"] = full_text
            st.session_state["text_for_bedrock"] = text_for_bedrock

        except Exception as e:
            st.error(f"Extraction failed: {e}")

if "full_text" in st.session_state:
    st.divider()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Full Extracted Text")
        st.write(f"Characters: **{len(st.session_state['full_text'])}**")

        with st.expander("View full extracted text", expanded=False):
            st.text_area(
                "Full extracted text",
                value=st.session_state["full_text"],
                height=350,
            )

        st.download_button(
            "Download full extracted text",
            data=st.session_state["full_text"],
            file_name="full_extracted_text.txt",
            mime="text/plain",
        )

    with col2:
        text_for_bedrock = st.session_state.get(
            "text_for_bedrock",
            st.session_state.get("text_for_llm", ""),
        )

        st.subheader("Text Sent to Bedrock")
        st.write(f"Characters sent: **{len(text_for_bedrock)}**")

        with st.expander("View text sent to Bedrock", expanded=True):
            st.text_area(
                "Text sent to Bedrock",
                value=text_for_bedrock,
                height=350,
            )

        st.download_button(
            "Download text sent to Bedrock",
            data=text_for_bedrock,
            file_name="text_sent_to_bedrock.txt",
            mime="text/plain",
        )

    st.divider()
    st.subheader("2. Run Amazon Bedrock Extraction")

    if st.button("Extract Required Fields"):
        if not bedrock_region:
            st.error("Please enter the AWS region.")
        elif not bedrock_model:
            st.error("Please enter the Bedrock model ID.")
        elif not bedrock_api_key:
            st.error(
                "Bedrock API key is missing. Enter it in the sidebar or set OPENAI_API_KEY."
            )
        elif not text_for_bedrock.strip():
            st.error("No document text available.")
        else:
            try:
                status = st.empty()

                status.info(f"Connecting to Amazon Bedrock: {bedrock_model}...")
                client = create_bedrock_client(
                    api_key=bedrock_api_key,
                    base_url=bedrock_base_url,
                )

                status.info("Sending extracted document text to Amazon Bedrock...")
                final_result, final_fields, raw_cleaned, elapsed = run_reasoning(
                    client=client,
                    model_id=bedrock_model,
                    full_document_text=text_for_bedrock,
                    validation_source_text=st.session_state["full_text"],
                    max_tokens=int(max_tokens),
                    temperature=float(temperature),
                )

                result_df = fields_to_table_df(final_fields)
                result_json = json.dumps(final_fields, indent=2, ensure_ascii=False)

                st.session_state["result_text"] = final_result
                st.session_state["result_fields"] = final_fields
                st.session_state["result_df"] = result_df
                st.session_state["result_json"] = result_json
                st.session_state["raw_cleaned"] = raw_cleaned
                st.session_state["elapsed"] = elapsed
                st.session_state["bedrock_model_used"] = bedrock_model

                status.success(f"Bedrock extraction complete in {elapsed} seconds.")

            except Exception as e:
                st.error(f"Amazon Bedrock request failed: {e}")

if "result_df" in st.session_state:
    st.divider()
    st.subheader("Required Fields Result")

    if "elapsed" in st.session_state:
        model_used = st.session_state.get("bedrock_model_used", bedrock_model)
        st.info(
            f"Bedrock model: {model_used} | "
            f"request/reasoning time: {st.session_state['elapsed']} seconds"
        )

    result_df = st.session_state["result_df"]
    result_text = st.session_state["result_text"]
    result_json = st.session_state.get(
        "result_json",
        json.dumps(st.session_state.get("result_fields", {}), indent=2),
    )

    st.dataframe(
        result_df,
        hide_index=True,
        use_container_width=True,
    )

    csv_text = table_df_to_csv_text(result_df)

    col_csv, col_json, col_txt = st.columns(3)

    with col_csv:
        st.download_button(
            "Download CSV",
            data=csv_text,
            file_name="ai_fcm_required_fields_table.csv",
            mime="text/csv",
        )

    with col_json:
        st.download_button(
            "Download JSON",
            data=result_json,
            file_name="ai_fcm_required_fields.json",
            mime="application/json",
        )

    with col_txt:
        st.download_button(
            "Download TXT",
            data=result_text,
            file_name="ai_fcm_required_fields.txt",
            mime="text/plain",
        )

    with st.expander("JSON output for RPA", expanded=True):
        st.code(result_json, language="json")

    with st.expander("Plain text output", expanded=False):
        st.text_area(
            "Final output",
            value=result_text,
            height=350,
        )

    with st.expander("Raw cleaned Bedrock output", expanded=False):
        st.text_area(
            "Raw cleaned output",
            value=st.session_state.get("raw_cleaned", ""),
            height=250,
        )
