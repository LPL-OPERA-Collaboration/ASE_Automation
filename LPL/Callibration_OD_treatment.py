def apply_od_correction(df):
    """
    Applies Optical Density (OD) correction to the dataframe.
    This logic is isolated here so it can be easily removed or skipped
    once the acquisition code handles 'energy_corrected' natively.
    """
    # Filter 0: Factor 1.0
    # Filter 1: Factor 10^(1.001)
    # Filter 3: Factor 10^(3.163)
    od_corrections = {0: 1.0, 1: 10**1.001, 3: 10**3.163}
    
    # Check if required columns exist
    if 'filter' not in df.columns:
        raise ValueError("CSV is missing 'filter' column required for manual OD correction.")

    df['correction'] = df['filter'].map(od_corrections)
    
    if df['correction'].isnull().any():
        raise ValueError(f"Unknown filter in CSV. Allowed: {list(od_corrections.keys())}")

    df['energy_corrected'] = df['energy_J'] * df['correction']
    return df