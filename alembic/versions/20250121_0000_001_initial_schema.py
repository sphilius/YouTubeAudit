"""Initial schema for YouTube Audit Engine

Revision ID: 001
Revises:
Create Date: 2025-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade database schema.

    Creates initial tables for:
    - analyses: Stores analysis metadata and status
    - videos: Stores video metadata and embeddings
    - clusters: Stores cluster information and statistics
    """

    # Create analyses table
    op.create_table(
        'analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=255), nullable=False, comment='Celery task ID for tracking async job'),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='analysisstatus'), nullable=False, comment='Current status of analysis job'),
        sa.Column('user_id', sa.String(length=255), nullable=True, comment='Optional user identifier for multi-user systems'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='When analysis was created'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='When processing started'),
        sa.Column('completed_at', sa.DateTime(), nullable=True, comment='When processing completed'),
        sa.Column('total_videos', sa.Integer(), nullable=False, comment='Total videos in watch history'),
        sa.Column('processed_videos', sa.Integer(), nullable=False, comment='Successfully processed videos'),
        sa.Column('failed_videos', sa.Integer(), nullable=False, comment='Videos that failed processing'),
        sa.Column('unique_channels', sa.Integer(), nullable=False, comment='Number of unique channels'),
        sa.Column('date_range_start', sa.DateTime(), nullable=True, comment='Earliest video watch date'),
        sa.Column('date_range_end', sa.DateTime(), nullable=True, comment='Latest video watch date'),
        sa.Column('total_watch_time_hours', sa.Float(), nullable=False, comment='Total watch time in hours'),
        sa.Column('num_clusters', sa.Integer(), nullable=False, comment='Number of generated clusters'),
        sa.Column('quota_used', sa.Integer(), nullable=False, comment='YouTube API quota units consumed'),
        sa.Column('embedding_model', sa.String(length=100), nullable=True, comment='Name of embedding model used'),
        sa.Column('clustering_algorithm', sa.String(length=50), nullable=True, comment='Clustering algorithm (e.g., DBSCAN, KMeans)'),
        sa.Column('summary', sa.JSON(), nullable=True, comment='JSON summary statistics and metadata'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if analysis failed'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for analyses table
    op.create_index('ix_analyses_task_id', 'analyses', ['task_id'], unique=True)
    op.create_index('ix_analyses_status', 'analyses', ['status'], unique=False)
    op.create_index('ix_analyses_user_id', 'analyses', ['user_id'], unique=False)
    op.create_index('ix_analyses_created_at', 'analyses', ['created_at'], unique=False)

    # Create clusters table
    op.create_table(
        'clusters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False, comment='Analysis this cluster belongs to'),
        sa.Column('cluster_number', sa.Integer(), nullable=False, comment='Sequential cluster number (0, 1, 2, ...)'),
        sa.Column('label', sa.String(length=255), nullable=True, comment='Human-readable cluster label/topic'),
        sa.Column('description', sa.Text(), nullable=True, comment='Detailed cluster description'),
        sa.Column('size', sa.Integer(), nullable=False, comment='Number of videos in this cluster'),
        sa.Column('avg_watch_time_hours', sa.Float(), nullable=False, comment='Average watch time for cluster videos'),
        sa.Column('top_channels', sa.JSON(), nullable=True, comment='List of top channels in cluster (JSON array)'),
        sa.Column('top_keywords', ARRAY(sa.String()), nullable=True, comment='List of top keywords/topics'),
        sa.Column('centroid', ARRAY(sa.Float()), nullable=True, comment='Cluster centroid vector (center in embedding space)'),
        sa.Column('avg_distance_to_center', sa.Float(), nullable=True, comment='Average distance of videos to centroid'),
        sa.Column('silhouette_score', sa.Float(), nullable=True, comment='Silhouette score for cluster quality (-1 to 1)'),
        sa.Column('metadata', sa.JSON(), nullable=True, comment='Additional cluster metadata (JSON)'),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for clusters table
    op.create_index('ix_clusters_analysis_id', 'clusters', ['analysis_id'], unique=False)
    op.create_index('ix_clusters_analysis_number', 'clusters', ['analysis_id', 'cluster_number'], unique=True)

    # Create videos table
    op.create_table(
        'videos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False, comment='Analysis this video belongs to'),
        sa.Column('cluster_id', sa.Integer(), nullable=True, comment='Assigned cluster'),
        sa.Column('video_id', sa.String(length=20), nullable=False, comment='YouTube video ID (e.g., dQw4w9WgXcQ)'),
        sa.Column('title', sa.Text(), nullable=True, comment='Video title'),
        sa.Column('description', sa.Text(), nullable=True, comment='Video description'),
        sa.Column('channel_id', sa.String(length=50), nullable=True, comment='YouTube channel ID'),
        sa.Column('channel_name', sa.String(length=255), nullable=True, comment='Channel name'),
        sa.Column('published_at', sa.DateTime(), nullable=True, comment='When video was published on YouTube'),
        sa.Column('watched_at', sa.DateTime(), nullable=True, comment='When user watched this video'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True, comment='Video duration in seconds'),
        sa.Column('view_count', sa.Integer(), nullable=True, comment='Number of views'),
        sa.Column('like_count', sa.Integer(), nullable=True, comment='Number of likes'),
        sa.Column('comment_count', sa.Integer(), nullable=True, comment='Number of comments'),
        sa.Column('category_id', sa.String(length=10), nullable=True, comment='YouTube category ID'),
        sa.Column('category_name', sa.String(length=100), nullable=True, comment='YouTube category name'),
        sa.Column('tags', ARRAY(sa.String()), nullable=True, comment='List of video tags'),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True, comment='URL to video thumbnail'),
        sa.Column('embedding_vector', ARRAY(sa.Float()), nullable=True, comment='Semantic embedding vector'),
        sa.Column('embedding_model', sa.String(length=100), nullable=True, comment='Name of embedding model used'),
        sa.Column('cluster_label', sa.String(length=255), nullable=True, comment='Human-readable cluster label'),
        sa.Column('distance_to_cluster_center', sa.Float(), nullable=True, comment='Distance to cluster centroid'),
        sa.Column('is_processed', sa.Boolean(), nullable=False, comment='Whether video was successfully processed'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if processing failed'),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for videos table
    op.create_index('ix_videos_analysis_id', 'videos', ['analysis_id'], unique=False)
    op.create_index('ix_videos_cluster_id', 'videos', ['cluster_id'], unique=False)
    op.create_index('ix_videos_video_id', 'videos', ['video_id'], unique=False)
    op.create_index('ix_videos_channel_id', 'videos', ['channel_id'], unique=False)
    op.create_index('ix_videos_watched_at', 'videos', ['watched_at'], unique=False)

    # Create composite indexes for videos table
    op.create_index('ix_videos_analysis_cluster', 'videos', ['analysis_id', 'cluster_id'], unique=False)
    op.create_index('ix_videos_analysis_channel', 'videos', ['analysis_id', 'channel_id'], unique=False)
    op.create_index('ix_videos_analysis_video_unique', 'videos', ['analysis_id', 'video_id'], unique=True)


def downgrade() -> None:
    """
    Downgrade database schema.

    Drops all tables and indexes created in the upgrade.
    """
    # Drop tables in reverse order (respect foreign key constraints)
    op.drop_index('ix_videos_analysis_video_unique', table_name='videos')
    op.drop_index('ix_videos_analysis_channel', table_name='videos')
    op.drop_index('ix_videos_analysis_cluster', table_name='videos')
    op.drop_index('ix_videos_watched_at', table_name='videos')
    op.drop_index('ix_videos_channel_id', table_name='videos')
    op.drop_index('ix_videos_video_id', table_name='videos')
    op.drop_index('ix_videos_cluster_id', table_name='videos')
    op.drop_index('ix_videos_analysis_id', table_name='videos')
    op.drop_table('videos')

    op.drop_index('ix_clusters_analysis_number', table_name='clusters')
    op.drop_index('ix_clusters_analysis_id', table_name='clusters')
    op.drop_table('clusters')

    op.drop_index('ix_analyses_created_at', table_name='analyses')
    op.drop_index('ix_analyses_user_id', table_name='analyses')
    op.drop_index('ix_analyses_status', table_name='analyses')
    op.drop_index('ix_analyses_task_id', table_name='analyses')
    op.drop_table('analyses')

    # Drop custom enum type
    op.execute("DROP TYPE IF EXISTS analysisstatus")
