# MEA Analysis Pipeline

Multi-Electrode Array (MEA) 데이터 분석을 위한 자동화 파이프라인

## 🎯 주요 기능

- ⚡ 원클릭 시각화 (`quick_visual.py`)
- 📊 전문가급 그래프 생성 (Nature/Cell/Science 스타일)
- 🔬 고급 분석 (연결성, 클러스터링, 공간 분석)
- 🎨 Publication-ready PDF 출력

## 🚀 빠른 시작

### 설치
```bash
pip install -r requirements.txt
```

### 실행
```python
from quick_visual import quick_visual

# 한 줄로 모든 시각화 생성
quick_visual(r"D:\MyProjects\#7-1")
```

**결과:** 3개의 핵심 플롯이 30초 안에 생성됩니다!

## 📊 생성되는 시각화

1. **DIV Timeline** - 분화 시기별 신경 활성도 변화
2. **Drug Comparison** - 약물 효과 직접 비교
3. **Integrated Heatmap** - 전체 조건 통합 히트맵

## 📁 프로젝트 구조

```
mea-analysis/
├── quick_visual.py                          # ⭐ 메인 실행 파일
├── mea_complete_analyzer_v35.py             # v3.5 통합 분석기
├── mea_auto_analyzer_v32.py                 # 자동 분석
├── mea_advanced_analytics_v33.py            # 고급 분석
├── mea_professional_visualizer_v34.py       # 전문가급 시각화
├── diagnose_data.py                         # 데이터 진단 도구
└── requirements.txt                         # 필요 패키지
```

## 🔬 완전한 분석 파이프라인

### 기본 분석
```python
from mea_complete_analyzer_v35 import CompleteAnalyzerV35

analyzer = CompleteAnalyzerV35(
    input_dir=r"D:\MyProjects\#7-1\output\processed",
    output_dir=r"D:\MyProjects\#7-1\analysis_v35"
)

analyzer.run(mode='full')  # 약 15분
```

### 모드 선택
- `'basic'` - 기본 분석만 (~5분)
- `'advanced'` - 기본 + 고급 분석 (~10분)
- `'professional'` - 기본 + 전문가급 스타일 (~7분)
- `'full'` - 모든 기능 (~15분) ⭐ 권장

## 📖 상세 가이드

- [빠른 시작 가이드](docs/QUICK_START.md)
- [전체 기능 가이드](docs/FULL_GUIDE.md)
- [문제 해결](docs/TROUBLESHOOTING.md)

## 🎓 논문 제출용

생성된 `*_professional.pdf` 파일들은 다음 저널에 바로 제출 가능:
- Nature, Cell, Science 시리즈
- Vector graphics (무한 확대 가능)
- Colorblind-safe 색상
- 통계 주석 포함

## 📦 필요 패키지

```
pandas>=1.5.0
numpy>=1.23.0
matplotlib>=3.6.0
seaborn>=0.12.0
scipy>=1.9.0
openpyxl>=3.0.0
```

## 🐛 문제 해결

### 데이터를 찾을 수 없어요
```python
from diagnose_data import diagnose_data
diagnose_data(r"D:\MyProjects\#7-1")
```

### "DIFF_DAY" 에러
→ v3.2 이상 사용 (옵션 컬럼으로 처리)

### Connectivity 에러
→ v3.3 최신 버전 사용 (스칼라 체크 추가)

## 📝 버전 히스토리

- **v3.5 (2024-11)** - Smart burst detection, 자동 적응
- **v3.4 (2024-11)** - Professional 스타일
- **v3.3 (2024-11)** - Advanced analytics
- **v3.2 (2024-11)** - 기본 파이프라인

## 👥 기여

Issues와 Pull Requests 환영합니다!

## 📄 라이선스

MIT License

## 📧 문의

버그 리포트나 기능 요청은 [Issues](../../issues)에 남겨주세요.

## 🙏 인용

이 코드를 사용하신 경우 다음과 같이 인용해주세요:

```
@software{mea_analysis_pipeline,
  title = {MEA Analysis Pipeline},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/yourusername/mea-analysis}
}
```
