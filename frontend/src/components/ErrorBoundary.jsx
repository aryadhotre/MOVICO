import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * Catches render errors so one broken component cannot white-screen the app.
 *
 * Has to be a class: `componentDidCatch` and `getDerivedStateFromError` have no
 * hook equivalent, and React still offers no functional API for error boundaries.
 *
 * Reloading is offered rather than a "try again" that re-renders the same tree —
 * a render error is almost always deterministic, so retrying in place just fails
 * again. The reset path clears the boundary only when the route changes, which is
 * the one case where a different tree will actually mount.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Surfaced in the console for local debugging; there is no error service to
    // report to, and swallowing it silently would make this harder to diagnose.
    console.error('Render error caught by boundary:', error, info?.componentStack);
  }

  componentDidUpdate(previous) {
    if (this.state.error && previous.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex min-h-[60svh] flex-col items-center justify-center px-6 text-center">
        <AlertTriangle className="h-8 w-8 text-tungsten-500" strokeWidth={1.4} />
        <h1 className="title-card mt-6 text-2xl text-print-50">The reel jammed</h1>
        <p className="mt-4 max-w-sm text-pretty text-sm leading-relaxed text-print-400">
          Something broke while rendering this page. Reloading usually clears it.
        </p>

        {import.meta.env.DEV && (
          <pre className="mt-6 max-w-xl overflow-x-auto border border-reel-500/30 bg-reel-600/10 p-4 text-left font-mono text-[10px] leading-relaxed text-reel-400">
            {String(this.state.error?.message ?? this.state.error)}
          </pre>
        )}

        <button
          type="button"
          onClick={() => window.location.reload()}
          className="btn-primary mt-8"
        >
          <RefreshCw className="h-4 w-4" />
          Reload
        </button>
      </div>
    );
  }
}
