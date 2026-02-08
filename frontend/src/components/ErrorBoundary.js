import React, { Component } from 'react';
import { AlertTriangle } from 'lucide-react';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo,
    });
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex items-center justify-center min-h-screen bg-bg p-6"
          data-testid="error-boundary"
        >
          <div className="max-w-md w-full bg-surface border border-border rounded-sm p-6 text-center">
            <AlertTriangle size={48} className="mx-auto text-destructive mb-4" />
            <h2 className="font-heading font-bold text-xl text-text-primary mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-text-secondary mb-4">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            {process.env.NODE_ENV === 'development' && this.state.errorInfo && (
              <details className="mb-4 text-left">
                <summary className="text-xs text-text-muted cursor-pointer mb-2">
                  Error Details (Dev Only)
                </summary>
                <pre className="text-xs text-text-muted bg-bg p-2 rounded-sm border border-border overflow-auto max-h-40">
                  {this.state.error?.stack}
                </pre>
              </details>
            )}
            <button
              onClick={this.handleReload}
              className="px-4 py-2 bg-primary text-white rounded-sm font-medium hover:bg-primary-hover transition-colors"
              data-testid="reload-button"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

