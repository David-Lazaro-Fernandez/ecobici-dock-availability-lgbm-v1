# M6: salida completa de la prueba final

Generada el 2026-10-07 con `uv run python -m ecobici.eval.test_report` (commit a226b54), en su única corrida. Resumen e interpretación en [M6_test.md](M6_test.md).

Estaciones que solo aparecen en los meses de prueba (sin filas): 2

# Prueba: 2026-01 (2026-01-01T06:00 → 2026-02-01T06:00 UTC)

Filas de saturadas + pico calibradas con el Platt fijo (sin ventana semanal): 15 min 0%, 30 min 0%, 45 min 0%

## Resultados (2026-01)

`(ref)`: mejor línea base fijada de antemano (ajustada con TRAIN). `(ref justa)`: mejor de todas, incluidas `_tvf` (TRAIN + VAL_FIT) e `_iso` (recalibrada en VAL_FIT).

| Horizon | Segment | n | Base rate | Model | Brier | Log loss | BSS (ref) | BSS (ref justa) |
|---|---|---|---|---|---|---|---|---|
| 15 min | all | 1,345,168 | 0.026 | p_persist | 0.0101 | 0.1394 | -0.189 | -0.191 |
| 15 min | all | 1,345,168 | 0.026 | p_persist_cal (ref) | 0.0085 | 0.0398 | +0.000 | -0.002 |
| 15 min | all | 1,345,168 | 0.026 | p_hist | 0.0230 | 0.1015 | -1.712 | -1.716 |
| 15 min | all | 1,345,168 | 0.026 | p_persist_cal_tvf (ref justa) | 0.0085 | 0.0397 | +0.002 | +0.000 |
| 15 min | all | 1,345,168 | 0.026 | p_hist_tvf | 0.0228 | 0.0983 | -1.687 | -1.692 |
| 15 min | all | 1,345,168 | 0.026 | p_persist_cal_iso | 0.0085 | 0.0395 | +0.002 | -0.000 |
| 15 min | all | 1,345,168 | 0.026 | p_hist_iso | 0.0228 | 0.0917 | -1.692 | -1.697 |
| 15 min | all | 1,345,168 | 0.026 | p_lgbm_raw | 0.0070 | 0.0239 | +0.180 | +0.179 |
| 15 min | all | 1,345,168 | 0.026 | p_lgbm | 0.0069 | 0.0239 | +0.181 | +0.179 |
| 15 min | all | 1,345,168 | 0.026 | p_lgbm_recal | 0.0069 | 0.0239 | +0.180 | +0.179 |
| 15 min | all | 1,345,168 | 0.026 | p_lgbm_sub | 0.0069 | 0.0239 | +0.181 | +0.179 |
| 15 min | all | 1,345,168 | 0.026 | p_lgbm_sub_roll | 0.0069 | 0.0239 | +0.181 | +0.179 |
| 15 min | peak | 102,948 | 0.028 | p_persist | 0.0200 | 0.2766 | -0.224 | -0.225 |
| 15 min | peak | 102,948 | 0.028 | p_persist_cal (ref) | 0.0164 | 0.0691 | +0.000 | -0.000 |
| 15 min | peak | 102,948 | 0.028 | p_hist | 0.0260 | 0.1117 | -0.588 | -0.589 |
| 15 min | peak | 102,948 | 0.028 | p_persist_cal_tvf (ref justa) | 0.0163 | 0.0691 | +0.000 | +0.000 |
| 15 min | peak | 102,948 | 0.028 | p_hist_tvf | 0.0254 | 0.1080 | -0.550 | -0.551 |
| 15 min | peak | 102,948 | 0.028 | p_persist_cal_iso | 0.0164 | 0.0696 | -0.002 | -0.002 |
| 15 min | peak | 102,948 | 0.028 | p_hist_iso | 0.0246 | 0.0955 | -0.506 | -0.507 |
| 15 min | peak | 102,948 | 0.028 | p_lgbm_raw | 0.0128 | 0.0412 | +0.215 | +0.215 |
| 15 min | peak | 102,948 | 0.028 | p_lgbm | 0.0128 | 0.0412 | +0.215 | +0.215 |
| 15 min | peak | 102,948 | 0.028 | p_lgbm_recal | 0.0129 | 0.0414 | +0.212 | +0.212 |
| 15 min | peak | 102,948 | 0.028 | p_lgbm_sub | 0.0128 | 0.0413 | +0.215 | +0.214 |
| 15 min | peak | 102,948 | 0.028 | p_lgbm_sub_roll | 0.0128 | 0.0412 | +0.215 | +0.215 |
| 15 min | saturated | 225,968 | 0.032 | p_persist | 0.0254 | 0.3509 | -0.274 | -0.276 |
| 15 min | saturated | 225,968 | 0.032 | p_persist_cal (ref) | 0.0199 | 0.0882 | +0.000 | -0.002 |
| 15 min | saturated | 225,968 | 0.032 | p_hist | 0.0298 | 0.1163 | -0.495 | -0.497 |
| 15 min | saturated | 225,968 | 0.032 | p_persist_cal_tvf | 0.0199 | 0.0879 | +0.002 | -0.000 |
| 15 min | saturated | 225,968 | 0.032 | p_hist_tvf | 0.0293 | 0.1138 | -0.469 | -0.471 |
| 15 min | saturated | 225,968 | 0.032 | p_persist_cal_iso (ref justa) | 0.0199 | 0.0875 | +0.002 | +0.000 |
| 15 min | saturated | 225,968 | 0.032 | p_hist_iso | 0.0286 | 0.1107 | -0.433 | -0.435 |
| 15 min | saturated | 225,968 | 0.032 | p_lgbm_raw | 0.0162 | 0.0525 | +0.185 | +0.184 |
| 15 min | saturated | 225,968 | 0.032 | p_lgbm | 0.0162 | 0.0525 | +0.186 | +0.184 |
| 15 min | saturated | 225,968 | 0.032 | p_lgbm_recal | 0.0163 | 0.0526 | +0.183 | +0.182 |
| 15 min | saturated | 225,968 | 0.032 | p_lgbm_sub | 0.0162 | 0.0525 | +0.185 | +0.184 |
| 15 min | saturated | 225,968 | 0.032 | p_lgbm_sub_roll | 0.0162 | 0.0525 | +0.186 | +0.184 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_persist | 0.0907 | 1.2531 | -0.218 | -0.219 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_persist_cal (ref) | 0.0745 | 0.2882 | +0.000 | -0.001 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_hist | 0.1187 | 0.3930 | -0.594 | -0.595 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_persist_cal_tvf (ref justa) | 0.0744 | 0.2890 | +0.001 | +0.000 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_hist_tvf | 0.1154 | 0.3844 | -0.549 | -0.550 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_persist_cal_iso | 0.0746 | 0.2932 | -0.002 | -0.003 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_hist_iso | 0.1110 | 0.3705 | -0.490 | -0.491 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_lgbm_raw | 0.0568 | 0.1747 | +0.237 | +0.237 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_lgbm | 0.0568 | 0.1746 | +0.238 | +0.237 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_lgbm_recal | 0.0570 | 0.1752 | +0.235 | +0.234 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_lgbm_sub | 0.0568 | 0.1748 | +0.237 | +0.237 |
| 15 min | saturated_peak | 17,298 | 0.127 | p_lgbm_sub_roll | 0.0567 | 0.1747 | +0.238 | +0.238 |
| 30 min | all | 1,420,604 | 0.026 | p_persist | 0.0141 | 0.1943 | -0.247 | -0.250 |
| 30 min | all | 1,420,604 | 0.026 | p_persist_cal (ref) | 0.0113 | 0.0514 | +0.000 | -0.002 |
| 30 min | all | 1,420,604 | 0.026 | p_hist | 0.0228 | 0.1015 | -1.025 | -1.030 |
| 30 min | all | 1,420,604 | 0.026 | p_persist_cal_tvf | 0.0113 | 0.0512 | +0.002 | -0.000 |
| 30 min | all | 1,420,604 | 0.026 | p_hist_tvf | 0.0226 | 0.0983 | -1.007 | -1.012 |
| 30 min | all | 1,420,604 | 0.026 | p_persist_cal_iso (ref justa) | 0.0112 | 0.0509 | +0.002 | +0.000 |
| 30 min | all | 1,420,604 | 0.026 | p_hist_iso | 0.0227 | 0.0913 | -1.011 | -1.016 |
| 30 min | all | 1,420,604 | 0.026 | p_lgbm_raw | 0.0090 | 0.0315 | +0.198 | +0.196 |
| 30 min | all | 1,420,604 | 0.026 | p_lgbm | 0.0090 | 0.0314 | +0.199 | +0.197 |
| 30 min | all | 1,420,604 | 0.026 | p_lgbm_recal | 0.0090 | 0.0313 | +0.201 | +0.199 |
| 30 min | all | 1,420,604 | 0.026 | p_lgbm_sub | 0.0090 | 0.0314 | +0.199 | +0.197 |
| 30 min | all | 1,420,604 | 0.026 | p_lgbm_sub_roll | 0.0090 | 0.0314 | +0.199 | +0.197 |
| 30 min | peak | 104,976 | 0.028 | p_persist | 0.0261 | 0.3601 | -0.273 | -0.273 |
| 30 min | peak | 104,976 | 0.028 | p_persist_cal (ref) | 0.0205 | 0.0852 | +0.000 | -0.000 |
| 30 min | peak | 104,976 | 0.028 | p_hist | 0.0259 | 0.1112 | -0.265 | -0.266 |
| 30 min | peak | 104,976 | 0.028 | p_persist_cal_tvf (ref justa) | 0.0205 | 0.0853 | +0.000 | +0.000 |
| 30 min | peak | 104,976 | 0.028 | p_hist_tvf | 0.0253 | 0.1075 | -0.235 | -0.235 |
| 30 min | peak | 104,976 | 0.028 | p_persist_cal_iso | 0.0205 | 0.0862 | -0.002 | -0.002 |
| 30 min | peak | 104,976 | 0.028 | p_hist_iso | 0.0246 | 0.0952 | -0.200 | -0.200 |
| 30 min | peak | 104,976 | 0.028 | p_lgbm_raw | 0.0161 | 0.0532 | +0.212 | +0.212 |
| 30 min | peak | 104,976 | 0.028 | p_lgbm | 0.0161 | 0.0532 | +0.212 | +0.212 |
| 30 min | peak | 104,976 | 0.028 | p_lgbm_recal | 0.0162 | 0.0534 | +0.210 | +0.210 |
| 30 min | peak | 104,976 | 0.028 | p_lgbm_sub | 0.0161 | 0.0533 | +0.212 | +0.212 |
| 30 min | peak | 104,976 | 0.028 | p_lgbm_sub_roll | 0.0162 | 0.0534 | +0.211 | +0.211 |
| 30 min | saturated | 238,654 | 0.030 | p_persist | 0.0316 | 0.4361 | -0.377 | -0.381 |
| 30 min | saturated | 238,654 | 0.030 | p_persist_cal (ref) | 0.0229 | 0.1014 | +0.000 | -0.003 |
| 30 min | saturated | 238,654 | 0.030 | p_hist | 0.0285 | 0.1122 | -0.242 | -0.246 |
| 30 min | saturated | 238,654 | 0.030 | p_persist_cal_tvf | 0.0229 | 0.1009 | +0.002 | -0.001 |
| 30 min | saturated | 238,654 | 0.030 | p_hist_tvf | 0.0280 | 0.1097 | -0.220 | -0.224 |
| 30 min | saturated | 238,654 | 0.030 | p_persist_cal_iso (ref justa) | 0.0229 | 0.1003 | +0.003 | +0.000 |
| 30 min | saturated | 238,654 | 0.030 | p_hist_iso | 0.0273 | 0.1064 | -0.190 | -0.194 |
| 30 min | saturated | 238,654 | 0.030 | p_lgbm_raw | 0.0187 | 0.0618 | +0.185 | +0.182 |
| 30 min | saturated | 238,654 | 0.030 | p_lgbm | 0.0187 | 0.0617 | +0.185 | +0.183 |
| 30 min | saturated | 238,654 | 0.030 | p_lgbm_recal | 0.0187 | 0.0619 | +0.183 | +0.180 |
| 30 min | saturated | 238,654 | 0.030 | p_lgbm_sub | 0.0187 | 0.0617 | +0.185 | +0.183 |
| 30 min | saturated | 238,654 | 0.030 | p_lgbm_sub_roll | 0.0187 | 0.0618 | +0.185 | +0.182 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_persist | 0.1168 | 1.6134 | -0.257 | -0.258 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_persist_cal (ref) | 0.0929 | 0.3523 | +0.000 | -0.000 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_hist | 0.1189 | 0.3937 | -0.280 | -0.280 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_persist_cal_tvf (ref justa) | 0.0929 | 0.3536 | +0.000 | +0.000 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_hist_tvf | 0.1156 | 0.3852 | -0.244 | -0.245 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_persist_cal_iso | 0.0932 | 0.3603 | -0.003 | -0.003 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_hist_iso | 0.1111 | 0.3710 | -0.197 | -0.197 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_lgbm_raw | 0.0715 | 0.2238 | +0.230 | +0.230 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_lgbm | 0.0715 | 0.2234 | +0.231 | +0.230 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_lgbm_recal | 0.0717 | 0.2242 | +0.228 | +0.228 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_lgbm_sub | 0.0715 | 0.2237 | +0.231 | +0.230 |
| 30 min | saturated_peak | 17,640 | 0.128 | p_lgbm_sub_roll | 0.0716 | 0.2243 | +0.229 | +0.229 |
| 45 min | all | 1,407,155 | 0.025 | p_persist | 0.0167 | 0.2302 | -0.300 | -0.303 |
| 45 min | all | 1,407,155 | 0.025 | p_persist_cal (ref) | 0.0128 | 0.0576 | +0.000 | -0.002 |
| 45 min | all | 1,407,155 | 0.025 | p_hist | 0.0220 | 0.0997 | -0.719 | -0.723 |
| 45 min | all | 1,407,155 | 0.025 | p_persist_cal_tvf (ref justa) | 0.0128 | 0.0574 | +0.002 | +0.000 |
| 45 min | all | 1,407,155 | 0.025 | p_hist_tvf | 0.0218 | 0.0965 | -0.704 | -0.707 |
| 45 min | all | 1,407,155 | 0.025 | p_persist_cal_iso | 0.0128 | 0.0571 | +0.002 | -0.001 |
| 45 min | all | 1,407,155 | 0.025 | p_hist_iso | 0.0218 | 0.0890 | -0.704 | -0.708 |
| 45 min | all | 1,407,155 | 0.025 | p_lgbm_raw | 0.0103 | 0.0364 | +0.197 | +0.195 |
| 45 min | all | 1,407,155 | 0.025 | p_lgbm | 0.0103 | 0.0363 | +0.199 | +0.197 |
| 45 min | all | 1,407,155 | 0.025 | p_lgbm_recal | 0.0102 | 0.0361 | +0.202 | +0.200 |
| 45 min | all | 1,407,155 | 0.025 | p_lgbm_sub | 0.0103 | 0.0363 | +0.199 | +0.197 |
| 45 min | all | 1,407,155 | 0.025 | p_lgbm_sub_roll | 0.0103 | 0.0363 | +0.199 | +0.197 |
| 45 min | peak | 106,966 | 0.026 | p_persist | 0.0276 | 0.3814 | -0.290 | -0.290 |
| 45 min | peak | 106,966 | 0.026 | p_persist_cal (ref, ref justa) | 0.0214 | 0.0903 | +0.000 | +0.000 |
| 45 min | peak | 106,966 | 0.026 | p_hist | 0.0248 | 0.1091 | -0.160 | -0.160 |
| 45 min | peak | 106,966 | 0.026 | p_persist_cal_tvf | 0.0214 | 0.0905 | -0.001 | -0.001 |
| 45 min | peak | 106,966 | 0.026 | p_hist_tvf | 0.0242 | 0.1053 | -0.130 | -0.130 |
| 45 min | peak | 106,966 | 0.026 | p_persist_cal_iso | 0.0214 | 0.0912 | -0.002 | -0.002 |
| 45 min | peak | 106,966 | 0.026 | p_hist_iso | 0.0234 | 0.0921 | -0.093 | -0.093 |
| 45 min | peak | 106,966 | 0.026 | p_lgbm_raw | 0.0171 | 0.0584 | +0.199 | +0.199 |
| 45 min | peak | 106,966 | 0.026 | p_lgbm | 0.0171 | 0.0583 | +0.202 | +0.202 |
| 45 min | peak | 106,966 | 0.026 | p_lgbm_recal | 0.0172 | 0.0586 | +0.198 | +0.198 |
| 45 min | peak | 106,966 | 0.026 | p_lgbm_sub | 0.0171 | 0.0583 | +0.203 | +0.203 |
| 45 min | peak | 106,966 | 0.026 | p_lgbm_sub_roll | 0.0171 | 0.0586 | +0.200 | +0.200 |
| 45 min | saturated | 236,397 | 0.030 | p_persist | 0.0363 | 0.5011 | -0.463 | -0.468 |
| 45 min | saturated | 236,397 | 0.030 | p_persist_cal (ref) | 0.0248 | 0.1097 | +0.000 | -0.003 |
| 45 min | saturated | 236,397 | 0.030 | p_hist | 0.0283 | 0.1122 | -0.141 | -0.145 |
| 45 min | saturated | 236,397 | 0.030 | p_persist_cal_tvf | 0.0247 | 0.1092 | +0.002 | -0.001 |
| 45 min | saturated | 236,397 | 0.030 | p_hist_tvf | 0.0278 | 0.1095 | -0.121 | -0.125 |
| 45 min | saturated | 236,397 | 0.030 | p_persist_cal_iso (ref justa) | 0.0247 | 0.1084 | +0.003 | +0.000 |
| 45 min | saturated | 236,397 | 0.030 | p_hist_iso | 0.0271 | 0.1062 | -0.092 | -0.096 |
| 45 min | saturated | 236,397 | 0.030 | p_lgbm_raw | 0.0204 | 0.0693 | +0.176 | +0.173 |
| 45 min | saturated | 236,397 | 0.030 | p_lgbm | 0.0204 | 0.0691 | +0.178 | +0.175 |
| 45 min | saturated | 236,397 | 0.030 | p_lgbm_recal | 0.0205 | 0.0694 | +0.175 | +0.172 |
| 45 min | saturated | 236,397 | 0.030 | p_lgbm_sub | 0.0204 | 0.0691 | +0.178 | +0.176 |
| 45 min | saturated | 236,397 | 0.030 | p_lgbm_sub_roll | 0.0204 | 0.0692 | +0.177 | +0.174 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_persist | 0.1198 | 1.6551 | -0.262 | -0.262 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_persist_cal (ref, ref justa) | 0.0949 | 0.3619 | +0.000 | +0.000 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_hist | 0.1120 | 0.3746 | -0.180 | -0.180 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_persist_cal_tvf | 0.0950 | 0.3636 | -0.001 | -0.001 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_hist_tvf | 0.1086 | 0.3656 | -0.144 | -0.144 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_persist_cal_iso | 0.0953 | 0.3703 | -0.004 | -0.004 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_hist_iso | 0.1038 | 0.3509 | -0.093 | -0.093 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_lgbm_raw | 0.0745 | 0.2399 | +0.215 | +0.215 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_lgbm | 0.0742 | 0.2386 | +0.219 | +0.219 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_lgbm_recal | 0.0745 | 0.2394 | +0.215 | +0.215 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_lgbm_sub | 0.0740 | 0.2385 | +0.221 | +0.221 |
| 45 min | saturated_peak | 17,972 | 0.117 | p_lgbm_sub_roll | 0.0743 | 0.2400 | +0.217 | +0.217 |

