import { Component } from 'react';
import { Link } from 'react-router-dom';

export default class ErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // RUM automatically captures this via the global error handler
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">💥</div>
          <h2 className="text-xl font-bold text-red-700 mb-2">Something crashed</h2>
          <p className="text-red-500 text-sm mb-4 max-w-md mx-auto font-mono bg-red-50 p-3 rounded-lg">
            {this.state.error?.message}
          </p>
          <Link
            to="/"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-purple-700"
          >
            Back to safety
          </Link>
        </div>
      );
    }
    return this.props.children;
  }
}
