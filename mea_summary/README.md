# Spontaneous Activity Metrics Visualization

이 프로젝트는 spontaneous activity 데이터를 시각화하여 differentiation day에 따른 메트릭 변화를 분석합니다.

## 기능

### 1. **Daily Analysis** (일별 분석)
- DIFF_DAY별로 메트릭 변화 추적
- 개별 well 데이터 포인트 표시
- 일별 평균 및 표준 오차(SE) 계산

### 2. **Weekly Analysis** (주간 분석)
- DIFF_DAY를 주(week) 단위로 그룹화
- 주별 평균 및 통계 계산
- 장기 트렌드 파악에 유용

## 파일 구조

```
summary/
├── visualize_metrics.py              # 일별 분석 메인 모듈
├── visualize_metrics_weekly.py       # 주간 분석 메인 모듈
├── run_visualization.py              # 일별 분석만 실행
├── run_weekly_visualization.py       # 주간 분석만 실행
├── run_all_analysis.py               # 일별 + 주간 분석 모두 실행
├── visualizations/                   # 일별 분석 결과 저장 폴더
└── weekly_visualizations/            # 주간 분석 결과 저장 폴더
```

## 사용 방법

### 필수 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 실행 옵션

#### 1. 일별 분석만 실행
```bash
python run_visualization.py
```
- 결과: `visualizations/` 폴더에 저장

#### 2. 주간 분석만 실행
```bash
python run_weekly_visualization.py
```
- 결과: `weekly_visualizations/` 폴더에 저장

#### 3. 일별 + 주간 분석 모두 실행 (권장)
```bash
python run_all_analysis.py
```
- 결과: 두 폴더에 모두 저장

## 출력 결과

### Daily Analysis 출력물
```
visualizations/
├── firing_rate.png
├── burst_characteristics.png
├── inter-burst_interval.png
├── isi_(inter-spike_interval).png
├── network_activity.png
├── synchrony_&_correlation.png
├── network_burst.png
├── summary_heatmap.png
└── summary_statistics.csv
```

### Weekly Analysis 출력물
```
weekly_visualizations/
├── firing_rate_weekly.png
├── burst_characteristics_weekly.png
├── inter-burst_interval_weekly.png
├── isi_(inter-spike_interval)_weekly.png
├── network_activity_weekly.png
├── synchrony_&_correlation_weekly.png
├── network_burst_weekly.png
├── weekly_heatmap.png
└── weekly_summary_statistics.csv
```

## 메트릭 카테고리

1. **Firing Rate**: 발화 빈도 관련 지표
2. **Burst Characteristics**: 버스트 특성 (지속시간, 빈도, 비율 등)
3. **Inter-Burst Interval**: 버스트 간 간격
4. **ISI (Inter-Spike Interval)**: 스파이크 간 간격
5. **Network Activity**: 네트워크 활성도 (전극 수, 버스트 수 등)
6. **Synchrony & Correlation**: 동기화 및 상관관계 지표
7. **Network Burst**: 네트워크 버스트 관련 지표

## 주간 분석 설정 변경

주간 분석의 주(week) 크기를 변경하려면:

```python
# run_weekly_visualization.py 또는 run_all_analysis.py 수정
visualizer = WeeklyMetricsVisualizer(data_dir='.', week_size=7)  # 7일 -> 원하는 값으로 변경
```

예시:
- `week_size=7`: 7일 단위 (기본값)
- `week_size=10`: 10일 단위
- `week_size=14`: 2주 단위

## 데이터 요구사항

- CSV 파일 이름: `*spontaneous_activity.csv` 패턴
- 필수 컬럼:
  - `DIFF_DAY`: Differentiation day
  - `Metric`: 메트릭 이름
  - `Mean`: 평균 값

## 주의사항

- 새로운 summary 파일이 추가되면 자동으로 로드됩니다
- CSV 파일은 현재 디렉토리(`.`)에 있어야 합니다
- 그래프는 300 DPI로 저장됩니다

## 문제 해결

**Q: "No CSV files found in the directory" 에러가 발생합니다**
- A: 현재 디렉토리에 `*spontaneous_activity.csv` 파일이 있는지 확인하세요

**Q: 특정 메트릭이 표시되지 않습니다**
- A: CSV 파일에 해당 메트릭 데이터가 있는지 확인하세요

**Q: 주간 분석에서 Week 수가 이상합니다**
- A: `week_size` 설정과 DIFF_DAY 범위를 확인하세요
