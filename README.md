# Easy.Label 개발환경 설정 가이드

이 문서는 로컬 개발 환경에서 PostgreSQL 및 MinIO 서버를 설치하고 실행하는 방법과 Python 패키지를 설치하는 방법을 안내합니다.

---
## 🐘 PostgreSQL 설치 및 실행 (macOS 기준)

### 1. 설치

```bash
brew install postgresql
```

### 2. 서버 시작 (백그라운드 실행)

```bash
brew services start postgresql

# 서버 종료 시
brew services stop postgresql
```

### 3. 기본 사용자 비밀번호 설정

```bash
psql postgres
\password
```

### 4. 외부 접속 허용 (DBeaver 등에서 연결 시 필요)

#### `postgresql.conf` 수정

```bash
# .conf 경로는 brew info postgresq로 확인
nano /opt/homebrew/var/postgresql@16/postgresql.conf

# 주석 해제 후 값 변경
listen_addresses = '*'
```

#### `pg_hba.conf` 수정

```bash
nano /opt/homebrew/var/postgresql@16/pg_hba.conf

# 맨 아래에 추가
host    all             all             0.0.0.0/0               md5
```

#### 서버 재시작

```bash
brew services restart postgresql
```

### 5. DBeaver
#### DBeaver 설치
```bash
brew install --cask dbeaver-community
```

#### 초기 테이블 생성
```bash
# 이미지 메타데이터 테이블 생성
CREATE TABLE metadata (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    project_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL,
    width INT NOT NULL,
    height INT NOT NULL,
    created_by TEXT NOT NULL,  
    created_at TIMESTAMP NOT NULL,
    assigned_by TEXT,
    last_modified_by TEXT NOT null,
    last_modified_at TIMESTAMP NOT NULL
);

# 이미지 어노테이션 테이블 생성
CREATE TABLE annotations (
    id SERIAL PRIMARY KEY,
    info_id INT NOT NULL REFERENCES metadata(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    bbox JSONB NOT NULL  
);
```

---

## 📦 MinIO 서버 설치 및 실행 (macOS 기준)

### 1. MinIO 서버 설치

```bash
brew install minio/stable/minio
```
 
### 2. MinIO 클라이언트(mcli) 설치 (선택)

```bash
brew install minio/stable/mc
```

### 3. 환경 변수 설정 및 실행
```bash
export MINIO_ROOT_USER=minioadmin # 계정명 예시
export MINIO_ROOT_PASSWORD=minioadmin # 계정 비밀번호 예시

# 1) 실행
minio server ~/minio # 경로 예시) minio

# 2) 백그라운드 실행 
nohup minio server --console-address ":9001" ~/minio > ~/minio.log 2>&1 & 
```

- Web UI: [http://localhost:9001](http://localhost:9001)
- S3 API: [http://localhost:9000](http://localhost:9000)

### 4. 실행 확인 및 종료
```bash
# 실행 확인
ps aux | grep minio

# 종료
kill [PID]
```

## 📦 필수 패키지 설치

### 1. Python 패키지 설치

```bash
pip install -r requirements.txt
```

---

---

## ✅ 정리

| 항목               | 명령어/주소                                            |
| ---------------- | ------------------------------------------------- |
| PostgreSQL 서버 시작 | `brew services start postgresql`                  |
| MinIO 서버 실행      | `nohup minio server ~/minio > ~/minio.log 2>&1 &` |
| MinIO Web UI     | [http://localhost:9001](http://localhost:9001)    |
| MinIO Access Key | `minioadmin`                                      |
| MinIO Secret Key | `minioadmin123`                                   |

---

필요에 따라 `.env` 파일로 환경 변수를 따로 분리해서 관리하셔도 좋습니다!

