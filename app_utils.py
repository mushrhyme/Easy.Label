import streamlit as st
import os
import json
from PIL import Image
import datetime
from postgresql_utils import *
from minio_utils import *
from style_utils import *

@st.cache_data
def load_credentials():
    with open("credentials.json", "r") as f:
        return json.load(f)

def login():
    # 로고 및 헤더
    st.markdown("""
        <div class="logo-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Nongshim_Logo.svg" 
                alt="Nongshim Logo" class="logo-image">
            <h1 class="main-header">EasyLabel</h1>
            <h2 class="sub-header">이미지 레이블링</h2>
        </div>
    """, unsafe_allow_html=True)

    # 입력 필드를 중앙에 배치
    _, col2, _ = st.columns([1,2,1])
    with col2:
        userid = st.text_input("아이디", placeholder="사번을 입력하세요")
        password = st.text_input("비밀번호", type="password", 
                               placeholder="초기 비밀번호는 1111 입니다")
        if st.button("로그인", type="primary", use_container_width=True):
            user_db = load_user_database()
            
            if userid not in user_db:
                st.error("등록되지 않은 사용자입니다.")
                return False
            if user_db[userid]["pw"] != password:
                st.error("비밀번호가 틀렸습니다.")
                return False
            
            st.success("로그인 성공!")
            st.session_state.userid = userid
            credentials = load_credentials()
            st.session_state.access_key = credentials["accessKey"]
            st.session_state.secret_key = credentials["secretKey"]
            st.session_state.logged_in = True
            st.rerun()

def set_mode(mode: str):
    """모드 전환: project_list, image_list, labeling"""
    st.session_state.mode = mode
    if mode == "project_list":
        st.session_state.project_id = None
        st.session_state.current_image = None
        st.session_state.image_list = []
    elif mode == "image_list":
        st.session_state.current_image = None
    elif mode == "labeling":
        pass  # 유지


def select_project(project_id: str):
    """프로젝트 선택 시 상태 초기화 + 이미지 목록 로드"""
    st.session_state.project_id = project_id

    # 이미지 목록 로딩
    prefix = f"{project_id}/"
    st.session_state.page_num = 1

    # get_path_by_status는 이미 storage_path 리스트를 반환하므로 리스트 컴프리헨션이 불필요
    st.session_state.image_list = get_path_by_status("assigned")

    set_mode("image_list")

def toggle_review_mode():
    """검토/레이블링 전환"""
    st.session_state.review_mode = not st.session_state.review_mode


