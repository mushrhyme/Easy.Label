import streamlit as st
import os
import json
import time
import zipfile
import io


# 리팩토링된 모듈 가져오기
from app_utils import *
from postgresql_utils import *
from minio_utils import MinIOManager
from annotate_utils import detection
from render_utils import *

def set_page_style():
    st.set_page_config(
        page_title="EasyLabel",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # CSS 스타일링
    st.markdown("""
        <style>
        /* 헤더 숨기기 */
        header {
            display: none !important;
        }
                
        /* 전체 페이지 배경 */
        .stApp {
            background: linear-gradient(135deg, #f0f2f6 0%, #e3e6e8 100%);
        }
        
        /* 메인 컨테이너 스타일링 */
        .main .block-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            padding: 2rem;
            max-width: 1400px;
            margin-top: 3rem;
            position: relative;
        }
                
        /* footer 숨기기 */
        footer {
            display: none !important;
        }
                
        /* 상단 장식 */
        .main .block-container:before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 10px;
            background: #E31837;
            border-radius: 20px 20px 0 0;
        }
        
        /* 로고 컨테이너 */
        .logo-container {
            text-align: center;
            padding: 1rem 0 2rem 0;
            border-bottom: 1px solid #eee;
            margin-bottom: 2rem;
        }
        
        .logo-image {
            max-width: 200px;
            margin-bottom: 1.5rem;
        }
        
        /* 헤더 텍스트 */
        .main-header {
            color: #E31837;
            font-size: 2.2rem;
            font-weight: bold;
            text-align: center;
            margin: 0.5rem 0;
        }
        
        .sub-header {
            color: #666;
            font-size: 1.3rem;
            text-align: center;
            margin-bottom: 1rem;
        }
        
        /* 입력 필드 스타일링 */
        .stTextInput > div > div > input {
            border-radius: 8px;
            padding: 0.8rem 1rem;
            border: 2px solid #eee;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #E31837;
            box-shadow: 0 0 0 2px rgba(227,24,55,0.2);
        }
        
        /* 버튼 스타일링 */
        .stButton > button {
            background-color: #E31837;
            color: white;
            padding: 0.75rem 2rem;
            border-radius: 8px;
            border: none;
            width: 100%;
            font-size: 1.1rem;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            background-color: #C41530;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(227,24,55,0.2);
        }
        
        /* 알림 메시지 스타일링 */
        .stAlert {
            border-radius: 8px;
            margin: 1rem 0;
        }
        </style>
    """, unsafe_allow_html=True)

# 세션 상태 초기화
def initialize_session_state():
    default_values = {
        'mode': 'main',
        'minio_client': None,
        'current_folder': None,
        'current_page': 0,
        'page_num':1,
        'page_memory': {},
        'current_mode': "Draw",
        'current_image': None,
        'selected_bucket': None,
        'logged_in': False,
        'access_key': None,
        'secret_key': None,
        'userid': None,
        'state': None,
        'annotations': {},
        'ocr': None,
        'pending_ocr_request': False,
        'ocr_suggestions': None,
        'render_key': int(time.time())

    }
    
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# 사이드바 UI 구성
def render_sidebar():
    with st.sidebar:
        if st.button("Rerun"):
            st.rerun()
        # MinIO 연결 상태 확인
        st.header("MinIO 연결 상태")
        connection_success, buckets_or_error = st.session_state.minio_client.check_connection()
        
        if connection_success:
            st.success("MinIO 서버에 연결되었습니다.")
            
            # easylabel 버킷만 열기
            bucket_name = "easylabel"
            st.session_state.selected_bucket = bucket_name
           
            selected_folder = st.selectbox("폴더 선택", ["working", "review", "confirmed"])

            update_current_folder(selected_folder)

            # working 폴더
            if os.path.join(selected_folder, st.session_state.userid) == os.path.join("working", st.session_state.userid):
                st.subheader("working 폴더")
                # 사용자별 working 폴더에서 이미지 업로드/삭제
                if "file_uploader_key" not in st.session_state:
                    st.session_state.file_uploader_key = 0  # 초기 키 값 설정

                uploaded_files = st.file_uploader(
                    "이미지 선택",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key=f"file_uploader_{st.session_state.file_uploader_key}",  # 동적 key 설정
)
                if uploaded_files is not None and len(uploaded_files) > 0:
                    selected_folder = os.path.join(selected_folder, st.session_state.userid)
                    if st.button("업로드"):
                        # 진행 상황을 보여줄 progress bar 생성
                        progress_bar = st.progress(0)
                        status_text = st.empty()  # 상태 메시지를 표시할 공간
        
                        total_files = len(uploaded_files)
                        for i, uploaded_file in enumerate(uploaded_files):
                            # 상태 메시지 업데이트
                            status_text.text(f"업로드 중... ({i+1}/{total_files}): {uploaded_file.name}")
                            
                            file_path = f"{selected_folder}/{uploaded_file.name}"
                            file_exists = st.session_state.minio_client.check_file_exists(bucket_name, file_path)
                            
                            # 파일이 존재하지 않으면 업로드
                            if not file_exists:
                                if st.session_state.minio_client.upload_image(bucket_name, selected_folder, uploaded_file):
                                    image_path = os.path.join(bucket_name, selected_folder, uploaded_file.name)
                                    time.sleep(1)  # 업로드 완료를 위해 1초 대기
                                    insert_metadata(image_path)
                            
                            # 진행 상황 업데이트
                            progress_bar.progress((i + 1) / total_files)
                        
                        # 완료 메시지
                        status_text.text("모든 파일 업로드 완료!")
                        time.sleep(1)  # 완료 메시지를 잠시 표시  
                        st.session_state.file_uploader_key += 1  # 새로운 key 값 설정
                        st.rerun()  # UI 새로고침
                        
            # review 폴더
            elif selected_folder == "review":
                st.subheader("review 폴더")
                st.info("working 폴더에서 이미지를 이동하여 추가할 수 있습니다.")

            # confirmed 폴더
            elif selected_folder == "confirmed":
                st.subheader("confirmed 폴더")
                st.info("confirmed 폴더에는 review 폴더에서 이미지를 이동하여 추가할 수 있습니다.")

            # 현재 폴더 정보 업데이트
            st.session_state.current_folder = os.path.join(selected_folder, st.session_state.userid) if selected_folder=="working" else selected_folder
            
        else:
            st.error(f"MinIO 서버 연결 실패: {buckets_or_error}")
            st.info("MinIO 서버가 실행 중인지 확인하세요.")

        st.markdown("---")
        st.header("단축키:")
        st.write("- Ctrl+E: 박스 편집(Edit) 모드")
        st.write("- Ctrl+D: 박스 그리기(Draw) 모드")
        st.write("- Ctrl+L: 라벨 입력(Label) 모드")
        st.write("- ESC: 취소") 
        st.write("- Del: 삭제") 

# 메인 컨텐츠 UI 구성
def render_main_content():
    """메인 컨텐츠 화면을 렌더링하는 함수"""    
    if not st.session_state.selected_bucket:
        st.info("왼쪽 사이드바에서 MinIO 버킷을 선택해주세요.")
        return
        
    # MinIO에서 이미지 목록 가져오기
    image_objects = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket, 
        prefix=st.session_state.current_folder
    )
    
    # 현재 폴더가 "review"라면 필터링 수행
    if st.session_state.current_folder == "review":
        user_id = st.session_state.userid  # 현재 로그인한 사용자 ID
        filtered_images = []
        for image in image_objects:
            if load_metadata(os.path.join(st.session_state.selected_bucket, image)):  # 메타데이터 로딩
                assigned_by = st.session_state.metadata.get("assigned_by")
                if assigned_by == user_id:  # 사용자에게 할당된 이미지인지 확인
                    filtered_images.append(image)
        
        image_objects = filtered_images  # 필터링된 이미지 리스트로 업데이트
    # print("DEBUG: image_objects", image_objects)
    adjust_page_after_action(image_objects)
    if not image_objects:
        st.warning("선택한 버킷에 이미지 파일이 없습니다.")
        st.info("사이드바에서 이미지를 업로드해주세요.")
        return
        
    # 현재 이미지 선택 및 업데이트
    print("DEBUG: current_page", st.session_state.current_page)
    st.session_state.current_image = image_objects[st.session_state.current_page]
    update_current_image()
    
    # 이미지 네비게이션 및 폴더 이동 컨트롤 표시
    render_image_controls(image_objects)
    
    # 이미지 어노테이션 표시 및 처리
    render_image_annotation()


