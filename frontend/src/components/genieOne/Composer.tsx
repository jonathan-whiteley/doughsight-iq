import { CSSProperties, forwardRef, KeyboardEvent } from 'react';
import { ArrowUp, RotateCcw, Sparkles } from 'lucide-react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onReset?: () => void;
  placeholder: string;
  disabled: boolean;
}

/** Multiline composer: Enter sends, Shift+Enter adds a newline. */
const Composer = forwardRef<HTMLTextAreaElement, Props>(function Composer({ value, onChange, onSend, onReset, placeholder, disabled }, ref) {
  const canSend = !disabled && !!value.trim();
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  return (
    <div className="bg-surface rounded-2xl border border-gray-100 shadow-medium p-3 flex items-end gap-3">
      <div className="w-9 h-9 shrink-0 rounded-xl lc-gradient flex items-center justify-center">
        <Sparkles className="w-4 h-4 text-white" />
      </div>
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        className="flex-1 resize-none text-sm outline-none placeholder:text-text-tertiary max-h-40 py-2"
        style={{ fieldSizing: 'content' } as CSSProperties}
      />
      {onReset && (
        <button type="button" onClick={onReset} className="text-xs px-3 py-2 rounded-xl text-text-secondary hover:bg-gray-100 flex items-center gap-1.5">
          <RotateCcw className="w-3.5 h-3.5" />
          New chat
        </button>
      )}
      <button type="button" onClick={onSend} disabled={!canSend} className="w-9 h-9 shrink-0 rounded-xl bg-lc-orange text-white flex items-center justify-center disabled:opacity-50">
        <ArrowUp className="w-4 h-4" />
      </button>
    </div>
  );
});

export default Composer;
