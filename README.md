# Stark Financial Holdings LLC — Asset Ledger

A private, searchable web-based ledger for tracking all company holdings: proprietary IP, computer resources, money market funds, securities, commodities, and cryptocurrency.

## Privacy

All sensitive financial data is stored in a local SQLite file (`ledger.db`) that is **never committed to git**. The repository contains only application code — no holdings data, no PII.

## Setup

**Requirements:** Python 3.10+

```bash
# 1. Clone and enter the repository
git clone https://github.com/Tonystark423/Tonystark423.git
cd Tonystark423

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set strong values for LEDGER_USER, LEDGER_PASS, and FLASK_SECRET_KEY

# 5. Initialize the database
python init_db.py

# 6. Run the server
flask run
```

The application will be available at `http://localhost:5000`. Your browser will prompt for the username and password set in `.env`.

## Asset Categories

| Category | Examples |
|---|---|
| Proprietary IP | Patents, algorithms, trade secrets, software |
| Computer Resources | HBM4 memory supply, servers, hardware |
| Money Market Funds | SPAXX (Fidelity) and similar instruments |
| Securities & Commodities | Stocks, bonds, precious metals held in kind |
| Cryptocurrency | Holdings at third-party exchanges |

## Features

- Full-text search across asset name, description, notes, and custodian
- Filter by category and status (active / pending / sold)
- Add, edit, and delete asset records via modal UI
- Export all records to CSV

## API

All endpoints require HTTP Basic Auth.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/assets` | List/search assets (`?q=`, `?category=`, `?status=`) |
| `POST` | `/api/assets` | Create a new asset |
| `GET` | `/api/assets/<id>` | Get a single asset |
| `PUT` | `/api/assets/<id>` | Update an asset |
| `DELETE` | `/api/assets/<id>` | Delete an asset |
| `GET` | `/api/export` | Download all assets as CSV |

## Security Notes

- Never commit `ledger.db` or `.env` to git (both are in `.gitignore`)
- Use a strong, unique password in `LEDGER_PASS`
- For remote access, run behind HTTPS (e.g. via nginx + Let's Encrypt)
- Consider restricting access by IP if the server is internet-facing
