export interface JsonViewProps {
  data: Record<string, unknown>;
}

export function JsonView({ data }: JsonViewProps) {
  return (
    <div className="json-view">
      <pre className="json-content">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}