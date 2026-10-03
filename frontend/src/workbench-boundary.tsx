import { Component, type ErrorInfo, type ReactNode } from 'react';

export class WorkbenchBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  componentDidCatch(error: Error, context: ErrorInfo): void {
    console.error('Workbench rendering failed', error, context.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return <main className="recovery"><h1>The workbench needs a reload.</h1>
        <p>Your circuit library is still available.</p>
        <button onClick={() => window.location.reload()}>Reload workbench</button></main>;
    }
    return this.props.children;
  }
}
