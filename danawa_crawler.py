import argparse
import csv
import random
import re
import time
from typing import Dict, List, Set, Optional

import pandas as pd
from playwright.sync_api import Playwright, sync_playwright, Browser, Page, BrowserContext


def wait_for_network_idle(page: Page, timeout_ms: int = 3000) -> None:
    start = time.time()
    page.wait_for_load_state("domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass
    finally:
        _ = start


def open_new_context(playwright: Playwright, headless: bool) -> BrowserContext:
    chromium = playwright.chromium
    browser = chromium.launch(headless=headless)
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    context = browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1366, "height": 800},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        device_scale_factor=1.0,
        has_touch=False,
    )
    return context


def human_delay(base_delay_ms: int = 500) -> None:
    jitter = random.randint(0, base_delay_ms)
    time.sleep((base_delay_ms + jitter) / 1000.0)


def slow_scroll(page: Page, steps: int = 6, step_px: int = 800, base_delay_ms: int = 300) -> None:
    for _ in range(steps):
        # Pass value into the page context properly
        page.evaluate("step => window.scrollBy(0, step)", step_px)
        human_delay(base_delay_ms)


def extract_specs_from_detail(page: Page) -> Dict[str, str]:
    specs: Dict[str, str] = {}

    # 더 많은 선택자 후보 추가
    candidates = [
        "section#productOptionArea",
        "div#productOptionArea",
        "div.spec_area",
        "div.spec_list",
        "div#danawa_detail_content",
        "table.spec_table",
        "div.product_spec",
        "div.prod_spec_cont",
        "div.spec_info",
        "div.product_detail",
    ]

    container = None
    for selector in candidates:
        if page.locator(selector).count() > 0:
            container = page.locator(selector).first
            break
    
    if container is None:
        # 상세정보 영역을 더 넓게 찾기
        detail_selectors = [
            "div[class*='spec']",
            "div[class*='detail']",
            "table[class*='spec']",
            "section[class*='spec']",
        ]
        for selector in detail_selectors:
            if page.locator(selector).count() > 0:
                container = page.locator(selector).first
                break
    
    if container is None:
        container = page.locator("body")

    # dl/dt/dd 패턴 처리
    dl_groups = container.locator("dl").all()
    for dl in dl_groups:
        dts = dl.locator("dt").all()
        dds = dl.locator("dd").all()
        for i in range(min(len(dts), len(dds))):
            try:
                key = dts[i].inner_text().strip()
                value = dds[i].inner_text().strip()
                if key and key not in specs:
                    specs[key] = value
            except Exception:
                continue

    # 표 형태 (tr/th/td) 처리
    table_rows = container.locator("tr").all()
    for tr in table_rows:
        try:
            th = tr.locator("th").first
            td = tr.locator("td").first
            if th.count() > 0 and td.count() > 0:
                key = th.inner_text().strip()
                value = td.inner_text().strip()
                # "인증" 같은 빈 헤더는 스킵하되, 실제 값이 있으면 저장
                # 빈 key는 이전 key의 하위 항목일 수 있으므로 처리
                if key:
                    # 인증번호 확인 버튼 등 UI 요소 제거
                    value = value.split("인증번호 확인")[0].strip()
                    if value and key not in specs:
                        specs[key] = value
                elif not key and value:
                    # 빈 key인 경우 이전 컬럼과 연결될 수 있음
                    # 하지만 일반적으로는 스킵
                    pass
        except Exception:
            continue

    # div.key / div.value 패턴
    kv_rows = container.locator("div:has(> .key), li:has(> .key), div:has(> .spec_key)").all()
    for row in kv_rows:
        try:
            key_elem = row.locator(".key, .spec_key").first
            value_elem = row.locator(".value, .spec_value").first
            if key_elem.count() > 0 and value_elem.count() > 0:
                key = key_elem.inner_text().strip()
                value = value_elem.inner_text().strip()
                if key and key not in specs:
                    specs[key] = value
        except Exception:
            continue

    # 더 넓은 범위에서 표 형태 찾기 (container 외부의 표도 검색)
    all_tables = page.locator("table").all()
    for table in all_tables:
        rows = table.locator("tr").all()
        for tr in rows:
            try:
                ths = tr.locator("th").all()
                tds = tr.locator("td").all()
                if len(ths) > 0 and len(tds) > 0:
                    key = ths[0].inner_text().strip()
                    value = tds[0].inner_text().strip()
                    # "인증번호 확인" 같은 버튼 텍스트 제거
                    value = value.split("인증번호 확인")[0].strip()
                    value = value.split("바로가기")[0].strip()
                    # 괄호 안의 링크 텍스트 제거
                    value = re.sub(r'\s*\([^)]*바로가기[^)]*\)', '', value)
                    if key and key not in specs and value:
                        specs[key] = value
            except Exception:
                continue

    # 추가로 상세정보가 있을 수 있는 영역 검색
    detail_areas = page.locator("div.prod_detail_area, div.product_info_detail, div.spec_detail").all()
    for area in detail_areas:
        rows = area.locator("tr").all()
        for tr in rows:
            try:
                ths = tr.locator("th").all()
                tds = tr.locator("td").all()
                if len(ths) > 0 and len(tds) > 0:
                    key = ths[0].inner_text().strip()
                    value = tds[0].inner_text().strip()
                    value = value.split("인증번호 확인")[0].strip()
                    value = value.split("바로가기")[0].strip()
                    value = re.sub(r'\s*\([^)]*바로가기[^)]*\)', '', value)
                    if key and key not in specs and value:
                        specs[key] = value
            except Exception:
                continue

    return specs


