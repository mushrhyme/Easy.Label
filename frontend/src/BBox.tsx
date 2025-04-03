import React, { useEffect, useRef } from "react";
import { Rect, Transformer } from "react-konva";
import Konva from "konva";

export interface RectProps {
  x: number;
  y: number;
  width: number;
  height: number;
  id: string;
  stroke: string;
  label: string;
}

export interface BBoxProps {
  rectProps: RectProps;
  onChange: (newRect: RectProps) => void;
  isSelected: boolean;
  onClick: () => void;
  scale: number;
  strokeWidth: number;
  mode?: string;
}

const BBox: React.FC<BBoxProps> = ({
  rectProps,
  onChange,
  isSelected,
  onClick,
  scale,
  strokeWidth,
  mode = "Edit",
}) => {
  // Ref 타입을 Konva.Rect와 Konva.Transformer로 명확히 지정
  const shapeRef = useRef<Konva.Rect | null>(null);
  const trRef = useRef<Konva.Transformer | null>(null);

  useEffect(() => {
    if (isSelected && trRef.current && shapeRef.current) {
      // Transformer 설정
      trRef.current.nodes([shapeRef.current]);
      
      // 변형 활성화 설정
      trRef.current.visible(true);
      
      // 더 정밀한 변형 제어를 위한 설정
      trRef.current.enabledAnchors([
        'top-left', 'top-center', 'top-right', 
        'middle-left', 'middle-right', 
        'bottom-left', 'bottom-center', 'bottom-right'
      ]);

      // 비율 유지 해제 (자유로운 리사이징)
      trRef.current.keepRatio(false);

      // 회전 비활성화 (필요시 활성화 가능)
      trRef.current.rotateEnabled(false);

      // 패딩 조정으로 앵커 포인트 접근성 향상
      trRef.current.padding(2);

      // 앵커 크기 키우기
      trRef.current.anchorSize(10);

      // 앵커 스트로크 두께 키우기
      trRef.current.anchorStrokeWidth(2);

      // 앵커 색상 설정
      trRef.current.anchorFill('#FFFFFF');
      trRef.current.anchorStroke(rectProps.stroke || '#0000FF');
      
      // 앵커 코너 라운딩 추가
      trRef.current.anchorCornerRadius(4);

      // 레이어 업데이트 (중요: 변경사항을 화면에 반영)
      trRef.current.getLayer()?.batchDraw();
    }
  }, [isSelected, rectProps.stroke]);

  // Edit 모드일 때만 드래그 가능하도록 설정
  const isDraggable = mode === "Edit";

  return (
    <>
      <Rect
        ref={shapeRef}
        x={rectProps.x * scale}
        y={rectProps.y * scale}
        width={rectProps.width * scale}
        height={rectProps.height * scale}
        stroke={rectProps.stroke}
        strokeWidth={strokeWidth}
        dash={[5, 5]} // 점선 스타일 추가
        fill={isSelected ? rectProps.stroke + "20" : "transparent"} // 선택 시 약간의 배경 투명도 추가
        draggable={isDraggable} // 드래그 가능 여부 설정
        onClick={onClick} // 클릭 이벤트 추가
        onTap={onClick} // 모바일 터치 이벤트 추가
        // 드래그 종료 시 위치 업데이트
        onDragEnd={(e) => { 
          if (!shapeRef.current) return;
          const node = shapeRef.current;
          onChange({ 
            ...rectProps,
            x: node.x() / scale,
            y: node.y() / scale,
          });
        }}
        // 스케일 변환 후 위치 및 크기 업데이트
        onTransformEnd={(e) => {
          if (!shapeRef.current) return;
          const node = shapeRef.current;
          const scaleX = node.scaleX();
          const scaleY = node.scaleY();

          // 스케일 초기화
          node.scaleX(1);
          node.scaleY(1);

          // 변경된 위치 및 크기 적용
          onChange({
            ...rectProps,
            x: node.x() / scale,
            y: node.y() / scale,
            width: Math.max(5, node.width() * scaleX) / scale, // 최소 크기 제한 추가
            height: Math.max(5, node.height() * scaleY) / scale, // 최소 크기 제한 추가
          });
        }}
      />
      {isSelected && mode === "Edit" && (
        <Transformer 
          ref={trRef}
          anchorStroke={rectProps.stroke || '#0000FF'}
          anchorFill="#FFFFFF"
          anchorSize={10}
          anchorCornerRadius={4}
          borderStroke={rectProps.stroke || '#0000FF'}
          borderDash={[3, 3]}
          borderStrokeWidth={1}
          boundBoxFunc={(oldBox, newBox) => {
            // 최소 크기 제한 (5x5 픽셀)
            if (newBox.width < 5 || newBox.height < 5) {
              return oldBox;
            }
            return newBox;
          }}
        />
      )}
    </>
  );
};

export default BBox;