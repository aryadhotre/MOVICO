import React, { useState, useEffect, useRef } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { getMe } from '../api/auth';
import SystemStatus from './SystemStatus';
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
        // user not logged in or token invalid
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
    { name: 'Home', path: '/', icon: <Home size={20} /> },
    { name: 'Browse', path: '/browse', icon: <Compass size={20} /> },
    { name: 'Trending', path: '/trending', icon: <TrendingUp size={20} /> },
    { name: 'Recommendations', path: '/recommendations', icon: <Sparkles size={20} /> },
    { name: 'Genres', path: '/genres', icon: <Tag size={20} /> },
    { name: 'Watchlist', path: '/watchlist', icon: <Bookmark size={20} /> },
    { name: 'History', path: '/history', icon: <Clock size={20} /> },
    { name: 'Ratings', path: '/ratings', icon: <Star size={20} /> },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left Sidebar */}
      <aside className="w-[260px] bg-white/5 backdrop-blur-xl border-r border-white/10 flex flex-col h-full z-10 shrink-0">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-primary to-accent-primaryHover flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.5)]">
            <Film size={18} className="text-white" />
          </div>
          <span className="text-xl font-bold tracking-widest text-text-primary">MOVICO</span>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) => 
                `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 font-medium ${
                  isActive 
                    ? 'bg-accent-primary/20 text-accent-primary shadow-[inset_0_0_10px_rgba(139,92,246,0.1)]' 
                    : 'text-text-secondary hover:bg-white/5 hover:text-text-primary'
                }`
              }
            >
              {item.icon}
              {item.name}
            </NavLink>
          ))}
        </nav>

        {/* System Status */}
        <SystemStatus />

        {/* User Card */}
        <div className="p-4 pt-0 border-t border-white/10">
          <div className="flex items-center gap-3 p-2 bg-black/20 rounded-xl mt-4">
            <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center shrink-0">
              <User size={20} className="text-text-secondary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-text-primary truncate">
                {user ? user.username : 'Guest'}
              </p>
              <p className="text-xs text-text-secondary truncate">
                {user ? user.email : 'Not logged in'}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Top Navbar */}
        <header className="h-16 bg-white/5 backdrop-blur-md border-b border-white/10 flex items-center justify-between px-8 z-20 shrink-0">
          <div className="w-96 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" size={18} />
            <input 
              type="text" 
              placeholder="Search movies, genres, actors..." 
              className="w-full bg-black/20 border border-white/10 rounded-full py-2 pl-10 pr-4 text-sm text-text-primary focus:outline-none focus:border-accent-primary/50 transition-colors"
            />
          </div>

          <div className="relative" ref={dropdownRef}>
            <button 
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 hover:bg-white/5 px-3 py-1.5 rounded-full transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
                <User size={16} className="text-text-primary" />
              </div>
              <ChevronDown size={16} className="text-text-secondary" />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-[#121620] border border-white/10 rounded-xl shadow-2xl py-1 z-30">
                <NavLink to="/profile" onClick={() => setDropdownOpen(false)} className="flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-white/5 hover:text-text-primary">
                  <User size={16} /> Profile
                </NavLink>
                <NavLink to="/settings" onClick={() => setDropdownOpen(false)} className="flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-white/5 hover:text-text-primary">
                  <Settings size={16} /> Settings
                </NavLink>
                <div className="h-px bg-white/10 my-1"></div>
                <button onClick={handleLogout} className="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-white/5 hover:text-red-400">
                  <LogOut size={16} /> Logout
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-8 relative z-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
