"""
Cluster model for persisting YouTube video clusters and topic analysis.

This model stores cluster metadata, labels, statistics, and
relationships to clustered videos.
"""

from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Float, ForeignKey, JSON, Index
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from backend.database import Base


class Cluster(Base):
    """
    Cluster model representing a thematic video cluster.

    Stores cluster metadata, topic labels, statistics, and
    relationships to videos assigned to this cluster.

    Attributes:
        id: Primary key
        analysis_id: Foreign key to Analysis
        cluster_number: Sequential cluster number (0, 1, 2, ...)
        label: Human-readable cluster label/topic
        description: Detailed cluster description
        size: Number of videos in this cluster
        avg_watch_time_hours: Average watch time for videos in cluster
        top_channels: List of top channels in this cluster
        top_keywords: List of top keywords/topics
        centroid: Cluster centroid vector (center point in embedding space)
        avg_distance_to_center: Average distance of videos to centroid
        silhouette_score: Silhouette score for cluster quality
        cluster_metadata: Additional JSON metadata
        analysis: Relationship to Analysis model
        videos: Relationship to Video models
    """

    __tablename__ = 'clusters'

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys
    analysis_id = Column(Integer, ForeignKey('analyses.id', ondelete='CASCADE'),
                        nullable=False, index=True,
                        comment="Analysis this cluster belongs to")

    # Cluster Information
    cluster_number = Column(Integer, nullable=False,
                           comment="Sequential cluster number (0, 1, 2, ...)")

    label = Column(String(255), nullable=True,
                  comment="Human-readable cluster label/topic")

    description = Column(Text, nullable=True,
                        comment="Detailed cluster description")

    # Statistics
    size = Column(Integer, default=0, nullable=False,
                 comment="Number of videos in this cluster")

    avg_watch_time_hours = Column(Float, default=0.0, nullable=False,
                                  comment="Average watch time for cluster videos")

    # Content Analysis
    top_channels = Column(JSON, nullable=True,
                         comment="List of top channels in cluster (JSON array)")

    top_keywords = Column(ARRAY(String), nullable=True,
                         comment="List of top keywords/topics")

    # Clustering Metrics
    centroid = Column(ARRAY(Float), nullable=True,
                     comment="Cluster centroid vector (center in embedding space)")

    avg_distance_to_center = Column(Float, nullable=True,
                                   comment="Average distance of videos to centroid")

    silhouette_score = Column(Float, nullable=True,
                             comment="Silhouette score for cluster quality (-1 to 1)")

    # Additional Data
    cluster_metadata = Column(JSON, nullable=True,
                             comment="Additional cluster metadata (JSON)")

    # Relationships
    analysis = relationship("Analysis", back_populates="clusters")
    videos = relationship("Video", back_populates="cluster", lazy="dynamic")

    # Composite Indexes
    __table_args__ = (
        # Unique constraint on cluster_number per analysis
        Index('ix_clusters_analysis_number', 'analysis_id', 'cluster_number', unique=True),
    )

    def __repr__(self) -> str:
        """String representation of Cluster."""
        return (
            f"<Cluster(id={self.id}, analysis_id={self.analysis_id}, "
            f"number={self.cluster_number}, label='{self.label}', size={self.size})>"
        )

    def to_dict(self, include_centroid: bool = False) -> dict:
        """
        Convert Cluster to dictionary.

        Args:
            include_centroid: Whether to include centroid vector (can be large)

        Returns:
            Dictionary representation of the cluster
        """
        data = {
            'id': self.id,
            'analysis_id': self.analysis_id,
            'cluster_number': self.cluster_number,
            'label': self.label,
            'description': self.description,
            'size': self.size,
            'avg_watch_time_hours': self.avg_watch_time_hours,
            'top_channels': self.top_channels,
            'top_keywords': self.top_keywords,
            'avg_distance_to_center': self.avg_distance_to_center,
            'silhouette_score': self.silhouette_score,
            'cluster_metadata': self.cluster_metadata
        }

        if include_centroid and self.centroid:
            data['centroid'] = self.centroid

        return data

    @property
    def quality_rating(self) -> Optional[str]:
        """
        Get quality rating based on silhouette score.

        Returns:
            Quality rating (Excellent, Good, Fair, Poor) or None
        """
        if self.silhouette_score is None:
            return None

        if self.silhouette_score >= 0.7:
            return "Excellent"
        elif self.silhouette_score >= 0.5:
            return "Good"
        elif self.silhouette_score >= 0.25:
            return "Fair"
        else:
            return "Poor"

    @property
    def is_noise_cluster(self) -> bool:
        """
        Check if this is a noise cluster (DBSCAN cluster -1).

        Returns:
            True if noise cluster, False otherwise
        """
        return self.cluster_number == -1

    @property
    def video_count(self) -> int:
        """
        Get count of videos in this cluster.

        Returns:
            Number of videos
        """
        return self.size

    def get_top_keywords(self, limit: int = 10) -> List[str]:
        """
        Get top N keywords for this cluster.

        Args:
            limit: Maximum number of keywords to return

        Returns:
            List of top keywords
        """
        if not self.top_keywords:
            return []
        return self.top_keywords[:limit]

    def get_top_channels(self, limit: int = 10) -> List[dict]:
        """
        Get top N channels for this cluster.

        Args:
            limit: Maximum number of channels to return

        Returns:
            List of channel dictionaries
        """
        if not self.top_channels:
            return []

        channels = self.top_channels
        if isinstance(channels, list):
            return channels[:limit]
        return []

    def add_keyword(self, keyword: str) -> None:
        """
        Add a keyword to the cluster.

        Args:
            keyword: Keyword to add
        """
        if self.top_keywords is None:
            self.top_keywords = []

        if keyword not in self.top_keywords:
            self.top_keywords.append(keyword)

    def update_statistics(
        self,
        size: int,
        avg_watch_time: float,
        avg_distance: Optional[float] = None,
        silhouette: Optional[float] = None
    ) -> None:
        """
        Update cluster statistics.

        Args:
            size: Number of videos in cluster
            avg_watch_time: Average watch time in hours
            avg_distance: Average distance to centroid
            silhouette: Silhouette score
        """
        self.size = size
        self.avg_watch_time_hours = avg_watch_time

        if avg_distance is not None:
            self.avg_distance_to_center = avg_distance

        if silhouette is not None:
            self.silhouette_score = silhouette
