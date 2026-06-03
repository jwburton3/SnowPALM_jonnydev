import sys
import os
sys.path.insert(1, 'ProgramFiles')
import dateutil.parser
import Output
program_pars = {}

# Simulation Parameters

program_pars['SimulationName'] = sys.argv[1]        # Name of simulation
program_pars['Verbose'] = False                     # Verbose Output

program_pars['NProcesses'] = 60

StartDate_str = sys.argv[2]
EndDate_str = sys.argv[3]
program_pars['StartDate'] = dateutil.parser.parse(StartDate_str)        # Simulation Start Date
program_pars['EndDate'] = dateutil.parser.parse(EndDate_str)            # Simulation End Date

program_pars['VarList'] = sys.argv[4]

# Additional Parameters (probably no change)

program_pars['ModelDir'] = 'Model/' + program_pars['SimulationName']                # Directory where model files are saved
program_pars['OutputDir'] = 'Output/' + program_pars['SimulationName']              # Directory where output files are saved
program_pars['least_significant_digit'] = 3                                         # Smallest decimal place in unpacked data that is a reliable value for nc data
program_pars['CreatePyramids'] = False                                              # Create pyramids for faster display (only affects tile maps)

## Call function to Output Data
if __name__ == '__main__':
    Output.getData(program_pars)
    