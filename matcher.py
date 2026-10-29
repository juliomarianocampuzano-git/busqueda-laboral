"""Ordenar avisos por palabras y habilidades compartidas."""

from __future__ import annotations

import html
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILLS = {
    "python",
    "sql",
    "javascript",
    "typescript",
    "react",
    "node",
    "django",
    "flask",
    "fastapi",
    "pandas",
    "numpy",
    "excel",
    "power bi",
    "aws",
    "azure",
    "docker",
    "kubernetes",
    "git",
    "linux",
    "html",
    "css",
    "java",
    "go",
    "golang",
    "php",
    "pytest",
    "machine learning",
    "data analysis",
    "etl",
    "postgres",
    "mysql",
    "sqlite",
    "mongodb",
    "rest",
    "api",
    "ci/cd",
    "automation",
}


def _clean(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).lower()


def extract_skills(text: str) -> set[str]:
    text = _clean(text)
    return {skill for skill in SKILLS if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text)}


def job_doc(job: dict) -> str:
    tags = job.get("tags") or []
    return _clean(f"{job.get('position', '')} {' '.join(tags)} {job.get('description', '')}")


def score_jobs(cv_text: str, jobs: list[dict], top_k: int = 20) -> list[dict]:
    if not jobs or top_k <= 0:
        return []
    docs = [_clean(cv_text)] + [job_doc(job) for job in jobs]
    try:
        matrix = TfidfVectorizer(
            stop_words="english", max_features=5000, ngram_range=(1, 2)
        ).fit_transform(docs)
        similarities = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    except ValueError:
        similarities = [0.0] * len(jobs)
    cv_skills = extract_skills(cv_text)
    results = []
    for job, similarity in zip(jobs, similarities):
        shared = sorted(cv_skills & extract_skills(job_doc(job)))
        overlap = len(shared) / len(cv_skills) if cv_skills else 0
        score = min(1.0, 0.8 * float(similarity) + 0.2 * overlap)
        if score <= 0:
            continue
        results.append(
            {
                **job,
                "affinity": round(score, 4),
                "why": {
                    "shared_skills": shared,
                    "tfidf_similarity": round(float(similarity), 4),
                },
            }
        )
    results.sort(key=lambda job: (-job["affinity"], str(job.get("id", ""))))
    return results[:top_k]
