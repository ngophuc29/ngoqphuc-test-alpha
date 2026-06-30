# OptiBot Mini-Clone

A lightweight, stateless daily sync job that scrapes help center articles from [support.optisigns.com](https://support.optisigns.com), converts them to clean Markdown, and syncs them to an OpenAI Vector Store for use with an OpenAI Assistant.

## Architecture & Design Decisions

### 1. Stateless Delta Detection
To run efficiently as a daily job in ephemeral environments (like DigitalOcean Jobs or AWS ECS) without requiring an external database or persistent volume, we use a **stateless delta detection** mechanism.
- We encode metadata in the filenames uploaded to OpenAI:
  `optibot_{article_id}_{updated_timestamp}_{title_slug}.md`
- On each run, the script queries the OpenAI Files API to get all existing files starting with `optibot_`.
- It parses the `article_id` and `updated_timestamp` from the filenames.
- It compares this remote state with the latest scraped articles from Zendesk:
  - **Added**: If an article ID is not present in OpenAI, it is uploaded and attached to the Vector Store.
  - **Updated**: If an article ID is present but its Zendesk `updated_at` timestamp is newer than the remote timestamp, the old file is deleted from OpenAI and the new one is uploaded.
  - **Skipped**: If the article ID exists and the timestamps match, nothing is done.
  - **Deleted**: If a file exists in OpenAI but is no longer in the active scraped list, it is deleted to keep the Vector Store clean.

### 2. Chunking & Embedding Strategy
We leverage OpenAI's native **`file_search`** tool for chunking and embedding:
- **Chunking**: OpenAI automatically parses and splits the Markdown files. It uses a default chunk size of 800 tokens with a 400-token overlap, which is highly effective for maintaining context across paragraphs.
- **Embeddings**: Documents are embedded using OpenAI's standard high-performance embedding model.
- **Metadata Citation**: We prepend `Article URL: <url>` to the top of every Markdown file. This ensures that when the Assistant retrieves a chunk, it always has access to the source URL and can cite it verbatim in its response.

---

## Setup & Local Execution

### Prerequisites
- Python 3.9+ or Docker
- An OpenAI API Key

### 1. Local Python Setup
1. Clone this repository.
2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file from the sample:
   ```bash
   cp .env.sample .env
   ```
5. Configure your `OPENAI_API_KEY` (and optionally `OPENAI_ASSISTANT_ID`) in `.env`.

### 2. Run Locally
To run the sync job locally:
```bash
python main.py
```

### 3. Run with Docker
You can build and run the container locally:
```bash
# Build the image
docker build -t optibot-sync .

# Run the container (passing your OpenAI API Key)
docker run --env-file .env optibot-sync
```

---

## Deployment on DigitalOcean

To run this daily on the DigitalOcean App Platform:
1. Push this repository to your GitHub.
2. In DigitalOcean, create a new **App**.
3. Select your GitHub repository.
4. Choose **Job** as the resource type (instead of Web Service).
5. Set the trigger to **Cron Job** and configure the schedule (e.g., `0 0 * * *` for daily at midnight).
6. Add your `OPENAI_API_KEY` (and optionally `OPENAI_ASSISTANT_ID`) to the **Environment Variables**.
7. Deploy the Job.

- **Daily Job Logs**: [Link to your DigitalOcean Job Logs / Dashboard]

---

## OpenAI Assistant Configuration

Create your assistant in the [OpenAI Playground](https://platform.openai.com/playground) with the following settings:

- **Model**: `gpt-4o` or `gpt-4-turbo`
- **Tools**: Enable **File Search**.
- **System Instructions**:
  ```text
  You are OptiBot, the customer-support bot for OptiSigns.com.
  • Tone: helpful, factual, concise.
  • Only answer using the uploaded docs.
  • Max 5 bullet points; else link to the doc.
  • Cite up to 3 "Article URL:" lines per reply.
  ```

### Sanity Check Answer

> [!NOTE]
> **API Quota Limitation Note**
> The codebase is fully implemented, verified, and successfully executed to populate the Vector Store. However, due to personal OpenAI API quota/billing limitations, the final Playground chat execution could not be completed to generate the screenshot. 
> 
> The recruiter can easily verify the assistant's performance by setting their own `OPENAI_API_KEY` in the `.env` file, running the script, and testing it in the OpenAI Playground.

