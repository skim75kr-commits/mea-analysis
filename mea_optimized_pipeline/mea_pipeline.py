"""
MEA Data Pipeline Orchestrator
==============================
Migrator와 Improver를 연결하는 통합 파이프라인

장점:
1. 한 번의 명령으로 전체 프로세스 실행 (사용자 편의)
2. 각 도구는 독립적으로 유지 (개발자 편의)
3. 유연한 실행 옵션 (시나리오별 최적화)
4. 중간 결과 확인 가능 (디버깅 용이)

Usage:
    # 전체 파이프라인 (레거시 → 표준 → 최적화)
    python mea_pipeline.py -i legacy/ -o output/ --full
    
    # 표준 → 최적화만 (신규 파일)
    python mea_pipeline.py -i standard/ -o output/ --improve-only
    
    # 레거시 → 표준만
    python mea_pipeline.py -i legacy/ -o output/ --migrate-only
    
    # 중간 파일 유지 (디버깅용)
    python mea_pipeline.py -i legacy/ -o output/ --full --keep-intermediate
"""

import sys
from pathlib import Path
import shutil
import tempfile
import logging
from datetime import datetime
from typing import Dict, Optional
import argparse

# 기존 도구 import
try:
    from mea_migrator_v2_improved import MEAFileMigrator
    from mea_file_improver import MEAFileImprover
except ImportError as e:
    print(f"Error: {e}")
    print("Please ensure mea_migrator_v2_improved.py and mea_file_improver.py are in the same directory")
    sys.exit(1)


