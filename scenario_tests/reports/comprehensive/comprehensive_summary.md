# CoPro Calculator — Comprehensive Test Summary
Generated: 2026-03-26 22:13:05
Total scenarios run: **21**

## Overview
| Scenario | Cat | Budget | Currency | Top Financing % | Amount | Scenarios | Runtime (ms) |
|----------|-----|--------|----------|-----------------|--------|-----------|--------------|
| sweep_doc_al | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 24938 |
| sweep_doc_bg | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 25155 |
| sweep_doc_cy | SWEEP | 500,000 | EUR | 14.0% | EUR 70,000 | 15 | 28908 |
| sweep_doc_ee | SWEEP | 500,000 | EUR | 12.0% | EUR 60,000 | 15 | 20884 |
| sweep_doc_fi | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 19401 |
| sweep_doc_ge | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 18928 |
| sweep_doc_hr | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 17335 |
| sweep_doc_is | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 16529 |
| sweep_doc_lt | SWEEP | 500,000 | EUR | 12.0% | EUR 60,000 | 15 | 16116 |
| sweep_doc_lv | SWEEP | 500,000 | EUR | 12.0% | EUR 60,000 | 15 | 15915 |
| sweep_doc_ma | SWEEP | 500,000 | EUR | 0.0% | EUR 0 | 15 | 8262 |
| sweep_doc_me | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 16724 |
| sweep_doc_mk | SWEEP | 500,000 | EUR | 8.0% | EUR 40,000 | 15 | 16157 |
| sweep_doc_mt | SWEEP | 500,000 | EUR | 16.0% | EUR 80,000 | 15 | 16060 |
| sweep_doc_pt | SWEEP | 500,000 | EUR | 12.0% | EUR 60,000 | 15 | 16061 |
| sweep_doc_ro | SWEEP | 500,000 | EUR | 14.0% | EUR 70,000 | 15 | 15908 |
| sweep_doc_rs | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 16324 |
| sweep_doc_si | SWEEP | 500,000 | EUR | 10.0% | EUR 50,000 | 15 | 19903 |
| sweep_doc_sk | SWEEP | 500,000 | EUR | 13.2% | EUR 66,000 | 15 | 18619 |
| sweep_doc_tr | SWEEP | 500,000 | EUR | 12.0% | EUR 60,000 | 15 | 17287 |
| sweep_doc_ua | SWEEP | 500,000 | EUR | 12.0% | EUR 60,000 | 15 | 17031 |

## RED FLAGS
*None — all scenarios completed without critical issues.*

## WARNINGS
- **sweep_doc_al**: Slow scenario generation: 24938ms
- **sweep_doc_bg**: Slow scenario generation: 25155ms
- **sweep_doc_cy**: Slow scenario generation: 28908ms
- **sweep_doc_ee**: Slow scenario generation: 20884ms
- **sweep_doc_fi**: Slow scenario generation: 19401ms
- **sweep_doc_ge**: Slow scenario generation: 18928ms
- **sweep_doc_hr**: Slow scenario generation: 17335ms
- **sweep_doc_is**: Slow scenario generation: 16529ms
- **sweep_doc_lt**: Slow scenario generation: 16116ms
- **sweep_doc_lv**: Slow scenario generation: 15915ms
- **sweep_doc_ma**: Very low financing (0.0%) for 100% shoot in one country — check incentive coverage
- **sweep_doc_me**: Slow scenario generation: 16724ms
- **sweep_doc_mk**: Slow scenario generation: 16157ms
- **sweep_doc_mt**: Slow scenario generation: 16060ms
- **sweep_doc_pt**: Slow scenario generation: 16061ms
- **sweep_doc_ro**: Slow scenario generation: 15908ms
- **sweep_doc_rs**: Slow scenario generation: 16324ms
- **sweep_doc_si**: Slow scenario generation: 19903ms
- **sweep_doc_sk**: Slow scenario generation: 18619ms
- **sweep_doc_tr**: Slow scenario generation: 17287ms
- **sweep_doc_ua**: Slow scenario generation: 17031ms

## Country Coverage
Countries that appeared as eligible incentive sources in the top scenario:

| Country | Scenarios where eligible |
|---------|--------------------------|
| AL | sweep_doc_al |
| BG | sweep_doc_bg |
| CY | sweep_doc_cy |
| EE | sweep_doc_ee |
| FI | sweep_doc_fi |
| GE | sweep_doc_ge |
| HR | sweep_doc_hr |
| IS | sweep_doc_is |
| LT | sweep_doc_lt |
| LV | sweep_doc_lv |
| ME | sweep_doc_me |
| MK | sweep_doc_mk |
| MT | sweep_doc_mt |
| PT | sweep_doc_pt |
| RO | sweep_doc_ro |
| RS | sweep_doc_rs |
| SI | sweep_doc_si |
| SK | sweep_doc_sk |
| TR | sweep_doc_tr |
| UA | sweep_doc_ua |

## Incentive Hit Rate
Incentives that fired (had benefit > 0) across all scenarios:

| Incentive | Times Fired |
|-----------|-------------|
| Albania Film Production Incentive | 1 |
| Bulgaria Cash Rebate Programme | 1 |
| Cyprus Cash Rebate Scheme for Film and TV | 1 |
| Estonia Cash Rebate for Film Production | 1 |
| Finland Production Incentive | 1 |
| Georgia Cash Rebate for Film Production | 1 |
| Croatia Cash Rebate for Film and TV | 1 |
| Iceland Film Reimbursement | 1 |
| Lithuania Tax Incentive for Film Production | 1 |
| Latvia Cash Rebate for Film Production | 1 |
| Montenegro Cash Rebate for Film Production | 1 |
| North Macedonia Cash Rebate for Film and TV | 1 |
| Malta Cash Rebate Programme | 1 |
| Portugal Cash Rebate for Film and TV | 1 |
| Romania Cash Rebate Programme | 1 |
| Serbia Cash Rebate for Film and TV | 1 |
| Slovenia Cash Rebate for Film and TV | 1 |
| Slovakia Cash Rebate Programme | 1 |
| Turkey Film Production Incentive | 1 |
| Ukraine Cash Rebate for Audiovisual Production | 1 |

## Countries With Zero Eligible Incentives
Countries used as shoot locations that never produced eligible incentives:

- Morocco (MA) in scenario 'sweep_doc_ma'

## Near-Miss Summary
Most common near-misses across all scenarios:

| Incentive | Near-Miss Count |
|-----------|-----------------|
| Bulgaria Cash Rebate Programme | 1 |
| Portugal Cash Rebate for Film and TV | 1 |
| Serbia Cash Rebate for Film and TV | 1 |
| Ukraine Cash Rebate for Audiovisual Production | 1 |
