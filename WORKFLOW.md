

## ⚙️ How It Works: An Architectural Overview

The Smart Meeting Assistant is an AI-powered system designed to transform raw meeting recordings into structured, actionable knowledge. The entire process follows a logical data pipeline, managed by a user-friendly web interface built with Streamlit.

### The Core Workflow: From Audio to Insight

The application's workflow can be broken down into five main steps:

1.  **File Upload & Pre-processing (`main.py` & `utils.py`)**
    - A user uploads a meeting recording (audio or video) via the web interface.
    - If the file is a video, the system uses **FFmpeg** to extract the audio into a standard `.wav` format, ensuring compatibility with the next stage.

2.  **AI Transcription (`ai_services.py`)**
    - The processed audio file is sent to the **OpenAI Whisper API**.
    - Whisper transcribes the speech into text, automatically detecting the language and providing a detailed transcript.

3.  **Multi-faceted AI Analysis (`ai_services.py`)**
    This is where the core intelligence lies. The transcript is processed in parallel by three different AI models:
    - **Content & Action Analysis (GPT-4o)**: The transcript is sent to **GPT-4o** with a detailed system prompt. GPT-4o analyzes the text to:
        - Generate an executive summary, key decisions, and a list of participants.
        - Use **Function Calling** to automatically trigger the creation of calendar events and tasks within the application.
    - **Visual Synthesis (DALL-E 3)**: The summary from GPT-4o is used to create a prompt for **DALL-E 3**, which generates a professional, infographic-style visual summary of the meeting.
    - **Semantic Indexing (Embeddings API)**: The transcript and summary are sent to the **OpenAI Embeddings API**, which converts the text into a numerical vector (embedding). This vector captures the semantic meaning of the meeting and is crucial for searching.

4.  **Data Persistence (`database.py`)**
    - All the generated data—the transcript, summary, decisions, action items, visual summary URL, and the semantic embedding—is saved into a relational **SQLite database**.
    - The database uses separate, linked tables to store meetings, calendar events, and tasks, ensuring data is organized and easy to manage.

5.  **Retrieval & Interaction (`main.py`)**
    - Users can access the processed information through various pages:
        - **Dashboard**: Shows key statistics and a list of recent meetings.
        - **Calendar & Tasks**: Displays all events and tasks created by the AI.
        - **Search & Analytics**: Allows users to perform a powerful **semantic search**. When a user enters a query, it's converted into an embedding and compared against the embeddings of all stored meetings to find the most conceptually similar results. This page also supports cross-language search.

### Component Roles

-   **`main.py`** - The "face" of the application. Builds the Streamlit user interface, manages page navigation, and orchestrates the overall workflow.
-   **`ai_services.py`** - The "brain" of the system. Handles all communication with the OpenAI and Google Translate APIs and contains the function-calling logic.
-   **`database.py`** - The "memory" of the application. Responsible for all data storage, retrieval, and complex querying in the SQLite database.
-   **`utils.py`** - The "toolbox." Contains helper functions for file handling, data formatting, and reusable UI components.
-   **`test_meeting_assistant.py`** - The "quality control" department. Contains unit and integration tests to ensure the core components work reliably.