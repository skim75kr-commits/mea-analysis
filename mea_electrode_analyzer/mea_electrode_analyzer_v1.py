"""
MEA Electrode-Level Analyzer v1.0
---------------------------------
- 24 wells × 16 electrodes (Axion Maestro 기준) 전극 레벨 분석
- 입력: electrode 전용 Excel (Metadata / Template / Well_Info)
- 출력:
    1) electrode_all_long.csv  : 전체 전극 × metric long-format
    2) electrode_selected_stats.csv : 필터 통과 전극 통계
    3) electrode_selected_long.csv  : 필터 통과 전극의 모든 metric

핵심 기능
- 전극 레벨 long-format 변환
- STIM 파일에서 metric 대부분이 채워진 전극만 사용
- BASE vs STIM에서 'Number of Spikes' 차이가 큰 전극만 선택
"""

from pathlib import Path
from dataclasses import dataclass
import re

import numpy as np
import pandas as pd


# =============================================================================
# 1. Metric 이름 표준화
# =============================================================================

def standardize_metric_name(name: str) -> str:
    """
    Axion에서 나온 metric 이름을 snake_case로 통일.
    (향후 분석 코드에서 쓰기 편하게 하기 위함)
    """
    mapping = {
        "Number of Spikes": "number_of_spikes",
        "Mean Firing Rate (Hz)": "mean_firing_rate_hz",
        "ISI Coefficient of Variation": "isi_cv",
        "Number of Bursts": "number_of_bursts",
        "Burst Duration - Avg (s)": "burst_duration_avg_s",
        "Burst Duration - Std (s)": "burst_duration_std_s",
        "Number of Spikes per Burst - Avg": "spikes_per_burst_avg",
        "Number of Spikes per Burst - Std": "spikes_per_burst_std",
        "Mean ISI within Burst - Avg": "mean_isi_within_burst_avg",
        "Mean ISI within Burst - Std": "mean_isi_within_burst_std",
        "Median ISI within Burst - Avg": "median_isi_within_burst_avg",
        "Median ISI within Burst - Std": "median_isi_within_burst_std",
        "Inter-Burst Interval - Avg (s)": "inter_burst_interval_avg_s",
        "Inter-Burst Interval - Std (s)": "inter_burst_interval_std_s",
        "Burst Frequency (Hz)": "burst_frequency_hz",
        "IBI Coefficient of Variation": "ibi_cv",
        "Normalized Duration IQR": "normalized_duration_iqr",
        "Burst Percentage": "burst_percentage",
    }
    if name in mapping:
        return mapping[name]

    # fallback: generic snake_case 변환
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s


# =============================================================================
# 2. 전극 ID 파싱 (A1_11 → (A1, 11))
# =============================================================================

def extract_electrode_info(col_name: str):
    """
    'A1_11' → ('A1', '11')
    Axion 24-well: Well = A1~D6, Electrode Index = 11~48
    """
    m = re.match(r'^([A-D][1-6])_(\d{2})$', col_name)
    if not m:
        return None, None
    return m.group(1), m.group(2)


# =============================================================================
# 3. 단일 Excel (electrode 파일) → long-format 변환
# =============================================================================

