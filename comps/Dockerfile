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

# Copy the comps directory (assuming your app.py and requirements.txt are inside comps)
COPY comps $HOME/comps

# Change ownership of the copied directory to the non-root user for write access
RUN chown -R user:user $HOME/comps

# Install system dependencies, including those required for OpenCV (cv2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set PYTHONPATH to include the comps directory
ENV PYTHONPATH=$PYTHONPATH:$HOME/comps

# Switch to non-root user
USER user

# Install Python dependencies as the non-root user using --user flag
# This installs packages to ~/.local, which we'll add to PATH
RUN pip install --user --no-cache-dir -r comps/requirements.txt && \
    pip install --user bson && \
    pip install --user motor

# Install the editable package from comps/dataprep/marker as non-root user
# This replicates 'pip install -e .' for your custom changes
RUN cd $HOME/comps/dataprep/marker && \
    pip install --user -e .

ENV PATH="${PATH}:/home/user/.local/bin"


EXPOSE 8000

ENV MONGO_URI=mongodb://localhost:27017
ENV DB_NAME=tender_eval
ENV GROQ_API_KEY=

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "comps.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

