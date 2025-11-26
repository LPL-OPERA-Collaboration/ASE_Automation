'''
Kaya/
│
├── gentec data/                           <-- OUTPUT of Step 0
│   └── 20251126_..._calibration.csv       (Source File)
│       [ACTION]: You must COPY this file manually to the daily folder below.
│
└── data/
    └── 20251126_Measurement_56/           <-- "BASE_DIR" in analysis_config.py
        │
        ├── 20251126_measurement.log       (Log file from Acquisition)
        ├── calibration_2025... .csv       (PASTED by You)
        ├── absorption_sample.txt          (PASTED by You)
        │
        ├── Raw_Data/                      <-- OUTPUT of Spectra Acquisition
        │   ├── ...angle_190.00... .txt    (Spectrum with Header info)
        │   └── ...angle_190.00... .tsf    (LabSpec Backup)
        │
        ├── Used_Acquisition_Codes_.../    <-- SNAPSHOT 1 (Auto-generated)
        │   ├── main_measurement.py
        │   └── experiment_config.py
        │
        ├── Results/                       <-- OUTPUT of Step 1 & Step 2
        │   ├── energies.csv               (Fluence values)
        │   ├── final_results_... .csv     (The Final Data Table)
        │   ├── ASE_Curve_... .png         (The Final Plot)
        │   ├── COMBINED_raw... .txt       (Matrix Data)
        │   └── COMBINED_smooth... .txt    (Matrix Data)
        │
        └── Used_Analysis_Codes_.../       <-- SNAPSHOT 2 (Auto-generated)
            ├── analysis_config.py
            ├── step1_energy_calc.py
            └── step2_spectrum_analysis.py
'''