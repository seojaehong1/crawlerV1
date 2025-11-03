# 다나와 크롤러 페이징 개선

## 현재 구현된 기능

### 크롤링 기본 기능
- Playwright로 브라우저 자동화
- 카테고리 페이지에서 제품 링크 수집
- 각 제품 상세 페이지 방문 및 스펙 추출
- CSV 파일로 저장 (상품명, URL, 상세정보)

### 안티-디텍션
- User-Agent 설정 (Chrome)
- 한국 locale/timezone 설정
- 랜덤 지연 (500~1000ms)
- 천천히 스크롤 (6단계, 800px씩)
- 네트워크 idle 대기

### HTML 파싱
- DL/DT/DD 구조
- TABLE/TR/TH/TD 구조
- DIV .key/.value 클래스 구조
- 여러 선택자 fallback 방식
- 불필요한 텍스트 제거 (인증번호 확인, 괄호 내용 등)

## 문제점

### 페이징 처리 실패

현재 코드의 `paginate_category` 함수는 URL 파라미터 변경 방식을 사용:

```python
# 현재 방식
next_url = f"{current_url}&page={page_num}"
page.goto(next_url)
```

하지만 다나와는 JavaScript 기반 SPA 구조:
- URL에 `page=3`을 넣어도 1페이지만 표시됨
- 실제로는 `movePage(N)` JavaScript 함수로 페이지 이동
- 페이지 버튼 클릭으로만 정상 작동

### 페이징 구조

```html
<div class="number_wrap">
  <a class="num now_on">1</a>  <!-- 현재 페이지 -->
  <a class="num" onclick="movePage(2)">2</a>
  <a class="num" onclick="movePage(3)">3</a>
  ...
  <a class="num" onclick="movePage(10)">10</a>
</div>
<a class="edge_nav nav_next" onclick="movePage(11)">다음 페이지</a>
```

페이징 규칙:
- 1~10페이지 버튼이 한 그룹으로 표시
- 11페이지부터는 > 버튼 클릭해야 11~20 그룹 표시
- 21페이지부터는 > 버튼 2번 클릭해야 21~30 그룹 표시


