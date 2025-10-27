import streamlit as st
import requests
import os
import time
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Configuration ---
API_URL = os.getenv("API_URL", "http://backend:8000")
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "dev-token-12345678")

# --- API Client Functions ---

def submit_analysis_job(uploaded_file, api_key: str, num_clusters: int = 10):
    """
    Submit analysis job to backend (async).

    Returns:
        tuple: (job_info, error_message)
        job_info contains: task_id, analysis_id, status_url, etc.
    """
    if not uploaded_file:
        return None, "No file uploaded."

    headers = {"Authorization": f"Bearer {API_BEARER_TOKEN}"}
    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    data = {
        'api_key': api_key,
        'num_clusters': num_clusters
    }

    try:
        response = requests.post(
            f"{API_URL}/analyze",
            headers=headers,
            files=files,
            data=data,
            timeout=30  # Short timeout - just for job submission
        )
        response.raise_for_status()

        if response.status_code == 202:
            return response.json(), None
        else:
            return None, f"Unexpected status code: {response.status_code}"

    except requests.exceptions.Timeout:
        return None, "Request timed out while submitting job."
    except requests.exceptions.RequestException as e:
        error_message = f"An error occurred: {e}"
        try:
            error_details = e.response.json().get('error', {})
            if isinstance(error_details, dict):
                error_message = error_details.get('message', str(error_details))
            else:
                error_message = str(error_details)
        except (ValueError, AttributeError):
            pass
        return None, error_message


