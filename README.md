# Perplexica Frontend

A simple Flask-based web frontend to interact with a [Perplexica]((https://github.com/ItzCrazyKns/Perplexica)) API instance. It allows users to submit queries, view results (including sources), and optionally send results to a [Karakeep](https://github.com/karakeep-app/karakeep) instance.

## Features

*   Simple web interface for Perplexica queries.
*   Displays formatted results and source links.
*   Optional integration to send results to Karakeep/Hoarder.
*   Basic user authentication.
*   Dark/Light mode based on browser preference.
*   Markdown rendering for Perplexica responses.

## Prerequisites

*   Docker
*   Docker Compose (usually included with Docker Desktop)
*   A running instance of the Perplexica backend API accessible from this frontend.
*   (Optional) A running instance of Karakeep if you want to use the "Send to Karakeep" feature.

## Configuration

1.  **Copy Environment File:**
    Create a `.env` file by copying the example:
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env` File:**
    Open the `.env` file in a text editor and configure the following variables:

    *   `FLASK_SECRET_KEY`: **Required.** A strong, random secret key for Flask session management. You can generate one using `python -c 'import os; print(os.urandom(24).hex())'`. **Login persistence will not work without this set correctly.**
    *   `ADMIN_USERNAME`: **Required.** The username for logging into the frontend.
    *   `ADMIN_PASSWORD`: **Required.** The password for logging into the frontend. **Change the default!**
    *   `PERPLEXICA_API_URL`: **Required.** The full URL to your Perplexica backend's `/api/search` endpoint (e.g., `http://your-perplexica-host:3000/api/search`).
    *   `PERPLEXICA_CHAT_PROVIDER`: **Required.** The provider name for the chat model configured in your Perplexica backend (e.g., `openai`, `ollama`, `gemini`). Check your Perplexica `/api/models` endpoint for available options.
    *   `PERPLEXICA_CHAT_NAME`: **Required.** The specific name of the chat model configured in your Perplexica backend (e.g., `gpt-4o-mini`, `llama3`). Check your Perplexica `/api/models` endpoint.
    *   `PERPLEXICA_EMBEDDING_PROVIDER`: **Required.** The provider name for the embedding model configured in your Perplexica backend.
    *   `PERPLEXICA_EMBEDDING_NAME`: **Required.** The specific name of the embedding model configured in your Perplexica backend.
    *   `PERPLEXICA_CUSTOM_OPENAI_BASE_URL` (Optional): If using a custom OpenAI-compatible endpoint with Perplexica, set its base URL here.
    *   `PERPLEXICA_CUSTOM_OPENAI_KEY` (Optional): If using a custom OpenAI-compatible endpoint with Perplexica, set its API key here.
    *   `KARAKEEP_API_URL` (Optional): The base API URL for your Karakeep/Hoarder instance (e.g., `http://your-hoarder-host/api/v1`). Required only if using the Karakeep integration.
    *   `KARAKEEP_API_KEY` (Optional): The API key generated within Karakeep/Hoarder. Required only if using the Karakeep integration.
    *   `KARAKEEP_LIST_NAME` (Optional): The exact name of the List within Karakeep/Hoarder where results should be sent. Required only if using the Karakeep integration.

## Running the Application

1.  **Navigate:** Open a terminal in the directory containing the `docker-compose.yaml` file.
2.  **Build and Start:** Run the following command:
    ```bash
    docker-compose up -d --build
    ```
    This will build the Docker image (if it doesn't exist or if changes were made) and start the service in the background.

## Accessing the Application

Once the container is running, you can access the frontend in your web browser at:

`http://localhost:25008`

(Or replace `localhost` with the IP address of your Docker host if necessary). You will be prompted to log in using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` you configured in the `.env` file.

## Stopping the Application

To stop the service, run:

```bash
docker-compose down
```
