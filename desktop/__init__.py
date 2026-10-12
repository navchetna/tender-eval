"""
Single-process Windows desktop build of Tender Evaluation (`TenderEval.exe`).

One process hosts everything the Docker/WSL deployment spreads over seven services: the FastAPI
backend, the statically exported Next.js UI, on-device models (OpenVINO GenAI, in-process), and
an embedded PostgreSQL (pixeltable-pgserver: bundled binaries, private data dir, random
localhost port, started/stopped with the app). See desktop/launcher.py.
"""
