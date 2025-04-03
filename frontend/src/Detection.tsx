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

// 테마 설정 - 강제 라이트 모드
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

  const [rectangles, setRectangles] = React.useState<Rectangle[]>(
    bbox_info.map((bb, i) => ({
      x: bb.bbox[0],
      y: bb.bbox[1],
      width: bb.bbox[2],
      height: bb.bbox[3],
      label: bb.label,
      stroke: "#39FF14",  // color_map[bb.label],
      id: 'bbox-' + i
    }))
  );
  
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [label, setLabel] = useState(""); 
  const [mode, setMode] = React.useState<string>('Draw');
  const [isLabelEditMode, setIsLabelEditMode] = useState(false);
  const [scale, setScale] = useState(1.0);
  const [saveNotification, setSaveNotification] = useState<boolean>(false);
  const [showLabels, setShowLabels] = useState(false);
  const [suggestedLabels, setSuggestedLabels] = useState<string[]>([]);
  const [isLoadingLabels, setIsLoadingLabels] = useState<boolean>(false);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);


  useEffect(() => {
    if (ocr_suggestions && ocr_suggestions.length > 0) {
      console.log("Received OCR suggestions from props:", ocr_suggestions);
      setSuggestedLabels(ocr_suggestions);
      setIsLoadingLabels(false);
      setShowSuggestions(true);
    }
  }, [ocr_suggestions]);
  
  // Streamlit 컴포넌트 통신 개선
  const sendStateToStreamlit = (currentMode: string, boxesData: Rectangle[], currentScale: number, selectedBoxId: string | null = null) => {
    try {
      // 필요한 데이터만 전송하도록 최적화
      const currentBboxValue = boxesData.map((rect) => ({
        bbox: [rect.x, rect.y, rect.width, rect.height],
        label: rect.label || "", // 빈 라벨 안전하게 처리
      }));
      
      // OCR 요청 시에만 full data 전송, 아닐 때는 최소 데이터만
      if (selectedBoxId !== null) {
        console.log("DEBUG: OCR 요청 전송", selectedBoxId);
        
        // 선택된 박스가 존재하는지 확인
        const selectedBox = boxesData.find(box => box.id === selectedBoxId);
        if (!selectedBox) {
          console.error("선택된 박스를 찾을 수 없음");
          return;
        }
        
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
        // 일반 상태 업데이트에서는 OCR 관련 플래그 제외
        Streamlit.setComponentValue({
          mode: currentMode,
          bboxes: currentBboxValue,
          scale: currentScale,
          save_requested: false
        });
      }
    } catch (error) {
      console.error("상태 전송 중 오류 발생:", error);
    }
  };
  
const pendingOCRRequestRef = useRef(false);

// const sendOCRRequest = (selectedId: string, mode: string, rectangles: Rectangle[], scale: number) => {
//   if (pendingOCRRequestRef.current) {
//     console.log("이미 처리 중인 OCR 요청이 있습니다");
//     return;
//   }
  
//   pendingOCRRequestRef.current = true;
  
//   // 선택된 ID에 해당하는 인덱스 찾기
//   const selectedIndex = rectangles.findIndex(rect => rect.id === selectedId);
  
//   // 인덱스를 찾았을 때만 요청 전송
//   if (selectedIndex !== -1) {
//     // OCR 요청 보내기
//     Streamlit.setComponentValue({
//       mode: mode,
//       bboxes: rectangles.map((rect) => ({
//         bbox: [rect.x, rect.y, rect.width, rect.height],
//         label: rect.label,
//       })),
//       scale: scale,
//       request_ocr: true,
//       selected_box_index: selectedIndex  // ID 대신 인덱스 전송
//     });
//   } else {
//     console.error("선택된 ID에 해당하는 바운딩 박스를 찾을 수 없습니다:", selectedId);
//   }

//   // 요청 플래그 초기화 (일정 시간 후)
//   setTimeout(() => {
//     pendingOCRRequestRef.current = false;
//   }, 1000);
// };

