import { useEffect, useMemo, useRef } from 'react';
import { Bookmark, Loader2 } from 'lucide-react';
import MovieGrid from '../components/MovieGrid';
import EmptyState from '../components/EmptyState';
import { useWatchlist } from '../lib/queries';

export default function Watchlist() {
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useWatchlist();

  const movies = useMemo(
    () => (data?.pages ?? []).flatMap((page) => (page.items ?? []).map((entry) => entry.movie)),
    [data],
  );
  const total = data?.pages?.[0]?.pagination?.total_items ?? 0;

  const sentinel = useRef(null);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isFetchingNextPage) fetchNextPage();
      },
      { rootMargin: '600px 0px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return (
    <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-6">
      <header className="mb-8">
        <p className="slate-label mb-3">Held over</p>
        <h1 className="title-card text-3xl text-print-50">Watchlist</h1>
        <p className="tech mt-3 normal-case">
          {total > 0 ? `${total} film${total === 1 ? '' : 's'} saved for later` : 'Films you save land here'}
        </p>
      </header>

      <MovieGrid
        movies={movies}
        loading={isLoading}
        emptyState={
          <EmptyState
            icon={Bookmark}
            title="Your watchlist is empty"
            description="Hit the bookmark on any poster and it will show up here, ready for the next free evening."
            action={{ to: '/app/browse', label: 'Find something to watch' }}
          />
        }
      />

      <div ref={sentinel} className="h-4" aria-hidden="true" />
      {isFetchingNextPage && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-tungsten-500" />
        </div>
      )}
    </div>
  );
}
