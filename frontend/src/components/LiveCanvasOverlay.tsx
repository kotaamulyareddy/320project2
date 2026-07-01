import React, { useRef, useEffect } from 'react';

interface BoundingBox {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
  label: string;
  confidence: number;
}

interface LiveCanvasOverlayProps {
  videoElement: HTMLVideoElement | null;
  boxes: BoundingBox[];
  width: number;
  height: number;
}

const LiveCanvasOverlay: React.FC<LiveCanvasOverlayProps> = ({ videoElement, boxes, width, height }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw bounding boxes
    boxes.forEach((box) => {
      const x = box.xMin * width;
      const y = box.yMin * height;
      const w = (box.xMax - box.xMin) * width;
      const h = (box.yMax - box.yMin) * height;

      ctx.strokeStyle = '#00FF00';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      // Draw label
      ctx.fillStyle = '#00FF00';
      ctx.font = '14px Arial';
      ctx.fillText(`${box.label} (${(box.confidence * 100).toFixed(0)}%)`, x, y > 20 ? y - 5 : y + 15);
    });
  }, [boxes, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none', // Allow clicking through
      }}
    />
  );
};

export default LiveCanvasOverlay;