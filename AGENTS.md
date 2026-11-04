# Repository Guidelines

## Project Structure & Architecture

This repository combines a React/Vite frontend and a FastAPI backend.

- src/ contains the client application. App.jsx coordinates session, route, and SCORM behavior; pages/ contains screens; components/ contains reusable UI; CSS and styles/ contain presentation code.
- public/ contains static assets. Treat public/scorm/ as published course content: do not change packages or .htaccess casually, because SCORM URLs must bypass the React fallback.
- backend/ contains the API. Put HTTP endpoints in backend/routes/, persistence models in models.py, request schemas in schemas.py, and reusable logic in focused helper modules.
- Database changes use one-off backend/migrate_*.py scripts. Review and run the applicable migration explicitly; automatic schema creation is disabled by default in production.
- Backend tests live in backend/tests/; technical execution notes belong in docs/.

## Setup, Build, and Test Commands

Install frontend dependencies with npm ci. Use npm run dev for Vite development, npm run lint before committing JavaScript or JSX changes, npm run build to create dist/, and npm run preview to inspect a production build.

Run API commands from backend/, whose imports assume that working directory:

powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
python -m unittest discover -s tests -v


Copy backend/.env.example to a private .env. Never commit credentials, databases, virtual environments, or generated dist/ files.

## Coding Style and Tests

Use four spaces and snake_case in Python. Use two spaces, camelCase, and PascalCase React components in JavaScript/JSX. Follow the existing FastAPI router pattern and keep authorization checks at route boundaries. ESLint covers frontend code; no Prettier configuration exists.

Name Python files and test methods test_<expected_behavior>. The current suite uses standard-library unittest, not pytest. Add focused regression coverage whenever changing authentication, enrollment, SCORM handling, or attendance; run lint and the relevant backend tests before handing off a change.

## Commits and Pull Requests

History has no rigid format, but concise Portuguese action subjects are common, such as corrige sessao expirada or adiciona validacao SCORM. Keep each commit scoped; avoid vague messages such as +. In a pull request, describe behavior changes, migrations and configuration variables, list validation commands, and attach screenshots for visible frontend changes. Do not mix generated SCORM assets with unrelated code changes.