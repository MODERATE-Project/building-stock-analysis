#!/usr/bin/env python
# coding: utf-8

# %%
#----    Settings    ----

from pathlib import Path
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.plot import show
import rasterstats
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Polygon
import re
import timeit

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

print('Loading data...')

# Read verified buildings
verified_data = gpd.read_file(my_env.CENEDPROCESSEDSHAPE)
verified_data['DATA_INS'] = pd.to_datetime(verified_data['DATA_INS'], format='%d/%m/%Y')
verified_data = verified_data.to_crs('EPSG:32632') # raster data crs

# Read S2 tails area available in eurac server
S2_all = gpd.read_file(my_env.S2EURAC)
S2_all = S2_all.to_crs(verified_data.crs)

# Read OSM buildings 
osm_buildings = gpd.read_file(my_env.OSMBUILDINGS)
osm_buildings = osm_buildings.to_crs(verified_data.crs)


# %%
#----    Filtering Data    ----
print('Filtering data...')

my_data = verified_data.copy()

# Store record of building point
my_data = my_data.rename(columns={'geometry':'geometry_point'})

# Join OSM building geom
my_data = my_data.join(
    osm_buildings.set_index('COD_APE'), 
    on = 'COD_APE', 
    how = 'left')

# Compute distance point to geom
my_data['distance'] = my_data['geometry'].distance(my_data['geometry_point'])

# Keep only buildings within available S2 images
mask_S2 = [point.within(S2_all.geometry.iloc[0]) for point in my_data['geometry_point']]

# Keep buildings with certification previous to '2021-08-14'
mask_date = my_data['DATA_INS'] <= '2021-08-14'

# Remove entries with empty geometry 
mask_geom = ~ my_data['geometry'].isnull()

# Remove entries with distance higher than 50m
mask_distance = my_data['distance'] <= 50

# All buildings are expected more than 100 m2
mask_area = my_data.area >= 100

mask = pd.DataFrame(zip(
    mask_S2, 
    mask_date, 
    mask_geom, 
    mask_distance, 
    mask_area)).apply(all, axis = 1)

my_data = my_data[mask]

# Remove entries with same geometry (keep the closest one)
my_data = my_data.sort_values(by = 'distance') 
my_data = my_data.drop_duplicates('geometry', keep = 'first')

# Sort and reindex
my_data = my_data.sort_index()
my_data = my_data.drop(['distance'], axis = 1)
my_data = my_data.reset_index(drop = True)

# %%
#----    Add ERA5 temperature data    ----

data_era5 = gpd.read_file(my_env.ERA5TEMPERATURE).to_crs(verified_data.crs)

my_data[['temp_winter', 'temp_summer']] = np.nan

# %%
print('Adding ERA5 temperature data...')
len_era5 = len(data_era5)
for i, row in data_era5.iterrows():
    if i%20 == 0:
        print(f'{i}/{len_era5}')
    
    mask = my_data['geometry_point'].within(row['geometry'])
    my_data.loc[mask, 'temp_winter'] = row['temp_winter']
    my_data.loc[mask, 'temp_summer'] = row['temp_summer']


# %%
#----    Winter Images Data    ----
print('Getting winter images data...')

files_winter = [
    my_env.OPENEODIR / 'winter'/ file \
    for file in os.listdir(my_env.OPENEODIR / 'winter')\
    if not file.startswith('.DS_Store')
    ]

bands_stats_winter = openeo_utils.loop_get_bands_stats(
    files = files_winter,
    geom_data = my_data
    )

bands_stats_winter = bands_stats_winter.add_prefix("winter_")


# %%
#----    Summer Images Data    ----
print('Getting summer images data...')

files_summer = [
    my_env.OPENEODIR / 'summer'/ file \
    for file in os.listdir(my_env.OPENEODIR / 'summer')\
    if not file.startswith('.DS_Store')
    ]


bands_stats_summer = openeo_utils.loop_get_bands_stats(
    files = files_summer,
    geom_data = my_data
    )

bands_stats_summer = bands_stats_summer.add_prefix("summer_")


# %%
#----    Finalize Dataset    ----
print('Finalizing dataset...')

# Combine winter and summer bands
bands_stats = pd.concat([bands_stats_winter, bands_stats_summer], axis = 1)

# Check
print('Same count of pixels: {}'.format(
    all(bands_stats['winter_count'] == bands_stats['summer_count'])))
print('Same COD_APE: {}'.format(
    all(bands_stats['winter_COD_APE'] == bands_stats['summer_COD_APE'])))

bands_stats = bands_stats.rename(columns = {
    'winter_COD_APE':'COD_APE',
    'winter_count':'count'
    })
bands_stats = bands_stats.drop(['summer_count', 'summer_COD_APE'], axis = 1)

# Combine with buildings data
my_data = my_data.join(
    bands_stats.set_index('COD_APE'),
    how = 'left',
    on = 'COD_APE'
    )

# move to pandas dataframe
my_data = my_data.drop(['geometry', 'geometry_point', 'id_tail'], axis = 1)

# %%
# Filtering

# Clouds
mask_clouds_summer = my_data['summer_CLOUD_MASK_max'] <= .2
mask_clouds_winter = my_data['winter_CLOUD_MASK_max'] <= .2

# Shadow
bands_summer = ['summer_' + band + '_max' for band in ['B02','B03', 'B04', 'B05', 'B06']]
mask_shadow_summer = ~ openeo_utils.test_shadow(
    data = my_data,
    col_bands = bands_summer,
    val = 100)

bands_winter = ['winter_' + band + '_max' for band in ['B02','B03', 'B04', 'B05', 'B06']]
mask_shadow_winter = ~ openeo_utils.test_shadow(
    data = my_data,
    col_bands = bands_winter,
    val = 100)

mask = pd.DataFrame(zip(
    mask_clouds_summer, 
    mask_clouds_winter, 
    mask_shadow_summer, 
    mask_shadow_winter)).apply(all, axis = 1)

my_data = my_data[mask]

# %%
# Save the data 
my_data.to_csv(my_env.DATAANALYSIS, index = False)


# %%


# # Scene Classification Values
# # https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm
# # 0 = nodata, 1 = defective, 2-3 = shadows, 4 = vegetation, 5 = not vegetation, 6 = water, 
# # 7-8-9 = low, medium and high probability of clouds, 10 = thin cirrus cloud, 11 = snow or ice
# print(verified_data_full["SCL"].value_counts())

# # NOTE: points with SCL = 0 are not usable, all data is equal to 0 - this happens due to atmospheric problems or electronic failures
# #       during the recording of the image or the communication with the satellite
# mask = verified_data_full["SCL"] == 0
# verified_data_full_filtered1 = verified_data_full[~mask]


# # Additional cloud mask generated using s2cloudless (provided by openEO)
# # https://medium.com/sentinel-hub/sentinel-hub-cloud-detector-s2cloudless-a67d263d3025
# # 1 = cloud, 0 = no cloud
# print(verified_data_full_filtered1["CLOUD_MASK"].value_counts())

# # NOTE: cloudy points are also a potential problem to the quality of data
# mask = verified_data_full_filtered1["CLOUD_MASK"] == 0
# verified_data_full_filtered2 = verified_data_full_filtered1[mask]