## Intervalos de confianza (bootstrap por bloques, 1000 réplicas, IC 95 %)

### BSS de p_lgbm y p_lgbm_sub_roll

| Horizon | Segment | Modelo | Referencia | Bloque | Bloques | BSS | IC 95 % |
|---|---|---|---|---|---|---|---|
| 15 min | all | p_lgbm | p_persist_cal (pre-registered) | day | 31 | +0.181 | [+0.170, +0.191] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 31 | +0.181 | [+0.170, +0.191] |
| 15 min | all | p_lgbm | p_persist_cal_tvf (fair) | day | 31 | +0.179 | [+0.168, +0.190] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 31 | +0.179 | [+0.168, +0.190] |
| 15 min | all | p_lgbm | p_persist_cal (pre-registered) | station_day | 20,874 | +0.181 | [+0.174, +0.187] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 20,874 | +0.181 | [+0.174, +0.187] |
| 15 min | all | p_lgbm | p_persist_cal_tvf (fair) | station_day | 20,874 | +0.179 | [+0.173, +0.186] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 20,874 | +0.179 | [+0.173, +0.186] |
| 15 min | peak | p_lgbm | p_persist_cal (pre-registered) | day | 22 | +0.215 | [+0.184, +0.241] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 22 | +0.215 | [+0.186, +0.241] |
| 15 min | peak | p_lgbm | p_persist_cal_tvf (fair) | day | 22 | +0.215 | [+0.184, +0.241] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 22 | +0.215 | [+0.186, +0.240] |
| 15 min | peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 14,812 | +0.215 | [+0.198, +0.233] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 14,812 | +0.215 | [+0.199, +0.232] |
| 15 min | peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 14,812 | +0.215 | [+0.198, +0.232] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 14,812 | +0.215 | [+0.199, +0.232] |
| 15 min | saturated | p_lgbm | p_persist_cal (pre-registered) | day | 31 | +0.186 | [+0.172, +0.198] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 31 | +0.186 | [+0.173, +0.198] |
| 15 min | saturated | p_lgbm | p_persist_cal_iso (fair) | day | 31 | +0.184 | [+0.170, +0.197] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 31 | +0.184 | [+0.171, +0.197] |
| 15 min | saturated | p_lgbm | p_persist_cal (pre-registered) | station_day | 3,508 | +0.186 | [+0.176, +0.196] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 3,508 | +0.186 | [+0.176, +0.195] |
| 15 min | saturated | p_lgbm | p_persist_cal_iso (fair) | station_day | 3,508 | +0.184 | [+0.174, +0.194] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 3,508 | +0.184 | [+0.175, +0.194] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | day | 22 | +0.238 | [+0.208, +0.261] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 22 | +0.238 | [+0.212, +0.259] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | day | 22 | +0.237 | [+0.208, +0.260] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 22 | +0.238 | [+0.211, +0.258] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 2,490 | +0.238 | [+0.218, +0.256] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 2,490 | +0.238 | [+0.220, +0.254] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 2,490 | +0.237 | [+0.217, +0.255] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 2,490 | +0.238 | [+0.220, +0.254] |
| 30 min | all | p_lgbm | p_persist_cal (pre-registered) | day | 31 | +0.199 | [+0.190, +0.209] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 31 | +0.199 | [+0.190, +0.209] |
| 30 min | all | p_lgbm | p_persist_cal_iso (fair) | day | 31 | +0.197 | [+0.188, +0.207] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 31 | +0.197 | [+0.188, +0.207] |
| 30 min | all | p_lgbm | p_persist_cal (pre-registered) | station_day | 20,868 | +0.199 | [+0.192, +0.206] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 20,868 | +0.199 | [+0.192, +0.206] |
| 30 min | all | p_lgbm | p_persist_cal_iso (fair) | station_day | 20,868 | +0.197 | [+0.190, +0.204] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 20,868 | +0.197 | [+0.190, +0.204] |
| 30 min | peak | p_lgbm | p_persist_cal (pre-registered) | day | 22 | +0.212 | [+0.180, +0.239] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 22 | +0.211 | [+0.182, +0.234] |
| 30 min | peak | p_lgbm | p_persist_cal_tvf (fair) | day | 22 | +0.212 | [+0.180, +0.239] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 22 | +0.211 | [+0.183, +0.234] |
| 30 min | peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 14,812 | +0.212 | [+0.195, +0.229] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 14,812 | +0.211 | [+0.195, +0.226] |
| 30 min | peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 14,812 | +0.212 | [+0.195, +0.229] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 14,812 | +0.211 | [+0.195, +0.226] |
| 30 min | saturated | p_lgbm | p_persist_cal (pre-registered) | day | 31 | +0.185 | [+0.170, +0.200] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 31 | +0.185 | [+0.171, +0.198] |
| 30 min | saturated | p_lgbm | p_persist_cal_iso (fair) | day | 31 | +0.183 | [+0.167, +0.197] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 31 | +0.182 | [+0.168, +0.196] |
| 30 min | saturated | p_lgbm | p_persist_cal (pre-registered) | station_day | 3,507 | +0.185 | [+0.175, +0.195] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 3,507 | +0.185 | [+0.175, +0.195] |
| 30 min | saturated | p_lgbm | p_persist_cal_iso (fair) | station_day | 3,507 | +0.183 | [+0.172, +0.193] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 3,507 | +0.182 | [+0.172, +0.193] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | day | 22 | +0.231 | [+0.199, +0.257] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 22 | +0.229 | [+0.204, +0.251] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | day | 22 | +0.230 | [+0.198, +0.256] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 22 | +0.229 | [+0.204, +0.251] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 2,490 | +0.231 | [+0.210, +0.250] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 2,490 | +0.229 | [+0.212, +0.246] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 2,490 | +0.230 | [+0.210, +0.250] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 2,490 | +0.229 | [+0.211, +0.246] |
| 45 min | all | p_lgbm | p_persist_cal (pre-registered) | day | 31 | +0.199 | [+0.188, +0.210] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 31 | +0.199 | [+0.188, +0.210] |
| 45 min | all | p_lgbm | p_persist_cal_tvf (fair) | day | 31 | +0.197 | [+0.186, +0.208] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 31 | +0.197 | [+0.186, +0.208] |
| 45 min | all | p_lgbm | p_persist_cal (pre-registered) | station_day | 20,867 | +0.199 | [+0.191, +0.206] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 20,867 | +0.199 | [+0.192, +0.205] |
| 45 min | all | p_lgbm | p_persist_cal_tvf (fair) | station_day | 20,867 | +0.197 | [+0.190, +0.204] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 20,867 | +0.197 | [+0.190, +0.204] |
| 45 min | peak | p_lgbm | p_persist_cal (pre-registered) | day | 22 | +0.202 | [+0.167, +0.231] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 22 | +0.200 | [+0.170, +0.223] |
| 45 min | peak | p_lgbm | p_persist_cal (fair) | day | 22 | +0.202 | [+0.167, +0.231] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal (fair) | day | 22 | +0.200 | [+0.170, +0.223] |
| 45 min | peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 14,812 | +0.202 | [+0.182, +0.221] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 14,812 | +0.200 | [+0.183, +0.217] |
| 45 min | peak | p_lgbm | p_persist_cal (fair) | station_day | 14,812 | +0.202 | [+0.182, +0.221] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal (fair) | station_day | 14,812 | +0.200 | [+0.183, +0.217] |
| 45 min | saturated | p_lgbm | p_persist_cal (pre-registered) | day | 31 | +0.178 | [+0.161, +0.193] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 31 | +0.177 | [+0.163, +0.190] |
| 45 min | saturated | p_lgbm | p_persist_cal_iso (fair) | day | 31 | +0.175 | [+0.157, +0.191] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 31 | +0.174 | [+0.160, +0.188] |
| 45 min | saturated | p_lgbm | p_persist_cal (pre-registered) | station_day | 3,507 | +0.178 | [+0.167, +0.189] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 3,507 | +0.177 | [+0.167, +0.187] |
| 45 min | saturated | p_lgbm | p_persist_cal_iso (fair) | station_day | 3,507 | +0.175 | [+0.164, +0.186] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 3,507 | +0.174 | [+0.164, +0.184] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | day | 22 | +0.219 | [+0.180, +0.247] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 22 | +0.217 | [+0.193, +0.236] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal (fair) | day | 22 | +0.219 | [+0.180, +0.247] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (fair) | day | 22 | +0.217 | [+0.193, +0.236] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 2,490 | +0.219 | [+0.197, +0.240] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 2,490 | +0.217 | [+0.198, +0.234] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal (fair) | station_day | 2,490 | +0.219 | [+0.197, +0.240] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (fair) | station_day | 2,490 | +0.217 | [+0.198, +0.234] |

