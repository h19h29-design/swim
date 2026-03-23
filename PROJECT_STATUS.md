# PROJECT_STATUS

Date: 2026-03-06

## Scope Completed
- Kept project structure and implemented policy-hardening end-to-end.
- Applied strict inclusion policy: only
  1) text strict pair (`거리:` + `시간:`), or
  2) image pair (distance+duration from image OCR/template).
- Updated parser score rules exactly:
  - strict only: 90
  - image only: 80
  - strict + image success: 100
  - image distance outlier (`<400` or `>2500`): 70 (still included)
- Fixed dashboard excluded/included rendering bug.
- Added and passed tests for parser/OCR/UI mapping.

## Files Modified
- Core:
  - `swimdash/parser.py`
  - `swimdash/ocr.py`
  - `swimdash/pipeline.py`
  - `swimdash/cli.py`
- UI:
  - `docs/assets/app.js`
- Tests:
  - `tests/test_parser.py`
  - `tests/test_ocr.py`
  - `tests/test_dashboard_ui_mapping.py` (new)
- Docs:
  - `README.md`
  - `CHANGELOG.md`
  - `PROJECT_STATUS.md`

## Mandatory Run Results
1. `python -m pytest -q`
- Result: `27 passed, 1 skipped`

2. `python -m swimdash debug-ocr --dir local_samples/images`
- Executed successfully.
- Current sample folder check:
  - Required target filenames (`samsung_1750m_13315*`, `samsung_550m_3149*`, `apple_825m_11216*`) are not present.
  - Existing local sample matches from filename-expected parser include:
    - `apple_1500_3505.png` -> match
    - `apple_1700_11116.png` -> match
    - `apple_600_4135.png` -> match
    - `apple_700_4443.png` -> match
    - `apple_1400_4510.jpg` -> match
    - `gamin_850_4229.png` -> match

3. `python -m swimdash incremental --lookback-days 3 --recent-pages 20 --rate-limit 0.55 --timeout 20`
- Executed successfully (long runtime due network retries).
- Final log: `pages=20`, `fetched=22`, `errors=0`, `lookback_days=3`.

4. `python -m swimdash rebuild`
- Executed successfully.

5. records/UI checks
- `docs/data/records.json`
  - total records: 133
  - `is_excluded=true`: 125 (non-zero)
  - included records: 8
  - included source types: `image_ocr_template_sum` only
  - included score distribution: `{80: 6, 70: 2}`
- UI mapping check
  - JS normalize/renderer check confirms excluded badge class is rendered for excluded rows.
  - Unit check: `tests/test_dashboard_ui_mapping.py` passed.

## Remaining Limits
- Some Samsung screenshots still fail to recover top distance reliably in poor-quality OCR cases.
- Because the exact user-target sample filenames were not present, those exact 3 target pairs could not be verified in this run.

## Next TODO
1. Add stronger Samsung top-number extraction (color-aware preprocessing for blue header).
2. Add stricter Apple distance panel filtering for edge cases like `apple_700_1654`.
3. Re-run debug validation on actual target files once present:
   - `samsung_1750m_13315`
   - `samsung_550m_3149`
   - `apple_825m_11216`
