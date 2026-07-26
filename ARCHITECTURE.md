# Architecture

TableMaster keeps the original Flask behavior while grouping responsibilities by domain.

## Request layer

- `tablemaster.routes.core`: PWA assets, authentication, uploads, and users
- `tablemaster.routes.tables`: floor view and table lifecycle
- `tablemaster.routes.orders`: order entry, history, export, and transfers
- `tablemaster.routes.billing`: bills and split payments
- `tablemaster.routes.catalog`: categories, subcategories, and products
- `tablemaster.routes.admin_actions`: printers, receipts, general settings, and backups
- `tablemaster.routes.settings`: settings dashboard and company information

Registration functions receive the Flask app and only the service callbacks they need. This preserves the existing endpoint names used throughout the Jinja templates.

## Data and services

- `tablemaster.database` owns SQLite connections and schema initialization.
- `tablemaster.licensing` owns machine-bound license validation.
- `tablemaster.services.spreadsheets` owns Excel catalogue synchronization.
- The remaining receipt and ESC/POS orchestration stays in the bootstrap module because its background scheduler and hardware behavior must be validated against real printers before a further extraction.

## Presentation

Templates remain grouped by pages, settings partials, reusable partials, and modals. Shared and page-specific CSS/JavaScript are kept separate, and inline presentation code is progressively limited to components that require server-rendered Jinja values.

## Compatibility policy

Refactoring must not change public URLs, Flask endpoint names, database schemas, template context keys, printer payloads, or backup formats. Hardware-related changes require a final test on the restaurant network.
