# YouTube Topic Audit Engine

This project is a YouTube Topic Audit engine. It ingests a user’s YouTube Takeout data (`watch-history.json`), enriches it with video metadata, generates embeddings for video titles, clusters the content into thematic topics, and presents the findings in an interactive dashboard.

The goal is to produce an interactive dashboard that helps users discover and analyze their viewing patterns and identify their strongest thematic niches.

## Architecture

The application is built using a two-service architecture:

*   **Backend**: A lightweight Flask server responsible for all heavy data processing. It exposes a single `/analyze` endpoint that accepts a YouTube Takeout file and returns the full analysis as a JSON object.
*   **Frontend**: A Streamlit application that provides the user interface. It handles file uploads, sends the data to the backend, and visualizes the results received from the backend.

This separation ensures the UI remains responsive and stable, as all computationally intensive tasks are isolated in the backend service.

## Prerequisites

*   Docker
*   Docker Compose
*   A Google API Key with the YouTube Data API v3 enabled.

## How to Run

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create an environment file:**
    Create a file named `.env` in the root of the project and add the following variables. This file is used to securely manage your API keys and configuration.

    ```env
    # A static bearer token to secure the backend API
    API_BEARER_TOKEN="a-secure-static-token"

    # Your Google API Key for fetching video metadata
    GOOGLE_API_KEY="your-google-api-key-here"
    ```
    *Note: The `API_BEARER_TOKEN` can be any secret string you choose. The frontend and backend will use it to communicate.*

3.  **Build and run the services using Docker Compose:**
    From the root directory, run the following command:
    ```bash
    docker-compose up --build
    ```
    This will build the Docker images for the backend and frontend services and start them.

4.  **Access the application:**
    Once the containers are running, open your web browser and navigate to:
    [http://localhost:8501](http://localhost:8501)

5.  **Use the application:**
    *   The application will automatically use the `GOOGLE_API_KEY` from your `.env` file.
    *   Upload your YouTube Takeout `.zip` file or just the `watch-history.json` file.
    *   Click the "Analyze Watch History" button.
    *   The analysis will run on the backend. This may take several minutes depending on the size of your watch history.
    *   Once complete, the results will be displayed on the dashboard.

## Local Development (Without Docker)

If you prefer to run the services locally without Docker:

1.  **Set up a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set environment variables:**
    ```bash
    export FLASK_APP=main.py
    export API_BEARER_TOKEN="a-secure-static-token"
    export GOOGLE_API_KEY="your-google-api-key-here"
    ```

4.  **Run the backend server:**
    Open a terminal and run:
    ```bash
    cd backend
    flask run --host=0.0.0.0 --port=8000
    ```

5.  **Run the frontend application:**
    Open a *second* terminal and run:
    ```bash
    cd frontend
    streamlit run app.py
    ```
    The Streamlit app will be available at `http://localhost:8501`. The `API_URL` in `frontend/app.py` may need to be changed from `http://backend:8000` to `http://localhost:8000` for local development if you are not using the Docker environment.