### Brecha de calibración en saturated_peak (meta ≤ 0.05)

La brecha es el máximo sobre los bins con n ≥ 1,000, así que el bootstrap la sesga hacia arriba: el IC es conservador.

| Horizon | Modelo | Bloque | Brecha | IC 95 % | Réplicas ≤ meta |
|---|---|---|---|---|---|
| 15 min | p_lgbm | day | 0.001 | [0.000, 0.002] | 100% |
| 15 min | p_lgbm | station_day | 0.001 | [0.000, 0.002] | 100% |
| 15 min | p_lgbm_recal | day | 0.001 | [0.000, 0.070] | 91% |
| 15 min | p_lgbm_recal | station_day | 0.001 | [0.000, 0.002] | 99% |
| 15 min | p_lgbm_sub | day | 0.002 | [0.000, 0.003] | 100% |
| 15 min | p_lgbm_sub | station_day | 0.002 | [0.000, 0.003] | 100% |
| 15 min | p_lgbm_sub_roll | day | 0.001 | [0.000, 0.003] | 100% |
| 15 min | p_lgbm_sub_roll | station_day | 0.001 | [0.000, 0.003] | 100% |
| 30 min | p_lgbm | day | 0.028 | [0.011, 0.083] | 73% |
| 30 min | p_lgbm | station_day | 0.028 | [0.012, 0.072] | 88% |
| 30 min | p_lgbm_recal | day | 0.052 | [0.014, 0.080] | 42% |
| 30 min | p_lgbm_recal | station_day | 0.052 | [0.030, 0.077] | 43% |
| 30 min | p_lgbm_sub | day | 0.032 | [0.014, 0.079] | 75% |
| 30 min | p_lgbm_sub | station_day | 0.032 | [0.016, 0.068] | 88% |
| 30 min | p_lgbm_sub_roll | day | 0.034 | [0.005, 0.070] | 78% |
| 30 min | p_lgbm_sub_roll | station_day | 0.034 | [0.010, 0.064] | 83% |
| 45 min | p_lgbm | day | 0.054 | [0.031, 0.084] | 31% |
| 45 min | p_lgbm | station_day | 0.054 | [0.036, 0.076] | 28% |
| 45 min | p_lgbm_recal | day | 0.053 | [0.027, 0.079] | 37% |
| 45 min | p_lgbm_recal | station_day | 0.053 | [0.033, 0.076] | 38% |
| 45 min | p_lgbm_sub | day | 0.034 | [0.016, 0.068] | 74% |
| 45 min | p_lgbm_sub | station_day | 0.034 | [0.022, 0.063] | 83% |
| 45 min | p_lgbm_sub_roll | day | 0.048 | [0.013, 0.080] | 53% |
| 45 min | p_lgbm_sub_roll | station_day | 0.048 | [0.021, 0.075] | 58% |

## Metas

