from pathlib import Path
import pandas as pd

from src.agents import Orchestrator

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

def load_seed_companies():
    input_path = DATA_DIR / "seed_companies.csv"
    df = pd.read_csv(input_path)
    return df["company_name"].dropna().astype(str).tolist()

def main():
    seed_companies = load_seed_companies()
    print(f"Loaded {len(seed_companies)} seed companies")

    orchestrator = Orchestrator()
    output_path = RESULTS_DIR / "final_results.csv"
    final_df = orchestrator.run_for_all(seed_companies, output_path=output_path)
    final_df.to_csv(output_path, index=False)

    print(f"Saved final results to {output_path}")
    
    if not final_df.empty:
        print(final_df.head(20).to_string(index=False))
    else:
        print("No final rows were produced.")

if __name__ == "__main__":
    main()
