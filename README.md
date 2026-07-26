# TableMaster

TableMaster is a Flask-based restaurant management and point-of-sale application designed for cafés, bars, and restaurants. It combines table management, ordering, billing, staff access, product administration, audit history, and ESC/POS network printing in one responsive web interface.

## Highlights

- Live floor and table-status management
- Order entry with categories, products, quantities, and comments
- Bill splitting, payment methods, receipts, and order transfers
- Product and category management with Excel import/export
- PIN-based users with administrator and staff roles
- Company, invoice, backup, and session settings
- Network ESC/POS printer routing and retry queue
- Audit logs and offline-friendly PWA assets
- Responsive Flask/Jinja interface for desktop, tablet, and mobile use

## Technology

- Python and Flask
- SQLite
- Jinja templates, HTML, CSS, and JavaScript
- Pandas and OpenPyXL for spreadsheet workflows
- python-escpos for receipt and kitchen printers
- Service worker and web app manifest for PWA behavior

## Project structure

```text
app.py                 Flask application and routes
templates/             Jinja pages, settings, partials, and modals
static/                CSS, JavaScript, icons, manifest, and service worker
schema.sql             Main SQLite schema
audit_schema.sql       Audit database schema
uploads/template.xlsx  Product import template
```

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Set `TABLEMASTER_SECRET_KEY` to a long random value.
4. Run `python generate_license.py` for a local development license.
5. Start the application with `python app.py` and open `http://localhost:5000`.

The application creates its SQLite databases locally from the included schemas. Database files, encryption keys, license files, backups, and customer uploads are intentionally excluded from this public repository.

## Portfolio note

This repository presents the application source and interface as a portfolio project. Printer communication expects compatible ESC/POS devices on the same local network. No production restaurant data or private credentials are included.
