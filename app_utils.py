import streamlit as st
import os
import json
from PIL import Image
import datetime

def toggle_mode():
    # 현재 모드의 반대 모드로 전환
    if st.session_state.mode == "main":
        st.session_state.mode = "assignment"
    else:
        st.session_state.mode = "main"

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
        userid = st.text_input("아이디", placeholder="이름을 입력하세요")
        password = st.text_input("비밀번호", type="password", 
                               placeholder="사번을 입력하세요")
        if st.button("로그인"):
            user_db = load_user_database()
            
            if userid not in user_db:
                st.error("등록되지 않은 사용자입니다.")
                return False
            if user_db[userid]["pw"] != password:
                st.error("비밀번호가 틀렸습니다.")
                return False
            
            st.success("로그인 성공!")
            st.session_state.userid = userid
            st.session_state.access_key = user_db[st.session_state.userid]["access_key"]
            st.session_state.secret_key = user_db[st.session_state.userid]["secret_key"]
            st.session_state.logged_in = True
            st.rerun()

def load_user_database():
    if os.path.exists("./DB/iam.json"):
        with open("./DB/iam.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_image_dimensions(image_filename):
    """이미지 파일의 크기를 반환합니다."""
    try:
        # 기존 코드 패턴에 맞춰 수정
        temp_image_path = st.session_state.minio_client.load_image(
            st.session_state.selected_bucket, 
            image_filename
        )
        print(f"DEBUG: temp_image_path={temp_image_path}")
        if not temp_image_path:
            st.error(f"이미지를 로드할 수 없습니다: {image_filename}")
        
        img = Image.open(temp_image_path)
        return img.width, img.height
    except Exception as e:
        print(f"이미지 크기를 확인하는 중 오류 발생: {e}")


def update_current_folder(selected_folder):
    # 🔹 폴더 변경 감지 추가
    if "previous_folder" not in st.session_state:
        st.session_state.previous_folder = selected_folder  # 초기 설정

    # 🌟 폴더가 변경되었는지 감지
    if selected_folder != st.session_state.previous_folder:
        # 이전 폴더의 페이지 기억
        st.session_state.page_memory[st.session_state.previous_folder] = st.session_state.current_page

        # 새 폴더의 마지막 페이지 불러오기 (없으면 0)
        st.session_state.current_page = st.session_state.page_memory.get(selected_folder, 0)
        
        # 이미지가 없으면 0으로 초기화
        image_objects = st.session_state.minio_client.list_images_in_bucket(st.session_state.selected_bucket, prefix=selected_folder)
        # if len(image_objects)-1 < st.session_state.current_page:
        #     st.session_state.current_page -= 1
        #     st.session_state.page_memory[st.session_state.previous_folder] = st.session_state.current_page

        # 🔹 폴더 변경 반영
        st.session_state.previous_folder = selected_folder  # 현재 폴더를 이전 폴더로 업데이트


def update_current_image():
    """현재 페이지에 해당하는 이미지를 업데이트하고 어노테이션 데이터 로드"""
    if not hasattr(st.session_state, 'minio_client') or not st.session_state.selected_bucket:
        st.warning("MinIO 클라이언트가 설정되지 않았거나 버킷이 선택되지 않았습니다.")
        return
        
    image_objects = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket,
        prefix=st.session_state.current_folder
        )
    
    # 이미지 목록이 있는 경우에만 업데이트
    if not image_objects:
        st.warning("선택된 버킷에 이미지가 없습니다.")
        st.session_state.current_page = 0
        st.session_state.current_image = None
        return
        
    if st.session_state.current_page >= len(image_objects):
        st.session_state.current_page = 0
        
    st.session_state.current_image = image_objects[st.session_state.current_page]
    # print(f"DEBUG: 업데이트 후 image_objects={image_objects}")


def get_all_users():
    """
    모든 사용자의 목록을 반환합니다.
    """
    # working 하위 폴더의 모든 사용자 목록 가져오기
    users = []
    working_images = st.session_state.minio_client.list_images_in_bucket(
        st.session_state.selected_bucket, 
        prefix="working"
    )
    
    # 하위 폴더에서 사용자 이름 추출
    for image_path in working_images:
        user_id = image_path.split("/")[1]
        if user_id not in users:
            users.append(user_id)

    return users