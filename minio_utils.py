import os
import io
import tempfile
from minio import Minio
from minio.error import S3Error
import streamlit as st
import datetime
import json
from PIL import Image

# @st.cache_resource
# minioadmin


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

class MinIOManager:
    """
    MinIO 서버와의 상호작용을 관리하는 클래스
    """
    def __init__(self, access_key, secret_key, endpoint="localhost:9000", secure=False):
        """
        MinIO 클라이언트를 초기화합니다.
        
        Args:
            access_key (str): MinIO 액세스 키
            secret_key (str): MinIO 시크릿 키
            endpoint (str): MinIO 서버 엔드포인트
            secure (bool): HTTPS 사용 여부
        """
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
    
    def check_connection(self):
        """
        MinIO 서버 연결 상태를 확인합니다.
        
        Returns:
            tuple: (성공 여부, 버킷 목록 또는 에러 메시지)
        """
        try:
            buckets = self.client.list_buckets()
            return True, buckets
        except Exception as e:
            return False, str(e)

    
    def list_images_in_bucket(self, bucket_name, prefix=None):
        """
        특정 버킷 내의 이미지 파일을 반환합니다. 
        prefix가 지정되면 해당 경로 내의 이미지만 반환합니다.
        
        Args:
            bucket_name (str): 조회할 버킷 이름
            prefix (str, optional): 조회할 폴더 경로
            
        Returns:
            list: 이미지 파일 이름 목록
        """
        try:
            # prefix가 있으면 해당 경로 내의 파일만 조회
            if prefix:
                objects = list(self.client.list_objects(bucket_name, prefix=prefix, recursive=True))
            else:
                objects = list(self.client.list_objects(bucket_name, recursive=True))
                
            image_objects = [obj.object_name for obj in objects if obj.object_name.lower().endswith(('.jpg', '.jpeg', '.png'))]
            return image_objects
        except Exception as e:
            st.error(f"이미지 목록 조회 실패: {e}")
            return []

    def list_project_folders(self, bucket_name):
        """
        easylabel 버킷 안에서 최상위 프로젝트 폴더 목록을 가져옵니다.
        (즉, easylabel/project_id/* 구조의 project_id 들만 추출)
        """
        try:
            objects = self.client.list_objects(bucket_name, recursive=False)
            folders = set()
            for obj in objects:
                parts = obj.object_name.split("/")
                if len(parts) >= 2:
                    folders.add(parts[0])  # 'project_id' 추출
            return sorted(list(folders))
        except Exception as e:
            st.error(f"MinIO 프로젝트 폴더 조회 실패: {e}")
            return []

    def list_all_files(self, bucket_name):
        """
        버킷 내의 모든 파일 경로 목록을 반환합니다.
        
        Args:
            bucket_name (str): 파일 목록을 가져올 버킷 이름
            
        Returns:
            list: 모든 파일 경로 목록
        """
        try:
            # 재귀적으로 모든 객체를 나열
            objects = self.client.list_objects(bucket_name, recursive=True)
            
            # 모든 파일 경로 수집
            all_files = []
            for obj in objects:
                all_files.append(obj.object_name)
                
            return all_files
        except Exception as e:
            print(f"Error listing files in bucket {bucket_name}: {e}")
            return []
    
    def upload_image(self, bucket_name, folder_path, uploaded_file):
        """
        이미지를 MinIO 버킷에 업로드합니다.
        
        Args:
            folder_path (str): 업로드할 폴더 경로
            uploaded_file (UploadedFile): Streamlit의 업로드된 파일 객체
            
        Returns:
            bool: 성공 여부
        """
        try:            
            # 업로드할 파일의 경로 설정: 폴더 경로와 파일 이름을 합쳐서 객체 키로 사용
            object_name = os.path.join(folder_path, uploaded_file.name) 
        
            # 파일 업로드
            file_data = uploaded_file.getvalue()
            print(f"[DEBUG] 업로드 시도: {bucket_name}/{object_name}, 파일 크기: {len(file_data)}")
            self.client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(file_data),
                length=len(file_data),
                content_type=uploaded_file.type
            )
            print(f"[DEBUG] 업로드 성공: {object_name}")
            return True
        except S3Error as err:
            st.error(f"MinIO 업로드 에러: {err}")
            return False
    
    def upload_image(self, bucket_name, folder_path, uploaded_file):
        try:
            # 파일 이름과 object 이름 구성
            file_name = uploaded_file.name
            object_name = os.path.join(folder_path, file_name).replace("\\", "/")
            
            # 파일 바이트 읽기
            file_data = uploaded_file.getvalue()
            file_size = len(file_data)
            
            if file_size == 0:
                st.error(f"⚠️ {file_name}: 파일 크기가 0입니다. 업로드 생략됨.")
                return False

            # content_type이 없을 경우 기본값 지정
            content_type = uploaded_file.type or "image/jpeg"
            
            print(f"[DEBUG] 업로드 시도: {bucket_name}/{object_name}, size={file_size}, type={content_type}")
            
            self.client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(file_data),
                length=file_size,
                content_type=content_type
            )
            print(f"[DEBUG] ✅ 업로드 성공: {object_name}")
            return True
        except Exception as e:
            st.error(f"MinIO 업로드 에러: {e}")
            return False


    def load_image(self, bucket_name, object_name):
        """
        MinIO에서 이미지를 로드하여 임시 파일 경로를 반환합니다.
        
        Args:
            bucket_name (str): 이미지가 있는 버킷 이름
            object_name (str): 이미지 객체 이름
            
        Returns:
            str: 임시 파일 경로 또는 None
        """
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(object_name)[1]) as temp_file:
                # MinIO에서 파일 다운로드
                self.client.fget_object(bucket_name, object_name, temp_file.name)
                return temp_file.name
        except S3Error as err:
            st.error(f"MinIO 에러: {err}")
            return None

    def delete_image(self, bucket_name, object_name):
        """
        MinIO 버킷에서 이미지를 삭제합니다.
        
        Args:
            bucket_name (str): 이미지가 있는 버킷 이름
            object_name (str): 삭제할 이미지 객체 이름
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 이미지 삭제 시도
            self.client.remove_object(bucket_name, object_name)
            st.write("DEBUG: MinIO에서 이미지 삭제 완료")  # st.write를 사용하여 디버깅
            # st.rerun()
            return True
        except Exception as err:
            print(f"MinIO 삭제 중 오류 발생: {err}")  # 오류 발생 시 출력
            return False
           

    def get_presigned_url(self, bucket_name, object_name):
        """
        MinIO/S3 객체에 대한 presigned URL을 생성합니다.
        
        Args:
            bucket_name (str): 버킷 이름
            object_name (str): 객체 이름(경로 포함)
            expires (int): URL 만료 시간(초), 기본값은 1시간
            
        Returns:
            str: 생성된 presigned URL
        """
        try:
            # MinIO 클라이언트를 사용하여 URL 생성
            url = self.client.presigned_get_object(
                bucket_name,
                object_name,
                expires=datetime.timedelta(hours=1)
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None