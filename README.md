# Homework 5 - Multi-Agent Corporate Relationship Verification

## Overview:
This project implements a custom Python multi-agent system that starts with only a list of seed companies,
discovers connected companies from the public web, verifies those relationships across multiple LLM providers
(OpenAI, Gemini, and Grok), compares the results through a consensus agent, and resolves disagreements with a resolution agent.

## Video:
Here is the Google Drive Link to a video explaination of the code and to see the model running: https://drive.google.com/file/d/1JYn7s2POSsMlaSRIuQyX3SQh1U3pmVQb/view?usp=sharing

## Agents:
1. DiscoveryAgent
2. VerificationAgent
3. ConsensusAgent
4. ResolutionAgent
5. Human reviewer for unresolved cases

## Relationship labels:
- Acquisition
- Merger
- Subsidiary
- None/Unclear

## Input:
A CSV file containing only seed companies:
`data/seed_companies.csv`

## Output:
- `results/raw_discovery/`
- `results/raw_verification/`
- `results/raw_resolution/`
- `results/final_results.csv`

## Setup:
1. Create a Python environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## To Run Workflow:
Add your API keys to the .env file and then run: 

```bash
python -m src.main
```

There will be outputs in the terminal that will inform you on the progress of the model. Once complete, there will be a results folder that matches the described output above. 

## Notes:
Right now the code limits the APIS to finding only 4 connections since some of these companies have 10s of connections and since this is a self-funded homework assignment, I wanted to limit this for now. However, in the future, you can adjust that number depending on how much someone is willing to spend. 