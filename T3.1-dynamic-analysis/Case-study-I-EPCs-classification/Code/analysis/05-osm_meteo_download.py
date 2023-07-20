#!/usr/bin/env python
# coding: utf-8

# %%
#----    Settings    ----

from pathlib import Path
import os
import osmnx as ox
from pyproj import Geod
import geopandas as gpd
import shapely as shp
from shapely import wkt
import pandas as pd
import math
import numpy as np
import time
import matplotlib.pyplot as plt
import timeit
import rasterio
from rasterio.plot import show
from rasterio.plot import show_hist


# Custom modules
from src.utils import my_utils
from src.utils import openeo_utils

if my_utils.in_ipython():
    # Automatic reload custom module to allow interactive development
    # https://stackoverflow.com/a/35597119/12481476
    from IPython import get_ipython
    get_ipython().run_line_magic('reload_ext', 'autoreload')
    get_ipython().run_line_magic('aimport', 'src.utils.my_utils')
    get_ipython().run_line_magic('aimport', 'src.utils.openeo_utils')
    get_ipython().run_line_magic('autoreload', '1')

# load environment variables
from py_config_env import EnvironmentLoader

env_loader = EnvironmentLoader(
    env_file='my-env',  # File to load
    env_path='environments'  # Path where files are contained
)

# Object containing loaded environmental variables
my_env = env_loader.configuration.get('my_env')

# Pass environment variables to custom module
openeo_utils.my_env = my_env


# %%
#----    Data Loading    ----

print('Data Loading...')

# Read verified buildings
verified_data = gpd.read_file(my_env.CENEDPROCESSEDSHAPE)
verified_data['DATA_INS'] = pd.to_datetime(verified_data['DATA_INS'], format='%d/%m/%Y')

# Read lombardy data (source: https://www.istat.it/it/archivio/222527)
geom_reg = openeo_utils.get_lombardy_geom(
    path = my_env.GEOREGION,
    crs = verified_data.crs
)

# Read S2 tails area available in eurac server
S2_all = gpd.read_file(my_env.S2EURAC)

# Keep only buildings within available S2 images
mask = [point.within(S2_all.geometry.iloc[0]) for point in verified_data.geometry]
verified_data = verified_data[mask].reset_index(drop = True)


# %%
#----    Define Tail Grid    ----

print('Defining tail grid...')

# Create inner tails and outer tails (with overlapping) to ensure including the 
# complete area of each building.   
#  - building points are identified using inner tails
#  - building areas are identified  using outer tails

# Inner (Keep only tails that cover Lombardy and with buildings)
tails_inner = openeo_utils.get_tails(
    data_geom = S2_all,
    tail_side_km = 20,
    overlapping_km = 0,
    crs = verified_data.crs
)
tails_inner = openeo_utils.filter_tails(
    tails = tails_inner,
    intersection_with = geom_reg,
    include_elements = verified_data
)

# Outer (Keep only tails that cover Lombardy and with buildings)
tails_outer = openeo_utils.get_tails(
    data_geom = S2_all,
    tail_side_km = 20,
    overlapping_km = .3,
    crs = verified_data.crs
)
tails_outer = openeo_utils.filter_tails(
    tails = tails_outer,
    intersection_with = geom_reg,
    include_elements = verified_data
)

openeo_utils.plot_tails_grid(
    region = geom_reg,
    tails = tails_outer,
    building_data = verified_data
)



# %%
#----    Download OSM Data    ----

# 'COD_APE' used as builidng ID
osm_buildings = verified_data[['COD_APE', 'geometry']].copy()

# Assign tail id_name for each available building
osm_buildings['id_tail'] = osm_buildings['geometry']\
    .apply(lambda x: openeo_utils.assign_tail(geom = x, data_tail = tails_inner))

# Bounds of outer tails used to download OSM data
tails_outer = pd.concat([tails_outer, tails_outer.bounds], axis = 1)

# Use projected crs for computing distance
osm_buildings = osm_buildings.to_crs('EPSG:32632')


# %% 

