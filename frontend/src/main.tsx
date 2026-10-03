import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { CircuitWorkbench } from './circuit-workbench';
import { WorkbenchBoundary } from './workbench-boundary';
import './workbench.css';

const root = document.getElementById('root');
if (!root) throw new Error('Workbench root is missing');
createRoot(root).render(
  <StrictMode><WorkbenchBoundary><CircuitWorkbench /></WorkbenchBoundary></StrictMode>,
);
