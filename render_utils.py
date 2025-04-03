import os
import time
import streamlit as st
from annotate_utils import *
from minio_utils import MinIOManager
from postgresql_utils import *
from app_utils import *

def render_image_controls(image_objects):
    """이미지 네비게이션 및 폴더 이동 컨트롤을 렌더링하는 함수"""
    # 전체 이미지 수
    total_images = len(image_objects)
    current_idx = st.session_state.current_page + 1
    
    # 스타일 적용
    apply_navigation_styles()
    
    # 진행 표시줄 및 파일 정보 렌더링
    render_progress_info(total_images, current_idx)
    
    # 네비게이션 및 폴더 이동 버튼 레이아웃
    col1, col2, col3, col4 = st.columns(4)
    
    # 이전 버튼
    with col1:
        if st.button("◀ 이전") and st.session_state.current_page > 0:
            st.session_state.current_page -= 1
            update_current_image()
    
    # 다음 버튼
    with col2:
        if st.button("다음 ▶") and st.session_state.current_page < len(image_objects) - 1:
            st.session_state.current_page += 1
            update_current_image()
    
    # 폴더 이동 버튼
    with col3:
        render_folder_move_buttons()
    
    # 추가 작업 버튼 (confirmed 이동, 삭제 등)
    with col4:
        render_additional_buttons()


def apply_navigation_styles():
    """네비게이션 UI 스타일을 적용하는 함수"""
    st.markdown("""
    <style>
    .image-nav-container {
        text-align: center;
        padding: 10px 0;
        margin-bottom: 15px;
    }
    .file-name-container {
        background-color: #f0f2f6;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }
    .file-name {
        font-size: 1.1em;
        font-weight: 500;
        color: #222;
        word-break: break-all;
    }
    .image-counter {
        font-weight: bold;
        color: #333;
        margin-bottom: 5px;
    }
    .progress-container {
        width: 100%;
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 8px;
        margin: 10px 0;
    }
    .progress-bar {
        background-color: #3366cc;
        height: 8px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)


def render_progress_info(total_images, current_idx):
    """진행 표시줄 및 파일 정보를 렌더링하는 함수"""
    progress_value = st.session_state.current_page / max(total_images - 1, 1) * 100
    filename = st.session_state.current_image
    
    st.markdown(f"""
    <div class="image-nav-container">
        <div class="file-name-container">
            <div class="file-name">📁 {filename}</div>
        </div>
        <div class="image-counter">이미지 {current_idx} / {total_images}</div>
        <div class="progress-container">
            <div class="progress-bar" style="width: {progress_value}%;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_folder_move_buttons():
    """현재 폴더에 따른 이동 버튼을 렌더링하는 함수"""
    current_folder = st.session_state.current_folder
    
    # working 폴더인 경우
    if current_folder.startswith("working"):
        if st.button("review 폴더로 이동"):
            move_image_to_folder("review")
    
    # review 폴더인 경우
    elif current_folder == "review":
        if st.button("working 폴더로 이동"):
            target_folder = os.path.join("working", st.session_state.userid)
            move_image_to_folder(target_folder)
    
    # confirmed 폴더인 경우
    elif current_folder == "confirmed":
        if st.button("review 폴더로 이동"):
            move_image_to_folder("review")


def render_additional_buttons():
    """추가 작업 버튼을 렌더링하는 함수"""
    # review 폴더에서 confirmed로 이동 버튼
    if st.session_state.current_folder.startswith("review") and st.button("confirmed 폴더로 이동"):
        move_image_to_folder("confirmed")
    
    # 이미지 삭제 버튼 - working 폴더일 때만 표시
    if st.session_state.current_folder.startswith("working") and st.button("이미지 삭제"):
        delete_current_image()


def get_new_path(bucket, current_image, target_folder, userid=None):
    """대상 폴더로 이동 시 새 경로를 생성하는 함수"""
    if target_folder == "review":
        if "working" in current_image:
            return os.path.join(bucket, current_image.replace(f"working/{userid}", "review"))
        else:  # confirmed에서 review로 이동
            return os.path.join(bucket, current_image.replace("confirmed", "review"))
    elif target_folder == "confirmed":
        return os.path.join(bucket, current_image.replace("review", "confirmed"))
    else:  # working으로 이동
        return os.path.join(bucket, current_image.replace("review", f"working/{userid}"))


def move_image_to_folder(target_folder):
    """이미지를 대상 폴더로 이동하는 함수"""
    # 현재 이미지 저장
    current_image = st.session_state.current_image
    bucket = st.session_state.selected_bucket
    
    # MinIO에서 이미지 이동
    success = st.session_state.minio_client.move_image_between_folders(
        bucket,
        current_image,
        target_folder
    )
    
    if not success:
        return
    
    # 메타데이터 업데이트
    image_path = os.path.join(bucket, current_image)
    
    # 새 경로 생성
    new_path = get_new_path(bucket, current_image, target_folder, st.session_state.userid)
    
    # 메타데이터 상태 업데이트
    folder_type = "confirmed" if target_folder == "confirmed" else (
        target_folder.split("/")[0] if "/" in target_folder else target_folder
    )
    
    update_metadata(image_path, new_path, folder_type)
    
    # confirmed 폴더로 이동 시 추가 작업
    if target_folder == "confirmed":
        handle_confirmed_folder_move()
    
    # 다음 이미지로 이동 또는 페이지 새로고침
    handle_next_image_after_action()


def handle_confirmed_folder_move():
    """confirmed 폴더로 이동 시 추가 처리를 하는 함수"""
    # 다음 이미지 처리를 위해 이미지 목록 확인
    updated_images = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket, 
        prefix=st.session_state.current_folder
    )
    
    if st.session_state.current_page < len(updated_images) - 1:
        st.session_state.current_page += 1
        update_current_image()
        # 원본 코드에 있던 추가 메타데이터 업데이트
        update_metadata(
            os.path.join(st.session_state.selected_bucket, st.session_state.current_image),
            get_new_path(st.session_state.selected_bucket, st.session_state.current_image, "confirmed"),
            "confirmed"
        )

