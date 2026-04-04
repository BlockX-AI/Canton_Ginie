"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface MermaidDiagramProps {
  chart: string;
  className?: string;
}

export function MermaidDiagram({ chart, className = "" }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const idRef = useRef(0);

  const renderChart = useCallback(async (chartStr: string) => {
    try {
      const mermaid = (await import("mermaid")).default;

      mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        themeVariables: {
          darkMode: true,
          background: "transparent",
          primaryColor: "#6366f1",
          primaryTextColor: "#e2e8f0",
          primaryBorderColor: "#818cf8",
          lineColor: "#94a3b8",
          secondaryColor: "#1e293b",
          tertiaryColor: "#0f172a",
          fontFamily: "system-ui, sans-serif",
          fontSize: "14px",
        },
        flowchart: {
          htmlLabels: true,
          curve: "basis",
          padding: 16,
          nodeSpacing: 40,
          rankSpacing: 50,
        },
      });

      idRef.current += 1;
      const id = `mermaid-diagram-${idRef.current}`;
      const { svg } = await mermaid.render(id, chartStr);
      setSvgContent(svg);
      setError(null);
    } catch (err) {
      console.error("Mermaid render error:", err);
      setError("Failed to render diagram");
    }
  }, []);

  useEffect(() => {
    if (!chart) return;
    setSvgContent("");
    setError(null);
    renderChart(chart);
  }, [chart, renderChart]);

  if (error) {
    return (
      <div className={`rounded-2xl border border-border bg-muted/50 p-6 text-center text-muted-foreground ${className}`}>
        <p className="text-sm">{error}</p>
        <pre className="mt-3 max-h-40 overflow-auto rounded-xl bg-background p-3 text-left text-xs text-muted-foreground">
          {chart}
        </pre>
      </div>
    );
  }

  if (!svgContent) {
    return (
      <div className={`flex items-center justify-center rounded-2xl border border-border bg-muted/50 p-12 ${className}`}>
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-foreground" />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`overflow-auto rounded-2xl border border-border bg-muted/30 p-4 [&_svg]:mx-auto [&_svg]:max-w-full ${className}`}
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  );
}