| Horizon | Modelo | Meta | Valor | ¿Cumple? |
|---|---|---|---|---|
| 15 min | p_lgbm | BSS > 0, all | 0.181 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, all | 0.180 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, all | 0.181 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, all | 0.181 | ✅ |
| 15 min | p_lgbm | BSS > 0, peak | 0.215 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, peak | 0.212 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, peak | 0.215 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, peak | 0.215 | ✅ |
| 15 min | p_lgbm | BSS > 0, saturated | 0.186 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, saturated | 0.183 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, saturated | 0.185 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, saturated | 0.186 | ✅ |
| 15 min | p_lgbm | BSS > 0, saturated_peak | 0.238 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.235 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, saturated_peak | 0.237 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, saturated_peak | 0.238 | ✅ |
| 15 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.001 | ✅ |
| 15 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.001 | ✅ |
| 15 min | p_lgbm_sub | calibration gap <= 0.05, saturated_peak | 0.002 | ✅ |
| 15 min | p_lgbm_sub_roll | calibration gap <= 0.05, saturated_peak | 0.001 | ✅ |
| 30 min | p_lgbm | BSS > 0, all | 0.199 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, all | 0.201 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, all | 0.199 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, all | 0.199 | ✅ |
| 30 min | p_lgbm | BSS > 0, peak | 0.212 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, peak | 0.210 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, peak | 0.212 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, peak | 0.211 | ✅ |
| 30 min | p_lgbm | BSS > 0, saturated | 0.185 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, saturated | 0.183 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, saturated | 0.185 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, saturated | 0.185 | ✅ |
| 30 min | p_lgbm | BSS > 0, saturated_peak | 0.231 | ✅ |
| 30 min | p_lgbm | BSS >= 0.1, saturated_peak | 0.231 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.228 | ✅ |
| 30 min | p_lgbm_recal | BSS >= 0.1, saturated_peak | 0.228 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, saturated_peak | 0.231 | ✅ |
| 30 min | p_lgbm_sub | BSS >= 0.1, saturated_peak | 0.231 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, saturated_peak | 0.229 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS >= 0.1, saturated_peak | 0.229 | ✅ |
| 30 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.028 | ✅ |
| 30 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.052 | ❌ |
| 30 min | p_lgbm_sub | calibration gap <= 0.05, saturated_peak | 0.032 | ✅ |
| 30 min | p_lgbm_sub_roll | calibration gap <= 0.05, saturated_peak | 0.034 | ✅ |
| 45 min | p_lgbm | BSS > 0, all | 0.199 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, all | 0.202 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, all | 0.199 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, all | 0.199 | ✅ |
| 45 min | p_lgbm | BSS > 0, peak | 0.202 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, peak | 0.198 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, peak | 0.203 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, peak | 0.200 | ✅ |
| 45 min | p_lgbm | BSS > 0, saturated | 0.178 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, saturated | 0.175 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, saturated | 0.178 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, saturated | 0.177 | ✅ |
| 45 min | p_lgbm | BSS > 0, saturated_peak | 0.219 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.215 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, saturated_peak | 0.221 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, saturated_peak | 0.217 | ✅ |
| 45 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.054 | ❌ |
| 45 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.053 | ❌ |
| 45 min | p_lgbm_sub | calibration gap <= 0.05, saturated_peak | 0.034 | ✅ |
| 45 min | p_lgbm_sub_roll | calibration gap <= 0.05, saturated_peak | 0.048 | ✅ |

### 15 min: calibración en saturated_peak (p_lgbm)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 12,779 | 0.007 | 0.006 | [0.005, 0.008] |
| 1 | 646 | 0.150 | 0.135 | [0.113, 0.156] |
| 2 | 466 | 0.252 | 0.223 | [0.183, 0.264] |
| 3 | 477 | 0.343 | 0.312 | [0.274, 0.356] |
| 4 | 682 | 0.452 | 0.440 | [0.402, 0.479] |
| 5 | 767 | 0.556 | 0.510 | [0.476, 0.546] |
| 6 | 521 | 0.650 | 0.676 | [0.645, 0.708] |
| 7 | 594 | 0.732 | 0.739 | [0.704, 0.775] |
| 8 | 293 | 0.844 | 0.799 | [0.748, 0.841] |
| 9 | 73 | 0.915 | 0.904 | [0.823, 0.959] |

### 15 min: calibración en saturated_peak (p_lgbm_sub_roll)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 12,919 | 0.006 | 0.008 | [0.006, 0.010] |
| 1 | 634 | 0.142 | 0.155 | [0.121, 0.187] |
| 2 | 582 | 0.249 | 0.254 | [0.214, 0.296] |
| 3 | 555 | 0.363 | 0.375 | [0.339, 0.417] |
| 4 | 567 | 0.449 | 0.464 | [0.415, 0.512] |
| 5 | 671 | 0.545 | 0.557 | [0.529, 0.588] |
| 6 | 665 | 0.647 | 0.702 | [0.668, 0.732] |
| 7 | 351 | 0.737 | 0.729 | [0.693, 0.764] |
| 8 | 288 | 0.838 | 0.812 | [0.768, 0.853] |
| 9 | 66 | 0.914 | 0.894 | [0.804, 0.953] |

V8 (ECE, todas las estaciones): p_lgbm: centro 0.0009, periferia 0.0004; p_lgbm_recal: centro 0.0003, periferia 0.0005; p_lgbm_sub: centro 0.0009, periferia 0.0005; p_lgbm_sub_roll: centro 0.0009, periferia 0.0004. Árboles: 153; entrenamiento 1.6 min.

Importancia (ganancia): docks_now 74.0%, occupancy_now 11.0%, flow_arrivals_target 2.7%, flow_departures_target 2.5%, docks_lag15 2.0%, station 1.6%, bikes_now 1.6%, flow_net_window 1.4%, docks_lag60 0.5%, nb_full_frac 0.4%, minute_of_day 0.4%, flow_net_target 0.3%, nb_occupancy_mean 0.2%, full_lag15 0.2%, docks_delta60 0.2%

Rezagos presentes: 15 min 46.0%, 30 min 49.8%, 60 min 47.2%

### 30 min: calibración en saturated_peak (p_lgbm)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 11,807 | 0.013 | 0.012 | [0.009, 0.016] |
| 1 | 1,288 | 0.149 | 0.121 | [0.101, 0.143] |
| 2 | 961 | 0.259 | 0.203 | [0.169, 0.238] |
| 3 | 999 | 0.353 | 0.340 | [0.308, 0.377] |
| 4 | 959 | 0.445 | 0.426 | [0.382, 0.463] |
| 5 | 785 | 0.552 | 0.549 | [0.515, 0.586] |
| 6 | 418 | 0.649 | 0.641 | [0.605, 0.684] |
| 7 | 221 | 0.736 | 0.738 | [0.649, 0.801] |
| 8 | 202 | 0.838 | 0.767 | [0.683, 0.827] |

### 30 min: calibración en saturated_peak (p_lgbm_sub_roll)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 12,419 | 0.012 | 0.017 | [0.013, 0.022] |
| 1 | 1,154 | 0.146 | 0.153 | [0.124, 0.183] |
| 2 | 1,093 | 0.249 | 0.283 | [0.250, 0.318] |
| 3 | 982 | 0.352 | 0.378 | [0.334, 0.416] |
| 4 | 711 | 0.443 | 0.509 | [0.476, 0.547] |
| 5 | 565 | 0.543 | 0.568 | [0.530, 0.611] |
| 6 | 371 | 0.641 | 0.685 | [0.640, 0.727] |
| 7 | 176 | 0.745 | 0.710 | [0.601, 0.784] |
| 8 | 165 | 0.841 | 0.788 | [0.714, 0.849] |
| 9 | 4 | 0.906 | 1.000 | [1.000, 1.000] |

V8 (ECE, todas las estaciones): p_lgbm: centro 0.0014, periferia 0.0004; p_lgbm_recal: centro 0.0005, periferia 0.0006; p_lgbm_sub: centro 0.0014, periferia 0.0004; p_lgbm_sub_roll: centro 0.0014, periferia 0.0004. Árboles: 137; entrenamiento 1.4 min.

Importancia (ganancia): docks_now 66.9%, occupancy_now 12.2%, flow_net_window 4.1%, flow_departures_target 3.3%, station 2.6%, bikes_now 2.1%, docks_lag15 1.9%, flow_arrivals_target 1.7%, minute_of_day 1.2%, flow_net_target 0.7%, docks_lag60 0.5%, nb_full_frac 0.5%, nb_occupancy_mean 0.5%, st_full_rate 0.3%, docks_lag30 0.2%

Rezagos presentes: 15 min 45.4%, 30 min 50.3%, 60 min 47.0%

### 45 min: calibración en saturated_peak (p_lgbm)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 11,208 | 0.020 | 0.014 | [0.010, 0.019] |
| 1 | 2,042 | 0.142 | 0.116 | [0.095, 0.142] |
| 2 | 1,608 | 0.254 | 0.200 | [0.175, 0.225] |
| 3 | 1,243 | 0.352 | 0.311 | [0.271, 0.349] |
| 4 | 831 | 0.454 | 0.436 | [0.388, 0.473] |
| 5 | 459 | 0.543 | 0.521 | [0.482, 0.564] |
| 6 | 280 | 0.635 | 0.646 | [0.581, 0.712] |
| 7 | 247 | 0.750 | 0.680 | [0.592, 0.754] |
| 8 | 54 | 0.824 | 0.833 | [0.744, 0.929] |

### 45 min: calibración en saturated_peak (p_lgbm_sub_roll)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 12,786 | 0.017 | 0.025 | [0.019, 0.034] |
| 1 | 1,766 | 0.150 | 0.172 | [0.145, 0.198] |
| 2 | 1,397 | 0.248 | 0.296 | [0.259, 0.327] |
| 3 | 794 | 0.351 | 0.419 | [0.375, 0.455] |
| 4 | 534 | 0.446 | 0.504 | [0.462, 0.549] |
| 5 | 287 | 0.549 | 0.582 | [0.514, 0.650] |
| 6 | 174 | 0.648 | 0.672 | [0.609, 0.740] |
| 7 | 179 | 0.755 | 0.709 | [0.617, 0.796] |
| 8 | 55 | 0.829 | 0.745 | [0.663, 0.844] |

V8 (ECE, todas las estaciones): p_lgbm: centro 0.0018, periferia 0.0005; p_lgbm_recal: centro 0.0005, periferia 0.0006; p_lgbm_sub: centro 0.0019, periferia 0.0004; p_lgbm_sub_roll: centro 0.0018, periferia 0.0007. Árboles: 139; entrenamiento 1.4 min.

Importancia (ganancia): docks_now 62.6%, occupancy_now 11.8%, flow_net_window 6.4%, flow_departures_target 3.7%, station 3.7%, bikes_now 2.4%, docks_lag15 1.8%, minute_of_day 1.7%, flow_net_target 1.0%, flow_arrivals_target 1.0%, nb_occupancy_mean 0.6%, nb_full_frac 0.5%, docks_lag60 0.5%, st_full_rate 0.5%, target_slot 0.3%

Rezagos presentes: 15 min 44.3%, 30 min 48.1%, 60 min 46.5%
# Prueba: 2026-09 (2026-09-11T06:00 → 2026-10-01T06:00 UTC)

Filas de saturadas + pico calibradas con el Platt fijo (sin ventana semanal): 15 min 73%, 30 min 74%, 45 min 75%

## Resultados (2026-09)

