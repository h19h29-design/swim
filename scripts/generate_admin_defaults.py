from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = ROOT / "data" / "admin"
BADGE_DIR = ROOT / "docs" / "assets" / "badges"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_badge(
    badge_id: str,
    category: str,
    name_ko: str,
    short_label_ko: str,
    description_ko: str,
    threshold_type: str,
    threshold_value: int,
    icon_key: str,
    tier: int,
    *,
    primary: bool = False,
    hidden: bool = False,
    season_tag: str | None = None,
) -> dict:
    return {
        "badge_id": badge_id,
        "category": category,
        "name_ko": name_ko,
        "short_label_ko": short_label_ko,
        "description_ko": description_ko,
        "threshold_type": threshold_type,
        "threshold_value": threshold_value,
        "icon_key": icon_key,
        "tier": tier,
        "is_primary_title_candidate": primary,
        "is_hidden": hidden,
        "season_tag": season_tag,
    }


def build_site_config() -> dict:
    return {
        "site_title_ko": "수영 스티커북",
        "site_subtitle_ko": "기록, 랭킹, 배지와 해금을 한 화면에서 보는 갤러리 수영 대시보드",
        "product_mode": "core_only",
        "theme_direction_ko": "스티커북 톤 + 게임형 정보 구조",
        "hero": {
            "eyebrow_ko": "SWIM STICKER BOOK",
            "headline_ko": "붙이고 모으는 수영 시즌 보드",
            "subheadline_ko": "갤 전체 운동량, 랭킹, 대표 칭호와 다음 해금을 한 번에 보여줍니다.",
        },
        "kpi_labels": {
            "swim_count": "갤 전체 운동횟수",
            "total_distance_m": "갤 전체 총거리",
            "total_seconds": "갤 전체 총시간",
            "active_authors": "참여 인원",
        },
        "gallery_labels": {
            "current_title_ko": "이번 시즌 갤 칭호",
            "next_title_ko": "다음 갤 칭호",
            "recent_unlocks_ko": "최근 해금",
        },
        "empty_state_ko": "아직 자동 포함된 기록이 많지 않습니다. 제목 양식을 맞춘 새 글이 쌓이면 바로 채워집니다.",
        "admin_edit_note_ko": "관리자 페이지에서 설정을 저장한 뒤 rebuild 하면 사용자 화면에 반영됩니다.",
        "main_experience_notes_ko": [
            "이 대시보드는 게시글 제목 양식만 공식 입력으로 읽습니다.",
            "메인 화면은 운동 정보, 랭킹, 해금 순으로 보여줍니다.",
            "배지와 섹션 구성은 data/admin JSON에서 조정할 수 있습니다."
        ]
    }


def build_navigation_config() -> dict:
    return {
        "default_nav_key": "home",
        "items": [
            {"nav_key": "home", "label_ko": "메인 대시보드", "description_ko": "갤 전체 기록과 랭킹", "visible": True, "href": "./index.html?desktop=1"},
            {"nav_key": "profiles", "label_ko": "개인 앨범", "description_ko": "닉네임별 성장과 배지", "visible": True, "href": "./profile.html"},
            {"nav_key": "parse_status", "label_ko": "파싱 현황", "description_ko": "성공/실패 글과 수동 보정", "visible": True, "href": "./parse-status.html"},
            {"nav_key": "badges", "label_ko": "배지 갤러리", "description_ko": "전체 배지와 아이콘 보기", "visible": True, "href": "./badge-gallery.html"},
            {"nav_key": "admin", "label_ko": "관리자", "description_ko": "문구, 배지, 아이콘 설정", "visible": True, "href": "./admin.html"},
        ],
    }