def load_single_electrode_excel(path: str) -> pd.DataFrame:
    """
    하나의 electrode Excel 파일을 long-format 전극 레벨 DataFrame으로 변환.
    - 각 row: (Plate_ID, File, Well, Electrode_ID, Metric, Value, ...)
    """
    file_path = Path(path)
    xls = pd.ExcelFile(file_path)

    df_meta = pd.read_excel(file_path, sheet_name="Metadata")
    df_template = pd.read_excel(file_path, sheet_name="Template")
    df_well = pd.read_excel(file_path, sheet_name="Well_Info")

    meta = df_meta.iloc[0].to_dict()
    # Well_Info: Well / Differentiation_Day
    diff_map = dict(zip(df_well["Well"], df_well["Differentiation_Day"]))

    plating_day = meta.get("Plating DAY", meta.get("PLATING_DAY", np.nan))

    # 전극 컬럼 찾기 (Metric / Unit / Condition 제외, A1_11 같은 패턴만)
    electrode_cols = []
    for c in df_template.columns:
        if c in ("Metric", "Unit", "Condition"):
            continue
        well, elec_idx = extract_electrode_info(c)
        if well is not None:
            electrode_cols.append(c)

    print(f"[LOAD] {file_path.name}: {len(electrode_cols)} electrode columns detected")

    rows = []
    for _, row in df_template.iterrows():
        metric_raw = row["Metric"]
        metric_std = standardize_metric_name(metric_raw)

        for col in electrode_cols:
            val = row[col]
            if pd.isna(val):
                # NaN 값은 저장하지 않음 (나중에 metric presence는 count로 계산)
                continue

            well, elec_idx = extract_electrode_info(col)
            diff_day0 = diff_map.get(well, np.nan)
            diff_day = (
                diff_day0 + plating_day
                if pd.notna(diff_day0) and pd.notna(plating_day)
                else np.nan
            )

            rows.append(
                {
                    "File": file_path.stem,
                    "Plate_ID": meta.get("PLATE_ID", "UNKNOWN"),
                    "Well": well,
                    "Electrode_ID": col,
                    "Electrode_Index": elec_idx,
                    "Metric": metric_std,
                    "Metric_Raw": metric_raw,
                    "Value": float(val),
                    "BASE_STIM": meta.get("BASE_STIM", "UNKNOWN"),
                    "TIME_START": meta.get("TIME_START", meta.get("TIME_START(sec)", 0)),
                    "TIME_DURATION_SEC": meta.get(
                        "TIME_DURATION(sec)", meta.get("TIME_DURATION_SEC", 0)
                    ),
                    "Plating_Day": plating_day,
                    "Differentiation_Day": diff_day0,
                    "DIFF_DAY": diff_day,
                    "LIGHT_CODE": meta.get("LIGHT_CODE", "UNKNOWN"),
                    "INTENSITY_PCT": meta.get(
                        "INTENSITY(%)", meta.get("INTENSITY_PCT", 0)
                    ),
                    "EXP_TYPE": meta.get("EXP_TYPE", "UNKNOWN"),
                    "DRUG": meta.get("DRUG", "NONE"),
                    "CONCENTRATION_mM": meta.get(
                        "CONCENTRATION (mM)", meta.get("CONCENTRATION_MM", 0)
                    ),
                }
            )

    df_long = pd.DataFrame(rows)
    return df_long


# =============================================================================
# 4. 여러 파일 로더 (폴더 단위)
# =============================================================================

class ElectrodeFormatLoader:
    """
    electrode Excel 파일들을 폴더에서 모두 읽어서
    전극 레벨 long-format DataFrame으로 합치는 클래스.
    """

    def __init__(self, input_dir):
        self.input_dir = Path(input_dir)
        self.files = []

    def load_all(self) -> pd.DataFrame:
        """폴더 내 *.xlsx (임시파일 ~\$ 제외)를 모두 읽어서 concat."""
        self.files = [
            f for f in self.input_dir.glob("*.xlsx") if not f.name.startswith("~$")
        ]

        if not self.files:
            print(f"[LOAD] No Excel files found in {self.input_dir}")
            return pd.DataFrame()

        all_rows = []
        for f in self.files:
            try:
                df_long = load_single_electrode_excel(str(f))
                all_rows.append(df_long)
            except Exception as e:
                print(f"[WARN] Failed to load {f.name}: {e}")

        if not all_rows:
            print("[LOAD] No valid data loaded from any file.")
            return pd.DataFrame()

        df_all = pd.concat(all_rows, ignore_index=True)
        print(
            f"[LOAD] Combined: {len(df_all)} rows, "
            f"{df_all['Electrode_ID'].nunique()} electrodes, "
            f"{df_all['Metric'].nunique()} metrics"
        )
        return df_all


