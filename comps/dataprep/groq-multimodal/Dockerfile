FROM python:3.11-slim

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    default-jre \
    libgl1-mesa-glx \
    libjemalloc-dev \
    libreoffice \
    poppler-utils \
    tesseract-ocr

RUN useradd -m -s /bin/bash user && \
    mkdir -p /home/user && \
    chown -R user /home/user/

USER user

COPY comps /home/user/comps

RUN pip install -r /home/user/comps/dataprep/groq-multimodal/requirements.txt

ENV PYTHONPATH=/home/user

WORKDIR /home/user/comps/dataprep/groq-multimodal

EXPOSE 8000

CMD ["python", "main.py"]