def build_home_sections() -> dict:
    return {
        "default_ranking_metric": "swim_count",
        "section_order": [
            "hero",
            "summary_kpis",
            "rankings",
            "recent_unlocks",
            "badge_shelf",
            "profile_search",
            "recent_records",
            "ops",
        ],
        "ranking_sections": [
            {"metric_key": "swim_count", "label_ko": "참여횟수", "description_ko": "이번 시즌 가장 꾸준히 수영한 닉네임"},
            {"metric_key": "total_distance_m", "label_ko": "거리", "description_ko": "누적 거리를 가장 많이 채운 닉네임"},
            {"metric_key": "total_seconds", "label_ko": "시간", "description_ko": "총 운동 시간이 가장 긴 닉네임"},
            {"metric_key": "distance_per_hour_m", "label_ko": "시간당 거리", "description_ko": "시간당 거리가 가장 높은 닉네임"},
            {"metric_key": "growth_swim_count", "label_ko": "성장: 횟수", "description_ko": "최근 28일 참여횟수가 가장 늘어난 닉네임"},
            {"metric_key": "growth_distance_m", "label_ko": "성장: 거리", "description_ko": "최근 28일 누적 거리가 가장 늘어난 닉네임"},
            {"metric_key": "growth_total_seconds", "label_ko": "성장: 시간", "description_ko": "최근 28일 운동 시간이 가장 늘어난 닉네임"},
        ],
        "recent_unlock_limit": 10,
        "recent_record_limit": 20,
    }


