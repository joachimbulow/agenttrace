import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { isRecord } from '@/features/trace-graph/lib/payload';
import { ScalarValue } from '@/features/trace-graph/components/ScalarValue';
import { cn } from '@/shared/lib/utils';

export function PayloadTree({ value }: { value: unknown }) {
  return (
    <div className="text-[11px] leading-snug">
      <ValueView value={value} />
    </div>
  );
}

function ValueView({ value }: { value: unknown }) {
  if (isRecord(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return <span className="font-mono text-muted-foreground">{'{}'}</span>;
    }
    return (
      <div className="flex flex-col gap-0.5">
        {entries.map(([name, nested]) => (
          <FieldRow key={name} name={name} value={nested} />
        ))}
      </div>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="font-mono text-muted-foreground">[]</span>;
    }
    return (
      <div className="flex flex-col gap-0.5">
        {value.map((item, index) => (
          <FieldRow key={index} name={String(index)} value={item} />
        ))}
      </div>
    );
  }

  return <ScalarValue value={value} maxChars={Number.POSITIVE_INFINITY} wrap />;
}

function FieldRow({ name, value }: { name: string; value: unknown }) {
  const nestable = isRecord(value) || Array.isArray(value);
  const [open, setOpen] = useState(false);

  if (!nestable) {
    return (
      <div className="flex min-w-0 gap-2">
        <span className="shrink-0 font-mono text-muted-foreground">{name}</span>
        <ScalarValue value={value} maxChars={Number.POSITIVE_INFINITY} wrap />
      </div>
    );
  }

  const count = Array.isArray(value) ? value.length : Object.keys(value).length;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={cn(
          'flex max-w-full items-center gap-1 rounded-sm text-left',
          'hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'
        )}
      >
        <ChevronRight
          aria-hidden
          className={cn('h-3 w-3 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
        />
        <span className="font-mono text-muted-foreground">{name}</span>
        <span className="font-mono text-muted-foreground/80">
          {Array.isArray(value) ? `[${count}]` : `{${count}}`}
        </span>
      </button>
      {open && (
        <div className="ml-2 mt-0.5 border-l border-border pl-2">
          <ValueView value={value} />
        </div>
      )}
    </div>
  );
}
