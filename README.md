# Tender Evaluation

Purpose: Large Companies set up tenders for the procurement of infrastructure needed by them. In order to reduce bias and select the best bid offered by other companies a streamlined system needs to be implemented.

This would require the comparison of the requirements made in the tender to the proposal by the bid. This would determine the degree of technical compliance. Likewise the price needs to be evaluated to ensure the most cost effective solution is selected.

Thus we implemented a solution to this problem by utilizing pdf parsing coupled with a LLM to give an explainable solution by parsing the tender pdf to create a tree structure along with a file containing a table of contents. We allowed the LLM to select the elements on the TOC that best match the technical compliance and pricing.

We then search the tree to find those tables and convert them to pandas dataframe. This is saved to an excel file for reference and explainability. This process is repeated for the bidder file whose relevant information is condensed into an excel file.

We cross examine the tender’s file with each bidder to take the relevant rows and package them into a json file which can be read by the LLM to compare between bidders and explain why some were selected and why some were not.

## Docker Installation

The Docker Compose setup is in `install/docker/docker-compose.yaml`. It builds the local application components from this repository instead of pulling prebuilt backend, UI, or Groq service images:

- `backend`: built from `comps/Dockerfile`
- `ui`: built from `ui/install/Dockerfile`
- `groq-service`: built from `comps/dataprep/groq-multimodal/Dockerfile`
- `mongodb`: pulled from the public `mongo` image

### Prerequisites

- Docker Engine with Docker Compose v2
- Enough free Docker storage for the backend image and Python dependencies
- A configured `install/docker/env.sh` file

The backend Dockerfile installs CPU-only PyTorch wheels before installing the rest of the Python dependencies. This avoids pulling CUDA PyTorch packages during the backend build.

### Configure Environment

Review `install/docker/env.sh` before starting the stack. At minimum it should export:

```bash
export MONGO_URI=mongodb://agents:agents@mongodb:27017/?authSource=admin
export DB_NAME=tender_eval
export GROQ_API_KEY=<your-groq-api-key>
```

If you use a corporate proxy, also export the relevant proxy variables before running Compose.

### Build And Run

From the repository root:

```bash
cd tender-eval
mkdir -p out
chmod 777 out
set -a
source install/docker/env.sh
set +a
docker compose -f install/docker/docker-compose.yaml up -d --build --force-recreate
```

The `--build` flag forces Compose to build the local services from their Dockerfiles. The `--force-recreate` flag recreates containers so changes to images, ports, volumes, or environment variables are applied.

The backend writes generated parser artifacts to the repository-level `out/` directory, mounted into the container as `/home/user/out`. The backend image includes an entrypoint that sets `out/` to `777` at container startup, so the directory works regardless of which host user ID owns it. The repository includes `out/.gitkeep` so new clones have the expected directory, while generated files remain ignored by Git.

### Service URLs

After the stack starts, use these local URLs:

```text
UI:           http://localhost:5009
Backend docs: http://localhost:8001/docs
Backend API:  http://localhost:8001
Groq service: http://localhost:5099
MongoDB:      localhost:27018
```

The backend is published on host port `8001` because port `8000` is commonly used by other local services.

### Verify The Deployment

```bash
set -a
source install/docker/env.sh
set +a
docker compose -f install/docker/docker-compose.yaml ps
curl -sS http://localhost:8001/projects
curl -I http://localhost:5009
```

`GET /projects` should return JSON, such as `[]` on a fresh database.

### Stop The Stack

```bash
docker compose -f install/docker/docker-compose.yaml down
```

To remove local MongoDB data and generated Docker volumes as well, add `--volumes`.

### Troubleshooting

If the backend build fails with `No space left on device`, check Docker storage usage:

```bash
docker system df
```

You can remove unused Docker build cache with:

```bash
docker builder prune
```

For a more aggressive cleanup of unused Docker objects, review what is safe to delete in your environment before running:

```bash
docker system prune -af
```

If the backend cannot connect to MongoDB or returns authentication errors, confirm `MONGO_URI` includes the `agents` credentials and `authSource=admin` as shown above.

If uploading a PDF fails with `PermissionError: [Errno 13] Permission denied: 'out/...'`, fix the host-side output directory and recreate the backend container:

```bash
mkdir -p out
chmod 777 out
set -a
source install/docker/env.sh
set +a
docker compose -f install/docker/docker-compose.yaml up -d --no-build --force-recreate backend ui
```

