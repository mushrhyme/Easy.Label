import os
import time
import streamlit as st
from annotate_utils import *
from minio_utils import MinIOManager
from postgresql_utils import *
from app_utils import *
from style_utils import *

def display_project_list(projects):
    """
    프로젝트 목록을 표시하는 함수
    """
    cols = st.columns(2)
    for idx, proj in enumerate(projects):
        with cols[idx % 2]:
            with st.container():
                st.markdown(f"### 📦 **{proj['name']}**")
                st.markdown(f"- 생성일: `{proj['created_at']}`  \n- 이미지 수: `{proj['num_images']}장`")
                if st.button("➡️ 열기", key=f"open_{proj['id']}", use_container_width=True):
                    select_project(proj["id"])
                    st.rerun()
            st.markdown("---")

def render_mode_indicator(review_mode):
    print(f"mode: {st.session_state.mode}")
    if st.session_state.mode == "confirmed":
        mode_class = "confirmed-mode"
        mode_title = "확정 모드"
        mode_desc = "검토가 완료된 이미지를 확인하세요"
    elif st.session_state.mode == "labeling":
        # 모드에 따른 클래스와 텍스트 설정
        mode_class = "review-mode" if review_mode else "labeling-mode"
        mode_title = "검토 모드" if review_mode else "레이블링 모드"
        mode_desc = "이미지 레이블링 결과를 검토하고 확정하세요" if review_mode else "이미지에 박스를 그리고 레이블을 입력하세요"
    elif st.session_state.mode == "image_list":
        mode_class = "default-mode"
        mode_title = "관리 모드"
        mode_desc = "이미지를 업로드/삭제하고 레이블링/검토 작업을 할당하세요"
    # 모드 전환 애니메이션을 위한 키
    animation_key = f"mode_switch_{time.time()}"
        
    # HTML 구성
    html = f"""
    <style>
        .mode-indicator {{
        display: flex;
        justify-content: center; /* 가로축에서 가운데 정렬 */
        width: 100%; /* 전체 너비를 사용하도록 설정 */
        height: 50px; /* 높이 설정 */
    }}
    .mode-content {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}

    .mode-title {{
        font-weight: bold;
    }}

    .mode-description {{
        font-size: 0.9em;
    }}
    </style>
    <div class="mode-indicator {mode_class} flash-animation" key="{animation_key}">
        <div class="mode-content">
            <span class="mode-title">📋 {mode_title}</span>
            <span class="mode-description">{mode_desc}</span>
        </div>
    </div>
    
    <script>
        // 프로그레스 바 애니메이션
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(function() {{
                document.getElementById('progress-ind').style.width = '100%';
            }}, 100);
        }});
    </script>
    """
    
    # HTML 렌더링
    st.markdown(html, unsafe_allow_html=True)

def render_navigation_buttons():
    """홈 버튼과 새로고침 버튼 렌더링"""
    # 스타일 추가
    # apply_buttons_styles()
    apply_custom_styles()
    
    def image_list_button():
        if st.button("📂", type="tertiary", help="이미지 목록으로 이동합니다", use_container_width=True):
            set_mode("image_list")
            st.rerun()
    col1, col2, col5, col3, col4 = st.columns([1, 1, 4, 1, 1])
    with col1:
        if st.button("🏠", type="tertiary", help="프로젝트 목록으로 이동합니다", use_container_width=True):
            set_mode("project_list")
            st.rerun()
    with col2:
        if st.button("🆕", type="tertiary", help="페이지를 새로고침합니다", use_container_width=True):
            st.rerun()
    with col3:
        if st.session_state.mode == "labeling":
            image_list_button()
            
        elif st.session_state.mode == "image_list":
            if st.button("✏️", type="tertiary", help="레이블링/검토 작업을 시작합니다", use_container_width=True):
                st.session_state.review_mode = False
                set_mode("labeling")
                st.rerun()
        elif st.session_state.mode == "confirmed":
            image_list_button()
    with col4:
        if st.session_state.mode in ["labeling", "image_list"]:
            if st.button("☑️",type="tertiary", help="확정된 이미지 확인하기", use_container_width=True):
                set_mode("confirmed")
                st.rerun()
        elif st.session_state.mode == "confirmed":
            if st.button("⚠️", help="재검토를 위해 나에게 검토 작업을 할당합니다", type="tertiary", use_container_width=True):
                update_metadata(get_image_id(st.session_state.current_image), "review")
                handle_next_image_after_action()
    with col5:
        render_mode_indicator(st.session_state.review_mode)

