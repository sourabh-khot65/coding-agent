 #!/bin/bash

# Coding Agent Setup Script
echo "🚀 Setting up Coding Agent..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo "✅ $1"
}

print_warning() {
    echo "⚠️  $1"
}

print_error() {
    echo "❌ $1"
}

print_info() {
    echo "ℹ️  $1"
}

# Check if Python 3 is installed
if ! which python3 >/dev/null 2>&1; then
    print_error "Python 3 is required but not installed. Please install Python 3.8+ and try again."
    exit 1
fi

print_success "Python 3 found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -eq 0 ]; then
        print_success "Virtual environment created"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
else
    print_success "Virtual environment already exists"
fi

# Check if virtual environment is working
echo "🔧 Checking virtual environment..."
if [ -f "venv/bin/python" ] || [ -f "venv/bin/python3" ]; then
    print_success "Virtual environment is ready"
else
    print_error "Virtual environment is not properly configured"
    exit 1
fi

# Use venv python directly (no activation needed)
VENV_PYTHON="venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="venv/bin/python3"
fi

# Test if pip works in venv, if not recreate it
echo "🔧 Testing pip installation..."
if ! $VENV_PYTHON -m pip --version >/dev/null 2>&1; then
    print_warning "Pip is corrupted, recreating virtual environment..."
    rm -rf venv
    python3 -m venv venv
    if [ -f "venv/bin/python" ]; then
        VENV_PYTHON="venv/bin/python"
    elif [ -f "venv/bin/python3" ]; then
        VENV_PYTHON="venv/bin/python3"
    else
        print_error "Failed to recreate virtual environment"
        exit 1
    fi
    print_success "Virtual environment recreated"
fi

# Upgrade pip
echo "⬆️  Upgrading pip..."
if $VENV_PYTHON -m pip install --upgrade pip --quiet; then
    print_success "Pip upgraded successfully"
else
    print_warning "Pip upgrade failed, continuing with existing version..."
fi

# Install dependencies
echo "📚 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    if $VENV_PYTHON -m pip install -r requirements.txt --quiet; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies from requirements.txt"
        print_info "Trying to install basic dependencies manually..."
        if $VENV_PYTHON -m pip install openai requests python-dotenv --quiet; then
            print_success "Basic dependencies installed"
        else
            print_error "Failed to install dependencies. You may need to install them manually:"
            echo "  $VENV_PYTHON -m pip install openai requests python-dotenv"
        fi
    fi
else
    print_warning "requirements.txt not found, installing basic dependencies..."
    if $VENV_PYTHON -m pip install openai requests python-dotenv --quiet; then
        print_success "Basic dependencies installed"
    else
        print_error "Failed to install basic dependencies. You may need to install them manually:"
        echo "  $VENV_PYTHON -m pip install openai requests python-dotenv"
    fi
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cat > .env << 'EOF'
# === API Keys (required) ===
OPENAI_API_KEY=your_openai_api_key_here      # OpenAI API key
GROQ_API_KEY=your_groq_api_key_here          # Groq API key (alternative)
GROQ_BASE_URL=https://api.groq.com/openai/v1 # Custom Groq endpoint (optional)

# === Agent Settings ===
WORKSPACE_DIR=./workspace        # Working directory for agent files

# === LLM Parameters ===
MAX_TOKENS=4096                  # Max tokens per LLM request
TEMPERATURE=0.1                  # LLM creativity (0.0-2.0)
COMMAND_TIMEOUT=120              # Shell command timeout (seconds)

# === Logging ===
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
MAX_LOG_SIZE=1000000             # Max log file size (bytes)
MAX_LOG_LINES=1000               # Max log lines to keep

# === Security ===
ENABLE_SECURITY_VALIDATION=true  # Enable security checks (true/false)

# === Custom Model Selection (optional) ===
OPENAI_MODEL=gpt-4o              # Custom OpenAI model
GROQ_MODEL=llama-3.3-70b-versatile # Custom Groq model
EOF
    print_success "Created .env with actual environment variables from codebase"
    echo ""
    print_info "🔑 IMPORTANT: Edit .env file and add your API key:"
    echo "   • OPENAI_API_KEY (recommended for best results)"
    echo "   • or GROQ_API_KEY (faster, free tier available)"
    echo ""
    echo "   You can edit it with: nano .env"
    echo "   Or any text editor: code .env, vim .env, etc."
else
    print_success ".env file already exists"
fi

# Create workspace directory
mkdir -p workspace
print_success "Workspace directory ready"

# Create agent directory if it doesn't exist
if [ ! -d "agent" ]; then
    print_warning "agent/ directory not found. Make sure agent.py is in the agent/ folder."
fi

# Validate .env file
if [ -f ".env" ]; then
    if grep -q "your_.*_api_key_here" .env; then
        print_warning "API keys not configured yet. Please edit .env file."
    else
        print_success "Environment configuration looks good"
    fi
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "═══════════════════════════════════════════════════════"
echo "                    ENVIRONMENT VARIABLES"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "📋 Available Environment Variables:"
echo ""
echo "🔑 API Configuration:"
echo "   OPENAI_API_KEY        - Your OpenAI API key"
echo "   GROQ_API_KEY          - Your Groq API key"
echo "   GROQ_BASE_URL         - Custom Groq endpoint"
echo ""
echo "⚙️  Agent Settings:"
echo "   WORKSPACE_DIR         - Working directory (default: ./workspace)"
echo "   MAX_TOKENS           - Max LLM tokens (default: 4096)"
echo "   TEMPERATURE          - LLM temperature (default: 0.1)"
echo "   COMMAND_TIMEOUT      - Shell timeout (default: 120s)"
echo ""
echo "📊 Logging:"
echo "   LOG_LEVEL            - DEBUG/INFO/WARNING/ERROR"
echo "   MAX_LOG_SIZE         - Max log file size"
echo "   MAX_LOG_LINES        - Max log lines to keep"
echo ""
echo "🔒 Security:"
echo "   ENABLE_SECURITY_VALIDATION - Enable/disable security checks"
echo ""
echo "🎯 Models:"
echo "   OPENAI_MODEL         - Custom OpenAI model"
echo "   GROQ_MODEL           - Custom Groq model"
echo ""
echo "═══════════════════════════════════════════════════════"
echo "                    NEXT STEPS"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "1. 🔑 Configure API keys:"
echo "   nano .env"
echo ""
echo "2. 📝 Create a task file:"
echo "   echo 'Create a hello world Python script' > workspace/task.txt"
echo ""
echo "3. 🚀 Run the agent:"
echo "   source venv/bin/activate"
echo "   python agent/agent.py"
echo ""
echo "4. 📦 Check the results:"
echo "   cat workspace/status.txt        # Job status"
echo "   cat workspace/log.txt           # Execution logs"
echo "   unzip workspace/output.zip      # Generated code"
echo ""
echo "═══════════════════════════════════════════════════════"
echo ""
print_info "For more information, see README.md"
print_info "For troubleshooting, check the logs in workspace/log.txt"
echo ""
echo "Happy coding! 🎯"