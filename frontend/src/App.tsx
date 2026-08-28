import { useCallback, useEffect, useMemo, useState } from 'react';
import { RunList } from './components/RunList/RunList';
import { RowList } from './components/RowList/RowList';
import { RunGraph } from './components/RunGraph/RunGraph';
import { StreamIndicator } from './components/StreamIndicator';
import { ThemeToggle } from './components/ThemeToggle';
import { useRowStream } from './hooks/useRowStream';
import { useRow, useRows } from './hooks/useRows';
import './App.css';

/**
 * Selection lives in the URL so a view is linkable and survives a reload.
 * `row` is the one the canvas renders; `run` scopes the row list.
 */
interface Selection {
  runId: string | null;
  rowId: string | null;
}

function selectionFromUrl(): Selection {
  const params = new URLSearchParams(window.location.search);
  return { runId: params.get('run'), rowId: params.get('row') };
}

function writeSelection({ runId, rowId }: Selection) {
  const url = new URL(window.location.href);
  runId ? url.searchParams.set('run', runId) : url.searchParams.delete('run');
  rowId ? url.searchParams.set('row', rowId) : url.searchParams.delete('row');
  window.history.replaceState(null, '', url);
}

function App() {
  const [selection, setSelection] = useState<Selection>(selectionFromUrl);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => writeSelection(selection), [selection]);

  // One subscription drives everything. The ping carries the run, so the
  // row list and the canvas both refresh off the same stream rather than
  // opening a connection each. See ADR-0001.
  const stream = useRowStream(selection.rowId);

  const { data: rowList, loading: rowsLoading, error: rowsError } = useRows(
    selection.runId,
    stream.rev
  );
  const { data: row, loading: rowLoading } = useRow(selection.rowId, stream.rev);

  const rows = useMemo(() => rowList?.rows ?? [], [rowList]);
  const selectedRow = useMemo(
    () => rows.find((r) => r.row_id === selection.rowId) ?? null,
    [rows, selection.rowId]
  );

  const selectRun = useCallback((runId: string) => {
    setSelection({ runId, rowId: null });
    setSelectedNodeId(null);
  }, []);

  const selectRow = useCallback((rowId: string) => {
    setSelection((current) => ({ ...current, rowId }));
    setSelectedNodeId(null);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agent Trace</h1>
        <span className="version">v0.1.0</span>
        <div className="header-spacer" />
        {selection.rowId && (
          <StreamIndicator status={stream.status} lastPingAt={stream.lastPingAt} />
        )}
        <ThemeToggle />
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <SidebarSection title="Runs">
            <RunList onSelectRun={selectRun} selectedRunId={selection.runId} />
          </SidebarSection>
          <SidebarSection title={`Rows${rows.length ? ` (${rows.length})` : ''}`} grow>
            <RowList
              rows={rows}
              runSelected={Boolean(selection.runId)}
              loading={rowsLoading}
              error={rowsError}
              selectedRowId={selection.rowId}
              onSelectRow={selectRow}
            />
          </SidebarSection>
        </aside>

        <section className="graph-view">
          <RunGraph
            root={row?.root ?? null}
            row={selectedRow}
            loading={rowLoading}
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