def build_badge_catalog() -> dict:
    badges: list[dict] = []

    attendance = [
        ("att_01", "첫 입수", "첫 입수", "첫 기록을 남기면 받는 시작 배지입니다.", 1, 1),
        ("att_02", "레인 발도장", "3회", "세 번의 기록으로 루틴의 첫 흔적을 남깁니다.", 3, 2),
        ("att_03", "오수완 시동", "5회", "다섯 번의 기록으로 꾸준함의 시동을 겁니다.", 5, 3),
        ("att_04", "꾸준러", "10회", "열 번의 기록으로 루틴이 자리를 잡습니다.", 10, 4),
        ("att_05", "출석왕", "20회", "스무 번의 기록으로 출석왕 배지를 해금합니다.", 20, 5),
        ("att_06", "물개 반장", "35회", "삼십오 번의 기록으로 수영 갤 분위기를 이끄는 단계입니다.", 35, 6),
        ("att_07", "레인 지박령", "50회", "쉰 번의 기록을 넘기면 레인 지박령입니다.", 50, 7),
        ("att_08", "수영장 상주자", "80회", "한 시즌 최상급 출석 칭호입니다.", 80, 8),
    ]
    for badge_id, name, short_label, description, threshold, tier in attendance:
        badges.append(make_badge(badge_id, "attendance", name, short_label, description, "author_total_swim_count", threshold, "att.base", tier, primary=True))

    distance = [
        ("dst_01", "1km 돌파", "1km", "누적 1km를 넘기며 첫 물결을 만듭니다.", 1_000, 1),
        ("dst_02", "물결 수집가", "3km", "3km부터는 거리를 쌓는 감각이 붙습니다.", 3_000, 2),
        ("dst_03", "중거리 주자", "5km", "누적 5km를 채운 중거리 단계입니다.", 5_000, 3),
        ("dst_04", "장거리 레이서", "10km", "누적 10km를 넘기면 장거리 레이서입니다.", 10_000, 4),
        ("dst_05", "수로 개척자", "25km", "25km를 쌓아 나만의 수로를 엽니다.", 25_000, 5),
        ("dst_06", "백킬로 클럽", "50km", "누적 50km를 달성한 거리 고수입니다.", 50_000, 6),
        ("dst_07", "물길의 주인", "100km", "누적 100km를 채운 물길의 주인입니다.", 100_000, 7),
        ("dst_08", "대양 주자", "200km", "한 시즌 최상위 거리 칭호입니다.", 200_000, 8),
    ]
    for badge_id, name, short_label, description, threshold, tier in distance:
        badges.append(make_badge(badge_id, "distance", name, short_label, description, "author_total_distance_m", threshold, "dst.base", tier, primary=True))

    time_badges = [
        ("tim_01", "첫 1시간 잠수", "1시간", "누적 1시간으로 첫 잠수 기록을 남깁니다.", 3_600, 1),
        ("tim_02", "물 적응 완료", "3시간", "3시간부터 레인 체류가 익숙해집니다.", 10_800, 2),
        ("tim_03", "레인 체류자", "6시간", "누적 6시간을 채운 레인 체류자입니다.", 21_600, 3),
        ("tim_04", "장시간 생존자", "12시간", "장시간 루틴을 유지하는 단계입니다.", 43_200, 4),
        ("tim_05", "물속 거주민", "24시간", "누적 하루를 채운 물속 거주민입니다.", 86_400, 5),
        ("tim_06", "심해 체류자", "48시간", "이틀 분량 시간을 채운 심해 체류자입니다.", 172_800, 6),
        ("tim_07", "레인 장기복무", "100시간", "100시간을 넘기면 장기복무 단계입니다.", 360_000, 7),
        ("tim_08", "수영 생활자", "200시간", "한 시즌 최상위 시간 칭호입니다.", 720_000, 8),
    ]
    for badge_id, name, short_label, description, threshold, tier in time_badges:
        badges.append(make_badge(badge_id, "time", name, short_label, description, "author_total_seconds", threshold, "tim.base", tier, primary=True))

    efficiency = [
        ("eff_01", "기본 추진", "700m/h", "시간당 700m를 넘기면 기본 추진 배지를 받습니다.", 700, 1),
        ("eff_02", "물속 모터", "900m/h", "시간당 900m를 넘기면 물속 모터 단계입니다.", 900, 2),
        ("eff_03", "레인 스프린터", "1100m/h", "시간당 1100m를 넘기면 스프린터 배지입니다.", 1_100, 3),
        ("eff_04", "수중 엔진", "1300m/h", "시간당 1300m를 넘기면 수중 엔진 단계입니다.", 1_300, 4),
        ("eff_05", "레인 터보", "1500m/h", "최상위 효율 배지입니다.", 1_500, 5),
    ]
    for badge_id, name, short_label, description, threshold, tier in efficiency:
        badges.append(make_badge(badge_id, "efficiency", name, short_label, description, "author_distance_per_hour_m", threshold, "eff.base", tier))

    growth = [
        ("grw_01", "요즘 상승", "횟수 +1", "최근 28일 참여횟수가 이전보다 늘었습니다.", "author_recent_growth_swim_count", 1, 1),
        ("grw_02", "거리 급상승", "+500m", "최근 28일 거리가 500m 이상 늘었습니다.", "author_recent_growth_distance_m", 500, 2),
        ("grw_03", "호흡이 붙음", "+30분", "최근 28일 운동 시간이 30분 이상 늘었습니다.", "author_recent_growth_total_seconds", 1_800, 3),
        ("grw_04", "출석 각성", "횟수 +3", "최근 28일 출석이 눈에 띄게 늘었습니다.", "author_recent_growth_swim_count", 3, 4),
        ("grw_05", "거리 각성", "+1500m", "최근 28일 거리가 크게 늘었습니다.", "author_recent_growth_distance_m", 1_500, 5),
        ("grw_06", "시간 각성", "+90분", "최근 28일 운동 시간이 크게 늘었습니다.", "author_recent_growth_total_seconds", 5_400, 6),
    ]
    for badge_id, name, short_label, description, threshold_type, threshold, tier in growth:
        badges.append(make_badge(badge_id, "growth", name, short_label, description, threshold_type, threshold, "grw.base", tier, primary=True))

    months = [
        ("sea_01", "03", "3월 개국 멤버", "3월", "3월 시즌에 첫 기록을 남긴 멤버입니다.", 1),
        ("sea_02", "04", "4월 물결 멤버", "4월", "4월 시즌 배지를 해금합니다.", 2),
        ("sea_03", "05", "봄 레인 멤버", "5월", "5월 시즌 배지입니다.", 3),
        ("sea_04", "06", "장마철 생존자", "6월", "장마철에도 루틴을 이어간 멤버입니다.", 4),
        ("sea_05", "07", "한여름 입수단", "7월", "7월 시즌을 채운 멤버입니다.", 5),
        ("sea_06", "08", "폭염 레인러", "8월", "한여름 시즌 배지입니다.", 6),
        ("sea_07", "09", "가을 루틴러", "9월", "가을 시즌 루틴을 만든 멤버입니다.", 7),
        ("sea_08", "10", "시즌 중반 지킴이", "10월", "10월 시즌을 이어간 멤버입니다.", 8),
        ("sea_09", "11", "찬물 적응자", "11월", "11월에도 꾸준히 입수한 멤버입니다.", 9),
        ("sea_10", "12", "연말 결산 멤버", "12월", "연말 시즌을 채운 멤버입니다.", 10),
        ("sea_11", "01", "새해 첫 입수", "1월", "새해 첫 시즌 배지입니다.", 11),
        ("sea_12", "02", "겨울 마감 주자", "2월", "겨울 시즌을 마무리한 멤버입니다.", 12),
    ]
    for badge_id, month, name, short_label, description, tier in months:
        badges.append(make_badge(badge_id, "season", name, short_label, description, "season_month_participation", 1, "sea.base", tier, season_tag=month))

    gallery_titles = [
        ("gal_01", "첫 물결", "50km", "갤 전체 누적 거리 50km를 달성했습니다.", 50_000, 1),
        ("gal_02", "레인 확장", "100km", "갤 전체 누적 거리 100km를 달성했습니다.", 100_000, 2),
        ("gal_03", "파도 가속", "150km", "갤 전체 누적 거리 150km를 달성했습니다.", 150_000, 3),
        ("gal_04", "대형 파도", "200km", "갤 전체 누적 거리 200km를 달성했습니다.", 200_000, 4),
        ("gal_05", "바다 개방", "250km", "갤 전체 누적 거리 250km를 달성했습니다.", 250_000, 5),
        ("gal_06", "원양 진출", "300km", "갤 전체 누적 거리 300km를 달성했습니다.", 300_000, 6),
        ("gal_07", "청해 돌파", "350km", "갤 전체 누적 거리 350km를 달성했습니다.", 350_000, 7),
        ("gal_08", "수영 갤 전설", "400km", "갤 전체 누적 거리 400km를 달성했습니다.", 400_000, 8),
    ]
    for badge_id, name, short_label, description, threshold, tier in gallery_titles:
        badges.append(make_badge(badge_id, "gallery", name, short_label, description, "gallery_total_distance_m", threshold, "gal.base", tier))

    fun = [
        ("fun_01", "오늘 길었수", "1회 1500m", "한 번의 기록에서 1500m를 채운 날 받는 보너스 배지입니다.", "author_single_swim_distance_m", 1_500, 1, False),
        ("fun_02", "물개 정복자", "1회 3000m", "한 번의 기록에서 3000m를 채우면 해금됩니다.", "author_single_swim_distance_m", 3_000, 2, False),
        ("fun_03", "주말 물개", "주말 3회", "주말 수영만 세 번 이상 남기면 받습니다.", "author_weekend_swim_count", 3, 3, False),
        ("fun_04", "새벽 입수단", "새벽 3회", "오전 8시 이전 기록이 세 번 이상입니다.", "author_early_bird_swim_count", 3, 4, False),
        ("fun_05", "야밤 수영부", "밤 2회", "밤 9시 이후 기록이 두 번 이상입니다.", "author_night_owl_swim_count", 2, 5, False),
        ("fun_06", "주말 레인 상주", "주말 8회", "주말 기록이 아주 많은 멤버입니다.", "author_weekend_swim_count", 8, 6, False),
        ("fun_07", "새벽 루틴 장인", "새벽 8회", "새벽 루틴이 확실한 멤버입니다.", "author_early_bird_swim_count", 8, 7, False),
        ("fun_08", "야행성 물고기", "밤 5회", "늦은 밤에도 꾸준히 입수한 시크릿 배지입니다.", "author_night_owl_swim_count", 5, 8, True),
    ]
    for badge_id, name, short_label, description, threshold_type, threshold, tier, hidden in fun:
        badges.append(make_badge(badge_id, "fun", name, short_label, description, threshold_type, threshold, "fun.base", tier, hidden=hidden))

    return {
        "version": 1,
        "title_ko": "수영 스티커북 배지 카탈로그",
        "description_ko": "출석, 거리, 시간, 효율, 성장, 시즌, 갤 전체, 보너스까지 1년 동안 모을 수 있는 기본 배지 묶음입니다.",
        "category_labels": {
            "attendance": "출석",
            "distance": "거리",
            "time": "시간",
            "efficiency": "효율",
            "growth": "성장",
            "season": "시즌",
            "gallery": "갤 전체",
            "fun": "보너스",
        },
        "badges": badges,
    }


