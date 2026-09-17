"""Offline training entry point.

Produces every artifact the serving layer loads, and an ``evaluation_metrics.json``
measured under the protocol in ``app.ml.evaluate``. A popularity baseline is always
evaluated alongside the learned models, because an accuracy number without a
baseline is unfalsifiable -- on a catalogue this skewed, "recommend the most
popular unseen title" is a genuinely strong strategy and anything claiming to be a
recommender has to beat it clearly.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from typing import Optional

import numpy as np
from scipy.sparse import csr_matrix

from app.config.settings import settings
from app.ml.dataset import Interactions, build_from_movielens
from app.ml.evaluate import HoldoutSet, UserProfile, build_holdout, evaluate_scorer
from app.ml.ials import ImplicitALS
from app.ml.itemknn import ItemKNN

logger = logging.getLogger(__name__)

ARTIFACT_DIR = os.path.join(settings.DATA_DIR, "artifacts")
INTERACTIONS_PATH = os.path.join(ARTIFACT_DIR, "interactions.npz")


def _standardise(scores: np.ndarray) -> np.ndarray:
    """Z-scores a score vector so heterogeneous models can be blended.

    iALS produces dot products around 1.0; the neighbourhood model produces summed
    similarities that scale with profile length. Blending them raw would let
    whichever has the larger variance dominate regardless of quality.
    """
    finite = np.isfinite(scores)
    if not finite.any():
        return np.zeros_like(scores)
    mean = scores[finite].mean()
    std = scores[finite].std()
    if std < 1e-9:
        return np.zeros_like(scores)
    out = np.zeros_like(scores)
    out[finite] = (scores[finite] - mean) / std
    return out


def train(
    factors: int = 128,
    iterations: int = 14,
    regularization: float = 0.06,
    reg_exponent: float = 0.7,
    alpha: float = 18.0,
    knn_top_k: int = 200,
    knn_shrinkage: float = 60.0,
    eval_users: int = 6_000,
    rebuild_interactions: bool = False,
    output_dir: Optional[str] = None,
) -> dict:
    output_dir = output_dir or settings.MODELS_DIR
    os.makedirs(output_dir, exist_ok=True)
    started = time.time()

    # ------------------------------------------------------------------ data
    if rebuild_interactions or not os.path.exists(INTERACTIONS_PATH):
        ratings_csv = os.path.join(settings.DATA_DIR, "ml-latest", "ratings.csv")
        interactions = build_from_movielens(ratings_csv, out_path=INTERACTIONS_PATH)
    else:
        interactions = Interactions.load(INTERACTIONS_PATH)
    logger.info("Interactions: %s", interactions.describe())

    holdout = build_holdout(interactions, n_eval_users=eval_users, alpha=alpha)

    full_matrix = interactions.to_csr(weighting="confidence", alpha=alpha)
    # Zero out evaluation users so nothing about them reaches the factors.
    train_matrix = full_matrix.multiply(
        holdout.training_user_mask[:, None].astype(np.float32)
    ).tocsr()
    train_matrix.eliminate_zeros()
    logger.info(
        "Training matrix: %s observations over %s fitting users",
        f"{train_matrix.nnz:,}", f"{int(holdout.training_user_mask.sum()):,}",
    )

    item_popularity = np.asarray((full_matrix > 0).sum(axis=0)).ravel().astype(np.float64)
    n_items = interactions.n_items

    # ------------------------------------------------------------------ models
    ials = ImplicitALS(
        factors=factors,
        regularization=regularization,
        reg_exponent=reg_exponent,
        iterations=iterations,
    ).fit(train_matrix, interactions.item_ids)

    knn = ItemKNN(top_k=knn_top_k, shrinkage=knn_shrinkage).fit(
        train_matrix, interactions.item_ids
    )

    # ------------------------------------------------------------------ scorers
    popularity_scores = np.log1p(item_popularity).astype(np.float32)

    def score_popularity(_profile: UserProfile) -> np.ndarray:
        return popularity_scores

    def score_ials(profile: UserProfile) -> np.ndarray:
        vector = ials.fold_in(profile.fit_indices, profile.fit_confidence)
        return ials.score_all(vector)

    def score_knn(profile: UserProfile) -> np.ndarray:
        return knn.score(profile.fit_indices, profile.fit_confidence)

    def make_fusion(w_ials: float, w_knn: float, w_pop: float):
        def score(profile: UserProfile) -> np.ndarray:
            return (
                w_ials * _standardise(score_ials(profile))
                + w_knn * _standardise(score_knn(profile))
                + w_pop * _standardise(popularity_scores)
            )

        return score

    # ------------------------------------------------------------------ evaluate
    metrics: dict[str, dict] = {}
    metrics["popularity"] = evaluate_scorer(
        score_popularity, holdout, n_items, item_popularity, label="popularity"
    )
    metrics["ials"] = evaluate_scorer(
        score_ials, holdout, n_items, item_popularity, label="iALS"
    )
    metrics["item_knn"] = evaluate_scorer(
        score_knn, holdout, n_items, item_popularity, label="item-kNN"
    )

    # Fusion weights are chosen on a disjoint slice of the holdout so the reported
    # figure is not tuned on the data it is reported over.
    tuning_cut = max(1, len(holdout.profiles) // 4)
    tuning = HoldoutSet(profiles=holdout.profiles[:tuning_cut], training_user_mask=None)
    reporting = HoldoutSet(profiles=holdout.profiles[tuning_cut:], training_user_mask=None)

    best = (None, -1.0)
    for w_ials, w_knn, w_pop in [
        (1.0, 0.0, 0.0),
        (0.8, 0.2, 0.0),
        (0.65, 0.35, 0.0),
        (0.5, 0.5, 0.0),
        (0.35, 0.65, 0.0),
        (0.6, 0.35, 0.05),
        (0.5, 0.4, 0.10),
    ]:
        trial = evaluate_scorer(
            make_fusion(w_ials, w_knn, w_pop),
            tuning,
            n_items,
            item_popularity,
            ks=(10, 20),
            label=f"fusion {w_ials:.2f}/{w_knn:.2f}/{w_pop:.2f}",
        )
        score = trial.get("ndcg@10", 0.0)
        if score > best[1]:
            best = ((w_ials, w_knn, w_pop), score)

    weights = best[0]
    logger.info("Selected fusion weights iALS=%.2f kNN=%.2f pop=%.2f", *weights)
    metrics["hybrid"] = evaluate_scorer(
        make_fusion(*weights), reporting, n_items, item_popularity, label="hybrid"
    )
    metrics["hybrid"]["weights"] = {
        "ials": weights[0], "item_knn": weights[1], "popularity": weights[2]
    }

    # ------------------------------------------------------------------ persist
    ials.save(output_dir)
    knn.save(output_dir)

    np.savez(
        os.path.join(output_dir, "catalogue_index.npz"),
        item_ids=interactions.item_ids,
        item_popularity=item_popularity,
    )

    report = {
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "training_seconds": round(time.time() - started, 1),
        "protocol": {
            "type": "strong_generalisation",
            "description": (
                "Evaluation users are excluded from training entirely and scored via "
                "fold-in. Each history is split chronologically 80/20. All unseen "
                "catalogue items compete for ranking (no negative sampling)."
            ),
            "evaluation_users": len(holdout.profiles),
            "catalogue_items": int(n_items),
            "training_interactions": int(train_matrix.nnz),
        },
        "hyperparameters": {
            "factors": factors,
            "iterations": iterations,
            "regularization": regularization,
            "reg_exponent": reg_exponent,
            "alpha": alpha,
            "knn_top_k": knn_top_k,
            "knn_shrinkage": knn_shrinkage,
        },
        "models": metrics,
    }

    metrics_path = os.path.join(output_dir, "evaluation_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    logger.info("Wrote %s", metrics_path)

    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Train the MOVICO recommendation engine")
    parser.add_argument("--factors", type=int, default=128)
    parser.add_argument("--iterations", type=int, default=14)
    parser.add_argument("--regularization", type=float, default=0.06)
    parser.add_argument("--reg-exponent", type=float, default=0.7)
    parser.add_argument("--alpha", type=float, default=18.0)
    parser.add_argument("--knn-top-k", type=int, default=200)
    parser.add_argument("--knn-shrinkage", type=float, default=60.0)
    parser.add_argument("--eval-users", type=int, default=6000)
    parser.add_argument("--rebuild-interactions", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where to write artifacts (default: MODELS_DIR). Use a scratch path to "
             "evaluate a configuration without replacing the serving models.",
    )
    args = parser.parse_args()

    report = train(
        factors=args.factors,
        iterations=args.iterations,
        regularization=args.regularization,
        reg_exponent=args.reg_exponent,
        alpha=args.alpha,
        knn_top_k=args.knn_top_k,
        knn_shrinkage=args.knn_shrinkage,
        eval_users=args.eval_users,
        rebuild_interactions=args.rebuild_interactions,
        output_dir=args.output_dir,
    )
    print(json.dumps(report["models"]["hybrid"], indent=2))


if __name__ == "__main__":
    main()
