This directory contains shapefiles that are used by the SnowPALM point simulations.  
The shapefiles can either have points or areas and can have any valid projection.  
The one requirement is that they need two attributes called "FID" and "Name".  "FID"
just needs to contain unique numbers for each feature, and the "Name" indicates what
the SnowPALM outputs for the each location will be called.  If the feature is a point,
SnowPALM will produce timeseries output for the pixel that contains the point feature,
and if the feature is an area, SnowPALM will produce average timeseries output for the 
pixels that are covered by the area.
