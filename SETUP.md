# ManoMitra AI - Repository Setup & Deployment Guide

This guide explains how to set up the unified ManoMitra AI repository for development and deployment.

## Prerequisites

### System Requirements
- **Operating System**: Windows, macOS, or Linux
- **Disk Space**: Minimum 5GB (2GB for Python venv + 3GB for node_modules)
- **Internet Connection**: Required for downloading dependencies

### Software Requirements
- **Git**: 2.25 or higher
- **Python**: 3.8 or higher (3.10+ recommended)
- **Node.js**: 16+ or **Bun**: Latest version
- **npm/yarn/bun**: Package manager (comes with Node.js)

## Repository Structure

```
ManoMitraAI/
├── backend/                   # FastAPI backend application
│   ├── app/                   # Application source code
│   ├── models/                # ML models (ignored in .gitignore - not in repo)
│   ├── project/               # Python venv (ignored in .gitignore - not in repo)
│   ├── .env.example           # Example environment variables
│   └── requirements.txt       # Python dependencies
│
├── frontend/                  # React TypeScript frontend
│   ├── src/                   # React source code
│   ├── node_modules/          # npm packages (ignored in .gitignore - not in repo)
│   ├── .env.example           # Example environment variables
│   └── package.json           # Node.js dependencies
│
├── .gitignore                 # Unified git ignore rules
├── .gitattributes             # Git attributes for line endings
└── README.md                  # Main project documentation
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ManoMitraAI.git
cd ManoMitraAI
```

### 2. Backend Setup

#### 2.1 Create Python Virtual Environment

```bash
cd backend

# Windows (PowerShell or CMD)
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 2.2 Install Python Dependencies

```bash
pip install -r app/requirements.txt
```

**Note**: This will also create/install the ML models if configured in requirements.txt

#### 2.3 Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env      # macOS/Linux
copy .env.example .env    # Windows

# Edit .env with your configuration
# Open with your favorite editor and fill in required values
```

#### 2.4 Download ML Models (if needed)

If models are not automatically downloaded:

```bash
# Models will be stored in backend/models/ (not tracked in git)
# The app will attempt to download on first run
python app/main.py
```

#### 2.5 Run the Backend Server

```bash
# From the backend directory with venv activated
python app/main.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API will be available at: **http://localhost:8000**
API Documentation: **http://localhost:8000/docs** (Swagger UI)

### 3. Frontend Setup

#### 3.1 Install Node.js Dependencies

```bash
cd frontend

# Using npm
npm install

# Or using yarn
yarn install

# Or using bun (faster)
bun install
```

#### 3.2 Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env.local    # macOS/Linux
copy .env.example .env.local  # Windows

# Edit .env.local with your configuration
```

#### 3.3 Run Development Server

```bash
# Using npm
npm run dev

# Using yarn
yarn dev

# Using bun
bun run dev
```

Frontend will be available at: **http://localhost:5173**

### 4. Verify Setup

Both backend and frontend should be running:

1. Open **http://localhost:5173** in your browser
2. The frontend should connect to the backend at `http://localhost:8000`
3. Look for the API documentation at **http://localhost:8000/docs**

## Development Workflow

### Adding Dependencies

#### Backend
```bash
cd backend
# Activate venv first
pip install <package_name>
pip freeze > app/requirements.txt  # Update requirements file
```

#### Frontend
```bash
cd frontend
npm install <package_name>  # Updates package.json and package-lock.json
```

### Making Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Commit with clear messages: `git commit -m "feat: add new feature"`
4. Push to your fork and create a pull request

### Important .gitignore Notes

The following directories and files are **intentionally ignored** by git (not in repository):

- **backend/models/** - Large ML model files (100MB+)
- **backend/project/** - Python virtual environment
- **frontend/node_modules/** - Node.js packages
- **.env files** - Local configuration and secrets
- **__pycache__/** - Python cache
- **dist/**, **build/** - Build outputs

**These will be created locally when you run setup commands.**

## Production Deployment

### Backend Deployment

```bash
# Install gunicorn or similar production server
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
```

### Frontend Deployment

```bash
# Build for production
npm run build

# Output will be in dist/ directory
# Serve with any static file server
```

### Environment Variables for Production

- Update `.env` (backend) and `.env.local` (frontend) with production values
- Never commit `.env` files to git
- Use your platform's secret management (e.g., GitHub Secrets, GitHub Actions)

## Troubleshooting

### Backend Issues

**Issue**: `pip install` fails
- **Solution**: Ensure Python 3.8+ is installed and in PATH
- Run: `python --version`

**Issue**: Port 8000 already in use
- **Solution**: Kill the process or use different port:
  ```bash
  uvicorn app.main:app --port 8001
  ```

**Issue**: Model files not downloaded
- **Solution**: Manually download from Hugging Face:
  ```bash
  python -c "from transformers import AutoModel; AutoModel.from_pretrained('model-name')"
  ```

### Frontend Issues

**Issue**: `npm install` fails
- **Solution**: Clear npm cache and reinstall:
  ```bash
  npm cache clean --force
  npm install
  ```

**Issue**: Cannot connect to backend API
- **Solution**: Verify:
  1. Backend is running on http://localhost:8000
  2. `VITE_API_URL` in `.env.local` is correct
  3. CORS settings in backend allow your frontend URL

**Issue**: Port 5173 already in use
- **Solution**: Use different port:
  ```bash
  npm run dev -- --port 5174
  ```

## Git Workflow

### Before Pushing to GitHub

```bash
# Check git status
git status

# Verify .env files are NOT committed
git ls-files | grep "\.env"  # Should return nothing

# Verify large model files are NOT committed
git ls-files | grep -E "(\.bin|\.safetensors|models/)"  # Should return nothing

# Check .gitignore is properly configured
git check-ignore -v backend/models/*
```

### Merging Between Branches

When pulling changes:
```bash
git pull origin main

# Reinstall dependencies if package files changed
pip install -r app/requirements.txt  # Backend
npm install  # Frontend
```

## Additional Resources

- **Backend README**: See [backend/README.md](backend/README.md)
- **Frontend README**: See [frontend/README.md](frontend/README.md)
- **API Documentation**: http://localhost:8000/docs (when backend is running)

## Support

For issues or questions:
1. Check relevant README files
2. Review .env.example files for configuration options
3. Check application logs for error messages
4. Create an issue on GitHub with detailed information

---

**Last Updated**: February 22, 2026
**Repository**: ManoMitra AI
