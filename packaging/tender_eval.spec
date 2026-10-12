# PyInstaller spec for TenderEval.exe (desktop build: backend + static UI + in-process models +
# embedded Postgres in one process). Don't run this directly — use packaging\build.ps1, which
# builds the static UI first and runs PyInstaller from the right venv.
#
# One-directory bundle (dist\TenderEval\), not --onefile: a onefile exe would re-extract several
# hundred MB of OpenVINO/Postgres binaries to %TEMP% on every launch. Models are NOT bundled —
# they download into %LOCALAPPDATA%\TenderEval\models on first run (or `TenderEval.exe setup`,
# which the installer runs), because the compiled form is specific to each machine's GPU/NPU.

import importlib.metadata
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

_PACKAGING = os.path.abspath(SPECPATH)
_ROOT = os.path.dirname(_PACKAGING)

datas = [
    (os.path.join(_ROOT, 'frontend', 'out'), 'frontend'),
    (os.path.join(_ROOT, 'desktop', 'config.env.example'), 'desktop'),
]
binaries = []
hiddenimports = collect_submodules('pydantic_backend') + collect_submodules('desktop')

# Native packages whose DLLs/plugins are loaded dynamically (OpenVINO device plugins, pdfium,
# Postgres binaries) or whose submodules are imported lazily — static analysis misses these.
for package in (
    'openvino',
    'openvino_genai',
    'openvino_tokenizers',
    'pixeltable_pgserver',
    'pypdfium2',
    'pypdfium2_raw',
    'psycopg',
    'psycopg_binary',
    'psycopg_pool',
    'pystray',
    'uvicorn',
    'pydantic_ai',
    'googleapiclient',  # static Gmail/Drive discovery documents (JSON data files)
    'tiktoken_ext',
):
    try:
        d, b, h = collect_all(package)
    except Exception:  # noqa: BLE001 — optional package not installed
        continue
    datas += d
    binaries += b
    hiddenimports += h

# Logfire (observability for the hosted deployment) is left out of the desktop build: the backend
# imports `logfire_api`, which turns every logfire call into a no-op when logfire isn't present.
# Its dist-info must stay out too — it registers a pydantic plugin entry point that would make
# pydantic try to import the missing package.
_NOT_BUNDLED = ('logfire', 'pyinstaller', 'pyinstaller-hooks-contrib')

# Several dependencies (OpenTelemetry's entry-point-registered context, pydantic-ai,
# google-api-python-client) read their own package metadata at runtime — ship the dist-info of
# everything installed rather than chasing them one by one (it's a few hundred KB).
for dist in importlib.metadata.distributions():
    name = dist.metadata['Name']
    if name and name.lower() not in _NOT_BUNDLED:
        try:
            datas += copy_metadata(name)
        except Exception:  # noqa: BLE001
            pass


def _keep(entry):
    path = entry[0].replace('\\', '/')
    # pixeltable_pgserver ships Postgres 16 *and* 18; only 18 (its default) is used. Headers and
    # import libraries are build-time only.
    if '/pixeltable_pgserver/pginstall/' in path:
        return False
    if '/pginstall18/include/' in path or path.endswith('.lib'):
        return False
    return True


datas = [entry for entry in datas if _keep(entry)]
binaries = [entry for entry in binaries if _keep(entry)]

a = Analysis(
    [os.path.join(_PACKAGING, 'tender_eval_main.py')],
    pathex=[_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(_PACKAGING, 'hooks', 'rthook_dll_dirs.py')],
    excludes=['logfire', 'torch', 'torchvision', 'tensorflow', 'transformers', 'tkinter', 'matplotlib', 'IPython'],
    noarchive=False,
)

# googleapiclient ships ~590 static discovery documents (~100 MB), added by PyInstaller's own
# contrib hook during Analysis; only Gmail v1 and Drive v3 are used (ingestion/gmail.py, drive.py).
_DISCOVERY_DIR = 'googleapiclient/discovery_cache/documents/'


def _keep_bundled(entry):
    dest = entry[0].replace('\\', '/')
    return _DISCOVERY_DIR not in dest or dest.rsplit('/', 1)[-1] in ('gmail.v1.json', 'drive.v3.json')


a.datas = [entry for entry in a.datas if _keep_bundled(entry)]

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TenderEval',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # tray app; all output goes to %LOCALAPPDATA%\TenderEval\logs
    icon=os.path.join(_ROOT, 'frontend', 'src', 'app', 'favicon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='TenderEval',
)
