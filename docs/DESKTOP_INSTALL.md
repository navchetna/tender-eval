# Tender Evaluation desktop app: install and configure

Tender Evaluation runs as a single Windows app on an Intel AI PC. The AI models run on the PC's
own NPU and GPU, and the app includes its own database. There's nothing else to install: no
Docker, WSL, Python, oneAPI or model servers.

## Requirements

- Windows 10 or 11, 64-bit, on an Intel Core Ultra PC (Arc GPU + NPU). Other Intel PCs work too,
  using the GPU or CPU, just more slowly.
- Up-to-date Intel graphics and NPU drivers. They're usually already installed. If not, get them
  from Intel's driver site or Windows Update.
- About 5 GB of free disk space: about 3.6 GB of AI models plus the app.
- Internet access for the first-time model download, Gmail and Google Drive, and Claude (if you
  use it).

## 1. Install

1. Download **[TenderEval-Setup-0.3.0.exe](https://github.com/navchetna/tender-eval/releases/download/desktop-v0.3.0/TenderEval-Setup-0.3.0.exe)** (about 115 MB; newer versions are on the
   [Releases page](https://github.com/navchetna/tender-eval/releases)) and run it. No administrator rights are needed; it installs for
   your Windows user only.
2. Work through the wizard:

   | Page | What to enter |
   |---|---|
   | **Admin account** | The email and password you'll sign in with (at least 8 characters). |
   | **Claude** (optional) | An API key if you want Claude to do the reasoning (compliance matrix, scoring, comparison). Leave it empty to use the on-device model instead. See [Claude options](#claude-options). |
   | **Gmail and Google Drive** (optional) | Your Google OAuth client ID and secret, and a reviewer email for notifications. You can also add these later. See [Google setup](#google-setup). |

3. Leave **"Download and prepare the on-device AI models now"** ticked. The installer downloads
   the models (about 3.6 GB) and prepares them for this PC's NPU and GPU. This can take 10–20
   minutes the first time.
4. Click **Finish** with **Launch Tender Evaluation** ticked.

## 2. Use it

- The app opens in your browser at **http://127.0.0.1:8011** and keeps running in the background.
  Sign in with the admin account from the wizard.
- It has a **tray icon** at the bottom-right of the taskbar. If you don't see it, click the **^**
  arrow next to the clock. Right-click the icon for these options:
  - **Open Tender Evaluation**
  - The models' status
  - **Connect Gmail…**
  - **Settings…**
  - **Open data folder**
  - **Open log**
  - **Quit**
- Start it again later from the **Start menu > Tender Evaluation**.

## 3. Change settings

All settings are in one file: **`%LOCALAPPDATA%\TenderEval\config.env`**.

1. Open it from **Start menu > Tender Evaluation settings**, or from the tray icon's **Settings…**.
2. Edit the values (`NAME=value`, one per line) and save.
3. **Restart the app.** Right-click the tray icon, choose **Quit**, and start Tender Evaluation
   again. Settings are only read at startup. Launching the app while it's already running just
   opens the browser.

| Setting | Required? | What it does |
|---|---|---|
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Yes | The admin sign-in. Changing `ADMIN_PASSWORD` resets the admin's password on the next start. |
| `ANTHROPIC_API_KEY` | No | Your Claude key. Without it, reasoning uses the on-device model. |
| `ANTHROPIC_BASE_URL` | No | Only for Claude on Azure AI Foundry: `https://<resource>.openai.azure.com/anthropic`. |
| `ANTHROPIC_QUALITY_MODEL` | No | Which Claude model to use, for example `claude-sonnet-4-5`. |
| `QUALITY_LLM_BASE_URL` / `QUALITY_LLM_API_KEY` / `QUALITY_LLM_MODEL` | No | Use an OpenAI-compatible gateway (LiteLLM, an enterprise gateway) for reasoning instead. |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` | To upload documents | Your Google OAuth client (see [Google setup](#google-setup)). |
| `GMAIL_QUERY` | No | Which emails Gmail ingestion picks up. |
| `DRIVE_PARENT_FOLDER_ID` | No | Drive folder for all projects. If empty, the app uses a "Tender Evaluation" folder in your own My Drive. |
| `REVIEWER_EMAIL` | No | Who receives review notification emails. If empty, no emails are sent. |
| `LOCAL_FAST_MODEL_DEVICE` | No | Device for the text model: `NPU` (default), `GPU` or `CPU`. |
| `LOCAL_OCR_MODEL_DEVICE` | No | Device for the OCR model: `GPU` (default), `NPU` or `CPU`. |

The file is commented, and `desktop/config.env.example` in the repo is the full template.

### Claude options

The app needs Claude only for the reasoning steps: the compliance matrix, scoring and the final
comparison. Pick one:

- **No Claude.** Leave the keys empty. Reasoning runs on the on-device Qwen model. It's free and
  runs offline, but it's less capable than Claude.
- **Anthropic API.** Set `ANTHROPIC_API_KEY=sk-ant-…` (from console.anthropic.com).
- **Claude on Azure AI Foundry.** Set `ANTHROPIC_API_KEY` to the Foundry key and
  `ANTHROPIC_BASE_URL=https://<resource>.openai.azure.com/anthropic`.
- **A LiteLLM or enterprise gateway.** Set `QUALITY_LLM_BASE_URL`, `QUALITY_LLM_API_KEY` and
  `QUALITY_LLM_MODEL`.

To switch between Claude and the on-device model at any time without a restart, an admin can use
**Operations > Reasoning model**:
- **Auto** uses Claude if it's configured, otherwise the on-device model.
- **Claude** always uses Claude.
- **On-device** always uses the on-device model.

### Google setup

Uploading and ingesting PDFs stores them in Google Drive, so the app needs a Google OAuth client:

1. In [Google Cloud Console](https://console.cloud.google.com), create or pick a project. Enable
   the **Gmail API** and the **Google Drive API**.
2. Go to **APIs & Services > Credentials > Create credentials > OAuth client ID**, with
   application type **Desktop app**.
3. Put the client ID and secret into `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET`, then restart
   the app.
4. Right-click the tray icon and choose **Connect Gmail…**. Sign in and approve the Gmail and
   Drive permissions. If Google warns that the app isn't verified, choose
   **Advanced > Go to …**; that's expected for your own OAuth client. You only need to do this
   once.

## Troubleshooting

- **Something fails.** The page shows the reason. For more detail, open the tray icon's
  **Open log** (`%LOCALAPPDATA%\TenderEval\logs\tender-eval.log`).
- **"Google Drive is not connected yet."** Fill in the Google settings, restart, then use
  **Connect Gmail…**.
- **Can't sign in.** Check `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `config.env`. Restart after
  changing them.
- **A Claude error appears on the compliance matrix.** Check the [Claude options](#claude-options),
  or switch **Operations > Reasoning model** to **On-device**.
- **Documents take a while to process.** OCR takes roughly 15–30 seconds per page. Progress is on
  the **Operations** page.

## Uninstall

Use **Windows Settings > Apps > Tender Evaluation > Uninstall**. Your data (projects database,
downloaded models and settings) stays in `%LOCALAPPDATA%\TenderEval`, so reinstalling picks up
where you left off. Delete that folder to remove everything.
