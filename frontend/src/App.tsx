import { useCallback, useEffect, useMemo, useState } from 'react';
import { RunList } from './components/RunList/RunList';
import { RecordList } from './components/RecordList/RecordList';
import { RunGraph } from './components/RunGraph/RunGraph';
import { StreamIndicator } from './components/StreamIndicator';
import { ThemeToggle } from './components/ThemeToggle';
import { useRecordStream } from './hooks/useRecordStream';
import { useRecord, useRecords } from './hooks/useRecords';
import './App.css';

/** Selection in the URL: `run` scopes the list, `record` is the canvas. */
interface Selection {
  runId: string | null;
  recordId: string | null;
}

function selectionFromUrl(): Selection {
  const params = new URLSearchParams(window.location.search);
  return { runId: params.get('run'), recordId: params.get('record') };
}

function writeSelection({ runId, recordId }: Selection) {
  const url = new URL(window.location.href);
  runId ? url.searchParams.set('run', runId) : url.searchParams.delete('run');
  recordId ? url.searchParams.set('record', recordId) : url.searchParams.delete('record');
  window.history.replaceState(null, '', url);
}

function App() {
  const [selection, setSelection] = useState<Selection>(selectionFromUrl);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => writeSelection(selection), [selection]);

  // One stream: the ping carries the run, so list + canvas share it. ADR-0001.
  const stream = useRecordStream(selection.recordId);

  const { data: recordList, loading: recordsLoading, error: recordsError } = useRecords(
    selection.runId,
    stream.rev
  );
  const { data: record, loading: recordLoading } = useRecord(
    selection.recordId,
    stream.rev
  );

  const records = useMemo(() => recordList?.records ?? [], [recordList]);
  const selectedRecord = useMemo(
    () => records.find((r) => r.id === selection.recordId) ?? null,
    [records, selection.recordId]
  );

  const selectRun = useCallback((runId: string) => {
    setSelection({ runId, recordId: null });
    setSelectedNodeId(null);
  }, []);

  const selectRecord = useCallback((recordId: string) => {
    setSelection((current) => ({ ...current, recordId }));
    setSelectedNodeId(null);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agent Trace</h1>
        <span className="version">v0.1.0</span>
        <div className="header-spacer" />
        {selection.recordId && (
          <StreamIndicator status={stream.status} lastPingAt={stream.lastPingAt} />
        )}
        <ThemeToggle />
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <SidebarSection title="Runs">
            <RunList onSelectRun={selectRun} selectedRunId={selection.runId} />
          </SidebarSection>
          <SidebarSection
            title={`Records${records.length ? ` (${records.length})` : ''}`}
            grow
          >
            <RecordList
              records={records}
              runSelected={Boolean(selection.runId)}
              loading={recordsLoading}
              error={recordsError}
              selectedRecordId={selection.recordId}
              onSelectRecord={selectRecord}
            />
          </SidebarSection>
        </aside>

        <section className="graph-view">
          <RunGraph
            root={record?.root ?? null}
            record={selectedRecord}
            loading={recordLoading}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
        </section>
      </main>
    </div>
  );
}

function SidebarSection({
  title,
  grow,
  children,
}: {
  title: string;
  grow?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`sidebar-section${grow ? ' sidebar-section-grow' : ''}`}
    >
      <h2 className="sidebar-title">{title}</h2>
      <div className="sidebar-body">{children}</div>
    </section>
  );
}

export default App;