`(ref)`: mejor línea base fijada de antemano (ajustada con TRAIN). `(ref justa)`: mejor de todas, incluidas `_tvf` (TRAIN + VAL_FIT) e `_iso` (recalibrada en VAL_FIT).

| Horizon | Segment | n | Base rate | Model | Brier | Log loss | BSS (ref) | BSS (ref justa) |
|---|---|---|---|---|---|---|---|---|
| 15 min | all | 1,539,781 | 0.017 | p_persist | 0.0074 | 0.1019 | -0.175 | -0.178 |
| 15 min | all | 1,539,781 | 0.017 | p_persist_cal (ref) | 0.0063 | 0.0308 | +0.000 | -0.003 |
| 15 min | all | 1,539,781 | 0.017 | p_hist | 0.0154 | 0.0703 | -1.450 | -1.457 |
| 15 min | all | 1,539,781 | 0.017 | p_persist_cal_tvf | 0.0063 | 0.0306 | +0.002 | -0.001 |
| 15 min | all | 1,539,781 | 0.017 | p_hist_tvf | 0.0152 | 0.0689 | -1.421 | -1.427 |
| 15 min | all | 1,539,781 | 0.017 | p_persist_cal_iso (ref justa) | 0.0063 | 0.0303 | +0.003 | +0.000 |
| 15 min | all | 1,539,781 | 0.017 | p_hist_iso | 0.0150 | 0.0646 | -1.385 | -1.392 |
| 15 min | all | 1,539,781 | 0.017 | p_lgbm_raw | 0.0052 | 0.0176 | +0.168 | +0.165 |
| 15 min | all | 1,539,781 | 0.017 | p_lgbm | 0.0052 | 0.0175 | +0.168 | +0.166 |
| 15 min | all | 1,539,781 | 0.017 | p_lgbm_recal | 0.0052 | 0.0175 | +0.168 | +0.166 |
| 15 min | all | 1,539,781 | 0.017 | p_lgbm_sub | 0.0052 | 0.0176 | +0.168 | +0.166 |
| 15 min | all | 1,539,781 | 0.017 | p_lgbm_sub_roll | 0.0052 | 0.0176 | +0.168 | +0.166 |
| 15 min | peak | 89,891 | 0.026 | p_persist | 0.0165 | 0.2285 | -0.175 | -0.175 |
| 15 min | peak | 89,891 | 0.026 | p_persist_cal (ref) | 0.0141 | 0.0588 | +0.000 | -0.001 |
| 15 min | peak | 89,891 | 0.026 | p_hist | 0.0231 | 0.0891 | -0.637 | -0.638 |
| 15 min | peak | 89,891 | 0.026 | p_persist_cal_tvf (ref justa) | 0.0141 | 0.0589 | +0.001 | +0.000 |
| 15 min | peak | 89,891 | 0.026 | p_hist_tvf | 0.0225 | 0.0865 | -0.595 | -0.596 |
| 15 min | peak | 89,891 | 0.026 | p_persist_cal_iso | 0.0141 | 0.0591 | -0.002 | -0.002 |
| 15 min | peak | 89,891 | 0.026 | p_hist_iso | 0.0218 | 0.0815 | -0.547 | -0.548 |
| 15 min | peak | 89,891 | 0.026 | p_lgbm_raw | 0.0107 | 0.0340 | +0.240 | +0.240 |
| 15 min | peak | 89,891 | 0.026 | p_lgbm | 0.0107 | 0.0340 | +0.242 | +0.241 |
| 15 min | peak | 89,891 | 0.026 | p_lgbm_recal | 0.0107 | 0.0340 | +0.241 | +0.240 |
| 15 min | peak | 89,891 | 0.026 | p_lgbm_sub | 0.0107 | 0.0342 | +0.238 | +0.237 |
| 15 min | peak | 89,891 | 0.026 | p_lgbm_sub_roll | 0.0107 | 0.0342 | +0.239 | +0.239 |
| 15 min | saturated | 260,578 | 0.027 | p_persist | 0.0193 | 0.2660 | -0.223 | -0.225 |
| 15 min | saturated | 260,578 | 0.027 | p_persist_cal (ref) | 0.0157 | 0.0733 | +0.000 | -0.002 |
| 15 min | saturated | 260,578 | 0.027 | p_hist | 0.0253 | 0.1051 | -0.610 | -0.612 |
| 15 min | saturated | 260,578 | 0.027 | p_persist_cal_tvf | 0.0157 | 0.0730 | +0.001 | -0.000 |
| 15 min | saturated | 260,578 | 0.027 | p_hist_tvf | 0.0249 | 0.1028 | -0.584 | -0.586 |
| 15 min | saturated | 260,578 | 0.027 | p_persist_cal_iso (ref justa) | 0.0157 | 0.0723 | +0.002 | +0.000 |
| 15 min | saturated | 260,578 | 0.027 | p_hist_iso | 0.0244 | 0.0987 | -0.551 | -0.553 |
| 15 min | saturated | 260,578 | 0.027 | p_lgbm_raw | 0.0131 | 0.0421 | +0.166 | +0.165 |
| 15 min | saturated | 260,578 | 0.027 | p_lgbm | 0.0131 | 0.0420 | +0.167 | +0.165 |
| 15 min | saturated | 260,578 | 0.027 | p_lgbm_recal | 0.0131 | 0.0420 | +0.167 | +0.166 |
| 15 min | saturated | 260,578 | 0.027 | p_lgbm_sub | 0.0131 | 0.0421 | +0.165 | +0.164 |
| 15 min | saturated | 260,578 | 0.027 | p_lgbm_sub_roll | 0.0131 | 0.0421 | +0.166 | +0.165 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_persist | 0.0821 | 1.1341 | -0.164 | -0.165 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_persist_cal (ref) | 0.0705 | 0.2718 | +0.000 | -0.001 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_hist | 0.1180 | 0.3909 | -0.672 | -0.673 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_persist_cal_tvf (ref justa) | 0.0705 | 0.2724 | +0.001 | +0.000 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_hist_tvf | 0.1147 | 0.3818 | -0.627 | -0.628 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_persist_cal_iso | 0.0708 | 0.2765 | -0.003 | -0.004 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_hist_iso | 0.1110 | 0.3700 | -0.574 | -0.575 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_lgbm_raw | 0.0530 | 0.1649 | +0.248 | +0.248 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_lgbm | 0.0529 | 0.1646 | +0.250 | +0.249 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_lgbm_recal | 0.0529 | 0.1643 | +0.249 | +0.249 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_lgbm_sub | 0.0533 | 0.1657 | +0.245 | +0.245 |
| 15 min | saturated_peak | 15,276 | 0.136 | p_lgbm_sub_roll | 0.0531 | 0.1655 | +0.247 | +0.246 |
| 30 min | all | 1,542,423 | 0.017 | p_persist | 0.0103 | 0.1423 | -0.247 | -0.251 |
| 30 min | all | 1,542,423 | 0.017 | p_persist_cal (ref) | 0.0083 | 0.0393 | +0.000 | -0.003 |
| 30 min | all | 1,542,423 | 0.017 | p_hist | 0.0153 | 0.0703 | -0.857 | -0.862 |
| 30 min | all | 1,542,423 | 0.017 | p_persist_cal_tvf | 0.0082 | 0.0391 | +0.002 | -0.001 |
| 30 min | all | 1,542,423 | 0.017 | p_hist_tvf | 0.0151 | 0.0688 | -0.834 | -0.839 |
| 30 min | all | 1,542,423 | 0.017 | p_persist_cal_iso (ref justa) | 0.0082 | 0.0387 | +0.003 | +0.000 |
| 30 min | all | 1,542,423 | 0.017 | p_hist_iso | 0.0149 | 0.0642 | -0.807 | -0.812 |
| 30 min | all | 1,542,423 | 0.017 | p_lgbm_raw | 0.0067 | 0.0231 | +0.184 | +0.182 |
| 30 min | all | 1,542,423 | 0.017 | p_lgbm | 0.0067 | 0.0229 | +0.185 | +0.182 |
| 30 min | all | 1,542,423 | 0.017 | p_lgbm_recal | 0.0067 | 0.0229 | +0.185 | +0.182 |
| 30 min | all | 1,542,423 | 0.017 | p_lgbm_sub | 0.0067 | 0.0230 | +0.184 | +0.182 |
| 30 min | all | 1,542,423 | 0.017 | p_lgbm_sub_roll | 0.0067 | 0.0230 | +0.184 | +0.182 |
| 30 min | peak | 89,195 | 0.024 | p_persist | 0.0206 | 0.2845 | -0.207 | -0.208 |
| 30 min | peak | 89,195 | 0.024 | p_persist_cal (ref) | 0.0171 | 0.0708 | +0.000 | -0.001 |
| 30 min | peak | 89,195 | 0.024 | p_hist | 0.0218 | 0.0868 | -0.281 | -0.281 |
| 30 min | peak | 89,195 | 0.024 | p_persist_cal_tvf (ref justa) | 0.0171 | 0.0709 | +0.001 | +0.000 |
| 30 min | peak | 89,195 | 0.024 | p_hist_tvf | 0.0212 | 0.0841 | -0.244 | -0.244 |
| 30 min | peak | 89,195 | 0.024 | p_persist_cal_iso | 0.0171 | 0.0712 | -0.003 | -0.003 |
| 30 min | peak | 89,195 | 0.024 | p_hist_iso | 0.0205 | 0.0782 | -0.200 | -0.201 |
| 30 min | peak | 89,195 | 0.024 | p_lgbm_raw | 0.0128 | 0.0422 | +0.248 | +0.248 |
| 30 min | peak | 89,195 | 0.024 | p_lgbm | 0.0128 | 0.0421 | +0.250 | +0.250 |
| 30 min | peak | 89,195 | 0.024 | p_lgbm_recal | 0.0128 | 0.0421 | +0.248 | +0.247 |
| 30 min | peak | 89,195 | 0.024 | p_lgbm_sub | 0.0128 | 0.0423 | +0.248 | +0.247 |
| 30 min | peak | 89,195 | 0.024 | p_lgbm_sub_roll | 0.0128 | 0.0422 | +0.249 | +0.248 |
| 30 min | saturated | 261,023 | 0.027 | p_persist | 0.0262 | 0.3615 | -0.328 | -0.332 |
| 30 min | saturated | 261,023 | 0.027 | p_persist_cal (ref) | 0.0197 | 0.0898 | +0.000 | -0.003 |
| 30 min | saturated | 261,023 | 0.027 | p_hist | 0.0252 | 0.1043 | -0.281 | -0.284 |
| 30 min | saturated | 261,023 | 0.027 | p_persist_cal_tvf | 0.0197 | 0.0894 | +0.002 | -0.001 |
| 30 min | saturated | 261,023 | 0.027 | p_hist_tvf | 0.0248 | 0.1021 | -0.260 | -0.264 |
| 30 min | saturated | 261,023 | 0.027 | p_persist_cal_iso (ref justa) | 0.0196 | 0.0885 | +0.003 | +0.000 |
| 30 min | saturated | 261,023 | 0.027 | p_hist_iso | 0.0243 | 0.0977 | -0.234 | -0.238 |
| 30 min | saturated | 261,023 | 0.027 | p_lgbm_raw | 0.0163 | 0.0532 | +0.172 | +0.170 |
| 30 min | saturated | 261,023 | 0.027 | p_lgbm | 0.0163 | 0.0531 | +0.171 | +0.169 |
| 30 min | saturated | 261,023 | 0.027 | p_lgbm_recal | 0.0163 | 0.0530 | +0.172 | +0.170 |
| 30 min | saturated | 261,023 | 0.027 | p_lgbm_sub | 0.0163 | 0.0531 | +0.170 | +0.168 |
| 30 min | saturated | 261,023 | 0.027 | p_lgbm_sub_roll | 0.0163 | 0.0531 | +0.170 | +0.168 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_persist | 0.0997 | 1.3777 | -0.187 | -0.188 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_persist_cal (ref) | 0.0840 | 0.3177 | +0.000 | -0.001 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_hist | 0.1107 | 0.3732 | -0.318 | -0.319 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_persist_cal_tvf (ref justa) | 0.0840 | 0.3186 | +0.001 | +0.000 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_hist_tvf | 0.1073 | 0.3632 | -0.277 | -0.278 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_persist_cal_iso | 0.0844 | 0.3239 | -0.004 | -0.005 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_hist_iso | 0.1031 | 0.3496 | -0.227 | -0.228 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_lgbm_raw | 0.0628 | 0.1981 | +0.253 | +0.252 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_lgbm | 0.0626 | 0.1973 | +0.255 | +0.255 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_lgbm_recal | 0.0628 | 0.1974 | +0.252 | +0.252 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_lgbm_sub | 0.0629 | 0.1985 | +0.252 | +0.251 |
| 30 min | saturated_peak | 15,162 | 0.123 | p_lgbm_sub_roll | 0.0628 | 0.1983 | +0.253 | +0.252 |
| 45 min | all | 1,532,952 | 0.017 | p_persist | 0.0135 | 0.1869 | -0.329 | -0.333 |
| 45 min | all | 1,532,952 | 0.017 | p_persist_cal (ref) | 0.0102 | 0.0472 | +0.000 | -0.003 |
| 45 min | all | 1,532,952 | 0.017 | p_hist | 0.0152 | 0.0699 | -0.498 | -0.503 |
| 45 min | all | 1,532,952 | 0.017 | p_persist_cal_tvf | 0.0102 | 0.0470 | +0.002 | -0.001 |
| 45 min | all | 1,532,952 | 0.017 | p_hist_tvf | 0.0151 | 0.0687 | -0.481 | -0.486 |
| 45 min | all | 1,532,952 | 0.017 | p_persist_cal_iso (ref justa) | 0.0101 | 0.0466 | +0.003 | +0.000 |
| 45 min | all | 1,532,952 | 0.017 | p_hist_iso | 0.0148 | 0.0639 | -0.458 | -0.462 |
| 45 min | all | 1,532,952 | 0.017 | p_lgbm_raw | 0.0082 | 0.0288 | +0.196 | +0.194 |
| 45 min | all | 1,532,952 | 0.017 | p_lgbm | 0.0082 | 0.0287 | +0.198 | +0.195 |
| 45 min | all | 1,532,952 | 0.017 | p_lgbm_recal | 0.0082 | 0.0287 | +0.197 | +0.195 |
| 45 min | all | 1,532,952 | 0.017 | p_lgbm_sub | 0.0082 | 0.0287 | +0.198 | +0.195 |
| 45 min | all | 1,532,952 | 0.017 | p_lgbm_sub_roll | 0.0082 | 0.0287 | +0.198 | +0.195 |
| 45 min | peak | 87,184 | 0.026 | p_persist | 0.0260 | 0.3591 | -0.228 | -0.228 |
| 45 min | peak | 87,184 | 0.026 | p_persist_cal (ref) | 0.0212 | 0.0868 | +0.000 | -0.000 |
| 45 min | peak | 87,184 | 0.026 | p_hist | 0.0226 | 0.0879 | -0.067 | -0.068 |
| 45 min | peak | 87,184 | 0.026 | p_persist_cal_tvf (ref justa) | 0.0212 | 0.0870 | +0.000 | +0.000 |
| 45 min | peak | 87,184 | 0.026 | p_hist_tvf | 0.0220 | 0.0854 | -0.040 | -0.040 |
| 45 min | peak | 87,184 | 0.026 | p_persist_cal_iso | 0.0212 | 0.0876 | -0.003 | -0.004 |
| 45 min | peak | 87,184 | 0.026 | p_hist_iso | 0.0214 | 0.0803 | -0.009 | -0.009 |
| 45 min | peak | 87,184 | 0.026 | p_lgbm_raw | 0.0161 | 0.0543 | +0.241 | +0.240 |
| 45 min | peak | 87,184 | 0.026 | p_lgbm | 0.0160 | 0.0543 | +0.242 | +0.242 |
| 45 min | peak | 87,184 | 0.026 | p_lgbm_recal | 0.0161 | 0.0544 | +0.241 | +0.241 |
| 45 min | peak | 87,184 | 0.026 | p_lgbm_sub | 0.0161 | 0.0543 | +0.242 | +0.241 |
| 45 min | peak | 87,184 | 0.026 | p_lgbm_sub_roll | 0.0161 | 0.0545 | +0.241 | +0.241 |
| 45 min | saturated | 259,405 | 0.027 | p_persist | 0.0329 | 0.4543 | -0.455 | -0.461 |
| 45 min | saturated | 259,405 | 0.027 | p_persist_cal (ref) | 0.0226 | 0.1021 | +0.000 | -0.004 |
| 45 min | saturated | 259,405 | 0.027 | p_hist | 0.0250 | 0.1029 | -0.104 | -0.108 |
| 45 min | saturated | 259,405 | 0.027 | p_persist_cal_tvf | 0.0226 | 0.1016 | +0.002 | -0.002 |
| 45 min | saturated | 259,405 | 0.027 | p_hist_tvf | 0.0246 | 0.1008 | -0.087 | -0.091 |
| 45 min | saturated | 259,405 | 0.027 | p_persist_cal_iso (ref justa) | 0.0225 | 0.1006 | +0.004 | +0.000 |
| 45 min | saturated | 259,405 | 0.027 | p_hist_iso | 0.0240 | 0.0967 | -0.064 | -0.068 |
| 45 min | saturated | 259,405 | 0.027 | p_lgbm_raw | 0.0187 | 0.0631 | +0.172 | +0.169 |
| 45 min | saturated | 259,405 | 0.027 | p_lgbm | 0.0187 | 0.0630 | +0.172 | +0.169 |
| 45 min | saturated | 259,405 | 0.027 | p_lgbm_recal | 0.0187 | 0.0630 | +0.172 | +0.169 |
| 45 min | saturated | 259,405 | 0.027 | p_lgbm_sub | 0.0187 | 0.0630 | +0.172 | +0.169 |
| 45 min | saturated | 259,405 | 0.027 | p_lgbm_sub_roll | 0.0187 | 0.0630 | +0.172 | +0.169 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_persist | 0.1271 | 1.7563 | -0.199 | -0.199 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_persist_cal (ref) | 0.1060 | 0.3970 | +0.000 | -0.000 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_hist | 0.1154 | 0.3846 | -0.088 | -0.088 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_persist_cal_tvf (ref justa) | 0.1060 | 0.3985 | +0.000 | +0.000 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_hist_tvf | 0.1122 | 0.3753 | -0.059 | -0.059 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_persist_cal_iso | 0.1066 | 0.4063 | -0.006 | -0.006 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_hist_iso | 0.1085 | 0.3635 | -0.024 | -0.024 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_lgbm_raw | 0.0799 | 0.2553 | +0.247 | +0.247 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_lgbm | 0.0797 | 0.2549 | +0.248 | +0.248 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_lgbm_recal | 0.0799 | 0.2554 | +0.246 | +0.246 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_lgbm_sub | 0.0798 | 0.2551 | +0.247 | +0.247 |
| 45 min | saturated_peak | 14,820 | 0.133 | p_lgbm_sub_roll | 0.0799 | 0.2559 | +0.247 | +0.247 |

