## Danawa Category Crawler (Playwright, Python)

### 특징
- 카테고리 목록 페이지에서 상품 링크 수집
- 각 상품 상세 페이지로 이동 → "상세정보/상세스펙" 탭 클릭 시도 → 스펙 추출
- 상품마다 다른 스펙 구조를 Key-Value 형태로 통합하여 CSV로 내보냄

### 준비 (Windows PowerShell)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install
```

### 실행 예시
```bash
python danawa_crawler.py \
  --category-url "https://search.danawa.com/dsearch.php?query=노트북" \
  --output danawa_output.csv \
  --pages 3 \
  --items-per-page 20 \
  --headless
```

옵션 설명:
- `--category-url`: 다나와 카테고리/검색 URL (목록 페이지)
- `--output`: 결과 CSV 파일 경로 (기본: danawa_output.csv)
- `--pages`: 최대 크롤링 페이지 수
- `--items-per-page`: 페이지당 최대 상품 수 (0이면 제한 없음)
- `--headless`: 헤드리스 모드 실행 플래그

### 결과
- CSV 헤더는 `상품명`, `URL` + 수집된 모든 스펙 키의 합집합으로 구성됩니다.

### 참고
- 사이트 구조가 바뀌면 선택자 조정이 필요할 수 있습니다.
- 네트워크 상태에 따라 대기 시간이 필요할 수 있어 기본적으로 `networkidle` 대기를 포함합니다.


