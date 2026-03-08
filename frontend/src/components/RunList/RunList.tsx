import { useRuns } from '../../hooks/useRuns';
import './RunList.css';

export interface RunListProps {
  onSelectRun: (runId: string) => void;
  selectedRunId: string | null;
}

export function RunList({ onSelectRun, selectedRunId }: RunListProps) {
  const { data, loading, error, refetch } = useRuns({ limit: 50 });

  if (loading) {
    return <div className="run-list-loading">Loading runs...</div>;
  }

  if (error) {
    return (
      <div className="run-list-error">
        <p>Error: {error.message}</p>
        <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  if (!data || data.runs.length === 0) {
    return (
      <div className="run-list-empty">
        <p>No runs found</p>
        <p className="hint">Run your agent with tracing enabled to see traces here.</p>
      </div>
    );
  }

  return (
    <div className="run-list">
      <div className="run-list-header">
        <h2>Runs ({data.total})</h2>
        <button onClick={() => refetch()} className="refresh-btn">
          Refresh
        </button>
      </div>
      <table className="run-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Started</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {data.runs.map((run) => (
            <tr
              key={run.id}
              className={`run-row ${selectedRunId === run.id ? 'selected' : ''}`}
              onClick={() => onSelectRun(run.id)}
            >
              <td className="run-name">{run.name}</td>
              <td>
                <span className={`status-badge status-${run.status}`}>
                  {run.status}
                </span>
              </td>
              <td className="run-started">
                {new Date(run.started_at).toLocaleString()}
              </td>
              <td className="run-duration">
                {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}