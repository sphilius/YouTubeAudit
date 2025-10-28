"""
YouTube Watch History Analyzer - Simple Single-File Version

Upload your YouTube watch history JSON and get AI-powered insights about
your viewing patterns, content themes, and recommendations.

No backend, no database, no complex setup - just upload and analyze!
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import Counter
import time

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np

# Configure page
st.set_page_config(
    page_title="YouTube Watch History Analyzer",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
MAX_VIDEOS_TO_ANALYZE = 500  # Limit for performance
MIN_CLUSTER_SIZE = 5  # Minimum videos for clustering


def load_watch_history(uploaded_file) -> List[Dict[str, Any]]:
    """Load and parse YouTube watch history (JSON) or playlist (CSV) file."""
    filename = uploaded_file.name.lower()

    try:
        # Handle CSV files (playlists from Google Takeout)
        if filename.endswith('.csv'):
            import csv
            import io

            content = uploaded_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))

            videos = []
            for row in csv_reader:
                # CSV format has different column names
                video_url = row.get('Video URL', row.get('URL', ''))
                video_id = ''

                # Extract video ID from URL
                if 'youtube.com/watch?v=' in video_url:
                    video_id = video_url.split('watch?v=')[1].split('&')[0]
                elif 'youtu.be/' in video_url:
                    video_id = video_url.split('youtu.be/')[1].split('?')[0]

                if video_id:
                    videos.append({
                        'video_id': video_id,
                        'title': row.get('Video Title', row.get('Title', 'Unknown')),
                        'time': row.get('Time Added', row.get('Date', '')),
                        'channel': row.get('Channel Name', row.get('Channel', 'Unknown'))
                    })

            return videos

        # Handle JSON files (watch history from Google Takeout)
        else:
            content = uploaded_file.read()
            data = json.loads(content)

            videos = []
            for item in data:
                # YouTube takeout format
                if 'titleUrl' in item:
                    video_id = item.get('titleUrl', '').split('?v=')[-1]
                    videos.append({
                        'video_id': video_id,
                        'title': item.get('title', 'Unknown'),
                        'time': item.get('time', ''),
                        'channel': item.get('subtitles', [{}])[0].get('name', 'Unknown') if item.get('subtitles') else 'Unknown'
                    })

            return videos

    except Exception as e:
        st.error(f"Error loading file: {e}")
        return []


def fetch_youtube_metadata(video_ids: List[str], api_key: str, progress_bar=None) -> Dict[str, Dict]:
    """Fetch metadata for videos from YouTube API."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
    except Exception as e:
        st.error(f"Failed to initialize YouTube API: {e}")
        return {}

    metadata = {}
    batch_size = 50  # YouTube API allows max 50 IDs per request

    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i:i + batch_size]

        try:
            response = youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(batch)
            ).execute()

            for item in response.get('items', []):
                video_id = item['id']
                snippet = item.get('snippet', {})
                stats = item.get('statistics', {})

                metadata[video_id] = {
                    'title': snippet.get('title', 'Unknown'),
                    'description': snippet.get('description', ''),
                    'channel_title': snippet.get('channelTitle', 'Unknown'),
                    'channel_id': snippet.get('channelId', ''),
                    'tags': snippet.get('tags', []),
                    'category_id': snippet.get('categoryId', '0'),
                    'view_count': int(stats.get('viewCount', 0)),
                    'like_count': int(stats.get('likeCount', 0)),
                }

            if progress_bar:
                progress_bar.progress(min(1.0, (i + batch_size) / len(video_ids)))

            time.sleep(0.1)  # Rate limiting

        except HttpError as e:
            if e.resp.status == 403:
                st.error("⚠️ YouTube API quota exceeded or invalid API key!")
                break
            else:
                st.warning(f"API error for batch {i//batch_size + 1}: {e}")
        except Exception as e:
            st.warning(f"Error fetching batch {i//batch_size + 1}: {e}")

    return metadata


def create_text_embeddings(texts: List[str]) -> np.ndarray:
    """Create embeddings using sentence-transformers (if available)."""
    try:
        from sentence_transformers import SentenceTransformer

        with st.spinner("Loading AI model for semantic analysis..."):
            model = SentenceTransformer('all-MiniLM-L6-v2')  # Small, fast model

        with st.spinner("Analyzing video content semantically..."):
            embeddings = model.encode(texts, show_progress_bar=False)

        return embeddings
    except ImportError:
        st.warning("⚠️ sentence-transformers not installed. Using basic keyword clustering instead.")
        return None
    except Exception as e:
        st.warning(f"⚠️ Could not use AI embeddings: {e}. Using basic clustering.")
        return None


