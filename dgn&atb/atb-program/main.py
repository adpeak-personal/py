"""아파트 실거래가 조회 데스크톱 앱 (진입점).

프론트(atb-front) → 백(atb-back) 요청 기능을 파이썬 GUI 로 재구현.
  - 국토교통부 실거래가 조회 (services/apt_api.py)
  - 네이버 검색 기반 이미지 표시 (services/image_service.py, ui/image_window.py)
  - MySQL 저장 (services/db.py)

실행:  .venv\\Scripts\\python.exe main.py
"""
from ui.app import run

if __name__ == "__main__":
    run()
