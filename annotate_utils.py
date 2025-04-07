import os
import streamlit.components.v1 as components
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from hashlib import md5
import streamlit as st
try:
    from streamlit.elements.image import image_to_url
except:
    from streamlit.elements.lib.image_utils import image_to_url
import cv2
from paddleocr import PaddleOCR
import traceback
import io
import zipfile
from postgresql_utils import * 

# 컴포넌트 선언
IS_RELEASE = False
absolute_path = os.path.dirname(os.path.abspath(__file__))
build_path = os.path.join(absolute_path, "frontend/build")
_component_func = components.declare_component("st-detection", path=build_path)

def split_first_dir(path):
    """
    폴더 경로를 첫 번째 디렉토리와 나머지 경로로 분할합니다.
    
    Args:
        path (str): 분할할 경로
        
    Returns:
        tuple: (첫 번째 디렉토리, 나머지 경로)
    """
    # 경로 정규화 (불필요한 구분자 제거)
    norm_path = os.path.normpath(path)
    
    # 경로 구분자로 분할
    parts = norm_path.split(os.sep)
    
    # 빈 문자열 제거 (경로가 / 로 시작하는 경우)
    parts = [p for p in parts if p]
    
    if not parts:
        return "", ""
    
    first_dir = parts[0]
    
    if len(parts) > 1:
        rest_path = os.sep.join(parts[1:])
        return first_dir, rest_path
    else:
        return first_dir, ""
    
def get_colormap(label_names, colormap_name='gist_rainbow'):
    """라벨에 대한 컬러맵을 생성합니다."""
    colormap = {} 
    cmap = plt.get_cmap(colormap_name)
    for idx, l in enumerate(label_names):
        rgb = [int(d) for d in np.array(cmap(float(idx)/len(label_names)))*255][:3]
        colormap[l] = ('#%02x%02x%02x' % tuple(rgb))
    return colormap

def detection(
        client, 
        bucket_name, 
        object_name, 
        bboxes=None, 
        labels=None, 
        height=None, 
        width=None, 
        line_width=5.0, 
        use_space=False, 
        key=None,
    ):
    """객체 탐지 및 어노테이션 컴포넌트를 표시합니다."""
    temp_image_path = client.load_image(bucket_name, split_first_dir(object_name)[1])
    if not temp_image_path:
        st.error(f"이미지를 로드할 수 없습니다: {object_name}")
        return None

    image = Image.open(temp_image_path)
    original_image_size = image.size
    image_np = np.array(image)

    if height is None or width is None:
        width = 1200
        height = int(original_image_size[1] * (width / original_image_size[0]))

    image.thumbnail(size=(width, height))
    resized_image_size = image.size
    scale = original_image_size[0]/resized_image_size[0]

    image_url = image_to_url(
        image, image.size[0], True, "RGB", "PNG",
        f"detection-{md5(image.tobytes()).hexdigest()}-{key}"
    )
    if image_url.startswith('/'):
        image_url = image_url[1:]

    color_map = get_colormap(labels, colormap_name='gist_rainbow')

    # bbox_info 생성
    bbox_info = []
    for i, (bbox, label) in enumerate(zip(bboxes, labels)):
        scaled_bbox = [b/scale for b in bbox]
        bbox_info.append({
            'bbox': scaled_bbox,
            'label_id': i,
            'label': label
        })
    
    # 컴포넌트 호출을 위한 args 구성
    component_args = {
        "image_url": image_url,
        "image_size": image.size,
        "bbox_info": bbox_info,
        "color_map": color_map,
        "line_width": line_width,
        "use_space": use_space,
    }

    # 컴포넌트 호출
    component_value = _component_func(**component_args, key=key)

    print(f"DEBUG: component_value={component_value}")

    # 반환값 없으면 아직 렌더 중
    if component_value is None:
        return None
    
    return {
        "mode": component_value.get("mode", "Draw"),
        "bboxes": component_value.get("bboxes", []),
        "save_requested": component_value.get("save_requested", False),
    }