def display_progress_cards():
    """
    작업 진행 현황을 카드 형태로 표시하는 함수
    """
    # 상태별 이미지 개수 가져오기
    status_counts = get_status_counts()
    
    print(f"DEBUG: status_counts", status_counts)

    # 진행 상황 데이터 준비
    progress_data = {
        "작업 중": status_counts.get("working", 0),
        "검토 중 (미할당)": status_counts.get("review", 0),
        "검토 중 (할당됨)": get_assigned_count("assigned"),
        "완료됨": status_counts.get("confirmed", 0)
    }
    print(f"DEBUG: progress_data", progress_data)
    # 더 예쁜 카드 형태의 진행 상황 표시
    st.markdown("## 📊 작업 진행 현황")
    st.markdown("<br>", unsafe_allow_html=True)

    # 4개의 열로 카드 배치
    col1, col2, col3, col4 = st.columns(4)

    # 각 카드의 색상 정의
    colors = {
        "작업 중": "#FF9F1C", # 연한 노란색
        "검토 중 (미할당)": "#1ABC9C", # 연한 초록색
        "검토 중 (할당됨)": "#F27059", # 연한 빨간색
        "완료됨":  "#3498DB", # 연한 파란색
    }

    # 아이콘 정의
    icons = {
        "작업 중": "🔨",
        "검토 중 (미할당)": "⏳",
        "검토 중 (할당됨)": "👁️",
        "완료됨": "☑️"
    }

    # 각 카드의 CSS 스타일 정의
    card_style = """
    <style>
    .metric-card {
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        text-align: center;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 34px;
        font-weight: bold;
    }
    .metric-label {
        font-size: 16px;
        opacity: 0.9;
    }
    .metric-icon {
        font-size: 24px;
        margin-bottom: 8px;
    }
    </style>
    """

    st.markdown(card_style, unsafe_allow_html=True)

    # 총 이미지 수 계산
    total_images = sum(progress_data.values())

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
            <div class="metric-label">{key}</div>
            <div class="metric-percent">{percent:.1f}%</div>
        </div>
        """
        
        # 열에 카드 추가
        columns[i].markdown(card_html, unsafe_allow_html=True)

    # 전체 진행률 표시 (선택 사항)
    st.markdown("<br>", unsafe_allow_html=True)
    completed_images = progress_data["완료됨"]
    overall_progress = (completed_images / total_images * 100) if total_images > 0 else 0
    st.markdown(f"### 전체 진행률: {overall_progress:.1f}%")
    st.progress(overall_progress / 100)


def download_confirmed_images():
    # "완료됨" 상태의 이미지 가져오기
    confirmed_images = get_filtered_images(status_filter="완료됨", user_filter="전체", sort_option="날짜순 (최신)")

    if not confirmed_images:
        st.warning("다운로드할 완료된 이미지가 없습니다.")
        return

    # 압축 파일 만들기
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for img_path in confirmed_images:
            # 이미지 파일 추가 (파일 이름 유지)
            zipf.write(img_path, arcname=os.path.basename(img_path))
    
    zip_buffer.seek(0)

    # 다운로드 버튼 추가
    st.download_button(
        label="완료된 이미지 다운로드 (ZIP)",
        data=zip_buffer,
        file_name="confirmed_images.zip",
        mime="application/zip"
    )


def render_assignment_mode():
    # 진행 상황 요약
    if st.session_state.selected_bucket:
        st.subheader("이미지 목록")

        # 완료된 이미지 다운로드 버튼 추가
        download_confirmed_images()
        
        # 진행 상황 카드 표시
        display_progress_cards()

        # 필터링 및 정렬 옵션
        st.subheader("필터 및 정렬")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "상태별 필터링",
                ["전체", "작업 중", "검토 중 (미할당)", "검토 중 (할당)", "완료됨"]
            )
        
        with col2:
            # 사용자 목록 가져오기
            users = get_all_users()
            user_filter = st.selectbox(
                "사용자별 필터링",
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
            st.subheader("이미지 목록")
        
            col1, col2, col3 = st.columns(3)
            
            with open("./DB/iam.json", "r", encoding="utf-8") as f:
                iam = json.load(f)
            with col1:
                selected_user = st.selectbox(
                    "할당할 사용자 선택",
                    [iam[i]["username"]+f"({i})" for i in users]
                )
                selected_user = selected_user.split("(")[1].replace(")", "")
            
            with col2:
                if st.button("선택 이미지 할당"):
                    count = assign_selected_images(selected_user)
                    if count > 0:
                        st.success(f"{count}개 이미지가 {selected_user}에게 할당되었습니다.")
                        st.rerun()
            
            with col3:
                if st.button("선택 이미지 할당 해제"):
                    count = unassign_selected_images()
                    if count > 0:
                        st.success(f"{count}개 이미지의 할당이 해제되었습니다.")
                        st.rerun()
            
            # 이미지 그리드 표시
            display_image_grid(images, page=st.session_state.page_num, items_per_page=12)
        
        else:
            st.warning("필터 조건에 맞는 이미지가 없습니다.")
    
    else:
        st.info("왼쪽 사이드바에서 MinIO 버킷을 선택해주세요.")

# 메인 함수 실행
def main():
    set_page_style()
    initialize_session_state()
    
    if not st.session_state.logged_in:
        login()
    else:
        st.session_state.minio_client = MinIOManager(st.session_state.access_key, st.session_state.secret_key)
        render_sidebar()

        # 모드에 따라 다른 아이콘과 텍스트 표시
        if st.session_state.mode == "main":
            button_icon = "📋"  # 할당 모드로 전환하는 아이콘
            button_text = "작업 할당 모드"
        else:
            button_icon = "🏠"  # 메인 모드로 전환하는 아이콘
            button_text = "메인 모드"
        
        # 토글 버튼
        st.button(f"{button_icon} {button_text}", on_click=toggle_mode)

        # 선택된 모드에 따라 함수 실행
        if st.session_state.mode == "assignment":
            render_assignment_mode()
        else:
            render_main_content()
    

if __name__ == "__main__":
    main()