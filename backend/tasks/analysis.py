"""
Analysis tasks for YouTube Audit Engine.

This module contains Celery tasks for analyzing YouTube watch history,
including video enrichment, embedding generation, clustering, and scoring.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
from celery import current_task
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.database import get_session
from backend.models.analysis import Analysis, AnalysisStatus
from backend.models.video import Video
from backend.models.cluster import Cluster
from backend.utils.logging_config import get_logger
from backend.exceptions import (
    IngestionError,
    EnrichmentError,
    EmbeddingError,
    ClusteringError,
    YouTubeAuditError
)

# Import analysis modules
from backend.modules.ingestion import parse_takeout_file
from backend.modules.enrichment import enrich_video_metadata
from backend.modules.embedding import get_video_embeddings
from backend.modules.clustering import cluster_videos
from backend.modules.scoring import score_clusters

logger = get_logger(__name__)


@celery_app.task(name='tasks.analyze_watch_history', bind=True, max_retries=0)
def analyze_watch_history(
    self,
    file_path: str,
    analysis_id: int,
    api_key: Optional[str] = None,
    num_clusters: int = 10
) -> Dict[str, Any]:
    """
    Analyze YouTube watch history asynchronously.

    This is the main analysis task that orchestrates the entire pipeline:
    1. Ingest watch history file
    2. Enrich with YouTube API metadata
    3. Generate semantic embeddings
    4. Cluster videos into topics
    5. Score clusters
    6. Persist results to database

    Args:
        file_path: Path to watch-history.json or takeout zip file
        analysis_id: Database ID of Analysis record
        api_key: Optional YouTube API key (falls back to config)
        num_clusters: Number of clusters to generate

    Returns:
        Dictionary with analysis results

    Raises:
        IngestionError: If file parsing fails
        EnrichmentError: If YouTube API enrichment fails
        EmbeddingError: If embedding generation fails
        ClusteringError: If clustering fails
    """
    task_id = self.request.id
    logger.info(
        "Starting watch history analysis",
        task_id=task_id,
        analysis_id=analysis_id,
        file_path=file_path
    )

    session: Session = get_session()
    analysis: Optional[Analysis] = None

    try:
        # Load Analysis record from database
        analysis = session.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise ValueError(f"Analysis record {analysis_id} not found")

        # Mark as started
        analysis.mark_started()
        session.commit()

        # ============================================================
        # STEP 1: Ingest Watch History
        # ============================================================
        _update_progress(self, 5, "Parsing watch history file...")
        logger.info("Step 1: Ingesting watch history", task_id=task_id)

        try:
            watch_history = parse_takeout_file(file_path)
            total_videos = len(watch_history)
            analysis.total_videos = total_videos
            session.commit()

            logger.info(
                "Watch history parsed",
                task_id=task_id,
                total_videos=total_videos
            )

            if total_videos == 0:
                raise IngestionError(
                    message="No videos found in watch history",
                    details={'file_path': file_path}
                )

        except Exception as e:
            raise IngestionError(
                message=f"Failed to parse watch history: {str(e)}",
                details={'file_path': file_path, 'error': str(e)}
            )

        # ============================================================
        # STEP 2: Extract Video IDs
        # ============================================================
        _update_progress(self, 10, "Extracting video IDs...")
        logger.info("Step 2: Extracting video IDs", task_id=task_id)

        video_ids = []
        watch_dates = {}

        for entry in watch_history:
            # Extract video ID from URL or titleUrl
            video_id = _extract_video_id(entry)
            if video_id:
                video_ids.append(video_id)
                # Store watch date
                watch_dates[video_id] = entry.get('time')

        unique_video_ids = list(set(video_ids))
        logger.info(
            "Video IDs extracted",
            task_id=task_id,
            total_entries=total_videos,
            unique_videos=len(unique_video_ids)
        )

        # ============================================================
        # STEP 3: Enrich with YouTube API
        # ============================================================
        _update_progress(self, 20, f"Enriching {len(unique_video_ids)} videos with YouTube API...")
        logger.info("Step 3: Enriching videos with YouTube API", task_id=task_id)

        try:
            enriched_metadata = enrich_video_metadata(
                video_ids=unique_video_ids,
                api_key=api_key
            )

            analysis.processed_videos = len(enriched_metadata)
            analysis.failed_videos = len(unique_video_ids) - len(enriched_metadata)
            session.commit()

            logger.info(
                "Video enrichment complete",
                task_id=task_id,
                processed=len(enriched_metadata),
                failed=analysis.failed_videos
            )

            if len(enriched_metadata) == 0:
                raise EnrichmentError(
                    message="No videos could be enriched",
                    details={'requested': len(unique_video_ids)}
                )

        except Exception as e:
            raise EnrichmentError(
                message=f"Failed to enrich videos: {str(e)}",
                details={'video_count': len(unique_video_ids), 'error': str(e)}
            )

        # ============================================================
        # STEP 4: Generate Embeddings
        # ============================================================
        _update_progress(self, 50, "Generating semantic embeddings...")
        logger.info("Step 4: Generating embeddings", task_id=task_id)

        try:
            embeddings = get_video_embeddings(enriched_metadata)
            embedding_dim = embeddings.shape[1]
            analysis.embedding_model = "all-MiniLM-L6-v2"
            session.commit()

            logger.info(
                "Embeddings generated",
                task_id=task_id,
                count=len(embeddings),
                dimension=embedding_dim
            )

        except Exception as e:
            raise EmbeddingError(
                message=f"Failed to generate embeddings: {str(e)}",
                details={'video_count': len(enriched_metadata), 'error': str(e)}
            )

        # ============================================================
        # STEP 5: Cluster Videos
        # ============================================================
        _update_progress(self, 70, f"Clustering videos into {num_clusters} topics...")
        logger.info("Step 5: Clustering videos", task_id=task_id)

        try:
            clusters = cluster_videos(embeddings, num_clusters=num_clusters)
            analysis.num_clusters = len(clusters)
            analysis.clustering_algorithm = "DBSCAN"
            session.commit()

            logger.info(
                "Clustering complete",
                task_id=task_id,
                num_clusters=len(clusters)
            )

        except Exception as e:
            raise ClusteringError(
                message=f"Failed to cluster videos: {str(e)}",
                details={'video_count': len(embeddings), 'error': str(e)}
            )

        # ============================================================
        # STEP 6: Score Clusters
        # ============================================================
        _update_progress(self, 85, "Scoring clusters...")
        logger.info("Step 6: Scoring clusters", task_id=task_id)

        try:
            scored_clusters = score_clusters(clusters, enriched_metadata)
            logger.info("Cluster scoring complete", task_id=task_id)
        except Exception as e:
            logger.warning(
                "Failed to score clusters",
                task_id=task_id,
                error=str(e)
            )
            scored_clusters = []

        # ============================================================
        # STEP 7: Persist to Database
        # ============================================================
        _update_progress(self, 90, "Saving results to database...")
        logger.info("Step 7: Persisting results", task_id=task_id)

        try:
            # Calculate statistics
            channel_ids = set()
            watch_times = []
            earliest_date = None
            latest_date = None

            for video_meta in enriched_metadata:
                channel_id = video_meta.get('snippet', {}).get('channelId')
                if channel_id:
                    channel_ids.add(channel_id)

            analysis.unique_channels = len(channel_ids)

            # Save cluster records
            cluster_models = []
            for cluster_data in scored_clusters:
                cluster_model = Cluster(
                    analysis_id=analysis_id,
                    cluster_number=cluster_data.get('cluster_id', -1),
                    label=cluster_data.get('label', f"Cluster {cluster_data.get('cluster_id')}"),
                    size=cluster_data.get('size', 0),
                    top_keywords=cluster_data.get('keywords', [])[:10],
                    metadata=cluster_data
                )
                cluster_models.append(cluster_model)
                session.add(cluster_model)

            session.flush()  # Get cluster IDs

            # Save video records
            cluster_id_map = {c.cluster_number: c.id for c in cluster_models}

            for idx, video_meta in enumerate(enriched_metadata):
                video_id = video_meta.get('id')
                snippet = video_meta.get('snippet', {})

                # Find cluster assignment
                cluster_num = _find_video_cluster(idx, clusters)
                cluster_db_id = cluster_id_map.get(cluster_num) if cluster_num is not None else None

                video_model = Video(
                    analysis_id=analysis_id,
                    cluster_id=cluster_db_id,
                    video_id=video_id,
                    title=snippet.get('title'),
                    description=snippet.get('description'),
                    channel_id=snippet.get('channelId'),
                    channel_name=snippet.get('channelTitle'),
                    published_at=_parse_datetime(snippet.get('publishedAt')),
                    watched_at=_parse_datetime(watch_dates.get(video_id)),
                    thumbnail_url=snippet.get('thumbnails', {}).get('default', {}).get('url'),
                    tags=snippet.get('tags', [])[:20] if snippet.get('tags') else None,
                    embedding_vector=embeddings[idx].tolist(),
                    embedding_model="all-MiniLM-L6-v2",
                    is_processed=True
                )
                session.add(video_model)

            # Mark analysis as complete
            analysis.mark_completed()
            session.commit()

            logger.info(
                "Results persisted to database",
                task_id=task_id,
                analysis_id=analysis_id,
                videos=len(enriched_metadata),
                clusters=len(cluster_models)
            )

        except Exception as e:
            logger.error(
                "Failed to persist results",
                task_id=task_id,
                error=str(e)
            )
            raise

        # ============================================================
        # STEP 8: Prepare Response
        # ============================================================
        _update_progress(self, 100, "Analysis complete!")
        logger.info("Analysis complete", task_id=task_id, analysis_id=analysis_id)

        return {
            'analysis_id': analysis_id,
            'task_id': task_id,
            'status': 'completed',
            'total_videos': total_videos,
            'processed_videos': len(enriched_metadata),
            'unique_channels': len(channel_ids),
            'num_clusters': len(scored_clusters),
            'clusters': scored_clusters[:10],  # Return top 10 for preview
            'completed_at': datetime.utcnow().isoformat()
        }

    except YouTubeAuditError as e:
        # Handle our custom exceptions
        logger.error(
            "Analysis failed with known error",
            task_id=task_id,
            analysis_id=analysis_id,
            error_code=e.error_code,
            error=str(e)
        )

        if analysis:
            analysis.mark_failed(str(e))
            session.commit()

        raise

    except Exception as e:
        # Handle unexpected exceptions
        logger.error(
            "Analysis failed with unexpected error",
            task_id=task_id,
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )

        if analysis:
            analysis.mark_failed(f"Unexpected error: {str(e)}")
            session.commit()

        raise

    finally:
        session.close()


def _update_progress(task, percent: int, status: str) -> None:
    """
    Update task progress.

    Args:
        task: Celery task instance
        percent: Progress percentage (0-100)
        status: Status message
    """
    task.update_state(
        state='PROGRESS',
        meta={
            'percent': percent,
            'status': status,
            'current': percent,
            'total': 100
        }
    )


def _extract_video_id(entry: Dict[str, Any]) -> Optional[str]:
    """
    Extract YouTube video ID from watch history entry.

    Args:
        entry: Watch history entry

    Returns:
        Video ID or None if not found
    """
    # Try to get from titleUrl
    title_url = entry.get('titleUrl', '')
    if 'watch?v=' in title_url:
        return title_url.split('watch?v=')[-1].split('&')[0]

    # Try to get from subtitles URL
    for subtitle in entry.get('subtitles', []):
        url = subtitle.get('url', '')
        if 'watch?v=' in url:
            return url.split('watch?v=')[-1].split('&')[0]

    return None


def _find_video_cluster(video_idx: int, clusters: Dict[int, List[int]]) -> Optional[int]:
    """
    Find which cluster a video belongs to.

    Args:
        video_idx: Video index
        clusters: Cluster assignments {cluster_id: [video_indices]}

    Returns:
        Cluster ID or None if not assigned
    """
    for cluster_id, video_indices in clusters.items():
        if video_idx in video_indices:
            return cluster_id
    return None


def _parse_datetime(date_string: Optional[str]) -> Optional[datetime]:
    """
    Parse datetime string to datetime object.

    Args:
        date_string: ISO format date string

    Returns:
        datetime object or None
    """
    if not date_string:
        return None

    try:
        # Try ISO format
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except:
        try:
            # Try other common formats
            from dateutil import parser
            return parser.parse(date_string)
        except:
            return None
