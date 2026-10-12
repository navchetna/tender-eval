"""
TenderEval.exe entry point.

    TenderEval.exe          start the app (tray icon + browser UI), or focus the running one
    TenderEval.exe setup    download the on-device models and warm their compile cache, then
                            exit — the installer's post-install step

Startup order: settings → embedded Postgres → schema init + admin bootstrap → uvicorn serving
the API under /api and the static UI everywhere else, on 127.0.0.1 only → browser → model
preload in the background (first run downloads ~3.5 GB; later runs load from the compile cache
in seconds). Everything user-writable lives under %LOCALAPPDATA%\\TenderEval (override with
TENDER_EVAL_HOME): config.env, pgdata/, models/, ov_cache/, logs/, .secrets/.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import logging.handlers
import os
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

APP_NAME = 'TenderEval'
APP_TITLE = 'Tender Evaluation'
DEFAULT_PORT = 8011

log = logging.getLogger('tender_eval.desktop')


# --------------------------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------------------------

def home_dir() -> Path:
    base = os.environ.get('TENDER_EVAL_HOME') or Path(os.environ.get('LOCALAPPDATA') or Path.home()) / APP_NAME
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundle_dir() -> Path:
    """Read-only bundled files: the PyInstaller `_internal` dir when frozen, else the repo root."""
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def frontend_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return bundle_dir() / 'frontend'
    return bundle_dir() / 'frontend' / 'out'


# --------------------------------------------------------------------------------------------
# Process setup
# --------------------------------------------------------------------------------------------

def setup_logging(home: Path) -> Path:
    logs = home / 'logs'
    logs.mkdir(exist_ok=True)
    log_file = logs / 'tender-eval.log'
    # A windowed (no-console) exe has no stdout/stderr; anything printed — uvicorn, logfire's
    # console exporter, OpenVINO plugin messages — goes to a sibling file instead of crashing.
    if sys.stdout is None or sys.stderr is None:
        console = open(logs / 'console.log', 'a', buffering=1, encoding='utf-8', errors='replace')  # noqa: SIM115
        sys.stdout = sys.stdout or console
        sys.stderr = sys.stderr or console
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stderr)])
    return log_file


def load_config(home: Path) -> bool:
    """Load config.env into the environment (real environment variables win). Returns True if
    this is the first run, i.e. config.env was just created from the template."""
    from dotenv import load_dotenv

    config_file = home / 'config.env'
    first_run = not config_file.exists()
    if first_run:
        shutil.copyfile(bundle_dir() / 'desktop' / 'config.env.template', config_file)
    load_dotenv(config_file, override=False)

    defaults = {
        'MODEL_RUNTIME': 'inprocess',
        'MODELS_DIR': str(home / 'models'),
        'OV_CACHE_DIR': str(home / 'ov_cache'),
        'GMAIL_TOKEN_PATH': str(home / '.secrets' / 'gmail-token.json'),
        'PARSE_WORKER_ENABLED': 'true',
        'LOGFIRE_SEND': 'false',
        'HF_HUB_DISABLE_SYMLINKS_WARNING': '1',
        'HF_HUB_DISABLE_TELEMETRY': '1',
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    # Relative paths anywhere in the backend (logfire's .logfire/, a relative token path) land
    # in the data dir, never next to the exe in Program Files.
    os.chdir(home)
    return first_run


def message_box(text: str, title: str = APP_TITLE, error: bool = False) -> None:
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 if error else 0x40)


def open_path(path: Path) -> None:
    os.startfile(str(path))  # noqa: S606 — opening a user file/folder in its default app


# --------------------------------------------------------------------------------------------
# Single instance
# --------------------------------------------------------------------------------------------

class SingleInstance:
    """An exclusively-locked file in the data dir; the running instance writes its port next to
    it so a second launch can just open the browser on it instead of starting another server."""

    def __init__(self, home: Path) -> None:
        self._lock_path = home / 'instance.lock'
        self._port_path = home / 'instance.port'
        self._handle = None

    def acquire(self) -> bool:
        import msvcrt

        handle = open(self._lock_path, 'a+')  # noqa: SIM115 — held open for the process lifetime
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def running_port(self) -> int | None:
        try:
            return int(self._port_path.read_text().strip())
        except (OSError, ValueError):
            return None

    def publish_port(self, port: int) -> None:
        self._port_path.write_text(str(port))


def pick_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(('127.0.0.1', port))
                return probe.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError('No free localhost port')


# --------------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------------

def start_postgres(home: Path):
    """Start (or attach to) the embedded Postgres for this data dir; it is stopped again by an
    atexit hook when the app quits. First start runs initdb (~10 s)."""
    import pixeltable_pgserver

    server = pixeltable_pgserver.get_server(home / 'pgdata', cleanup_mode='stop')
    os.environ['DATABASE_URL'] = server.get_uri()
    return server


async def init_database(home: Path) -> None:
    """Idempotent: CREATE TABLE IF NOT EXISTS + additive migrations, then make sure the
    configured admin account exists — what `POST /setup/database` does in the Docker setup.

    Unlike the Docker setup (which never overwrites an existing admin password), on the desktop
    config.env *is* the control panel: whenever ADMIN_PASSWORD there changes, it's applied to the
    admin account on the next start. A password changed in the app itself is left alone until
    config.env's value changes again."""
    import bcrypt

    from pydantic_backend.config import get_settings
    from pydantic_backend.db import pool_connection, stop_pools
    from pydantic_backend.ingestion.postgres import PostgresRepository

    settings = get_settings()
    repository = PostgresRepository(settings)
    try:
        await repository.initialize()
        email = settings.admin_email
        password = settings.admin_password.get_secret_value()
        if email and password:
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await repository.ensure_admin(email, password_hash)
            # Remembers which config value was last applied (a digest, never the password).
            marker = home / '.admin-password-applied'
            fingerprint = hashlib.sha256(f'{email}\0{password}'.encode('utf-8')).hexdigest()
            if not marker.exists() or marker.read_text().strip() != fingerprint:
                async with pool_connection(settings) as connection:
                    await connection.execute(
                        'UPDATE employees SET password_hash = %s WHERE email = %s', (password_hash, email),
                    )
                    await connection.commit()
                marker.write_text(fingerprint)
                log.info('Applied ADMIN_PASSWORD from config.env to %s', email)
    finally:
        # The pool is bound to this throwaway event loop; uvicorn's loop opens its own.
        await stop_pools()


