# YouTube Topic Audit Engine

This project is a YouTube Topic Audit engine. It ingests a user’s YouTube data (subscriptions, watch history, playlists), enriches that with metadata, embeds textual features using an LLM (Gemini embeddings), clusters content into “topic themes,” and scores each theme by metrics like weight, demand, competition, and opportunity (“impact” I-score).

The goal is to produce an interactive dashboard + labeling UI + report that helps content creators discover their strongest thematic niches.