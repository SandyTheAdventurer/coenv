"""
COEnv Inference Script
Used by validators to run episodes with LLMs
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, Any, Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen3-30B")
HF_TOKEN = os.getenv("HF_TOKEN")


def main():
    parser = argparse.ArgumentParser(description='Run COEnv inference')
    parser.add_argument('--api-base-url', type=str, default=API_BASE_URL, help='Base URL for the COEnv API')
    parser.add_argument('--model-name', type=str, default=MODEL_NAME, help='Name of the model to use')
    parser.add_argument('--hf-token', type=str, default=HF_TOKEN, help='Hugging Face token (if needed)')
    parser.add_argument('--task-id', type=str, default='pod_recovery', help='Task ID to run')
    parser.add_argument('--max-steps', type=int, default=15, help='Maximum steps per episode')
    
    args = parser.parse_args()
    
    api_base_url = args.api_base_url.rstrip('/')
    model_name = args.model_name
    hf_token = args.hf_token or HF_TOKEN
    task_id = args.task_id
    max_steps = args.max_steps
    
    print(f"[START] task={task_id} env=coenv model={model_name}")
    
    reset_url = f"{api_base_url}/reset"
    try:
        response = requests.post(reset_url, json={"task": task_id})
        response.raise_for_status()
        observation = response.json()
    except Exception as e:
        print(f"[ERROR] Failed to reset environment: {e}")
        return 1
    
    total_reward = []
    
    for step in range(1, max_steps + 1):
        action = {
            "action_type": "describe",
            "resource_type": "deployment",
            "name": "frontend"
        }
        action_str = f"describe('deployment','frontend')"
        
        step_url = f"{api_base_url}/step"
        try:
            response = requests.post(step_url, json={"action": action})
            response.raise_for_status()
            result = response.json()
            
            reward = result.get('reward', 0.0)
            done = result.get('done', False)
            info = result.get('info', {})
            error_str = "null"
            
            if 'error' in info and info['error']:
                error_str = f"\"{info['error']}\""
            
            total_reward.append(reward)
            
            print(f"[STEP] step={step} action={action_str} reward={reward:.2f} done={done} error={error_str}")
            
            if done:
                print(f"[END] success={str(done).lower()} steps={step} rewards={total_reward}")
                return 0
                
        except Exception as e:
            print(f"[ERROR] Failed to step environment: {e}")
            print(f"[STEP] step={step} action={action_str} reward=0.00 done=false error=\"{str(e)}\"")
    
    print(f"[END] success=false steps={max_steps} rewards={total_reward}")
    return 0


if __name__ == "__main__":
    sys.exit(main())