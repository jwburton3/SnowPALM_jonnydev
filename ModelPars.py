
model_pars = {
    # Forcing Data Adjustment
    'snow_mult': 1.1,               # Snowfall Multiplier [-]
    'srad_mult_summer': 1.05,       # Shortwave Radiation Multiplier (summer) [-]
    'srad_mult_winter': 0.9,      	# Shortwave Radiation Multiplier (winter) [-]
    'lrad_mult_summer': 1.1,        # Longwave Radiation Multiplier (summer) [-]
    'lrad_mult_winter': 1.1,      	# Longwave Radiation Multiplier (winter) [-]
    'airt_adj': 0,                  # Adjustment to air temperature [C]
    'rh_mult': 1.0,                 # Relative humitidy multiplier [-]
    'RainThresh': 2,                # Rain-Snow transition temperature [C] (suggested range: -1 - 3, only if snowfall is not perscribed)
    'RainThresh_dh': 1.0,           # Temperature range over which the rain/snow transition occurs [C] (suggested range: 1 - 2)
    'diffuse_fr_0': 0.1,            # Fraction of shortwave radiation that is diffuse [-] (suggested range: 0.1 - 0.15)
    'LF_trans': 2,                  # Effective LAI for computing for direct and diffuse shortwave radiation under canopy  for Mahat and Tarboton model [-] (suggested range: 2 - 4)
    'lwi_par': 3.15,                # LWI (Or longwave influence of warm tree trunks at the edges of canopy stands) Parameter 1 (suggested range: 0.5 - 1.5)
    'snowfall_wind_trans': 0.0,     # 0 -> Only below canopy wind index is used, 1-> Only above canopy wind index is used), or can be a mixture (suggested range: 0 - 0.5)   
    'snowfall_wind_exp': 2,         # Exponent applied to wind index map (suggested range: 0.5 - 2), only if wind model is on
                                    # Higher values accentuate wind distribution effect, lower values mute wind distribution effect
    
    # Albedo Parameters
    'NoSnowAlbedo_winter': 0.22,    # Albedo of bare ground during the winter (suggested range: 0.2 - 0.3)
    'NoSnowAlbedo_summer': 0.14,    # Albedo of bare ground during the summer (suggested range: 0.1 - 0.2)
    'Snowfall_factor': 200,         # Size of snowfall to fully reset albedo [mm] (suggested range: 10 - 50)
    'MaxAlbedo': 0.82,              # Maximum (or fresh snow) albedo (-) (suggested range: 0.8 - 0.9)
    'minalbedo': 0.2,               # Minimum snowpack albedo [-] (suggested range: 0.3 - 0.4)
    'albedo_decay_cold': 0.01,      # Albedo Decay Factor for cold snowpack [1/day] (suggested range: 0.01 - 0.05)
    'albedo_decay_warm': 0.05,      # Albedo Decay Factor for cold snowpack [1/day] (suggested range: 0.05 - 0.15)
    'albedo_enh_red': 0.5,          # Albedo enhancement or reduction based on SFI (0: no enhancement / reduction -> higher number: more enhancement / reduction)

    # Snow Density Parameters
    'density_min': 0.07,             # Density of new snow [g/cm3] (suggested range: 0.05-0.15)
    'density_max': 0.5,             # Maximum snow density [g/cm3] (suggested range: 0.5-0.6)
    'apar': 0.02,                   # Snow densification rate due to age [Fraction / day] (suggested range: 0.01-0.02)
    'dpar': 0.002,                  # Snow densfication rate due to overburdin [Fraction / cm SWE] (suggested range: 0.001-0.002)
    'rpar': 0.05,                   # Snow densfication rate due to liquid in snowpack [Fraction / day when isothermal snowpack] (suggested range: 0.01-0.1)

    # Snow Interception Parameters
    'melt_drip_par': 0.01,           # Melt Drip Rate [mm/day per deg-C above freezing] (suggested range: 0-1)
    'snow_unload_par': 0.05,         # Fraction of canopy snow that unloads each day [-] (suggested range: 0-1)
    'canopy_sub_mult': 2.0,          # Canopy sublimation multiplier applied to potential sublimation rate (which is computed for snowpack surface) [-] (suggested range: 5-20)
    'C_S_cap_mult': 20,              # Factor multiplied by LAI to compute canopy snow storage capacity (suggested range: 5-20)

    # Rainfall Interception Parameters
    'inter_cap_mult': 5,            # Factor multiplied by LAI to compute canopy snow storage capacity (suggested range: 2-10) in mm
    'drip_par': 5,                  # Drip rate of intercepted water (suggested range: 1-5 mm/day)
    'canevappar': 1,                # Factor multiplied by PET to get canopy evaporation (suggested range: 1-5)

    # Miscellaneous Snowpack Parameters
    'max_sub_pct_when_snow': 0.1,   # Maximum fraction of snowfall that can be sublimation when snowing (suggested range: 0-0.5)
    'max_melt_pct_when_snow': 0.1,  # Maximum fraction of snowfall that can be melt when snowing (suggested range: 0-0.5)
    'Ch': 0.5,                      # Multiplier applied to sensible heating equation (suggested range: 0.5-1)
    'ground_sub_mult': 0.5,         # Ground Sublimation Multiplier (suggested range: 0.5-1)
    'sroughness': 1E-5,             # Snow surface roughness length [m] (suggested range: 1E-5 - 1E-4)
    'windlevel': 10,                # Height of windspeed measurement [m]
    'kappa_snow': 0.1,              # Soil thermal conductivity [W/m/K] (suggested range: 0.05-0.2)
    'kappa_soil': 0.5,              # Snow thermal conductivity [W/m/K] (suggested range: 0.2-1)
    'tempdampdepth': 2,             # Temperature at damping depth underneath a snowpack [C]
    'dampdepth': 1,                 # Damping depth [m]
    'groundveght': 0.2,             # Ground Vegetation height [m] (suggested range 0.05-0.2)
    'fstab': 0,                     # Stability correction [0 1]

    # Note: The soil / vadose zone model still needs some updates.  Right now, it is experimental
    
    # Soil Layer Parameters
    'PET_Mult': 0.3,                # Potential evapotranspirataion multiplier [-]
    'max_infil_mult': 0.2,          # Fraction of incoming water that becomes infiltration excess when the soil moisture is above the level specified by sm_max_infil [-]
    'sm_max_infil': 0.2,            # Soil moisture content below which infiltration excess runoff is minimized [-]
    'H': 300,                       # Thickness of surface soil layer [mm] 
    'ssat': 0.451,                  # Saturated water content [-] (current value for loam)
    'sres': 0.05,                   # Residual water content [-] (current value for loam)
    'psi_s': 146,                   # Soil air entry pressure [cm] (current value for loam)
    'b_soil': 5.39,                 # Pore size distribution index [-] (current value for loam)
    'k_soil': 600.48,               # Saturated hydraulic conductivity [mm/day] (current value for loam)
    'wp': 0.05,                     # Wilting Point [-] (suggested range 0.05-0.15)
    'cmc': 0.3,                     # Critical Moisture Content [-] (suggested range: 0.25-0.35)

    # Vadose Zone Parameters
    'coef_vadose': 0.1,             # Vadose Zone Reservoir Decay Parameter (multiplier) [-]
    'coef_vadose2phreatic': 0.02,   # Leakage Rate between Vadose and Phreatic Reservoirs [-]
    'coef_phreatic': 0.001,         # Phreatic Zone Decay Parameter (multiplier) [-]

    # Initial States
    'albedosnow_i': 0.5,            # Initial snow albedo [-]
    'swe_i': 0,                     # Initial snow water equivalent [mm]
    'cansnowstor_i': 0,             # Initial canopy intercepted snow storage [mm]
    'canrainstor_i': 0,             # Initial canopy intercepted rain storage [mm]
    'density_i': 0.1,               # Initial snow density [g/cm3]
    'Tm_i': 0,                      # Initial snowpack temperature [C]
    'T_soil_i': 0,                  # Initial top soil layer temperature [C]
    'ice_percent_soil_i': 0,        # Initial soil ice fraction [cm3/cm3]
    'sm_i': 0.3,                    # Initial soil moisture [cm3/cm3]
    'q_vadose_i': 0.5,              # Initial water content in the vadose zone (below the top soil layer) [mm]
    'q_phreatic_i': 0.1,            # Initial water content in the preatic zone [mm]
}
