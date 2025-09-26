import streamlit as st
import requests
import os
import pandas as pd
import plotly.express as px

# --- Configuration ---
API_URL = os.getenv("API_URL", "http://backend:8000")
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "a-secure-static-token")

# --- API Client ---
def run_analysis(uploaded_file, api_key: str):
    """
    Sends the uploaded file and API key to the backend for analysis.
    """
    if not uploaded_file:
        return None, "No file uploaded."

    headers = {"Authorization": f"Bearer {API_BEARER_TOKEN}"}
    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    data = {'api_key': api_key}

    try:
        st.info(f"Sending request to {API_URL}/analyze...")
        response = requests.post(f"{API_URL}/analyze", headers=headers, files=files, data=data, timeout=900) # 15 min timeout
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        st.error("The request timed out. The analysis is taking too long.")
        return None, "Request timed out."
    except requests.exceptions.RequestException as e:
        error_message = f"An error occurred: {e}"
        try:
            # Try to parse the error from the backend's JSON response
            error_details = e.response.json().get('error')
            if error_details:
                error_message = f"Analysis failed: {error_details}"
        except (ValueError, AttributeError):
            pass # Stick with the original error message
        st.error(error_message)
        return None, error_message

# --- UI Components ---
def display_results(results):
    """Renders the analysis results in the Streamlit UI."""
    st.subheader("📊 Analysis Results")

    if not results or 'clusters' not in results:
        st.warning("No clusters were found in the results.")
        st.json(results) # Show raw results for debugging
        return

    # Create a DataFrame for easier manipulation
    all_videos = []
    for i, cluster in enumerate(results['clusters']):
        for video in cluster['videos']:
            video_data = {
                'cluster_id': i,
                'cluster_label': cluster.get('label', f'Topic {i+1}'),
                'cluster_score': cluster.get('score', 0),
                'video_title': video.get('title', 'N/A'),
                'video_id': video.get('video_id', 'N/A'),
                'view_count': int(video.get('view_count', 0)),
                'like_count': int(video.get('like_count', 0)),
                'comment_count': int(video.get('comment_count', 0)),
                'channel_title': video.get('channel_title', 'N/A'),
                'published_at': video.get('published_at', 'N/A'),
            }
            all_videos.append(video_data)

    if not all_videos:
        st.warning("No video data could be processed from the results.")
        return

    df = pd.DataFrame(all_videos)
    df['published_at'] = pd.to_datetime(df['published_at'])

    # --- Summary Metrics ---
    st.subheader("📈 Overall Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Videos Analyzed", f"{len(df)}")
    col2.metric("Total Topics Found", f"{df['cluster_id'].nunique()}")
    col3.metric("Average Views", f"{int(df['view_count'].mean()):,}")
    col4.metric("Average Likes", f"{int(df['like_count'].mean()):,}")


    # --- Cluster Bubble Chart ---
    st.subheader("🫧 Topic Clusters Overview")
    cluster_summary = df.groupby('cluster_label').agg(
        video_count=('video_id', 'count'),
        total_views=('view_count', 'sum'),
        avg_score=('cluster_score', 'mean')
    ).reset_index()

    fig = px.scatter(
        cluster_summary,
        x='video_count',
        y='total_views',
        size='total_views',
        color='cluster_label',
        hover_name='cluster_label',
        hover_data={'video_count': True, 'total_views': True, 'avg_score': ':.2f'},
        title="Topic Clusters by Video Count and Total Views",
        labels={'video_count': 'Number of Videos in Topic', 'total_views': 'Total Views for Topic'}
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


    # --- Detailed Cluster Accordion ---
    st.subheader("📄 Detailed Topic Breakdown")
    for label in df['cluster_label'].unique():
        with st.expander(f"**{label}** (Score: {df[df['cluster_label'] == label]['cluster_score'].iloc[0]:.2f})"):
            cluster_df = df[df['cluster_label'] == label].sort_values('view_count', ascending=False)
            st.dataframe(cluster_df[[
                'video_title', 'view_count', 'like_count', 'channel_title'
            ]])


# --- Main App UI ---
st.set_page_config(page_title="YouTube Topic Audit Engine", layout="wide")
st.title("🎬 YouTube Topic Audit Engine")

st.info(
    "Upload your YouTube `watch-history.json` or Takeout `.zip` file to analyze your viewing patterns."
)

# --- State Management ---
if 'results' not in st.session_state:
    st.session_state.results = None

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("⚙️ Inputs")

    # Use st.secrets for the API key if available, otherwise use text_input
    try:
        google_api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("Using Google API Key from secrets.")
    except (FileNotFoundError, KeyError):
        google_api_key = st.text_input("Enter your Google API Key:", type="password")

    uploaded_file = st.file_uploader(
        "Upload your `watch-history.json` or `.zip` file",
        type=['json', 'zip']
    )

    analyze_button = st.button("🚀 Analyze Watch History", type="primary", disabled=(not uploaded_file or not google_api_key))

# --- Main Content Area ---
if analyze_button:
    st.session_state.results = None # Reset previous results
    with st.spinner("Hold tight! Analyzing your watch history... This can take several minutes."):
        results, error = run_analysis(uploaded_file, google_api_key)
        if error:
            st.error(f"Analysis failed: {error}")
        else:
            st.session_state.results = results
            st.balloons()

if st.session_state.results:
    display_results(st.session_state.results)
else:
    st.info("Upload a file and click 'Analyze' to see your results.")