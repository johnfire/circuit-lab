import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { CircuitWorkbench } from './circuit-workbench';
import { WorkbenchBoundary } from './workbench-boundary';
import './workbench.css';
import { I18nextProvider } from 'react-i18next';
import { localization, updateDocumentLanguage } from './localization.ts';

const root = document.getElementById('root');
if (!root) throw new Error('Workbench root is missing');
updateDocumentLanguage();
createRoot(root).render(<StrictMode><I18nextProvider i18n={localization}>
  <WorkbenchBoundary><CircuitWorkbench /></WorkbenchBoundary>
</I18nextProvider></StrictMode>);
