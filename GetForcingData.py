import sys, os
sys.path.insert(1, 'ProgramFiles')
import Forcing
pars = {}

#################### General Parameters ####################

pars['Verbose'] = True                                # Verbose output
pars['GriddedForcingDir'] = 'GriddedForcing'     # Directory containing gridded forcing data
# Note: Existing files will always be overwritten!!!
pars['prism_ppt_version'] = 3                   # PRISM Precip version
pars['prism_tmean_version'] = 3                 # PRISM TMean version
pars['PRISMLapsePX'] = 3                        # Number of surrounding rows and columns to calclate local lapse rates (1 implies 9 pixels, 2 implies 25 pixels, 3 implies 49 pixels ...)
pars['NLDASResamplingMethod'] = 'bilinear'      # Resampling method applied to NLDAS data
pars['least_significant_digit'] = 3             # Smallest decimal place in unpacked data that is a reliable value

pars['ForcingSetName'] = sys.argv[1]
pars['StartYear'] = eval(sys.argv[2])
pars['StartMonth'] = eval(sys.argv[3])
pars['EndYear'] = eval(sys.argv[4])
pars['EndMonth'] = eval(sys.argv[5])

#################### Get Forcing Data ####################

pars['UTCOffset'] = -7                      # Local UTC offset (for NLDAS data)

if pars['ForcingSetName'] == 'DailyNLDASData':
    # Daily forcing files (needed if using Data Source = 1 (Local Station))
    pars['DailyForcingFile'] = ''
    # Monthly forcing files (needed for Lapse Rates = 2 (PRISM lapse rate corrected to station data))
    pars['MonthlyForcingFile'] = ''
    pars['DataSource'] = 0                      # 0: NLDAS, 1: Local Station
    pars['FillWithNLDAS'] = True                # Fill Missing Station Data with NLDAS data (only when station data is used)
    pars['ApplyPPTLapseRate'] = 1               # Apply monthly lapse rate precipitation correction (0: None, 1: PRISM-based, 2: PRISM-based lapse rate with station based correction)
    pars['ApplyAirTLapseRate'] = 1              # Apply monthly lapse rate temperature correction (0: None, 1: PRISM-based, 2: PRISM-based lapse rate with station based correction)
    pars['OutputTimestep'] = 1                  # 0: Hourly, 1: Daily

elif pars['ForcingSetName'] == 'HourlyNLDASData':
    # Daily forcing files (needed if using Data Source = 1 (Local Station))
    pars['DailyForcingFile'] = ''
    # Monthly forcing files (needed for Lapse Rates = 2 (PRISM lapse rate corrected to station data))
    pars['MonthlyForcingFile'] = ''
    pars['DataSource'] = 0                      # 0: NLDAS, 1: Local Station
    pars['FillWithNLDAS'] = True                # Fill Missing Station Data with NLDAS data (only when station data is used)
    pars['ApplyPPTLapseRate'] = 1               # Apply monthly lapse rate precipitation correction (0: None, 1: PRISM-based, 2: PRISM-based lapse rate with station based correction)
    pars['ApplyAirTLapseRate'] = 1              # Apply monthly lapse rate temperature correction (0: None, 1: PRISM-based, 2: PRISM-based lapse rate with station based correction)
    pars['OutputTimestep'] = 0                  # 0: Hourly, 1: Daily

elif pars['ForcingSetName'] == 'DailyStationData':

    # Daily forcing files (needed if using Data Source = 1 (Local Station))
    pars['DailyForcingFile'] = 'InputData/ForcingData/MaverickForkDailyForcing.csv'
    # Monthly forcing files (needed for Lapse Rates = 2 (PRISM lapse rate corrected to station data))
    pars['MonthlyForcingFile'] = 'InputData/ForcingData/MaverickForkMonthlyForcing.csv'
    pars['DataSource'] = 1                      # 0: NLDAS, 1: Local Station
    pars['FillWithNLDAS'] = False                # Fill Missing Station Data with NLDAS data
    pars['ApplyPPTLapseRate'] = 2               # Apply monthly lapse rate precipitation correction (0: None, 1: PRISM-based, 2: PRISM-based lapse rate with station based correction)
    pars['ApplyAirTLapseRate'] = 2              # Apply monthly lapse rate temperature correction (0: None, 1: PRISM-based, 2: PRISM-based lapse rate with station based correction)
    pars['OutputTimestep'] = 1                  # 0: Hourly, 1: Daily
    
    
pars['LoResDTMFile'] = os.getcwd() + '/Preprocess/GIS/DTM_small.tif'            # Low Resolution DTM (defines grid and lapse rates for forcing data)
pars['NLDASForcingDir'] = pars['GriddedForcingDir'] + '/NLDAS'                  # Path to NLDAS Data Directory
pars['PRISMForcingDir'] = pars['GriddedForcingDir'] + '/PRISM'  
pars['OFDir'] = os.getcwd() + '/Preprocess/Forcing/' + pars['ForcingSetName']   # Output Directory

if __name__ == '__main__':
    Forcing.GetForcingData(pars)