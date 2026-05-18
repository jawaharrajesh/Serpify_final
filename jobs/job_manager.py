import uuid
import time
import threading
import subprocess
import sys
import os
import json
import tempfile
import shutil

from analytics.db import get_conn

MAX_CONCURRENT_JOBS = 2
lock = threading.Lock()

# 🧹 1. STARTUP CLEANUP (Prevents permanent deadlocks on server restart)
def cleanup_stuck_jobs():
    conn = get_conn()
    conn.execute(
        "UPDATE jobs SET status='failed', error='Server rebooted' WHERE status='running'"
    )
    conn.commit()
    conn.close()

# Run once when the app starts
cleanup_stuck_jobs()

def get_running_jobs_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jobs WHERE status='running'")
    count = cur.fetchone()[0]
    conn.close()
    return count

def create_job(user_id, tool, params):
    job_id = str(uuid.uuid4())
    conn = get_conn()
    cur = conn.cursor()
    
    # Jobs start as "queued"
    cur.execute("""
        INSERT INTO jobs (job_id, user_id, tool, status, params, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_id, user_id, tool, "queued", json.dumps(params), time.time()))
    
    conn.commit()
    conn.close()
    return job_id

def update_job_status(job_id, status):
    conn = get_conn()
    conn.execute("UPDATE jobs SET status=? WHERE job_id=?", (status, job_id))
    conn.commit()
    conn.close()

def update_job(job_id, status, result_json=None, result_excel=None, error=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE jobs
        SET status=?, result_json=?, result_excel=?, error=?
        WHERE job_id=?
    """, (status, result_json, result_excel, error, job_id))
    conn.commit()
    conn.close()

def get_job(job_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return row

# 🚀 CORE EXECUTION FUNCTION
def run_job(job_id, script_builder):
    tmp_dir = None
    try:
        # 1. Wait for a slot
        while True:
            if get_running_jobs_count() < MAX_CONCURRENT_JOBS:
                with lock:
                    if get_running_jobs_count() < MAX_CONCURRENT_JOBS:
                        update_job_status(job_id, "running")
                        break
            time.sleep(2)

        # 2. Setup paths - CRITICAL FIX FOR ONEDRIVE
        # Using tempfile.mkdtemp() creates a folder in the SYSTEM temp dir, 
        # which OneDrive cannot "lock" or "sync".
        tmp_dir = tempfile.mkdtemp(prefix=f"serpify_{job_id}_")
        
        os.makedirs("results", exist_ok=True)
        json_path = os.path.abspath(os.path.join("results", f"{job_id}.json"))
        
        script = script_builder(json_path)
        script_file = os.path.join(tmp_dir, "spider_run.py")

        # 3. Write the spider file
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script)

        # 4. Execute the spider
        process = subprocess.Popen(
            [sys.executable, "spider_run.py"],
            cwd=tmp_dir, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        stdout, stderr = process.communicate()

        # 5. Finalize
        if os.path.exists(json_path):
            update_job(job_id, "completed", result_json=json_path)
        else:
            raise Exception(f"No output generated. Stderr: {stderr[-500:]}")
            
    except Exception as e:
        update_job(job_id, "failed", error=str(e))
    
    finally:
        # 6. Safe Cleanup
        # We wrap this in a try-block because OneDrive sometimes keeps a lock 
        # even on system temp files for a few milliseconds.
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except:
                pass

def start_job(user_id, tool, params, script_builder):
    job_id = create_job(user_id, tool, params)
    thread = threading.Thread(target=run_job, args=(job_id, script_builder))
    thread.start()
    return job_id