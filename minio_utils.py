import os
import io
import tempfile
from minio import Minio
from minio.error import S3Error
import streamlit as st
import datetime
import json

# @st.cache_resource
# minioadmin
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
    
    def list_buckets(self):
        """
        MinIO의 모든 버킷 목록을 반환합니다.
        
        Returns:
            list: 버킷 이름 목록
        """
        try:
            buckets = self.client.list_buckets()
            return [bucket.name for bucket in buckets]
        except Exception as e:
            st.error(f"버킷 목록 조회 실패: {e}")
            return []
    
    def create_bucket(self, bucket_name):
        """
        새 버킷을 생성합니다.
        
        Args:
            bucket_name (str): 생성할 버킷 이름
            
        Returns:
            bool: 성공 여부
        """
        try:
            self.client.make_bucket(bucket_name)
            return True
        except Exception as e:
            st.error(f"버킷 생성 실패: {e}")
            return False
    
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
        
    def move_image_between_folders(self, bucket_name, object_name, target_folder):
        """
        이미지를 한 폴더에서 다른 폴더로 이동시킵니다.
        
        Args:
            bucket_name (str): 버킷 이름
            object_name (str): 이동할 객체 이름 (전체 경로 포함)
            target_folder (str): 대상 폴더 경로
            
        Returns:
            bool: 이동 성공 여부
        """
        try:
            # 원본 파일 데이터 가져오기
            data = self.client.get_object(bucket_name, object_name)
            
            # 새로운 경로 생성 (파일 이름만 추출하여 대상 폴더에 추가)
            file_name = os.path.basename(object_name)
            new_object_name = f"{target_folder}/{file_name}"
            
            # 파일 크기 확인 (put_object에 정확한 크기 전달)
            file_size = data.info().get('Content-Length')
            if not file_size:
                file_size = -1  # 크기를 모를 경우 -1 사용
            
            # 대상 폴더에 복사
            self.client.put_object(
                bucket_name,
                new_object_name,
                data,
                length=int(file_size),
                content_type="image/jpeg"  # 이미지 타입에 맞게 설정
            )
            
            # 원본 파일 삭제
            self.client.remove_object(bucket_name, object_name)
            
            return True
        except Exception as e:
            st.error(f"이미지 이동 실패: {e}")
            return False
    
    def check_file_exists(self, bucket_name, file_path):
        try:
            # MinIO에서 파일 존재 여부 확인
            self.client.stat_object(bucket_name, file_path)
            return True  # 파일이 존재함
        except Exception as e:
            # NoSuchKey 또는 다른 예외가 발생하면 파일이 존재하지 않음
            return False
    
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
            object_name = os.path.join(folder_path, uploaded_file.name)  # 예: 'working/user1/image.jpg'
        
            # 파일 업로드
            file_data = uploaded_file.getvalue()
            self.client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(file_data),
                length=len(file_data),
                content_type=uploaded_file.type
            )
            return True
        except S3Error as err:
            st.error(f"MinIO 업로드 에러: {err}")
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