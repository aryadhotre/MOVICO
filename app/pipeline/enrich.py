"""Bulk TMDB enrichment, catalogue expansion and score recomputation.

Three operations, each resumable and each safe to re-run:

``enrich_pending``
    Fills poster/backdrop/overview/cast/trailer for catalogue rows that have a
    TMDB id but no enrichment yet, highest-audience titles first. Rows are marked
    with ``enriched_at`` even when TMDB returns nothing, so a dead identifier is
    attempted once rather than on every run.

``import_discover``
    Pulls titles TMDB knows about that MovieLens does not. The MovieLens archive
    stops in July 2023, so everything from 2023 onward has to come from here.

``recompute_scores``
    Rebuilds the ranking columns once metadata exists, on a single scale that
    covers both MovieLens-derived and TMDB-only titles.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import Iterable, Optional

from app.config.settings import settings
from app.pipeline.ingest import connect
from app.pipeline.tmdb import TMDBClient, parse_movie_detail

logger = logging.getLogger(__name__)

# Columns written by enrichment. Title and genres are deliberately excluded:
# MovieLens titles carry the "(year)" convention the rest of the catalogue uses,
# and its genre vocabulary is what the genre filters are built from.
ENRICH_FIELDS = (
    "poster_path", "backdrop_path", "overview", "tagline", "release_date",
    "release_year", "runtime", "vote_average", "vote_count", "tmdb_popularity",
    "original_language", "director", "cast_list", "keywords", "trailer_key",
)

# TMDB caps discover at 500 pages per query.
MAX_DISCOVER_PAGES = 500


def _pending_movies(limit: Optional[int]) -> list[tuple[int, str]]:
    """Catalogue rows awaiting enrichment, most-rated first."""
    query = """
        SELECT id, tmdb_id FROM movies
        WHERE enriched_at IS NULL
          AND tmdb_id IS NOT NULL AND tmdb_id NOT IN ('', 'nan', 'None')
        ORDER BY rating_count DESC, id ASC
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    connection = connect()
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def _write_enrichment(rows: list[tuple]) -> None:
    """Applies a batch of enrichment updates in one transaction."""
    assignments = ", ".join(f"{field}=?" for field in ENRICH_FIELDS)
    statement = f"UPDATE movies SET {assignments}, enriched_at=? WHERE id=?"
    connection = connect()
    try:
        with connection:
            connection.executemany(statement, rows)
    finally:
        connection.close()


async def enrich_pending(
    limit: Optional[int] = None,
    batch_size: int = 500,
    concurrency: int = 24,
    rate: float = 36.0,
) -> dict[str, int]:
    """Enriches catalogue rows from TMDB, committing batch by batch."""
    pending = _pending_movies(limit)
    if not pending:
        logger.info("No catalogue rows pending enrichment.")
        return {"attempted": 0, "enriched": 0, "missing": 0}

    logger.info("Enriching %s catalogue rows from TMDB ...", f"{len(pending):,}")
    enriched = missing = 0
    started = asyncio.get_event_loop().time()

    async with TMDBClient(settings.TMDB_API_KEY, concurrency=concurrency, rate=rate) as client:
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            payloads = await client.map_concurrent(
                batch, lambda pair: client.movie_detail(pair[1])
            )

            stamp = dt.datetime.utcnow()
            updates = []
            for (movie_id, _tmdb_id), payload in zip(batch, payloads):
                if not payload:
                    # Mark as attempted so a resumed run skips it.
                    updates.append(tuple([None] * len(ENRICH_FIELDS)) + (stamp, movie_id))
                    missing += 1
                    continue
                parsed = parse_movie_detail(payload)
                updates.append(
                    tuple(parsed[field] for field in ENRICH_FIELDS) + (stamp, movie_id)
                )
                enriched += 1

            await asyncio.to_thread(_write_enrichment, updates)

            done = offset + len(batch)
            elapsed = asyncio.get_event_loop().time() - started
            rps = done / elapsed if elapsed else 0.0
            remaining = (len(pending) - done) / rps if rps else 0.0
            logger.info(
                "  %s/%s enriched (%s ok, %s missing) | %.0f req/s | ~%.0f min left",
                f"{done:,}", f"{len(pending):,}", f"{enriched:,}", f"{missing:,}",
                rps, remaining / 60,
            )

    logger.info("Enrichment finished: %s enriched, %s unavailable", f"{enriched:,}", f"{missing:,}")
    return {"attempted": len(pending), "enriched": enriched, "missing": missing}


