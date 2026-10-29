# TechFix

TechFix is a Django web application that helps people troubleshoot technology problems and explore devices, accessories, and repair solutions. Its assistant combines locally matched catalog and repair-guide information with optional Google Gemini responses.

## Project Concept Paper

The BSIT class project concept paper describes the proposed scope, objectives, intended users, technology, and limitations of TechFix.

- [Read the concept paper (PDF)](docs/TECHFIX-Concept-Paper.pdf)
- [Download the editable concept paper (Word)](docs/TECHFIX-Concept-Paper.docx)

## Features

- Ask technology and device-repair questions in the TechFix assistant.
- Search and browse product and accessory listings, including product details and accessory compatibility information.
- Read step-by-step repair guides and explore the brand library.
- Create, search, update, and delete personal information records within the signed-in user's data scope.
- Register and sign in to use account-based pages, including the scheduled assistant.
- Manage application users through the administrator user-management page.
- Maintain product, accessory, repair-guide, and category records through Django's administration tools.

Assistant responses can use the configured Gemini API when a key is available. The application also has a local answer path, so the assistant can fall back to locally generated guidance when Gemini is not configured or available. AI-generated troubleshooting guidance should be checked against device documentation, especially before attempting repairs.

## Technology

- Python and Django
- SQLite by default
- HTML, CSS, JavaScript, and Bootstrap-based interface
- Optional Google Gemini API integration

## Run locally

From the repository root:

```powershell
cd projectv3
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The Django administration site is available at `/admin/`; the application user-management page is at `/users/` and is restricted to superusers.

To enable Gemini responses, set `GEMINI_API_KEY` in the environment or in a local `.env` file. The key is optional and must not be committed to the repository. The configured model can be changed with `GEMINI_MODEL`.

Run the Django tests from the `projectv3` directory:

```powershell
python manage.py test
```

## Main application areas

- `projectv3/apps/core/` - assistant, catalog, repair-guide, and authentication functionality.
- `projectv3/apps/users/` - superuser-only application user management.
- `projectv3/apps/info/` - information-record management.
- `projectv3/templates/` and `projectv3/static/` - user interface templates and static assets.
- `projectv3/mysite/settings.py` - Django settings, database configuration, and optional Gemini configuration.