def handle_confirmed_folder_move():
    """confirmed 폴더로 이동 시 추가 처리를 하는 함수"""
    # 다음 이미지 처리를 위해 이미지 목록 확인
    updated_images = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket, 
        prefix=st.session_state.current_folder
    )

def delete_current_image():
    """현재 이미지를 삭제하는 함수"""
    # MinIO 이미지 삭제
    st.session_state.minio_client.delete_image(
        st.session_state.selected_bucket, 
        st.session_state.current_image
    )
    
    # PostgreSQL 메타데이터 삭제
    image_path = os.path.join(st.session_state.selected_bucket, st.session_state.current_image)
    delete_image_and_metadata(image_path)
    
    # 현재 페이지 조정
    if st.session_state.current_page != 0:
        st.session_state.current_page -= 1
    
    update_current_image()
    st.rerun()


def handle_next_image_after_action():
    """액션 후 다음 이미지로 이동하거나 페이지를 새로고침하는 함수"""
    # MinIO에서 현재 폴더의 이미지 목록 다시 가져오기
    updated_image_objects = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket, 
        prefix=st.session_state.current_folder
    )
    
    # 이미지 목록 처리
    adjust_page_after_action(updated_image_objects)
    
    update_current_image()
    st.rerun()  # UI 업데이트를 위해 페이지 새로고침


def adjust_page_after_action(updated_image_objects):
    """이미지 액션 후 페이지 번호를 조정하는 함수"""
    # 이미지 목록이 비어있는 경우
    if not updated_image_objects:
        st.session_state.current_page = 0
        return
    
    # 현재 페이지가 유효한지 확인하고 조정
    if st.session_state.current_page >= len(updated_image_objects):
        # 페이지 번호가 범위를 벗어나면 마지막 이미지로 조정
        st.session_state.current_page = len(updated_image_objects) - 1
    
    # 이미지가 하나만 남았다면 페이지를 0으로 설정
    if len(updated_image_objects) == 1:
        st.session_state.current_page = 0
 