def poll_job_status(task_id: str):
    """
    Poll job status.

    Returns:
        tuple: (status_info, error_message)
    """
    try:
        response = requests.get(
            f"{API_URL}/jobs/{task_id}",
            timeout=10
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Failed to get job status: {e}"


def get_job_results(task_id: str, include_videos: bool = False):
    """
    Get complete job results.

    Returns:
        tuple: (results, error_message)
    """
    try:
        params = {'include_videos': 'true'} if include_videos else {}
        response = requests.get(
            f"{API_URL}/jobs/{task_id}/results",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        error_message = f"Failed to get results: {e}"
        try:
            error_details = e.response.json()
            error_message = error_details.get('message', error_message)
        except (ValueError, AttributeError):
            pass
        return None, error_message


def cancel_job(task_id: str):
    """
    Cancel a running job.

    Returns:
        tuple: (success, error_message)
    """
    try:
        response = requests.delete(
            f"{API_URL}/jobs/{task_id}",
            timeout=10
        )
        response.raise_for_status()
        return True, None
    except requests.exceptions.RequestException as e:
        return False, f"Failed to cancel job: {e}"


# --- UI Components ---

def display_progress(status_info):
    """Display job progress with visual progress bar."""
    state = status_info.get('state', 'UNKNOWN')
    progress = status_info.get('progress', 0)
    message = status_info.get('message', 'Processing...')

    # Progress bar
    progress_bar = st.progress(progress / 100.0)

    # Status message
    st.write(f"**Status:** {message}")

    # Statistics if available
    if 'statistics' in status_info:
        stats = status_info['statistics']
        cols = st.columns(4)
        cols[0].metric("Total Videos", f"{stats.get('total_videos', 0):,}")
        cols[1].metric("Processed", f"{stats.get('processed_videos', 0):,}")
        cols[2].metric("Channels", f"{stats.get('unique_channels', 0):,}")
        cols[3].metric("Clusters", f"{stats.get('num_clusters', 0)}")

    return progress


def display_results(results):
    """Renders the analysis results in the Streamlit UI."""
    st.subheader("📊 Analysis Results")

    # Summary section
    if 'summary' in results:
        summary = results['summary']
        st.subheader("📈 Overall Summary")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Videos", f"{summary.get('total_videos', 0):,}")
        col2.metric("Unique Channels", f"{summary.get('unique_channels', 0):,}")
        col3.metric("Topics Found", f"{summary.get('num_clusters', 0)}")
        col4.metric("Watch Time", f"{summary.get('total_watch_time_hours', 0):.1f}h")

        # Date range
        date_range = summary.get('date_range', {})
        if date_range.get('start') and date_range.get('end'):
            st.info(f"📅 Analysis Period: {date_range['start'][:10]} to {date_range['end'][:10]}")

    # Top Channels
    if 'top_channels' in results and results['top_channels']:
        st.subheader("🎥 Top Channels")

        channels_df = pd.DataFrame(results['top_channels'])

        # Bar chart
        fig = px.bar(
            channels_df.head(10),
            x='video_count',
            y='channel_name',
            orientation='h',
            title="Top 10 Channels by Video Count",
            labels={'video_count': 'Videos Watched', 'channel_name': 'Channel'}
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

    # Clusters
    if 'clusters' in results and results['clusters']:
        st.subheader("🎯 Content Clusters")

        clusters = results['clusters']

        # Cluster summary table
        cluster_data = []
        for cluster in clusters:
            cluster_data.append({
                'Topic': cluster.get('label', f"Cluster {cluster.get('cluster_number')}"),
                'Size': cluster.get('size', 0),
                'Avg Watch Time (h)': f"{cluster.get('avg_watch_time_hours', 0):.1f}",
                'Keywords': ', '.join(cluster.get('top_keywords', [])[:5])
            })

        clusters_df = pd.DataFrame(cluster_data)
        st.dataframe(clusters_df, use_container_width=True)

        # Cluster size visualization
        fig = px.pie(
            clusters_df,
            values='Size',
            names='Topic',
            title="Content Distribution by Topic"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Detailed cluster breakdown
        st.subheader("📄 Detailed Topic Breakdown")
        for cluster in clusters:
            label = cluster.get('label', f"Cluster {cluster.get('cluster_number')}")
            size = cluster.get('size', 0)
            keywords = cluster.get('top_keywords', [])

            with st.expander(f"**{label}** ({size} videos)"):
                if keywords:
                    st.write("**Keywords:**", ", ".join(keywords[:10]))

                if cluster.get('description'):
                    st.write("**Description:**", cluster['description'])

                # Top channels in this cluster
                if cluster.get('top_channels'):
                    st.write("**Top Channels:**")
                    for ch in cluster['top_channels'][:5]:
                        if isinstance(ch, dict):
                            st.write(f"- {ch.get('channel_name', 'Unknown')}: {ch.get('video_count', 0)} videos")

    # Raw data expander (for debugging)
    with st.expander("🔍 View Raw Data"):
        st.json(results)


def run_analysis_with_polling(uploaded_file, api_key: str, num_clusters: int = 10):
    """
    Submit analysis job and poll until complete.

    Displays progress in real-time using Streamlit components.
    """
    # Step 1: Submit job
    with st.spinner("Submitting analysis job..."):
        job_info, error = submit_analysis_job(uploaded_file, api_key, num_clusters)

        if error:
            st.error(f"Failed to submit job: {error}")
            return None

        task_id = job_info['task_id']
        analysis_id = job_info.get('analysis_id')

        st.success(f"✅ Job submitted successfully!")
        st.info(f"Task ID: `{task_id}`")

        # Store in session state
        st.session_state.task_id = task_id
        st.session_state.analysis_id = analysis_id

    # Step 2: Poll for progress
    st.subheader("⏳ Processing Analysis")

    progress_container = st.container()
    status_placeholder = st.empty()
    cancel_button_placeholder = st.empty()

    poll_interval = 2  # seconds
    max_polls = 900  # 30 minutes max (900 * 2 seconds)
    poll_count = 0

    while poll_count < max_polls:
        # Check if user wants to cancel
        if cancel_button_placeholder.button("❌ Cancel Job", key=f"cancel_{poll_count}"):
            with st.spinner("Cancelling job..."):
                success, error = cancel_job(task_id)
                if success:
                    st.warning("Job cancelled successfully.")
                    return None
                else:
                    st.error(f"Failed to cancel: {error}")

        # Poll status
        status_info, error = poll_job_status(task_id)

        if error:
            st.error(f"Failed to get job status: {error}")
            time.sleep(poll_interval)
            poll_count += 1
            continue

        state = status_info.get('state', 'UNKNOWN')

        with status_placeholder.container():
            current_progress = display_progress(status_info)

        # Check if complete
        if state == 'SUCCESS':
            cancel_button_placeholder.empty()  # Remove cancel button
            st.success("✅ Analysis complete!")

            # Step 3: Fetch results
            with st.spinner("Fetching results..."):
                results, error = get_job_results(task_id, include_videos=False)

                if error:
                    st.error(f"Failed to get results: {error}")
                    return None

                return results

        elif state == 'FAILURE':
            cancel_button_placeholder.empty()
            error_msg = status_info.get('error', 'Unknown error')
            st.error(f"❌ Analysis failed: {error_msg}")
            return None

        elif state == 'REVOKED':
            cancel_button_placeholder.empty()
            st.warning("⚠️ Job was cancelled.")
            return None

        # Wait before next poll
        time.sleep(poll_interval)
        poll_count += 1

    # Timeout
    cancel_button_placeholder.empty()
    st.error("⏱️ Analysis timed out after 30 minutes.")
    return None


# --- Main App UI ---
st.set_page_config(page_title="YouTube Topic Audit Engine", layout="wide")

# Header
st.title("🎬 YouTube Topic Audit Engine")
st.markdown("---")

st.info(
    "Upload your YouTube `watch-history.json` or Takeout `.zip` file to analyze your viewing patterns. "
    "The analysis runs in the background with real-time progress tracking."
)

# --- State Management ---
if 'results' not in st.session_state:
    st.session_state.results = None
if 'task_id' not in st.session_state:
    st.session_state.task_id = None
if 'analysis_id' not in st.session_state:
    st.session_state.analysis_id = None

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("⚙️ Configuration")

    # API Key
    try:
        google_api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Using Google API Key from secrets.")
    except (FileNotFoundError, KeyError):
        google_api_key = st.text_input(
            "Google API Key:",
            type="password",
            help="Enter your YouTube Data API v3 key"
        )

    # File upload
    uploaded_file = st.file_uploader(
        "Upload watch-history.json or .zip",
        type=['json', 'zip'],
        help="Get this file from Google Takeout"
    )

    # Advanced options
    with st.expander("🔧 Advanced Options"):
        num_clusters = st.slider(
            "Number of clusters",
            min_value=5,
            max_value=20,
            value=10,
            help="More clusters = more granular topic segmentation"
        )

    # Analyze button
    analyze_button = st.button(
        "🚀 Analyze Watch History",
        type="primary",
        disabled=(not uploaded_file or not google_api_key),
        use_container_width=True
    )

    # Info
    st.markdown("---")
    st.caption("💡 Tip: Analysis runs in the background. You can monitor progress in real-time!")

# --- Main Content Area ---
if analyze_button:
    # Reset previous results
    st.session_state.results = None
    st.session_state.task_id = None
    st.session_state.analysis_id = None

    # Run analysis with polling
    results = run_analysis_with_polling(uploaded_file, google_api_key, num_clusters)

    if results:
        st.session_state.results = results
        st.balloons()

# Display results if available
if st.session_state.results:
    display_results(st.session_state.results)

    # Download button
    st.download_button(
        label="📥 Download Results (JSON)",
        data=str(st.session_state.results),
        file_name=f"youtube_audit_results_{st.session_state.analysis_id}.json",
        mime="application/json"
    )
else:
    # Welcome message
    st.markdown("""
    ### 👋 Welcome!

    **Getting Started:**
    1. Get your YouTube watch history from [Google Takeout](https://takeout.google.com)
    2. Get a YouTube Data API key from [Google Cloud Console](https://console.cloud.google.com)
    3. Upload your file and click "Analyze"

    **What you'll discover:**
    - 📊 Your viewing patterns and habits
    - 🎯 Content clusters (topics you watch most)
    - 🎥 Top channels you follow
    - ⏰ Watch time statistics
    """)

# Footer
st.markdown("---")
st.caption("🤖 Powered by YouTube Audit Engine | Built with Streamlit & Flask")
