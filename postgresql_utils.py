import streamlit as st
import os
import json
import datetime
import psycopg2
from app_utils import *

def connect_to_postgres():
    """PostgreSQL 데이터베이스에 연결합니다."""
    try:
        conn = psycopg2.connect(
            dbname="postgres", 
            user="postgres", 
            password="1111", 
            host="localhost", 
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"PostgreSQL 연결 오류: {e}")
        return None

def insert_metadata(image_path):
    """이미지 메타데이터를 데이터베이스에 삽입합니다."""
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # info 테이블에 데이터 삽입
        current_time = datetime.datetime.now().isoformat()
    
        # 이미지 크기 확인
        print(f"이미지 크기 확인 전 확인: {image_path}")
        img_width, img_height = get_image_dimensions(image_path.replace("easylabel/", ""))
        print(f"DEBUG: img_width={img_width}, img_height={img_height}")
        info_data = {
            'filename': os.path.basename(image_path),
            'storage_path': image_path,
            'status': 'working',
            'width': img_width,
            'height': img_height,
            'created_by': st.session_state.userid,
            'created_at': current_time,
            'assigned_by': None,    
            'last_modified_by': st.session_state.userid,
            'last_modified_at': current_time,
            
        }
        insert_info_sql = """
            INSERT INTO metadata (filename, storage_path, status, width, height, created_by, created_at, assigned_by, last_modified_by, last_modified_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """
        cursor.execute(insert_info_sql, (
            info_data['filename'], info_data['storage_path'], info_data['status'],
            info_data['width'], info_data['height'], 
            info_data['created_by'], info_data['created_at'], info_data['assigned_by'],
            info_data['last_modified_by'], info_data['last_modified_at']
        ))
        print("DEBUG: 메타데이터 삽입 완료")
        # 커밋 후 연결 종료
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"데이터베이스 저장 오류: {e}")
        return False


def delete_image_and_metadata(image_path):
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()

        # metadata 테이블에서 이미지 삭제
        delete_metadata_sql = """
            DELETE FROM metadata
            WHERE storage_path = %s;
        """
        cursor.execute(delete_metadata_sql, (image_path,))
        conn.commit()

        # 커밋 후 연결 종료
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"이미지 및 메타데이터 삭제 중 오류 발생: {e}")


def update_metadata(image_path, new_image_path, new_status):
    """이미지 메타데이터의 storage_path와 status 값을 업데이트합니다."""
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 업데이트할 데이터
        current_time = datetime.datetime.now().isoformat()
    
        update_sql = """
            UPDATE metadata
            SET storage_path = %s, 
            status = %s, 
            last_modified_by = %s, 
            last_modified_at = %s
            WHERE storage_path = %s;
        """
        cursor.execute(update_sql, (
            new_image_path, 
            new_status, 
            st.session_state.userid, 
            current_time, 
            image_path
        ))

        print(f"DEBUG: {new_image_path}의 메타데이터 업데이트 완료")
        
        # 커밋 후 연결 종료
        conn.commit()
        cursor.close()
        conn.close()

        return True
    except Exception as e:
        print(f"데이터베이스 업데이트 오류: {e}")
        return False


def get_assigned_count(folder_prefix):
    """
    특정 폴더 내에서 사용자에게 할당된 이미지 수를 DB에서 조회하여 반환합니다.
    """
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 이미지 목록 가져오기 (MinIO에서 경로 가져오기)
        images = st.session_state.minio_client.list_images_in_bucket(
            st.session_state.selected_bucket, 
            prefix=folder_prefix
        )
        
        # 파일명 목록 생성
        filenames = [os.path.basename(image_path) for image_path in images]
        
        if not filenames:
            return 0
        
        # SQL 쿼리 작성 (이미지 파일명 목록에 해당하는 할당된 이미지 수 조회)
        # status 필드가 'assigned'인 이미지 수 조회
        if folder_prefix == "working":
            # working 폴더에서는 현재 사용자에게 할당된 이미지만 카운트
            select_sql = """
                SELECT COUNT(*) 
                FROM metadata 
                WHERE filename IN %s 
                AND status = 'assigned'
                AND last_modified_by = %s
            """
            cursor.execute(select_sql, (tuple(filenames), st.session_state.userid))
        else:
            # 다른 폴더에서는 모든 할당된 이미지 카운트
            select_sql = """
                SELECT COUNT(*) 
                FROM metadata 
                WHERE filename IN %s 
                AND status = 'assigned'
            """
            cursor.execute(select_sql, (tuple(filenames),))
        
        # 결과 가져오기
        assigned_count = cursor.fetchone()[0]
        
        # 연결 종료
        cursor.close()
        conn.close()
        
        return assigned_count
        
    except Exception as e:
        print(f"DEBUG: 할당된 이미지 수 조회 중 오류 발생 - {e}")
        return 0


