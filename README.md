# AI powered test generation

**Disclaimer:**  
This project is a learning exercise only, created to explore the interaction between git source code, language models (OpenAI & Ollama), and automated test generation.  

The output should not be relied upon, use at your own discretion.

This project extracts C source code from a git commit, summarises it using an AI model (OpenAI or Ollama), and generates Python test cases using `pytest` and `lib389`.

## Features

- Summarizes C code from git commits
- Supports OpenAI GPT-4 (cloud) and Ollama (local)
- Generates pytest test stubs based on code analysis
- Saves summaries and test cases to file prepended with the commit hash
- CLI based evaluation pipeline

---

##  Setup & Configuration
Below is the setup for the environment I used during playtime. Your setup may differ slightly.

### 1. Setup Olamma
#### 1.1 Download model
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### 1.2 Pull 7b-instruct model
```bash
ollama pull codellama:7b-instruct
```

#### 1.3 Run a Test Interaction with Ollama (Optional: Verify your model is working locally)
```bash
ollama run codellama:7b-instruct
```

### 2. Create a parent directory
```bash
mkdir -p ~/projects && cd ~/projects
```

### 3. Clone Directory Server
```bash
git clone https://github.com/389ds/389-ds-base.git
```

### 4. Clone the AI project
```bash
git clone https://github.com/jchapma/ai.git
cd ai/test-generation
```

### 5. Setup python environment
```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 6. Export OpenAI key (If you are using OpenAI, you will have to pay though...)
```bash
echo 'export OPENAI_API_KEY=[YOUR OPENAI API KEY]' >> ~/.bashrc
source ~/.bashrc
```

### 7. Usage instructions
```bash
usage: test_generation.py [-h] -r REPO -c COMMIT -m {ollama,openai} [-o OUTPUTDIR] (--summary | --train)

Summarise C source code and generate pytest stubs from a specific git commit using either OpenAI or Ollama language models. Intended as a learning exercise.

options:
  -h, --help            show this help message and exit
  -r, --repo REPO       path to the Git repository
  -c, --commit COMMIT   commit hash to analyse
  -m, --model {ollama,openai}
                        AI model to use
  -o, --outputdir OUTPUTDIR
                        output directory (default: summary)
  --summary             Run in summary mode (extracts and analyses code)
  --train               Run in training mode (Not implemented)
```



