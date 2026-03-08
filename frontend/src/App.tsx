import { useState } from 'react';
import { RunList } from './components/RunList/RunList';
import { TraceTree } from './components/TraceTree/TraceTree';
import { DetailsPanel } from './components/DetailsPanel/DetailsPanel';
import './App.css';

function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agent Trace</h1>
        <span className="version">v0.1.0</span>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <RunList
            onSelectRun={(runId) => {
              setSelectedRunId(runId);
              setSelectedNodeId(null);
            }}
            selectedRunId={selectedRunId}
          />
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
