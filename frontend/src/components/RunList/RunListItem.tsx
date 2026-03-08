import type { Run } from '../../types';

export interface RunListItemProps {
  run: Run;
  isSelected: boolean;
  onSelect: () => void;
}

export function RunListItem({ run, isSelected, onSelect }: RunListItemProps) {
  return (
    <div
      className={`run-list-item ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <div className="run-info">
        <span className="run-name">{run.name}</span>
        <span className={`status-badge status-${run.status}`}>
          {run.status}
        </span>
      </div>
      <div className="run-meta">
        <span className="run-duration">
          {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : 'running'}
        </span>
        <span className="run-time">
          {new Date(run.started_at).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}