def get_image_id(storage_path):
    """storage_path에 해당하는 image_id를 metadata 테이블에서 가져오는 함수"""
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()

        # 해당 storage_path에 대한 image_id를 찾는 쿼리
        query = """
            SELECT id FROM metadata WHERE storage_path = %s;
        """
        cursor.execute(query, (storage_path,))
        result = cursor.fetchone()

        # 결과가 없으면 None을 반환
        if result is None:
            print(f"DEBUG: 해당 storage_path에 대한 image_id를 찾을 수 없습니다. storage_path: {storage_path}")
            return None
        return result[0]  # id 값 반환

    except Exception as e:
        print(f"DEBUG: 오류 발생 - {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def load_metadata(image_path):
    """
    이미지의 메타데이터를 DB에서 읽어오는 함수
    """
    try:
        image_id = get_image_id(image_path)
        
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 해당 이미지의 메타데이터 정보 조회
        print(f"DEBUG: image_id={image_id}")
        select_sql = "SELECT filename, storage_path, assigned_by, status FROM metadata WHERE id = %s"
        cursor.execute(select_sql, (image_id,))
        
        # 결과 가져오기
        metadata = cursor.fetchone()
        
        # 연결 종료
        cursor.close()
        conn.close()
    
        if metadata:
            st.session_state.metadata = {
                'filename': metadata[0],
                'storage_path': metadata[1],
                'assigned_by': metadata[2] if not None else None,
                'status': metadata[3]
            }
            print(f"DEBUG: 메타데이터 로딩 완료: {st.session_state.metadata}")
            return True
        else:
            print("DEBUG: 메타데이터가 존재하지 않음")
            return False
        
    except Exception as e:
        print(f"DEBUG: 메타데이터 로딩 중 오류 발생 - {e}")
        return False

def get_status_counts():
    """
    데이터베이스에서 status 기준으로 이미지 개수를 가져오는 함수
    
    Returns:
        dict: 각 status별 이미지 개수
    """
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 상태별 이미지 수 조회 쿼리
        count_sql = """
        SELECT status, COUNT(*) 
        FROM metadata 
        GROUP BY status
        """
        cursor.execute(count_sql)
        
        # 결과를 딕셔너리로 변환
        status_counts = {status: count for status, count in cursor.fetchall()}
        
        # 연결 종료
        cursor.close()
        conn.close()
        
        return status_counts
        
    except Exception as e:
        print(f"DEBUG: 상태별 이미지 수 조회 중 오류 발생 - {e}")
        return {}


def get_assigned_count(status):
    """
    특정 상태 중 할당된 이미지 개수를 가져오는 함수
    
    Args:
        status: 조회할 이미지 상태
        
    Returns:
        int: 해당 상태 중 할당된 이미지 개수
    """
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 특정 상태 중 할당된 이미지 수 조회 쿼리
        count_sql = """
        SELECT COUNT(*) 
        FROM metadata 
        WHERE status = %s AND assigned_by IS NOT NULL
        """
        cursor.execute(count_sql, (status,))
        
        # 결과 가져오기
        count = cursor.fetchone()[0]
        
        # 연결 종료
        cursor.close()
        conn.close()
        
        return count
        
    except Exception as e:
        print(f"DEBUG: 할당된 '{status}' 상태 이미지 수 조회 중 오류 발생 - {e}")
        return 0

def load_annotations(image_path):
    """
    이미지의 어노테이션을 DB에서 읽어오는 함수
    """
    try:
        image_id = get_image_id(image_path)
        
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 해당 이미지의 어노테이션 정보 조회
        print(f"DEBUG: image_id={image_id}")
        select_sql = "SELECT label, bbox FROM annotations WHERE info_id = %s"
        cursor.execute(select_sql, (image_id,))
        
        # 결과 가져오기
        annotations = []
        for row in cursor.fetchall():
            label, bbox = row
            annotations.append({
                'label': label,
                'bbox': bbox
            })
        
        # 연결 종료
        cursor.close()
        conn.close()
        
        # session_state에 저장
        st.session_state.annotations = annotations
        
        print(f"DEBUG: {len(annotations)}개의 어노테이션을 불러옴")
        return True
        
    except Exception as e:
        print(f"DEBUG: 어노테이션 로딩 중 오류 발생 - {e}")
        return False
    
def insert_annotations(image_path):
    """
    여러 어노테이션을 PostgreSQL 데이터베이스에 저장하거나 업데이트하는 함수.
    """
    try:
        image_id = get_image_id(image_path)

        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()

        # 트랜잭션 시작
        conn.autocommit = False  # 자동 커밋 비활성화
        
        # 먼저 해당 이미지의 모든 어노테이션을 삭제
        delete_sql = "DELETE FROM annotations WHERE info_id = %s"
        cursor.execute(delete_sql, (image_id,))
        
        # 새로운 어노테이션을 추가
        for ann in st.session_state.annotations:
            label = ann['label']
            bbox = ann['bbox']
            # print(ann)
            
            insert_sql = """
                INSERT INTO annotations (info_id, label, bbox) 
                VALUES (%s, %s, %s);
            """
            cursor.execute(insert_sql, (
                image_id, label, json.dumps(bbox)
            ))

        # 모든 작업이 성공적으로 완료되면 커밋
        conn.commit()

        # 연결 종료
        cursor.close()
        conn.close()

        print("DEBUG: 어노테이션 저장/업데이트 완료")
        return True

    except Exception as e:
        # 오류 발생 시 롤백
        if conn:
            conn.rollback()
        print(f"DEBUG: 오류 발생 - {e}")
        return False
    

def get_filtered_images(status_filter, user_filter, sort_option):
    """
    필터 및 정렬 옵션에 따라 데이터베이스에서 이미지 목록을 가져옵니다.
    """
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 기본 쿼리 시작
        query = "SELECT filename, storage_path FROM metadata WHERE 1=1"
        params = []
        
        # 상태 필터 적용
        print(f"DEBUG: status_filter={status_filter}")
        if status_filter=="작업 중":
            query += " AND status = %s"
            params.append('working')

        elif status_filter=="검토 중 (미할당)":
            query += " AND status = %s"
            params.append('review')

        elif status_filter=="검토 중 (할당)":
            query += " AND status = %s"
            params.append('assigned')

        elif status_filter=="완료됨":
            query += " AND status = %s"
            params.append('confirmed')

        # 사용자 필터 적용
        if user_filter != "전체":
            query += " AND created_by = %s"
            params.append(user_filter)
        
        # 정렬 적용
        if sort_option == "날짜순 (최신)":
            query += " ORDER BY last_modified_at DESC"
        elif sort_option == "날짜순 (오래된)":
            query += " ORDER BY last_modified_at ASC"
        elif sort_option == "파일명순":
            query += " ORDER BY filename ASC"
        elif sort_option == "상태순":
            query += " ORDER BY status ASC"
        
        # 쿼리 실행
        cursor.execute(query, tuple(params))
        
        # 결과 가져오기
        results = cursor.fetchall()
        
        # 결과를 이미지 경로 리스트로 변환
        images = []
        for row in results:
            filename, storage_path = row
            
            # MinIO 경로를 구성하기 위해 storage_path와 filename 결합
            # storage_path는 이미 버킷 내의 경로를 포함하고 있다고 가정
            image_path = storage_path
            
            # 경로가 bucket 이름을 포함하는지 확인하고, 포함하지 않으면 추가
            bucket_name = st.session_state.selected_bucket
            if not image_path.startswith(bucket_name):
                image_path = os.path.join(bucket_name, image_path)
            
            # 파일명이 경로에 포함되어 있지 않으면 추가
            if not image_path.endswith(filename):
                image_path = os.path.join(image_path, filename)
            
            images.append(image_path)
        
        # 연결 종료
        cursor.close()
        conn.close()
        
        return images
        
    except Exception as e:
        print(f"DEBUG: 이미지 필터링 중 오류 발생 - {e}")
        return []
    

def assign_selected_images(user_id):
    """
    선택된 이미지를 특정 사용자에게 할당하고 metadata 테이블을 업데이트하는 함수
    """
    count = 0

    # PostgreSQL 연결
    conn = connect_to_postgres()
    cursor = conn.cursor()
    
    try:
        # 선택된 모든 이미지에 대해
        for key in st.session_state:
            if key.startswith("select_") and st.session_state[key]:
                image_path = key.replace("select_", "")
                
                # 이미지 ID 가져오기
                image_id = get_image_id(image_path)
                
                # 어노테이션 로드 (디버깅용)
                load_annotations(image_path)

                # 현재 시간 가져오기
                now = datetime.datetime.now()

                # metadata 테이블 업데이트
                update_sql = """
                UPDATE metadata
                SET status = %s,
                    assigned_by = %s,
                    last_modified_by = %s,
                    last_modified_at = %s
                WHERE id = %s
                """
                cursor.execute(update_sql, ("assigned", user_id, st.session_state.userid, now, image_id))

                count += 1

        # 변경사항 커밋
        conn.commit()

    except Exception as e:
        print(f"DEBUG: 이미지 할당 중 오류 발생 - {e}")
        conn.rollback()

    finally:
        cursor.close()
        conn.close()
    
    return count


def unassign_selected_images():
    """
    선택된 이미지의 할당을 해제하고 metadata 테이블을 업데이트하는 함수
    """
    count = 0
    # PostgreSQL 연결
    conn = connect_to_postgres()
    cursor = conn.cursor()
    
    try:
        # 선택된 모든 이미지에 대해
        for key in st.session_state:
            if key.startswith("select_") and st.session_state[key]:
                image_path = key.replace("select_", "")
                
                # 이미지 ID 가져오기
                image_id = get_image_id(image_path)
                
                # 어노테이션 로드 (디버깅용)
                load_annotations(image_path)
                # 현재 시간 가져오기
                now = datetime.datetime.now()
                # metadata 테이블 업데이트
                update_sql = """
                UPDATE metadata
                SET status = %s,
                    assigned_by = NULL,
                    last_modified_by = %s,
                    last_modified_at = %s
                WHERE id = %s
                """
                cursor.execute(update_sql, ("review", st.session_state.userid, now, image_id))
                count += 1
        # 변경사항 커밋
        conn.commit()
    except Exception as e:
        print(f"DEBUG: 이미지 할당 해제 중 오류 발생 - {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return count


# 페이지의 모든 이미지 선택 토글 기능
def toggle_select_all_images(images, page, items_per_page, select_all):
    """
    현재 페이지의 모든 이미지 선택/해제 토글 함수
    
    Args:
        images: 전체 이미지 경로 목록
        page: 현재 페이지 번호
        items_per_page: 페이지당 이미지 수
        select_all: 모든 이미지 선택 여부
    """
    # 현재 페이지에 표시할 이미지 슬라이싱
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(images))
    page_images = images[start_idx:end_idx]
    
    # 페이지의 모든 이미지에 대해 선택 상태 설정
    for image_path in page_images:
        st.session_state[f"select_{image_path}"] = select_all


def display_image_grid(images, page=1, items_per_page=12):
    """
    이미지를 그리드 형태로 표시하고 각 이미지의 메타데이터를 데이터베이스에서 가져와 표시합니다.
    단순화된 페이지네이션 UI가 적용되었습니다.
    
    Args:
        images: 표시할 이미지 경로 목록
        page: 현재 페이지 번호 (1부터 시작)
        items_per_page: 페이지당 표시할 이미지 수
    """
    def add_select_all_checkbox():
        # 모두 선택 체크박스
        select_all_key = f"select_all_page_{st.session_state.page_num}"
        
        # 전체 선택 체크박스가 없는 경우 초기화
        if select_all_key not in st.session_state:
            st.session_state[select_all_key] = False
        
        col1, col2 = st.columns([1, 9])
        with col1:
            select_all = st.checkbox("모두 선택", key=select_all_key)
            
            # 선택 상태가 변경되면 모든 이미지 체크박스 업데이트
            if select_all != st.session_state.get(f"{select_all_key}_previous", False):
                toggle_select_all_images(images, page, items_per_page, select_all)
                st.session_state[f"{select_all_key}_previous"] = select_all
        
        with col2:
            if select_all:
                st.markdown(f"<span style='color:#3366cc;'>현재 페이지의 모든 이미지가 선택되었습니다.</span>", unsafe_allow_html=True)
                
    # 스타일 적용
    apply_pagination_styles()
    
    # 한 행에 표시할 이미지 수
    cols_per_row = 4
    
    # 이미지가 없는 경우 메시지 표시
    if not images:
        st.info("표시할 이미지가 없습니다.")
        return
    
    # 페이지네이션 계산
    total_images = len(images)
    total_pages = (total_images + items_per_page - 1) // items_per_page  # 올림 나눗셈
    
    # 페이지 번호 유효성 검사
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    # 모두 선택 체크박스 추가
    add_select_all_checkbox()

    # 현재 페이지에 표시할 이미지 슬라이싱
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_images)
    page_images = images[start_idx:end_idx]
    
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 이미지를 행으로 나누기
        rows = [page_images[i:i + cols_per_row] for i in range(0, len(page_images), cols_per_row)]
        
        # 각 행마다 컬럼 생성
        for row in rows:
            cols = st.columns(cols_per_row)
            
            for i, image_path in enumerate(row):
                with cols[i]:
                    # 파일명 추출
                    filename = os.path.basename(image_path)
                    
                    # 데이터베이스에서 이미지 메타데이터 가져오기
                    cursor.execute("""
                        SELECT status, created_by, created_at, assigned_by
                        FROM metadata 
                        WHERE filename = %s
                    """, (filename,))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        status, created_by, created_at, assigned_by = result
                        
                        # 상태에 따른 배지 색상
                        badge_color = {
                            "working": "orange",
                            "assigned": "red",
                            "review": "green",
                            "confirmed": "blue"
                        }.get(status, "gray")
                        
                        
                        # 썸네일 표시
                        image_url = st.session_state.minio_client.get_presigned_url(
                            st.session_state.selected_bucket,
                            image_path.replace("easylabel/", "")
                        )
                        st.image(image_url)
                        
                        # 파일명 표시 
                        st.text(filename)
                        
                        # 상태 배지
                        st.markdown(f"<span style='background-color:{badge_color};padding:2px 6px;border-radius:3px;color:white;'>{status}</span>", unsafe_allow_html=True)
                        
                        # 할당된 사용자 (있는 경우)
                        with open("./DB/iam.json", "r", encoding="utf-8") as f:
                            iam = json.load(f)
                        if assigned_by:
                            st.text(f"할당된 사용자: {iam[assigned_by]['username']}({assigned_by})")

                        if created_by:
                            st.text(f"업로드한 사용자: {iam[created_by]['username']}({created_by})")
                        
                        # 업로드 날짜
                        if created_at:
                            st.text(f"업로드 시간: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # 체크박스
                        st.checkbox("선택", key=f"select_{image_path}")
                    else:
                        # 데이터베이스에 정보가 없는 경우
                        st.image(image_path, width=150)
                        st.text(filename)
                        st.warning("메타데이터 없음")
        
        # 연결 종료
        cursor.close()
        conn.close()
        
        # 단순화된 페이지네이션 UI 렌더링
        render_simplified_pagination(page, total_pages, total_images)
        
    except Exception as e:
        st.error(f"이미지 표시 중 오류 발생: {e}")


def apply_pagination_styles():
    """페이지네이션 UI 스타일을 적용하는 함수"""
    st.markdown("""
    <style>
    /* 전체 페이지네이션 컨테이너 */
    .pagination-container {
        text-align: center;
        padding: 15px 0;
        margin: 20px 0;
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    
    /* 페이지 카운터 표시 */
    .page-counter {
        font-weight: bold;
        color: #333;
        margin-bottom: 10px;
        font-size: 1.1em;
    }
    
    /* 진행 표시줄 */
    .progress-container {
        width: 100%;
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 8px;
        margin: 10px 0 15px 0;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    
    .progress-bar {
        background-color: #3366cc;
        height: 8px;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
    </style>
    """, unsafe_allow_html=True)


def render_simplified_pagination(current_page, total_pages, total_items):
    """단순화된 페이지네이션 UI를 렌더링하는 함수"""
    # 진행률 계산
    progress_value = (current_page - 1) / max(total_pages - 1, 1) * 100 if total_pages > 1 else 100
    
    # 페이지네이션 HTML 구성
    pagination_html = f"""
    <div class="pagination-container">
        <div class="page-counter">페이지 {current_page} / {total_pages} (총 {total_items}개 이미지)</div>
        <div class="progress-container">
            <div class="progress-bar" style="width: {progress_value}%;"></div>
        </div>
    </div>
    """
    
    # HTML 렌더링
    st.markdown(pagination_html, unsafe_allow_html=True)
    
    # 이전 및 다음 버튼 (고정된 위치에 배치)
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if current_page > 1:
            if st.button("◀ 이전", key="prev_page", use_container_width=True):
                st.session_state.page_num = current_page - 1
                st.rerun()
        else:
            # 이전 버튼을 비활성화된 상태로 표시하기 위한 더미 버튼
            st.button("◀ 이전", key="prev_page_disabled", disabled=True, use_container_width=True)
    
    # 중앙 컬럼은 비워둠 (고정된 레이아웃을 위해)
    
    with col3:
        if current_page < total_pages:
            if st.button("다음 ▶", key="next_page", use_container_width=True):
                st.session_state.page_num = current_page + 1
                st.rerun()
        else:
            # 다음 버튼을 비활성화된 상태로 표시하기 위한 더미 버튼
            st.button("다음 ▶", key="next_page_disabled", disabled=True, use_container_width=True)