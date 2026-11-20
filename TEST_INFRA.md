# E2E Test Infra: Video Agent

## Test Philosophy
- **Opaque-Box & Requirement-Driven**: Tests are designed directly from `ORIGINAL_REQUEST.md` and public CLI/API interface specifications in `PROJECT.md`. They verify externally observable behaviors (CLI options, output video files, media formats, audio-video synchronization, subtitles, metadata JSON schemas, diagnostic reports) without assuming internal implementation details.
- **Methodology**: 4-Tier verification incorporating Category-Partition, Boundary Value Analysis (BVA), Pairwise Combinatorial Testing, and Realistic Workload Application Scenarios.
- **Progressive Testability**: Verification checks are structured so that earlier tests provide pass/fail signals independently of later stage rendering complexity.

## Feature Inventory
Mapping all 15 features from `PROJECT.md` to requirements and test coverage tiers:

| # | Feature | Source (requirement) | Tier 1 (Min 5) | Tier 2 (Min 5) | Tier 3 (Pairwise) | Tier 4 (Scenario) |
|---|---------|---------------------|:--------------:|:--------------:|:-----------------:|:-----------------:|
| 1 | Global Tooling Setup & Verification | ORIGINAL_REQUEST R1, AC-1 | 5 | 5 | ✓ | ✓ |
| 2 | Environment Doctor & Diagnostics | ORIGINAL_REQUEST R1, AC-1 | 5 | 5 | ✓ | ✓ |
| 3 | Topic Research & Knowledge Engine | ORIGINAL_REQUEST R2, AC-2 | 5 | 5 | ✓ | ✓ |
| 4 | Multi-Option Script Generation | ORIGINAL_REQUEST R2, R3, AC-2 | 5 | 5 | ✓ | ✓ |
| 5 | Voiceover Synthesis & Timing Sync | ORIGINAL_REQUEST R2, AC-3 | 5 | 5 | ✓ | ✓ |
| 6 | Subtitle Generator & Master Clock | ORIGINAL_REQUEST R2, AC-3 | 5 | 5 | ✓ | ✓ |
| 7 | Programmatic Animation Engine | ORIGINAL_REQUEST R2, AC-4 | 5 | 5 | ✓ | ✓ |
| 8 | Terminal Code Execution Recorder | ORIGINAL_REQUEST R2, AC-4 | 5 | 5 | ✓ | ✓ |
| 9 | Dual-Format Composition Engine | ORIGINAL_REQUEST R2, AC-5 | 5 | 5 | ✓ | ✓ |
| 10 | Vertical Reel Formatter (9:16) | ORIGINAL_REQUEST R2, AC-5 | 5 | 5 | ✓ | ✓ |
| 11 | Horizontal Video Formatter (16:9) | ORIGINAL_REQUEST R2, AC-5 | 5 | 5 | ✓ | ✓ |
| 12 | Interactive CLI & Multi-Option UI | ORIGINAL_REQUEST R3, AC-6 | 5 | 5 | ✓ | ✓ |
| 13 | Interactive & Non-Interactive Selection | ORIGINAL_REQUEST R3, AC-6 | 5 | 5 | ✓ | ✓ |
| 14 | Project Delivery & Metadata Storage | ORIGINAL_REQUEST R3, AC-7 | 5 | 5 | ✓ | ✓ |
| 15 | E2E Acceptance & Quality Verification | ORIGINAL_REQUEST AC-1 to AC-7 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Test Runner**: `pytest`
- **Invocation**:
  - Full suite: `pytest tests/ -v`
  - Specific category: `pytest tests/test_r1_environment.py -v`
  - Marker selection: `pytest -m "tier1"` or `pytest -m "e2e"`
- **Pass/Fail Semantics**: Standard pytest exit code 0 on all tests passed; exit code >0 on any failure.
- **Directory Layout**:
  ```
  c:\Users\anike\Desktop\Video Agent\tests\
  ├── conftest.py              # Shared fixtures, test runners, media mocks & helpers
  ├── test_r1_environment.py   # Features 1 & 2: Global tooling, CLI doctor, runtime diagnostics
  ├── test_r2_pipeline.py      # Features 3-11: Research, scriptwriting, voiceover, subtitles, visuals, compositor
  ├── test_r3_cli.py           # Features 12-14: CLI options, selection UI, non-interactive flags, artifact delivery
  └── test_e2e_pipeline.py     # Feature 15 & Tier 4: End-to-end user workflows and full real-world scenarios
  ```

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity | Target Output |
|---|----------|--------------------|------------|---------------|
| 1 | Python Data Science Reel | F1, F3, F4, F5, F6, F7, F8, F9, F10, F12, F13, F14 | High | 9:16 Vertical Reel (1080x1920) with NumPy code demo & animated graphs |
| 2 | Web Architecture Explainer Video | F1, F3, F4, F5, F6, F7, F9, F11, F12, F13, F14 | High | 16:9 Horizontal Widescreen (1920x1080) with animated diagram & voiceover |
| 3 | CLI Developer Quickstart Reel | F1, F3, F4, F5, F6, F8, F9, F10, F12, F13, F14 | Medium | 9:16 Vertical Reel with terminal CLI command recording |
| 4 | Dual-Format Multi-Option Selection Run | F1, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12, F13, F14, F15 | High | Both 9:16 & 16:9 rendered MP4s + full research.json & script.json |
| 5 | Non-Interactive Headless Batch Pipeline | F1, F2, F3, F4, F5, F6, F9, F10, F13, F14, F15 | Medium | Automated execution via `--select 1 --format 9:16 --output output/` |

## Coverage Thresholds
- **Tier 1 - Feature Coverage**: ≥5 test cases per feature (15 features × 5 = ≥75 test cases)
- **Tier 2 - Boundary & Corner Cases**: ≥5 test cases per feature covering boundaries (15 features × 5 = ≥75 test cases)
- **Tier 3 - Cross-Feature Combinations**: Pairwise combination test cases across modules (≥15 test cases)
- **Tier 4 - Real-World Application Scenarios**: ≥5 comprehensive application-level scenario tests
- **Total Minimum Target**: ≥170 test cases
