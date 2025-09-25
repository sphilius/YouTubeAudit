# Jules Tasks / To Do List

## Feature Tasks

- [ ] **Endpoint: POST /run-analysis**
  Accepts: Takeout upload or OAuth token
  Returns: a job id
  Starts asynchronous pipeline: ingestion → enrichment → embeddings → clustering → scoring.

- [ ] **Status / Progress API**
  `GET /status/{job_id}` returning a structured state machine for user feedback (e.g. “INGESTING”, “EMBEDDING”, “CLUSTERING”, “DONE”)

- [ ] **Results API**
  `GET /results/{job_id}` returns JSON object: clusters, video lists, key metrics.

- [ ] **Frontend Dashboard Page**
  A web page (React/Vue) or Streamlit app that displays cluster summaries, top videos per cluster, scores.

- [ ] **Labeling UI**
  A UI component that shows ambiguous videos for cluster assignment and allows manual override.

- [ ] **Classifier Retrain Endpoint**
  `POST /retrain` that uses labeled data to retrain and reassign clusters across the dataset.

- [ ] **Unit Tests & Fixtures**
  Add minimal tests for ingestion, embedding, clustering modules. Provide a small sample Takeout export as a fixture.

- [ ] **Rate limiting & quota guards**
  Add protection so embedding and API usage can’t spin into infinite loops or runaway costs.

- [ ] **Deployment Setup**
  Dockerfile + compose file, production server scaffold, health-check, logging setup.

- [ ] **Jules Self-Maintenance Task**
  Periodically check `JULES_TASKS.md` and propose new tasks (e.g. linting, refactoring).