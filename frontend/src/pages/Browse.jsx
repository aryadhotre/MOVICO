import React, { useState, useEffect, useCallback, useRef } from 'react';
import { browse, getGenres } from '../api/movies';
import GlassCard from '../components/GlassCard';
import { Link } from 'react-router-dom';
import { Star, Filter, X, Search, ChevronLeft, ChevronRight } from 'lucide-react';

function MovieCard({ movie }) {
  return (
    <Link to={`/movies/${movie.id}`} className="group block h-full">
      <GlassCard className="h-full flex flex-col p-0 overflow-hidden group-hover:-translate-y-2 transition-transform duration-300">
        <div className="relative aspect-[2/3] w-full bg-[#161B26] rounded-t-2xl overflow-hidden">
          {movie.poster_url ? (
            <img src={movie.poster_url} alt={movie.title} className="w-full h-full object-cover" loading="lazy" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-secondary text-xs text-center p-4">No Poster</div>
          )}
          <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/80 to-transparent" />
        </div>
        <div className="p-3 flex-1 flex flex-col gap-1">
          <h3 className="font-semibold text-text-primary text-sm line-clamp-2 group-hover:text-accent-primary transition-colors">
            {movie.title}
          </h3>
          <div className="flex items-center justify-between mt-auto pt-1 text-xs text-text-secondary">
            <span>{movie.release_date ? movie.release_date.substring(0, 4) : ''}</span>
            {movie.vote_average > 0 && (
              <div className="flex items-center gap-1 text-rating font-medium">
                <Star size={11} className="fill-rating" />
                {movie.vote_average.toFixed(1)}
              </div>
            )}
          </div>
        </div>
      </GlassCard>
    </Link>
  );
}