def _existing_tmdb_ids() -> set[str]:
    connection = connect()
    try:
        rows = connection.execute(
            "SELECT tmdb_id FROM movies WHERE tmdb_id IS NOT NULL AND tmdb_id != ''"
        ).fetchall()
    finally:
        connection.close()
    return {str(row[0]) for row in rows}


def _next_movie_id() -> int:
    connection = connect()
    try:
        current = connection.execute("SELECT COALESCE(MAX(id), 0) FROM movies").fetchone()[0]
    finally:
        connection.close()
    return int(current) + 1


IMPORT_COLUMNS = (
    "id", "title", "genres", "imdb_id", "tmdb_id", "poster_path", "backdrop_path",
    "overview", "tagline", "release_date", "release_year", "runtime",
    "vote_average", "vote_count", "tmdb_popularity", "original_language",
    "director", "cast_list", "keywords", "trailer_key", "rating_count",
    "rating_mean", "bayes_score", "enriched_at",
)


async def import_discover(
    start_year: int = 2023,
    end_year: Optional[int] = None,
    pages: int = 60,
    min_votes: int = 8,
    sort_by: str = "popularity.desc",
    concurrency: int = 24,
    rate: float = 36.0,
) -> dict[str, int]:
    """Imports titles from TMDB's discover feed that are not already catalogued.

    Discover returns summaries only, so each new title costs a second request for
    its full record (credits, trailer, keywords). ``min_votes`` filters the very
    long tail of unreleased or unrated entries that would otherwise pad the
    catalogue with posterless rows.
    """
    end_year = end_year or dt.date.today().year + 1
    known = _existing_tmdb_ids()
    pages = min(pages, MAX_DISCOVER_PAGES)

    logger.info(
        "Discovering TMDB titles %d-%d across %d pages (sort=%s) ...",
        start_year, end_year, pages, sort_by,
    )

    imported = 0
    skipped = 0
    next_id = _next_movie_id()

    async with TMDBClient(settings.TMDB_API_KEY, concurrency=concurrency, rate=rate) as client:
        page_numbers = list(range(1, pages + 1))
        # Fetch discover pages in blocks so new ids start resolving immediately.
        for block_start in range(0, len(page_numbers), 20):
            block = page_numbers[block_start : block_start + 20]
            listings = await client.map_concurrent(
                block,
                lambda page: client.discover(
                    page=page,
                    sort_by=sort_by,
                    release_date_gte=f"{start_year}-01-01",
                    release_date_lte=f"{end_year}-12-31",
                    vote_count_gte=min_votes,
                ),
            )

            candidates: list[str] = []
            for listing in listings:
                for result in (listing or {}).get("results", []):
                    tmdb_id = str(result.get("id"))
                    if tmdb_id in known:
                        skipped += 1
                        continue
                    known.add(tmdb_id)
                    candidates.append(tmdb_id)

            if not candidates:
                continue

            payloads = await client.map_concurrent(candidates, client.movie_detail)

            stamp = dt.datetime.utcnow()
            records = []
            for payload in payloads:
                if not payload or not payload.get("poster_path"):
                    # A title with no poster cannot be displayed; skip rather than
                    # pad the catalogue with blank cards.
                    continue
                parsed = parse_movie_detail(payload)
                year = parsed["release_year"]
                title = f"{parsed['title']} ({year})" if year else parsed["title"]

                # TMDB votes are 0-10; the catalogue is on the MovieLens 0-5 scale.
                tmdb_mean = (parsed["vote_average"] or 0.0) / 2.0
                votes = parsed["vote_count"] or 0
                bayes = (votes * tmdb_mean + 46 * 3.543) / (votes + 46)

                records.append(
                    (
                        next_id, title, parsed["genres"], parsed["imdb_id"], parsed["tmdb_id"],
                        parsed["poster_path"], parsed["backdrop_path"], parsed["overview"],
                        parsed["tagline"], parsed["release_date"], year, parsed["runtime"],
                        parsed["vote_average"], votes, parsed["tmdb_popularity"],
                        parsed["original_language"], parsed["director"], parsed["cast_list"],
                        parsed["keywords"], parsed["trailer_key"],
                        0, round(tmdb_mean, 4), round(bayes, 4), stamp,
                    )
                )
                next_id += 1

            if records:
                placeholders = ", ".join("?" * len(IMPORT_COLUMNS))
                statement = (
                    f"INSERT OR IGNORE INTO movies ({', '.join(IMPORT_COLUMNS)}) "
                    f"VALUES ({placeholders})"
                )

                def write(rows=records, sql=statement):
                    connection = connect()
                    try:
                        with connection:
                            connection.executemany(sql, rows)
                    finally:
                        connection.close()

                await asyncio.to_thread(write)
                imported += len(records)

            logger.info(
                "  pages %d-%d: +%s imported (%s already known)",
                block[0], block[-1], f"{imported:,}", f"{skipped:,}",
            )

    logger.info("Discover import finished: %s new titles", f"{imported:,}")
    return {"imported": imported, "skipped": skipped}


