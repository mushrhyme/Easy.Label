import React, { useState, useEffect } from "react";
import { Layer, Rect, Stage, Image, Group, Text, Label, Tag } from 'react-konva';
import Konva from 'konva';
import BBox, { RectProps } from './BBox';
import { Input, Box } from '@chakra-ui/react';

interface Rectangle extends RectProps {
  // RectProps already contains x, y, width, height, id, stroke, label
}

interface BBoxCanvasLayerProps {
  rectangles: Rectangle[];
  setRectangles: React.Dispatch<React.SetStateAction<Rectangle[]>>;
  mode: string;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  setLabel: (label: string) => void;
  color_map: { [key: string]: string };
  scale: number;
  label: string;
  image_size: number[];
  image: HTMLImageElement | undefined;
  strokeWidth: number;
  isLabelEditMode?: boolean; 
  setIsLabelEditMode?: React.Dispatch<React.SetStateAction<boolean>>;
  handleLabelInputChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  showLabels?: boolean;
  // 새로 추가된 props
  suggestedLabels?: string[];
  showSuggestions?: boolean;
  setShowSuggestions?: React.Dispatch<React.SetStateAction<boolean>>;
  handleSuggestionSelect?: (label: string) => void;
  isLoadingLabels?: boolean; // 로딩 상태 추가
}

