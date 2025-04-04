import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps
} from "streamlit-component-lib"
import React, { useEffect, useState, useRef } from "react"
import { ChakraProvider, Input, Box, HStack, VStack, Center, Button, Text, Flex } from '@chakra-ui/react'
import { extendTheme } from '@chakra-ui/react';
import useImage from 'use-image';
import BBoxCanvas from "./BBoxCanvas";
import { useOcrManager } from "./useOcrManager"; // OCR 훅
import debounce from 'lodash/debounce'; // 🔄 줌 최적화를 위한 debounce 추가


// Chakra UI 테마 설정
const theme = extendTheme({
  config: {
    initialColorMode: 'light',
    useSystemColorMode: false,
  },
});

// Python에서 전달된 파라미터 정의
export interface PythonArgs {
  image_url: string,
  image_size: number[],
  bbox_info: any[],
  color_map: any,
  line_width: number,
  use_space: boolean,
  ocr_suggestions: string[],
  request_ocr?: boolean
}

// BBox 타입 정의
interface Rectangle {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  stroke: string;
  id: string;
}

// Python에서 사용할 형식으로 포맷
const formatBBoxes = (rects: Rectangle[]) =>
  rects.map((rect) => ({
    box_id: rect.id,
    bbox: [rect.x, rect.y, rect.width, rect.height],
    label: rect.label || "",
  }));