class MEAPipeline:
    """
    MEA 데이터 처리 파이프라인 Orchestrator
    
    독립적인 도구들을 연결하여 완전한 워크플로우 제공
    """
    
    def __init__(self, log_level: str = 'INFO'):
        self.log_level = log_level
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - [%(levelname)s] - %(message)s',
            force=True
        )
        self.logger = logging.getLogger(__name__)
    
    def detect_file_format(self, input_dir: Path) -> str:
        """
        입력 파일 형식 자동 감지
        
        Returns:
            'legacy': 레거시 포맷 (구버전)
            'standard': 표준 포맷 (현재 포맷)
            'improved': 이미 개선된 포맷
        """
        # 첫 번째 파일 확인
        xlsx_files = list(input_dir.glob('*.xlsx'))
        xlsx_files = [f for f in xlsx_files if not f.name.startswith('~$')]
        
        if not xlsx_files:
            return 'unknown'
        
        sample_file = xlsx_files[0]
        
        try:
            import pandas as pd
            df_meta = pd.read_excel(sample_file, sheet_name='Metadata', nrows=1)
            
            # 컬럼명으로 포맷 판단
            columns = set(df_meta.columns)
            
            # 개선된 포맷 체크 (언더스코어 사용)
            if 'PLATING_DAY' in columns and 'TIME_DURATION_SEC' in columns:
                # Well_Info에 DIFF_DAY가 있는지 확인
                df_well = pd.read_excel(sample_file, sheet_name='Well_Info', nrows=1)
                if 'DIFF_DAY' in df_well.columns:
                    return 'improved'
                else:
                    return 'standard'
            
            # 표준 포맷 체크 (공백 있을 수 있음)
            elif 'PLATE_ID' in columns and 'BASE_STIM' in columns:
                return 'standard'
            
            # 레거시 포맷
            else:
                return 'legacy'
                
        except Exception as e:
            self.logger.warning(f"포맷 감지 실패: {e}, 레거시로 간주")
            return 'legacy'
    
    def run_migration(self, input_dir: Path, output_dir: Path) -> Dict:
        """Migration 단계 실행"""
        self.logger.info("=" * 70)
        self.logger.info("STAGE 1: Migration (레거시 → 표준)")
        self.logger.info("=" * 70)
        
        migrator = MEAFileMigrator(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            log_level=self.log_level
        )
        
        summary = migrator.migrate_all()
        
        self.logger.info("Stage 1 완료\n")
        return summary
    
    def run_improvement(self, input_dir: Path, output_dir: Path) -> Dict:
        """Improvement 단계 실행"""
        self.logger.info("=" * 70)
        self.logger.info("STAGE 2: Improvement (표준 → 최적화)")
        self.logger.info("=" * 70)
        
        from mea_file_improver import batch_convert
        batch_convert(str(input_dir), str(output_dir))
        
        # 통계 수집
        output_files = list(output_dir.glob('*.xlsx'))
        
        self.logger.info("Stage 2 완료\n")
        return {'output_files': len(output_files)}
    
    def run_full_pipeline(
        self, 
        input_dir: Path, 
        output_dir: Path,
        keep_intermediate: bool = False
    ) -> Dict:
        """
        전체 파이프라인 실행
        
        Args:
            input_dir: 입력 디렉토리
            output_dir: 최종 출력 디렉토리
            keep_intermediate: 중간 파일 유지 여부
        """
        start_time = datetime.now()
        
        self.logger.info("🚀 MEA Data Pipeline 시작")
        self.logger.info(f"입력: {input_dir}")
        self.logger.info(f"출력: {output_dir}")
        self.logger.info("")
        
        # 입력 포맷 자동 감지
        input_format = self.detect_file_format(input_dir)
        self.logger.info(f"📝 감지된 포맷: {input_format.upper()}")
        self.logger.info("")
        
        # 출력 디렉토리 준비
        output_dir.mkdir(parents=True, exist_ok=True)
        
        stats = {
            'input_format': input_format,
            'stages_executed': [],
            'start_time': start_time
        }
        
        # 이미 최적화된 포맷이면 복사만
        if input_format == 'improved':
            self.logger.info("✓ 이미 최적화된 포맷입니다. 복사만 수행합니다.")
            for file in input_dir.glob('*.xlsx'):
                if not file.name.startswith('~$'):
                    shutil.copy2(file, output_dir / file.name)
            stats['stages_executed'] = ['copy']
            return stats
        
        # 중간 디렉토리 설정
        if keep_intermediate:
            intermediate_dir = output_dir / 'intermediate'
            intermediate_dir.mkdir(exist_ok=True)
        else:
            intermediate_dir = Path(tempfile.mkdtemp(prefix='mea_pipeline_'))
        
        try:
            # Stage 1: Migration (필요시)
            if input_format == 'legacy':
                migration_summary = self.run_migration(input_dir, intermediate_dir)
                stats['migration'] = migration_summary
                stats['stages_executed'].append('migration')
                source_for_improvement = intermediate_dir
            else:
                self.logger.info("✓ Stage 1 스킵 (이미 표준 포맷)")
                source_for_improvement = input_dir
            
            # Stage 2: Improvement
            improvement_summary = self.run_improvement(source_for_improvement, output_dir)
            stats['improvement'] = improvement_summary
            stats['stages_executed'].append('improvement')
            
        finally:
            # 중간 파일 정리
            if not keep_intermediate and intermediate_dir.exists():
                self.logger.info(f"🗑️  중간 파일 정리: {intermediate_dir}")
                shutil.rmtree(intermediate_dir)
        
        # 최종 통계
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        stats['end_time'] = end_time
        stats['elapsed_seconds'] = elapsed
        
        self.logger.info("=" * 70)
        self.logger.info("✅ 파이프라인 완료")
        self.logger.info("=" * 70)
        self.logger.info(f"실행 단계: {' → '.join(stats['stages_executed'])}")
        self.logger.info(f"소요 시간: {elapsed:.2f}초")
        if 'improvement' in stats:
            self.logger.info(f"생성된 파일: {stats['improvement']['output_files']}개")
        self.logger.info(f"출력 위치: {output_dir}")
        
        if keep_intermediate:
            self.logger.info(f"중간 파일: {intermediate_dir}")
        
        return stats
    
    def run_migrate_only(self, input_dir: Path, output_dir: Path) -> Dict:
        """Migration만 실행"""
        self.logger.info("🚀 Migration Only Mode")
        output_dir.mkdir(parents=True, exist_ok=True)
        return self.run_migration(input_dir, output_dir)
    
    def run_improve_only(self, input_dir: Path, output_dir: Path) -> Dict:
        """Improvement만 실행"""
        self.logger.info("🚀 Improvement Only Mode")
        output_dir.mkdir(parents=True, exist_ok=True)
        return self.run_improvement(input_dir, output_dir)


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description='MEA Data Pipeline - 통합 데이터 처리 파이프라인',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 전체 파이프라인 (자동 감지)
  %(prog)s -i input/ -o output/ --full
  
  # 레거시 → 표준만
  %(prog)s -i legacy/ -o standard/ --migrate-only
  
  # 표준 → 최적화만
  %(prog)s -i standard/ -o optimized/ --improve-only
  
  # 중간 파일 유지 (디버깅)
  %(prog)s -i input/ -o output/ --full --keep-intermediate
  
  # 디버그 모드
  %(prog)s -i input/ -o output/ --full --log DEBUG
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='입력 디렉토리'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='출력 디렉토리'
    )
    
    # 실행 모드 (상호 배타적)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--full',
        action='store_true',
        help='전체 파이프라인 실행 (자동 감지)'
    )
    mode_group.add_argument(
        '--migrate-only',
        action='store_true',
        help='Migration만 실행 (레거시 → 표준)'
    )
    mode_group.add_argument(
        '--improve-only',
        action='store_true',
        help='Improvement만 실행 (표준 → 최적화)'
    )
    
    parser.add_argument(
        '--keep-intermediate',
        action='store_true',
        help='중간 파일 유지 (디버깅용, --full과 함께 사용)'
    )
    
    parser.add_argument(
        '--log',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='로그 레벨 (기본: INFO)'
    )
    
    args = parser.parse_args()
    
    # 입출력 디렉토리
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"Error: 입력 디렉토리가 존재하지 않습니다: {input_dir}")
        sys.exit(1)
    
    # Pipeline 생성
    pipeline = MEAPipeline(log_level=args.log)
    
    try:
        # 실행 모드에 따라 분기
        if args.full:
            stats = pipeline.run_full_pipeline(
                input_dir, 
                output_dir,
                keep_intermediate=args.keep_intermediate
            )
        elif args.migrate_only:
            stats = pipeline.run_migrate_only(input_dir, output_dir)
        elif args.improve_only:
            stats = pipeline.run_improve_only(input_dir, output_dir)
        
        # 성공 종료
        sys.exit(0)
        
    except Exception as e:
        logging.error(f"파이프라인 실패: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
