"""Tests for the recommendation engine components.

These use small synthetic matrices with a planted structure, so a correct model has
a predictable answer and a broken one fails loudly. Two user groups like two
disjoint sets of films; any working collaborative model must rank within-group
items above cross-group ones.
"""

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from app.ml.content import ContentModel
from app.ml.dataset import POSITIVE_THRESHOLD, Interactions
from app.ml.ials import ImplicitALS
from app.ml.itemknn import ItemKNN


@pytest.fixture
def planted_matrix():
    """40 users x 12 items with two clean taste clusters.

    Users 0-19 like items 0-5, users 20-39 like items 6-11.
    """
    rows, cols = [], []
    for user in range(20):
        for item in range(6):
            rows.append(user)
            cols.append(item)
    for user in range(20, 40):
        for item in range(6, 12):
            rows.append(user)
            cols.append(item)
    data = np.full(len(rows), 18.0, dtype=np.float32)
    return csr_matrix((data, (rows, cols)), shape=(40, 12), dtype=np.float32)


class TestImplicitALS:
    def test_learns_planted_clusters(self, planted_matrix):
        model = ImplicitALS(factors=8, iterations=12, regularization=0.02).fit(planted_matrix)

        # A user who likes items 0-2 should score item 3-5 above items 6-11.
        vector = model.fold_in([0, 1, 2], [18.0, 18.0, 18.0])
        scores = model.score_all(vector)

        assert scores[3:6].mean() > scores[6:12].mean()

    def test_fold_in_is_deterministic(self, planted_matrix):
        model = ImplicitALS(factors=8, iterations=5).fit(planted_matrix)
        first = model.fold_in([0, 1], [18.0, 18.0])
        second = model.fold_in([0, 1], [18.0, 18.0])
        np.testing.assert_allclose(first, second)

    def test_fold_in_handles_empty_profile(self, planted_matrix):
        model = ImplicitALS(factors=8, iterations=3).fit(planted_matrix)
        vector = model.fold_in([], [])
        assert vector.shape == (8,)
        assert not np.any(vector)

    def test_roundtrip(self, planted_matrix, tmp_path):
        model = ImplicitALS(factors=8, iterations=3).fit(planted_matrix)
        model.save(str(tmp_path))
        restored = ImplicitALS.load(str(tmp_path))

        np.testing.assert_allclose(model.item_factors, restored.item_factors)
        assert restored.factors == model.factors


class TestItemKNN:
    def test_neighbours_stay_within_cluster(self, planted_matrix):
        model = ItemKNN(top_k=6, shrinkage=1.0).fit(planted_matrix)
        neighbours = dict(model.similar_items(0, limit=6))

        # Every neighbour of item 0 should come from its own cluster.
        assert neighbours, "item 0 should have neighbours"
        assert all(index < 6 for index in neighbours)

    def test_scores_profile(self, planted_matrix):
        model = ItemKNN(top_k=6, shrinkage=1.0).fit(planted_matrix)
        scores = model.score([0, 1], [1.0, 1.0])

        assert scores[2:6].mean() > scores[6:12].mean()

    def test_attribution_names_contributing_items(self, planted_matrix):
        model = ItemKNN(top_k=6, shrinkage=1.0).fit(planted_matrix)
        contributors = model.top_contributors(2, [0, 1, 7], limit=3)

        assert contributors, "expected at least one contributing profile item"
        # The cross-cluster item must not be credited.
        assert 7 not in [index for index, _ in contributors]

    def test_diagonal_is_removed(self, planted_matrix):
        model = ItemKNN(top_k=6, shrinkage=1.0).fit(planted_matrix)
        assert model.similarity[3, 3] == 0.0


class TestContentModel:
    @pytest.fixture
    def rows(self):
        return [
            {"id": 1, "title": "Space Opera (1999)", "genres": "Sci-Fi|Adventure",
             "keywords": "spaceship, alien", "user_tags": "space epic",
             "director": "Ann Director", "cast_list": "Lead One, Lead Two",
             "overview": "A fleet crosses the galaxy.", "tagline": "To the stars",
             "release_year": 1999, "original_language": "en"},
            {"id": 2, "title": "Star Voyage (2001)", "genres": "Sci-Fi|Adventure",
             "keywords": "spaceship, alien", "user_tags": "space epic",
             "director": "Ann Director", "cast_list": "Lead One, Other Three",
             "overview": "Another fleet crosses another galaxy.", "tagline": None,
             "release_year": 2001, "original_language": "en"},
            {"id": 3, "title": "Kitchen Romance (2010)", "genres": "Romance|Comedy",
             "keywords": "cooking, wedding", "user_tags": "cosy romance",
             "director": "Bob Other", "cast_list": "Someone Else",
             "overview": "Two chefs fall in love.", "tagline": None,
             "release_year": 2010, "original_language": "en"},
        ]

    def test_similar_prefers_same_genre_and_crew(self, rows):
        model = ContentModel().fit(rows)
        similar = model.similar_items(0, limit=2)

        assert similar[0][0] == 1, "the other sci-fi film should rank first"

    def test_profile_score_separates_taste(self, rows):
        model = ContentModel().fit(rows)
        scores = model.profile_score([0], [1.0])

        assert scores[1] > scores[2]

    def test_channel_normalisation_bounds_verbosity(self, rows):
        """A long overview must not let one channel dominate the vector."""
        rows[2]["overview"] = " ".join(["word"] * 400)
        model = ContentModel().fit(rows)
        norms = np.sqrt(model.matrix.multiply(model.matrix).sum(axis=1)).A.ravel()

        np.testing.assert_allclose(norms, 1.0, atol=1e-5)


class TestInteractions:
    def test_confidence_weighting_rewards_higher_ratings(self):
        interactions = Interactions(
            user_idx=np.array([0, 0, 0], dtype=np.uint32),
            item_idx=np.array([0, 1, 2], dtype=np.uint32),
            rating=np.array([3.5, 4.0, 5.0], dtype=np.float32),
            timestamp=np.zeros(3, dtype=np.uint32),
            user_ids=np.array([1], dtype=np.int32),
            item_ids=np.array([10, 11, 12], dtype=np.int32),
        )
        matrix = interactions.to_csr(weighting="confidence", alpha=18.0)
        row = matrix.toarray()[0]

        assert row[0] < row[1] < row[2]

    def test_ratings_below_threshold_are_dropped(self):
        interactions = Interactions(
            user_idx=np.array([0, 0], dtype=np.uint32),
            item_idx=np.array([0, 1], dtype=np.uint32),
            rating=np.array([1.0, 5.0], dtype=np.float32),
            timestamp=np.zeros(2, dtype=np.uint32),
            user_ids=np.array([1], dtype=np.int32),
            item_ids=np.array([10, 11], dtype=np.int32),
        )
        matrix = interactions.to_csr(positive_only=True)

        assert matrix.nnz == 1
        assert matrix.toarray()[0, 0] == 0.0

    def test_roundtrip(self, tmp_path):
        interactions = Interactions(
            user_idx=np.array([0, 1], dtype=np.uint32),
            item_idx=np.array([0, 1], dtype=np.uint32),
            rating=np.array([4.5, 3.0], dtype=np.float32),
            timestamp=np.array([100, 200], dtype=np.uint32),
            user_ids=np.array([7, 8], dtype=np.int32),
            item_ids=np.array([10, 11], dtype=np.int32),
        )
        path = str(tmp_path / "interactions.npz")
        interactions.save(path)
        restored = Interactions.load(path)

        np.testing.assert_allclose(restored.rating, interactions.rating)
        np.testing.assert_array_equal(restored.item_ids, interactions.item_ids)
