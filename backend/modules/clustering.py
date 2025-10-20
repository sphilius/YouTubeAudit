from typing import List, Dict, Any
import numpy as np
from sklearn.cluster import KMeans
from backend.utils.logging_config import get_logger
from backend.exceptions import ClusteringError, InsufficientDataError, ClusteringAlgorithmError

log = get_logger(__name__)


def cluster_videos(embeddings: np.ndarray, num_clusters: int = 10) -> Dict[int, List[int]]:
    """
    Clusters video embeddings into a specified number of clusters.

    Args:
        embeddings: A numpy array of video embeddings.
        num_clusters: The number of clusters to create.

    Returns:
        A dictionary mapping cluster ID to a list of video indices in that cluster.

    Raises:
        InsufficientDataError: If there are too few videos to cluster
        ClusteringAlgorithmError: If the clustering algorithm fails
    """
    log.info("Starting video clustering",
             video_count=embeddings.shape[0],
             embedding_dimension=embeddings.shape[1],
             num_clusters=num_clusters)

    # Validate input
    if embeddings.shape[0] < 2:
        log.error("Insufficient data for clustering", video_count=embeddings.shape[0])
        raise InsufficientDataError(data_points=embeddings.shape[0], minimum_required=2)

    # Adjust num_clusters if needed
    original_num_clusters = num_clusters
    if embeddings.shape[0] < num_clusters:
        num_clusters = embeddings.shape[0]
        log.warning("Reducing cluster count due to insufficient samples",
                   original=original_num_clusters,
                   adjusted=num_clusters,
                   video_count=embeddings.shape[0])

    try:
        # Perform clustering
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
        labels = kmeans.fit_predict(embeddings)

        log.debug("KMeans clustering complete", inertia=kmeans.inertia_)

        # Build cluster mapping
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(i)

        # Ensure the keys are standard Python integers
        clusters = {int(k): v for k, v in clusters.items()}

        # Log cluster statistics
        cluster_sizes = {k: len(v) for k, v in clusters.items()}
        log.info("Clustering complete",
                 num_clusters=len(clusters),
                 cluster_sizes=cluster_sizes,
                 total_videos=embeddings.shape[0])

        return clusters

    except Exception as e:
        log.error("Clustering algorithm failed", error=str(e), algorithm="KMeans")
        raise ClusteringAlgorithmError(algorithm="KMeans", reason=str(e))