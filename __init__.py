import streamlit as st
import os
import json
import time
import zipfile
import io
import uuid
import datetime


# 리팩토링된 모듈 가져오기
from app_utils import *
from postgresql_utils import *
from minio_utils import MinIOManager
from annotate_utils import detection
from render_utils import *
from style_utils import * 

def set_page_style():
    st.set_page_config(
        page_title="EasyLabel",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # CSS 스타일링
    apply_custom_styles()
# 세션 상태 초기화
def initialize_session_state():
    default_values = {
        # 로그인 관련
        "logged_in": False,
        "userid": None,
        "selected_userid": None,
        "access_key": None,
        "secret_key": None,

        # 모드 및 파일 관리
        "mode": "project_list",
        "review_mode": False,    # 레이블링 vs 검토 화면 전환
        "project_id": None,
        "project_name": None,
        "current_image": None,
        "file_uploader_key": 0,

        # 페이지 및 리스트 관련
        "current_page": 0,
        "page_by_mode": {
            ("confirmed", None): 0,
            ("labeling", True): 0,
            ("labeling", False): 0,
        },
        "page_num": 1,
        "image_list": [],
        "project_list": [],
        "selected_images": set(),

        # 레이블링 전용 상태
        "current_mode": "Draw",
        "annotations": {},
        "ocr_suggestions": None,
        "pending_ocr_request": False,
        "render_key": int(time.time()),
        "ocr": None,

        # MinIO 및 저장소
        "minio_client": None,
        "selected_bucket": "easylabel",
    }

    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# 사이드바 UI 구성
def render_sidebar():
    with st.sidebar:
        st.markdown("---")
        st.header("단축키:")
        st.write("- Ctrl+E: 박스 편집(Edit) 모드")
        st.write("- Ctrl+D: 박스 그리기(Draw) 모드")
        st.write("- Ctrl+L: 라벨 입력(Label) 모드")
        st.write("- ESC: 취소") 
        st.write("- Del: 삭제") 



def render_main_content():
    print(f"mode: {st.session_state.mode}")
    # image_list 업데이트
    if st.session_state.review_mode:
        st.session_state.image_list = get_path_by_status("review")
    elif st.session_state.mode == "labeling":
        st.session_state.image_list = get_path_by_status("assigned")
    elif st.session_state.mode == "confirmed":
        print(f"0) total images: {len(st.session_state.image_list)}")
        st.session_state.image_list = get_path_by_status("confirmed")
    print(f"1) total images: {len(st.session_state.image_list)}")
    
    # 모드 표시자 스타일 추가
    apply_mode_indicator_styles()

    # 현재 이미지 설정'
    if len(st.session_state.image_list) > 0:
        if len(st.session_state.image_list) <= get_current_page():
            set_current_page(get_current_page()-1)
        st.session_state.current_image = st.session_state.image_list[get_current_page()]

        # 어노테이션 로드
        load_annotations(st.session_state.current_image)
        
        # 어노테이션 데이터 준비
        bboxes, labels = prepare_annotation_data()
    print(f"2) total images: {len(st.session_state.image_list)}")
    # 상태 전환 버튼
    if st.session_state.mode != "confirmed":
        col1, col2, col3 = st.columns(3)
        with col2:
            # 상단: 모드 전환 버튼 (레이블링 ↔ 검토)
            if st.session_state.review_mode:
                label = "🔁 레이블링 모드로 전환" 
            elif st.session_state.mode == "confirmed" or not st.session_state.review_mode:
                label = "🔁 검토 모드로 전환"

            if st.button(label, use_container_width=True):
                st.session_state.review_mode = not st.session_state.review_mode
                st.rerun()

        image_id = get_image_id(st.session_state.current_image)
        
        if not st.session_state.review_mode:
            with col1:
                if st.button("✅ 검토로 넘기기", help="나에게 검토 작업을 할당합니다.", type="primary", use_container_width=True):
                    update_metadata(image_id, "review")
                    handle_next_image_after_action()
            with col3:
                if st.session_state.mode == "confirmed":
                    label = "🔁 레이블링 모드로 전환"
                if 'render_key' not in st.session_state:
                    st.session_state.render_key = 0
                    
                # 자동 감지 전에 현재 시간을 포함한 고유 키 생성
                if st.button("🔍 자동 감지", help="OCR을 활용해 박스를 자동으로 그려줍니다", type="tertiary", use_container_width=True):
                    object_name = st.session_state.current_image.replace("easylabel/","")
                    print(f"DEBUG: object_name: {object_name}")
                    auto_detect_text_regions(st.session_state.selected_bucket, object_name, bboxes, labels)
                    # 키 업데이트
                    st.session_state.render_key += 1
        else:
            with col1:
                if st.button("↩️ 레이블링으로 되돌리기", help="나에게 레이블링 작업을 할당합니다.", type="primary", use_container_width=True):
                    update_metadata(image_id, "assigned")
                    handle_next_image_after_action()

            with col3:
                if st.button("🎯 검토 확정하기", help="업로드한 사용자에게 전달합니다.", type="primary", use_container_width=True):
                    conn = connect_to_postgres()
                    cursor = conn.cursor()
                    cursor.execute("SELECT created_by FROM metadata WHERE id = %s", (image_id,))
                    result = cursor.fetchone()
                    if result:
                        assigned_by = result[0]  # created_by 값을 assigned_by에 할당
                    update_metadata(image_id, "confirmed", assigned_by)
                    handle_next_image_after_action()
    print(f"3) total images: {len(st.session_state.image_list)}")
    if len(st.session_state.image_list) > 0:
        # 이미지 정보 표시
        update_current_image()
        print(f"4) total images: {len(st.session_state.image_list)}")
        # 이미지 네비게이션
        print(f"DEBUG: 현재 이미지: {st.session_state.current_page}")
        render_image_controls()

        # 이미지 어노테이션 표시
        render_image_annotation(st.session_state.current_image, bboxes, labels)
    
    else:
        st.error("표시할 이미지가 없습니다.")


def render_project_list_screen():
    st.markdown("## 📁 내 프로젝트")
    st.markdown("작업할 프로젝트를 선택하거나 새로 만들 수 있어요.")
    
    # 🔹 새 프로젝트 생성 섹션
    with st.expander("➕ 새 프로젝트 만들기"):
        new_project_name = st.text_input("프로젝트 이름", placeholder="예: OCR 4월 작업")
        if check_project_name_exists(new_project_name):
            st.warning("이미 존재하는 프로젝트 이름입니다.")
        else:
            uploaded_files = st.file_uploader("이미지 업로드", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

            if st.button("📦 프로젝트 생성", use_container_width=True):
                if not new_project_name or not uploaded_files:
                    st.warning("프로젝트 이름과 이미지를 모두 입력해주세요.")
                else:
                    st.session_state.project_name = new_project_name
                    # 고유한 project_id 생성
                    project_id = str(uuid.uuid4())[:8]
                    st.session_state.project_id = project_id
                    success = file_uploader(uploaded_files)
                    if success:
                        st.success("프로젝트 생성 완료!")
                        st.session_state.file_uploader_key += 1
                    else:
                        st.error("프로젝트 생성 실패")


    st.markdown("---")

    # 🔄 DB에서 사용자 기반 프로젝트 목록 로딩

    my_projects = get_projects_by_user(st.session_state.userid)
    
    # 🔄 DB에서 사용자가 공유받은 프로젝트 목록 로딩  
    shared_projects = get_shared_projects(st.session_state.userid)

    # 내 프로젝트 표시
    st.markdown("### 🔒 내가 만든 프로젝트")
    if not my_projects:
        st.info("아직 생성된 프로젝트가 없습니다. 상단에서 새 프로젝트를 만들어보세요.")
    else:
        display_project_list(my_projects)

    # 공유받은 프로젝트 표시
    st.markdown("---")
    st.markdown("### 🔗 공유받은 프로젝트")
    if not shared_projects:
        st.info("공유받은 프로젝트가 없습니다.")
    else:
        display_project_list(shared_projects)


# 메인 함수 실행
def main():
    set_page_style()
    initialize_session_state()

    if not st.session_state.logged_in:
        login()
        return

    st.session_state.minio_client = MinIOManager(
        st.session_state.access_key, st.session_state.secret_key
    )
 
    # 현재 모드에 따라 화면 렌더링
    if st.session_state.mode == "project_list":
        render_project_list_screen()

    elif st.session_state.mode == "image_list":
        render_navigation_buttons()
        render_image_list_screen()

    elif st.session_state.mode == "labeling":
        render_navigation_buttons()
        render_main_content()

    elif st.session_state.mode == "confirmed":
        render_navigation_buttons()
        render_main_content()

if __name__ == "__main__":
    main()