def detect_text_regions(image_path, ocr):
    """
    이미지에서 텍스트 영역(BBox)만 검출하는 함수
    """
    img_np = cv2.imread(image_path)
    if img_np is None:
        img = Image.open(image_path)
        img_np = np.array(img)
    else:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
    
    # Detection 수행
    boxes_result = ocr.text_detector(img_np)
    boxes = boxes_result[0] if boxes_result else []
    
    return img_np, boxes  # 원본 이미지, 검출된 BBox 반환


def auto_detect_text_regions(bucket_name, object_name, bboxes, labels):
    """
    MinIO에서 이미지를 가져와 텍스트 영역을 자동으로 감지하는 함수
    """    
    # 임시 파일 다운로드
    temp_image_path = None
    try:
        # MinIO에서 임시 파일로 이미지 다운로드
        temp_image_path = st.session_state.st.session_state.minio_client.load_image(
            bucket_name,
            object_name
        )
        
        if temp_image_path:
            # 텍스트 영역 감지
            if st.session_state.ocr is None:
                st.session_state.ocr = PaddleOCR(
                    use_angle_cls=True,
                    show_log=False,
                    lang='korean',
                    det_model_dir='/Users/nongshim/Desktop/Python/project/streamlit_image_annotation/Detection/inference/det_v6',
                    rec_model_dir='/Users/nongshim/Desktop/Python/project/streamlit_image_annotation/Detection/inference/rec_v2_19_best'
                )

            _, detected_boxes = detect_text_regions(temp_image_path, st.session_state.ocr)
            # 감지된 바운딩 박스를 기존 어노테이션에 추가
            for box in detected_boxes:
                # PaddleOCR의 box는 4개의 점(점 4개가 x, y 좌표를 가짐)으로 구성됨
                # 최소/최대 x, y 값을 찾아서 bounding box를 만듦
                points = np.array(box)
                min_x, min_y = np.min(points, axis=0)
                max_x, max_y = np.max(points, axis=0)

                # 새로운 바운딩 박스 좌표 생성 (x1, y1, x2, y2 형식)
                new_bbox = [float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)]
                # print("DEBUG: new_bbox", new_bbox)
                # 새 바운딩 박스가 기존에 없으면 추가
                if new_bbox not in bboxes:
                    bboxes.append(new_bbox)
                    labels.append("")  # 자동 감지된 텍스트의 기본 라벨
                    
                    # 세션 상태의 어노테이션 데이터 업데이트 (실제로는 여기서 DB에 저장이 필요할 수 있음)
                    if 'annotations' in st.session_state:
                        # 현재 최대 ID 찾기
                        max_id = 0
                        if st.session_state.annotations:
                            for annotation in st.session_state.annotations:
                                if annotation.get("id", 0) > max_id:
                                    max_id = annotation["id"]
                        
                        # 새 어노테이션 객체 생성
                        new_annotation = {
                            "id": max_id + 1,
                            "label": "",
                            "bbox": {
                                "x": new_bbox[0],
                                "y": new_bbox[1],
                                "width": new_bbox[2],
                                "height": new_bbox[3]
                            }
                        }
                        # print("DEBUG: new_annotation", new_annotation)
                        st.session_state.annotations.append(new_annotation)
  
    except Exception as e:
        st.error(f"이미지 로드 또는 텍스트 감지 중 오류 발생: {e}")
    finally:
        # 임시 파일 삭제
        if temp_image_path and os.path.exists(temp_image_path):
            os.unlink(temp_image_path)

def preprocess_roi(cropped, target_width=320, target_height=48):
    h, w = cropped.shape[:2]
    ratio = w / float(h)
    
    # 종횡비를 유지하면서 높이 맞추기
    if int(target_height * ratio) <= target_width:
        resized_w = int(target_height * ratio)
        resized = cv2.resize(cropped, (resized_w, target_height))
        
        # 패딩 추가
        processed = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        processed[:, 0:resized_w, :] = resized
    else:
        # 너비가 너무 길면 너비에 맞추고 높이 조정
        resized_h = int(target_width / ratio)
        resized = cv2.resize(cropped, (target_width, resized_h))
        
        # 패딩 추가 (세로 중앙 정렬)
        processed = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        pad_top = (target_height - resized_h) // 2
        processed[pad_top:pad_top+resized_h, :, :] = resized
    
    return processed

