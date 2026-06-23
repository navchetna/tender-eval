FROM python:3.10-slim

# Set working directory inside the container
RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set home directory
ENV HOME=/home/user

# Create a non-root user
RUN useradd -m -s /bin/bash user && \
    mkdir -p $HOME && \
    chown -R user $HOME

# Set working directory
WORKDIR $HOME

# Install system dependencies, including those required for OpenCV (cv2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set PYTHONPATH to include the comps directory
ENV PYTHONPATH=$HOME/comps

ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN mkdir -p $HOME/comps && chown -R user:user $HOME/comps

COPY --chown=user:user comps/requirements.txt $HOME/comps/requirements.txt

# Switch to non-root user
USER user

# Install Python dependencies as the non-root user using --user flag
# This installs packages to ~/.local, which we'll add to PATH
RUN pip install --user --no-cache-dir --index-url "$PYTORCH_INDEX_URL" \
    torch \
    torchvision && \
    grep -Ev '^(torch|torchvision|triton)(==|[<>=!~])' comps/requirements.txt > /tmp/requirements-no-pytorch.txt && \
    pip install --user --no-cache-dir -r /tmp/requirements-no-pytorch.txt && \
    pip install --user bson && \
    pip install --user motor

USER root

# Copy the comps directory after dependency installation so app-only changes reuse cached packages.
COPY --chown=user:user comps $HOME/comps

USER user

# Install the editable package from comps/dataprep/marker as non-root user
# This replicates 'pip install -e .' for your custom changes
RUN cd $HOME/comps/dataprep/marker && \
    pip install --user -e .

ENV PATH="${PATH}:/home/user/.local/bin"

# Entrypoint fixes bind-mount ownership at container start so any host UID works
USER root
COPY --chmod=755 comps/entrypoint.sh /entrypoint.sh
USER user

EXPOSE 8000

ENV MONGO_URI=mongodb://localhost:27017
ENV DB_NAME=tender_eval
ENV GROQ_API_KEY=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

ENTRYPOINT ["/entrypoint.sh"]
# Run the FastAPI app with uvicorn
CMD ["uvicorn", "comps.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

