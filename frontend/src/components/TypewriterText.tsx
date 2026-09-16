import React, { useState, useEffect } from "react";

interface TypewriterTextProps {
  text: string;
  speed?: number; // Base typing speed in ms
  initialDelay?: number; // Delay before typing starts in ms
  onComplete?: () => void;
  className?: string;
  style?: React.CSSProperties;
  showCursor?: boolean;
}

/**
 * TypewriterText: Natural Letter-by-Letter Cinematic Typewriter Animation
 *
 * - Smooth natural character-by-character reveal
 * - Organic delay variations (longer pause for punctuation/spaces)
 * - Zero layout shift (preserves dimensions)
 * - Blinking caret that fades out upon completion
 * - Full accessibility with prefers-reduced-motion support
 */
export const TypewriterText: React.FC<TypewriterTextProps> = ({
  text,
  speed = 36,
  initialDelay = 150,
  onComplete,
  className,
  style,
  showCursor = true,
}) => {
  const isReducedMotion = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [displayedLength, setDisplayedLength] = useState<number>(() => isReducedMotion ? text.length : 0);
  const [isTypingComplete, setIsTypingComplete] = useState<boolean>(() => isReducedMotion);
  const [caretVisible, setCaretVisible] = useState<boolean>(() => !isReducedMotion);

  useEffect(() => {
    if (isReducedMotion) {
      onComplete?.();
      return;
    }

    let timeoutId: ReturnType<typeof setTimeout>;
    let currentIndex = 0;

    const typeNextChar = () => {
      if (currentIndex < text.length) {
        currentIndex++;
        setDisplayedLength(currentIndex);

        const currentChar = text[currentIndex - 1];
        let charDelay = speed + (Math.random() * 20 - 10);

        // Organic pause at punctuation and comma/period
        if (currentChar === "." || currentChar === "!" || currentChar === "?") {
          charDelay += 180;
        } else if (currentChar === "," || currentChar === "—" || currentChar === "•") {
          charDelay += 100;
        } else if (currentChar === " ") {
          charDelay += 30;
        }

        timeoutId = setTimeout(typeNextChar, Math.max(charDelay, 15));
      } else {
        setIsTypingComplete(true);
        onComplete?.();
        // Fade out caret after typing ends
        timeoutId = setTimeout(() => {
          setCaretVisible(false);
        }, 1200);
      }
    };

    timeoutId = setTimeout(typeNextChar, initialDelay);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [text, speed, initialDelay, onComplete, isReducedMotion]);

  return (
    <span className={className} style={{ ...style, display: "inline" }}>
      {text.slice(0, displayedLength)}
      {showCursor && caretVisible && (
        <span
          className="typewriter-caret"
          aria-hidden="true"
          style={{
            display: "inline-block",
            marginLeft: "2px",
            width: "2px",
            height: "1.05em",
            verticalAlign: "middle",
            background: "var(--accent-cyan, #00f0ff)",
            boxShadow: "0 0 8px rgba(0, 240, 255, 0.6)",
            animation: "typewriterBlink 0.8s ease-in-out infinite",
            transition: "opacity 0.5s ease",
            opacity: isTypingComplete ? 0.4 : 1,
          }}
        />
      )}
    </span>
  );
};

export default TypewriterText;