def recognize_text_from_rois(img_np, boxes, ocr, batch_size=32, width=320, height=48):
    """
    검출된 BBox를 기반으로 ROI를 추출한 후, 텍스트를 인식하는 함수
    """
    roi_images = []
    valid_boxes = []

    # ROI 추출 및 전처리
    for points in boxes:
        x_min, x_max = int(min(points[:, 0])), int(max(points[:, 0]))
        y_min, y_max = int(min(points[:, 1])), int(max(points[:, 1]))
        
        cropped = img_np[y_min:y_max, x_min:x_max]
        processed = preprocess_roi(cropped, width, height)  # 전처리 함수 적용
        
        roi_images.append(processed)
        valid_boxes.append(points)

    paddle_boxes = []
    paddle_txts = []
    paddle_scores = []

    # 배치 단위로 Recognition 수행
    for i in range(0, len(roi_images), batch_size):
        batch_images = roi_images[i:i+batch_size]
        batch_boxes = valid_boxes[i:i+batch_size]
        
        rec_results = ocr.text_recognizer(batch_images)
        
        if rec_results is None or len(rec_results[0]) == 0:
            continue
        
        texts = rec_results[0]
        
        for j, (text_info, box) in enumerate(zip(texts, batch_boxes)):
            if text_info is not None:
                text, conf = text_info
                paddle_boxes.append(box.tolist())
                paddle_txts.append(text)
                paddle_scores.append(conf)

    return paddle_boxes, paddle_txts, paddle_scores


