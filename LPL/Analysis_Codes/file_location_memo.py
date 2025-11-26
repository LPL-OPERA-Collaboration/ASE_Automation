'''
LOCATION A: YOUR GITHUB REPO (The Logic)
C:\Users\Equipe_OPAL\Documents\GitHub\...\Analysis_Codes\
│
├── config.py                     (The Bridge: Points to Location B)
├── step1_energy_calc.py          (Reads B, Saves to B)
└── step2_spectrum_analysis.py    (Reads B, Saves to B, Copies Self to B)


           ⬇️  BRIDGE (BASE_DIR = "...\Measurement_56")  ⬇️


LOCATION B: YOUR DATA FOLDER (The Storage)
C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251118_Measurement_56\
│
├── calibration.csv               (Input)
├── absorption.txt                (Input)
├── Raw_Data/                     (Input)
│
├── Results/                      (Output from Step 1 & 2)
│   ├── energies.csv
│   └── ASE_Curve...png
│
└── Used_Analysis_Codes_2025.../  (Snapshot Output)
    ├── config.py                 (Copy from Location A)
    ├── step1_energy_calc.py      (Copy from Location A)
    └── step2_spectrum_analysis.py(Copy from Location A)
'''