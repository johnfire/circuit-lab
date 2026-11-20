import { translate } from './localization.ts';
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
      return <main className="recovery"><h1>{translate("workbench-boundary.the_workbench_needs_a_reload")}</h1>
        <p>{translate("workbench-boundary.your_circuit_library_is_still")}</p>
        <button onClick={() => window.location.reload()}>{translate("workbench-boundary.reload_workbench")}</button></main>;
    }
    return this.props.children;
  }
}