# =============================================================================
# 5. 전극 필터링 기준 설정 (dataclass)
# =============================================================================

@dataclass
class ElectrodeFilterConfig:
    """
    전극 선택 기준 설정값.
    - min_metric_ratio : STIM에서 non-NaN metric 비율 최소값 (ex. 0.5 = 절반 이상 채워져야)
    - min_abs_spike_diff : BASE vs STIM에서 number_of_spikes 절대 차이 최소값
    - min_fold_change : BASE vs STIM에서 number_of_spikes 배수 변화 최소값
    """

    min_metric_ratio: float = 0.5
    min_abs_spike_diff: float = 20.0
    min_fold_change: float = 2.0


# =============================================================================
# 6. 실제 필터링 로직
# =============================================================================

def filter_electrodes(
    df_long: pd.DataFrame,
    min_metric_ratio: float = 0.5,
    min_abs_spike_diff: float = 20.0,
    min_fold_change: float = 2.0,
    verbose: bool = True,
):
    """
    전극 레벨 필터링.
    1) STIM에서 metric 대부분이 non-NaN인 전극만 고려
    2) BASE vs STIM 'number_of_spikes' 차이가 큰 전극만 선택

    반환:
      - selected_stats: 전극별 통계 (metric 개수, spike diff, fold change 등)
      - df_filtered   : 선택된 전극들의 모든 metric (BASE/STIM/WASH 등 포함)
    """
    if df_long.empty:
        if verbose:
            print("[FILTER] Empty DataFrame, nothing to filter.")
        return None, df_long.iloc[0:0]

    df = df_long.copy()
    total_metrics = df["Metric"].nunique()
    if verbose:
        print(f"[FILTER] Total unique metrics: {total_metrics}")

    # 전극 식별을 위한 key
    key_cols = [
        "Plate_ID",
        "Well",
        "Electrode_ID",
        "Electrode_Index",
        "LIGHT_CODE",
        "INTENSITY_PCT",
        "EXP_TYPE",
        "DRUG",
    ]

    # (1) STIM에서 metric presence 계산
    stim_nonan = df[(df["BASE_STIM"] == "STIM") & df["Value"].notna()]
    if stim_nonan.empty:
        if verbose:
            print("[FILTER] No STIM data found.")
        return None, df.iloc[0:0]

    stim_counts = (
        stim_nonan.groupby(key_cols)["Metric"]
        .nunique()
        .reset_index()
        .rename(columns={"Metric": "n_metrics_stim"})
    )
    stim_counts["metric_ratio"] = stim_counts["n_metrics_stim"] / float(total_metrics)

    # (2) BASE vs STIM number_of_spikes 비교
    spikes_base = (
        df[
            (df["BASE_STIM"] == "BASE")
            & (df["Metric"] == "number_of_spikes")
        ]
        .groupby(key_cols)["Value"]
        .mean()
        .reset_index()
        .rename(columns={"Value": "spikes_base"})
    )

    spikes_stim = (
        df[
            (df["BASE_STIM"] == "STIM")
            & (df["Metric"] == "number_of_spikes")
        ]
        .groupby(key_cols)["Value"]
        .mean()
        .reset_index()
        .rename(columns={"Value": "spikes_stim"})
    )

    merged = (
        stim_counts.merge(spikes_base, on=key_cols, how="left")
        .merge(spikes_stim, on=key_cols, how="left")
    )

    # spike 값이 없는 전극 제거
    merged = merged.dropna(subset=["spikes_base", "spikes_stim"])

    eps = 1e-6
    merged["abs_diff"] = (merged["spikes_stim"] - merged["spikes_base"]).abs()
    merged["fold_change"] = (merged["spikes_stim"] + eps) / (merged["spikes_base"] + eps)

    # 조건식
    cond_metrics = merged["metric_ratio"] >= min_metric_ratio
    cond_diff = merged["abs_diff"] >= min_abs_spike_diff
    cond_fc = merged["fold_change"] >= min_fold_change

    merged["selected"] = cond_metrics & (cond_diff | cond_fc)

    selected_stats = merged[merged["selected"]].copy()

    if verbose:
        print(
            f"[FILTER] Electrodes with sufficient metrics: "
            f"{cond_metrics.sum()}/{len(merged)}"
        )
        print(
            f"[FILTER] Selected electrodes (large spike change): "
            f"{selected_stats.shape[0]}"
        )

    # (3) 원래 DataFrame에서 선택된 전극의 모든 metric 추출
    if selected_stats.empty:
        df_filtered = df.iloc[0:0]
    else:
        df_flagged = df.merge(
            selected_stats[key_cols + ["selected"]], on=key_cols, how="left"
        )
        df_filtered = df_flagged[df_flagged["selected"] == True].copy()
        df_filtered.drop(columns=["selected"], inplace=True)

    return selected_stats, df_filtered


