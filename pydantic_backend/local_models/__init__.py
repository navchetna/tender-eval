"""
In-process on-device models (`model_runtime='inprocess'`): OpenVINO GenAI pipelines loaded
straight into the backend process, replacing the OVMS (fast LLM) and llama.cpp + docling
(OCR parser) servers the LiteLLM deployment talks to over HTTP.

Each model is downloaded once from Hugging Face (pre-converted OpenVINO IR) into
`settings.models_dir`, compiled lazily on first use for its configured device (falling back to
GPU, then CPU, if that device is missing or rejects the model), and the compiled blob is cached
in `settings.ov_cache_dir` so later starts skip the expensive compile.
"""