def _pending_cast(limit: Optional[int]) -> list[tuple[int, str]]:
    """Enriched rows that still have no structured billing, most-rated first."""
    query = """
        SELECT id, tmdb_id FROM movies
        WHERE cast_json IS NULL
          AND poster_path IS NOT NULL
          AND tmdb_id IS NOT NULL AND tmdb_id NOT IN ('', 'nan', 'None')
        ORDER BY rating_count DESC, vote_count DESC, id ASC
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    connection = connect()
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


async def backfill_cast(
    limit: Optional[int] = None,
    batch_size: int = 500,
    concurrency: int = 24,
    rate: float = 36.0,
    max_cast: int = 10,
) -> dict[str, int]:
    """Adds structured cast billing (name, character, portrait) to the catalogue.

    Deliberately additive: it writes ``cast_json`` and nothing else, so a failure
    part-way through cannot damage metadata that is already correct. Rows are
    marked with an empty array when TMDB has no cast, which keeps the run
    resumable without re-requesting dead identifiers.
    """
    pending = _pending_cast(limit)
    if not pending:
        logger.info("No rows pending cast backfill.")
        return {"attempted": 0, "written": 0}

    logger.info("Backfilling cast for %s titles ...", f"{len(pending):,}")
    written = 0
    started = asyncio.get_event_loop().time()

    def write(rows: list[tuple]) -> None:
        connection = connect()
        try:
            with connection:
                connection.executemany(
                    "UPDATE movies SET cast_json = ? WHERE id = ?", rows
                )
        finally:
            connection.close()

    async with TMDBClient(settings.TMDB_API_KEY, concurrency=concurrency, rate=rate) as client:
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            payloads = await client.map_concurrent(
                batch, lambda pair: client.credits(pair[1])
            )

            updates = []
            for (movie_id, _tmdb_id), payload in zip(batch, payloads):
                billing = []
                for member in sorted(
                    (payload or {}).get("cast", []), key=lambda m: m.get("order", 9_999)
                )[:max_cast]:
                    name = (member.get("name") or "").strip()
                    if not name:
                        continue
                    billing.append(
                        {
                            "n": name,
                            "c": (member.get("character") or "").strip() or None,
                            "p": member.get("profile_path"),
                        }
                    )
                updates.append((json.dumps(billing, ensure_ascii=False), movie_id))
                written += 1

            await asyncio.to_thread(write, updates)

            done = offset + len(batch)
            elapsed = asyncio.get_event_loop().time() - started
            rps = done / elapsed if elapsed else 0.0
            logger.info(
                "  %s/%s  |  %.0f req/s  |  ~%.0f min left",
                f"{done:,}", f"{len(pending):,}", rps,
                ((len(pending) - done) / rps / 60) if rps else 0.0,
            )

    logger.info("Cast backfill finished: %s rows written", f"{written:,}")
    return {"attempted": len(pending), "written": written}


def recompute_scores() -> dict[str, int]:
    """Rebuilds ranking columns across the whole catalogue on one scale.

    ``bayes_score``
        Shrunk quality on the 0-5 scale. MovieLens ratings are authoritative where
        they exist; otherwise TMDB votes are rescaled and shrunk identically, so
        a 2025 release and a 1994 classic are directly comparable.

    ``popularity_score``
        Quality weighted by audience size. Neither term alone is usable: the mean
        lets obscure titles win, and raw volume ignores whether anyone liked it.

    ``trending_score``
        TMDB's live popularity, damped by a release-recency term. This is what
        makes "trending" reflect the present -- the MovieLens time-decay signal
        cannot, because the archive ends in July 2023.
    """
    connection = connect()
    try:
        with connection:
            connection.execute(
                """
                UPDATE movies SET
                    rating_count    = COALESCE(rating_count, 0),
                    rating_mean     = COALESCE(rating_mean, 0.0),
                    vote_count      = COALESCE(vote_count, 0),
                    vote_average    = COALESCE(vote_average, 0.0),
                    tmdb_popularity = COALESCE(tmdb_popularity, 0.0)
                """
            )

            # Shrink toward the global mean. The two sources use different priors
            # on purpose.
            #
            # On the 14,788 titles rated by both, TMDB/2 and MovieLens means agree
            # closely (slope 1.02, r=0.85), so no rescaling is needed. What differs
            # is how much a vote is worth: MovieLens ratings accrue over years from
            # a broad panel, while a just-released film's TMDB votes are early and
            # self-selecting. At m=46 a 2026 release with 1,100 fan votes keeps 96%
            # of its own 9.1/10 average and outranks The Shawshank Redemption.
            # A heavier prior on TMDB-only titles damps that without silencing
            # genuinely well-received releases.
            connection.execute(
                """
                UPDATE movies SET bayes_score = ROUND(
                    CASE
                        WHEN rating_count > 0 THEN
                            (rating_count * rating_mean + 46 * 3.543) / (rating_count + 46)
                        WHEN vote_count > 0 THEN
                            (vote_count * (vote_average / 2.0) + 300 * 3.543) / (vote_count + 300)
                        ELSE 0.0
                    END, 4)
                """
            )

            connection.execute(
                """
                UPDATE movies SET popularity_score = ROUND(
                    bayes_score * LN(1 + MAX(rating_count, vote_count)), 4)
                """
            )

            # TMDB's own popularity field already reflects current attention, so the
            # recency term only needs to break ties -- at a 2.5 numerator it gave
            # current-year titles a 3.5x multiplier against 1.5x for five-year-olds,
            # and unreleased films swamped every trending surface.
            #
            # The vote factor saturates slowly for the same reason: a film with 300
            # votes has not yet earned the same confidence as one with thousands.
            connection.execute(
                """
                UPDATE movies SET trending_score = ROUND(
                    LN(1 + tmdb_popularity)
                    * (1.0 + 1.0 / (1.0 + MAX(0, :this_year - COALESCE(release_year, 1900)) / 2.0))
                    * (0.30 + 0.70 * MIN(1.0, vote_count / 1200.0)), 4)
                """,
                {"this_year": dt.date.today().year},
            )

            updated = connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    finally:
        connection.close()

    logger.info("Recomputed ranking scores for %s titles", f"{updated:,}")
    return {"updated": int(updated)}


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs every request at INFO; at catalogue scale that is ~87k lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="TMDB catalogue enrichment")
    parser.add_argument("command", choices=["enrich", "discover", "scores", "cast"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pages", type=int, default=60)
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--sort-by", type=str, default="popularity.desc")
    parser.add_argument("--min-votes", type=int, default=8)
    args = parser.parse_args()

    if args.command == "enrich":
        print(asyncio.run(enrich_pending(limit=args.limit)))
    elif args.command == "cast":
        print(asyncio.run(backfill_cast(limit=args.limit)))
    elif args.command == "discover":
        print(
            asyncio.run(
                import_discover(
                    start_year=args.start_year,
                    end_year=args.end_year,
                    pages=args.pages,
                    min_votes=args.min_votes,
                    sort_by=args.sort_by,
                )
            )
        )
    else:
        print(recompute_scores())
