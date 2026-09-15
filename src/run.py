import os
import json
import time
import csv
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai import types

from prompt import SYSTEM_PROMPT, format_user_prompt
from score import score

# Load environment variables (API Keys)
load_dotenv()

# --- Config ---
DB_PATH = "chinook.db"
INPUT_DATA = "data/items.jsonl"
OUTPUT_CSV = "results/per_item.csv"

# Make sure results directory exists
os.makedirs("results", exist_ok=True)

# --- Initialize Clients ---
# 1. LM Studio (Local)
local_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
LOCAL_MODEL_NAME = "gemma-4-12b-heretic-abliterated@q6_k" # Change to exactly match your LM Studio model

# 2. Gemini (Cheap API)
try:
    gemini_client = genai.Client() # Picks up GEMINI_API_KEY from environment
    GEMINI_MODEL_NAME = "gemini-3.1-flash-lite"
except Exception as e:
    print(f"Warning: Could not initialize Gemini client. Check .env file. Error: {e}")
    gemini_client = None

def evaluate_model(client_type, model_name, question, gold_sql):
    t0 = time.perf_counter()
    input_tokens = 0
    output_tokens = 0
    raw_output = ""
    
    try:
        if client_type == "local":
            response = local_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": format_user_prompt(question)},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            raw_output = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            
        elif client_type == "gemini":
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=format_user_prompt(question),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=256,
                )
            )
            raw_output = response.text
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count

    except Exception as e:
        raw_output = f"API_ERROR: {str(e)}"
        return (time.perf_counter() - t0) * 1000, 0, "refusal/timeout", 0, 0, raw_output

    latency_ms = (time.perf_counter() - t0) * 1000.0
    is_correct, status, parsed_sql = score(DB_PATH, raw_output, gold_sql)
    
    return latency_ms, is_correct, status, input_tokens, output_tokens, parsed_sql


def main():
    with open(INPUT_DATA, "r") as f:
        items = [json.loads(line) for line in f]

    results = []
    
    print(f"Starting evaluation of {len(items)} items...")
    
    for item in items:
        item_id = item["id"]
        q = item["question"]
        gold = item["gold_sql"]
        
        print(f"Processing Item {item_id}: {q[:40]}...")

        # 1. Run Local Model
        print(f"  -> Querying {LOCAL_MODEL_NAME}...")
        lat_ms, is_corr, status, in_tok, out_tok, sql = evaluate_model("local", LOCAL_MODEL_NAME, q, gold)
        results.append([item_id, LOCAL_MODEL_NAME, round(lat_ms, 2), is_corr, status, in_tok, out_tok, sql])
        
        # 2. Run Gemini Flash (if configured)
        if gemini_client:
            print(f"  -> Querying {GEMINI_MODEL_NAME}...")
            # Gentle sleep to respect rate limits on the free tier if needed
            time.sleep(1) 
            lat_ms, is_corr, status, in_tok, out_tok, sql = evaluate_model("gemini", GEMINI_MODEL_NAME, q, gold)
            results.append([item_id, GEMINI_MODEL_NAME, round(lat_ms, 2), is_corr, status, in_tok, out_tok, sql])

    # Write to CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["item_id", "model", "latency_ms", "is_correct", "status", "input_tokens", "output_tokens", "output_sql"])
        writer.writerows(results)
        
    print(f"\nEvaluation complete! Results saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()