// 메시지 이벤트 리스너 수정


const sendOCRRequest = debounce((selectedId: string) => {
  const selectedBox = rectangles.find(rect => rect.id === selectedId);
  if (!selectedBox) return;

  Streamlit.setComponentValue({
    mode,
    bboxes: rectangles.map(rect => ({
      bbox: [rect.x, rect.y, rect.width, rect.height],
      label: rect.label
    })),
    scale,
    request_ocr: true,
    selected_box_id: selectedId,
    selected_box_coords: [selectedBox.x, selectedBox.y, selectedBox.width, selectedBox.height]
  });
}, 500); // debounce로 rerun 방지


useEffect(() => {
  const onDataFromPython = (event: MessageEvent) => {
    if (event.data.type === 'streamlit:render') {
      console.log("전체 데이터:", event.data.args);
      console.log("컴포넌트 데이터:", event.data.args.data);
      try {
        const data = event.data.args.data;
        
        // OCR 추천 결과 처리 개선
        if (data && data.ocr_suggestions && Array.isArray(data.ocr_suggestions)) {
          console.log("DEBUG: OCR 추천 목록 받음:", data.ocr_suggestions);
          
          // 상태 업데이트를 일괄적으로 처리
          setSuggestedLabels(data.ocr_suggestions);
          setIsLoadingLabels(false);
          setShowSuggestions(true);
          
          // 디버깅: 실제로 UI에 표시되는지 확인
          setTimeout(() => {
            console.log("DEBUG: UI 상태 최종 확인", {
              suggestedLabels: data.ocr_suggestions,
              showSuggestions: true
            });
          }, 100);
        }
      } catch (error) {
        console.error("오류 발생:", error);
      }
    }
  };
  
  window.addEventListener('message', onDataFromPython);
  return () => window.removeEventListener('message', onDataFromPython);
}, [setSuggestedLabels, setIsLoadingLabels, setShowSuggestions]); // 상태 업데이트 함수들을 의존성 배열에 추가

  // 현재 선택된 박스의 라벨로 입력란 업데이트
  useEffect(() => {
    if (selectedId) {
      const selectedRect = rectangles.find(rect => rect.id === selectedId);
      if (selectedRect) {
        setLabel(selectedRect.label);
      }
    }
  }, [selectedId, rectangles]);

  // 모드가 변경될 때마다 Streamlit으로 전송
  useEffect(() => {
    sendStateToStreamlit(mode, rectangles, scale);
  }, [mode, rectangles]);
  
  // 모드 변경이 제대로 되는지 확인
  useEffect(() => {
    console.log("현재 모드:", mode);
  }, [mode]);

  // 사용자 입력을 반영하는 함수
  const handleLabelInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newLabel = event.target.value;
    setLabel(newLabel);
    if (selectedId !== null) {
      setRectangles((prev) =>
        prev.map((rect) =>
          rect.id === selectedId ? { ...rect, label: newLabel, stroke: "#39FF14" } : rect
      // color_map[newLabel] || "#FF0000" } : rect
        )
      );
    }
  };

  
  // 캔버스 크기 조정
  useEffect(() => {
    // 초기 스케일 설정 및 프레임 높이 조정을 하나의 useEffect로 통합
    const initializeScale = () => {
      // 최초 로드 시 초기 스케일 계산
      if (scale === 1.0 && image_size[0] > 0) {
        const scale_ratio = window.innerWidth * 0.8 / image_size[0];
        setScale(Math.min(scale_ratio, 1.0));
      }
    };
    
    const updateFrameHeight = () => {
      // 현재 이미지 크기와 스케일 기반으로 프레임 높이 조정
      if (image_size[1] > 0) {
        Streamlit.setFrameHeight(image_size[1] * scale + 100);
      }
    };
    
    // 초기화 및 첫 번째 프레임 높이 설정
    initializeScale();
    updateFrameHeight();
    
    // 윈도우 리사이즈 이벤트 리스너
    window.addEventListener('resize', updateFrameHeight);
    return () => {
      window.removeEventListener('resize', updateFrameHeight);
    };
  }, [image_size, scale]); // 이미지 크기와 스케일 의존성 추가


  // 키보드 단축키 처리
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      console.log("keydown 이벤트 감지됨:", event.code, "Ctrl:", event.ctrlKey, "Shift:", event.shiftKey);
      
      if (use_space && event.code === "Space") {
        sendStateToStreamlit(mode, rectangles, scale);  
      }
  
      if (event.ctrlKey && event.code === "KeyE") {
        event.preventDefault();
        console.log("변경: Edit 모드로 전환");
        setMode("Edit");
      }
  
      if (event.ctrlKey && event.code === "KeyD") {
        event.preventDefault();
        console.log("변경: Draw 모드로 전환");
        setMode("Draw");
      }

      // // 라벨 입력 모드 토글 (Ctrl + L)
      // if (event.ctrlKey && event.code === "KeyL") {
      //   event.preventDefault();
      //   console.log("Ctrl+L 감지, 선택된 ID:", selectedId);
        
      //   if (selectedId) {
      //     // 상태 변경을 일괄 처리하고 함수형 업데이트 사용
      //     setIsLabelEditMode(true);
      //     setShowSuggestions(true);
          
      //     // OCR 요청을 다음 렌더링 사이클로 지연
      //     // 렌더링 사이클이 완료된 후 실행되도록 함
      //     requestAnimationFrame(() => {
      //       setIsLoadingLabels(true);
      //       sendOCRRequest(selectedId, mode, rectangles, scale);
      //     });
      //   }
      // }

      if (event.ctrlKey && event.code === "KeyL") {
        event.preventDefault();
        if (selectedId) {
          setIsLabelEditMode(true);
          setShowSuggestions(true);
          setIsLoadingLabels(true);
      
          // ❗️OCR 요청을 살짝 지연시켜 debounce + 안정성 확보
          requestAnimationFrame(() => {
            sendOCRRequest(selectedId); // debounce 적용된 함수
          });
        }
      }
      

      // 라벨 표시 토글 (Ctrl + T)
      if (event.ctrlKey && event.code === "KeyT") {
        event.preventDefault();
        console.log("변경: 라벨 표시 토글");
        setShowLabels(prev => !prev);
      }

      // Ctrl+S 단축키 감지 추가
      if (event.ctrlKey && event.code === "KeyS") {
        event.preventDefault();
        console.log("Ctrl+S 감지: 어노테이션 저장");
        
        // 안내 표시 활성화
        setSaveNotification(true);
        
        // 3초 후에 안내 메시지 숨기기
        setTimeout(() => {
          setSaveNotification(false);
        }, 3000);
        
        // Streamlit으로 저장 명령 전송
        Streamlit.setComponentValue({
          mode: mode,
          id: rect.id,
          bboxes: rectangles.map((rect) => ({
            bbox: [rect.x, rect.y, rect.width, rect.height],
            label: rect.label,
          })),
          scale: scale,
          save_requested: true  // 저장 요청 플래그 추가
        });
      }
      // 삭제 기능
      if (event.code === "Delete" && selectedId) {
        event.preventDefault();
        console.log("삭제: 선택된 바운딩 박스 삭제", selectedId);
        setRectangles((prev) => prev.filter((rect) => rect.id !== selectedId));
        setSelectedId(null);
        setIsLabelEditMode(false);
      }
      
      // ESC 키로 라벨 입력 모드 취소 및 선택 해제
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

  // 마우스 휠 확대/축소
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

  // 스케일 포맷팅
  const formatScale = (scale: number) => {
    return `${Math.round(scale * 100)}%`;
  };

  // 라이트 모드로 고정된 색상 설정
  const borderColor = 'gray.200';
  const textColor = 'black';
  const controlBgColor = 'gray.200';
  const inputbgColor = 'white';

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    // scale을 유지하면서 상태 업데이트
    sendStateToStreamlit(newMode, rectangles, scale);
  };

  // 라벨 추천 선택 핸들러 함수 추가
  const handleSuggestionSelect = (suggestedLabel: string) => {
    setLabel(suggestedLabel);
    if (selectedId !== null) {
      setRectangles((prev) =>
        prev.map((rect) =>
          rect.id === selectedId ? { ...rect, label: suggestedLabel, stroke: "#39FF14" } : rect
        )
      );
    }
    setShowSuggestions(false); // 선택 후 추천 UI 닫기
  };

  
  return (
    <ChakraProvider theme={theme}>
      <VStack spacing={4} align="stretch">
        {/* 저장 알림 메시지 */}
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
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <Text fontWeight="bold">
              <span role="img" aria-label="save">💾</span> 어노테이션 저장 요청이 전송되었습니다!
            </Text>
          </Box>
        )}
        
        {/* 상단 컨트롤 영역 */}
        <Box 
          p={3} 
          bg={controlBgColor} 
          borderRadius="md" 
          position="sticky" 
          top={0} 
          zIndex={10}
          borderColor={borderColor}
          borderWidth="1px"
          boxShadow="sm"
        >
          <Flex justifyContent="space-between" alignItems="center">
            <HStack spacing={4}>
              {/* 라벨 입력 */}
              <Box>
                <Text fontSize="sm" mb={1} color={textColor}>Class</Text>
                <Input 
                  value={label} 
                  onChange={handleLabelInputChange} 
                  placeholder="Enter label"
                  size="sm"
                  width="200px"
                  bg={inputbgColor}
                  borderColor={borderColor}
                />
              </Box>
            </HStack>
            
            <HStack>
              <Text fontSize="sm" mr={2} color={textColor}>Zoom: {formatScale(scale)}</Text>
              <Button 
                size="sm" 
                colorScheme="teal"
                variant={showLabels ? "solid" : "outline"}
                opacity={showLabels ? 1 : 0.7}
                onClick={() => setShowLabels(prev => !prev)}
              >
                {showLabels ? "Hide Labels" : "Show Labels"}
              </Button>

              <Button 
                size="sm" 
                colorScheme="green"
                variant={mode === "Draw" ? "solid" : "outline"}
                opacity={mode === "Draw" ? 1 : 0.7}
                // onClick={() => setMode("Draw")}
                onClick={() => handleModeChange("Draw")} // 직접 setMode 대신 핸들러 사용
              >
                Draw
              </Button>
              <Button 
                size="sm" 
                colorScheme="blue"
                variant={mode === "Edit" ? "solid" : "outline"}
                opacity={mode === "Edit" ? 1 : 0.7}
                onClick={() => setMode("Edit")}
              >
                Edit
              </Button>
              <Button 
                size="sm" 
                colorScheme="purple"
                onClick={() => {
                  // 저장 요청 플래그를 포함하여 Streamlit으로 데이터 전송
                  setSaveNotification(true);
                  setTimeout(() => setSaveNotification(false), 3000);
                  
                  Streamlit.setComponentValue({
                    mode: mode,
                    bboxes: rectangles.map((rect) => ({
                      bbox: [rect.x, rect.y, rect.width, rect.height],
                      label: rect.label,
                    })),
                    scale: scale,
                    save_requested: true
                  });
                }}
              >
                Save
              </Button>
            </HStack>
          </Flex>
          
          <Flex mt={2} justifyContent="space-between" alignItems="center">
            <Text fontSize="xs" color={textColor}>Selected Items: {rectangles.length}</Text>
          </Flex>
        </Box>
        
        {/* 이미지 영역 */}
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
            suggestedLabels={suggestedLabels} // 여기가 제대로 전달되는지 확인
            showSuggestions={showSuggestions} // 여기가 true로 설정되는지 확인
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