def click_detail_tab_if_present(page: Page) -> None:
    labels = ["상세정보", "상세 사양", "상세스펙", "상세 스펙", "스펙", "사양"]
    for label in labels:
        button = page.get_by_role("button", name=label)
        if button.count() > 0:
            try:
                button.first.click(timeout=2000)
                wait_for_network_idle(page)
                return
            except Exception:
                pass
        link = page.get_by_role("link", name=label)
        if link.count() > 0:
            try:
                link.first.click(timeout=2000)
                wait_for_network_idle(page)
                return
            except Exception:
                pass

    for label in labels:
        locator = page.locator(f"text={label}")
        if locator.count() > 0:
            try:
                locator.first.click(timeout=2000)
                wait_for_network_idle(page)
                return
            except Exception:
                pass


def collect_product_links_from_category(page: Page, max_per_page: Optional[int]) -> List[str]:
    # Prefer product title anchors inside list cards; avoid option/price links
    selectors = [
        "li.prod_item div.prod_info a.prod_link",
        "li.prod_item .prod_name a",
        "div.prod_info a.prod_link",
        "a[href*='/product/']",
        "a[href*='product/view.html']",
    ]
    links: List[str] = []
    seen: Set[str] = set()
    for selector in selectors:
        # ensure list is rendered and visible before grabbing
        if page.locator(selector).count() == 0:
            continue
        for a in page.locator(selector).all():
            try:
                href = a.get_attribute("href")
                text = (a.inner_text() or "").strip()
            except Exception:
                continue
            if not href:
                continue
            if href.startswith("javascript:"):
                continue
            # danawa product details live under prod.danawa.com/product/... or similar
            if "danawa" not in href and not href.startswith("/"):
                continue
            if href in seen:
                continue
            # Skip obvious non-title links like 가격비교/옵션 등
            lowered = text.lower()
            if any(x in lowered for x in ["가격", "비교", "옵션", "구성"]):
                continue
            seen.add(href)
            links.append(href)
            if max_per_page and len(links) >= max_per_page:
                return links
    return links


def paginate_category(page: Page, current_url: str, page_num: int) -> bool:
    # URL 기반 페이지네이션 시도
    try:
        if "page=" in current_url:
            # 기존 page 파라미터를 다음 페이지로 변경
            next_url = re.sub(r'page=\d+', f'page={page_num}', current_url)
            if next_url != current_url:
                page.goto(next_url)
                wait_for_network_idle(page)
                return True
        else:
            # page 파라미터가 없으면 추가
            separator = "&" if "?" in current_url else "?"
            next_url = f"{current_url}{separator}page={page_num}"
            page.goto(next_url)
            wait_for_network_idle(page)
            return True
    except Exception:
        pass
    
    # 버튼/링크 기반 페이지네이션 시도
    next_labels = ["다음", ">", "다음페이지", "Next"]
    for label in next_labels:
        control = page.get_by_role("link", name=label)
        if control.count() > 0:
            try:
                control.first.click()
                wait_for_network_idle(page)
                return True
            except Exception:
                pass
    
    # 다양한 선택자로 다음 페이지 버튼 찾기
    pager_selectors = [
        "a.btn_next",
        "a.next",
        "button.next",
        "a[class*='next']",
        "button[class*='next']",
        ".pager a:has-text('다음')",
        ".pagination a:has-text('다음')",
    ]
    for selector in pager_selectors:
        pager = page.locator(selector)
        if pager.count() > 0:
            try:
                pager.first.click()
                wait_for_network_idle(page)
                return True
            except Exception:
                pass
    
    return False


