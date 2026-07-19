import React, { useState, useEffect, useRef } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { getMe } from '../api/auth';
import Logo from './Logo';
import { 
  Film, Home, Compass, TrendingUp, Sparkles, Bookmark, 
  Clock, Tag, Star, User, Settings, LogOut, Search, ChevronDown
} from 'lucide-react';

export default function Layout() {
  const [user, setUser] = useState(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchUser() {
      try {
        const userData = await getMe();
        setUser(userData);
      } catch (err) {
        console.error("Failed to get user:", err);
      }
    }
    fetchUser();
  }, []);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('jwt');
    navigate('/login');
  };

  const navItems = [
    { name: 'Home', path: '/', icon: <Home size={18} /> },
    { name: 'Browse Movies', path: '/browse', icon: <Compass size={18} /> },
    { name: 'Trending', path: '/trending', icon: <TrendingUp size={18} /> },
    { name: 'Recommendations', path: '/recommendations', icon: <Sparkles size={18} /> },
    { name: 'Watchlist', path: '/watchlist', icon: <Bookmark size={18} /> },
    { name: 'History', path: '/history', icon: <Clock size={18} /> },
    { name: 'Genres', path: '/genres', icon: <Tag size={18} /> },
    { name: 'My Ratings', path: '/ratings', icon: <Star size={18} /> },
  ];

  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* Ambient background glow */}
      <div className="ambient-glow" />

      {/* Left Sidebar */}
      <aside className="w-[260px] bg-white/[0.03] backdrop-blur-2xl border-r border-white/[0.06] flex flex-col h-full z-10 shrink-0 relative">
        <div className="p-6 pb-4">
          <Logo className="text-2xl" />
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => 
                `flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-300 text-[13px] font-medium ${
                  isActive 
                    ? 'nav-pill-active text-accent-primary' 
                    : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary'
                }`
              }
            >
              {item.icon}
              {item.name}
            </NavLink>
          ))}
        </nav>



        {/* User Card */}
        <div className="p-3 border-t border-white/[0.06]">
          <div className="flex items-center gap-3 p-2.5 bg-white/[0.03] border border-white/[0.06] rounded-xl">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-primary/30 to-accent-primaryHover/20 flex items-center justify-center shrink-0 border border-white/10">
              <User size={16} className="text-accent-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-text-primary truncate">
                {user ? user.username : 'Guest'}
              </p>
              <p className="text-[11px] text-text-secondary truncate">
                {user ? user.email : 'Not logged in'}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-[1]">
        {/* Top Navbar */}
        <header className="h-14 bg-white/[0.03] backdrop-blur-xl border-b border-white/[0.06] flex items-center justify-between px-6 z-20 shrink-0">
          <div className="w-80 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/60" size={16} />
            <input 
              type="text" 
              placeholder="Search movies, genres, people..." 
              className="w-full bg-white/[0.04] border border-white/[0.06] rounded-full py-2 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-primary/40 focus:bg-white/[0.06] transition-all duration-200"
            />
          </div>

          <div className="relative" ref={dropdownRef}>
            <button 
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 hover:bg-white/[0.04] px-3 py-1.5 rounded-full transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-primary/30 to-accent-primaryHover/20 flex items-center justify-center border border-white/10">
                <User size={14} className="text-accent-primary" />
              </div>
              <ChevronDown size={14} className="text-text-secondary" />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-[#121620]/95 backdrop-blur-xl border border-white/[0.08] rounded-xl shadow-2xl py-1 z-30">
                <NavLink to="/profile" onClick={() => setDropdownOpen(false)} className="flex items-center gap-2 px-4 py-2.5 text-sm text-text-secondary hover:bg-white/[0.04] hover:text-text-primary transition-colors">
                  <User size={14} /> Profile
                </NavLink>
                <NavLink to="/settings" onClick={() => setDropdownOpen(false)} className="flex items-center gap-2 px-4 py-2.5 text-sm text-text-secondary hover:bg-white/[0.04] hover:text-text-primary transition-colors">
                  <Settings size={14} /> Settings
                </NavLink>
                <div className="h-px bg-white/[0.06] my-1"></div>
                <button onClick={handleLogout} className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-text-secondary hover:bg-white/[0.04] hover:text-red-400 transition-colors">
                  <LogOut size={14} /> Logout
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6 relative z-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
