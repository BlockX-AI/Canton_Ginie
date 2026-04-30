"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";
import { Camera, Upload, X, RotateCw, Check } from "lucide-react";

interface ProfilePicturePickerProps {
  value: string | null; // current preview URL
  onChange: (blob: Blob | null) => void;
  email?: string; // for default avatar initials
}

type Mode = "idle" | "camera" | "preview";

const MAX_BYTES = 2 * 1024 * 1024;

export function ProfilePicturePicker({
  value,
  onChange,
  email,
}: ProfilePicturePickerProps): ReactNode {
  const [mode, setMode] = useState<Mode>("idle");
  const [previewUrl, setPreviewUrl] = useState<string | null>(value);
  const [error, setError] = useState<string>("");
  const [isCameraReady, setIsCameraReady] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Cleanup camera on unmount
  useEffect(() => {
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync external value
  useEffect(() => {
    setPreviewUrl(value);
  }, [value]);

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsCameraReady(false);
  };

  const startCamera = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 720 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      setMode("camera");
      // Wait for next render so videoRef is mounted
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.onloadedmetadata = () => {
            videoRef.current?.play();
            setIsCameraReady(true);
          };
        }
      }, 50);
    } catch (e) {
      console.error("Camera access failed", e);
      setError("Could not access camera. You can upload a photo instead.");
    }
  };

  const captureFromCamera = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    // Center-crop to square
    const size = Math.min(video.videoWidth, video.videoHeight);
    const sx = (video.videoWidth - size) / 2;
    const sy = (video.videoHeight - size) / 2;

    canvas.width = 600;
    canvas.height = 600;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Mirror horizontally so it matches the preview
    ctx.save();
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, sx, sy, size, size, 0, 0, canvas.width, canvas.height);
    ctx.restore();

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        if (blob.size > MAX_BYTES) {
          setError("Captured image too large. Try uploading a smaller photo.");
          return;
        }
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
        onChange(blob);
        stopCamera();
        setMode("preview");
      },
      "image/jpeg",
      0.9,
    );
  };

  const handleFileSelect = (file: File) => {
    setError("");
    if (!file.type.match(/^image\/(jpeg|jpg|png|webp)$/)) {
      setError("Please use a JPG, PNG, or WebP image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(`Image too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 2 MB.`);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    onChange(file);
    setMode("preview");
  };

  const removePicture = () => {
    setPreviewUrl(null);
    onChange(null);
    setMode("idle");
  };

  const initials = email ? email.slice(0, 2).toUpperCase() : "";

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Avatar / preview */}
      {mode !== "camera" && (
        <div className="relative group">
          <div
            className={`
              h-28 w-28 rounded-full overflow-hidden flex items-center justify-center
              border-2 transition-all
              ${previewUrl
                ? "border-accent/60 bg-muted"
                : "border-dashed border-border bg-muted hover:border-accent/40"
              }
            `}
          >
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={previewUrl} alt="Profile preview" className="h-full w-full object-cover" />
            ) : (
              <span className="text-3xl font-semibold text-muted-foreground select-none">
                {initials || "+"}
              </span>
            )}
          </div>

          {previewUrl && (
            <button
              type="button"
              onClick={removePicture}
              aria-label="Remove picture"
              className="absolute -top-1 -right-1 h-7 w-7 rounded-full bg-background border border-border shadow flex items-center justify-center text-muted-foreground hover:text-red-500 hover:border-red-500/50 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Camera mode */}
      {mode === "camera" && (
        <div className="relative">
          <div className="h-56 w-56 rounded-full overflow-hidden border-2 border-accent/60 bg-black flex items-center justify-center">
            <video
              ref={videoRef}
              playsInline
              muted
              className="h-full w-full object-cover"
              style={{ transform: "scaleX(-1)" }}
            />
            {!isCameraReady && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <div className="text-xs text-white">Starting camera…</div>
              </div>
            )}
          </div>
          <canvas ref={canvasRef} className="hidden" />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 w-full max-w-xs">
        {mode === "camera" ? (
          <>
            <button
              type="button"
              onClick={() => {
                stopCamera();
                setMode("idle");
              }}
              className="flex-1 px-3 py-2 rounded-xl border border-border bg-muted text-sm text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors flex items-center justify-center gap-2"
            >
              <X className="h-4 w-4" /> Cancel
            </button>
            <button
              type="button"
              onClick={captureFromCamera}
              disabled={!isCameraReady}
              className="flex-1 px-3 py-2 rounded-xl bg-accent text-black text-sm font-semibold hover:bg-accent/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
            >
              <Camera className="h-4 w-4" /> Capture
            </button>
          </>
        ) : mode === "preview" && previewUrl ? (
          <>
            <button
              type="button"
              onClick={startCamera}
              className="flex-1 px-3 py-2 rounded-xl border border-border bg-muted text-sm text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors flex items-center justify-center gap-2"
            >
              <RotateCw className="h-4 w-4" /> Retake
            </button>
            <div className="flex-1 px-3 py-2 rounded-xl border border-accent/30 bg-accent/10 text-sm text-accent flex items-center justify-center gap-2">
              <Check className="h-4 w-4" /> Looks good
            </div>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={startCamera}
              className="flex-1 px-3 py-2 rounded-xl border border-border bg-muted text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors flex items-center justify-center gap-2"
            >
              <Camera className="h-4 w-4" /> Take photo
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 px-3 py-2 rounded-xl border border-border bg-muted text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors flex items-center justify-center gap-2"
            >
              <Upload className="h-4 w-4" /> Upload
            </button>
          </>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelect(file);
          e.target.value = ""; // allow re-selecting same file
        }}
      />

      {error && (
        <p className="text-xs text-red-500 text-center max-w-xs">{error}</p>
      )}

      <p className="text-[11px] text-muted-foreground text-center">
        Optional · JPG, PNG or WebP · Max 2 MB
      </p>
    </div>
  );
}
