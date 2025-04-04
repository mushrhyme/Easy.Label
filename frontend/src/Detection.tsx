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
import debounce from 'lodash/debounce';

const theme = extendTheme({
  config: {
    initialColorMode: 'light',
    useSystemColorMode: false,
  },
});

export interface PythonArgs {
  image_url: string,
  image_size: number[],
  bbox_info: any[],
  color_map: any,
  line_width: number,
  use_space: boolean,
  ocr_suggestions: string[]
}

interface Rectangle {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  stroke: string;
  id: string;
}

// 공통 bbox 포맷터 함수
const formatBBoxes = (rects: Rectangle[]) =>
  rects.map((rect) => ({
    box_id: rect.id,
    bbox: [rect.x, rect.y, rect.width, rect.height],
    label: rect.label || "",
  }));

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
  const baseUrl = params.get('streamlitUrl')
  const [image] = useImage(baseUrl + image_url)

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
  const [suggestedLabels, setSuggestedLabels] = useState<string[]>([]);
  const [isLoadingLabels, setIsLoadingLabels] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const pendingOCRRequestRef = useRef(false);

  useEffect(() => {
    if (ocr_suggestions && ocr_suggestions.length > 0) {
      setSuggestedLabels(ocr_suggestions);
      setIsLoadingLabels(false);
      setShowSuggestions(true);
    }
  }, [ocr_suggestions]);

  const sendStateToStreamlit = (currentMode: string, boxesData: Rectangle[], currentScale: number, selectedBoxId: string | null = null) => {
    const currentBboxValue = formatBBoxes(boxesData);

    if (selectedBoxId !== null) {
      const selectedBox = boxesData.find(box => box.id === selectedBoxId);
      if (!selectedBox) return;

      Streamlit.setComponentValue({
        mode: currentMode,
        bboxes: currentBboxValue,
        scale: currentScale,
        save_requested: false,
        request_ocr: true,
        selected_box_id: selectedBoxId,
        selected_box_coords: [selectedBox.x, selectedBox.y, selectedBox.width, selectedBox.height]
      });
    } else {
      Streamlit.setComponentValue({
        mode: currentMode,
        bboxes: currentBboxValue,
        scale: currentScale,
        save_requested: false
      });
    }
  };

  const sendOCRRequest = debounce((selectedId: string) => {
    const selectedBox = rectangles.find(rect => rect.id === selectedId);
    if (!selectedBox) return;

    Streamlit.setComponentValue({
      mode,
      bboxes: formatBBoxes(rectangles),
      scale,
      request_ocr: true,
      selected_box_id: selectedId,
      selected_box_coords: [selectedBox.x, selectedBox.y, selectedBox.width, selectedBox.height]
    });
  }, 500);
  
  useEffect(() => {
    const onDataFromPython = (event: MessageEvent) => {
      if (event.data.type === 'streamlit:render') {
        try {
          const data = event.data.args.data;
          if (data && Array.isArray(data.ocr_suggestions)) {
            setSuggestedLabels(data.ocr_suggestions);
            setIsLoadingLabels(false);
            setShowSuggestions(true);
          }
        } catch (error) {
          console.error("오류 발생:", error);
        }
      }
    };
    window.addEventListener('message', onDataFromPython);
    return () => window.removeEventListener('message', onDataFromPython);
  }, []);

  useEffect(() => {
    if (selectedId) {
      const selectedRect = rectangles.find(rect => rect.id === selectedId);
      if (selectedRect) {
        setLabel(selectedRect.label);
      }
    }
  }, [selectedId, rectangles]);

  useEffect(() => {
    sendStateToStreamlit(mode, rectangles, scale);
  }, [mode, rectangles]);

  const handleLabelInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newLabel = event.target.value;
    setLabel(newLabel);
    if (selectedId !== null) {
      setRectangles((prev) =>
        prev.map((rect) =>
          rect.id === selectedId ? { ...rect, label: newLabel, stroke: "#39FF14" } : rect
        )
      );
    }
  };

  useEffect(() => {
    const initializeScale = () => {
      if (scale === 1.0 && image_size[0] > 0) {
        const scale_ratio = window.innerWidth * 0.8 / image_size[0];
        setScale(Math.min(scale_ratio, 1.0));
      }
    };
    const updateFrameHeight = () => {
      if (image_size[1] > 0) {
        Streamlit.setFrameHeight(image_size[1] * scale + 100);
      }
    };
    initializeScale();
    updateFrameHeight();
    window.addEventListener('resize', updateFrameHeight);
    return () => {
      window.removeEventListener('resize', updateFrameHeight);
    };
  }, [image_size, scale]);

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (use_space && event.code === "Space") {
        sendStateToStreamlit(mode, rectangles, scale);  
      }
      if (event.ctrlKey && event.code === "KeyE") {
        event.preventDefault();
        setMode("Edit");
      }
      if (event.ctrlKey && event.code === "KeyD") {
        event.preventDefault();
        setMode("Draw");
      }
      if (event.ctrlKey && event.code === "KeyL") {
        event.preventDefault();
        if (selectedId) {
          setIsLabelEditMode(true);
          setShowSuggestions(true);
          setIsLoadingLabels(true);
          requestAnimationFrame(() => {
            sendOCRRequest(selectedId);
          });
        }
      }
      if (event.ctrlKey && event.code === "KeyT") {
        event.preventDefault();
        setShowLabels(prev => !prev);
      }
      if (event.ctrlKey && event.code === "KeyS") {
        event.preventDefault();
        setSaveNotification(true);
        setTimeout(() => {
          setSaveNotification(false);
        }, 3000);
        Streamlit.setComponentValue({
          mode,
          bboxes: formatBBoxes(rectangles),
          scale,
          save_requested: true
        });
      }
      if (event.code === "Delete" && selectedId) {
        event.preventDefault();
        setRectangles((prev) => prev.filter((rect) => rect.id !== selectedId));
        setSelectedId(null);
        setIsLabelEditMode(false);
      }
      if (event.code === "Escape") {
        event.preventDefault();
        if (isLabelEditMode) {
          setIsLabelEditMode(false);
        } else if (selectedId) {
          setSelectedId(null);
        }
      }
    };
    window.addEventListener("keydown", handleKeyPress);
    return () => {
      window.removeEventListener("keydown", handleKeyPress);
    };
  }, [rectangles, use_space, selectedId, isLabelEditMode, mode]);

  useEffect(() => {
    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey) {
        event.preventDefault();
        let newScale = scale + (event.deltaY < 0 ? 0.1 : -0.1);
        newScale = Math.min(Math.max(newScale, 0.5), 3.0);
        setScale(newScale);
      }
    };
    window.addEventListener('wheel', handleWheel, { passive: false, capture: true });
  }, [scale]);

  const formatScale = (scale: number) => `${Math.round(scale * 100)}%`;

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    sendStateToStreamlit(newMode, rectangles, scale);
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
          <Box 
            p={3} 
            bg="green.100" 
            color="green.800" 
            borderRadius="md" 
            position="fixed" 
            top="20px" 
            left="50%" 
            transform="translateX(-50%)" 
            zIndex={100}
            boxShadow="md"
          >
            <Text fontWeight="bold">
              <span role="img" aria-label="save">💾</span> 어노테이션 저장 요청이 전송되었습니다!
            </Text>
          </Box>
        )}

        <Box 
          p={3} 
          bg="gray.200" 
          borderRadius="md" 
          position="sticky" 
          top={0} 
          zIndex={10}
          borderWidth="1px"
          boxShadow="sm"
        >
          <Flex justifyContent="space-between" alignItems="center">
            <HStack spacing={4}>
              <Box>
                <Text fontSize="sm" mb={1} color="black">Class</Text>
                <Input 
                  value={label} 
                  onChange={handleLabelInputChange} 
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
              <Button size="sm" colorScheme="green" variant={mode === "Draw" ? "solid" : "outline"} onClick={() => handleModeChange("Draw")}>
                Draw
              </Button>
              <Button size="sm" colorScheme="blue" variant={mode === "Edit" ? "solid" : "outline"} onClick={() => handleModeChange("Edit")}>
                Edit
              </Button>
              <Button size="sm" colorScheme="purple" onClick={() => {
                setSaveNotification(true);
                setTimeout(() => setSaveNotification(false), 3000);
                Streamlit.setComponentValue({
                  mode,
                  bboxes: formatBBoxes(rectangles),
                  scale,
                  save_requested: true
                });
              }}>
                Save
              </Button>
            </HStack>
          </Flex>

          <Flex mt={2} justifyContent="space-between" alignItems="center">
            <Text fontSize="xs" color="black">Selected Items: {rectangles.length}</Text>
          </Flex>
        </Box>

        <Box>
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
