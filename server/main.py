#!/usr/bin/env python3
"""
FastAPI Orchestration Server for Coding Agent System
Handles job scheduling and Docker container management
"""

import os
import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import docker

# Configuration
JOBS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../jobs'))
AGENT_IMAGE = 'coding-agent'

# FastAPI setup
app = FastAPI(title="Coding Agent API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Docker client
client = docker.from_env()

class ScheduleRequest(BaseModel):
    task: str

@app.get("/")
def root():
    """API status endpoint"""
    return {"status": "Coding Agent API is running"}

@app.post('/schedule')
async def schedule(request: Request):
    """Schedule a new coding job"""
    try:
        # Accept both JSON and plain text
        try:
            data = await request.json()
            task = data.get('task')
        except Exception:
            task = (await request.body()).decode()
        
        if not task:
            raise HTTPException(status_code=400, detail='No task provided')
        
        # Create job
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Write task file
        with open(os.path.join(job_dir, 'task.txt'), 'w') as f:
            f.write(task)
        
        # Prepare environment variables
        env_vars = {}
        if os.environ.get('GROQ_API_KEY'):
            env_vars['GROQ_API_KEY'] = os.environ.get('GROQ_API_KEY')
        if os.environ.get('OPENAI_API_KEY'):
            env_vars['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY')
        if os.environ.get('GROQ_BASE_URL'):
            env_vars['GROQ_BASE_URL'] = os.environ.get('GROQ_BASE_URL')
        
        # Start agent container
        client.containers.run(
            AGENT_IMAGE,
            volumes={job_dir: {'bind': '/workspace', 'mode': 'rw'}},
            environment=env_vars,
            detach=True,
            working_dir='/app',
            name=f'agent-{job_id[:8]}'
        )
        
        return {'job_id': job_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to schedule job: {str(e)}')

@app.get('/status/{job_id}')
def status(job_id: str):
    """Get job status"""
    job_dir = os.path.join(JOBS_DIR, job_id)
    status_file = os.path.join(job_dir, 'status.txt')
    output_zip = os.path.join(job_dir, 'output.zip')
    
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail='Job not found')
    
    if os.path.exists(status_file):
        if os.path.exists(output_zip):
            return JSONResponse({
                'status': 'complete',
                'download': f'/download/{job_id}'
            })
        else:
            return {'status': 'complete', 'download': None}
    else:
        return {'status': 'running'}

@app.get('/download/{job_id}')
def download(job_id: str):
    """Download job output"""
    job_dir = os.path.join(JOBS_DIR, job_id)
    output_zip = os.path.join(job_dir, 'output.zip')
    
    if not os.path.exists(output_zip):
        raise HTTPException(status_code=404, detail='Output not found')
    
    return FileResponse(output_zip, filename='output.zip')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 