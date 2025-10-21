from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional
import numpy as np
from backend.utils.logging_config import get_logger
from backend.config import get_config
from backend.exceptions import (
    EmbeddingError,
    ModelLoadError,
    VectorStoreError,
    DimensionMismatchError
)

log = get_logger(__name__)
config = get_config()

# Conditional import for FAISS
try:
    import faiss
except ImportError:
    faiss = None
    log.warning("FAISS not available - vector store functionality will be limited")

# Conditional import for sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    log.warning("sentence-transformers not available - will use random embeddings")

# Global model cache (singleton pattern)
_embedding_model: Optional[SentenceTransformer] = None

class VectorStore(ABC):
    """Abstract base class for a vector store."""

    @abstractmethod
    def upsert(self, vectors: np.ndarray, ids: List[str]):
        """Upsert vectors into the store."""
        pass

    @abstractmethod
    def query(self, vector: np.ndarray, k: int) -> List[Any]:
        """Query the store for the k nearest neighbors."""
        pass

class FaissVectorStore(VectorStore):
    """A local vector store implementation using FAISS."""

    def __init__(self, dimension: int = 768):
        if not faiss:
            log.error("FAISS not installed")
            raise ModelLoadError(
                model_name="FAISS",
                reason="FAISS is not installed. Please run 'pip install faiss-cpu' to use it."
            )

        log.info("Initializing FAISS vector store", dimension=dimension)
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.id_map = []
        log.debug("FAISS vector store initialized successfully")

    def upsert(self, vectors: np.ndarray, ids: List[str]):
        """Adds vectors to the index."""
        log.debug("Upserting vectors to FAISS", vector_count=len(vectors), dimension=vectors.shape[1])

        if vectors.shape[1] != self.dimension:
            log.error("Dimension mismatch", expected=self.dimension, actual=vectors.shape[1])
            raise DimensionMismatchError(expected=self.dimension, actual=vectors.shape[1])

        try:
            self.index.add(vectors.astype('float32'))
            self.id_map.extend(ids)
            log.info("Vectors upserted successfully", count=len(vectors), total_vectors=len(self.id_map))
        except Exception as e:
            log.error("Failed to upsert vectors", error=str(e))
            raise VectorStoreError(operation="upsert", reason=str(e))

    def query(self, vector: np.ndarray, k: int) -> List[Any]:
        """
        Searches the index for the k nearest neighbors.

        Returns:
            A list of tuples containing (id, distance).
        """
        log.debug("Querying FAISS index", k=k)

        try:
            distances, indices = self.index.search(vector.astype('float32'), k)
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1:
                    results.append((self.id_map[idx], float(distances[0][i])))

            log.debug("Query completed", results_found=len(results))
            return results
        except Exception as e:
            log.error("Failed to query FAISS index", error=str(e))
            raise VectorStoreError(operation="query", reason=str(e))

def get_embedding_model() -> SentenceTransformer:
    """
    Get or load the sentence transformer model (singleton).

    Returns:
        SentenceTransformer model

    Raises:
        ModelLoadError: If model fails to load
    """
    global _embedding_model

    if _embedding_model is None:
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ModelLoadError(
                model_name="sentence-transformers",
                reason="sentence-transformers library not installed. Install with: pip install sentence-transformers"
            )

        model_name = config.embedding_model_name
        log.info("Loading sentence transformer model", model_name=model_name)

        try:
            _embedding_model = SentenceTransformer(model_name)
            log.info(
                "Sentence transformer model loaded successfully",
                model_name=model_name,
                max_seq_length=_embedding_model.max_seq_length,
                embedding_dimension=_embedding_model.get_sentence_embedding_dimension()
            )
        except Exception as e:
            log.error("Failed to load sentence transformer model", model_name=model_name, error=str(e))
            raise ModelLoadError(model_name=model_name, reason=str(e))

    return _embedding_model