## Intervalos de confianza (bootstrap por bloques, 1000 réplicas, IC 95 %)

### BSS de p_lgbm y p_lgbm_sub_roll

| Horizon | Segment | Modelo | Referencia | Bloque | Bloques | BSS | IC 95 % |
|---|---|---|---|---|---|---|---|
| 15 min | all | p_lgbm | p_persist_cal (pre-registered) | day | 20 | +0.168 | [+0.155, +0.181] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 20 | +0.168 | [+0.155, +0.181] |
| 15 min | all | p_lgbm | p_persist_cal_iso (fair) | day | 20 | +0.166 | [+0.153, +0.179] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 20 | +0.166 | [+0.153, +0.179] |
| 15 min | all | p_lgbm | p_persist_cal (pre-registered) | station_day | 13,439 | +0.168 | [+0.161, +0.176] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 13,439 | +0.168 | [+0.161, +0.175] |
| 15 min | all | p_lgbm | p_persist_cal_iso (fair) | station_day | 13,439 | +0.166 | [+0.159, +0.173] |
| 15 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 13,439 | +0.166 | [+0.159, +0.173] |
| 15 min | peak | p_lgbm | p_persist_cal (pre-registered) | day | 14 | +0.242 | [+0.218, +0.262] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 14 | +0.239 | [+0.216, +0.259] |
| 15 min | peak | p_lgbm | p_persist_cal_tvf (fair) | day | 14 | +0.241 | [+0.217, +0.262] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 14 | +0.239 | [+0.215, +0.258] |
| 15 min | peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 9,392 | +0.242 | [+0.224, +0.259] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 9,392 | +0.239 | [+0.222, +0.256] |
| 15 min | peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 9,392 | +0.241 | [+0.223, +0.258] |
| 15 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 9,392 | +0.239 | [+0.221, +0.256] |
| 15 min | saturated | p_lgbm | p_persist_cal (pre-registered) | day | 20 | +0.167 | [+0.153, +0.181] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 20 | +0.166 | [+0.152, +0.180] |
| 15 min | saturated | p_lgbm | p_persist_cal_iso (fair) | day | 20 | +0.165 | [+0.151, +0.180] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 20 | +0.165 | [+0.151, +0.179] |
| 15 min | saturated | p_lgbm | p_persist_cal (pre-registered) | station_day | 2,280 | +0.167 | [+0.156, +0.178] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 2,280 | +0.166 | [+0.155, +0.177] |
| 15 min | saturated | p_lgbm | p_persist_cal_iso (fair) | station_day | 2,280 | +0.165 | [+0.155, +0.177] |
| 15 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 2,280 | +0.165 | [+0.154, +0.176] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | day | 14 | +0.250 | [+0.228, +0.267] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 14 | +0.247 | [+0.225, +0.264] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | day | 14 | +0.249 | [+0.228, +0.266] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 14 | +0.246 | [+0.225, +0.263] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 1,596 | +0.250 | [+0.228, +0.269] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 1,596 | +0.247 | [+0.226, +0.266] |
| 15 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 1,596 | +0.249 | [+0.227, +0.269] |
| 15 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 1,596 | +0.246 | [+0.226, +0.265] |
| 30 min | all | p_lgbm | p_persist_cal (pre-registered) | day | 20 | +0.185 | [+0.171, +0.198] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 20 | +0.184 | [+0.171, +0.197] |
| 30 min | all | p_lgbm | p_persist_cal_iso (fair) | day | 20 | +0.182 | [+0.168, +0.195] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 20 | +0.182 | [+0.168, +0.195] |
| 30 min | all | p_lgbm | p_persist_cal (pre-registered) | station_day | 13,439 | +0.185 | [+0.177, +0.192] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 13,439 | +0.184 | [+0.177, +0.192] |
| 30 min | all | p_lgbm | p_persist_cal_iso (fair) | station_day | 13,439 | +0.182 | [+0.175, +0.190] |
| 30 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 13,439 | +0.182 | [+0.175, +0.189] |
| 30 min | peak | p_lgbm | p_persist_cal (pre-registered) | day | 14 | +0.250 | [+0.223, +0.278] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 14 | +0.249 | [+0.225, +0.271] |
| 30 min | peak | p_lgbm | p_persist_cal_tvf (fair) | day | 14 | +0.250 | [+0.222, +0.277] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 14 | +0.248 | [+0.225, +0.271] |
| 30 min | peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 9,392 | +0.250 | [+0.228, +0.270] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 9,392 | +0.249 | [+0.228, +0.268] |
| 30 min | peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 9,392 | +0.250 | [+0.228, +0.270] |
| 30 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 9,392 | +0.248 | [+0.228, +0.268] |
| 30 min | saturated | p_lgbm | p_persist_cal (pre-registered) | day | 20 | +0.171 | [+0.159, +0.184] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 20 | +0.170 | [+0.159, +0.184] |
| 30 min | saturated | p_lgbm | p_persist_cal_iso (fair) | day | 20 | +0.169 | [+0.157, +0.181] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 20 | +0.168 | [+0.156, +0.181] |
| 30 min | saturated | p_lgbm | p_persist_cal (pre-registered) | station_day | 2,280 | +0.171 | [+0.160, +0.182] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 2,280 | +0.170 | [+0.160, +0.181] |
| 30 min | saturated | p_lgbm | p_persist_cal_iso (fair) | station_day | 2,280 | +0.169 | [+0.158, +0.180] |
| 30 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 2,280 | +0.168 | [+0.157, +0.179] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | day | 14 | +0.255 | [+0.224, +0.285] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 14 | +0.253 | [+0.226, +0.278] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | day | 14 | +0.255 | [+0.223, +0.285] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 14 | +0.252 | [+0.226, +0.278] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 1,596 | +0.255 | [+0.229, +0.277] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 1,596 | +0.253 | [+0.229, +0.273] |
| 30 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 1,596 | +0.255 | [+0.229, +0.277] |
| 30 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 1,596 | +0.252 | [+0.229, +0.273] |
| 45 min | all | p_lgbm | p_persist_cal (pre-registered) | day | 20 | +0.198 | [+0.181, +0.214] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 20 | +0.198 | [+0.182, +0.214] |
| 45 min | all | p_lgbm | p_persist_cal_iso (fair) | day | 20 | +0.195 | [+0.178, +0.213] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 20 | +0.195 | [+0.179, +0.212] |
| 45 min | all | p_lgbm | p_persist_cal (pre-registered) | station_day | 13,439 | +0.198 | [+0.190, +0.206] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 13,439 | +0.198 | [+0.190, +0.206] |
| 45 min | all | p_lgbm | p_persist_cal_iso (fair) | station_day | 13,439 | +0.195 | [+0.187, +0.203] |
| 45 min | all | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 13,439 | +0.195 | [+0.187, +0.203] |
| 45 min | peak | p_lgbm | p_persist_cal (pre-registered) | day | 14 | +0.242 | [+0.206, +0.271] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 14 | +0.241 | [+0.210, +0.266] |
| 45 min | peak | p_lgbm | p_persist_cal_tvf (fair) | day | 14 | +0.242 | [+0.206, +0.271] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 14 | +0.241 | [+0.209, +0.266] |
| 45 min | peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 9,391 | +0.242 | [+0.220, +0.265] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 9,391 | +0.241 | [+0.220, +0.262] |
| 45 min | peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 9,391 | +0.242 | [+0.219, +0.265] |
| 45 min | peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 9,391 | +0.241 | [+0.220, +0.261] |
| 45 min | saturated | p_lgbm | p_persist_cal (pre-registered) | day | 20 | +0.172 | [+0.159, +0.185] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 20 | +0.172 | [+0.160, +0.184] |
| 45 min | saturated | p_lgbm | p_persist_cal_iso (fair) | day | 20 | +0.169 | [+0.155, +0.183] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | day | 20 | +0.169 | [+0.156, +0.182] |
| 45 min | saturated | p_lgbm | p_persist_cal (pre-registered) | station_day | 2,280 | +0.172 | [+0.160, +0.185] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 2,280 | +0.172 | [+0.160, +0.183] |
| 45 min | saturated | p_lgbm | p_persist_cal_iso (fair) | station_day | 2,280 | +0.169 | [+0.157, +0.182] |
| 45 min | saturated | p_lgbm_sub_roll | p_persist_cal_iso (fair) | station_day | 2,280 | +0.169 | [+0.157, +0.181] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | day | 14 | +0.248 | [+0.205, +0.282] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | day | 14 | +0.247 | [+0.210, +0.276] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | day | 14 | +0.248 | [+0.205, +0.282] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | day | 14 | +0.247 | [+0.210, +0.276] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal (pre-registered) | station_day | 1,596 | +0.248 | [+0.220, +0.273] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal (pre-registered) | station_day | 1,596 | +0.247 | [+0.222, +0.269] |
| 45 min | saturated_peak | p_lgbm | p_persist_cal_tvf (fair) | station_day | 1,596 | +0.248 | [+0.220, +0.273] |
| 45 min | saturated_peak | p_lgbm_sub_roll | p_persist_cal_tvf (fair) | station_day | 1,596 | +0.247 | [+0.222, +0.269] |