def cluster_videos_simple(videos: List[Dict], n_clusters: int = 5) -> List[Dict]:
    """Simple clustering based on channel and basic features."""
    # Create feature vectors based on channel, category
    channel_mapping = {ch: idx for idx, ch in enumerate(set(v['channel_title'] for v in videos))}
    category_mapping = {cat: idx for idx, cat in enumerate(set(v.get('category_id', '0') for v in videos))}

    features = []
    for v in videos:
        features.append([
            channel_mapping[v['channel_title']],
            category_mapping.get(v.get('category_id', '0'), 0),
            np.log1p(v.get('view_count', 0)),
        ])

    features = np.array(features)
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # K-means clustering
    n_clusters = min(n_clusters, len(videos) // MIN_CLUSTER_SIZE)
    if n_clusters < 2:
        for v in videos:
            v['cluster'] = 0
        return videos

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(features_scaled)

    for v, cluster in zip(videos, clusters):
        v['cluster'] = int(cluster)

    return videos


def cluster_videos_semantic(videos: List[Dict], n_clusters: int = 5) -> List[Dict]:
    """Advanced clustering using semantic embeddings."""
    # Create text for embedding (title + description + tags)
    texts = []
    for v in videos:
        text_parts = [
            v['title'],
            v['channel_title'],
            v.get('description', '')[:200],  # First 200 chars
            ' '.join(v.get('tags', [])[:5])  # Top 5 tags
        ]
        texts.append(' '.join(text_parts))

    # Get embeddings
    embeddings = create_text_embeddings(texts)

    if embeddings is None:
        # Fall back to simple clustering
        return cluster_videos_simple(videos, n_clusters)

    # K-means on embeddings
    n_clusters = min(n_clusters, len(videos) // MIN_CLUSTER_SIZE)
    if n_clusters < 2:
        for v in videos:
            v['cluster'] = 0
        return videos

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(embeddings)

    for v, cluster in zip(videos, clusters):
        v['cluster'] = int(cluster)

    return videos


def analyze_clusters(videos: List[Dict]) -> List[Dict]:
    """Analyze clusters to extract insights."""
    clusters_info = []

    for cluster_id in sorted(set(v['cluster'] for v in videos)):
        cluster_videos = [v for v in videos if v['cluster'] == cluster_id]

        # Top channels
        channels = [v['channel_title'] for v in cluster_videos]
        top_channels = Counter(channels).most_common(5)

        # Top tags
        all_tags = []
        for v in cluster_videos:
            all_tags.extend(v.get('tags', []))
        top_tags = Counter(all_tags).most_common(10)

        # Average stats
        avg_views = np.mean([v.get('view_count', 0) for v in cluster_videos])

        # Generate label
        if top_channels:
            label = f"Cluster {cluster_id}: {top_channels[0][0]}"
        else:
            label = f"Cluster {cluster_id}"

        clusters_info.append({
            'cluster_id': cluster_id,
            'label': label,
            'size': len(cluster_videos),
            'top_channels': top_channels,
            'top_tags': top_tags,
            'avg_views': avg_views,
            'sample_videos': cluster_videos[:5]
        })

    return sorted(clusters_info, key=lambda x: x['size'], reverse=True)


def main():
    """Main Streamlit app."""
    st.title("📺 YouTube Watch History Analyzer")
    st.markdown("""
    Upload your YouTube watch history (JSON) or playlists (CSV) and get AI-powered insights about your viewing patterns,
    content themes, and recommendations for content creation.

    **Accepts:** `watch-history.json` or any playlist CSV from Google Takeout
    """)

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        api_key = st.text_input(
            "YouTube API Key",
            type="password",
            help="Get your API key from: https://console.cloud.google.com/apis/credentials"
        )

        st.markdown("---")

        n_clusters = st.slider(
            "Number of topic clusters",
            min_value=3,
            max_value=15,
            value=7,
            help="How many content themes to identify"
        )

        use_semantic = st.checkbox(
            "Use AI semantic analysis",
            value=True,
            help="More accurate but slower (requires sentence-transformers)"
        )

        st.markdown("---")
        st.markdown("""
        ### 📝 How to get your data:

        **Watch History (JSON):**
        1. Go to [Google Takeout](https://takeout.google.com/)
        2. Deselect all, select only **YouTube**
        3. Click "All YouTube data included"
        4. Select only **history**
        5. Download and extract
        6. Upload `watch-history.json`

        **Playlists (CSV):**
        1. Go to [Google Takeout](https://takeout.google.com/)
        2. Deselect all, select only **YouTube**
        3. Select **playlists**
        4. Download and extract
        5. Upload any CSV file from `playlists/` folder
        """)

    # File upload
    uploaded_file = st.file_uploader(
        "Upload watch-history.json or playlist CSV",
        type=['json', 'csv'],
        help="Your YouTube watch history (JSON) or playlist (CSV) from Google Takeout"
    )

    if not uploaded_file:
        st.info("👆 Upload your watch-history.json or playlist CSV file to get started!")
        return

    if not api_key:
        st.warning("⚠️ Please enter your YouTube API key in the sidebar to continue.")
        return

    # Load watch history
    with st.spinner("Loading watch history..."):
        videos = load_watch_history(uploaded_file)

    if not videos:
        st.error("No videos found in the uploaded file. Please check the format.")
        return

    st.success(f"✅ Loaded {len(videos)} videos from your watch history")

    # Limit videos for performance
    if len(videos) > MAX_VIDEOS_TO_ANALYZE:
        st.warning(f"⚠️ Analyzing the most recent {MAX_VIDEOS_TO_ANALYZE} videos for performance.")
        videos = videos[:MAX_VIDEOS_TO_ANALYZE]

    # Fetch metadata
    video_ids = [v['video_id'] for v in videos if v['video_id']]

    st.subheader("📡 Fetching video metadata from YouTube...")
    progress_bar = st.progress(0)

    metadata = fetch_youtube_metadata(video_ids, api_key, progress_bar)

    if not metadata:
        st.error("Failed to fetch metadata. Please check your API key and try again.")
        return

    # Enrich videos with metadata
    enriched_videos = []
    for v in videos:
        if v['video_id'] in metadata:
            enriched_videos.append({**v, **metadata[v['video_id']]})

    st.success(f"✅ Fetched metadata for {len(enriched_videos)} videos")

    # Cluster videos
    st.subheader("🤖 Analyzing content themes...")

    if use_semantic:
        clustered_videos = cluster_videos_semantic(enriched_videos, n_clusters)
    else:
        clustered_videos = cluster_videos_simple(enriched_videos, n_clusters)

    clusters_info = analyze_clusters(clustered_videos)

    # Display results
    st.header("📊 Analysis Results")

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Videos", len(clustered_videos))

    with col2:
        unique_channels = len(set(v['channel_title'] for v in clustered_videos))
        st.metric("Unique Channels", unique_channels)

    with col3:
        st.metric("Content Themes", len(clusters_info))

    with col4:
        total_views = sum(v.get('view_count', 0) for v in clustered_videos)
        st.metric("Total Views", f"{total_views:,}")

    # Cluster distribution
    st.subheader("📈 Content Theme Distribution")

    cluster_sizes = pd.DataFrame([
        {'Theme': c['label'], 'Videos': c['size']}
        for c in clusters_info
    ])

    fig = px.bar(
        cluster_sizes,
        x='Theme',
        y='Videos',
        title='Videos per Content Theme',
        color='Videos',
        color_continuous_scale='Viridis'
    )
    st.plotly_chart(fig, use_container_width=True)

    # Top channels
    st.subheader("📺 Top Channels You Watch")
    all_channels = [v['channel_title'] for v in clustered_videos]
    top_channels = Counter(all_channels).most_common(10)

    channels_df = pd.DataFrame(top_channels, columns=['Channel', 'Videos Watched'])
    fig2 = px.bar(
        channels_df,
        x='Videos Watched',
        y='Channel',
        orientation='h',
        title='Your Most Watched Channels',
        color='Videos Watched',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Detailed cluster analysis
    st.header("🎯 Content Theme Deep Dive")

    for cluster in clusters_info:
        with st.expander(f"**{cluster['label']}** ({cluster['size']} videos)", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**🔝 Top Channels:**")
                for ch, count in cluster['top_channels'][:5]:
                    st.markdown(f"- {ch} ({count} videos)")

            with col2:
                st.markdown("**🏷️ Top Tags:**")
                for tag, count in cluster['top_tags'][:5]:
                    st.markdown(f"- {tag} ({count}×)")

            st.markdown(f"**📊 Average Views:** {cluster['avg_views']:,.0f}")

            st.markdown("**🎬 Sample Videos:**")
            for vid in cluster['sample_videos'][:3]:
                st.markdown(f"- {vid['title']} ({vid['channel_title']})")

    # Recommendations
    st.header("💡 Content Creation Insights")

    st.markdown("""
    Based on your viewing patterns, here are insights for content creation:
    """)

    # Find your niche
    biggest_cluster = clusters_info[0]
    st.success(f"""
    **🎯 Your Primary Interest:** {biggest_cluster['label']}

    You've watched {biggest_cluster['size']} videos in this theme. This represents your strongest
    content knowledge area and potential audience overlap.
    """)

    # Diversification opportunity
    if len(clusters_info) > 3:
        smaller_clusters = clusters_info[-3:]
        st.info(f"""
        **🌟 Diversification Opportunities:**

        You also show interest in: {', '.join([c['label'] for c in smaller_clusters])}

        These could be unique angles or crossover content opportunities.
        """)

    # Download results
    st.header("💾 Download Results")

    results_json = json.dumps({
        'summary': {
            'total_videos': len(clustered_videos),
            'unique_channels': unique_channels,
            'themes': len(clusters_info)
        },
        'clusters': clusters_info
    }, indent=2, default=str)

    st.download_button(
        label="Download Full Analysis (JSON)",
        data=results_json,
        file_name=f"youtube_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )


if __name__ == "__main__":
    main()
