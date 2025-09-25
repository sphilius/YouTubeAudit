from typing import List, Dict, Any
import numpy as np
from sklearn.cluster import KMeans

def cluster_videos(embeddings: np.ndarray, num_clusters: int = 10) -> Dict[int, List[int]]:
    """
    Clusters video embeddings into a specified number of clusters.

    Args:
        embeddings: A numpy array of video embeddings.
        num_clusters: The number of clusters to create.

    Returns:
        A dictionary mapping cluster ID to a list of video indices in that cluster.
    """
    # Placeholder implementation using KMeans
    print(f"Clustering {embeddings.shape[0]} videos into {num_clusters} clusters...")
    if embeddings.shape[0] < num_clusters:
        print("Warning: Number of samples is less than number of clusters. Reducing clusters.")
        num_clusters = embeddings.shape[0]

    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(embeddings)

    clusters = {}
    for i, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(i)

    # Ensure the keys are standard Python integers
    return {int(k): v for k, v in clusters.items()}