const BBoxCanvas = (props: BBoxCanvasLayerProps) => {
  const {
    rectangles,
    mode,
    selectedId,
    setSelectedId,
    setRectangles,
    setLabel,
    color_map,
    scale,
    label,
    image_size,
    image,
    strokeWidth,
    isLabelEditMode = false,
    setIsLabelEditMode = () => {},
    handleLabelInputChange = () => {},
    showLabels = false,
    suggestedLabels = [],
    showSuggestions = false,
    setShowSuggestions = () => {},
    handleSuggestionSelect = () => {},
    isLoadingLabels = false, // 로딩 상태 prop 추출
  } = props;

  const [adding, setAdding] = useState<number[] | null>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number, y: number } | null>(null);
  
  // 라벨 입력 위치 상태 추가
  const [labelPosition, setLabelPosition] = useState({ x: 0, y: 0 });
  // 라벨 입력 상자의 참조
  const inputRef = React.useRef<HTMLInputElement>(null);

  // 라벨 입력 필드 포커스 처리 개선
  useEffect(() => {
    if (isLabelEditMode && inputRef.current) {
      setTimeout(() => {
        inputRef.current?.focus();
        // 라벨 모드가 활성화되면 추천 목록도 표시
        setShowSuggestions(true);
      }, 100);
    }
  }, [isLabelEditMode]);

  // 선택된 바운딩 박스가 변경되면 라벨 입력 위치 업데이트
  useEffect(() => {
    if (selectedId) {
      const selectedRect = rectangles.find(rect => rect.id === selectedId);
      if (selectedRect) {
        setLabelPosition({
          x: (selectedRect.x + selectedRect.width / 2) * scale + position.x,
          y: (selectedRect.y - 30) * scale + position.y // 박스 상단에 위치
        });
      }
    }
  }, [selectedId, rectangles, scale, position]);

  const checkDeselect = (e: any) => {
    // 먼저 대상이 Rect인지 확인
    const isClickOnRect = e.target instanceof Konva.Rect;
    
    // 커서 위치 가져오기
    const stage = e.target.getStage();
    if (!stage) return;
    
    const pointer = stage.getPointerPosition();
    if (!pointer) return;

    // Edit 모드에서 Rect가 선택되지 않았을 때 캔버스 드래깅 시작
    if (mode === 'Edit' && !isClickOnRect) {
      setIsDragging(true);
      setDragStart({ x: pointer.x, y: pointer.y });
    }
    // Draw 모드에서 바운딩 박스 그리기 시작
    else if (mode === 'Draw' && !isClickOnRect) {
      if (selectedId === null) {
        setAdding([
          (pointer.x - position.x) / scale, 
          (pointer.y - position.y) / scale, 
          (pointer.x - position.x) / scale, 
          (pointer.y - position.y) / scale
        ]);
        // 새 박스 그리기 시작할 때 라벨 초기화
        setLabel("");
      } else {
        setSelectedId(null);
        setIsLabelEditMode(false);
      }
    }
    // Rect를 클릭하지 않았고 다른 모드일 경우 선택 해제
    else if (!isClickOnRect) {
      setSelectedId(null);
      setIsLabelEditMode(false);
    }
  };
  
  useEffect(() => {
    // Delete 키 입력 시 선택된 바운딩 박스 삭제
    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' && selectedId !== null) {
        setRectangles((prev) => prev.filter(rect => rect.id !== selectedId));
        setSelectedId(null);
        setIsLabelEditMode(false);
      }
    };
    
    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, [selectedId, setRectangles, setSelectedId, setIsLabelEditMode]);

  // 라벨 입력 필드 핸들러
  const handleLabelInputBlur = () => {
    setIsLabelEditMode(false);
  };

  // 라벨 입력 필드 키 다운 핸들러
  const handleLabelInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setIsLabelEditMode(false);
    } else if (e.key === 'Escape') {
      setIsLabelEditMode(false);
    }
  };
  useEffect(() => {
    console.log("BBoxCanvas: suggestedLabels 변경됨", suggestedLabels);
    // showSuggestions가 true이고 라벨이 있는 경우에만 추천 UI 표시
    console.log("showSuggestions:", showSuggestions);
    console.log("suggestedLabels:", suggestedLabels);
    if (showSuggestions && suggestedLabels.length > 0) {
      console.log("추천 UI 표시됨");
    }
  }, [suggestedLabels, showSuggestions]);
  // 스테이지 컨테이너 참조
  const stageContainerRef = React.useRef<HTMLDivElement>(null);

  return (
    <div 
      ref={stageContainerRef} 
      style={{ 
        position: 'relative',
        width: `${image_size[0] * scale}px`,
        height: `${image_size[1] * scale}px`,
        overflow: 'hidden', // 중요: 영역을 넘어가는 부분은 숨김
        border: '2px solid #3182CE', // 파란색 테두리 추가
        borderRadius: '4px',         // 테두리 모서리 둥글게
        boxShadow: '0 0 10px rgba(0,0,0,0.1)', // 약간의 그림자 효과
        background: 'repeating-conic-gradient(#f0f0f0 0% 25%, #e0e0e0 0% 50%) 50% / 20px 20px' // 체커보드 패턴 배경
      }}
    >
      <Stage
        width={image_size[0] * scale}
        height={image_size[1] * scale}
        // 마우스 클릭 시 이벤트
        onMouseDown={checkDeselect}
        // 마우스 이동 시 이벤트
        onMouseMove={(e) => {
          const stage = e.target.getStage();
          if (!stage) return;
          
          const pointer = stage.getPointerPosition();
          if (!pointer) return;
          
          // 박스 그리기 중인 경우
          if (adding !== null && mode === 'Draw') {
            setAdding([
              adding[0], 
              adding[1], 
              (pointer.x - position.x) / scale, 
              (pointer.y - position.y) / scale
            ]);
          } 
          // 캔버스 드래깅 중인 경우
          else if (isDragging && mode === 'Edit') {
            // 드래그 시작점과 현재 포인터 위치의 차이만큼 캔버스 이동
            setPosition({
              x: position.x + (pointer.x - dragStart!.x),
              y: position.y + (pointer.y - dragStart!.y)
            });
            setDragStart({ x: pointer.x, y: pointer.y });
          }
        }}
        // 마우스 클릭 해제 시 이벤트
        onMouseUp={() => {
          // Draw 모드에서 바운딩 박스 그리기 완료
          if (adding !== null && mode === 'Draw') {
            // 최소 크기 이상인 경우에만 박스 생성 (작은 실수 클릭 방지)
            if (Math.abs(adding[2] - adding[0]) > 5 && Math.abs(adding[3] - adding[1]) > 5) {
              const newId = `bbox-${rectangles.length}`; // 순차적 ID 생성
              setLabel("");  // 라벨 상태 초기화
              setRectangles((prev) => [
                ...prev,
                {
                  x: Math.min(adding[0], adding[2]),
                  y: Math.min(adding[1], adding[3]),
                  width: Math.abs(adding[2] - adding[0]),
                  height: Math.abs(adding[3] - adding[1]),
                  label: label,
                  stroke: color_map[label] || "#39FF14",
                  id: newId
                }
              ]);
              setSelectedId(newId);
              // 박스 생성 후 자동으로 라벨 입력 모드 활성화
              setIsLabelEditMode(true);
            }
          }
          
          // 항상 상태 초기화
          setAdding(null);
          setIsDragging(false);
          setDragStart(null);
        }}
      >
        {/* Layer 추가: 이미지 영역 표시를 위한 배경 레이어 */}
        <Layer x={position.x} y={position.y}>
          <Rect 
            x={0}
            y={0}
            width={image_size[0] * scale}
            height={image_size[1] * scale}
            fill="#FFFFFF"
            stroke="#DDDDDD"
            strokeWidth={1}
          />
        </Layer>
        {/* 기존 이미지 레이어 */}
        <Layer x={position.x} y={position.y}>
          <Image image={image || undefined} scaleX={scale} scaleY={scale} />
        </Layer>
        <Layer x={position.x} y={position.y}>
          {rectangles.map((rect) => (
            <Group key={rect.id}>
              <BBox
                rectProps={rect}
                scale={scale}
                strokeWidth={strokeWidth}
                isSelected={rect.id === selectedId}
                onClick={() => {
                  setSelectedId(rect.id);
                  setLabel(rect.label);
                }}
                mode={mode}
                onChange={(newAttrs) => {
                  setRectangles((prev) => prev.map((r) => (r.id === newAttrs.id ? newAttrs : r)));
                }}
              />
              {showLabels && (
                <Label
                  x={rect.x * scale}
                  y={rect.y * scale - 20}
                  opacity={0.8}
                >
                  <Tag
                    fill="#2F4F4F"
                    cornerRadius={3}
                    pointerDirection="down"
                    pointerWidth={10}
                    pointerHeight={10}
                    lineJoin="round"
                  />
                  <Text
                    text={rect.label || "unlabeled"}
                    padding={3}
                    fontFamily="Arial"
                    fontSize={25}
                    fill="white"
                  />
                </Label>
              )}
            </Group>
          ))}
          {adding && (
            <Rect
              fill="#39FF144D"
              x={Math.min(adding[0], adding[2]) * scale}
              y={Math.min(adding[1], adding[3]) * scale}
              width={Math.abs(adding[2] - adding[0]) * scale}
              height={Math.abs(adding[3] - adding[1]) * scale}
              stroke="#39FF14"
              strokeWidth={1}
            />
          )}
        </Layer>
      </Stage>
      {isLabelEditMode && selectedId && stageContainerRef.current && (
        <div 
          style={{
            position: 'absolute',
            top: `${labelPosition.y}px`,
            left: `${labelPosition.x}px`,
            transform: 'translate(-50%, -100%)',
            zIndex: 1000,
            background: 'white',
            padding: '5px',
            borderRadius: '4px',
            boxShadow: '0 2px 5px rgba(0,0,0,0.2)'
          }}
        >
          <Input
            ref={inputRef}
            size="sm"
            value={label}
            placeholder="라벨 입력"
            onChange={handleLabelInputChange}
            onBlur={() => {
              // 포커스 잃을 때 바로 끄지 않고 약간의 딜레이 추가
              // 이렇게 하면 추천 항목 클릭이 가능해짐
              setTimeout(() => {
                if (!document.activeElement?.classList.contains('suggestion-item')) {
                  setIsLabelEditMode(false);
                  setShowSuggestions(false);
                }
              }, 200);
            }}
            onKeyDown={handleLabelInputKeyDown}
            width="200px"
          />
          
          {/* 라벨 추천 UI */}
          {showSuggestions && (
            <Box
              mt={1}
              p={2}
              bg="white"
              borderRadius="md"
              boxShadow="sm"
              border="1px solid"
              borderColor="gray.200"
              width="200px"
            >
              {isLoadingLabels ? (
                // 로딩 상태 표시
                <div style={{ 
                  padding: '10px', 
                  textAlign: 'center', 
                  color: 'gray' 
                }}>
                  텍스트 인식 중...
                </div>
              ) : suggestedLabels.length > 0 ? (
                // 추천 목록 표시
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '5px',
                  maxHeight: '150px',
                  overflowY: 'auto'
                }}>
                  {suggestedLabels.map((sugLabel, idx) => (
                    <div
                      key={idx}
                      className="suggestion-item"
                      style={{
                        padding: '5px 8px',
                        borderRadius: '3px',
                        cursor: 'pointer',
                        backgroundColor: sugLabel === label ? '#e2f1ff' : 'transparent',
                        fontWeight: sugLabel === label ? 'bold' : 'normal',
                      }}
                      onMouseDown={(e) => {
                        e.preventDefault(); // 입력 창 blur 방지
                        handleSuggestionSelect(sugLabel);
                      }}
                    >
                      {sugLabel}
                    </div>
                  ))}
                </div>
              ) : (
                // 추천 결과가 없을 때
                <div style={{ 
                  padding: '10px', 
                  textAlign: 'center', 
                  color: 'gray' 
                }}>
                  추천 텍스트가 없습니다
                </div>
              )}
            </Box>
          )}
        </div>
      )}
          </div>
        );
};

export default BBoxCanvas;