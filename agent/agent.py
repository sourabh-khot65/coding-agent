#!/usr/bin/env python3
"""
Coding Agent - Generates and executes code using LLMs
Supports Groq and OpenAI APIs with comprehensive error handling and security
"""

import os
import sys
import json
import zipfile
import logging
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import contextmanager
from enum import Enum
import re

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("openai package is required. Install with: pip install openai")

try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
except ImportError:
    # dotenv is optional, continue without it
    pass


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETE = "complete"
    ERROR = "error"


class LLMProvider(Enum):
    """Supported LLM providers"""
    GROQ = "groq"
    OPENAI = "openai"


def get_env_bool(key: str, default: bool = True) -> bool:
    """Get boolean value from environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def validate_environment() -> None:
    """Validate required environment variables"""
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("GROQ_API_KEY"):
        print("❌ Error: No LLM API key found!")
        print("Please set one of the following environment variables:")
        print("  • OPENAI_API_KEY (recommended)")
        print("  • GROQ_API_KEY (free alternative)")
        print()
        print("You can:")
        print("  1. Edit your .env file: nano .env")
        print("  2. Run setup: ./setup.sh")
        print("  3. Set directly: export OPENAI_API_KEY='your_key'")
        sys.exit(1)


@dataclass
class AgentConfig:
    """Configuration for the coding agent"""
    workspace: Path = field(default_factory=lambda: Path(os.getenv('WORKSPACE_DIR', './workspace')))
    task_file: str = 'task.txt'
    status_file: str = 'status.txt'
    log_file: str = 'log.txt'
    output_zip: str = 'output.zip'
    max_log_size: int = field(default_factory=lambda: int(os.getenv('MAX_LOG_SIZE', '1000000')))
    max_log_lines: int = field(default_factory=lambda: int(os.getenv('MAX_LOG_LINES', '1000')))
    command_timeout: int = field(default_factory=lambda: int(os.getenv('COMMAND_TIMEOUT', '120')))
    max_tokens: int = field(default_factory=lambda: int(os.getenv('MAX_TOKENS', '4096')))
    temperature: float = field(default_factory=lambda: float(os.getenv('TEMPERATURE', '0.1')))
    enable_security: bool = field(default_factory=lambda: get_env_bool('ENABLE_SECURITY_VALIDATION', True))
    
    def __post_init__(self):
        """Initialize workspace directory and validate configuration"""
        self.workspace = Path(self.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        if self.max_tokens < 100 or self.max_tokens > 32768:
            raise ValueError(f"MAX_TOKENS must be between 100 and 32768, got: {self.max_tokens}")
        
        if self.temperature < 0.0 or self.temperature > 2.0:
            raise ValueError(f"TEMPERATURE must be between 0.0 and 2.0, got: {self.temperature}")
        
        if self.command_timeout < 10 or self.command_timeout > 3600:
            raise ValueError(f"COMMAND_TIMEOUT must be between 10 and 3600 seconds, got: {self.command_timeout}")
    
    @property
    def task_path(self) -> Path:
        return self.workspace / self.task_file
    
    @property
    def status_path(self) -> Path:
        return self.workspace / self.status_file
    
    @property
    def log_path(self) -> Path:
        return self.workspace / self.log_file
    
    @property
    def output_zip_path(self) -> Path:
        return self.workspace / self.output_zip
    
    def print_config(self) -> None:
        """Print current configuration for debugging"""
        print(f"Configuration:")
        print(f"  Workspace: {self.workspace}")
        print(f"  Max Tokens: {self.max_tokens}")
        print(f"  Temperature: {self.temperature}")
        print(f"  Command Timeout: {self.command_timeout}s")
        print(f"  Security Validation: {self.enable_security}")


class AgentLogger:
    """Centralized logging for the agent"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger with file and console handlers"""
        logger = logging.getLogger('coding_agent')
        
        # Set log level from environment
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        try:
            level = getattr(logging, log_level)
        except AttributeError:
            level = logging.INFO
            print(f"⚠️  Invalid LOG_LEVEL '{log_level}', using INFO")
        
        logger.setLevel(level)
        logger.handlers.clear()
        
        # Create handlers
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(self.config.log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def info(self, message: str) -> None:
        self.logger.info(message)
    
    def error(self, message: str, exc_info: bool = False) -> None:
        self.logger.error(message, exc_info=exc_info)
    
    def warning(self, message: str) -> None:
        self.logger.warning(message)
    
    def debug(self, message: str) -> None:
        self.logger.debug(message)
    
    def prune_if_needed(self) -> None:
        """Prune log file if it exceeds size limit"""
        try:
            if (self.config.log_path.exists() and 
                self.config.log_path.stat().st_size > self.config.max_log_size):
                
                with open(self.config.log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-self.config.max_log_lines:]
                
                with open(self.config.log_path, 'w', encoding='utf-8') as f:
                            f.writelines(lines)

                self.info(f"Pruned log file to {self.config.max_log_lines} lines")
        except Exception as e:
            self.error(f"Failed to prune log file: {e}")


class LLMClient:
    """Client for interacting with LLM APIs"""
    
    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self.provider, self.client = self._setup_client()

    def _setup_client(self) -> Tuple[LLMProvider, OpenAI]:
        """Setup LLM client based on available API keys"""
        groq_key = os.environ.get("GROQ_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        
        if groq_key and groq_key != "your_groq_api_key_here":
            self.logger.info("Using Groq API")
            client = OpenAI(
                api_key=groq_key,
                base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                timeout=30.0,
                max_retries=3
            )
            return LLMProvider.GROQ, client
        elif openai_key and openai_key != "your_openai_api_key_here":
            self.logger.info("Using OpenAI API")
            client = OpenAI(api_key=openai_key, timeout=30.0, max_retries=3)
            return LLMProvider.OPENAI, client
        else:
            raise ValueError("No valid LLM API key found. Set GROQ_API_KEY or OPENAI_API_KEY")
    
    def call(self, prompt: str, config: AgentConfig) -> str:
        """Call the LLM API with the given prompt"""
        # Get model from environment or use defaults
        if self.provider == LLMProvider.GROQ:
            model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
        else:
            model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        
        try:
            self.logger.info(f"Calling {self.provider.value} API with model {model}")
            self.logger.debug(f"Request params - tokens: {config.max_tokens}, temp: {config.temperature}")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a coding agent that generates code and shell commands. Always respond with valid JSON containing 'files' and 'shell' keys."},
                {"role": "user", "content": prompt}
            ],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")
            
            self.logger.debug(f"LLM response length: {len(content)} characters")
            return content
            
        except Exception as e:
            error_msg = f"LLM API call failed: {str(e)}"
            self.logger.error(error_msg)
            
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"HTTP status: {e.response.status_code}")
                self.logger.error(f"Response body: {e.response.text}")
            
            # Provide helpful error messages
            if "401" in str(e) or "authentication" in str(e).lower():
                self.logger.error("Authentication failed. Please check your API key.")
                self.logger.error("Edit your .env file or run ./setup.sh to configure API keys.")
            elif "quota" in str(e).lower() or "billing" in str(e).lower():
                self.logger.error("API quota exceeded. Please check your account billing and limits.")
            
            raise RuntimeError(error_msg) from e