def process_ocr_for_bbox_array(image_np, bbox, ocr):
    """
    NumPy 배열 형태의 이미지에서 선택된 바운딩 박스에 대해 OCR 처리를 수행합니다.
    
    Args:
        image_np: 이미지 NumPy 배열
        bbox: 바운딩 박스 좌표 [x, y, width, height]
        ocr: OCR 모델 인스턴스
    
    Returns:
        인식된 텍스트 목록
    """
    default_text = ["추천"]  # 기본 추천 텍스트
    try:        
        # 바운딩 박스 좌표 계산
        x, y, width, height = bbox
        x1, y1 = int(x), int(y)
        x2, y2 = int(x + width), int(y + height)
        
        # 이미지 크기 확인 및 좌표 보정
        h, w = image_np.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        # 범위가 유효한지 확인
        if x1 >= x2 or y1 >= y2 or x1 >= w or y1 >= h:
            print(f"DEBUG: 유효하지 않은 바운딩 박스 좌표: x1={x1}, y1={y1}, x2={x2}, y2={y2}, w={w}, h={h}")
            return default_text  # 유효하지 않은 영역
        
        # 이미지 크롭
        cropped_image = image_np[y1:y2, x1:x2]
        
        # 크롭된 이미지 크기 확인 (디버깅용)
        print(f"DEBUG: 크롭된 이미지 크기: {cropped_image.shape}")
        
        # PaddleOCR에서 사용하는 형식으로 바운딩 박스 좌표 변환
        # 좌상, 우상, 우하, 좌하 순서의 4개 점 좌표
        paddle_box = np.array([
            [x1, y1],  # 좌상단
            [x2, y1],  # 우상단
            [x2, y2],  # 우하단
            [x1, y2]   # 좌하단
        ]).reshape(1, 4, 2)  # (1, 4, 2) 형태로 변환
        
        # recognize_text_from_rois 함수 호출
        paddle_boxes, paddle_txts, paddle_scores = recognize_text_from_rois(
            image_np, paddle_box, ocr, batch_size=1
        )
        
        # 결과 확인 및 반환
        if paddle_txts and len(paddle_txts) > 0:
            print(f"DEBUG: 인식된 텍스트: {paddle_txts}, 점수: {paddle_scores}")
            
            # # 신뢰도 기준으로 필터링 (옵션)
            # confidence_threshold = 0.5
            # filtered_texts = [txt for txt, score in zip(paddle_txts, paddle_scores) if score > confidence_threshold]
            
            # "추천" 항목을 맨 앞에 추가하고 결과 반환
            return paddle_txts
        else:
            print("DEBUG: 텍스트가 인식되지 않았습니다.")
            return default_text # 인식된 텍스트가 없는 경우
        
    except Exception as e:
        print(f"OCR 처리 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()  # 상세 오류 정보 출력
        return default_text  # 오류 발생 시 기본값 반환
    

def convert_annotations(annotations, format_option, image_path):
    if format_option == "YOLO":
        # 예: YOLO 포맷으로 변환 (x_center, y_center, width, height) 정규화 필요
        # 이미지 크기를 불러오는 부분이 필요함
        from PIL import Image
        image_file = st.session_state.minio_client.load_image(st.session_state.selected_bucket, image_path)
        with Image.open(image_file) as img:
            img_w, img_h = img.size

        yolo_lines = []
        for ann in annotations:
            x = ann["bbox"]["x"]
            y = ann["bbox"]["y"]
            w = ann["bbox"]["width"]
            h = ann["bbox"]["height"]
            x_center = (x + w / 2) / img_w
            y_center = (y + h / 2) / img_h
            w /= img_w
            h /= img_h
            yolo_lines.append(f"{ann['label']} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")

        return "\n".join(yolo_lines)

    elif format_option == "Pascal VOC":
        # Pascal VOC: XML 형식
        from xml.etree.ElementTree import Element, SubElement, tostring
        import xml.dom.minidom

        annotation = Element('annotation')
        filename = SubElement(annotation, 'filename')
        filename.text = os.path.basename(image_path)

        size = SubElement(annotation, 'size')
        image_file = st.session_state.minio_client.load_image(st.session_state.selected_bucket, image_path)
        from PIL import Image
        with Image.open(image_file) as img:
            img_w, img_h = img.size
        SubElement(size, 'width').text = str(img_w)
        SubElement(size, 'height').text = str(img_h)
        SubElement(size, 'depth').text = "3"

        for ann in annotations:
            obj = SubElement(annotation, 'object')
            SubElement(obj, 'name').text = ann["label"]
            bndbox = SubElement(obj, 'bndbox')
            SubElement(bndbox, 'xmin').text = str(ann["bbox"]["x"])
            SubElement(bndbox, 'ymin').text = str(ann["bbox"]["y"])
            SubElement(bndbox, 'xmax').text = str(ann["bbox"]["x"] + ann["bbox"]["width"])
            SubElement(bndbox, 'ymax').text = str(ann["bbox"]["y"] + ann["bbox"]["height"])

        xml_str = xml.dom.minidom.parseString(tostring(annotation)).toprettyxml(indent="  ")
        return xml_str


def create_download_zip(selected_images, format_option, download_option):
    zip_buffer = io.BytesIO()
    print(st.session_state.annotations)
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for image_path in selected_images:
            object_name = image_path.replace("easylabel/", "")
            # 이미지 로드
            image_file = None
            if download_option in ["이미지만", "이미지 + 라벨"]:
                image_file = st.session_state.minio_client.load_image(st.session_state.selected_bucket, object_name)
                if image_file:
                    zipf.write(image_file, arcname=f"images/{os.path.basename(object_name)}")

            # 라벨 로드 및 변환
            if download_option in ["라벨만", "이미지 + 라벨"]:
                success = load_annotations(image_path)
                if success and "annotations" in st.session_state:
                    annotations = st.session_state.annotations
                    label_content = convert_annotations(annotations, format_option, object_name)
                    label_filename = os.path.splitext(os.path.basename(object_name))[0] + ".txt"
                    zipf.writestr(f"labels/{label_filename}", label_content)

    zip_buffer.seek(0)
    return zip_buffer
