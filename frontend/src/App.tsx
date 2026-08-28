import { useCallback, useState } from 'react';
import { RunList } from './components/RunList/RunList';
import { TraceTree } from './components/TraceTree/TraceTree';
import { DetailsPanel } from './components/DetailsPanel/DetailsPanel';
import { ThemeToggle } from './components/ThemeToggle';
import { Button } from '@/components/ui/button';
import './App.css';

function runIdFromUrl(): string | null {
  const value = new URLSearchParams(window.location.search).get('run');
  return value ? value : null;
}

function setRunQuery(runId: string | null) {
  const url = new URL(window.location.href);
  if (runId) {
    url.searchParams.set('run', runId);
  } else {
    url.searchParams.delete('run');
  }
  window.history.replaceState(null, '', url);
}

function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(runIdFromUrl);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectRun = useCallback((runId: string) => {
    setSelectedRunId(runId);
    setSelectedNodeId(null);
    setRunQuery(runId);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agent Trace</h1>
        <span className="version">v0.1.0</span>
        <div className="header-spacer" />
        <Button size="sm" variant="secondary">shadcn/ui ready</Button>
        <ThemeToggle />
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <RunList onSelectRun={selectRun} selectedRunId={selectedRunId} />
        </aside>

        <section className="trace-view">
          <TraceTree
            runId={selectedRunId}
            onSelectNode={setSelectedNodeId}
            selectedNodeId={selectedNodeId}
          />
        </section>

        <section className="details-view">
          <DetailsPanel
            runId={selectedRunId}
            selectedNodeId={selectedNodeId}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