class TaskManager:
    """Manages task reading and validation"""
    
    def __init__(self, config: AgentConfig, logger: AgentLogger):
        self.config = config
        self.logger = logger
    
    def read_task(self) -> str:
        """Read and validate the task from task file"""
        try:
            if not self.config.task_path.exists():
                # Create a default task file if it doesn't exist
                default_task = "Create a simple 'Hello World' Python script that prints a greeting message."
                with open(self.config.task_path, 'w', encoding='utf-8') as f:
                    f.write(default_task)
                self.logger.info(f"Created default task file: {self.config.task_path}")
                return default_task
            
            with open(self.config.task_path, 'r', encoding='utf-8') as f:
                task = f.read().strip()
            
            if not task:
                raise ValueError("Task file is empty")
            
            # Security validation if enabled
            if self.config.enable_security:
                self._validate_task_security(task)
            
            return task
        except Exception as e:
            self.logger.error(f"Failed to read task: {e}")
            raise
    
    def _validate_task_security(self, task: str) -> None:
        """Validate task for security concerns"""
        dangerous_patterns = [
            r'rm\s+-rf\s+/', r'sudo\s+rm', r'curl.*\|\s*bash', r'wget.*\|\s*sh',
            r'chmod\s+777', r'>/dev/null.*&', r'nc\s+-l', r'python.*-c.*import.*os'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, task, re.IGNORECASE):
                self.logger.warning(f"Potentially dangerous pattern detected in task: {pattern}")


