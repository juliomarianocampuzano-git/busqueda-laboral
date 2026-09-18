"""Semantic-ish matching via TF-IDF cosine + skill overlap."""
from __future__ import annotations
import re
from typing import Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILLS = {
    "python","sql","javascript","typescript","react","node","django","flask","fastapi",
    "pandas","numpy","excel","power bi","aws","azure","docker","kubernetes","git","linux",
    "html","css","java","go","golang","php","pytest","machine learning","data analysis",
    "etl","postgres","mysql","sqlite","mongodb","rest","api","ci/cd","automation",
}


def _clean(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").lower()


def extract_skills(text: str) -> set[str]:
    t = _clean(text)
    return {s for s in SKILLS if s in t}


def job_doc(job: dict[str, Any]) -> str:
    return f"{job.get('position','')} {' '.join(job.get('tags') or [])} {job.get('description','')}"


def score_jobs(cv_text: str, jobs: list[dict[str, Any]], top_k: int = 20) -> list[dict[str, Any]]:
    if not jobs:
        return []
    docs = [cv_text] + [job_doc(j) for j in jobs]
    matrix = TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2)).fit_transform(docs)
    sims = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    cv_skills = extract_skills(cv_text)
    out = []
    for job, sim in zip(jobs, sims):
        shared = sorted(cv_skills & extract_skills(job_doc(job)))
        text = _clean(job_doc(job))
        seniority = "senior" if "senior" in text else ("junior" if "junior" in text else "no indicado")
        modality = "remote" if "remote" in text or "remote" in _clean(str(job.get("location") or "")) else (job.get("location") or "no indicada")
        out.append({
            **job,
            "affinity": round(float(sim) + 0.03 * len(shared), 4),
            "why": {
                "shared_skills": shared,
                "seniority_signal": seniority,
                "modality": modality,
                "tfidf_similarity": round(float(sim), 4),
            },
        })
    out.sort(key=lambda x: x["affinity"], reverse=True)
    return out[:top_k]
