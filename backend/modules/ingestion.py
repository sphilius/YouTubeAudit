import zipfile
import json
from typing import List, Dict, Any
from backend.utils.logging_config import get_logger
from backend.exceptions import (
    IngestionError,
    TakeoutParseError,
    MissingWatchHistoryError,
    InvalidJSONError,
    EmptyDatasetError
)

log = get_logger(__name__)

def _parse_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Reads a simple JSON file containing a list of video entries."""
    log.debug("Parsing JSON file", file_path=file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            log.info("Successfully parsed JSON file", file_path=file_path, entries=len(data))
            return data
    except json.JSONDecodeError as e:
        log.error("Invalid JSON format", file_path=file_path, error=str(e))
        raise InvalidJSONError(filename=file_path, parse_error=str(e))
    except Exception as e:
        log.error("Failed to read JSON file", file_path=file_path, error=str(e))
        raise TakeoutParseError(reason=str(e), filename=file_path)

def _parse_zip_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts and parses the watch-history.json from a YouTube Takeout zip file.
    """
    log.debug("Parsing ZIP file", file_path=file_path)
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # Find the watch history file in the zip archive
            all_files = z.namelist()
            log.debug("Examining ZIP contents", file_count=len(all_files))

            watch_history_files = [f for f in all_files if 'watch-history.json' in f]
            if not watch_history_files:
                log.error("watch-history.json not found in ZIP", file_path=file_path, files_in_zip=all_files[:10])
                raise MissingWatchHistoryError()

            watch_history_file = watch_history_files[0]
            log.info("Found watch history file", filename=watch_history_file)

            # Read the found file
            with z.open(watch_history_file) as f:
                try:
                    data = json.load(f)
                    log.info("Successfully parsed ZIP file", file_path=file_path, entries=len(data))
                    return data
                except json.JSONDecodeError as e:
                    log.error("Invalid JSON in ZIP", filename=watch_history_file, error=str(e))
                    raise InvalidJSONError(filename=watch_history_file, parse_error=str(e))
    except zipfile.BadZipFile as e:
        log.error("Invalid ZIP file", file_path=file_path, error=str(e))
        raise TakeoutParseError(reason="Invalid or corrupted ZIP file", filename=file_path)
    except MissingWatchHistoryError:
        raise
    except InvalidJSONError:
        raise
    except Exception as e:
        log.error("Failed to parse ZIP file", file_path=file_path, error=str(e))
        raise TakeoutParseError(reason=str(e), filename=file_path)

def parse_takeout_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses a YouTube Takeout file (either .zip or .json) to extract watch history.

    Args:
        file_path: The path to the Takeout file.

    Returns:
        A list of dictionaries, where each dictionary represents a watched video.

    Raises:
        IngestionError: If file parsing fails
        EmptyDatasetError: If no valid video data is found
    """
    log.info("Starting Takeout file ingestion", file_path=file_path)

    if file_path.endswith('.zip'):
        data = _parse_zip_file(file_path)
    elif file_path.endswith('.json'):
        data = _parse_json_file(file_path)
    else:
        log.error("Unsupported file type", file_path=file_path)
        raise TakeoutParseError(
            reason="Unsupported file type. Only .zip and .json files are supported.",
            filename=file_path
        )

    # Validate that we have data
    if not data or len(data) == 0:
        log.error("Empty dataset after parsing", file_path=file_path)
        raise EmptyDatasetError()

    log.info("Ingestion complete", file_path=file_path, video_count=len(data))
    return data