class FileManager:
    """Manages file operations with security and error handling"""
    
    def __init__(self, config: AgentConfig, logger: AgentLogger):
        self.config = config
        self.logger = logger
    
    def write_files(self, files: Dict[str, str]) -> None:
        """Write multiple files with validation"""
        self.logger.info(f"Writing {len(files)} files")
        for filename, content in files.items():
            self._write_file(filename, content)
    
    def _write_file(self, filename: str, content: str) -> None:
        """Write a single file with security checks"""
        try:
            # Security validation if enabled
            if self.config.enable_security:
                self._validate_filename_security(filename)
            
            file_path = self.config.workspace / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            file_size = len(content.encode('utf-8'))
            self.logger.info(f"Successfully wrote file: {filename} ({file_size} bytes)")
            
        except Exception as e:
            self.logger.error(f"Failed to write file {filename}: {e}")
            raise
    
    def _validate_filename_security(self, filename: str) -> None:
        """Validate filename for security"""
        # Prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            raise ValueError(f"Invalid filename (security): {filename}")
        
        # Prevent writing to sensitive areas
        dangerous_paths = ['etc', 'var', 'bin', 'usr', 'sys', 'proc', 'dev']
        if any(part in dangerous_paths for part in Path(filename).parts):
            raise ValueError(f"Invalid filename (dangerous path): {filename}")
        
        # Prevent executable extensions in sensitive locations
        dangerous_extensions = ['.sh', '.bat', '.cmd', '.exe', '.scr']
        if Path(filename).suffix.lower() in dangerous_extensions:
            self.logger.warning(f"Executable file detected: {filename}")
    
    def create_output_zip(self) -> None:
        """Create ZIP file of all generated files"""
        try:
            excluded_files = {
                self.config.output_zip, self.config.status_file,
                self.config.log_file, self.config.task_file
            }
            
            files_added = 0
            with zipfile.ZipFile(self.config.output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in self.config.workspace.rglob('*'):
                    if file_path.is_file() and file_path.name not in excluded_files:
                        relative_path = file_path.relative_to(self.config.workspace)
                        zipf.write(file_path, relative_path)
                        files_added += 1
            
            zip_size = self.config.output_zip_path.stat().st_size
            self.logger.info(f"Created output ZIP: {self.config.output_zip_path} ({files_added} files, {zip_size} bytes)")
            
        except Exception as e:
            self.logger.error(f"Failed to create output ZIP: {e}")
            raise


class CommandExecutor:
    """Executes shell commands with security and monitoring"""
    
    def __init__(self, config: AgentConfig, logger: AgentLogger):
        self.config = config
        self.logger = logger
    
    def execute_commands(self, commands: List[str]) -> None:
        """Execute multiple shell commands"""
        if not commands:
            self.logger.info("No shell commands to execute")
            return
            
        self.logger.info(f"Executing {len(commands)} shell commands")
        for i, command in enumerate(commands, 1):
            self.logger.info(f"Command {i}/{len(commands)}: {command}")
            self._execute_command(command)
    
    def _execute_command(self, command: str) -> None:
        """Execute a single shell command with security checks"""
        try:
            # Security validation if enabled
            if self.config.enable_security:
                self._validate_command_security(command)
            
            self.logger.debug(f"Executing command: {command}")
            
            process = subprocess.run(
                command, shell=True, cwd=str(self.config.workspace),
                timeout=self.config.command_timeout, capture_output=True,
                text=True, check=False
            )
            
            if process.stdout:
                self.logger.info(f"Command output: {process.stdout.strip()}")
            if process.stderr:
                self.logger.warning(f"Command stderr: {process.stderr.strip()}")
            if process.returncode != 0:
                self.logger.warning(f"Command failed with exit code {process.returncode}")
            else:
                self.logger.debug(f"Command completed successfully")
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after {self.config.command_timeout}s: {command}")
            self.logger.error("Consider increasing COMMAND_TIMEOUT in your .env file")
        except Exception as e:
            self.logger.error(f"Failed to execute command '{command}': {e}")
            raise
    
    def _validate_command_security(self, command: str) -> None:
        """Validate command for security"""
        dangerous_patterns = [
            r'rm\s+-rf\s+/', r'sudo\s+rm', r'chmod\s+777', r'curl.*\|\s*(bash|sh)',
            r'wget.*\|\s*(bash|sh)', r'eval\s+', r'exec\s+', r'/dev/tcp',
            r'nc\s+-l', r'python.*-c.*import.*os', r'>\s*/dev/null.*&'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise ValueError(f"Dangerous command pattern detected: {pattern}")


class ResponseParser:
    """Parses and validates LLM responses"""
    
    def __init__(self, logger: AgentLogger):
        self.logger = logger
    
    def parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response with robust error handling"""
        try:
            self.logger.debug("Parsing LLM response")
            json_str = self._clean_json_response(response)
            result = json.loads(json_str)
            self._validate_response_structure(result)
            
            # Log response summary
            files_count = len(result.get('files', {}))
            commands_count = len(result.get('shell', []))
            self.logger.info(f"Parsed response: {files_count} files, {commands_count} commands")
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            self.logger.error(f"Raw response: {response[:500]}...")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            raise
    
    def _clean_json_response(self, response: str) -> str:
        """Clean JSON response by removing markdown and extracting JSON"""
        json_str = response.strip()
        
        # Remove markdown code blocks
        if json_str.startswith('```json'):
            json_str = json_str[7:]
        elif json_str.startswith('```'):
            json_str = json_str[3:]
        if json_str.endswith('```'):
            json_str = json_str[:-3]
        
        json_str = json_str.strip()
        
        # Extract JSON object
        try:
            start = json_str.find('{')
            if start == -1:
                raise ValueError("No JSON object found in response")
            
            brace_count = 0
            end = start
            
            for i in range(start, len(json_str)):
                if json_str[i] == '{':
                    brace_count += 1
                elif json_str[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            json_str = json_str[start:end]
        except Exception:
            pass  # Use cleaned string as-is if extraction fails
        
        return json_str
    
    def _validate_response_structure(self, response: Dict[str, Any]) -> None:
        """Validate that response has expected structure"""
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
        
        if 'files' in response:
            files = response['files']
            if not isinstance(files, dict):
                raise ValueError("'files' must be a dictionary")
            for filename, content in files.items():
                if not isinstance(filename, str) or not isinstance(content, str):
                    raise ValueError("File entries must be string key-value pairs")
        
        if 'shell' in response:
            shell = response['shell']
            if not isinstance(shell, list):
                raise ValueError("'shell' must be a list")
            for command in shell:
                if not isinstance(command, str):
                    raise ValueError("Shell commands must be strings")


class CodingAgent:
    """Main coding agent class"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        # Validate environment before initialization
        validate_environment()
        
        self.config = config or AgentConfig()
        self.logger = AgentLogger(self.config)
        
        # Print configuration in debug mode
        if os.getenv('LOG_LEVEL', '').upper() == 'DEBUG':
            self.config.print_config()
        
        self.llm_client = LLMClient(self.logger)
        self.task_manager = TaskManager(self.config, self.logger)
        self.file_manager = FileManager(self.config, self.logger)
        self.command_executor = CommandExecutor(self.config, self.logger)
        self.response_parser = ResponseParser(self.logger)
    
    def run(self) -> None:
        """Main execution method"""
        self.logger.info("🚀 Coding agent started")
        self.logger.prune_if_needed()
        
        try:
            self._update_status(JobStatus.RUNNING)
            
            # Read and process task
            task = self.task_manager.read_task()
            self.logger.info(f"📋 Task: {task[:200]}{'...' if len(task) > 200 else ''}")
            
            # Generate and call LLM
            prompt = self._create_prompt(task)
            llm_response = self.llm_client.call(prompt, self.config)
            self.logger.info("✅ Received response from LLM")
            
            # Parse and execute response
            parsed_response = self.response_parser.parse_llm_response(llm_response)
            self._execute_response(parsed_response)
            
            # Package output
            self.file_manager.create_output_zip()
            self._update_status(JobStatus.COMPLETE)
            self.logger.info("🎉 Job completed successfully")
            
            # Print success message
            print("\n" + "="*60)
            print("🎯 TASK COMPLETED SUCCESSFULLY!")
            print("="*60)
            print(f"📁 Generated files are in: {self.config.workspace}")
            print(f"📦 Download package: {self.config.output_zip_path}")
            print(f"📊 View logs: {self.config.log_path}")
            print("="*60)
            
        except Exception as e:
            self.logger.error(f"💥 Job failed: {e}", exc_info=True)
            self._update_status(JobStatus.ERROR)
        
            # Print error guidance
            print("\n" + "="*60)
            print("❌ TASK FAILED")
            print("="*60)
            print("Troubleshooting steps:")
            print("1. Check logs:", self.config.log_path)
            print("2. Verify API key in .env file")
            print("3. Check task complexity and API limits")
            print("4. Run with LOG_LEVEL=DEBUG for detailed info")
            print("="*60)
            raise
    
    def _create_prompt(self, task: str) -> str:
        """Create prompt for LLM"""
        return f"""
You are a coding agent. Generate ONLY a valid JSON object with these keys:
- files: dict of filename to file content  
- shell: list of shell commands to run

Rules:
- Return ONLY valid JSON, no markdown, no extra text
- Use simple file content without complex escaping
- Keep shell commands simple and safe
- No dangerous commands (rm -rf, sudo, etc.)
- Create functional, well-commented code
- Include proper file structure for the project
- Task: {task}

Example: {{"files": {{"index.html": "<!DOCTYPE html>..."}}, "shell": ["npm init -y", "npm install"]}}
"""
    
    def _execute_response(self, response: Dict[str, Any]) -> None:
        """Execute the parsed LLM response"""
        if 'files' in response:
            self.file_manager.write_files(response['files'])
        if 'shell' in response:
            self.command_executor.execute_commands(response['shell'])
    
    def _update_status(self, status: JobStatus) -> None:
        """Update job status"""
        try:
            with open(self.config.status_path, 'w', encoding='utf-8') as f:
                f.write(status.value)
            self.logger.info(f"Status updated to: {status.value}")
        except Exception as e:
            self.logger.error(f"Failed to update status: {e}")
            raise


@contextmanager
def error_context(operation: str, logger: AgentLogger):
    """Context manager for error handling"""
    try:
        yield
    except Exception as e:
        logger.error(f"Error during {operation}: {e}", exc_info=True)
        raise


def main():
    """Main entry point"""
    try:
        agent = CodingAgent()
        with error_context("agent execution", agent.logger):
            agent.run()
    except Exception as e:
        print(f"\n💥 Critical error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main() 