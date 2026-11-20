# Deployment

## Docker Compose on one machine

From MultiAgentSLR, copy .env.example to .env and supply the desired provider settings. For Ollama on the host, the Compose default endpoint is http://host.docker.internal:11434. Leave OLLAMA_BASE_URL blank to use that default or specify a reachable endpoint. The chosen model must already be pulled. A local development URL such as localhost:11434 refers to the application container when used in Compose.

    docker compose config --quiet
    docker compose up --build -d --wait app
    docker compose ps
    docker compose exec app python -m slr.health
    docker compose --profile tests run --rm --build tests

Open http://127.0.0.1:8501. The exposed host port can be changed with SLR_HOST_PORT. The named review_data volume stores SQLite, cached responses and experiment logs under /app/data. The health command checks Streamlit and database write access. Restart the app and verify that a saved review can be selected to check persistence. Back up /app/data according to your team's retention policy. Keep the local port bound to loopback unless you explicitly deploy behind authenticated HTTPS.

The test container runs controlled tests by default. To call live services from a test container, explicitly pass provider credentials and reachable URLs using Docker environment settings and run pytest with the live marker and SLR_RUN_LIVE=1. The live suite checks endpoints separately from the controlled tests.

## Render blueprint

The included [render.yaml](render.yaml) describes a single Docker Web Service with a persistent disk and Streamlit's HTTP health endpoint. Use a plan that supports persistent disks. Import this folder as a standalone repository, or set the Blueprint path to MultiAgentSLR/render.yaml and adjust dockerfilePath and dockerContext to the same folder relative to the repository root. See [Blueprint YAML reference](https://render.com/docs/blueprint-spec) and [persistent disk documentation](https://render.com/docs/disks).

1. Create a Blueprint for the repository and review the proposed resources before applying it.
2. Set GROQ_API_KEY, a strong SLR_ACCESS_TOKEN and the available source credentials as secret environment variables. Optional source variables can be left unset. This configuration uses Groq. If you operate an Ollama endpoint separately, configure its URL and chosen model before selecting Ollama.
3. Wait for a successful build and a healthy HTTP check. Open the Render URL over HTTPS, authenticate, and start a small review. Record statuses for each scientific source, then verify a resume after restart and report exports.
4. Run live smoke tests with credentials in the deployment environment and inspect their actual results. Keep the app to one instance with its persistent SQLite disk. Protect the access token, review text and exports.

The Blueprint is a deployment configuration. No cloud instance was provisioned by this project delivery.