def render_image_annotation():
    """이미지 어노테이션 UI를 렌더링하고 처리하는 함수"""
    # 현재 이미지 경로
    image_path = os.path.join(st.session_state.selected_bucket, st.session_state.current_image)
    
    # 어노테이션 로드
    load_annotations(image_path)
    # print("DEBUG: 어노테이션 로드 후 세션 상태:", st.session_state.annotations)
    
    # 어노테이션 데이터 준비
    bboxes, labels = prepare_annotation_data()
    # print("DEBUG: 어노테이션 데이터 준비:", bboxes, labels)
    
    if 'render_key' not in st.session_state:
        st.session_state.render_key = 0
        
    # 자동 감지 전에 현재 시간을 포함한 고유 키 생성
    if st.button("자동 감지"):
        auto_detect_text_regions(st.session_state.selected_bucket, st.session_state.current_image, bboxes, labels, image_path)
        # 키 업데이트
        st.session_state.render_key += 1

    # print("DEBUG: before annotations", st.session_state.annotations)
    # 전체 화면 너비를 사용하도록 컨테이너 설정
    container = st.container()
    with container:      
        # OCR 추천 결과가 있으면 컴포넌트에 전달
        ocr_data = None
        if hasattr(st.session_state, 'ocr_suggestions') and st.session_state.ocr_suggestions:
            ocr_data = st.session_state.ocr_suggestions
            print("DEBUG: OCR 데이터 컴포넌트로 전달:", ocr_data)
            # 전달 후 초기화 (중복 전송 방지)
            st.session_state.ocr_suggestions = None
        
        # detection 함수 호출 시 업데이트된 키 사용
        result = detection(
            client=st.session_state.minio_client,
            bucket_name=st.session_state.selected_bucket,
            object_name=st.session_state.current_image, 
            bboxes=bboxes,  
            labels=labels,  
            line_width=3, 
            use_space=True, 
            key=f"{st.session_state.current_image}-{st.session_state.render_key}",
            width=None,
            height=None,
        )
        
        if result is not None:
            process_detection_result(result, image_path)
            # OCR 결과가 있으면 세션 상태에 저장하고 재렌더링
            if "ocr_suggestions" in result:
                print("DEBUG: OCR 결과 세션 상태에 저장:", result["ocr_suggestions"])
                st.session_state.ocr_suggestions = result["ocr_suggestions"]
                # 컴포넌트 강제 재렌더링을 위해 render_key 업데이트
                st.session_state.render_key = int(time.time())
                # st.rerun()  # 강제 재실행으로 OCR 결과를 즉시 반영
            
    # JSON 결과 표시
    with st.expander("JSON 결과 보기"):
        st.json(st.session_state.annotations)


def prepare_annotation_data():
    """어노테이션 데이터를 준비하는 함수"""
    bboxes = []
    labels = []
    for ann in st.session_state["annotations"]:
        bboxes.append([
            ann['bbox']['x'],
            ann['bbox']['y'],
            ann['bbox']['width'],
            ann['bbox']['height']
        ])
        label = ann.get('label')
        labels.append(label)
    
    return bboxes, labels


def process_detection_result(result, image_path):
    """Detection 결과를 처리하는 함수"""
    # 모드 정보 업데이트
    if "mode" in result:
        st.session_state.current_mode = result["mode"]
    
    # OCR 결과가 있으면 세션 상태에 저장
    if "ocr_suggestions" in result:
        st.session_state.ocr_suggestions = result["ocr_suggestions"]
        print("DEBUG: process_detection_result에서 OCR 결과 저장:", result["ocr_suggestions"])
    
    # 바운딩 박스 정보 업데이트
    if "bboxes" in result:
        update_annotations_from_result(result["bboxes"])
        
        # Ctrl+S로 저장 요청이 있는 경우에만 어노테이션 저장
        if result.get("save_requested", False):
            insert_annotations(image_path)

def update_annotations_from_result(new_labels):
    """결과로부터 어노테이션 정보를 업데이트하는 함수"""
    # 새로운 annotations 배열 생성
    annotations = []
    for i, item in enumerate(new_labels):
        annotation = {
            "id": i + 1,  
            "label": item.get('label'),
            "bbox": {
                "x": item['bbox'][0],
                "y": item['bbox'][1],
                "width": item['bbox'][2],
                "height": item['bbox'][3]
            },
        }
        annotations.append(annotation)
    
    # 어노테이션 업데이트
    st.session_state.annotations = annotations