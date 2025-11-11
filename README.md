# hackathon-dont-touch-the-grass-enjoyers

## Prerequisites

- Python 3.14 or higher

## Setup Instructions

### 1. Create a Virtual Environment

```bash
python3.14 -m venv venv
```

### 2. Activate the Virtual Environment

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

Check that ruff and pyright are installed:
```bash
ruff --version
pyright --version
```

## Development Tools

This project uses:
- **ruff**: Fast Python linter and formatter
- **pyright**: Static type checker for Python

### Running Linter

```bash
ruff check .
```

### Running Type Checker

```bash
pyright
```

## Deactivating the Virtual Environment

When you're done working, deactivate the virtual environment:
```bash
deactivate
```