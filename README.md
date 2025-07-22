# Coding Agent

Coding agent that generates and executes code using LLMs with comprehensive error handling and security.

## Features

- **🤖 Multi-LLM Support**: OpenAI and Groq APIs with automatic retry logic
- **🔧 Environment Configuration**: Flexible configuration via .env files
- **🔒 Security Features**: Input validation, command filtering, sandboxed execution
- **📦 Auto-packaging**: Generated code automatically zipped for download
- **📊 Comprehensive Logging**: Structured logging with configurable levels

## Quick Start

### 1. Setup Environment

```bash
# Automated setup
chmod +x setup.sh
./setup.sh
```

### 2. Configure API Keys

Edit the `.env` file and add your API key:
```bash
nano .env
```

Add one of the following:
```env
# OpenAI API (recommended)
OPENAI_API_KEY=your_openai_api_key_here

# OR Groq API (free alternative)
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Run the Agent

```bash
# Create a task
echo "Create a React todo app with TypeScript" > workspace/task.txt

# Run the agent
source venv/bin/activate
python agent/agent.py

# Check results
cat workspace/status.txt
unzip workspace/output.zip -d generated_code/
```

## Environment Variables

Configure the agent by setting these variables in your `.env` file:

### **API Configuration**
```env
OPENAI_API_KEY=your_key          # OpenAI API key
GROQ_API_KEY=your_key            # Groq API key (alternative)
GROQ_BASE_URL=custom_endpoint    # Custom Groq endpoint
```

### **Agent Settings**
```env
WORKSPACE_DIR=./workspace        # Working directory
MAX_TOKENS=4096                  # Maximum tokens per request
TEMPERATURE=0.1                  # LLM creativity (0.0-1.0)
COMMAND_TIMEOUT=120              # Shell command timeout (seconds)
```

### **Logging**
```env
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
MAX_LOG_SIZE=1000000            # Max log file size
MAX_LOG_LINES=1000              # Max log lines to keep
```

### **Security**
```env
ENABLE_SECURITY_VALIDATION=true # Enable security checks
```

### **Custom Models**
```env
OPENAI_MODEL=gpt-4o             # Override default OpenAI model
GROQ_MODEL=llama-3.3-70b-versatile # Override default Groq model
```

## Project Structure

```
coding-agent/
├── agent/
│   └── agent.py              # Main agent implementation
├── workspace/                # Agent working directory
│   ├── task.txt             # Input task file
│   ├── log.txt              # Execution logs
│   ├── status.txt           # Job status
│   └── output.zip           # Generated code package
├── .env.example             # Environment template
├── .env                     # Your configuration
├── requirements.txt         # Dependencies
├── setup.sh                # Setup script
└── README.md               # This file
```

## Configuration Examples

### Development
```env
OPENAI_API_KEY=your_key
LOG_LEVEL=DEBUG
TEMPERATURE=0.2
COMMAND_TIMEOUT=60
```

### Production
```env
GROQ_API_KEY=your_key
LOG_LEVEL=INFO
TEMPERATURE=0.1
COMMAND_TIMEOUT=300
ENABLE_SECURITY_VALIDATION=true
```

## Requirements

- Python 3.8+
- OpenAI API key OR Groq API key
- 500MB+ free disk space

## Troubleshooting

**"No valid LLM API key found"**
- Check your `.env` file contains a valid API key
- Run `source venv/bin/activate` to load environment

**"Command timed out"**
- Increase `COMMAND_TIMEOUT` in `.env`
- Check if generated commands are appropriate

**"Empty response from LLM"**
- Check API key balance/quota
- Try reducing `MAX_TOKENS` or increasing `TEMPERATURE`

### Debug Mode
```env
LOG_LEVEL=DEBUG
```

---

Built with ❤️ for automated code generation 