// 컴포넌트 본체
const Detection = ({ args }: ComponentProps) => {
  const {
    image_url,
    image_size,
    bbox_info,
    color_map,
    line_width,
    use_space,
    ocr_suggestions
  }: PythonArgs = args

  const params = new URLSearchParams(window.location.search);
  const baseUrl = params.get('streamlitUrl');
  const [image] = useImage(baseUrl + image_url);

  const [rectangles, setRectangles] = useState<Rectangle[]>(
    bbox_info.map((bb, i) => ({
      x: bb.bbox[0],
      y: bb.bbox[1],
      width: bb.bbox[2],
      height: bb.bbox[3],
      label: bb.label,
      stroke: "#39FF14",
      id: 'bbox-' + i
    }))
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [mode, setMode] = useState<string>('Draw');
  const [isLabelEditMode, setIsLabelEditMode] = useState(false);
  const [scale, setScale] = useState(1.0);
  const [saveNotification, setSaveNotification] = useState(false);
  const [showLabels, setShowLabels] = useState(false);

  const canvasWrapperRef = useRef<HTMLDivElement>(null); // 🔍 캔버스 영역 추적용 ref

  const {
    requestOcrForBox,
    handleOcrResponse,
    resetOcrState,
    suggestedLabels,
    showSuggestions,
    isLoading: isLoadingLabels,
    setShowSuggestions
  } = useOcrManager({ rectangles, scale, mode });

  useEffect(() => {
    if (selectedId) {
      const selectedRect = rectangles.find(rect => rect.id === selectedId);
      if (selectedRect) {
        setLabel(selectedRect.label);
      }
    }
  }, [selectedId, rectangles]);

  const handleLabelInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setLabel(event.target.value);
  };

  const commitLabelChange = () => {
    if (selectedId !== null) {
      setRectangles((prev) =>
        prev.map((rect) =>
          rect.id === selectedId ? { ...rect, label: label, stroke: "#39FF14" } : rect
        )
      );
    }
  };

  // // OCR 요청을 위한 함수
  // useEffect(() => {
  //   if (args.ocr_suggestions && args.ocr_suggestions.length > 0) {
  //     handleOcrResponse(args.ocr_suggestions);
  //   }
  // }, [args.ocr_suggestions]);

  const previousOcrRef = useRef<string[] | null>(null); // ✅ 이전 OCR 결과 캐시
  console.log(args.request_ocr, args.ocr_suggestions, previousOcrRef.current);
  useEffect(() => {
    if (
      args.request_ocr === true &&
      args.ocr_suggestions &&
      args.ocr_suggestions.length > 0 &&
      JSON.stringify(args.ocr_suggestions) !== JSON.stringify(previousOcrRef.current)
    ) {
      previousOcrRef.current = args.ocr_suggestions; // ✅ 중복 방지용 캐시 업데이트
      handleOcrResponse(args.ocr_suggestions); // ✅ OCR 결과 반영
      sendToStreamlit({ request_ocr: false }); // ✅ JS 측에서도 OCR 요청 종료 신호

      console.log("request_ocr 변했나??", args.request_ocr);
    }
  }, [args.ocr_suggestions, args.ocr_suggestions]);

  // OCR 응답을 처리하는 함수
  useEffect(() => {
    const onDataFromPython = (event: MessageEvent) => {
      if (event.data.type === 'streamlit:render') {
        try {
          const args = event.data.args;
          if (args?.ocr_suggestions && Array.isArray(args.ocr_suggestions)) {
            handleOcrResponse(args.ocr_suggestions);
          }
        } catch (error) {
          console.error("Error handling OCR suggestions from message:", error);
        }
      }
    };
    window.addEventListener('message', onDataFromPython);
    return () => window.removeEventListener('message', onDataFromPython);
  }, []);

  useEffect(() => {
    if (args.request_ocr === false || args.request_ocr === undefined) {
      resetOcrState();
    }
  }, [args.request_ocr]);

  // 🔄 줌 최적화를 위한 debounce 설정
  const debouncedUpdateFrameHeight = debounce(() => {
    if (image_size[1] > 0) {
      Streamlit.setFrameHeight(image_size[1] * scaleRef.current + 100);
    }
  }, 100); // ← 100ms 안에 1번만 실행
  
  useEffect(() => {
    const initializeScale = () => {
      if (scale === 1.0 && image_size[0] > 0) {
        const scale_ratio = window.innerWidth * 0.8 / image_size[0];
        setScale(Math.min(scale_ratio, 1.0));
      }
    };

    initializeScale();
    debouncedUpdateFrameHeight();
    window.addEventListener('resize', debouncedUpdateFrameHeight);
    return () => {
      window.removeEventListener('resize', debouncedUpdateFrameHeight);
    };
  }, [image_size, scale]);

  const modeRef = useRef(mode);
  const selectedIdRef = useRef(selectedId);
  const useSpaceRef = useRef(use_space);
  const isLabelEditModeRef = useRef(isLabelEditMode);
  const rectanglesRef = useRef(rectangles);
  const scaleRef = useRef(scale);

  useEffect(() => { modeRef.current = mode }, [mode]);
  useEffect(() => { selectedIdRef.current = selectedId }, [selectedId]);
  useEffect(() => { useSpaceRef.current = use_space }, [use_space]);
  useEffect(() => { isLabelEditModeRef.current = isLabelEditMode }, [isLabelEditMode]);
  useEffect(() => { rectanglesRef.current = rectangles }, [rectangles]);
  useEffect(() => { scaleRef.current = scale }, [scale]);

  const buildPayload = (options: {
    mode?: string;
    selectedBoxId?: string | null;
    save_requested?: boolean;
    request_ocr?: boolean;
  } = {}) => {
    const currentMode = options.mode ?? modeRef.current;
    const selectedBoxId = options.selectedBoxId ?? selectedIdRef.current;
    const currentRectangles = rectanglesRef.current;
    const currentScale = scaleRef.current;

    const selectedBox = currentRectangles.find(box => box.id === selectedBoxId);

    const payload: any = {
      mode: currentMode,
      bboxes: formatBBoxes(currentRectangles),
      scale: currentScale,
      save_requested: options.save_requested ?? false,
      request_ocr: options.request_ocr ?? false
    };

    if (selectedBox) {
      payload.selected_box_id = selectedBox.id;
      payload.selected_box_coords = [
        selectedBox.x,
        selectedBox.y,
        selectedBox.width,
        selectedBox.height
      ];
    }

    return payload;
  };

  const sendToStreamlit = (options = {}) => {
    const payload = buildPayload(options);
    Streamlit.setComponentValue(payload);
  };

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      const mode = modeRef.current;
      const selectedId = selectedIdRef.current;
      const use_space = useSpaceRef.current;
      const isLabelEditMode = isLabelEditModeRef.current;
      const rectangles = rectanglesRef.current;

      if (use_space && event.code === "Space") {
        sendToStreamlit();
      }

      if (event.ctrlKey && event.code === "KeyE") {
        event.preventDefault();
        setMode("Edit");
        sendToStreamlit({ mode: "Edit" });
      }

      if (event.ctrlKey && event.code === "KeyD") {
        event.preventDefault();
        setMode("Draw");
        sendToStreamlit({ mode: "Draw" });
      }

      if (event.ctrlKey && event.code === "KeyL") {
        event.preventDefault();
        if (selectedId) {
          setIsLabelEditMode(true);
          setShowSuggestions(true);
        }
      }

      if (event.ctrlKey && event.code === "KeyM") {
        event.preventDefault();
        if (selectedId) {
          requestOcrForBox(selectedId);
        }
      }

      if (event.ctrlKey && event.code === "KeyR") {
        event.preventDefault();
        setShowLabels(prev => !prev);
      }

      if (event.ctrlKey && event.code === "KeyS") {
        event.preventDefault();
        setSaveNotification(true);
        setTimeout(() => {
          setSaveNotification(false);
        }, 3000);
        sendToStreamlit({ save_requested: true });
      }

      if (event.code === "Delete" && selectedId) {
        event.preventDefault();
        setRectangles((prev) => prev.filter((rect) => rect.id !== selectedId));
        setSelectedId(null);
        setIsLabelEditMode(false);
      }

      if (event.code === "Escape") {
        event.preventDefault();
        if (isLabelEditMode || selectedId) {
          setIsLabelEditMode(false);
          setSelectedId(null);
        }
      }
      
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => {
      window.removeEventListener("keydown", handleKeyPress);
    };
  }, []);

  useEffect(() => {
    const debouncedSetScale = debounce((newScale: number) => {
      setScale(newScale);
    }, 50);

    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey && canvasWrapperRef.current?.contains(event.target as Node)) {
        event.preventDefault();
        let newScale = scaleRef.current + (event.deltaY < 0 ? 0.1 : -0.1);
        newScale = Math.min(Math.max(newScale, 0.5), 3.0);
        debouncedSetScale(newScale);
      }
    };

    window.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      window.removeEventListener('wheel', handleWheel);
    };
  }, []);

  const formatScale = (scale: number) => `${Math.round(scale * 100)}%`;

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    sendToStreamlit({ mode: newMode });
  };

  const handleSuggestionSelect = (suggestedLabel: string) => {
    setLabel(suggestedLabel);
    if (selectedId !== null) {
      setRectangles((prev) =>
        prev.map((rect) =>
          rect.id === selectedId ? { ...rect, label: suggestedLabel, stroke: "#39FF14" } : rect
        )
      );
    }
    setShowSuggestions(false);
  };

  return (
    <ChakraProvider theme={theme}>
      <VStack spacing={4} align="stretch">
        {saveNotification && (
          <Box p={3} bg="green.100" color="green.800" borderRadius="md" position="fixed" top="20px" left="50%" transform="translateX(-50%)" zIndex={100} boxShadow="md">
            <Text fontWeight="bold">💾 어노테이션 저장 요청이 전송되었습니다!</Text>
          </Box>
        )}

        <Box p={3} bg="gray.200" borderRadius="md" position="sticky" top={0} zIndex={10} borderWidth="1px" boxShadow="sm">
          <Flex justifyContent="space-between" alignItems="center">
            <HStack spacing={4}>
              <Box>
                <Text fontSize="sm" mb={1} color="black">Class</Text>
                <Input
                  value={label}
                  onChange={handleLabelInputChange}
                  onBlur={commitLabelChange}
                  onKeyDown={(e) => { if (e.key === 'Enter') commitLabelChange(); }}
                  placeholder="Enter label"
                  size="sm"
                  width="200px"
                  bg="white"
                  borderColor="gray.200"
                />
              </Box>
            </HStack>

            <HStack>
              <Text fontSize="sm" mr={2} color="black">Zoom: {formatScale(scale)}</Text>
              <Button size="sm" colorScheme="teal" variant={showLabels ? "solid" : "outline"} onClick={() => setShowLabels(prev => !prev)}>
                {showLabels ? "Hide Labels" : "Show Labels"}
              </Button>
              <Button size="sm" colorScheme="green" variant={mode === "Draw" ? "solid" : "outline"} onClick={() => handleModeChange("Draw")}>Draw</Button>
              <Button size="sm" colorScheme="blue" variant={mode === "Edit" ? "solid" : "outline"} onClick={() => handleModeChange("Edit")}>Edit</Button>
              <Button size="sm" colorScheme="purple" onClick={() => {
                setSaveNotification(true);
                setTimeout(() => setSaveNotification(false), 3000);
                sendToStreamlit({ save_requested: true });
              }}>
                Save
              </Button>
            </HStack>
          </Flex>

          <Flex mt={2} justifyContent="space-between" alignItems="center">
            <Text fontSize="xs" color="black">Selected Items: {rectangles.length}</Text>
          </Flex>
        </Box>

        <Box ref={canvasWrapperRef}>
          <Center>
            <BBoxCanvas
              rectangles={rectangles}
              mode={mode}
              selectedId={selectedId}
              scale={scale}
              setSelectedId={setSelectedId}
              setRectangles={setRectangles}
              setLabel={setLabel}
              color_map={color_map}
              label={label}
              image={image}
              image_size={image_size}
              strokeWidth={line_width}
              isLabelEditMode={isLabelEditMode}
              setIsLabelEditMode={setIsLabelEditMode}
              handleLabelInputChange={handleLabelInputChange}
              showLabels={showLabels}
              suggestedLabels={suggestedLabels}
              showSuggestions={showSuggestions}
              setShowSuggestions={setShowSuggestions}
              handleSuggestionSelect={handleSuggestionSelect}
              isLoadingLabels={isLoadingLabels}
            />
          </Center>
        </Box>
      </VStack>
    </ChakraProvider>
  );
};

export default withStreamlitConnection(Detection);
