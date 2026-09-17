import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, Search as SearchIcon } from 'lucide-react';
import MovieGrid from '../components/MovieGrid';
import EmptyState from '../components/EmptyState';
import { useSearchResults } from '../lib/queries';

/**
 * Full search results.
 *
 * The command palette caps at twelve so it stays a quick-jump control; this is
 * where a query goes when the answer is not in the first few. The term lives in
 * the URL, so a result set is shareable and survives a reload.
 */
export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const term = searchParams.get('q') ?? '';
  const [draft, setDraft] = useState(term);

  // Keep the field in step when the query changes from elsewhere (the palette,
  // the back button) without fighting the user mid-keystroke.
  useEffect(() => {
    setDraft(term);
  }, [term]);

  const { data, isLoading, isFetching, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useSearchResults(term);

  const movies = useMemo(
    () => (data?.pages ?? []).flatMap((page) => page.items ?? []),
    [data],
  );

  const sentinel = useRef(null);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isFetchingNextPage) fetchNextPage();
      },
      { rootMargin: '900px 0px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const submit = (event) => {
    event.preventDefault();
    const next = draft.trim();
    setSearchParams(next ? { q: next } : {}, { replace: true });
  };

  return (
    <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-8">
      <header className="mb-8">
        <p className="slate-label mb-3">Search</p>
        <h1 className="title-card text-3xl text-print-50">
          {term ? `“${term}”` : 'Find a film'}
        </h1>

        <form onSubmit={submit} className="mt-6 flex max-w-xl gap-2">
          <div className="relative flex-1">
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-print-500" />
            <input
              id="search-query"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Title, director or cast…"
              aria-label="Search films"
              className="input pl-10"
              autoComplete="off"
            />
          </div>
          <button type="submit" className="btn-primary px-6">
            Search
          </button>
        </form>

        {term.length >= 2 && !isLoading && (
          <p className="tech mt-4 normal-case">
            {movies.length}
            {hasNextPage ? '+' : ''} result{movies.length === 1 ? '' : 's'}
            {isFetching && !isFetchingNextPage ? ' · searching…' : ''}
          </p>
        )}
      </header>

      {term.length < 2 ? (
        <EmptyState
          icon={SearchIcon}
          title="Type at least two characters"
          description="Search runs across titles, directors and cast. A director's name returns their films, not documentaries about them."
        />
      ) : (
        <>
          <MovieGrid
            movies={movies}
            loading={isLoading}
            skeletonCount={18}
            emptyState={
              <EmptyState
                icon={SearchIcon}
                title={`Nothing matched “${term}”`}
                description="Try fewer words, or check the spelling. Partial titles work — “shawshank” finds the film."
              />
            }
          />

          <div ref={sentinel} className="h-4" aria-hidden="true" />
          {isFetchingNextPage && (
            <div className="flex justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-tungsten-500" />
            </div>
          )}
        </>
      )}
    </div>
  );
}