export default function Browse() {
  const [movies, setMovies] = useState([]);
  const [genresList, setGenresList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [meta, setMeta] = useState({ page: 1, total_pages: 1, total_items: 0 });
  
  // Filter state
  const [filters, setFilters] = useState({
    page: 1,
    sort_by: 'popularity',
    order: 'desc',
    genres: [],
    year: '',
    language: ''
  });

  // Debounce ref
  const timeoutRef = useRef(null);

  // Fetch Genres on mount
  useEffect(() => {
    getGenres().then(res => {
      if (res && res.genres) setGenresList(res.genres.map(g => g.name));
    }).catch(() => {});
  }, []);

  // Fetch movies
  const fetchMovies = useCallback(async (currentFilters) => {
    setLoading(true);
    setError('');
    
    // Build query params
    const params = {
      page: currentFilters.page,
      page_size: 24,
      sort_by: currentFilters.sort_by,
      order: currentFilters.order
    };
    if (currentFilters.genres.length > 0) {
      params.genres = currentFilters.genres.join(',');
    }
    if (currentFilters.year) {
      params.year = currentFilters.year;
    }
    if (currentFilters.language) {
      params.language = currentFilters.language;
    }

    try {
      const res = await browse(params);
      setMovies(res.items || []);
      setMeta(res.pagination || { page: 1, total_pages: 1, total_items: 0 });
    } catch (err) {
      setError('Failed to fetch movies.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Effect to trigger fetch with debounce
  useEffect(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    
    timeoutRef.current = setTimeout(() => {
      fetchMovies(filters);
    }, 300);

    return () => clearTimeout(timeoutRef.current);
  }, [filters, fetchMovies]);

  // Handlers
  const updateFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }));
  };

  const toggleGenre = (genre) => {
    setFilters(prev => {
      const newGenres = prev.genres.includes(genre)
        ? prev.genres.filter(g => g !== genre)
        : [...prev.genres, genre];
      return { ...prev, genres: newGenres, page: 1 };
    });
  };

  const clearAll = () => {
    setFilters({ page: 1, sort_by: 'popularity', order: 'desc', genres: [], year: '', language: '' });
  };

  const removeChip = (key, value = null) => {
    if (key === 'genres') {
      setFilters(prev => ({ ...prev, genres: prev.genres.filter(g => g !== value), page: 1 }));
    } else {
      updateFilter(key, '');
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= meta.total_pages) {
      setFilters(prev => ({ ...prev, page: newPage }));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Derived chips
  const activeChips = [];
  if (filters.sort_by !== 'popularity') activeChips.push({ key: 'sort_by', label: `Sort: ${filters.sort_by.replace('_', ' ')}` });
  if (filters.year) activeChips.push({ key: 'year', label: `Year: ${filters.year}` });
  if (filters.language) activeChips.push({ key: 'language', label: `Lang: ${filters.language}` });
  filters.genres.forEach(g => activeChips.push({ key: 'genres', value: g, label: g }));

  return (
    <div className="max-w-7xl mx-auto space-y-6 flex flex-col h-full min-h-full">
      <div className="flex flex-col md:flex-row gap-6">
        
        {/* Sidebar Filters */}
        <aside className="w-full md:w-[280px] shrink-0 space-y-6">
          <GlassCard className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
                <Filter size={18} className="text-accent-primary" /> Filters
              </h2>
              {activeChips.length > 0 && (
                <button onClick={clearAll} className="text-xs text-text-secondary hover:text-red-400 transition-colors">
                  Clear All
                </button>
              )}
            </div>

            <div className="space-y-5">
              {/* Sort By */}
              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Sort By</label>
                <select 
                  className="w-full bg-black/20 border border-white/10 rounded-lg p-2.5 text-sm text-text-primary focus:outline-none focus:border-accent-primary transition-colors"
                  value={filters.sort_by}
                  onChange={(e) => updateFilter('sort_by', e.target.value)}
                >
                  <option value="popularity">Popularity</option>
                  <option value="trending">Trending</option>
                  <option value="vote_average">Average Rating</option>
                  <option value="release_date">Release Date</option>
                  <option value="title">Title</option>
                </select>
              </div>

              {/* Year */}
              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Release Year</label>
                <input 
                  type="text" 
                  placeholder="e.g. 2023" 
                  maxLength={4}
                  className="w-full bg-black/20 border border-white/10 rounded-lg p-2.5 text-sm text-text-primary focus:outline-none focus:border-accent-primary transition-colors"
                  value={filters.year}
                  onChange={(e) => updateFilter('year', e.target.value)}
                />
              </div>

              {/* Language */}
              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Language</label>
                <select 
                  className="w-full bg-black/20 border border-white/10 rounded-lg p-2.5 text-sm text-text-primary focus:outline-none focus:border-accent-primary transition-colors"
                  value={filters.language}
                  onChange={(e) => updateFilter('language', e.target.value)}
                >
                  <option value="">All Languages</option>
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="ja">Japanese</option>
                  <option value="ko">Korean</option>
                  <option value="de">German</option>
                </select>
              </div>

              {/* Genres */}
              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Genres</label>
                <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto pr-2 pb-2">
                  {genresList.map(g => (
                    <button
                      key={g}
                      onClick={() => toggleGenre(g)}
                      className={`text-xs px-3 py-1.5 rounded-full transition-all border ${
                        filters.genres.includes(g)
                          ? 'bg-accent-primary/20 border-accent-primary/50 text-accent-primary font-semibold'
                          : 'bg-white/5 border-white/10 text-text-secondary hover:bg-white/10'
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </GlassCard>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col min-w-0 space-y-4">
          
          {/* Header & Active Chips */}
          <div className="flex flex-col gap-3">
            <h1 className="text-3xl font-bold text-text-primary">Browse Movies</h1>
            
            <div className="flex flex-wrap items-center gap-2 min-h-[32px]">
              {activeChips.map((chip, idx) => (
                <span key={`${chip.key}-${idx}`} className="flex items-center gap-1 bg-white/10 border border-white/20 px-3 py-1 rounded-full text-xs text-text-primary">
                  {chip.label}
                  <button onClick={() => removeChip(chip.key, chip.value)} className="hover:text-red-400 ml-1">
                    <X size={14} />
                  </button>
                </span>
              ))}
              {activeChips.length > 0 && <span className="text-sm text-text-secondary ml-2">{meta.total_items} results</span>}
            </div>
          </div>

          {/* Grid */}
          <div className="flex-1">
            {loading ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {Array.from({ length: 24 }).map((_, i) => (
                  <GlassCard key={i} className="aspect-[2/3] animate-pulse bg-white/5 p-0" />
                ))}
              </div>
            ) : error ? (
              <div className="p-12 text-center text-red-400 font-medium bg-white/5 rounded-2xl border border-white/10">{error}</div>
            ) : movies.length === 0 ? (
              <div className="p-12 text-center flex flex-col items-center justify-center bg-white/5 rounded-2xl border border-white/10 h-64">
                <Search size={40} className="text-text-secondary mb-4 opacity-50" />
                <p className="text-text-primary font-semibold">No movies found</p>
                <p className="text-text-secondary text-sm">Try adjusting your filters.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {movies.map(movie => (
                  <MovieCard key={movie.id} movie={movie} />
                ))}
              </div>
            )}
          </div>

          {/* Pagination */}
          {!loading && meta.total_pages > 1 && (
            <div className="flex items-center justify-center gap-4 pt-6 pb-4">
              <button
                onClick={() => handlePageChange(meta.page - 1)}
                disabled={meta.page === 1}
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-50 text-text-primary transition-colors"
              >
                <ChevronLeft size={20} />
              </button>
              
              <span className="text-sm text-text-secondary font-medium">
                Page <strong className="text-text-primary">{meta.page}</strong> of {meta.total_pages}
              </span>

              <button
                onClick={() => handlePageChange(meta.page + 1)}
                disabled={meta.page === meta.total_pages}
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-50 text-text-primary transition-colors"
              >
                <ChevronRight size={20} />
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
