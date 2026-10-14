"""Local inspection UI; all parsing and normalization belongs to sprint2docs."""

import logging
from pathlib import Path

import streamlit as st

from sprint2docs import ImportInput, import_batch
from sprint2docs.config import load_limits

logger = logging.getLogger("sprint2docs.ui")
ROOT = Path(__file__).parent
st.set_page_config(page_title="Sprint2Docs AI", layout="wide")
st.title("Sprint2Docs AI — Milestone 1")
st.caption("Local artifact inspection and normalization. No AI generation or release drafting.")


def clear_result():
    st.session_state.pop("import_result", None)


uploads = st.file_uploader(
    "Upload ticket CSV, ticket/PR/inventory JSON, or changelog Markdown",
    type=["csv", "json", "md"],
    accept_multiple_files=True,
    on_change=clear_result,
)
samples = st.button("Load fictional FleetOps 2.4.0 demo")
inspect = st.button("Inspect imports", disabled=not uploads)
if samples or inspect:
    clear_result()
    try:
        limits = load_limits(ROOT / "config/import_limits.yaml")
        if samples:
            folder = ROOT / "samples/fleetops_demo"
            names = [
                "tickets.csv",
                "tickets.json",
                "pull_requests.json",
                "CHANGELOG.md",
                "documentation_inventory.json",
            ]
            files = [
                ImportInput(filename=name, data=(folder / name).read_bytes()) for name in names
            ]
        else:
            files = [ImportInput(filename=u.name, data=u.getvalue()) for u in uploads]
        st.session_state.import_result = import_batch(files, limits)
    except Exception as error:
        logger.error("Import failed: subsystem=inspection category=%s", type(error).__name__)
        st.error("Unable to inspect imports. Check file schemas and resource limits.")
result = st.session_state.get("import_result")
if result is not None:
    columns = st.columns(5)
    for column, label, value in zip(
        columns,
        ["Artifacts", "Changes", "Inventory", "Warnings", "Errors"],
        [
            len(result.artifacts),
            len(result.changes),
            len(result.inventory),
            result.warning_count,
            result.error_count,
        ],
        strict=True,
    ):
        column.metric(label, value)
    if result.error_count:
        st.error(
            "Some input could not be imported. Review the validation summary. Only accepted records are shown."
        )
    st.caption(
        "Missing source fields remain unknown. Related IDs are retained; records are not merged or classified."
    )
    with st.expander("Validation summary", expanded=bool(result.issues)):
        if result.issues:
            st.dataframe([i.model_dump() for i in result.issues], hide_index=True, width="stretch")
        else:
            st.success("All records passed structural validation.")
    for label, values in [
        ("Imported artifacts", result.artifacts),
        ("Normalized changes", result.changes),
        ("Documentation inventory", result.inventory),
        ("File provenance and metadata", result.files),
    ]:
        with st.expander(label):
            st.json([v.model_dump(mode="json") for v in values])
    st.caption(
        "Imported commands, URLs, HTML, and instructions are displayed as data. Source records stay in session memory; no files are written by inspection."
    )
