"""
YouTube Watch History Analyzer - Simple Single-File Version

Upload your YouTube watch history JSON and get AI-powered insights about
your viewing patterns, content themes, and recommendations.

Now with Claude AI for deeper insights and multi-file CSV support!

No backend, no database, no complex setup - just upload and analyze!
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import Counter
import time
import io

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


def merge_csv_files(uploaded_files) -> List[Dict[str, Any]]:
    """Merge multiple CSV playlist files into one list of videos."""
    import csv

    all_videos = []
    seen_video_ids = set()  # Deduplicate

    progress_bar = st.progress(0)
    st.write(f"Merging {len(uploaded_files)} CSV files...")

    for idx, uploaded_file in enumerate(uploaded_files):
        try:
            content = uploaded_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))

            for row in csv_reader:
                video_url = row.get('Video URL', row.get('URL', ''))
                video_id = ''

                # Extract video ID from URL
                if 'youtube.com/watch?v=' in video_url:
                    video_id = video_url.split('watch?v=')[1].split('&')[0]
                elif 'youtu.be/' in video_url:
                    video_id = video_url.split('youtu.be/')[1].split('?')[0]

                # Deduplicate videos
                if video_id and video_id not in seen_video_ids:
                    seen_video_ids.add(video_id)
                    all_videos.append({
                        'video_id': video_id,
                        'title': row.get('Video Title', row.get('Title', 'Unknown')),
                        'time': row.get('Time Added', row.get('Date', '')),
                        'channel': row.get('Channel Name', row.get('Channel', 'Unknown')),
                        'source_file': uploaded_file.name
                    })

            progress_bar.progress((idx + 1) / len(uploaded_files))

        except Exception as e:
            st.warning(f"⚠️ Error reading {uploaded_file.name}: {e}")

    st.success(f"✅ Merged {len(uploaded_files)} files → {len(all_videos)} unique videos")
    return all_videos


def load_watch_history(uploaded_file) -> List[Dict[str, Any]]:
    """Load and parse YouTube watch history (JSON) or playlist (CSV) file."""
    filename = uploaded_file.name.lower()

    try:
        # Handle CSV files (playlists from Google Takeout)
        if filename.endswith('.csv'):
            import csv

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


def enhance_clusters_with_claude(clusters_info: List[Dict], anthropic_api_key: str) -> List[Dict]:
    """Use Claude AI to generate better cluster labels and insights."""
    try:
        import anthropic
    except ImportError:
        st.warning("⚠️ anthropic package not installed. Install with: pip install anthropic")
        return clusters_info

    try:
        client = anthropic.Anthropic(api_key=anthropic_api_key)

        with st.spinner("🤖 Using Claude AI to generate deeper insights..."):
            for cluster in clusters_info:
                # Prepare data for Claude
                cluster_summary = {
                    'size': cluster['size'],
                    'top_channels': [ch[0] for ch in cluster['top_channels'][:3]],
                    'top_tags': [tag[0] for tag in cluster['top_tags'][:5]],
                    'sample_titles': [v['title'] for v in cluster['sample_videos'][:5]]
                }

                prompt = f"""Analyze this YouTube content cluster and provide insights:

Cluster Data:
- Number of videos: {cluster_summary['size']}
- Top channels: {', '.join(cluster_summary['top_channels'])}
- Top tags: {', '.join(cluster_summary['top_tags'])}
- Sample video titles: {', '.join(cluster_summary['sample_titles'][:3])}

Provide:
1. A concise theme label (5-10 words max)
2. A brief description (1-2 sentences)
3. Content creation opportunity (1-2 sentences on what content the viewer could create based on this knowledge area)

Format as JSON:
{{
  "theme": "theme label here",
  "description": "description here",
  "opportunity": "content creation opportunity here"
}}"""

                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )

                # Parse Claude's response
                try:
                    response_text = message.content[0].text
                    # Extract JSON from response (handle markdown code blocks)
                    if '```json' in response_text:
                        response_text = response_text.split('```json')[1].split('```')[0].strip()
                    elif '```' in response_text:
                        response_text = response_text.split('```')[1].split('```')[0].strip()

                    claude_insights = json.loads(response_text)

                    cluster['ai_theme'] = claude_insights.get('theme', cluster['label'])
                    cluster['ai_description'] = claude_insights.get('description', '')
                    cluster['ai_opportunity'] = claude_insights.get('opportunity', '')
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    cluster['ai_theme'] = cluster['label']
                    cluster['ai_description'] = message.content[0].text
                    cluster['ai_opportunity'] = ''

                time.sleep(0.5)  # Rate limiting

        st.success("✅ Claude AI insights generated!")
        return clusters_info

    except Exception as e:
        st.warning(f"⚠️ Claude AI analysis failed: {e}. Using basic analysis.")
        return clusters_info


def generate_overall_insights_with_claude(clusters_info: List[Dict], total_videos: int, unique_channels: int, anthropic_api_key: str) -> Dict[str, str]:
    """Use Claude to generate overall content creation recommendations."""
    try:
        import anthropic
    except ImportError:
        return {}

    try:
        client = anthropic.Anthropic(api_key=anthropic_api_key)

        # Prepare summary data
        cluster_summaries = []
        for c in clusters_info[:5]:  # Top 5 clusters
            cluster_summaries.append({
                'theme': c.get('ai_theme', c['label']),
                'size': c['size'],
                'channels': [ch[0] for ch in c['top_channels'][:2]]
            })

        prompt = f"""Analyze this YouTube viewing data and provide content creation recommendations:

