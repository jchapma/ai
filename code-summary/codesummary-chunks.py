#!/usr/bin/python

from openai import OpenAI
import time
import requests
import re
import openai
import os
import sys

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
OPENAI_API_KEY="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"
openai.api_key = OPENAI_API_KEY
MAX_CHUNK_CHARS = 3000

def read_and_chunk_file(path):
    try:
        with open(path, 'r') as f:
            code = f.read()
    except Exception as e:
        print(f"[Error] Failed to read file: {e}")
        sys.exit(1)

    # Simple split: split on function headers
    chunks = re.split(r'(?=^[\w\s\*]+\s+\w+\s*\([^)]*\)\s*\{)', code, flags=re.MULTILINE)

    # Merge small chunks to fit size constraint
    final_chunks, buffer = [], ""
    for chunk in chunks:
        if len(buffer) + len(chunk) < MAX_CHUNK_CHARS:
            buffer += chunk
        else:
            final_chunks.append(buffer.strip())
            buffer = chunk
    if buffer:
        final_chunks.append(buffer.strip())

    return final_chunks


def create_prompt(c_code_chunks):
    joined_code = "\n\n".join(c_code_chunks).strip()
    return (
        "Generate a single Python pytest test file using lib389 to test LDAP operations on a 389 Directory Server.\n"
        "The tests should cover search, add, modify, and delete operations based on the following C code functions.\n"
        "Use lib389's DirectoryManager and search_s API in the tests.\n"
        "Output ONLY the Python test code, no explanations.\n\n"
        f"{joined_code}\n"
    )


def query_model(prompt, use_openai=False, max_tokens=1000, temperature=0.2, model_ollama="codellama:7b-instruct", model_openai="gpt-4.1"):

    if use_openai:
        client = OpenAI(api_key=OPENAI_API_KEY)
        if not client:
            raise ValueError("OpenAI API key not found !")
        try:
            start = time.time()
            response = client.chat.completions.create(
                model=model_openai,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an assistant that explains C code in detail."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            duration = time.time() - start
            print(f"[OpenAI] Response in {duration:.2f} seconds.")
            return response.choices[0].message.content.strip()
        except openai.OpenAIError as e:
            return f"[OpenAI Error] {e}"
    else:
        try:
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
            duration = time.time() - start
            print(f"[Ollama] Response in {duration:.2f} seconds.")
            return response.json().get('response', '[No response]')
        except requests.RequestException as e:
            return f"[Ollama Error] {e}"

def main():

    if len(sys.argv) < 2:
        print("Usage: python summarize_c_code.py <path_to_c_file> [--openai]")
        return

    use_openai = "--openai" in sys.argv
    file_path = sys.argv[1]
    max_tokens = 1000

    chunks = read_and_chunk_file(file_path)
    print(f"Found {len(chunks)} code block(s).\n")

    summaries = []
    for i, chunk in enumerate(chunks, 1):
        prompt = create_prompt(chunk)
        summary = query_model(prompt, use_openai, max_tokens)
        summaries.append(f"Function {i}:\n{summary}\n")
    print("\n".join(summaries))

if __name__ == "__main__":
    main()

