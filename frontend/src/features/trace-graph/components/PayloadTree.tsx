import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { isRecord } from '@/features/trace-graph/lib/payload';
import { ScalarValue } from '@/features/trace-graph/components/ScalarValue';
import { cn } from '@/shared/lib/utils';

export function PayloadTree({ value }: { value: unknown }) {
  return (
    <div className="text-[12px] leading-relaxed">
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
      <div className="flex flex-col gap-2">
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
      <div className="flex flex-col gap-2">
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
  const [open, setOpen] = useState(true);

  if (!nestable) {
    return (
      <div className="flex min-w-0 items-baseline gap-3">
        <span className="w-[7.5rem] shrink-0 truncate font-mono text-[11px] text-muted-foreground">
          {name}
        </span>
        <ScalarValue value={value} maxChars={Number.POSITIVE_INFINITY} wrap />
      </div>
    );
  }

  const count = Array.isArray(value) ? value.length : Object.keys(value).length;

  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={cn(
          'flex max-w-full items-center gap-1.5 rounded-sm py-0.5 text-left',
          'hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'
        )}
      >
        <ChevronDown
          aria-hidden
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
            !open && '-rotate-90'
          )}
        />
        <span className="font-mono text-[11px] text-muted-foreground">{name}</span>
        <span className="font-mono text-[11px] text-muted-foreground/70">
          {Array.isArray(value) ? `[${count}]` : `{${count}}`}
        </span>
      </button>
      {open && (
        <div className="ml-1.5 border-l border-border/80 py-1 pl-3">
          <ValueView value={value} />
        </div>
      )}
    </div>
  );
}
