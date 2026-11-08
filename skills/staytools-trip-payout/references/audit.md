# 숙소 점검 — 영역별 절차 · 합격 기준

"점검해줘", "현황 봐줘", "뭐가 부족해"에 쓴다. 입금가 계산(`pricing.md`)과 별개로 노출 순위·요금 경쟁력·정보 점수·리뷰·프로그램을 훑는다.
결과는 `property.json` 의 `audit[]` 에 한 줄씩 남기고 콘솔 「점검 결과」 카드로 낸다.

**조회만 한다.** 참여·활성화·비활성화·수정·삭제 버튼은 누르지 않는다. 기준값(고지 한도, 혜택 금액, 점수 단계)은 숙소·시기마다 다르니 **화면 문구를 그대로 옮긴다.**

## 0. 이동과 읽기

주소 앞부분은 `https://ebooking.ctrip.com` 이다. 주소로 바로 이동해도 세션이 유지된다(시점값, 다를 수 있음).

| 영역 | 경로 | 메뉴 |
|---|---|---|
| Property Health 대시보드 | `/ebkgrowth/datacenter/oversea/psi` | 데이터 분석 |
| 요금 모니터링 | `/ebkgrowth/datacenter/oversea/price/compare` | 데이터 분석 |
| 경쟁권 | `/ebkgrowth/datacenter/oversea/competitive/circle` | 데이터 분석 |
| 실적 인사이트 | `/ebkgrowth/businessSuggestion` | 비즈니스 기회 |
| Preferred Partner | `/ebkgrowth/preferredpartner` | 비즈니스 기회 |
| TripPlus | `/promotion/createTplus` | 비즈니스 기회 |
| CoinPlus | `/promotion/coinplus` | 비즈니스 기회 |
| 취소 보호 | `/promotion/cancellationProtection` | 비즈니스 기회 |
| Smart Offer | `/promotion/SmartOffer` | 비즈니스 기회 |
| 리뷰 분석 | `/comment/analysis` | 고객 리뷰 |
| 호텔 개요(정보 점수) | `/hotelinfo/ebooking/informationhome` | 호텔 정보 |
| 객실 정보 | `/hotelinfo/ebooking/roominfo/roomlist` | 호텔 정보 |
| 호텔 정책 | `/hotelinfo/ebooking/hotelpolicy` | 호텔 정보 |

- 왼쪽 메뉴 하위 항목은 실제 마우스로 펼쳐야 링크가 생긴다. **아래 항목부터 펼치면** 위 항목 좌표가 밀리지 않는다.
- 읽기는 `__ebText()` 로 한다. 왼쪽 메뉴·머리글 글자를 빼고 이메일·긴 번호·전화번호를 가린다.
- 링크를 모을 때는 주소의 `?` 뒤를 잘라 낸다. 붙은 값이 세션 정보로 막힌다.
- 화면이 늦게 뜬다. 8초 기다린 뒤 읽고, 글자가 짧으면 한 번 더 기다린다.
- 리뷰 분석의 항목별 점수처럼 **그래프 안의 숫자는 글자로 안 읽힌다.** 화면 캡처로 읽는다.
- **메인·예약 관리·메시지·예약 리뷰 목록 화면은 본문 통째 읽기 금지.** 투숙객 이름이 있다. 답글률은 리뷰 분석 화면에서 읽는다.

## 1. Property Health 대시보드 — `psi`

지역 순위(「N곳 중 M위」), 경쟁권 순위, 그리고 핵심 지표를 「귀하의 숙소 / 경쟁권 평균」 그대로 옮긴다.

| 지표 | 볼 것 |
|---|---|
| 총 전환율 | 경쟁권 평균보다 낮으면 주의 |
| 정보 점수 | 3장으로 이어진다 |
| 고객 리뷰 점수 | 4장으로 이어진다 |
| 평균 일일 요금(ADR) | 경쟁권 중 ADR이 더 높은 숙소 비율 |
| **가격 매력도** | 가격 경쟁력이 없는 요금 수. **0이 아니면 2장을 먼저 본다** |
| 객실 재고 | 향후 30일 중 예약 가능한 객실이 없는 일수 |
| 위반 사항 | 지난 90일 건수 |

합격: 가격 매력도 0, 위반 사항 0, 재고 없는 날 0.

## 2. 요금 경쟁력 — `price/compare` · Preferred Partner 「오퍼 매력도」

요금 모니터링 표에서 숙박 날짜·지역·기기·플랫폼별로 **다른 플랫폼 요금과 트립 요금**을 옮기고, 트립이 몇 % 비싼지 적는다.

- 다른 플랫폼 요금에는 **재판매(협력업체) 요금이 섞일 수 있다.** 우리 요금을 내리기 전에 그 플랫폼 고객 페이지에서 우리 요금인지 가른다(`portal-map.md` 재판매 구분과 같은 방식).
- 표 아래 「참고용」 안내대로 화면 값은 확정값이 아니다. 판단 근거로 쓰되 원문을 같이 적는다.
- Preferred Partner의 「오퍼 매력도」 개선 고지 수(예: 9/3)는 **분모가 한도**다. 한도를 넘으면 「평가 패스」로 보여도 트래픽 혜택에 영향이 있다는 안내가 물음표에 있다. 위험으로 적는다.
- 요금을 맞추는 판단은 `payout.py check` 로 입금가를 먼저 계산한 뒤에 한다.

합격: 가격 매력도 0, 오퍼 매력도 고지가 한도 이하.

## 3. 정보 점수 — `informationhome` · `roomlist` · `hotelpolicy`