### Brecha de calibración en saturated_peak (meta ≤ 0.05)

La brecha es el máximo sobre los bins con n ≥ 1,000, así que el bootstrap la sesga hacia arriba: el IC es conservador.

| Horizon | Modelo | Bloque | Brecha | IC 95 % | Réplicas ≤ meta |
|---|---|---|---|---|---|
| 15 min | p_lgbm | day | 0.002 | [0.001, 0.004] | 100% |
| 15 min | p_lgbm | station_day | 0.002 | [0.001, 0.003] | 100% |
| 15 min | p_lgbm_recal | day | 0.001 | [0.000, 0.002] | 100% |
| 15 min | p_lgbm_recal | station_day | 0.001 | [0.000, 0.002] | 100% |
| 15 min | p_lgbm_sub | day | 0.003 | [0.002, 0.004] | 100% |
| 15 min | p_lgbm_sub | station_day | 0.003 | [0.002, 0.004] | 100% |
| 15 min | p_lgbm_sub_roll | day | 0.002 | [0.000, 0.004] | 100% |
| 15 min | p_lgbm_sub_roll | station_day | 0.002 | [0.001, 0.003] | 100% |
| 30 min | p_lgbm | day | 0.005 | [0.004, 0.068] | 79% |
| 30 min | p_lgbm | station_day | 0.005 | [0.004, 0.062] | 93% |
| 30 min | p_lgbm_recal | day | 0.003 | [0.001, 0.013] | 100% |
| 30 min | p_lgbm_recal | station_day | 0.003 | [0.001, 0.005] | 100% |
| 30 min | p_lgbm_sub | day | 0.054 | [0.006, 0.069] | 53% |
| 30 min | p_lgbm_sub | station_day | 0.054 | [0.007, 0.071] | 45% |
| 30 min | p_lgbm_sub_roll | day | 0.005 | [0.001, 0.057] | 88% |
| 30 min | p_lgbm_sub_roll | station_day | 0.005 | [0.003, 0.053] | 95% |
| 45 min | p_lgbm | day | 0.031 | [0.008, 0.067] | 81% |
| 45 min | p_lgbm | station_day | 0.031 | [0.010, 0.062] | 89% |
| 45 min | p_lgbm_recal | day | 0.012 | [0.004, 0.075] | 79% |
| 45 min | p_lgbm_recal | station_day | 0.012 | [0.006, 0.062] | 90% |
| 45 min | p_lgbm_sub | day | 0.015 | [0.005, 0.068] | 93% |
| 45 min | p_lgbm_sub | station_day | 0.015 | [0.005, 0.044] | 99% |
| 45 min | p_lgbm_sub_roll | day | 0.014 | [0.004, 0.062] | 95% |
| 45 min | p_lgbm_sub_roll | station_day | 0.014 | [0.004, 0.041] | 99% |

## Metas

