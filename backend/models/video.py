"""
Video model for persisting YouTube video metadata and analysis results.

This model stores video information, watch history data, metadata
from YouTube API, embeddings, and cluster assignments.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from backend.database import Base


class Video(Base):
    """
    Video model representing a YouTube video from watch history.

    Stores video metadata, watch information, embeddings, and cluster assignment.

    Attributes:
        id: Primary key
        analysis_id: Foreign key to Analysis
        video_id: YouTube video ID
        title: Video title
        description: Video description
        channel_id: YouTube channel ID
        channel_name: Channel name
        published_at: When video was published
        watched_at: When user watched the video
        duration_seconds: Video duration in seconds
        view_count: Number of views
        like_count: Number of likes
        comment_count: Number of comments
        category_id: YouTube category ID
        category_name: Category name
        tags: List of video tags
        thumbnail_url: URL to video thumbnail
        embedding_vector: Semantic embedding vector (stored as array)
        embedding_model: Name of embedding model used
        cluster_id: Foreign key to Cluster (assigned cluster)
        cluster_label: Human-readable cluster label
        distance_to_cluster_center: Distance to cluster centroid
        is_processed: Whether video was successfully processed
        error_message: Error message if processing failed
        analysis: Relationship to Analysis model
        cluster: Relationship to Cluster model
    """

    __tablename__ = 'videos'

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys
    analysis_id = Column(Integer, ForeignKey('analyses.id', ondelete='CASCADE'),
                        nullable=False, index=True,
                        comment="Analysis this video belongs to")

    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='SET NULL'),
                       nullable=True, index=True,
                       comment="Assigned cluster")

    # YouTube Video Information
    video_id = Column(String(20), nullable=False, index=True,
                     comment="YouTube video ID (e.g., dQw4w9WgXcQ)")

    title = Column(Text, nullable=True,
                  comment="Video title")

    description = Column(Text, nullable=True,
                        comment="Video description")

    # Channel Information
    channel_id = Column(String(50), nullable=True, index=True,
                       comment="YouTube channel ID")

    channel_name = Column(String(255), nullable=True,
                         comment="Channel name")

    # Timestamps
    published_at = Column(DateTime, nullable=True,
                         comment="When video was published on YouTube")

    watched_at = Column(DateTime, nullable=True, index=True,
                       comment="When user watched this video")

    # Video Metrics
    duration_seconds = Column(Integer, nullable=True,
                             comment="Video duration in seconds")

    view_count = Column(Integer, nullable=True,
                       comment="Number of views")

    like_count = Column(Integer, nullable=True,
                       comment="Number of likes")

    comment_count = Column(Integer, nullable=True,
                          comment="Number of comments")

    # Categorization
    category_id = Column(String(10), nullable=True,
                        comment="YouTube category ID")

    category_name = Column(String(100), nullable=True,
                          comment="YouTube category name")

    tags = Column(ARRAY(String), nullable=True,
                 comment="List of video tags")

    # Media
    thumbnail_url = Column(String(500), nullable=True,
                          comment="URL to video thumbnail")

    # Embeddings
    embedding_vector = Column(ARRAY(Float), nullable=True,
                             comment="Semantic embedding vector")

    embedding_model = Column(String(100), nullable=True,
                            comment="Name of embedding model used")

    # Clustering Results
    cluster_label = Column(String(255), nullable=True,
                          comment="Human-readable cluster label")

    distance_to_cluster_center = Column(Float, nullable=True,
                                       comment="Distance to cluster centroid")

    # Processing Status
    is_processed = Column(Boolean, default=False, nullable=False,
                         comment="Whether video was successfully processed")

    error_message = Column(Text, nullable=True,
                          comment="Error message if processing failed")

    # Relationships
    analysis = relationship("Analysis", back_populates="videos")
    cluster = relationship("Cluster", back_populates="videos")

    # Composite Indexes
    __table_args__ = (
        # Index for finding videos by analysis and cluster
        Index('ix_videos_analysis_cluster', 'analysis_id', 'cluster_id'),
        # Index for finding videos by channel in an analysis
        Index('ix_videos_analysis_channel', 'analysis_id', 'channel_id'),
        # Unique constraint on video_id per analysis
        Index('ix_videos_analysis_video_unique', 'analysis_id', 'video_id', unique=True),
    )

    def __repr__(self) -> str:
        """String representation of Video."""
        return (
            f"<Video(id={self.id}, video_id='{self.video_id}', "
            f"title='{self.title[:50] if self.title else None}...')>"
        )

    def to_dict(self, include_embedding: bool = False) -> dict:
        """
        Convert Video to dictionary.

        Args:
            include_embedding: Whether to include embedding vector (can be large)

        Returns:
            Dictionary representation of the video
        """
        data = {
            'id': self.id,
            'analysis_id': self.analysis_id,
            'video_id': self.video_id,
            'title': self.title,
            'description': self.description,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'watched_at': self.watched_at.isoformat() if self.watched_at else None,
            'duration_seconds': self.duration_seconds,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'category_id': self.category_id,
            'category_name': self.category_name,
            'tags': self.tags,
            'thumbnail_url': self.thumbnail_url,
            'cluster_id': self.cluster_id,
            'cluster_label': self.cluster_label,
            'distance_to_cluster_center': self.distance_to_cluster_center,
            'is_processed': self.is_processed,
            'error_message': self.error_message
        }

        if include_embedding and self.embedding_vector:
            data['embedding_vector'] = self.embedding_vector
            data['embedding_model'] = self.embedding_model

        return data

    @property
    def youtube_url(self) -> str:
        """
        Get YouTube watch URL.

        Returns:
            Full YouTube URL for this video
        """
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def duration_formatted(self) -> Optional[str]:
        """
        Get formatted duration (HH:MM:SS).

        Returns:
            Formatted duration string, or None if duration not available
        """
        if not self.duration_seconds:
            return None

        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    @property
    def has_embedding(self) -> bool:
        """Check if video has an embedding vector."""
        return self.embedding_vector is not None and len(self.embedding_vector) > 0

    def mark_processed(self) -> None:
        """Mark video as successfully processed."""
        self.is_processed = True
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        """
        Mark video processing as failed.

        Args:
            error_message: Error description
        """
        self.is_processed = False
        self.error_message = error_message