def render_image_controls():
    """이미지 네비게이션 및 폴더 이동 컨트롤을 렌더링하는 함수"""
    # 전체 이미지 수
    total_images = len(st.session_state.image_list)
    # 스타일 적용
    apply_navigation_styles()

    
    # 네비게이션 및 폴더 이동 버튼 레이아웃
    col3, col1, col2, col4 = st.columns(4)
    
    # 이전 버튼
    with col1:
        if st.button("◀ 이전", type="secondary", use_container_width=True) and get_current_page() > 0:
            set_current_page(get_current_page() - 1)
            update_current_image()
    
    # 다음 버튼
    with col2:
        if st.button("다음 ▶", type="secondary", use_container_width=True) and get_current_page()< len(st.session_state.image_list) - 1:
            set_current_page(get_current_page() + 1)
            update_current_image()
    # 진행 표시줄 및 파일 정보 렌더링
    render_progress_info(total_images, get_current_page()+1)

def render_progress_info(total_images, current_idx):
    """진행 표시줄 및 파일 정보를 렌더링하는 함수"""
    progress_value = get_current_page() / max(total_images - 1, 1) * 100
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

def render_image_list_screen():
    apply_mode_indicator_styles()

    if st.session_state.selected_bucket:
        # 진행 상황 카드 표시
        display_progress_cards()

        # 필터링 및 정렬 옵션
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "상태별 필터링",
                ["전체", "미할당", "할당", "검토", "확정"]
            )
        
        with col2:
            # 사용자 목록 가져오기
            with open("./DB/iam.json", "r", encoding="utf-8") as f:
                iam = json.load(f)
            users = []
            for k, v in iam.items():
                if v["username"] not in users:
                    users.append(v["username"]+f"({k})")
            user_filter = st.selectbox(
                "업로드한 사용자별 필터링",
                ["전체"] + users
            )
            
        
        with col3:
            sort_option = st.selectbox(
                "정렬",
                ["날짜순 (최신)", "날짜순 (오래된)", "파일명순", "상태순"]
            )
        
        # 이미지 가져오기
        images = get_filtered_images(status_filter, user_filter, sort_option)
        
        if images:
            # 이미지 그리드 표시
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.write("")
                action = st.selectbox(
                    "적용할 작업 선택",
                    ["할당", "할당 해제", "검토로 변경", "확정으로 변경", "삭제"],
                )
                is_disabled = action in ["할당 해제", "확정으로 변경", "삭제"]  

            with col2:
                st.write("")
                # 할당 작업을 선택한 경우에만 사용자 선택 드롭다운 표시
                selected_user_box = st.selectbox(
                    "적용할 사용자 선택",
                    users,
                    disabled=is_disabled
                )
                selected_user = selected_user_box.split("(")[1].replace(")", "")
                st.session_state.selected_userid = selected_user
      
            with col3:
                # 메인 UI 부분
                if "delete_result" in st.session_state:
                    # 삭제 완료 후 결과 표시
                    count = st.session_state.delete_result
                    if count > 0:
                        st.toast(f"{count}개 이미지가 삭제되었습니다.")
                    else:
                        st.toast("삭제된 이미지가 없습니다.")
                    # 상태 초기화 (다음 실행을 위해)
                    del st.session_state.delete_result
                elif "delete_cancelled" in st.session_state:
                    # 상태 초기화
                    del st.session_state.delete_cancelled
                st.write("&nbsp;", unsafe_allow_html=True)
                
                if st.button("적용", type="primary", help=f"선택한 이미지에 대해 {action} 작업을 수행합니다", use_container_width=True):
                    # 선택된 이미지가 있는지 확인
                    has_selected = any(key.startswith("select") and st.session_state[key] for key in st.session_state)
                    
                    if not has_selected:
                        st.toast("작업할 이미지를 선택해주세요.")
                    else:
                        # 선택된 작업에 따라 다른 함수 실행
                        if action == "할당":
                            count =  change_status_selected_images("assigned", selected_user)
                            if count > 0:
                                st.toast(f"{count}개 이미지가 {selected_user_box}에게 할당되었습니다.")
                                time.sleep(1)
                                st.rerun()
                        
                        elif action == "할당 해제":
                            count =  change_status_selected_images("unassigned")
                            if count > 0:
                                st.toast(f"{count}개 이미지의 할당이 해제되었습니다.")
                                time.sleep(1)
                                st.rerun()
                        elif action == "검토로 변경":
                            count = change_status_selected_images("review", selected_user)
                            if count > 0:
                                st.toast(f"{count}개 이미지가 검토로 변경되었습니다.")
                                time.sleep(1)
                                st.rerun()
                        elif action == "확정으로 변경":
                            count = change_status_selected_images("confirmed")
                            if count > 0:
                                st.toast(f"{count}개 이미지가 확정으로 변경되었습니다.")
                                time.sleep(1)
                                st.rerun()
                        elif action == "삭제":
                            own_images = check_own_uploaded_images()
    
                            if own_images['not_own'] > 0:
                                st.toast("본인이 업로드한 이미지만 삭제할 수 있습니다.")
                            else:
                                # 삭제 확인 대화상자 표시
                                confirm_delete()
            with col4:
                # 업로드 대화상자 함수 정의
                @st.dialog("이미지 업로드")
                def upload_dialog():
                    st.write("업로드할 이미지 파일을 선택해주세요.\n동일한 파일명의 이미지가 서버에 존재할 경우 업로드가 불가능합니다")
                    
                    # 파일 업로더
                    uploaded_files = st.file_uploader(
                        "이미지 선택", 
                        type=["jpg", "jpeg", "png"], 
                        accept_multiple_files=True,
                        key=f"file_uploader_dialog_{st.session_state.file_uploader_key}"
                    )
                    
                    if st.button("업로드", type="primary", key="confirm_upload", use_container_width=True):
                        if uploaded_files:
                            success = file_uploader(uploaded_files)
                            if success:
                                st.success("업로드 완료!")
                                st.session_state.file_uploader_key += 1
                                st.session_state.upload_success = True
                            else:
                                st.error("업로드 실패")
                                st.session_state.upload_failed = True
                        else:
                            st.warning("업로드할 파일을 선택해주세요.")
                st.write("&nbsp;", unsafe_allow_html=True)       
                if st.button("이미지 업로드", type="primary", help="프로젝트에 이미지를 추가합니다", key="show_upload_dialog", use_container_width=True):
                    upload_dialog()

            with col5:
                @st.dialog("이미지 및 라벨 다운로드")
                def download_dialog():
                    st.write("다운로드할 형식과 옵션을 선택하세요.")
                    
                    format_option = st.selectbox("라벨 포맷 선택", ["YOLO", "Pascal VOC"])
                    download_option = st.radio("다운로드 항목 선택", ["이미지만", "라벨만", "이미지 + 라벨"])
                    
                    if st.button("다운로드 시작", type="primary", use_container_width=True):
                        selected_images = [
                            key.split("_")[1]
                            for key in st.session_state
                            if key.startswith("select_") and st.session_state[key]
                        ]

                        if not selected_images:
                            st.warning("선택된 이미지가 없습니다.")
                            return

                        # 압축 파일 생성
                        zip_buffer = create_download_zip(selected_images, format_option, download_option)
                        
                        if zip_buffer:
                            st.download_button(
                                label="📦 압축파일 다운로드",
                                data=zip_buffer,
                                file_name="images_and_labels.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
                        else:
                            st.error("다운로드 준비에 실패했습니다.")
                
                st.write("&nbsp;", unsafe_allow_html=True)
                if st.button("다운로드", type="primary", help="선택한 이미지와 라벨을 다운로드합니다", use_container_width=True):
                    download_dialog()


            ##############################################################################################################################
            # 이미지 그리드 표시
            display_image_grid(images, page=st.session_state.page_num, items_per_page=12)

        else:
            st.warning("필터 조건에 맞는 이미지가 없습니다.")
    
    else:
        st.info("왼쪽 사이드바에서 MinIO 버킷을 선택해주세요.")

def render_image_annotation(image_path, bboxes, labels):
    container = st.container()
    with container:      
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