| Horizon | Modelo | Meta | Valor | ¿Cumple? |
|---|---|---|---|---|
| 15 min | p_lgbm | BSS > 0, all | 0.168 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, all | 0.168 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, all | 0.168 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, all | 0.168 | ✅ |
| 15 min | p_lgbm | BSS > 0, peak | 0.242 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, peak | 0.241 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, peak | 0.238 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, peak | 0.239 | ✅ |
| 15 min | p_lgbm | BSS > 0, saturated | 0.167 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, saturated | 0.167 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, saturated | 0.165 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, saturated | 0.166 | ✅ |
| 15 min | p_lgbm | BSS > 0, saturated_peak | 0.250 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.249 | ✅ |
| 15 min | p_lgbm_sub | BSS > 0, saturated_peak | 0.245 | ✅ |
| 15 min | p_lgbm_sub_roll | BSS > 0, saturated_peak | 0.247 | ✅ |
| 15 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.002 | ✅ |
| 15 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.001 | ✅ |
| 15 min | p_lgbm_sub | calibration gap <= 0.05, saturated_peak | 0.003 | ✅ |
| 15 min | p_lgbm_sub_roll | calibration gap <= 0.05, saturated_peak | 0.002 | ✅ |
| 30 min | p_lgbm | BSS > 0, all | 0.185 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, all | 0.185 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, all | 0.184 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, all | 0.184 | ✅ |
| 30 min | p_lgbm | BSS > 0, peak | 0.250 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, peak | 0.248 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, peak | 0.248 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, peak | 0.249 | ✅ |
| 30 min | p_lgbm | BSS > 0, saturated | 0.171 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, saturated | 0.172 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, saturated | 0.170 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, saturated | 0.170 | ✅ |
| 30 min | p_lgbm | BSS > 0, saturated_peak | 0.255 | ✅ |
| 30 min | p_lgbm | BSS >= 0.1, saturated_peak | 0.255 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.252 | ✅ |
| 30 min | p_lgbm_recal | BSS >= 0.1, saturated_peak | 0.252 | ✅ |
| 30 min | p_lgbm_sub | BSS > 0, saturated_peak | 0.252 | ✅ |
| 30 min | p_lgbm_sub | BSS >= 0.1, saturated_peak | 0.252 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS > 0, saturated_peak | 0.253 | ✅ |
| 30 min | p_lgbm_sub_roll | BSS >= 0.1, saturated_peak | 0.253 | ✅ |
| 30 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.005 | ✅ |
| 30 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.003 | ✅ |
| 30 min | p_lgbm_sub | calibration gap <= 0.05, saturated_peak | 0.054 | ❌ |
| 30 min | p_lgbm_sub_roll | calibration gap <= 0.05, saturated_peak | 0.005 | ✅ |
| 45 min | p_lgbm | BSS > 0, all | 0.198 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, all | 0.197 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, all | 0.198 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, all | 0.198 | ✅ |
| 45 min | p_lgbm | BSS > 0, peak | 0.242 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, peak | 0.241 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, peak | 0.242 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, peak | 0.241 | ✅ |
| 45 min | p_lgbm | BSS > 0, saturated | 0.172 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, saturated | 0.172 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, saturated | 0.172 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, saturated | 0.172 | ✅ |
| 45 min | p_lgbm | BSS > 0, saturated_peak | 0.248 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.246 | ✅ |
| 45 min | p_lgbm_sub | BSS > 0, saturated_peak | 0.247 | ✅ |
| 45 min | p_lgbm_sub_roll | BSS > 0, saturated_peak | 0.247 | ✅ |
| 45 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.031 | ✅ |
| 45 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.012 | ✅ |
| 45 min | p_lgbm_sub | calibration gap <= 0.05, saturated_peak | 0.015 | ✅ |
| 45 min | p_lgbm_sub_roll | calibration gap <= 0.05, saturated_peak | 0.014 | ✅ |

### 15 min: calibración en saturated_peak (p_lgbm)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 11,248 | 0.007 | 0.005 | [0.003, 0.007] |
| 1 | 538 | 0.150 | 0.113 | [0.093, 0.140] |
| 2 | 402 | 0.252 | 0.231 | [0.198, 0.270] |
| 3 | 395 | 0.344 | 0.273 | [0.232, 0.311] |
| 4 | 598 | 0.454 | 0.468 | [0.435, 0.502] |
| 5 | 610 | 0.557 | 0.567 | [0.522, 0.609] |
| 6 | 467 | 0.650 | 0.677 | [0.628, 0.724] |
| 7 | 651 | 0.729 | 0.785 | [0.746, 0.816] |
| 8 | 299 | 0.839 | 0.846 | [0.804, 0.880] |
| 9 | 68 | 0.917 | 0.971 | [0.936, 1.000] |

### 15 min: calibración en saturated_peak (p_lgbm_sub_roll)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 11,233 | 0.007 | 0.005 | [0.003, 0.007] |
| 1 | 541 | 0.142 | 0.104 | [0.083, 0.126] |
| 2 | 447 | 0.246 | 0.230 | [0.191, 0.274] |
| 3 | 364 | 0.339 | 0.275 | [0.231, 0.312] |
| 4 | 616 | 0.445 | 0.469 | [0.436, 0.502] |
| 5 | 595 | 0.550 | 0.571 | [0.528, 0.610] |
| 6 | 620 | 0.646 | 0.697 | [0.646, 0.741] |
| 7 | 573 | 0.743 | 0.794 | [0.759, 0.831] |
| 8 | 212 | 0.850 | 0.887 | [0.839, 0.939] |
| 9 | 75 | 0.919 | 0.907 | [0.800, 0.968] |

V8 (ECE, todas las estaciones): p_lgbm: centro 0.0008, periferia 0.0008; p_lgbm_recal: centro 0.0003, periferia 0.0004; p_lgbm_sub: centro 0.0008, periferia 0.0009; p_lgbm_sub_roll: centro 0.0008, periferia 0.0008. Árboles: 153; entrenamiento 1.6 min.

Importancia (ganancia): docks_now 74.0%, occupancy_now 11.0%, flow_arrivals_target 2.7%, flow_departures_target 2.5%, docks_lag15 2.0%, station 1.6%, bikes_now 1.6%, flow_net_window 1.4%, docks_lag60 0.5%, nb_full_frac 0.4%, minute_of_day 0.4%, flow_net_target 0.3%, nb_occupancy_mean 0.2%, full_lag15 0.2%, docks_delta60 0.2%

Rezagos presentes: 15 min 46.0%, 30 min 49.8%, 60 min 47.2%

### 30 min: calibración en saturated_peak (p_lgbm)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 10,475 | 0.012 | 0.007 | [0.005, 0.010] |
| 1 | 949 | 0.151 | 0.096 | [0.081, 0.116] |
| 2 | 722 | 0.257 | 0.187 | [0.157, 0.220] |
| 3 | 735 | 0.351 | 0.331 | [0.301, 0.367] |
| 4 | 802 | 0.448 | 0.436 | [0.400, 0.480] |
| 5 | 701 | 0.555 | 0.565 | [0.497, 0.640] |
| 6 | 413 | 0.650 | 0.671 | [0.602, 0.744] |
| 7 | 213 | 0.732 | 0.746 | [0.688, 0.809] |
| 8 | 152 | 0.841 | 0.882 | [0.847, 0.917] |

### 30 min: calibración en saturated_peak (p_lgbm_sub_roll)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 10,578 | 0.013 | 0.008 | [0.005, 0.012] |
| 1 | 973 | 0.152 | 0.112 | [0.093, 0.138] |
| 2 | 738 | 0.257 | 0.205 | [0.162, 0.251] |
| 3 | 900 | 0.356 | 0.362 | [0.338, 0.393] |
| 4 | 718 | 0.458 | 0.475 | [0.416, 0.538] |
| 5 | 556 | 0.552 | 0.594 | [0.518, 0.672] |
| 6 | 382 | 0.637 | 0.686 | [0.622, 0.754] |
| 7 | 211 | 0.740 | 0.754 | [0.697, 0.813] |
| 8 | 94 | 0.842 | 0.894 | [0.841, 0.938] |
| 9 | 12 | 0.909 | 1.000 | [1.000, 1.000] |

V8 (ECE, todas las estaciones): p_lgbm: centro 0.0011, periferia 0.0008; p_lgbm_recal: centro 0.0004, periferia 0.0004; p_lgbm_sub: centro 0.0011, periferia 0.0009; p_lgbm_sub_roll: centro 0.0011, periferia 0.0009. Árboles: 137; entrenamiento 1.4 min.

Importancia (ganancia): docks_now 66.9%, occupancy_now 12.2%, flow_net_window 4.1%, flow_departures_target 3.3%, station 2.6%, bikes_now 2.1%, docks_lag15 1.9%, flow_arrivals_target 1.7%, minute_of_day 1.2%, flow_net_target 0.7%, docks_lag60 0.5%, nb_full_frac 0.5%, nb_occupancy_mean 0.5%, st_full_rate 0.3%, docks_lag30 0.2%

Rezagos presentes: 15 min 45.4%, 30 min 50.3%, 60 min 47.0%

### 45 min: calibración en saturated_peak (p_lgbm)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 9,296 | 0.019 | 0.017 | [0.012, 0.023] |
| 1 | 1,489 | 0.143 | 0.132 | [0.104, 0.160] |
| 2 | 1,191 | 0.255 | 0.223 | [0.186, 0.261] |
| 3 | 981 | 0.351 | 0.334 | [0.296, 0.383] |
| 4 | 777 | 0.456 | 0.445 | [0.395, 0.505] |
| 5 | 447 | 0.544 | 0.548 | [0.470, 0.630] |
| 6 | 358 | 0.637 | 0.620 | [0.533, 0.712] |
| 7 | 220 | 0.747 | 0.723 | [0.665, 0.778] |
| 8 | 61 | 0.829 | 0.902 | [0.846, 0.962] |

### 45 min: calibración en saturated_peak (p_lgbm_sub_roll)

| Bin | n | Predicted | Observed | IC 95 % (días) |
|---|---|---|---|---|
| 0 | 9,367 | 0.020 | 0.018 | [0.012, 0.025] |
| 1 | 1,481 | 0.139 | 0.137 | [0.107, 0.163] |
| 2 | 1,426 | 0.249 | 0.236 | [0.201, 0.269] |
| 3 | 819 | 0.346 | 0.365 | [0.320, 0.412] |
| 4 | 892 | 0.447 | 0.469 | [0.402, 0.540] |
| 5 | 391 | 0.554 | 0.596 | [0.523, 0.679] |
| 6 | 263 | 0.645 | 0.673 | [0.590, 0.756] |
| 7 | 151 | 0.747 | 0.755 | [0.704, 0.789] |
| 8 | 30 | 0.818 | 0.900 | [0.808, 1.000] |

V8 (ECE, todas las estaciones): p_lgbm: centro 0.0006, periferia 0.0004; p_lgbm_recal: centro 0.0005, periferia 0.0002; p_lgbm_sub: centro 0.0006, periferia 0.0004; p_lgbm_sub_roll: centro 0.0006, periferia 0.0003. Árboles: 139; entrenamiento 1.4 min.

Importancia (ganancia): docks_now 62.6%, occupancy_now 11.8%, flow_net_window 6.4%, flow_departures_target 3.7%, station 3.7%, bikes_now 2.4%, docks_lag15 1.8%, minute_of_day 1.7%, flow_net_target 1.0%, flow_arrivals_target 1.0%, nb_occupancy_mean 0.6%, nb_full_frac 0.5%, docks_lag60 0.5%, st_full_rate 0.5%, target_slot 0.3%

Rezagos presentes: 15 min 44.3%, 30 min 48.1%, 60 min 46.5%
