"use client";

import { useRef, useEffect, useState, type ReactNode } from "react";

interface OTPInputProps {
  length?: number;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  disabled?: boolean;
  error?: boolean;
}

export function OTPInput({
  length = 6,
  value,
  onChange,
  onComplete,
  disabled = false,
  error = false,
}: OTPInputProps): ReactNode {
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);
  const [shake, setShake] = useState(false);

  useEffect(() => {
    if (!error) return;
    setShake(true);
    const t = setTimeout(() => setShake(false), 500);
    return () => clearTimeout(t);
  }, [error]);

  // Auto-focus first input on mount
  useEffect(() => {
    if (!disabled) inputsRef.current[0]?.focus();
  }, [disabled]);

  const setDigit = (index: number, digit: string) => {
    const cleaned = digit.replace(/\D/g, "");
    if (!cleaned) return;
    const chars = value.padEnd(length, " ").split("");
    chars[index] = cleaned[0]!;
    const next = chars.join("").trim();
    onChange(next);

    if (index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
    if (next.length === length && onComplete) {
      onComplete(next);
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      const chars = value.padEnd(length, " ").split("");
      if (chars[index] && chars[index] !== " ") {
        chars[index] = "";
        onChange(chars.join("").trimEnd());
      } else if (index > 0) {
        chars[index - 1] = "";
        onChange(chars.join("").trimEnd());
        inputsRef.current[index - 1]?.focus();
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      inputsRef.current[index - 1]?.focus();
    } else if (e.key === "ArrowRight" && index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (pasted) {
      onChange(pasted);
      if (pasted.length === length && onComplete) onComplete(pasted);
      inputsRef.current[Math.min(pasted.length, length - 1)]?.focus();
    }
  };

  const digits = value.padEnd(length, " ").split("").slice(0, length);

  return (
    <div className={`flex gap-2 sm:gap-3 justify-center ${shake ? "animate-shake" : ""}`}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => {
            inputsRef.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          maxLength={1}
          value={d.trim()}
          disabled={disabled}
          onChange={(e) => setDigit(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          className={`
            h-14 w-11 sm:h-16 sm:w-12 text-center text-2xl font-semibold rounded-xl
            border-2 transition-all
            bg-muted text-foreground
            focus:outline-none focus:ring-2 focus:ring-accent/40
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error
              ? "border-red-500/60 focus:border-red-500"
              : d.trim()
                ? "border-accent/60 focus:border-accent bg-accent/5"
                : "border-border focus:border-accent"
            }
          `}
        />
      ))}
      <style jsx>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%, 60% { transform: translateX(-8px); }
          40%, 80% { transform: translateX(8px); }
        }
        .animate-shake {
          animation: shake 0.4s ease-in-out;
        }
      `}</style>
    </div>
  );
}
