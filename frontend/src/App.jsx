import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import PublicShell from './components/PublicShell';
import PageSpinner from './components/PageSpinner';
import ErrorBoundary from './components/ErrorBoundary';
import { useAuth } from './lib/auth';

/**
 * Routes are code-split so the landing page does not ship the entire app.
 * A first-time visitor downloads the marketing page and nothing else.
 */
const Landing = lazy(() => import('./pages/Landing'));
const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const Onboarding = lazy(() => import('./pages/Onboarding'));
const Home = lazy(() => import('./pages/Home'));
const Browse = lazy(() => import('./pages/Browse'));
const MovieDetail = lazy(() => import('./pages/MovieDetail'));
const Recommendations = lazy(() => import('./pages/Recommendations'));
const Watchlist = lazy(() => import('./pages/Watchlist'));
const Ratings = lazy(() => import('./pages/Ratings'));
const Profile = lazy(() => import('./pages/Profile'));
const NotFound = lazy(() => import('./pages/NotFound'));

/** Blocks a route until auth state is known, so a signed-in reload does not bounce. */
function RequireAuth({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <PageSpinner />;
  if (!isAuthenticated) {
    // Remember where they were headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

/** Keeps a signed-in user off the marketing and auth pages. */
function RedirectIfAuthed({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageSpinner />;
  if (isAuthenticated) return <Navigate to="/app" replace />;
  return children;
}

export default function App() {
  const location = useLocation();

  return (
    // The boundary resets on navigation: a render error is deterministic, so the
    // only thing that reliably clears it is mounting a different tree.
    <ErrorBoundary resetKey={location.pathname}>
      <Suspense fallback={<PageSpinner />}>
      <Routes>
        <Route
          path="/"
          element={
            <RedirectIfAuthed>
              <Landing />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/login"
          element={
            <RedirectIfAuthed>
              <Login />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/signup"
          element={
            <RedirectIfAuthed>
              <Signup />
            </RedirectIfAuthed>
          }
        />

        {/* Public browsing: someone should be able to look before signing up. */}
        <Route element={<PublicShell />}>
          <Route path="/discover" element={<Browse publicMode />} />
          <Route path="/movie/:id" element={<MovieDetail />} />
        </Route>

        <Route
          path="/onboarding"
          element={
            <RequireAuth>
              <Onboarding />
            </RequireAuth>
          }
        />

        <Route
          path="/app"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Home />} />
          <Route path="recommendations" element={<Recommendations />} />
          <Route path="browse" element={<Browse />} />
          <Route path="watchlist" element={<Watchlist />} />
          <Route path="ratings" element={<Ratings />} />
          <Route path="profile" element={<Profile />} />
        </Route>

        <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