# --------------------------------------------------------------------------------------------
# Web server: API under /api, static UI everywhere else, one origin (so no CORS)
# --------------------------------------------------------------------------------------------

def _without_basic_challenge(send):
    """Drop `WWW-Authenticate` from API responses. The UI does its own login form with HTTP Basic
    credentials, but when it's served from the *same origin* as the API (unlike the Docker setup's
    separate ports) a 401 carrying that header makes the browser pop its native sign-in dialog
    over the app on every failed or expired login."""

    async def wrapped(message):
        if message['type'] == 'http.response.start':
            headers = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'www-authenticate']
            message = {**message, 'headers': headers}
        await send(message)

    return wrapped


def build_asgi_app(static_dir: Path):
    from starlette.staticfiles import StaticFiles

    from pydantic_backend.app import app as backend

    static = StaticFiles(directory=static_dir, html=True)

    async def app(scope, receive, send):
        if scope['type'] == 'http':
            path = scope['path']
            if path == '/api' or path.startswith('/api/'):
                inner = path[len('/api'):] or '/'
                scope = {**scope, 'path': inner, 'raw_path': inner.encode('utf-8')}
                await backend(scope, receive, _without_basic_challenge(send))
                return
            await static(scope, receive, send)
            return
        # 'lifespan' (and anything else) goes to the backend, so its startup hooks — pool,
        # pipeline worker — run exactly as under plain uvicorn.
        await backend(scope, receive, send)

    return app


class ServerThread(threading.Thread):
    def __init__(self, app, port: int) -> None:
        super().__init__(name='uvicorn', daemon=True)
        import uvicorn

        config = uvicorn.Config(app, host='127.0.0.1', port=port, log_config=None, access_log=False)
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        # psycopg's async driver can't run on Windows' default ProactorEventLoop.
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.server.serve())
        finally:
            loop.close()

    def stop(self) -> None:
        self.server.should_exit = True
        self.join(timeout=15)


# --------------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------------

class ModelStatus:
    def __init__(self) -> None:
        self.text = 'Models: waiting'
        self.listeners: list = []

    def set(self, text: str) -> None:
        self.text = text
        log.info(text)
        for listener in self.listeners:
            listener()


def preload_models(status: ModelStatus) -> bool:
    """Download (first run) + compile both on-device models. Returns True if both loaded."""
    from pydantic_backend.local_models import llm, ocr

    ok = True
    for label, loader in (('Text model', llm.preload), ('OCR model', ocr.preload)):
        status.set(f'{label}: downloading / loading…')
        try:
            device = loader()
            status.set(f'{label}: ready on {device}')
        except Exception as exc:  # noqa: BLE001 — the app still runs; parsing/detection will retry
            log.exception('%s failed to load', label)
            status.set(f'{label}: failed ({exc.__class__.__name__}) — see logs')
            ok = False
    status.set('Models ready' if ok else 'Some models failed to load — see logs')
    return ok


