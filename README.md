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

## 필요한 개선사항

### 1. paginate_category 함수 전면 수정
기존 URL 변경 방식을 완전히 제거하고 JavaScript 실행 방식으로 변경

### 2. 헬퍼 함수 추가

```python
def get_current_page_number(page: Page) -> int:
    # a.num.now_on 요소에서 현재 페이지 번호 추출
    pass

def get_visible_page_buttons(page: Page) -> List[int]:
    # 현재 화면에 보이는 페이지 버튼 번호들 반환
    # a.num 요소들의 텍스트 수집
    pass

def click_next_group_button(page: Page) -> bool:
    # a.edge_nav.nav_next 클릭
    # network idle 대기
    pass

def paginate_to_page(page: Page, target_page: int) -> bool:
    # 목표 페이지로 이동하는 메인 로직
    pass
```

### 3. 페이징 로직

목표: 15페이지로 이동하는 경우

```
1. 현재 페이지 확인 (get_current_page_number)
2. 보이는 버튼 확인 (get_visible_page_buttons) → [1,2,3...10]
3. 15가 안 보임 → > 버튼 클릭 (click_next_group_button)
4. 다시 확인 → [11,12,13...20]
5. 15 버튼 클릭
6. 성공 확인
```

계산식: `(target_page - 1) // 10` = > 버튼 클릭 횟수
- 15페이지: `(15-1)//10 = 1번`
- 25페이지: `(25-1)//10 = 2번`
- 5페이지: `(5-1)//10 = 0번` (클릭 불필요)

### 4. crawl_category 수정

```python
# 기존
if page_index < max_pages - 1:
    next_page_num = page_index + 2
    moved = paginate_category(page, category_url, next_page_num)

# 개선
if page_index < max_pages - 1:
    next_page_num = page_index + 2
    moved = paginate_to_page(page, next_page_num)
    if not moved:
        current = get_current_page_number(page)
        visible = get_visible_page_buttons(page)
        print(f"이동 실패 - 현재: {current}, 보이는 버튼: {visible}")
        break
```

### 5. 추가 개선

대기 시간 조정:
```python
# movePage 실행 후
wait_for_network_idle(page, 3000)

# 버튼 클릭 후
human_delay(500)
```

JavaScript 직접 실행:
```python
page.evaluate(f"movePage({page_num})")
```

에러 처리:
- 최대 3번 재시도
- 실패 시 상세 정보 출력
- 페이지 이동 검증: 제품 목록 변경 여부 확인

로깅 강화:
- 각 단계별 상세 로그
- 현재 페이지/목표 페이지 출력
- > 버튼 클릭 횟수 출력

## 구현 우선순위

- [ ] `get_current_page_number()` 구현
- [ ] `get_visible_page_buttons()` 구현  
- [ ] `click_next_group_button()` 구현
- [ ] `paginate_to_page()` 구현
- [ ] `crawl_category()` 수정
- [ ] 테스트 (2페이지, 15페이지, 25페이지 이동)

## 테스트 시나리오

같은 그룹 내 이동:
```bash
python crawler.py --category-url "https://prod.danawa.com/list/?cate=16249098" --pages 3
```

다른 그룹으로 이동:
```bash
python crawler.py --category-url "https://prod.danawa.com/list/?cate=16249098" --pages 15
```

여러 그룹 이동:
```bash
python crawler.py --category-url "https://prod.danawa.com/list/?cate=16249098" --pages 25
```

확인사항:
- [ ] 페이지 번호가 올바르게 변경되는가
- [ ] 제품 목록이 실제로 바뀌는가
- [ ] 에러 없이 완료되는가
- [ ] 로그가 명확하게 출력되는가