def crawl_category(
    category_url: str,
    output_csv: str,
    max_pages: int,
    max_items_per_page: Optional[int],
    headless: bool,
    max_total_items: Optional[int] = None,
    base_delay_ms: int = 500,
    long_format: bool = False,
) -> None:
    with sync_playwright() as p:
        context = open_new_context(p, headless=headless)
        page = context.new_page()
        page.set_default_timeout(10000)

        page.goto(category_url)
        wait_for_network_idle(page)
        slow_scroll(page)
        human_delay(base_delay_ms)

        all_rows: List[Dict[str, str]] = []
        all_keys: Set[str] = set()

        for page_index in range(max_pages):
            try:
                print(f"페이지 {page_index + 1}/{max_pages} 크롤링 중...")
                product_links = collect_product_links_from_category(page, max_items_per_page)
                print(f"  - {len(product_links)}개 링크 발견")
                
                if not product_links:
                    print(f"  - 페이지 {page_index + 1}에 제품이 없습니다. 종료합니다.")
                    break
                
                for idx, link in enumerate(product_links, 1):
                    if max_total_items and len(all_rows) >= max_total_items:
                        print(f"최대 아이템 수({max_total_items})에 도달했습니다.")
                        break
                    
                    try:
                        print(f"  [{len(all_rows) + 1}] {link[:80]}... 크롤링 중...")
                        detail_page = context.new_page()
                        detail_page.set_default_timeout(15000)  # 타임아웃 증가
                        try:
                            detail_page.goto(link, wait_until="domcontentloaded", timeout=15000)
                            wait_for_network_idle(detail_page)
                            slow_scroll(detail_page, steps=4, step_px=900, base_delay_ms=base_delay_ms)
                            click_detail_tab_if_present(detail_page)
                            specs = extract_specs_from_detail(detail_page)
                            title = ""
                            try:
                                title = detail_page.title() or ""
                            except Exception as e:
                                print(f"    경고: 제목 추출 실패 - {e}")
                                pass
                            
                            # 스펙 정보를 하나의 문자열로 합치기
                            spec_parts = []
                            certification_items = []
                            
                            for key, value in specs.items():
                                if not value or not value.strip():
                                    continue
                                
                                # 값 정리
                                clean_value = value.strip()
                                # 인증번호 확인 버튼 텍스트 제거
                                clean_value = clean_value.split("인증번호 확인")[0].strip()
                                # 괄호와 그 안의 모든 내용 제거 (닫힌/안 닫힌 괄호 모두 처리)
                                clean_value = re.sub(r'\s*\([^)]*\)', '', clean_value)  # 닫힌 괄호
                                clean_value = re.sub(r'\s*\([^)]*$', '', clean_value)  # 닫히지 않은 괄호 (끝까지)
                                clean_value = re.sub(r'\s*\([^)]*', '', clean_value)    # 열린 괄호부터 끝까지
                                # "제조사 웹사이트" 같은 텍스트 직접 제거
                                clean_value = clean_value.replace("제조사 웹사이트", "").strip()
                                clean_value = clean_value.replace("웹사이트", "").strip()
                                # "바로가기" 관련 텍스트 제거
                                clean_value = clean_value.split("바로가기")[0].strip()
                                # 불필요한 공백 정리
                                clean_value = re.sub(r'\s+', ' ', clean_value).strip()
                                
                                if not clean_value:
                                    continue
                                
                                # 의미없는 값 체크
                                meaningless_values = [
                                    "상세설명 / 판매 사이트 문의",
                                    "상세설명",
                                    "판매 사이트 문의",
                                    "인증번호 확인"
                                ]
                                is_meaningless = clean_value in meaningless_values or any(mv in clean_value for mv in ["상세설명 / 판매 사이트 문의"])
                                
                                # 체크 표시(○)인 경우 키 이름을 값으로 사용
                                check_marks = ["○", "O", "o", "●"]
                                if clean_value in check_marks:
                                    # HACCP인증은 인증 목록에 추가
                                    if "HACCP" in key or key == "HACCP인증":
                                        if key not in certification_items:
                                            certification_items.append(key)
                                    else:
                                        # 키 이름이 실제 값이 됨
                                        # 키 이름을 카테고리명으로 매핑
                                        category_mapping = {
                                            "레토르트이유식": "품목",
                                            "파우치": "포장용기",
                                            "6개월~": "최소연령",
                                            "상온": "보관방식",
                                        }
                                        # 키 이름을 카테고리로 변환 (매핑에 없으면 키 이름 그대로)
                                        category = category_mapping.get(key, key)
                                        spec_parts.append(f"{category}:{key}")
                                # 인증 관련 항목들을 따로 모으기
                                elif "인증" in key:
                                    # 인증 키 이름 자체를 인증 목록에 추가 (값이 의미없어도)
                                    cert_name = key  # "적합성평가인증", "안전확인인증" 등
                                    if cert_name not in certification_items:
                                        certification_items.append(cert_name)
                                else:
                                    # 일반 스펙 항목 - 의미없는 값은 스킵
                                    if not is_meaningless:
                                        spec_parts.append(f"{key}:{clean_value}")
                            
                            # 인증 항목이 있으면 합쳐서 추가
                            if certification_items:
                                cert_str = ",".join(certification_items)
                                spec_parts.append(f"인증:{cert_str}")
                            
                            detail_info = "/".join(spec_parts)
                            row = {"상품명": title, "URL": link, "상세정보": detail_info}
                            all_rows.append(row)
                            print(f"    완료! (총 {len(all_rows)}개 수집)")
                        except Exception as e:
                            print(f"    오류: {link} 크롤링 실패 - {e}")
                            # 실패한 경우에도 빈 행 추가는 하지 않음
                        finally:
                            try:
                                detail_page.close()
                            except:
                                pass
                        
                        human_delay(base_delay_ms)
                    except Exception as e:
                        print(f"  오류: 페이지 생성 실패 - {e}")
                        continue
                
                if max_total_items and len(all_rows) >= max_total_items:
                    print(f"최대 아이템 수({max_total_items})에 도달했습니다.")
                    break
                    
                if page_index < max_pages - 1:
                    print(f"  다음 페이지로 이동 시도...")
                    next_page_num = page_index + 2  # 다음 페이지 번호 (1부터 시작)
                    moved = paginate_category(page, category_url, next_page_num)
                    if not moved:
                        print(f"  다음 페이지로 이동할 수 없습니다. 종료합니다.")
                        break
                    slow_scroll(page)
                    human_delay(base_delay_ms)
            except Exception as e:
                print(f"페이지 {page_index + 1} 처리 중 오류 발생: {e}")
                # 계속 진행
                if page_index < max_pages - 1:
                    try:
                        next_page_num = page_index + 2
                        paginate_category(page, category_url, next_page_num)
                    except:
                        pass

        # 모든 상세 정보를 하나의 컬럼에 저장
        fieldnames = ["상품명", "URL", "상세정보"]
        with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})

        context.browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Danawa category crawler -> CSV")
    parser.add_argument("--category-url", required=True, help="Danawa category URL (list view)")
    parser.add_argument("--output", default="danawa_output.csv", help="Output CSV filepath")
    parser.add_argument("--pages", type=int, default=1, help="Max pages to crawl")
    parser.add_argument("--items-per-page", type=int, default=0, help="Max items per page (0 for all)")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--max-total-items", type=int, default=0, help="Stop after N items across pages (0=unlimited)")
    parser.add_argument("--delay-ms", type=int, default=600, help="Base human-like delay in ms")
    parser.add_argument("--long-format", action="store_true", help="Export as rows: 상품명,URL,key,value")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    crawl_category(
        category_url=args.category_url,
        output_csv=args.output,
        max_pages=args.pages,
        max_items_per_page=(args.items_per_page or None),
        headless=args.headless,
        max_total_items=(args.max_total_items or None),
        base_delay_ms=args.delay_ms,
        long_format=args.long_format,
    )


if __name__ == "__main__":
    main()


