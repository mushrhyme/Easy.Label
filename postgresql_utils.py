import streamlit as st
import os
import json
import datetime
import psycopg2
# from app_utils import *
from minio_utils import *
from style_utils import *


def get_mode_key():
    mode = st.session_state.get("mode")
    review_mode = st.session_state.get("review_mode") if mode == "labeling" else None
    return (mode, review_mode)


def get_current_page():
    key = get_mode_key()
    return st.session_state.page_by_mode.get(key, 0)

def set_current_page(value):
    key = get_mode_key()
    st.session_state.page_by_mode[key] = value


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

def get_projects_by_user(userid):
    """
    로그인한 사용자가 생성한 프로젝트 목록을 반환합니다.
    각 프로젝트는 storage_path에서 project_id를 추출하여 그룹화합니다.
    """
    try:
        conn = connect_to_postgres()
        cursor = conn.cursor()

        query = """
        SELECT 
            project_name,
            substring(storage_path from 'easylabel/([^/]+)/') AS project_id,
            MIN(created_at) AS created_at,
            COUNT(*) AS image_count
        FROM metadata 
        WHERE created_by = %s
        GROUP BY project_name, project_id
        ORDER BY MIN(created_at) DESC
        """
        cursor.execute(query, (userid,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [
            {
                "id": row[1],
                "name": row[0],
                "created_at": row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else "알 수 없음",
                "num_images": row[3],
            }
            for row in rows
        ]

    except Exception as e:
        print(f"프로젝트 목록 로딩 오류: {e}")
        return []

def get_shared_projects(userid):
    """
    사용자가 공유받은 프로젝트 목록을 반환합니다.
    assigned_by가 사용자인 경우 = 타인의 프로젝트에서 이미지 할당받음 = 프로젝트 공유받음
    """
    try:
        conn = connect_to_postgres()
        cursor = conn.cursor()

        query = """
        SELECT 
            project_name,
            substring(storage_path from 'easylabel/([^/]+)/') AS project_id,
            MIN(created_at) AS created_at,
            COUNT(*) AS image_count
        FROM metadata 
        WHERE assigned_by = %s 
        AND created_by != %s
        GROUP BY project_name, project_id
        ORDER BY MIN(created_at) DESC
        """
        cursor.execute(query, (userid, userid))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [
            {
                "id": row[1],
                "name": row[0],
                "created_at": row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else "알 수 없음",
                "num_images": row[3],
            }
            for row in rows
        ]

    except Exception as e:
        print(f"공유받은 프로젝트 목록 로딩 오류: {e}")
        return []


def insert_metadata(project_name, image_path):
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
            'project_name': project_name,
            'storage_path': image_path,
            'status': 'unassigned',
            'width': img_width,
            'height': img_height,
            'created_by': st.session_state.userid,
            'created_at': current_time,
            'assigned_by': None,    
            'last_modified_by': st.session_state.userid,
            'last_modified_at': current_time,
            
        }
        insert_info_sql = """
            INSERT INTO metadata (filename, project_name, storage_path, status, width, height, created_by, created_at, assigned_by, last_modified_by, last_modified_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """
        cursor.execute(insert_info_sql, (
            info_data['filename'], info_data['project_name'], info_data['storage_path'], info_data['status'],
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


def update_metadata(image_path, new_status):
    """이미지 메타데이터의 storage_path와 status 값을 업데이트합니다."""
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 업데이트할 데이터
        current_time = datetime.datetime.now().isoformat()
    
        update_sql = """
            UPDATE metadata
            SET  
            status = %s, 
            last_modified_by = %s, 
            last_modified_at = %s
            WHERE storage_path = %s;
        """
        cursor.execute(update_sql, (
            new_status, 
            st.session_state.userid, 
            current_time, 
            image_path
        ))
        
        # 커밋 후 연결 종료
        conn.commit()
        cursor.close()
        conn.close()

        return True
    except Exception as e:
        print(f"데이터베이스 업데이트 오류: {e}")
        return False

def update_metadata(image_id, new_status, assigned_by=None):
    """이미지 메타데이터의 storage_path와 status 값을 업데이트합니다."""
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 업데이트할 데이터
        now = datetime.datetime.now()

        # assigned_by가 None인 경우, DB에서 현재 값을 가져옴
        if assigned_by is None:
            cursor.execute("SELECT assigned_by FROM metadata WHERE id = %s", (image_id,))
            result = cursor.fetchone()
            if result:
                assigned_by = result[0]  # 현재 값 사용

        query = """
                UPDATE metadata 
                SET status = %s, 
                    assigned_by = %s,
                    last_modified_by = %s,
                    last_modified_at = %s
                WHERE id = %s
                """
        cursor.execute(
            query, 
            (new_status, assigned_by, st.session_state.userid, now, image_id))
        print(f"DEBUG: 메타데이터 업데이트 완료: {image_id}, {new_status}, {assigned_by}")
        # 커밋 후 연결 종료
        conn.commit()
        cursor.close()
        conn.close()

        return True
    except Exception as e:
        print(f"데이터베이스 업데이트 오류: {e}")
        return False


def check_project_name_exists(project_name):
    """
    데이터베이스에서 프로젝트명이 이미 존재하는지 확인합니다.
    
    Args:
        project_name (str): 확인할 프로젝트 이름
        
    Returns:
        bool: 프로젝트명이 존재하면 True, 아니면 False
    """
    try:
        conn = connect_to_postgres()
        cur = conn.cursor()
        
        # 프로젝트명이 이미 존재하는지 확인
        cur.execute("SELECT COUNT(*) FROM metadata WHERE project_name = %s and created_by = %s", (project_name, st.session_state.userid))
        count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return count > 0
    except Exception as e:
        print(f"Error checking project name existence: {e}")
        # 오류 발생 시 보수적으로 중복된 것으로 처리
        return True

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

def get_path_by_status(status):
    """
    현재 프로젝트의 내 작업 중 특정 상태의 이미지 개수를 반환합니다.
    내가 업로드한 모든 이미지 + 내가 작업 중인 모든 이미지
    
    Args:
        status: 조회할 이미지 상태
        
    Returns:
        int: 해당 상태의 이미지 개수
    """
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 특정 상태 중 할당된 이미지 수 조회 쿼리
        count_sql = """
        SELECT storage_path
        FROM metadata 
        WHERE 1=1
        AND status = %s 
        AND (
            substring(storage_path from 'easylabel/([^/]+)/') = %s
            AND assigned_by = %s 
            OR created_by = %s 
        )
        """
        cursor.execute(count_sql, (status, st.session_state.project_id, st.session_state.userid, st.session_state.userid))
        
        # 결과 가져오기
        rows = cursor.fetchall()
        # print(f"DEBUG: '{status}' 상태 이미지 수: {count}")
        # 연결 종료
        cursor.close()
        conn.close()
        
        return [row[0] for row in rows]
        
    except Exception as e:
        print(f"DEBUG: 할당된 '{status}' 상태 이미지 수 조회 중 오류 발생 - {e}")
        return []

def get_filtered_images(status_filter, user_filter, sort_option):
    """
    필터 및 정렬 옵션에 따라 데이터베이스에서 이미지 목록을 가져옵니다.
    """
    try:
        # PostgreSQL 연결
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        # 기본 쿼리 시작
        query = """
        SELECT filename, storage_path 
        FROM metadata 
        WHERE 1=1
        AND (
            substring(storage_path from 'easylabel/([^/]+)/') = %s
            AND assigned_by = %s -- 내가 업로드한 이미지
            OR created_by = %s -- 내가 할당받은 이미지
            
        )
         
        """
        params = [st.session_state.project_id, st.session_state.userid, st.session_state.userid]
        
        # 상태 필터 적용
        if status_filter=="미할당":
            query += " AND status = %s"
            params.append('unassigned')

        elif status_filter=="검토":
            query += " AND status = %s"
            params.append('review')

        elif status_filter=="할당":
            query += " AND status = %s"
            params.append('assigned')

        elif status_filter=="확정":
            query += " AND status = %s"
            params.append('confirmed')

        # 사용자 필터 적용
        if user_filter != "전체":
            user_filter = user_filter.split("(")[1].replace(")","").strip()  # 사용자 ID만 추출
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

def check_own_uploaded_images():
    """
    선택된 이미지 중 사용자가 직접 업로드한 이미지 수를 확인합니다.
    
    Returns:
        dict: {'count': 선택된 이미지 수, 'own': 본인이 업로드한 이미지 수, 'not_own': 타인이 업로드한 이미지 수}
    """
    try:
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        total_count = 0
        own_count = 0
        
        for key, value in st.session_state.items():
            if key.startswith("select_") and value:
                image_id = key.replace("select_", "")
                total_count += 1
                
                # 이미지가 현재 사용자가 업로드한 것인지 확인
                query = """
                SELECT COUNT(*) FROM metadata 
                WHERE storage_path = %s AND created_by = %s
                """
                cursor.execute(query, (image_id, st.session_state.userid))
                if cursor.fetchone()[0] > 0:
                    own_count += 1
        
        cursor.close()
        conn.close()
        
        return {
            'count': total_count,
            'own': own_count,
            'not_own': total_count - own_count
        }
        
    except Exception as e:
        print(f"이미지 소유권 확인 오류: {e}")
        return {'count': 0, 'own': 0, 'not_own': 0}

def change_status_selected_images(new_status, user_id=None):
    """선택된 이미지들의 상태를 변경하는 함수"""
    try:
        conn = connect_to_postgres()
        cursor = conn.cursor()
        
        count = 0
        for key, value in st.session_state.items():
            if key.startswith("select_") and value:
                image_path = key.replace("select_", "")
                
                # 이미지 ID 가져오기
                image_id = get_image_id(image_path)

                # 현재 시간 가져오기
                now = datetime.datetime.now()
                if new_status == "confirmed":
                    # created_by 값 가져오기
                    cursor.execute("SELECT created_by FROM metadata WHERE id = %s", (image_id,))
                    result = cursor.fetchone()
                    if result:
                        assigned_by = result[0]  # created_by 값을 assigned_by에 할당
                    else:
                        assigned_by = user_id
                elif new_status in ["assigned", "review"]:
                    assigned_by = user_id
                elif new_status == "unassigned":
                    assigned_by = "NULL"
                update_metadata(image_id, new_status, assigned_by)
                count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return count
        
    except Exception as e:
        print(f"상태 변경 오류: {e}")
        return 0
    
def delete_selected_images():
    """
    선택된 이미지를 MinIO에서 삭제하고 metadata 테이블에서도 삭제하는 함수
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
                
                # MinIO에서 이미지 삭제
                bucket_name = image_path.split("/")[0]
                object_name = "/".join(image_path.split("/")[1:])
                
                deletion_success = st.session_state.minio_client.delete_image(
                    bucket_name, 
                    object_name
                )
                
                if deletion_success:
                    # metadata 테이블에서 이미지 삭제
                    delete_metadata_sql = """
                        DELETE FROM metadata
                        WHERE storage_path = %s;
                    """
                    cursor.execute(delete_metadata_sql, (image_path,))
                    
                    count += 1
    
                else:
                    st.warning(f"이미지 삭제 실패: {object_name}")

        # 변경사항 커밋
        conn.commit()
        
        if count > 0:
            st.success(f"{count}개의 이미지를 성공적으로 삭제했습니다.")
            # 선택 상태 초기화
            for key in list(st.session_state.keys()):
                if key.startswith("select_"):
                    del st.session_state[key]
        else:
            st.warning("삭제할 이미지가 선택되지 않았습니다.")
            
    except Exception as e:
        st.error(f"이미지 삭제 중 오류가 발생했습니다: {e}")
        # 롤백
        conn.rollback()
    finally:
        # 연결 종료
        cursor.close()
        conn.close()
        
    return count


# 선택된 이미지가 있는지 확인
@st.dialog("이미지 삭제 확인")
def confirm_delete():
    st.warning("⚠️ 선택한 이미지를 정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("예, 삭제합니다", key="confirm_delete", use_container_width=True):
            count = delete_selected_images()
            st.session_state.delete_result = count
            st.rerun()

    with col2:
        if st.button("아니오, 취소합니다", key="cancel_delete", use_container_width=True):
            st.session_state.delete_cancelled = True
            st.rerun()

            
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
    def apply_select_all_checkbox():
        # 모두 선택 체크박스
        select_all_key = f"select_all_page_{st.session_state.page_num}"
        
        # 전체 선택 체크박스가 없는 경우 초기화
        if select_all_key not in st.session_state:
            st.session_state[select_all_key] = False
        
        select_all = st.checkbox("모두 선택", key=select_all_key)
        
        # 선택 상태가 변경되면 모든 이미지 체크박스 업데이트
        if select_all != st.session_state.get(f"{select_all_key}_previous", False):
            toggle_select_all_images(images, page, items_per_page, select_all)
            st.session_state[f"{select_all_key}_previous"] = select_all
        
        if select_all:
            st.toast(f"{st.session_state.page_num}페이지의 모든 이미지가 선택되었습니다")
                                     
    # 스타일 적용
    apply_pagination_styles()
    
    # 한 행에 표시할 이미지 수
    cols_per_row = 5
    
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
    apply_select_all_checkbox()

    # 단순화된 페이지네이션 UI 렌더링
    render_simplified_pagination(page, total_pages, total_images)

    # 현재 페이지에 표시할 이미지 슬라이싱
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_images)
    page_images = images[start_idx:end_idx]
    
    # try:
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
                        "assigned": "green",
                        "unassigned": "red",
                        "review": "orange",
                        "confirmed": "blue"
                    }.get(status, "gray")
                    
                    status_dict = {
                        "assigned": "할당",
                        "unassigned": "미할당",
                        "review": "검토",
                        "confirmed": "확정"
                    }
                    # 썸네일 표시
                    image_url = st.session_state.minio_client.get_presigned_url(
                        st.session_state.selected_bucket,
                        image_path.replace("easylabel/", "")
                    )
                    st.image(image_url)
                    
                    # 파일명 표시 
                    # 체크박스
                    st.checkbox("선택", key=f"select_{image_path}")

                    st.text(filename)
                    
                    # 상태 배지
                    st.markdown(f"<span style='background-color:{badge_color};padding:2px 6px;border-radius:3px;color:white;'>{status_dict[status]}</span>", unsafe_allow_html=True)
                    
                    # 할당된 사용자 (있는 경우)
                    with open("./DB/iam.json", "r", encoding="utf-8") as f:
                        iam = json.load(f)
            
                    if assigned_by != "NULL":
                        st.text(f"할당된 사용자: {iam[assigned_by]['username']}({assigned_by})")

                    st.text(f"업로드한 사용자: {iam[created_by]['username']}({created_by})")
                    
                    st.text(f"업로드 시간: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    
                else:
                    # 데이터베이스에 정보가 없는 경우
                    st.image(image_path, width=150)
                    st.text(filename)
                    st.warning("메타데이터 없음")
    
    # 연결 종료
    cursor.close()
    conn.close()
        
    # except Exception as e:
    #     st.error(f"이미지 표시 중 오류 발생: {e}")

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
    col3, col1, col2, col4 = st.columns(4)
    
    with col1:
        if current_page > 1:
            if st.button("◀ 이전", key="prev_page", use_container_width=True):
                st.session_state.page_num = current_page - 1
                st.rerun()
        else:
            # 이전 버튼을 비활성화된 상태로 표시하기 위한 더미 버튼
            st.button("◀ 이전", key="prev_page_disabled", disabled=True, use_container_width=True)
    
    # 중앙 컬럼은 비워둠 (고정된 레이아웃을 위해)
    
    with col2:
        if current_page < total_pages:
            if st.button("다음 ▶", key="next_page", use_container_width=True):
                st.session_state.page_num = current_page + 1
                st.rerun()
        else:
            # 다음 버튼을 비활성화된 상태로 표시하기 위한 더미 버튼
            st.button("다음 ▶", key="next_page_disabled", disabled=True, use_container_width=True)