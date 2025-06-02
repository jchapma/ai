#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 James Chapman
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import openai
import os
import re
import shutil
import sys
import time
import argparse
import requests
from pydriller import Repository
from threading import Thread, Event
from openai import OpenAI

OLLAMA_URL = "http://localhost:11434/api/generate"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MAX_CHUNK_CHARS = 2000

def is_test(filename):
    return filename.startswith("test_") or filename.endswith("_test.py")

def is_source_file(filename):
    return filename.endswith(('.c', '.h'))

def create_prompt(code):
    return f"""You are a Python developer using the lib389 library to test C code behavior via integration tests.

Your tasks are:

1. Summarize what the following C source file does, focusing on key functions and their purposes.
2. Ensure the test code includes:
   - A working `pytest` fixture to set up a temporary `lib389` server instance
   - Utility functions if needed (e.g. to add or search entries)
   - At least one or two actual test functions that assert expected behavior

Here is the C code:

```c
{code}
```"""

def show_progress(stop_event):
    spinner = ['|', '/', '-', '\\']
    idx = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\rWaiting for response... {spinner[idx % len(spinner)]}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.2)
    sys.stdout.write("\n")
    sys.stdout.flush()

def query_model(prompt, chunk, model="ollama"):
    stop_event = Event()
    temperature=0.2
    result = "No response"

    if model == "ollama":
        model_ollama="codellama:7b-instruct"

        progress_thread = Thread(target=show_progress, args=(stop_event,))

        try:
            progress_thread.start()
            start = time.time()
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": model_ollama,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json().get('response', 'No response')
            duration = time.time() - start
        except requests.RequestException as e:
            result = f"Ollama - Error {e}"
        finally:
            stop_event.set()
            progress_thread.join()
            print(f"{model} - Response for chunk {chunk} in {duration:.2f} seconds")
            return result
    
    if model == "openai":
        model_openai="gpt-4.1"
        max_tokens = 2000

        client = OpenAI(api_key=OPENAI_API_KEY)
        if not client:
            raise ValueError("OpenAI API key not found")
        
        progress_thread = Thread(target=show_progress, args=(stop_event,))

        try:
            progress_thread.start()
            start = time.time()
            response = client.chat.completions.create(
                model=model_openai,
                messages=[
                    {
                        "role": "system", "content": "You are an assistant that explains C code in detail."
                    },
                    {
                        "role": "user", "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            duration = time.time() - start
            result = response.choices[0].message.content.strip()
        except openai.OpenAIError as e:
            result = f"OpenAI Error {e}"
        finally:
            stop_event.set()
            progress_thread.join()
            print(f"{model} - Response for chunk {chunk} in {duration:.2f} seconds")
            return result


def get_single_commit(repo_path, commit_hash, output_dir):

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    for commit in Repository(repo_path, single=commit_hash).traverse_commits():
        tests = []
        code = []
        for mod in commit.modified_files:
            if mod.source_code:
                if is_test(mod.filename):
                    tests.append(mod.source_code)
                else:
                    code.append(mod.source_code)

        if tests or code:
            code_ext = '.c'
            code_path = os.path.join(output_dir, f"{commit.hash[:8]}_code{code_ext}")
            test_path = os.path.join(output_dir, f"{commit.hash[:8]}_test.py")

            if code:
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(code))
                print(f"Wrote code to {code_path}")

            if tests:
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(tests))
                print(f"Wrote tests to {test_path}")

def read_and_chunk_directory(directory):
    all_chunks = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if is_source_file(filename):
                path = os.path.join(root, filename)
                try:
                    with open(path, 'r') as f:
                        code = f.read()
                except Exception as e:
                    print(f"Failed to read {path}: {e}")
                    continue
                chunks = re.split(r'(?=^[\w\s\*]+\s+\w+\s*\([^)]*\)\s*\{)', code, flags=re.MULTILINE)
                buffer = ""
                for chunk in chunks:
                    if len(buffer) + len(chunk) < MAX_CHUNK_CHARS:
                        buffer += chunk
                    else:
                        all_chunks.append(buffer.strip())
                        buffer = chunk
                if buffer:
                    all_chunks.append(buffer.strip())
    return all_chunks

def summary_mode(model, repo, commit, outputdir):
    get_single_commit(repo, commit, outputdir)
    chunks = read_and_chunk_directory(outputdir)
    print(f"Number of chunks found {len(chunks)}")
    summaries = []
    start_time = time.time()
    for i, chunk in enumerate(chunks, 1):
        prompt = create_prompt(chunk)
        summary = query_model(prompt, i, model)
        summaries.append(f"### Function {i}\n{summary.strip()}\n")
    summary_text = "\n".join(summaries)

    output_file = os.path.join(outputdir, f"{commit[:8]}_summary.log")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary_text)

    total_time = time.time() - start_time
    print(f"\nSummary Mode - Total time: {total_time:.2f} seconds")

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Summarise C source code and generate pytest stubs from a specific git commit "
            "using either OpenAI or Ollama language models. Intended as a learning exercise."
        )
    )
    parser.add_argument("-r", "--repo", required=True, help="path to the Git repository")
    parser.add_argument("-c", "--commit", required=True, help="commit hash to analyse")
    parser.add_argument("-m", "--model", required=True, choices=["ollama", "openai"], help="AI model to use")
    parser.add_argument("-o", "--outputdir", required=False,  default="summary", help="output directory (default: summary)")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--summary", action="store_true", help="Run in summary mode (extracts and analyses code)")
    mode_group.add_argument("--train", action="store_true", help="Run in training mode (Not implemented)")

    args = parser.parse_args()

    if args.summary:
        print("Summary mode")
        os.makedirs(args.outputdir, exist_ok=True)
        summary_mode(args.model, args.repo, args.commit, args.outputdir)
    elif args.train:
        print("Train mode")

if __name__ == "__main__":
    main()