def build_season_badges() -> dict:
    months = []
    labels = {
        "03": "3월 오픈런",
        "04": "4월 물결",
        "05": "5월 레인",
        "06": "6월 장마",
        "07": "7월 입수단",
        "08": "8월 열기",
        "09": "9월 루틴",
        "10": "10월 중반전",
        "11": "11월 냉수 적응",
        "12": "12월 연말",
        "01": "1월 새해",
        "02": "2월 피날레",
    }
    for idx, month in enumerate(["03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "01", "02"], start=1):
        months.append({"month": month, "label_ko": labels[month], "badge_id": f"sea_{idx:02d}"})
    return {
        "season_key": "2026",
        "season_name_ko": "2026 시즌",
        "unlock_rule_ko": "해당 월에 제목 양식 기록을 남기면 그 달 시즌 배지가 열립니다.",
        "months": months,
    }


def build_gallery_title_rules() -> dict:
    rules = []
    labels = [
        ("gal_01", "첫 물결", "50km", "갤 전체 누적 거리 50km를 달성했습니다.", 50_000, 1),
        ("gal_02", "레인 확장", "100km", "갤 전체 누적 거리 100km를 달성했습니다.", 100_000, 2),
        ("gal_03", "파도 가속", "150km", "갤 전체 누적 거리 150km를 달성했습니다.", 150_000, 3),
        ("gal_04", "대형 파도", "200km", "갤 전체 누적 거리 200km를 달성했습니다.", 200_000, 4),
        ("gal_05", "바다 개방", "250km", "갤 전체 누적 거리 250km를 달성했습니다.", 250_000, 5),
        ("gal_06", "원양 진출", "300km", "갤 전체 누적 거리 300km를 달성했습니다.", 300_000, 6),
        ("gal_07", "청해 돌파", "350km", "갤 전체 누적 거리 350km를 달성했습니다.", 350_000, 7),
        ("gal_08", "수영 갤 전설", "400km", "갤 전체 누적 거리 400km를 달성했습니다.", 400_000, 8),
    ]
    for badge_id, name, short_label, description, threshold, tier in labels:
        rules.append({
            "badge_id": badge_id,
            "name_ko": name,
            "short_label_ko": short_label,
            "description_ko": description,
            "threshold_type": "gallery_total_distance_m",
            "threshold_value": threshold,
            "icon_key": "gal.base",
            "tier": tier,
        })
    return {
        "metric_key": "gallery_total_distance_m",
        "title_basis_ko": "갤 전체 누적 거리",
        "progress_label_ko": "다음 갤 칭호까지 남은 거리",
        "fallback_title": {
            "badge_id": "gal_00",
            "name_ko": "시즌 준비중",
            "short_label_ko": "준비중",
            "description_ko": "아직 첫 갤 칭호가 열리기 전입니다.",
            "icon_key": "shared.gallery-title-seal",
            "tier": 0,
        },
        "rules": rules,
    }


def build_profile_layout_config() -> dict:
    return {
        "header_stat_keys": ["swim_count", "total_distance_m", "total_seconds", "distance_per_hour_m"],
        "section_order": ["hero", "metrics", "growth_compare", "badge_summary", "trend", "recent_records"],
        "badge_category_order": ["attendance", "distance", "time", "efficiency", "growth", "season", "gallery", "fun"],
        "recent_unlock_limit": 6,
        "badge_preview_limit": 8,
        "next_badge_label_ko": "다음 해금",
    }


def build_badge_art_catalog() -> dict:
    family_map = {
        "att": {"label_ko": "출석", "label_en": "Attendance", "badge_id_prefixes": ["att"], "display_note": "참여횟수와 출석 계열"},
        "dst": {"label_ko": "거리", "label_en": "Distance", "badge_id_prefixes": ["dst"], "display_note": "누적 거리와 거리 milestone 계열"},
        "tim": {"label_ko": "시간", "label_en": "Time", "badge_id_prefixes": ["tim"], "display_note": "누적 시간과 체류 계열"},
        "eff": {"label_ko": "효율", "label_en": "Efficiency", "badge_id_prefixes": ["eff"], "display_note": "시간당 거리와 효율 계열"},
        "grw": {"label_ko": "성장", "label_en": "Growth", "badge_id_prefixes": ["grw"], "display_note": "최근 28일 성장 계열"},
        "sea": {"label_ko": "시즌", "label_en": "Season", "badge_id_prefixes": ["sea"], "display_note": "월별 시즌 배지 계열"},
        "gal": {"label_ko": "갤 전체", "label_en": "Gallery", "badge_id_prefixes": ["gal"], "display_note": "갤 전체 누적 칭호 계열"},
        "fun": {"label_ko": "보너스", "label_en": "Fun", "badge_id_prefixes": ["fun"], "display_note": "이벤트와 보너스 배지 계열"},
    }
    icons = []
    for family in ["att", "dst", "tim", "eff", "grw", "sea", "gal", "fun"]:
        icons.append({
            "icon_key": f"{family}.base",
            "file_path": f"docs/assets/badges/{family}-base.svg",
            "family": family,
            "tier_compatibility": ["starter", "rally", "gold", "prism"],
            "color_notes": family_map[family]["label_ko"],
            "display_notes": f"{family_map[family]['label_ko']} 계열 기본 아이콘",
            "badge_id_prefixes": [family],
        })
    icons.extend([
        {"icon_key": "frame.sticker", "file_path": "docs/assets/badges/frame-sticker.svg", "family": "shared", "tier_compatibility": ["starter", "rally", "gold", "prism"], "color_notes": "스티커 프레임", "display_notes": "기본 스티커 프레임", "badge_id_prefixes": []},
        {"icon_key": "frame.ribbon", "file_path": "docs/assets/badges/frame-ribbon.svg", "family": "shared", "tier_compatibility": ["rally", "gold", "prism"], "color_notes": "리본 프레임", "display_notes": "조금 더 강조된 프레임", "badge_id_prefixes": []},
        {"icon_key": "frame.seal", "file_path": "docs/assets/badges/frame-seal.svg", "family": "shared", "tier_compatibility": ["gold", "prism"], "color_notes": "씰 프레임", "display_notes": "상위 티어용 씰 프레임", "badge_id_prefixes": []},
        {"icon_key": "shared.representative-title", "file_path": "docs/assets/badges/special-representative-title.svg", "family": "shared", "tier_compatibility": ["gold", "prism"], "color_notes": "대표 칭호", "display_notes": "개인 대표 칭호 카드용", "badge_id_prefixes": []},
        {"icon_key": "shared.recent-unlock-chip", "file_path": "docs/assets/badges/special-recent-unlock-chip.svg", "family": "shared", "tier_compatibility": ["starter", "rally", "gold", "prism"], "color_notes": "최근 해금", "display_notes": "최근 해금 칩용", "badge_id_prefixes": []},
        {"icon_key": "shared.gallery-title-seal", "file_path": "docs/assets/badges/special-gallery-title-seal.svg", "family": "shared", "tier_compatibility": ["gold", "prism"], "color_notes": "갤 칭호", "display_notes": "갤 전체 칭호 씰", "badge_id_prefixes": []},
    ])
    return {
        "generated_on": "2026-03-17",
        "asset_root": "docs/assets/badges",
        "naming_rule": "{family}-base.svg for family icons; frame-{shape}.svg for shared frames; special-{treatment}.svg for featured treatments.",
        "family_map": family_map,
        "tier_palettes": [
            {"id": "starter", "label_ko": "입문", "swatch": ["#fff4ea", "#ffd966", "#ffb38f"], "color_notes": "처음 해금하는 배지용 팔레트"},
            {"id": "rally", "label_ko": "활약", "swatch": ["#83d6c9", "#7cb7ff", "#fffaf7"], "color_notes": "중간 단계 배지용 팔레트"},
            {"id": "gold", "label_ko": "상위", "swatch": ["#ffd966", "#ff9d5c", "#fff7d6"], "color_notes": "대표 칭호와 상위 배지용"},
            {"id": "prism", "label_ko": "하이라이트", "swatch": ["#ff8f7a", "#83d6c9", "#7cb7ff"], "color_notes": "최근 해금과 특수 배지용"},
        ],
        "icons": icons,
    }


def main() -> None:
    write_json(ADMIN_DIR / "site_config.json", build_site_config())
    write_json(ADMIN_DIR / "navigation_config.json", build_navigation_config())
    write_json(ADMIN_DIR / "home_sections.json", build_home_sections())
    write_json(ADMIN_DIR / "badge_catalog.json", build_badge_catalog())
    write_json(ADMIN_DIR / "season_badges.json", build_season_badges())
    write_json(ADMIN_DIR / "gallery_title_rules.json", build_gallery_title_rules())
    write_json(ADMIN_DIR / "profile_layout_config.json", build_profile_layout_config())
    write_json(ADMIN_DIR / "badge_art_catalog.json", build_badge_art_catalog())


if __name__ == "__main__":
    main()