# =============================================================================
# 7. 파이프라인 클래스 (입력폴더 → 출력폴더)
# =============================================================================

class ElectrodeAnalysisPipeline:
    """
    사용 예:
        pipeline = ElectrodeAnalysisPipeline(
            input_dir=r"D:\MEAdata\#7_electrode",
            output_dir=r"D:\MEAdata\#7_electrode\analysis",
            filter_config=ElectrodeFilterConfig(
                min_metric_ratio=0.5,
                min_abs_spike_diff=20,
                min_fold_change=2.0
            )
        )
        pipeline.run()
    """

    def __init__(
        self,
        input_dir,
        output_dir,
        filter_config: ElectrodeFilterConfig | None = None,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.filter_config = filter_config or ElectrodeFilterConfig()

        self.df_all: pd.DataFrame | None = None
        self.selected_stats: pd.DataFrame | None = None
        self.df_selected: pd.DataFrame | None = None

    def run(self):
        # 1) 로딩
        loader = ElectrodeFormatLoader(self.input_dir)
        self.df_all = loader.load_all()

        if self.df_all.empty:
            print("[PIPELINE] No electrode data loaded. Abort.")
            return

        # 2) raw long-format 저장
        combined_path = self.output_dir / "electrode_all_long.csv"
        self.df_all.to_csv(combined_path, index=False)
        print(f"[PIPELINE] Saved: {combined_path}")

        # 3) 전극 필터링
        self.selected_stats, self.df_selected = filter_electrodes(
            self.df_all,
            min_metric_ratio=self.filter_config.min_metric_ratio,
            min_abs_spike_diff=self.filter_config.min_abs_spike_diff,
            min_fold_change=self.filter_config.min_fold_change,
            verbose=True,
        )

        if self.selected_stats is None or self.selected_stats.empty:
            print("[PIPELINE] No electrodes passed the selection criteria.")
            return

        # 4) 결과 저장
        stats_path = self.output_dir / "electrode_selected_stats.csv"
        self.selected_stats.to_csv(stats_path, index=False)
        print(f"[PIPELINE] Saved: {stats_path}")

        selected_path = self.output_dir / "electrode_selected_long.csv"
        self.df_selected.to_csv(selected_path, index=False)
        print(f"[PIPELINE] Saved: {selected_path}")


# =============================================================================
# 8. 직접 실행용 예시
# =============================================================================

if __name__ == "__main__":
    # 예시 경로 (원하는 대로 수정해서 사용)
    input_dir = r"D:\MEAdata\#7_electrode"
    output_dir = r"D:\MEAdata\#7_electrode\analysis_electrode"

    config = ElectrodeFilterConfig(
        min_metric_ratio=0.5,     # STIM에서 metric의 절반 이상이 채워진 전극만
        min_abs_spike_diff=20.0,  # BASE vs STIM spike 차이 20 이상
        min_fold_change=2.0       # 또는 2배 이상 증가/감소
    )

    pipeline = ElectrodeAnalysisPipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        filter_config=config,
    )
    pipeline.run()