정보 점수(%)와 「대기 중인 작업」 문구를 옮긴다. 객실 정보에서 객실 유형 수, 객실별 **수량·객실 층·인원 「확인 불가」** 같은 빈칸을 센다. 호텔 정책의 「미션」 문구(예: 침대 추가 정보 미등록 객실 수)도 적는다.

합격: 대기 중인 작업 0, 객실 정보 빈칸 없음.

## 4. 리뷰 — `comment/analysis`

리뷰 분석 「주요 정보」(최근 3년 기준)에서 항목별 점수(위치·시설·서비스·청결도)와 경쟁권 점수, 전체·부정 리뷰 수, 답글률을 적는다. 그래프 숫자라 캡처로 읽는다.

합격: 모든 항목이 경쟁권 이상, 답글률 100%.

## 5. 프로그램 — Preferred Partner · TripPlus · CoinPlus · 취소 보호 · Smart Offer

| 프로그램 | 볼 것 |
|---|---|
| Preferred Partner | 기준 4개(정보 점수·수수료·오퍼 매력도·리뷰 점수)의 판정과 고지 수, 혜택 사용 현황 |
| TripPlus | 활성 여부, 등급별 할인 %, 대상 요금제. **할인은 지급액을 깎는다** — `pricing.md` 의 Σ 에 들어가는지 본다 |
| CoinPlus | 활성 여부와 할인율 |
| 취소 보호 · Smart Offer | 소개 화면만 나오면 미참여다. 참여 제안은 입금가와 같이 판단한다 |

## 6. 실적 인사이트 — `businessSuggestion`

제안 제목과 한 줄 내용을 옮긴다. **전부 실행하라는 뜻이 아니다.** XPOS·국가 할인·모바일 요금 같은 할인 제안은 `payout.py check` 로 입금가와 목표를 먼저 계산한다.

## 기록 형식 — `audit[]`

```json
{ "area": "요금 경쟁력", "item": "가격 매력도", "value": "경쟁력 없는 요금 12개", "status": "bad",
  "rule": "0개", "action": "요금 모니터링에서 더 싼 플랫폼과 재판매 여부 확인", "source": "Property Health 대시보드" }
```

`status`: `ok` 합격 · `warn` 주의 · `bad` 위험 · `unknown` 못 읽음. 위 값은 형식 예시다.

## 아고다 스킬과 같은 산출물 — 기록 칸

점검이 끝나면 `audit[]` 말고도 아래 칸을 채운다. 콘솔이 「현재 설정 · 발견 사항 · 프로그램 · 콘텐츠 · 요금제 · 노출가 실측」 카드로 낸다. 칸 이름은 아고다 스킬과 같다.

| 칸 | 어디서 읽나 | 무엇을 적나 |
|---|---|---|
| `findings` | 아래 영역에서 나온 결론 | 심각도(high·med·info) · 근거 · 정정 |
| `programs` | TripPlus · CoinPlus · Preferred Partner · 판매당 비용 계정 | 설정 가능 범위와 현재 설정(할인 %, 등급, 잔액)을 나눠 적는다. 소개 화면만 뜨면 미등록 |
| `content.photos` | 사진 & 동영상 화면 | 분류별 장수 합계, 추천 사진 수, 0장인 분류 |
| `content.reviews` | 리뷰 분석 「주요 정보」 (캡처로 읽는다) | 항목별 점수와 경쟁권 점수(`compare`), 전체·부정 리뷰 수, 답글률 |
| `content.mapping` | Connectivity 설정 | 채널 매니저 연결 여부와 요금 책정 방법. 객실 정보의 객실 수와 대조 |
| `ratePlans` | 요금제 화면 | 요금제명 · 파생 규칙(예: Room Only 보다 10% 낮음) · 취소 정책 · 판매 상태 |
| `measurements` | 고객 페이지 (`__resale` 의 DIRECT 행만) | 날짜 3개 이상. 입력값은 그날 달력 판매가 × r, 화면값은 손님가. 다른 공급처(AGENT) 행은 넣지 않는다 |

- `findings[]` 는 결론이다. `{"title", "severity", "detail", "evidence", "revised"}`. **실측은 `evidence`, 판단은 `detail`** 에 나눠 적는다. 판정이 뒤집히면 `revised` 에 이전 판정과 정정 사유를 남긴다.
- `programs[]` 는 `{"name", "status", "range", "setting", "note", "verified"}`. 화면에서 못 읽은 범위는 `null` 이다. 일반 구조를 그 숙소 값처럼 적지 마라.
- `content` 는 `photos{total, lowRes, untagged, note}` · `reviews{score, count, unanswered, detail{}, compare{}, note}` · `mapping{mapped, total, unmapped, note}`. 숫자 칸에 글자를 넣지 않는다.
- `ratePlans[]` 는 `{"name", "id", "rooms", "base", "policy", "sold", "status"}`. 가격표(요금제 배수·요금)와 다른 것이다. `sold` 가 0이면 `--check` 가 알린다.
- `measurements[]` 는 `{"label", "condition", "input", "shown", "expected", "tolerance"}`. **날짜 3개 이상**을 재서 화면값 ÷ 입력값 비율이 0.001 안에서 맞으면 공식이 선형으로 확인된 것이다. 조회 조건(국가·기기·박수·인원·로그인)을 `condition` 에 적는다.
- `summary[]` 는 맨 위 요약 칸 `{"label", "value", "note"}` 이다. 수수료·계수처럼 그 숙소의 핵심 숫자를 넣는다. 적용 중 프로모션 수·발견 사항·점검 건수·하한은 자동으로 붙는다.
