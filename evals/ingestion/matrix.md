# DEXPI ingestion matrix

All 35 official DEXPI 1.3 example files, run through the unchanged pipeline (ProteusSerializer -> GraphLoader -> GraphAbstractor -> normalize -> GraphService). 35 of 35 complete every stage. This shows ingestion compatibility, not answer quality.

| File | Proteus | Stages | Plant n/e | Conceptual n/e | Equip. | Piping | Instr. | Lines | Tagged / untagged | Components | Connections | Dropped links |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C01V04-VER.EX01.xml | 4.1.1 | all ok | 214 / 376 | 36 / 39 | 5 | 21 | 10 | 11 | 5 / 31 | 1 | direct_piping_connection 2, measuring_line 3, open_end 4, operated_valve_reference 3, pipe 25, sensing_location 3, signal_line 3 | none |
| C02V03-VER.EX02.xml | 4.1.1 | all ok | 87 / 146 | 17 / 17 | 1 | 10 | 6 | 4 | 1 / 16 | 2 | direct_piping_connection 4, measuring_line 2, open_end 1, pipe 6, sensing_location 2, signal_line 2 | composition 1 |
| C03V04-VER.EX02.xml | 4.1.1 | all ok | 52 / 98 | 12 / 11 | 0 | 10 | 2 | 3 | 0 / 12 | 1 | direct_piping_connection 6, operated_valve_reference 1, pipe 3, signal_line 1 | none |
| E01V02-VER.EX01.xml | 4.1.1 | all ok | 4 / 3 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E02V02-VER.EX01.xml | 4.1.1 | all ok | 14 / 13 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E03V01-VER.EX01.xml | 4.1.1 | all ok | 5 / 4 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E04V01-VER.EX01.xml | 4.1.1 | all ok | 8 / 7 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E05V01-VER.EX01.xml | 4.1.1 | all ok | 11 / 10 | 2 / 0 | 2 | 0 | 0 | 0 | 2 / 0 | 2 | none | none |
| E06V01-VER.EX01.xml | 4.1.1 | all ok | 18 / 21 | 2 / 1 | 2 | 0 | 0 | 1 | 2 / 0 | 1 | pipe 1 | none |
| E07V01-VER.EX01.xml | 4.1.1 | all ok | 10 / 11 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E08V01-VER.EX01.xml | 4.1.1 | all ok | 10 / 9 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E09V01-VER.EX01.xml | 4.1.1 | all ok | 2 / 1 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E11V01-VER.EX01.xml | 4.1.1 | all ok | 4 / 3 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E12V01-VER.EX01.xml | 4.1.1 | all ok | 12 / 15 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E13V01-VER.EX01.xml | 4.1.1 | all ok | 2 / 1 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| E14V01-VER.EX01.xml | 4.1.1 | all ok | 2 / 1 | 1 / 0 | 1 | 0 | 0 | 0 | 1 / 0 | 1 | none | none |
| I01V01-VER.EX01.xml | 4.1.1 | all ok | 13 / 21 | 4 / 3 | 1 | 1 | 2 | 1 | 1 / 3 | 1 | direct_piping_connection 1, measuring_line 1, sensing_location 1 | none |
| I02V01-VER.EX01.xml | 4.1.1 | all ok | 15 / 23 | 3 / 2 | 0 | 1 | 2 | 1 | 0 / 3 | 1 | open_end 2, operated_valve_reference 1, signal_line 1 | none |
| I03V01-VER.EX01.xml | 4.1.1 | all ok | 25 / 41 | 6 / 5 | 1 | 2 | 3 | 2 | 0 / 6 | 1 | direct_piping_connection 1, measuring_line 1, open_end 2, operated_valve_reference 1, sensing_location 1, signal_line 1 | none |
| I04V01-VER.EX01.xml | 4.1.1 | all ok | 24 / 39 | 5 / 4 | 0 | 2 | 3 | 2 | 0 / 5 | 1 | measuring_line 1, open_end 4, operated_valve_reference 1, sensing_location 1, signal_line 1 | none |
| I05V01-VER.EX01.xml | 4.1.1 | all ok | 28 / 51 | 9 / 7 | 0 | 1 | 8 | 2 | 0 / 9 | 2 | measuring_line 2, open_end 3, operated_valve_reference 1, signal_line 4 | none |
| I06V01-VER.EX01.xml | 4.1.1 | all ok | 25 / 44 | 6 / 5 | 0 | 1 | 5 | 1 | 0 / 6 | 1 | measuring_line 1, open_end 2, operated_valve_reference 1, signal_line 3 | none |
| I07V01-VER.EX01.xml | 4.1.1 | all ok | 16 / 27 | 6 / 3 | 0 | 0 | 6 | 1 | 0 / 6 | 3 | measuring_line 2, open_end 1, signal_line 1 | none |
| I08V01-VER.EX01.xml | 4.1.1 | all ok | 20 / 37 | 7 / 4 | 0 | 0 | 7 | 1 | 0 / 7 | 3 | measuring_line 2, open_end 1, signal_line 2 | none |
| I09V01-VER.EX01.xml | 4.1.1 | all ok | 8 / 11 | 3 / 2 | 1 | 0 | 2 | 0 | 1 / 2 | 1 | measuring_line 1, sensing_location 1 | none |
| I10V01-VER.EX01.xml | 4.1.1 | all ok | 8 / 11 | 3 / 1 | 0 | 0 | 3 | 1 | 0 / 3 | 2 | measuring_line 1, open_end 1 | none |
| I11V01-VER.EX01.xml | 4.1.1 | all ok | 12 / 19 | 3 / 2 | 0 | 1 | 2 | 1 | 0 / 3 | 1 | measuring_line 1, open_end 2, sensing_location 1 | none |
| I12V01-VER.EX01.xml | 4.1.1 | all ok | 15 / 23 | 3 / 2 | 0 | 1 | 2 | 1 | 0 / 3 | 1 | open_end 2, operated_valve_reference 1, signal_line 1 | none |
| I13V01-VER.EX01.xml | 4.1.1 | all ok | 25 / 45 | 6 / 5 | 0 | 3 | 3 | 2 | 0 / 6 | 1 | direct_piping_connection 1, measuring_line 1, open_end 2, pipe 1, sensing_location 1, signal_line 1 | none |
| I14V01-VER.EX01.xml | 4.1.1 | all ok | 14 / 24 | 4 / 3 | 0 | 1 | 3 | 1 | 0 / 4 | 1 | measuring_line 1, open_end 2, sensing_location 1, signal_line 1 | none |
| I15V01-VER.EX01.xml | 4.1.1 | all ok | 12 / 18 | 4 / 4 | 1 | 0 | 3 | 0 | 1 / 3 | 1 | measuring_line 2, sensing_location 2 | none |
| P01V01-VER.EX01.xml | 4.1.1 | all ok | 10 / 13 | 2 / 1 | 2 | 0 | 0 | 1 | 2 / 0 | 1 | pipe 1 | none |
| P02V01-VER.EX01.xml | 4.1.1 | all ok | 10 / 14 | 3 / 2 | 1 | 1 | 1 | 1 | 1 / 2 | 2 | pipe 1 | composition 1 |
| P03V01-VER.EX01.xml | 4.1.1 | all ok | 7 / 8 | 1 / 0 | 1 | 0 | 0 | 1 | 1 / 0 | 1 | open_end 1 | none |
| P04V01-VER.EX01.xml | 4.1.1 | all ok | 12 / 15 | 1 / 0 | 1 | 0 | 0 | 2 | 1 / 0 | 1 | open_end 2 | none |

Source: DEXPI e.V. TrainingTestCases, dexpi 1.3/example pids (CC BY 4.0). C01 is the file at data/C01V04-VER.EX01.xml (identical to the official copy and to the one shipped with pyDEXPI).
