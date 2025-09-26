import zipfile
import json
from typing import List, Dict, Any

def _parse_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Reads a simple JSON file containing a list of video entries."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _parse_zip_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts and parses the watch-history.json from a YouTube Takeout zip file.
    """
    with zipfile.ZipFile(file_path, 'r') as z:
        # Find the watch history file in the zip archive
        watch_history_files = [f for f in z.namelist() if 'watch-history.json' in f]
        if not watch_history_files:
            raise FileNotFoundError("Could not find 'watch-history.json' in the provided zip file.")

        # Read the found file
        with z.open(watch_history_files[0]) as f:
            data = json.load(f)
            return data

def parse_takeout_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses a YouTube Takeout file (either .zip or .json) to extract watch history.

    Args:
        file_path: The path to the Takeout file.

    Returns:
        A list of dictionaries, where each dictionary represents a watched video.
    """
    if file_path.endswith('.zip'):
        return _parse_zip_file(file_path)
    elif file_path.endswith('.json'):
        return _parse_json_file(file_path)
    else:
        raise ValueError("Unsupported file type. Please upload a .zip or .json file.")