def load_user_database():
    if os.path.exists("./DB/iam.json"):
        with open("./DB/iam.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def file_uploader(uploaded_files):
    progress_bar = st.progress(0)
    status_text = st.empty() 

    project_path = f"{st.session_state.project_id}/"

    total_files = len(uploaded_files)
    failed_files = []
    duplicate_files = []

    # 1️⃣ 중복 파일 확인
    all_files_in_bucket = st.session_state.minio_client.list_all_files(st.session_state.selected_bucket)
    all_filenames = [os.path.basename(file_path) for file_path in all_files_in_bucket]
    
    for i, file in enumerate(uploaded_files):
        # 상태 메시지 업데이트
        status_text.text(f"업로드 중... ({i+1}/{total_files}): {file.name}")

        if file.name not in all_filenames:
            # 2️⃣ 이미지 업로드
            success = st.session_state.minio_client.upload_image(
                bucket_name=st.session_state.selected_bucket,
                folder_path=project_path,
                uploaded_file=file
            )
            if not success:
                # 업로드 실패한 파일 처리
                failed_files.append(file.name)
                continue
            else:
                # 3️⃣ 메타데이터 DB에 삽입
                image_path = f"{st.session_state.selected_bucket}/{project_path}{file.name}"
                if not st.session_state.project_name:
                    st.error("프로젝트 이름을 찾을 수 없습니다. 업로드를 중단합니다.")
                    return False

                insert_metadata(st.session_state.project_name, image_path)
        else:
            # 중복된 파일 처리
            duplicate_files.append(file.name)
            continue
        progress_bar.progress((i + 1) / total_files)
    
    # 4️⃣ 결과 요약
    if failed_files:
        st.error("업로드 실패한 파일은 제외합니다:")
        st.warning(', '.join(failed_files))
    if duplicate_files:
        st.error("중복된 파일은 제외합니다:")
        st.warning(', '.join(duplicate_files))

    if len(set(failed_files+duplicate_files)) == total_files:
        return False
    else:
        return True


def update_current_image():
    """현재 페이지에 해당하는 이미지를 업데이트하고 어노테이션 데이터 로드"""
    if not hasattr(st.session_state, 'minio_client') or not st.session_state.selected_bucket:
        st.warning("MinIO 클라이언트가 설정되지 않았거나 버킷이 선택되지 않았습니다.")
        return
        
    # 이미지 목록이 있는 경우에만 업데이트
    if not st.session_state.image_list:
        st.warning("선택된 프로젝트에 이미지가 없습니다.")
        set_current_page(0)
        st.session_state.current_image = None
        return
        
    if get_current_page() >= len(st.session_state.image_list):
        set_current_page(0)
        
    st.session_state.current_image = st.session_state.image_list[get_current_page()]

def display_progress_cards():
    """
    작업 진행 현황을 카드 형태로 표시하는 함수
    """

    # 진행 상황 데이터 준비
    progress_data = {
        "미할당": len(get_path_by_status("unassigned")),
        "할당": len(get_path_by_status("assigned")),
        "검토": len(get_path_by_status("review")),
        "확정": len(get_path_by_status("confirmed"))
    }

    # 총 이미지 수 계산
    total_images = sum(progress_data.values())

    # # 전체 진행률 표시 (선택 사항)
    # st.markdown("<br>", unsafe_allow_html=True)
    # completed_images = progress_data["확정"]
    # overall_progress = (completed_images / total_images * 100) if total_images > 0 else 0
    # st.markdown(f"### 전체 진행률: {overall_progress:.1f}%")
    # st.progress(overall_progress / 100)

    # 4개의 열로 카드 배치
    col1, col2, col3, col4 = st.columns(4)

    # 각 카드의 색상 정의
    colors = {
        "검토": "#FF9F1C", # 연한 노란색
        "할당": "#1ABC9C", # 연한 초록색
        "미할당": "#F27059", # 연한 빨간색
        "확정":  "#3498DB", # 연한 파란색
    }

    # 아이콘 정의
    icons = {
        "미할당": "🔨",
        "검토": "⏳",
        "할당": "👁️",
        "확정": "☑️"
    }

    # 각 카드의 CSS 스타일 정의
    apply_card_style()


    # 각 열에 카드 추가
    columns = [col1, col2, col3, col4]
    for i, (key, value) in enumerate(progress_data.items()):
        # 퍼센트 계산
        percent = (value / total_images * 100) if total_images > 0 else 0
        
        # 카드 HTML 생성
        card_html = f"""
        <div class="metric-card" style="background-color: {colors[key]}">
            <div class="metric-icon">{icons[key]}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-label" style="font-weight: bold; font-size: 20px;">{key}</div>
            <div class="metric-percent">{percent:.1f}%</div>
        </div>
        """
        
        # 열에 카드 추가
        columns[i].markdown(card_html, unsafe_allow_html=True)

    
def adjust_page_after_action(updated_image_objects):
    """이미지 액션 후 페이지 번호를 조정하는 함수"""
    # 이미지 목록이 비어있는 경우
    if not updated_image_objects:
        set_current_page(0)
        return
    
    # 현재 페이지가 유효한지 확인하고 조정
    if get_current_page() >= len(updated_image_objects):
        # 페이지 번호가 범위를 벗어나면 마지막 이미지로 조정
        set_current_page(len(updated_image_objects) - 1)
    
    # 이미지가 하나만 남았다면 페이지를 0으로 설정
    if len(updated_image_objects) == 1:
        set_current_page(0)
 
def handle_next_image_after_action():
    """액션 후 다음 이미지로 이동하거나 페이지를 새로고침하는 함수"""
    # MinIO에서 현재 폴더의 이미지 목록 다시 가져오기
    updated_image_objects = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket, 
        prefix=st.session_state.project_id
    )
    
    # 이미지 목록 처리
    adjust_page_after_action(updated_image_objects)
    
    update_current_image()
    st.rerun()  # UI 업데이트를 위해 페이지 새로고침

# def download_confirmed_images():
#     # "완료됨" 상태의 이미지 가져오기
#     confirmed_images = get_filtered_images(status_filter="확정", user_filter="전체", sort_option="날짜순 (최신)")

#     if not confirmed_images:
#         st.warning("다운로드할 완료된 이미지가 없습니다.")
#         return

#     # 압축 파일 만들기
#     zip_buffer = io.BytesIO()
#     with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
#         for img_path in confirmed_images:
#             # 이미지 파일 추가 (파일 이름 유지)
#             zipf.write(img_path, arcname=os.path.basename(img_path))
    
#     zip_buffer.seek(0)

#     # 다운로드 버튼 추가
#     st.download_button(
#         label="완료된 이미지 다운로드 (ZIP)",
#         data=zip_buffer,
#         file_name="confirmed_images.zip",
#         mime="application/zip"
#     )