# --------------------------------------------------------------------------------------------
# Tray
# --------------------------------------------------------------------------------------------

def run_tray(url: str, home: Path, status: ModelStatus, on_quit) -> None:
    import pystray
    from PIL import Image

    icon_file = frontend_dir() / 'favicon.ico'
    image = Image.open(icon_file) if icon_file.exists() else Image.new('RGB', (64, 64), (0, 104, 181))

    def connect_gmail(_icon, _item) -> None:
        def flow() -> None:
            from pydantic_backend.config import get_settings
            from pydantic_backend.ingestion.gmail import authorize

            settings = get_settings()
            if not settings.gmail_client_id:
                message_box('Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in Settings first, then restart.')
                return
            try:
                authorize(settings)
                message_box('Gmail connected.')
            except Exception as exc:  # noqa: BLE001
                log.exception('Gmail authorization failed')
                message_box(f'Gmail authorization failed: {exc}', error=True)

        threading.Thread(target=flow, daemon=True).start()

    def quit_app(icon, _item) -> None:
        icon.visible = False
        on_quit()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(f'Open {APP_TITLE}', lambda: webbrowser.open(url), default=True),
        pystray.MenuItem(lambda _item: status.text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Connect Gmail…', connect_gmail),
        pystray.MenuItem('Settings (restart to apply)…', lambda: open_path(home / 'config.env')),
        pystray.MenuItem('Open data folder', lambda: open_path(home)),
        pystray.MenuItem('Open log', lambda: open_path(home / 'logs' / 'tender-eval.log')),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', quit_app),
    )
    icon = pystray.Icon(APP_NAME, image, APP_TITLE, menu)
    status.listeners.append(icon.update_menu)
    icon.run()


# --------------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------------

def cmd_setup(home: Path) -> int:
    load_config(home)
    # Model preparation never touches the database, but Settings() requires a URL to exist.
    os.environ.setdefault('DATABASE_URL', 'postgresql://unused')
    status = ModelStatus()
    return 0 if preload_models(status) else 1


def cmd_run(home: Path, open_browser: bool) -> int:
    instance = SingleInstance(home)
    if not instance.acquire():
        port = instance.running_port() or DEFAULT_PORT
        webbrowser.open(f'http://127.0.0.1:{port}/')
        return 0

    first_run = load_config(home)
    static_dir = frontend_dir()
    if not (static_dir / 'index.html').exists():
        message_box(f'The UI bundle is missing ({static_dir}). Reinstall {APP_TITLE}.', error=True)
        return 1

    try:
        start_postgres(home)
        asyncio.run(init_database(home), loop_factory=asyncio.SelectorEventLoop)  # see ServerThread.run
    except Exception as exc:  # noqa: BLE001
        log.exception('Database startup failed')
        message_box(f'Could not start the local database: {exc}\n\nSee {home / "logs"}.', error=True)
        return 1

    port = pick_port(DEFAULT_PORT)
    server = ServerThread(build_asgi_app(static_dir), port)
    server.start()
    instance.publish_port(port)
    url = f'http://127.0.0.1:{port}/'
    log.info('Serving %s', url)

    status = ModelStatus()
    threading.Thread(target=preload_models, args=(status,), name='model-preload', daemon=True).start()

    if first_run:
        subprocess.Popen(['notepad.exe', str(home / 'config.env')])  # noqa: S603, S607
        message_box(
            f'{APP_TITLE} is running (tray icon).\n\n'
            'First run: fill in your Anthropic API key and Gmail OAuth client in the settings file '
            'that just opened, then restart the app from the tray icon.\n\n'
            'The on-device models (~3.5 GB) are downloading in the background — the tray menu '
            'shows progress.'
        )
    if open_browser:
        webbrowser.open(url)

    run_tray(url, home, status, on_quit=server.stop)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument('command', nargs='?', default='run', choices=['run', 'setup'])
    parser.add_argument('--no-browser', action='store_true', help='do not open the UI on start')
    args = parser.parse_args(argv)

    home = home_dir()
    setup_logging(home)
    log.info('%s %s (frozen=%s) home=%s', APP_NAME, args.command, getattr(sys, 'frozen', False), home)
    try:
        if args.command == 'setup':
            return cmd_setup(home)
        return cmd_run(home, open_browser=not args.no_browser)
    except Exception as exc:  # noqa: BLE001 — last resort: a windowed exe must never fail silently
        log.exception('Fatal error')
        message_box(f'{APP_TITLE} failed to start: {exc}\n\nSee {home / "logs"}.', error=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
