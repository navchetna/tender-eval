# Use a lightweight Python base image
FROM python:3.10-slim

# Set working directory inside the container
RUN apt-get update && apt-get upgrade -y && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

ENV HOME=/home/user

RUN useradd -m -s /bin/bash user && \
  mkdir -p $HOME && \
  chown -R user $HOME

WORKDIR $HOME

# copy just relevant parts
COPY comps $HOME/comps

WORKDIR $HOME

ENV PYTHONPATH=$PYTHONPATH:$HOME/user/comps

USER user

# Copy requirements.txt and install dependencies
RUN pip install --no-cache-dir -r comps/requirements.txt


# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI app with uvicorn
CMD ["python3", "app.py", "api"]