def create_text_from_metadata(video: Dict[str, Any]) -> str:
    """
    Create a rich text representation from video metadata.

    Combines title, description, tags, and channel info into a single string
    for embedding generation.

    Args:
        video: Video metadata dictionary from YouTube API

    Returns:
        Text string for embedding
    """
    parts = []

    # Extract from YouTube API response structure
    snippet = video.get('snippet', {})
    statistics = video.get('statistics', {})

    # Title (most important)
    title = snippet.get('title', '')
    if title:
        parts.append(f"Title: {title}")

    # Description
    description = snippet.get('description', '')
    if description:
        # Limit description length to avoid overwhelming the model
        description = description[:500]
        parts.append(f"Description: {description}")

    # Tags
    tags = snippet.get('tags', [])
    if tags:
        tags_str = ', '.join(tags[:10])  # Limit to first 10 tags
        parts.append(f"Tags: {tags_str}")

    # Channel
    channel_title = snippet.get('channelTitle', '')
    if channel_title:
        parts.append(f"Channel: {channel_title}")

    # Category (if available)
    category = snippet.get('categoryId', '')
    if category:
        parts.append(f"Category ID: {category}")

    # Combine all parts
    text = ' | '.join(parts)

    # Fallback if no meaningful content
    if not text.strip():
        video_id = video.get('id', 'unknown')
        text = f"Video {video_id}"

    return text


def get_video_embeddings(video_metadata: List[Dict[str, Any]]) -> np.ndarray:
    """
    Generates semantic embeddings for a list of video metadata using sentence-transformers.

    This function uses a pre-trained transformer model to create dense vector
    representations of video content based on titles, descriptions, tags, etc.

    Features:
    - Real semantic embeddings (not random!)
    - Batch processing for efficiency
    - Progress tracking
    - Automatic model caching

    Args:
        video_metadata: A list of dictionaries, each containing video metadata
                       from YouTube API (with 'snippet', 'statistics', etc.)

    Returns:
        A numpy array of embeddings with shape (num_videos, embedding_dim)
        Default model 'all-MiniLM-L6-v2' produces 384-dimensional embeddings

    Raises:
        EmbeddingError: If embedding generation fails
        ModelLoadError: If model cannot be loaded

    Example:
        >>> metadata = [{"snippet": {"title": "...", "description": "..."}}]
        >>> embeddings = get_video_embeddings(metadata)
        >>> print(embeddings.shape)  # (1, 384)
    """
    if not video_metadata:
        log.warning("get_video_embeddings called with empty metadata list")
        return np.array([]).reshape(0, config.embedding_dimension)

    log.info(
        "Starting embedding generation",
        video_count=len(video_metadata),
        model_name=config.embedding_model_name
    )

    try:
        # Load or get cached model
        model = get_embedding_model()

        # Create text representations from video metadata
        log.debug("Creating text representations from metadata")
        texts = []
        for i, video in enumerate(video_metadata):
            text = create_text_from_metadata(video)
            texts.append(text)

            if (i + 1) % 100 == 0:
                log.debug("Text creation progress", processed=i+1, total=len(video_metadata))

        log.info("Text representations created", count=len(texts))

        # Generate embeddings in batches
        log.info(
            "Generating embeddings",
            batch_size=config.embedding_batch_size,
            batches=len(texts) // config.embedding_batch_size + 1
        )

        embeddings = model.encode(
            texts,
            batch_size=config.embedding_batch_size,
            show_progress_bar=False,  # We log progress ourselves
            convert_to_numpy=True,
            normalize_embeddings=True  # L2 normalization for better similarity
        )

        # Ensure correct dtype
        embeddings = embeddings.astype('float32')

        log.info(
            "Embedding generation complete",
            video_count=len(video_metadata),
            embedding_dimension=embeddings.shape[1],
            embeddings_shape=embeddings.shape,
            model_name=config.embedding_model_name
        )

        # Verify dimensions match config
        expected_dim = model.get_sentence_embedding_dimension()
        if embeddings.shape[1] != expected_dim:
            log.warning(
                "Embedding dimension mismatch",
                expected=expected_dim,
                actual=embeddings.shape[1]
            )

        return embeddings

    except ModelLoadError:
        # Re-raise model loading errors
        raise

    except Exception as e:
        log.error(
            "Embedding generation failed",
            error=str(e),
            video_count=len(video_metadata),
            exc_info=True
        )
        raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")