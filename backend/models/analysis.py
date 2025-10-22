"""
Analysis model for persisting YouTube watch history analysis results.

This model stores metadata about each analysis run, including timing,
status, summary statistics, and relationships to videos and clusters.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, JSON, Text, Float, Boolean,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class AnalysisStatus(str, enum.Enum):
    """Status of an analysis job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Analysis(Base):
    """
    Analysis model representing a YouTube watch history analysis.

    Stores metadata about the analysis run, summary statistics,
    and relationships to analyzed videos and generated clusters.

    Attributes:
        id: Primary key
        task_id: Celery task ID for async processing
        status: Current status of the analysis
        user_id: Optional user identifier (for multi-user systems)
        created_at: When the analysis was created
        started_at: When processing started
        completed_at: When processing completed
        total_videos: Total number of videos in watch history
        processed_videos: Number of successfully processed videos
        failed_videos: Number of videos that failed processing
        unique_channels: Number of unique channels
        date_range_start: Earliest video watch date
        date_range_end: Latest video watch date
        total_watch_time_hours: Total watch time in hours
        num_clusters: Number of generated clusters
        quota_used: YouTube API quota units consumed
        embedding_model: Name of the embedding model used
        clustering_algorithm: Name of the clustering algorithm used
        summary: JSON summary statistics
        error_message: Error message if analysis failed
        videos: Relationship to Video models
        clusters: Relationship to Cluster models
    """

    __tablename__ = 'analyses'

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Task Tracking
    task_id = Column(String(255), unique=True, index=True, nullable=False,
                    comment="Celery task ID for tracking async job")

    status = Column(SQLEnum(AnalysisStatus), default=AnalysisStatus.PENDING,
                   nullable=False, index=True,
                   comment="Current status of analysis job")

    # User Information
    user_id = Column(String(255), index=True, nullable=True,
                    comment="Optional user identifier for multi-user systems")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False,
                       index=True, comment="When analysis was created")

    started_at = Column(DateTime, nullable=True,
                       comment="When processing started")

    completed_at = Column(DateTime, nullable=True,
                         comment="When processing completed")

    # Video Statistics
    total_videos = Column(Integer, default=0, nullable=False,
                         comment="Total videos in watch history")

    processed_videos = Column(Integer, default=0, nullable=False,
                             comment="Successfully processed videos")

    failed_videos = Column(Integer, default=0, nullable=False,
                          comment="Videos that failed processing")

    unique_channels = Column(Integer, default=0, nullable=False,
                            comment="Number of unique channels")

    # Time Range
    date_range_start = Column(DateTime, nullable=True,
                             comment="Earliest video watch date")

    date_range_end = Column(DateTime, nullable=True,
                           comment="Latest video watch date")

    # Watch Time
    total_watch_time_hours = Column(Float, default=0.0, nullable=False,
                                   comment="Total watch time in hours")

    # Clustering Results
    num_clusters = Column(Integer, default=0, nullable=False,
                         comment="Number of generated clusters")

    # Resource Usage
    quota_used = Column(Integer, default=0, nullable=False,
                       comment="YouTube API quota units consumed")

    # Model Configuration
    embedding_model = Column(String(100), nullable=True,
                            comment="Name of embedding model used")

    clustering_algorithm = Column(String(50), nullable=True,
                                 comment="Clustering algorithm (e.g., DBSCAN, KMeans)")

    # Summary Data
    summary = Column(JSON, nullable=True,
                    comment="JSON summary statistics and metadata")

    # Error Handling
    error_message = Column(Text, nullable=True,
                          comment="Error message if analysis failed")

    # Relationships
    videos = relationship(
        "Video",
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="dynamic"  # Lazy load for large collections
    )

    clusters = relationship(
        "Cluster",
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        """String representation of Analysis."""
        return (
            f"<Analysis(id={self.id}, task_id='{self.task_id}', "
            f"status='{self.status}', videos={self.total_videos})>"
        )

    def to_dict(self) -> dict:
        """
        Convert Analysis to dictionary.

        Returns:
            Dictionary representation of the analysis
        """
        return {
            'id': self.id,
            'task_id': self.task_id,
            'status': self.status.value if isinstance(self.status, AnalysisStatus) else self.status,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_videos': self.total_videos,
            'processed_videos': self.processed_videos,
            'failed_videos': self.failed_videos,
            'unique_channels': self.unique_channels,
            'date_range_start': self.date_range_start.isoformat() if self.date_range_start else None,
            'date_range_end': self.date_range_end.isoformat() if self.date_range_end else None,
            'total_watch_time_hours': self.total_watch_time_hours,
            'num_clusters': self.num_clusters,
            'quota_used': self.quota_used,
            'embedding_model': self.embedding_model,
            'clustering_algorithm': self.clustering_algorithm,
            'summary': self.summary,
            'error_message': self.error_message
        }

    @property
    def duration_seconds(self) -> Optional[float]:
        """
        Calculate analysis duration in seconds.

        Returns:
            Duration in seconds, or None if not completed
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    @property
    def is_completed(self) -> bool:
        """Check if analysis is completed."""
        return self.status == AnalysisStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if analysis failed."""
        return self.status == AnalysisStatus.FAILED

    @property
    def is_processing(self) -> bool:
        """Check if analysis is currently processing."""
        return self.status == AnalysisStatus.PROCESSING

    @property
    def success_rate(self) -> float:
        """
        Calculate success rate of video processing.

        Returns:
            Success rate as percentage (0-100)
        """
        if self.total_videos == 0:
            return 0.0
        return (self.processed_videos / self.total_videos) * 100

    def mark_started(self) -> None:
        """Mark analysis as started."""
        self.status = AnalysisStatus.PROCESSING
        self.started_at = datetime.utcnow()

    def mark_completed(self) -> None:
        """Mark analysis as completed."""
        self.status = AnalysisStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def mark_failed(self, error_message: str) -> None:
        """
        Mark analysis as failed.

        Args:
            error_message: Error description
        """
        self.status = AnalysisStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
