# Development Setup Guide

## Environment Setup

### Frontend Setup

1. **Node.js Installation**
```bash
# Install NVM (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Install Node.js
nvm install 18
nvm use 18

# Verify installation
node --version
npm --version
```

2. **Angular CLI Installation**
```bash
npm install -g @angular/cli
```

3. **Frontend Dependencies**
```bash
cd frontend
npm install
```

### Backend Setup

1. **Python Environment**
```bash
# Install pyenv for Python version management
curl https://pyenv.run | bash

# Install Python 3.11
pyenv install 3.11.0
pyenv global 3.11.0

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

2. **Install Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

3. **Database Setup**
```bash
# Install PostgreSQL
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb school_management_db
sudo -u postgres createuser --interactive

# Run migrations
python -m alembic upgrade head
```

## Development Workflow

### Frontend Development

1. **Start Development Server**
```bash
cd frontend
ng serve
```

2. **Running Tests**
```bash
# Unit tests
ng test

# E2E tests
ng e2e
```

3. **Code Linting**
```bash
ng lint
```

### Backend Development

1. **Start Development Server**
```bash
cd backend
uvicorn app.main:app --reload
```

2. **Running Tests**
```bash
pytest
```

3. **Code Formatting**
```bash
# Install black
pip install black

# Format code
black .
```

## Docker Development Environment

1. **Build Images**
```bash
docker-compose build
```

2. **Start Services**
```bash
docker-compose up -d
```

3. **View Logs**
```bash
docker-compose logs -f
```

## Git Workflow

1. **Create Feature Branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Commit Changes**
```bash
git add .
git commit -m "feat: your feature description"
```

3. **Push Changes**
```bash
git push origin feature/your-feature-name
```

## IDE Setup

### VS Code Extensions
- Angular Language Service
- Python
- PostgreSQL
- Docker
- ESLint
- Prettier
- GitLens

### VS Code Settings
```json
{
    "editor.formatOnSave": true,
    "python.linting.enabled": true,
    "python.formatting.provider": "black",
    "[typescript]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    }
}
```

## Debugging

### Frontend Debugging
1. Use Chrome DevTools
2. Enable source maps in development
3. Use Angular DevTools browser extension

### Backend Debugging
1. Use VS Code debugger
2. Configure launch.json for Python debugging
3. Use pdb for manual debugging

## Common Issues and Solutions

1. **Database Connection Issues**
- Check PostgreSQL service status
- Verify connection strings
- Check firewall settings

2. **Node Module Issues**
- Clear npm cache
- Delete node_modules and reinstall
- Check package.json for conflicts

3. **Python Environment Issues**
- Verify virtual environment activation
- Check Python version compatibility
- Validate package versions in requirements.txt