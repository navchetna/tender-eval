"""PyInstaller runtime hook: register every bundled folder that holds DLLs with the Windows
loader before any native extension is imported.

openvino_genai / openvino_tokenizers DLLs depend on openvino.dll and tbb12.dll, which live in a
sibling package folder (openvino/libs/). Windows only resolves dependent DLLs from the loading
DLL's own folder, the exe folder, System32 and PATH — not from arbitrary sibling folders inside
the bundle — so without this the import fails with "Cannot load library ...: 126" even though
every file is present. OpenVINO's device plugins (CPU/GPU/NPU) are loaded the same way, by name,
at runtime.
"""
import os
import sys

if sys.platform == 'win32':
    _base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    for _root, _dirs, _files in os.walk(_base):
        # pixeltable_pgserver's Postgres binaries run as their own processes; registering them
        # would only risk shadowing the bundle's own libssl/libcrypto with Postgres' copies.
        if 'pginstall' in _root:
            continue
        if any(name.lower().endswith('.dll') for name in _files):
            try:
                os.add_dll_directory(_root)
            except (OSError, AttributeError):
                pass