Viewing Statistics:
- Total videos analyzed: {total_videos}
- Unique channels watched: {unique_channels}
- Number of content themes: {len(clusters_info)}

Top Content Themes:
{json.dumps(cluster_summaries, indent=2)}

Provide personalized content creation advice:
1. Primary Niche: What content niche should they focus on based on their strongest interests?
2. Unique Angle: What unique perspective or crossover content could they create?
3. Audience Strategy: Who would be their ideal target audience?
4. First Steps: What should they create first?

Keep each section to 2-3 sentences. Be specific and actionable.

Format as JSON:
{{
  "primary_niche": "...",
  "unique_angle": "...",
  "audience_strategy": "...",
  "first_steps": "..."
}}"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        response_text = message.content[0].text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        return json.loads(response_text)

    except Exception as e:
        st.warning(f"⚠️ Could not generate overall insights: {e}")
        return {}


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

        anthropic_api_key = st.text_input(
            "Anthropic API Key (Optional)",
            type="password",
            help="For enhanced AI insights with Claude. Get from: https://console.anthropic.com/"
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

        use_claude = st.checkbox(
            "Use Claude AI for deeper insights",
            value=bool(anthropic_api_key),
            help="Generate smarter theme labels and content recommendations (requires Anthropic API key)"
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
        5. Upload CSV file(s) from `playlists/` folder

        **💡 Tip:** You can upload **multiple CSV files** at once to merge all your playlists!
        """)

    # File upload mode selection
    upload_mode = st.radio(
        "Upload Mode:",
        ["Single File (JSON or CSV)", "Multiple CSV Files (Merge Playlists)"],
        horizontal=True
    )

    # File upload
    if upload_mode == "Multiple CSV Files (Merge Playlists)":
        uploaded_files = st.file_uploader(
            "Upload multiple playlist CSV files",
            type=['csv'],
            accept_multiple_files=True,
            help="Select all CSV files from your playlists folder to merge them"
        )

        if not uploaded_files:
            st.info("👆 Upload multiple CSV files to merge all your playlists!")
            return

        if not api_key:
            st.warning("⚠️ Please enter your YouTube API key in the sidebar to continue.")
            return

        # Merge CSV files
        with st.spinner("Merging CSV files..."):
            videos = merge_csv_files(uploaded_files)

    else:
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
        with st.spinner("Loading file..."):
            videos = load_watch_history(uploaded_file)

    if not videos:
        st.error("No videos found in the uploaded file(s). Please check the format.")
        return

    st.success(f"✅ Loaded {len(videos)} videos")

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

    # Enhance with Claude AI if enabled
    if use_claude and anthropic_api_key:
        clusters_info = enhance_clusters_with_claude(clusters_info, anthropic_api_key)

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
        theme_title = cluster.get('ai_theme', cluster['label'])
        with st.expander(f"**{theme_title}** ({cluster['size']} videos)", expanded=False):
            # Show AI insights if available
            if cluster.get('ai_description'):
                st.info(f"**🤖 AI Insight:** {cluster['ai_description']}")

            if cluster.get('ai_opportunity'):
                st.success(f"**💡 Content Opportunity:** {cluster['ai_opportunity']}")

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

    # Claude AI enhanced insights
    if use_claude and anthropic_api_key:
        st.markdown("### 🤖 AI-Powered Recommendations")

        overall_insights = generate_overall_insights_with_claude(
            clusters_info,
            len(clustered_videos),
            unique_channels,
            anthropic_api_key
        )

        if overall_insights:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**🎯 Primary Niche**")
                st.write(overall_insights.get('primary_niche', 'N/A'))

                st.markdown("**🌟 Unique Angle**")
                st.write(overall_insights.get('unique_angle', 'N/A'))

            with col2:
                st.markdown("**👥 Audience Strategy**")
                st.write(overall_insights.get('audience_strategy', 'N/A'))

                st.markdown("**🚀 First Steps**")
                st.write(overall_insights.get('first_steps', 'N/A'))

            st.markdown("---")

    # Basic recommendations
    st.markdown("""
    ### 📊 Data-Driven Insights
    """)

    # Find your niche
    biggest_cluster = clusters_info[0]
    theme_label = biggest_cluster.get('ai_theme', biggest_cluster['label'])

    st.success(f"""
    **🎯 Your Primary Interest:** {theme_label}

    You've watched {biggest_cluster['size']} videos in this theme. This represents your strongest
    content knowledge area and potential audience overlap.
    """)

    if biggest_cluster.get('ai_description'):
        st.info(f"**💡 Theme Insight:** {biggest_cluster['ai_description']}")

    if biggest_cluster.get('ai_opportunity'):
        st.success(f"**🎬 Content Opportunity:** {biggest_cluster['ai_opportunity']}")

    # Diversification opportunity
    if len(clusters_info) > 3:
        smaller_clusters = clusters_info[-3:]
        cluster_labels = [c.get('ai_theme', c['label']) for c in smaller_clusters]

        st.info(f"""
        **🌟 Diversification Opportunities:**

        You also show interest in: {', '.join(cluster_labels)}

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
