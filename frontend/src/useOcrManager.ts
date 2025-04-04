import { useRef, useState, useEffect } from "react";
import { Streamlit } from "streamlit-component-lib";

interface Rectangle {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  stroke: string;
  id: string;
}

interface UseOcrManagerProps {
  rectangles: Rectangle[];
  scale: number;
  mode: string;
}

export const useOcrManager = ({ rectangles, scale, mode }: UseOcrManagerProps) => {
  const [suggestedLabels, setSuggestedLabels] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const pendingRef = useRef(false);
  const prevTriggerRef = useRef<string | null>(null);
  const [triggerId, setTriggerId] = useState<string | null>(null);

  const formatBBoxes = (rects: Rectangle[]) =>
    rects.map((rect) => ({
      box_id: rect.id,
      bbox: [rect.x, rect.y, rect.width, rect.height],
      label: rect.label || "",
    }));

  // OCR 요청 트리거
  const requestOcrForBox = (boxId: string) => {
    if (pendingRef.current || prevTriggerRef.current === boxId) return;

    const box = rectangles.find((r) => r.id === boxId);
    if (!box) return;

    pendingRef.current = true;
    prevTriggerRef.current = boxId;
    setIsLoading(true);

    Streamlit.setComponentValue({
      mode,
      bboxes: formatBBoxes(rectangles),
      scale,
      request_ocr: true,
      selected_box_id: boxId,
      selected_box_coords: [box.x, box.y, box.width, box.height]
    });

    setTriggerId(boxId); // 내부 상태 유지
  };

  // OCR 응답 수신 후 호출
  const handleOcrResponse = (suggestions: string[]) => {
    if (!suggestions || suggestions.length === 0) return;
    setSuggestedLabels(suggestions);
    setShowSuggestions(true);
    setIsLoading(false);
    resetOcrState(); // 응답 도착 후 상태 초기화
  };

  // 외부에서 OCR 상태 초기화 (ex: args.request_ocr === false)
  const resetOcrState = () => {
    pendingRef.current = false;
    prevTriggerRef.current = null;
    setTriggerId(null);
  };

  return {
    requestOcrForBox,
    handleOcrResponse,
    resetOcrState,
    suggestedLabels,
    showSuggestions,
    isLoading,
    setShowSuggestions
  };
};
