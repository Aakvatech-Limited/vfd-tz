# VFD TZ

VFD TZ is an Aakvatech Frappe/ERPNext application for integrating ERPNext sales transactions with Tanzania Virtual Fiscal Device (VFD) workflows.

The `version-16-hotfix` line is intended for:

- Frappe 16
- ERPNext 16
- Python 3.14 or later

## Key Features

### Sales Invoice VFD integration

The app extends ERPNext Sales Invoice processing with VFD-specific controls and automation, including:

- VFD validation before Sales Invoice submission
- Automatic enqueueing of submitted Sales Invoices for VFD processing
- Cancellation validation for invoices that have already entered the VFD flow
- Support for automatic and excluded-from-VFD invoice flags
- Storage of VFD receipt, verification, posting, date/time and Z-report information on the Sales Invoice
- Optional serial-number submission to TRA where applicable

### Customer tax information

Customer records are extended with VFD customer identification fields. The app validates and normalizes customer tax identification information during Customer validation.

### VFD Tax Invoice

The app includes a dedicated VFD Tax Invoice workflow and scheduled processing for pending VFD tax invoices.

### VFD Z Reports

The application supports VFD Z-report generation and delivery, including:

- Scheduled Z-report generation
- Multi-VFD Z-report processing
- Association of Z-report information with Sales Invoices

### Automated processing and retries

Background jobs periodically process pending VFD documents.

Current scheduler behavior includes:

- Every 15 minutes: process pending Sales Invoices and VFD Tax Invoices
- Every 5 minutes during the configured off-peak window: additional VFD posting attempts
- Hourly: process multi-VFD Z reports
- Daily at 02:00: generate VFD Z reports and check VFD status

## ERPNext Integration

The app adds VFD-related behavior and metadata to standard ERPNext documents including:

- Sales Invoice
- Customer
- Item Tax Template
- Mode of Payment
- POS Profile
- Sales Taxes and Charges Template

These extensions are delivered through app hooks and fixtures.

## Installation

From your Frappe bench:

```bash
bench get-app https://github.com/Aakvatech-Limited/vfd-tz --branch version-16-hotfix
bench --site <your-site> install-app vfd_tz
bench --site <your-site> migrate
```

For an existing installation:

```bash
cd apps/vfd-tz
git fetch origin
git checkout version-16-hotfix
git pull origin version-16-hotfix
cd ../..
bench --site <your-site> migrate
bench build --app vfd_tz
bench restart
```

## Dependencies

Python package dependencies are managed through `pyproject.toml`.

Runtime dependencies include:

- `dicttoxml`
- `defusedxml`

The app declares compatibility with:

```toml
[tool.bench.frappe-dependencies]
frappe = ">=16.0.0,<17.0.0"
erpnext = ">=16.0.0,<17.0.0"
```

## Development

The repository uses the Frappe application structure and a `pyproject.toml`-based build.

Development tooling includes:

- pre-commit
- Ruff linting and formatting
- standard repository CI checks

Install development dependencies as required and run the configured pre-commit checks before submitting changes.

## Branching

For Frappe/ERPNext 16 production fixes and maintenance work, use `version-16-hotfix` as the target branch unless a change specifically belongs to another maintained version line.

## License

MIT

## Maintainer

Aakvatech Limited  
https://aakvatech.com

For implementation, integration, or support enquiries, contact:

`info@aakvatech.com`