# Loop along tails, download data and get building polygons 
start = timeit.default_timer()
for index, tail in tails_outer.iterrows():
    start_iter = timeit.default_timer()
    print('\n\nTail {}/{}'.format(index + 1, len(tails_outer)))
    id_tail = tail['id_name']
    
    print('Downloading OSM data...')
    # Download buildings OSM data for the tail
    osm_data = ox.geometries_from_bbox(
        north = tail['maxy'],
        south = tail['miny'],
        east = tail['maxx'],
        west = tail['minx'],
        tags = {'building': True}
        )
    osm_data = osm_data.to_crs(osm_buildings.crs) # web mercator crs

    # Subset buildings in the current tail 
    mask = osm_buildings['id_tail'] == id_tail

    # Get geometry and distance of the closest OSM building
    print('Getting closest buildings (n = {})...'.format(len(osm_buildings.loc[mask])))
    osm_buildings.loc[mask, 'geometry'] = osm_buildings.loc[mask, 'geometry']\
                .apply(lambda x: openeo_utils.get_closest_geom(
                    point = x,
                    geoms = osm_data.geometry,
                    initial_buffer= 20,
                    max_buffer = 100
                    )
                )

    stop = timeit.default_timer()
    print('Iter Time: {:.2f}'.format(stop - start_iter))
    print('Total Time: {:.2f}'.format(stop - start))

# %%
# Save final result
osm_buildings = osm_buildings.to_crs(verified_data.crs) # return to EPSG:4326

osm_buildings.to_file(my_env.OSMBUILDINGS, index = False, driver = 'GeoJSON')


# %%
#----    Plot OSM Data    ----

tail_outer = tails_outer.iloc[5]
tail_inner = tails_inner.iloc[5]
osm_data = ox.geometries_from_bbox(
        north = tail_outer['maxy'],
        south = tail_outer['miny'],
        east = tail_outer['maxx'],
        west = tail_outer['minx'],
        tags = {'building': True}
        )
mask = osm_buildings.within(tail_inner['geometry'])

# %%
ax = geom_reg['geometry'].intersection(tail_outer['geometry']).plot(figsize=(50,50), alpha = .3)
osm_data.plot(ax = ax)
# osm_buildings.loc[mask].plot(ax = ax, color = 'green')
# verified_data.loc[mask].plot(ax = ax, color = 'red', markersize = 1)
plt.show()


# %%
#----    Plot Satellite Image    ----
# Satelite image
img_winter = 'winter/tail_S2_eurac_2x3_openeo_2022-01-10_2022-01-12_now_2022-11-16_h12_m31_s22'
img_summer = 'summer/tail_S2_eurac_2x3_openeo_2021-08-13_2021-08-15_now_2022-11-16_h13_m55_s11'

openeo_utils.plot_satellite(
    file = Path(my_env.OPENEODIR / img_summer),
    bands = [4,3,2],
    osm_raster = osm_data,
    buildings = osm_buildings.loc[mask],
    points = verified_data.loc[mask],
    figsize = (10, 10)
    )

# %%
#----    Get Era5 Data    ----

# get data ERA5 2m temperature https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels?tab=overview

# Data have been downloaded manually form the website.

# Winter data includes
# [1:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 8 hrs:from 202201110000,
#  2:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 9 hrs:from 202201110000,
#  3:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 10 hrs:from 202201110000,
#  4:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 11 hrs:from 202201110000,
#  5:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 12 hrs:from 202201110000,
#  6:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 13 hrs:from 202201110000,
#  7:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 14 hrs:from 202201110000]
#  data at time 10 is used
data_winter = openeo_utils.get_data_era_5(my_env.ERA5WINTER_IMPORT, 
                                          layer=2, 
                                          crs = verified_data.crs)

# Summer data includes
# [1:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 10 hrs:from 202108140000,
#  2:2 metre temperature:K (instant):regular_ll:surface:level 0:fcst time 11 hrs:from 202108140000]
# data at time 10 is used
data_summer = openeo_utils.get_data_era_5(my_env.ERA5SUMMER_IMPORT, 
                                          layer=0,
                                          crs = verified_data.crs)


data_era5 = pd.merge(data_winter, data_summer, 
                     on='geometry', 
                     suffixes= ('_winter', '_summer'))
data_era5 = data_era5.loc[:,['temp_winter', 'temp_summer', 'geometry']]

# %%
data_era5.to_file(my_env.ERA5TEMPERATURE, index = False, driver = 'GeoJSON')


# %%
