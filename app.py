import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import re
from googleapiclient.discovery import build
import io
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

# --- Helper Functions ---

def parse_watch_history(file_content):
    """Parses the watch history HTML file to extract video URLs."""
    soup = BeautifulSoup(file_content, "lxml")
    links = []
    for link in soup.find_all('a', href=re.compile(r"watch\?v=")):
        href = link.get('href')
        if href:
            links.append(href)
    return list(set(links))

def extract_video_id(url):
    """Extracts the YouTube video ID from a URL."""
    match = re.search(r"v=([^&]+)", url)
    return match.group(1) if match else None

def get_video_details(_youtube_api, video_ids):
    """Fetches video details from the YouTube API in batches."""
    video_details = []
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        request = _youtube_api.videos().list(
            part="snippet,statistics,topicDetails",
            id=",".join(batch_ids)
        )
        response = request.execute()
        video_details.extend(response.get("items", []))
    return video_details

def load_embedding_model():
    """Loads the sentence transformer model."""
    with st.spinner("Downloading AI model... This may take a moment."):
        model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

def generate_embeddings(_model, texts):
    """Generates embeddings for a list of texts."""
    return _model.encode(texts, show_progress_bar=True)

def cluster_videos(embeddings, num_clusters=20):
    """Clusters videos using KMeans."""
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
    kmeans.fit(embeddings)
    return kmeans.labels_

def get_topic_representation(df, cluster_id):
    """Generates a topic label for a cluster using TF-IDF."""
    cluster_texts = df[df['cluster'] == cluster_id]['text_features'].tolist()
    if not cluster_texts:
        return "N/A"

    vectorizer = TfidfVectorizer(stop_words='english', max_features=5)
    try:
        vectorizer.fit(cluster_texts)
        return ", ".join(vectorizer.get_feature_names_out())
    except ValueError:
        return ", ".join(re.findall(r'\b\w+\b', " ".join(cluster_texts))[:5])


# --- UI Setup ---
st.set_page_config(page_title="YouTube Topic Audit Engine", layout="wide")
st.title("🎬 YouTube Topic Audit Engine")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your YouTube Data API v3 Key", type="password", help="Your API key is used to fetch up-to-date video details.")

    st.header("📂 Upload Your Data")
    uploaded_watch_history = st.file_uploader("Upload your `watch-history.html`", type="html")
    uploaded_subscriptions = st.file_uploader("Upload your `subscriptions.csv` (optional)", type="csv")

    st.header("📊 Analysis Parameters")
    num_clusters = st.slider("Number of Topic Clusters", min_value=5, max_value=50, value=20, step=1)


# --- Analysis Trigger ---
if st.button("🚀 Analyze My YouTube Data", type="primary", use_container_width=True):
    if not api_key:
        st.error("Please enter your YouTube API key to proceed.")
    elif not uploaded_watch_history:
        st.error("Please upload your watch-history.html file.")
    else:
        progress_bar = st.progress(0, text="Starting analysis...")
        try:
            # 1. Initialize YouTube API client
            youtube_api = build("youtube", "v3", developerKey=api_key)
            progress_bar.progress(5, text="1️⃣ Parsing watch history...")

            # 2. Parse Watch History
            watch_history_content = uploaded_watch_history.getvalue().decode("utf-8")
            video_urls = parse_watch_history(watch_history_content)
            video_ids = [extract_video_id(url) for url in video_urls if extract_video_id(url)]

            if not video_ids:
                st.error("Could not find any valid YouTube video links in the watch history file.")
                st.stop()

            st.success(f"Found {len(video_ids)} unique videos in your watch history.")
            progress_bar.progress(15, text="2️⃣ Fetching video details from API...")

            # 3. Fetch Video Details from API
            video_details = get_video_details(youtube_api, video_ids)

            if not video_details:
                st.error("Could not fetch video details. Check your API key and permissions.")
                st.stop()

            df = pd.DataFrame([{
                'id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'channelTitle': item['snippet']['channelTitle'],
                'tags': ", ".join(item['snippet'].get('tags', [])),
            } for item in video_details])

            df['video_url'] = "https://www.youtube.com/watch?v=" + df['id']
            st.success(f"Successfully fetched details for {len(df)} videos.")

            # 4. Load Model and Generate Embeddings
            progress_bar.progress(30, text="3️⃣ Loading AI model...")
            embedding_model = load_embedding_model()

            progress_bar.progress(40, text="4️⃣ Generating text embeddings...")
            df['text_features'] = df['title'] + " " + df['description'] + " " + df['tags']
            embeddings = generate_embeddings(embedding_model, df['text_features'].tolist())

            # 5. Cluster Videos
            progress_bar.progress(70, text="5️⃣ Clustering videos into topics...")
            actual_num_clusters = min(num_clusters, len(df) // 5)
            if actual_num_clusters < 2:
                st.error("Not enough videos to perform clustering.")
                st.stop()
            df['cluster'] = cluster_videos(embeddings, num_clusters=actual_num_clusters)

            # 6. Generate Topic Labels
            progress_bar.progress(90, text="6️⃣ Generating topic labels...")
            topic_labels = [get_topic_representation(df, i) for i in range(actual_num_clusters)]
            df['topic'] = df['cluster'].apply(lambda x: topic_labels[x])

            st.session_state.analysis_results = df
            st.session_state.analysis_complete = True
            progress_bar.progress(100, text="Analysis complete!")
            st.balloons()

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.stop()

# --- Visualization ---
if st.session_state.get('analysis_complete'):
    st.header("📊 Analysis Results")
    results_df = st.session_state.analysis_results

    st.subheader("Your Top Topic Clusters")
    cluster_summary = results_df['topic'].value_counts().reset_index()
    cluster_summary.columns = ['Topic', 'Video Count']

    st.bar_chart(cluster_summary.set_index('Topic'), use_container_width=True)

    st.subheader("Explore Your Topics")
    topic_details = []
    for topic in cluster_summary['Topic']:
        topic_df = results_df[results_df['topic'] == topic]
        sample_titles = " / ".join(topic_df['title'].head(3).tolist())
        topic_details.append({
            "Topic": topic,
            "Video Count": len(topic_df),
            "Sample Videos": sample_titles,
            "Channels": ", ".join(topic_df['channelTitle'].unique()[:3])
        })
    st.dataframe(pd.DataFrame(topic_details), use_container_width=True)

    st.subheader("Video Explorer")
    selected_topic = st.selectbox("Select a topic to see its videos", options=cluster_summary['Topic'])

    if selected_topic:
        videos_in_topic_df = results_df[results_df['topic'] == selected_topic][['title', 'channelTitle', 'video_url']]
        st.dataframe(
            videos_in_topic_df,
            column_config={"video_url": st.column_config.LinkColumn("Watch on YouTube")},
            use_container_width=True,
            hide_index=True
        )