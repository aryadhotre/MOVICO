"""Ranking evaluation under a strong-generalisation protocol.

Most recommender numbers quoted online are not comparable because the protocol is
left unstated. This module fixes one, and it is the strict version:

* **Held-out users, not held-out ratings.** Evaluation users are removed from
  training entirely, so their embeddings must be produced by the same fold-in path
  that serves a real signed-up user. A model that only looks good on users it
  trained on tells us nothing about the live experience.
* **Chronological split.** Each evaluation user's history is cut by time: the
  earlier 80% is the visible profile, the most recent 20% is the target. The task
  is therefore predicting the future, not interpolating a random hole.
* **Full-catalogue ranking.** Every unseen title competes. Sampling 100 negatives
  (a very common shortcut) inflates hit-rate several-fold and is not used here.

Reported metrics and what each one honestly means:

``hit_rate@K``
    Share of users for whom at least one held-out title appears in the top K.
``recall@K`` / ``precision@K`` / ``ndcg@K`` / ``map@K``
    Standard top-N accuracy against the held-out positives.
``auc``
    Probability a held-out liked title outranks a random unseen title. This is the
    model's pairwise ranking accuracy over the whole catalogue.
``liked_precision@K``
    Of the top-K recommendations the user *did* rate, the share they rated >= 3.5.
    This is the closest honest analogue to "how often is a recommendation right",
    because it only counts items where the user actually expressed an opinion.
``coverage`` / ``novelty`` / ``gini``
    Catalogue health. A model that only ever surfaces the same 200 blockbusters
    can post good accuracy while being useless, so these are reported alongside.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np

from app.ml.dataset import POSITIVE_THRESHOLD, Interactions

logger = logging.getLogger(__name__)

DEFAULT_KS = (5, 10, 20, 50)


@dataclass
class UserProfile:
    """One evaluation user, split chronologically."""

    fit_indices: np.ndarray
    fit_confidence: np.ndarray
    test_indices: np.ndarray
    test_ratings: np.ndarray

    @property
    def test_positives(self) -> np.ndarray:
        return self.test_indices[self.test_ratings >= POSITIVE_THRESHOLD]


@dataclass
class HoldoutSet:
    """Evaluation users plus the training-user mask that excludes them."""

    profiles: list[UserProfile] = field(default_factory=list)
    training_user_mask: Optional[np.ndarray] = None

    def __len__(self) -> int:
        return len(self.profiles)


def build_holdout(
    interactions: Interactions,
    n_eval_users: int = 8_000,
    min_history: int = 12,
    test_fraction: float = 0.2,
    alpha: float = 18.0,
    seed: int = 20260917,
) -> HoldoutSet:
    """Selects evaluation users and splits each history by time."""
    rng = np.random.default_rng(seed)

    order = np.lexsort((interactions.timestamp, interactions.user_idx))
    users = interactions.user_idx[order]
    items = interactions.item_idx[order]
    ratings = interactions.rating[order]

    boundaries = np.flatnonzero(np.diff(users)) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [users.shape[0]]))

    counts = ends - starts
    eligible = np.flatnonzero(counts >= min_history)
    if eligible.size == 0:
        raise ValueError("No users have enough history to evaluate.")

    chosen = rng.choice(eligible, size=min(n_eval_users, eligible.size), replace=False)

    training_mask = np.ones(interactions.n_users, dtype=bool)
    profiles: list[UserProfile] = []

    for slot in chosen:
        start, end = starts[slot], ends[slot]
        training_mask[users[start]] = False

        history_items = items[start:end]
        history_ratings = ratings[start:end]

        cut = max(1, int(round(len(history_items) * (1.0 - test_fraction))))
        fit_items = history_items[:cut]
        fit_ratings = history_ratings[:cut]
        test_items = history_items[cut:]
        test_ratings = history_ratings[cut:]

        # The visible profile the model consumes is the positive part only, with
        # the same confidence mapping used in training.
        positive = fit_ratings >= POSITIVE_THRESHOLD
        if positive.sum() == 0 or test_items.size == 0:
            training_mask[users[start]] = True
            continue

        graded = (fit_ratings[positive] - POSITIVE_THRESHOLD) / (5.0 - POSITIVE_THRESHOLD)
        confidence = alpha * (0.33 + 0.67 * graded)

        profiles.append(
            UserProfile(
                fit_indices=fit_items[positive].astype(np.int64),
                fit_confidence=confidence.astype(np.float32),
                test_indices=test_items.astype(np.int64),
                test_ratings=test_ratings.astype(np.float32),
            )
        )

    logger.info(
        "Holdout: %s evaluation users withheld from training (%s remain for fitting)",
        f"{len(profiles):,}", f"{int(training_mask.sum()):,}",
    )
    return HoldoutSet(profiles=profiles, training_user_mask=training_mask)


def _dcg(gains: np.ndarray) -> float:
    discounts = 1.0 / np.log2(np.arange(2, gains.size + 2))
    return float(np.sum(gains * discounts))


def evaluate_scorer(
    scorer: Callable[[UserProfile], np.ndarray],
    holdout: HoldoutSet,
    n_items: int,
    item_popularity: Optional[np.ndarray] = None,
    ks: Sequence[int] = DEFAULT_KS,
    label: str = "model",
) -> dict[str, float]:
    """Scores every held-out user and aggregates ranking metrics.

    ``scorer`` receives a profile and must return a score for every catalogue
    item. Items in the visible profile are masked out here, so scorers do not need
    to handle exclusion themselves.
    """
    max_k = max(ks)
    totals: dict[str, list[float]] = {}
    recommended_counts = np.zeros(n_items, dtype=np.int64)
    auc_values: list[float] = []

    if item_popularity is None:
        item_popularity = np.ones(n_items, dtype=np.float64)
    # Self-information of each item, for the novelty term.
    share = np.maximum(item_popularity, 1e-9) / max(item_popularity.sum(), 1e-9)
    self_information = -np.log2(share)

    def push(key: str, value: float) -> None:
        totals.setdefault(key, []).append(value)

    for profile in holdout.profiles:
        scores = scorer(profile).astype(np.float64, copy=True)
        scores[profile.fit_indices] = -np.inf

        positives = profile.test_positives
        if positives.size == 0:
            continue

        # --- pairwise ranking accuracy over the full catalogue -------------------
        positive_scores = scores[positives]
        higher = (scores[None, :] > positive_scores[:, None]).sum(axis=1)
        n_candidates = n_items - profile.fit_indices.size
        n_negatives = n_candidates - positives.size
        if n_negatives > 0:
            # Discount the positives that outrank each positive, leaving only
            # negatives ranked above it.
            ordered = np.sort(higher)
            negatives_above = ordered - np.arange(ordered.size)
            auc_values.append(float(np.mean(1.0 - negatives_above / n_negatives)))

        # --- top-N metrics -------------------------------------------------------
        top = np.argpartition(-scores, max_k - 1)[:max_k]
        top = top[np.argsort(-scores[top])]
        recommended_counts[top[: max(ks)]] += 1

        positive_set = set(positives.tolist())
        rated = dict(zip(profile.test_indices.tolist(), profile.test_ratings.tolist()))

        for k in ks:
            cut = top[:k]
            hits = np.array([item in positive_set for item in cut.tolist()], dtype=np.float64)

            push(f"hit_rate@{k}", float(hits.any()))
            push(f"precision@{k}", float(hits.sum() / k))
            push(f"recall@{k}", float(hits.sum() / positives.size))

            ideal = _dcg(np.ones(min(k, positives.size)))
            push(f"ndcg@{k}", _dcg(hits) / ideal if ideal > 0 else 0.0)

            if hits.any():
                precisions = np.cumsum(hits) / np.arange(1, k + 1)
                push(f"map@{k}", float((precisions * hits).sum() / min(k, positives.size)))
            else:
                push(f"map@{k}", 0.0)

            # Of the recommendations this user actually rated, how many did they like?
            judged = [rated[item] for item in cut.tolist() if item in rated]
            if judged:
                liked = sum(1 for value in judged if value >= POSITIVE_THRESHOLD)
                push(f"liked_precision@{k}", liked / len(judged))

            push(f"novelty@{k}", float(self_information[cut].mean()))

    metrics = {key: float(np.mean(values)) for key, values in sorted(totals.items())}
    metrics["auc"] = float(np.mean(auc_values)) if auc_values else 0.0

    surfaced = recommended_counts > 0
    metrics["coverage"] = float(surfaced.sum() / n_items)

    # Gini over recommendation frequency: 0 = every item shown equally,
    # 1 = all traffic on one title.
    if recommended_counts.sum() > 0:
        sorted_counts = np.sort(recommended_counts)
        index = np.arange(1, n_items + 1)
        metrics["gini"] = float(
            (2 * index - n_items - 1).dot(sorted_counts) / (n_items * sorted_counts.sum())
        )
    else:
        metrics["gini"] = 0.0

    metrics["evaluated_users"] = float(len(holdout.profiles))

    logger.info(
        "[%s] HR@10 %.4f | NDCG@10 %.4f | Recall@20 %.4f | AUC %.4f | liked-P@10 %.4f | cov %.3f",
        label,
        metrics.get("hit_rate@10", 0.0),
        metrics.get("ndcg@10", 0.0),
        metrics.get("recall@20", 0.0),
        metrics["auc"],
        metrics.get("liked_precision@10", 0.0),
        metrics["coverage"],
    )
    return metrics
