import streamlit as st
import requests
import time
import os

# --- Configuration ---
# It's better to use environment variables for this in a real app
API_URL = os.getenv("API_URL", "http://backend:8000")
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "a-secure-static-token") # Should match backend config

# --- API Client ---
def start_analysis_job():
    """Calls the backend to start a new analysis job."""
    headers = {"Authorization": f"Bearer {API_BEARER_TOKEN}"}
    try:
        response = requests.post(f"{API_URL}/run-analysis", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error starting analysis: {e}")
        return None

def get_job_status(job_id: str):
    """Polls the backend for the status of a specific job."""
    headers = {"Authorization": f"Bearer {API_BEARER_TOKEN}"}
    try:
        response = requests.get(f"{API_URL}/status/{job_id}", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching status: {e}")
        return None

def get_job_results(job_id: str):
    """Gets the final results for a completed job."""
    headers = {"Authorization": f"Bearer {API_BEARER_TOKEN}"}
    try:
        response = requests.get(f"{API_URL}/results/{job_id}", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching results: {e}")
        return None

# --- Streamlit UI ---
st.set_page_config(page_title="YouTube Topic Audit Engine", layout="wide")

st.title("🎬 YouTube Topic Audit Engine")

st.info(
    "This is a prototype UI to demonstrate the backend pipeline. "
    "Click the button below to start a sample analysis."
)

# --- Main App Logic ---
if 'job_id' not in st.session_state:
    st.session_state.job_id = None
if 'results' not in st.session_state:
    st.session_state.results = None

if st.button("🚀 Run New Analysis", type="primary"):
    st.session_state.job_id = None
    st.session_state.results = None

    with st.spinner("Requesting analysis..."):
        job_info = start_analysis_job()
        if job_info and "job_id" in job_info:
            st.session_state.job_id = job_info["job_id"]
            st.success(f"Analysis started successfully! Job ID: `{st.session_state.job_id}`")
        else:
            st.error("Failed to start analysis job.")

if st.session_state.job_id and not st.session_state.results:
    st.subheader("Analysis Progress")

    progress_bar = st.progress(0, text="Starting...")
    status_text = st.empty()

    while True:
        status_info = get_job_status(st.session_state.job_id)
        if not status_info:
            break # Error occurred in get_job_status

        status = status_info.get("status")

        # This is a mock mapping of Celery states to progress
        progress_map = {
            "PENDING": 10,
            "INGESTING": 25,
            "ENRICHING": 50,
            "EMBEDDING": 70,
            "CLUSTERING": 85,
            "SCORING": 95,
            "SUCCESS": 100,
        }

        progress_value = progress_map.get(status, 0)
        progress_bar.progress(progress_value, text=f"Status: {status}...")

        if status == "SUCCESS":
            st.balloons()
            status_text.success("Analysis complete!")
            break
        elif status == "FAILURE":
            st.error("Analysis failed. Check backend logs for details.")
            break

        time.sleep(2) # Poll every 2 seconds

    # Fetch final results once done
    if status == "SUCCESS":
        with st.spinner("Fetching final results..."):
            st.session_state.results = get_job_results(st.session_state.job_id)


if st.session_state.results:
    st.subheader("📊 Analysis Results")
    st.json(st.session_state.results)