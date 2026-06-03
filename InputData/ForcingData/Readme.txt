This folder contains in situ forcing datasets to use with SnowPALM.  Depending on the model 
configuration (e.g. run with only the downscaled gridded forcing inputs, whether precipitation
and temperature should be corrected to local data at a monthly scale - requiring local 
monthly forcing data file, and/or whether daily or hourly station data should be used - requiring 
the daily or hourly forcing data files.

A note on timesteps: all times are local - using a constant UTC offset.  Since the gridded 
datasets are based on UTC, the model takes this into account (by introducing a date shift 
based on a specified UTC offset (which is specified in a model run file - GetForcingData.py).