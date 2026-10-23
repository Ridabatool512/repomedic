# RepoMedic

RepoMedic is a developer-focused project analysis dashboard designed to help you understand a Python codebase before making changes. It brings together Python file scanning, bug checks, dependency exploration, and change-impact analysis in one interface.

## What it does

- **Project scanning** — scan a selected project folder and view summary information such as Python files, functions, import statements, and syntax errors.
- **GitHub repository import** — import a public GitHub repository into the backend's workspace, then select it for analysis.
- **Bug detection** — use the bug-checking panel to inspect a project for issues.
- **Dependency analysis** — inspect imports between files, explore the dependency graph, and check for circular imports.
- **Change-impact analysis** — select or enter a project-relative file path to see which files may be affected by a change and review the returned risk estimate.
- **Dashboard feedback** — see loading states, errors, and status messages as analysis requests run.

## Tech stack

- **Frontend:** React, Vite, and Lucide icons
- **Backend:** Python API (the frontend communicates with it through an API service)
- **Styling:** CSS

## Repository structure

```text
repomedic/
├── frontend/       # React dashboard
└── backend/        # Python API and analysis logic
```

The exact contents may evolve as the project develops.

## How it works

1. Start the backend API.
2. Start the frontend development server.
3. Open the dashboard in your browser.
4. Select the demo project or import a public GitHub repository.
5. Run a scan, inspect dependencies, use the bug-detection panel, or analyze the impact of a changed file.

The frontend currently expects the API at `http://127.0.0.1:8000` in the local development setup. For a deployed version, configure the frontend API base URL to point to the publicly hosted backend.

## Run locally

You need Node.js/npm for the frontend and Python for the backend.

### 1. Clone the repository

```powershell
git clone https://github.com/Ridabatool512/repomedic.git
cd repomedic
```

### 2. Start the backend

Open a terminal in the backend directory:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation, you can use the environment's Python executable directly instead. Start the API using the entry point and command defined by the backend files; the frontend's local API address is `http://127.0.0.1:8000`.

### 3. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite in the terminal.

> **Note:** Backend installation and startup commands depend on the files included in the current backend version. If your checkout does not contain `requirements.txt`, use the dependency and startup instructions provided by the backend project.

## Important notes

- GitHub import currently supports **public repositories** through the app's import flow.
- Imported repository selections are saved in browser local storage.
- The project path is interpreted by the backend environment; a Windows path on your computer will not automatically exist on a remote server.
- Do not run untrusted source code just to analyze it. RepoMedic's import UI states that importing copies the code and does not run repository scripts.
- The local API address is for development only. A public deployment needs a hosted backend and a configured frontend API URL.

## Current status

RepoMedic is an evolving project. Features and setup details may change as development continues.

## Contributing

Issues and pull requests are welcome. When reporting a problem, include the steps to reproduce it, the expected behavior, and any relevant error message—without sharing secrets, tokens, or private source code.

## License

No license is specified here yet. Unless a license is added to the repository, standard copyright restrictions apply.
