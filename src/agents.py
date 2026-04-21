import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Any

import pandas as pd

from src.config import (
    MAX_DISCOVERIES_PER_PROVIDER,
    DISCOVERY_CONFIDENCE_THRESHOLD,
    CONSENSUS_ACCEPT_THRESHOLD,
)
from src.prompts import DISCOVERY_PROMPT, VERIFY_PROMPT, RESOLUTION_PROMPT
from src.providers import get_active_providers
from src.safe_links import evaluate_link_safety

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
RAW_DISCOVERY_DIR = RESULTS_DIR / "raw_discovery"
RAW_VERIFICATION_DIR = RESULTS_DIR / "raw_verification"
RAW_RESOLUTION_DIR = RESULTS_DIR / "raw_resolution"

for folder in [RESULTS_DIR, RAW_DISCOVERY_DIR, RAW_VERIFICATION_DIR, RAW_RESOLUTION_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_company_name(name: str) -> str:
    text = name.lower().strip()
    replacements = [
        ", inc.", " inc.", ", inc", " inc",
        ", ltd.", " ltd.", " ltd", ", ltd",
        ", llc", " llc",
        ", corp.", " corp.", " corp", ", corp",
        ", plc", " plc",
        " corporation", " holdings", " group"
    ]
    for item in replacements:
        text = text.replace(item, "")
    return " ".join(text.split())


def score_level(value: str) -> int:
    mapping = {"low": 1, "medium": 2, "high": 3}
    return mapping.get(value, 1)


class DiscoveryAgent:
    def __init__(self) -> None:
        self.providers = get_active_providers()

    def run(self, seed_company: str) -> List[Dict[str, Any]]:
        discovered_items = []

        for provider in self.providers:
            print(f"[DISCOVERY START] provider={provider.name} seed={seed_company}")

            prompt = DISCOVERY_PROMPT.format(
                seed_company=seed_company,
                max_items=MAX_DISCOVERIES_PER_PROVIDER
            )

            try:
                result = provider.generate_json(prompt)
                print(f"[DISCOVERY RESPONSE RECEIVED] provider={provider.name} seed={seed_company}")

                result["provider"] = provider.name

                provider_citations = result.pop("_provider_citations", [])
                for item in result.get("discoveries", []):
                    existing_urls = item.get("evidence_urls", [])
                    item["evidence_urls"]  = list(dict.fromkeys(existing_urls + provider_citations))

                output_path = RAW_DISCOVERY_DIR / f"{normalize_company_name(seed_company)}__{provider.name}.json"
                save_json(output_path, result)

                discoveries = result.get("discoveries", [])
                print(f"[DISCOVERY COUNT] provider={provider.name} seed={seed_company} count={len(discoveries)}")

                for item in discoveries:
                    related_company = item.get("related_company", "").strip()
                    confidence = float(item.get("confidence", 0.0))

                    if not related_company:
                        print(f"[DISCOVERY SKIP] provider={provider.name} reason=missing_related_company")
                        continue
                    if normalize_company_name(related_company) == normalize_company_name(seed_company):
                        print(f"[DISCOVERY SKIP] provider={provider.name} reason=self_match related_company={related_company}")
                        continue
                    if confidence < DISCOVERY_CONFIDENCE_THRESHOLD:
                        print(f"[DISCOVERY SKIP] provider={provider.name} reason=low_confidence confidence={confidence} related_company={related_company}")
                        continue

                    enriched_item = dict(item)
                    enriched_item["seed_company"] = seed_company
                    enriched_item["provider"] = provider.name
                    discovered_items.append(enriched_item)
                    print(f"[DISCOVERY KEEP] provider={provider.name} related_company={related_company} confidence={confidence}")

            except Exception as e:
                print(f"[DISCOVERY ERROR] {provider.name} | {seed_company} | {e}")

        return discovered_items


class VerificationAgent:
    def __init__(self) -> None:
        self.providers = get_active_providers()

    def run(self, seed_company: str, related_company: str) -> List[Dict[str, Any]]:
        verification_outputs = []

        for provider in self.providers:
            prompt = VERIFY_PROMPT.format(
                seed_company=seed_company,
                related_company=related_company,
            )

            try:
                print(f"[VERIFICATION START] provider={provider.name} seed={seed_company} related={related_company}")
                result = provider.generate_json(prompt)
                print(f"[VERIFICATION RESPONSE RECEIVED] provider={provider.name} seed={seed_company} related={related_company}")
                result["provider"] = provider.name
                result["seed_company"] = seed_company
                result["related_company"] = related_company

                provider_citations = result.pop("_provider_citations", [])
                existing_urls = result.get("evidence_urls", [])
                result["evidence_urls"] = list(dict.fromkeys(existing_urls + provider_citations))

                verification_outputs.append(result)

                file_name = (
                    f"{normalize_company_name(seed_company)}__"
                    f"{normalize_company_name(related_company)}__"
                    f"{provider.name}.json"
                )
                save_json(RAW_VERIFICATION_DIR / file_name, result)

            except Exception as e:
                print(f"[VERIFICATION ERROR] {provider.name} | {seed_company} | {related_company} | {e}")

        return verification_outputs


class ConsensusAgent:
    def run(self, verification_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        labels = [item["relationship_type"] for item in verification_outputs]
        label_counts = Counter(labels)
        majority_label, agreement_count = label_counts.most_common(1)[0]

        avg_confidence = sum(float(item["confidence"]) for item in verification_outputs) / len(verification_outputs)
        avg_source = sum(score_level(item["source_authority"]) for item in verification_outputs) / len(verification_outputs)
        avg_recency = sum(score_level(item["recency"]) for item in verification_outputs) / len(verification_outputs)
        avg_clarity = sum(score_level(item["clarity"]) for item in verification_outputs) / len(verification_outputs)
        avg_safety = sum(item.get("safety_score", 1.0) for item in verification_outputs) / len(verification_outputs)

        # run safety
        all_urls = []
        for item in verification_outputs:
            all_urls.extend(item.get("evidence_urls", []))

        safety_result = evaluate_link_safety(all_urls)
        safe_urls = safety_result["links"]
        avg_safety = safety_result["safety_score"]

        multiplier = 1.0
        if agreement_count == len(verification_outputs):
            multiplier = 1.2
        elif agreement_count == 1:
            multiplier = 0.85

        penalty = 0.0
        if avg_source < 2:
            penalty += 0.10
        if avg_recency < 2:
            penalty += 0.05
        if avg_clarity < 2:
            penalty += 0.10

        if avg_safety < 0.9:
            penalty += 0.05
        if avg_safety < 0.75:
            penalty += 0.15
        if avg_safety < 0.5:
            penalty += 0.30

        final_confidence = max(0.0, min(1.0, (avg_confidence * multiplier) - penalty))
        needs_resolution = (
            agreement_count < len(verification_outputs)
            or final_confidence < CONSENSUS_ACCEPT_THRESHOLD
        )

        return {
            "seed_company": verification_outputs[0]["seed_company"],
            "related_company": verification_outputs[0]["related_company"],
            "final_label": majority_label,
            "final_confidence": round(final_confidence, 3),
            "safety_score": round(avg_safety, 3),
            "agreement_count": agreement_count,
            "num_models": len(verification_outputs),
            "needs_resolution": needs_resolution,
            "evidence_urls": list(dict.fromkeys(safe_urls)),
            "model_outputs": verification_outputs,
        }


class ResolutionAgent:
    def __init__(self) -> None:
        self.providers = get_active_providers()

    def run(self, seed_company: str, related_company: str, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        resolver_provider = self.providers[0]

        prompt = RESOLUTION_PROMPT.format(
            seed_company=seed_company,
            related_company=related_company,
            model_outputs=json.dumps(model_outputs, indent=2)
        )

        try:
            result = resolver_provider.generate_json(prompt)
            result["provider"] = f"{resolver_provider.name}_resolver"
            
            # run safety
            urls = result.get("evidence_urls", [])
            safety_result = evaluate_link_safety(urls)
            safe_urls = safety_result["links"]
            avg_safety = safety_result["safety_score"]

            result["evidence_urls"] = safe_urls
            result["safety_score"] = round(avg_safety, 3)

            file_name = (
                f"{normalize_company_name(seed_company)}__"
                f"{normalize_company_name(related_company)}__resolver.json"
            )
            save_json(RAW_RESOLUTION_DIR / file_name, result)

            return result

        except Exception as e:
            print(f"[RESOLUTION ERROR] {seed_company} | {related_company} | {e}")
            return {
                "seed_company": seed_company,
                "related_company": related_company,
                "relationship_type": "None/Unclear",
                "confidence": 0.0,
                "safety_score": 0.0,
                "source_authority": "low",
                "recency": "low",
                "clarity": "low",
                "evidence_summary": f"Resolution failed: {e}",
                "evidence_urls": [],
                "needs_review": True,
                "provider": "resolver_failed",
            }


class Orchestrator:
    def __init__(self) -> None:
        self.discovery_agent = DiscoveryAgent()
        self.verification_agent = VerificationAgent()
        self.consensus_agent = ConsensusAgent()
        self.resolution_agent = ResolutionAgent()

    def deduplicate_candidates(self, discovered_items: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        seen = set()
        pairs = []

        for item in discovered_items:
            seed_company = item["seed_company"]
            related_company = item["related_company"]

            key = (
                normalize_company_name(seed_company),
                normalize_company_name(related_company)
            )
            if key not in seen:
                seen.add(key)
                pairs.append((seed_company, related_company))

        return pairs

    def run_for_seed_company(self, seed_company: str) -> List[Dict[str, Any]]:
        discovered_items = self.discovery_agent.run(seed_company)
        candidate_pairs = self.deduplicate_candidates(discovered_items)

        final_rows = []

        for seed_company_value, related_company in candidate_pairs:
            verification_outputs = self.verification_agent.run(seed_company_value, related_company)

            if not verification_outputs:
                continue

            consensus_result = self.consensus_agent.run(verification_outputs)

            if consensus_result["needs_resolution"]:
                resolution_result = self.resolution_agent.run(
                    seed_company_value,
                    related_company,
                    consensus_result["model_outputs"]
                )

                forced_human_review = (
                    resolution_result["relationship_type"] == "None/Unclear"
                    or resolution_result["needs_review"]
                )

                res_urls = resolution_result.get("evidence_urls", [])
                cons_urls = consensus_result.get("evidence_urls", [])
                all_urls = res_urls + cons_urls

                safety_score = (resolution_result.get("safety_score", 1.0) * len(res_urls)  + consensus_result.get("safety_score", 1.0) * len(cons_urls)) / len(all_urls) if all_urls else 1.0

                final_rows.append({
                    "seed_company": seed_company_value,
                    "related_company": related_company,
                    "final_label": resolution_result["relationship_type"],
                    "final_confidence": resolution_result["confidence"],
                    "safety_score": safety_score,
                    "agreement_count": consensus_result["agreement_count"],
                    "num_models": consensus_result["num_models"],
                    "final_status": "needs_human_review" if forced_human_review else "resolved_by_resolution_agent",
                    "needs_human_review": forced_human_review,
                    "evidence_urls": " | ".join(all_urls),
                    "summary": resolution_result["evidence_summary"],
                })
            else:
                forced_human_review = (
                    consensus_result["final_label"] == "None/Unclear"
                )

                final_rows.append({
                    "seed_company": seed_company_value,
                    "related_company": related_company,
                    "final_label": consensus_result["final_label"],
                    "final_confidence": consensus_result["final_confidence"],
                    "safety_score": consensus_result.get("safety_score", 1.0),
                    "agreement_count": consensus_result["agreement_count"],
                    "num_models": consensus_result["num_models"],
                    "final_status": "needs_human_review" if forced_human_review else "accepted_by_consensus",
                    "needs_human_review": forced_human_review,
                    "evidence_urls": " | ".join(consensus_result["evidence_urls"]),
                    "summary": verification_outputs[0]["evidence_summary"],
                })

        return final_rows

    def run_for_all(self, seed_companies: List[str]) -> pd.DataFrame:
        all_rows = []

        for seed_company in seed_companies:
            print(f"Running pipeline for: {seed_company}")
            rows = self.run_for_seed_company(seed_company)
            all_rows.extend(rows)

        final_df = pd.DataFrame(all_rows)

        if not final_df.empty:
            final_df = final_df.sort_values(
                by=["seed_company", "final_confidence"],
                ascending=[True, False]
            )

        return final_df