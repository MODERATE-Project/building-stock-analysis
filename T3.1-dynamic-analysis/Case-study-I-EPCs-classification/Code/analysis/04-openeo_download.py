#!/usr/bin/env python
# coding: utf-8

# %%
#----    Settings    ----

from pathlib import Path
import os
import openeo
from pyproj import Geod
import numpy as np
import geopandas as gpd
import shapely as shp
from shapely import wkt
import pandas as pd
import math
import time
import matplotlib.pyplot as plt


# Custom modules
import importlib
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


# %%
#----    Sentinel 2 Tails    ----

print('Checking available Sentinel 2 tails...')

# Get the Sentinel 2 tails covering Lombardy region
S2_tails = openeo_utils.get_S2_tails(
    path_file = 'data/external/S2_tiles.geojson',
    crs = verified_data.crs
    )

# From 'S2_L2A_ALPS', tails '32TNQ' and '32TPQ' are not available
mask  = [tail not in ['32TNQ', '32TPQ'] for tail in S2_tails['id_name']]
S2_tails = S2_tails[mask]
S2_tails = S2_tails.reset_index(drop = True)

# Get Lombardy tail 
tail_region = gpd.GeoDataFrame({
    'id_name':'Lombardy', 
    'geometry':openeo_utils.get_polygon(geom_reg.bounds)
    }, crs = verified_data.crs)

# Crop Sentinel 2 tails to Lombardy tail
S2_tails['geometry'] = S2_tails['geometry'].intersection(tail_region['geometry'].iloc[0])

openeo_utils.plot_tails_grid(
    region = geom_reg,
    tails = S2_tails,
    building_data = verified_data
)

# Lombardy area covered by available Sentinel 2 eurac images
S2_eurac = gpd.GeoDataFrame({
    'id_name':'S2_eurac', 
    'geometry':gpd.GeoSeries(shp.ops.unary_union(S2_tails['geometry']))
    }, crs = verified_data.crs)

S2_eurac.to_file(my_env.S2EURAC, index=False)


# %%
#----    Define Tail Grid    ----

print('Defining tail grid...')

tails = openeo_utils.get_tails(
    data_geom = S2_eurac,
    tail_side_km = 20,
    overlapping_km = 0,
    crs = verified_data.crs
)

# Keep only tails that cover Lombardy and with buildings
tails = openeo_utils.filter_tails(
    tails = tails,
    intersection_with = geom_reg,
    include_elements = verified_data
)

openeo_utils.plot_tails_grid(
    region = geom_reg,
    tails = tails,
    building_data = verified_data
)


# %%
#----    Connect EURAC OpenEO    ----

print('Connecting EURAC OpenEO...')

# EURAC server allows only OIDC auth (https://open-eo.github.io/openeo-python-client/auth.html)
print('Authenticate with OIDC authentication')
connection = openeo.connect(my_env.BACKEND_SERVER)
connection.authenticate_oidc(my_env.CLIENT_ID)
collection_data = connection.describe_collection(my_env.COLLECTION_ID)
collection_info = collection_data['cube:dimensions']
print('Temporal range:', collection_info['DATE']['extent'])
print('Spatial x range:', collection_info['X']['extent'])
print('Spatial y range:', collection_info['Y']['extent'])
print('Reference system:', collection_info['X']['reference_system'])
print('Available bands:', collection_info['bands']['values'])


# %%
#----    Download Tails Timeseries    ----

print('Download tails timeseries...')

bounds_lombardy = geom_reg.bounds

# Check percent builidings available after a given date
start_date_ts = '2021-06-01'
end_date_ts = '2022-09-01'
np.mean(verified_data['DATA_INS'] > start_date_ts)

# %%

openeo_utils.download_datacube_loop(
    tails = tails,
    start_date = start_date_ts,
    end_date = end_date_ts,
    bands = ['CLOUD_MASK'],
    aggregate = 'spatial',
    out_dir = my_env.OPENEODIR / 'cloud-mask',
    connection = connection,
    collection = my_env.COLLECTION_ID,
    backend_server = my_env.BACKEND_SERVER,
    client_id = my_env.CLIENT_ID
    )


# %%
#----    Evaluate Tails Timeseries    ----

print('Evaluating tails timeseries...')

# Get clouds data 
data_cloud = openeo_utils.get_data_cloud_mask(my_env.OPENEODIR / 'cloud-mask')

# Filter winter and summer months
mask = [month in [11, 12, 1, 2, 5, 6, 7, 8, 9] for month in data_cloud['date_time'].dt.month]
data_cloud = data_cloud[mask]
data_cloud = data_cloud.reset_index(drop = True)

# Compute number of buildings per tail
tails['n_build'] = tails['geometry'].apply(lambda x:\
    sum(verified_data['geometry'].within(x))
    )

# Joining data
data_cloud = data_cloud.join(
    tails.set_index('id_name').drop(['id_parent', 'geometry'], axis = 1),
    on = 'id_name')

# Compute score (the higher the better)
data_cloud['score'] = data_cloud.apply(lambda x:\
    (1 - x['cloud_mask']) * x['n_build'], axis = 1)

# All data are between 10:15 and 10:40
min_time = data_cloud['date_time'].dt.time.min()
max_time = data_cloud['date_time'].dt.time.max()
print('Range time: {} - {}'.format(min_time, max_time))

# %%
# Group by date
data_cloud['date'] = data_cloud['date_time'].dt.date

# Summarize tails with multiple values same day
info_cloud = data_cloud.groupby(['id_name', 'date'], as_index = False)\
    .agg(
        n_build = ('n_build', 'first'),
        cloud_mask = ('cloud_mask', 'max'),
        score = ('score', 'min')
    )

# Summarize info for each day
info_cloud = info_cloud.groupby(['date'], as_index = False)\
    .agg(
        n_tail = ('date', 'size'),
        n_build_sum = ('n_build', 'sum'),
        cloud_mask_avg = ('cloud_mask', 'mean'),
        cloud_mask_max = ('cloud_mask', 'max'),
        score_sum = ('score', 'sum')
    )

# Possible good dates
sel_dates = ['2021-12-07', '2022-01-11', '2022-01-16', # Winter
             '2021-07-20', '2021-08-14'] # Summer
mask = [str(date) in sel_dates for date in info_cloud['date']]
info_cloud[mask].sort_values(by = ['score_sum'], ascending = False)


# %%
#----    Download Tails Images    ----

print('Downloading tails images...\n')

# Define tails with overlapping borders
tails = openeo_utils.get_tails(
    data_geom = S2_eurac,
    tail_side_km = 20,
    overlapping_km = 0.3,
    crs = verified_data.crs
)

# Keep only tails that cover Lombardy and with buildings
tails = openeo_utils.filter_tails(
    tails = tails,
    intersection_with = geom_reg,
    include_elements = verified_data
)

openeo_utils.plot_tails_grid(
    region = geom_reg,
    tails = tails,
    building_data = verified_data
)

# %%
# ATTENTION: the OpenEO servers are not stable (if the download of a raster 
# fails, just try again: unfortunately, the server do not show the error which 
# causes the problem)

# winter day '2022-01-11'
start_date_winter = '2022-01-10'
end_date_winter = '2022-01-12'  
# summer day '2022-08-14'
start_date_summer = '2021-08-13'
end_date_summer = '2021-08-15'  


# %%
# Winter

# Download tails (if fails try up to 1 + 3 times) 
n_trial = 0
fails = tails['id_name'].unique()
while ((len(fails) > 0) & (n_trial < 4)):
    print("Downloading winter images...")
    mask = [id in fails for id in tails['id_name']]
    tails_to_download = tails[mask]

    successes, fails = openeo_utils.download_datacube_loop(
        tails = tails_to_download,
        start_date = start_date_winter,
        end_date = end_date_winter,
        bands = ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B11', 
                 'B12', 'B8A', 'SCL', 'WVP', 'CLOUD_MASK'],
        aggregate = 'temporal',
        out_dir = my_env.OPENEODIR / 'winter',
        connection = connection,
        collection = my_env.COLLECTION_ID,
        backend_server = my_env.BACKEND_SERVER,
        client_id = my_env.CLIENT_ID
        )

    n_trial = n_trial + 1


# %%
# Summer

# Download tails (if fails try up to 1 + 3 times) 
n_trial = 0
fails = tails['id_name'].unique()
while ((len(fails) > 0) & (n_trial < 4)):
    print("Downloading summer images...")
    mask = [id in fails for id in tails['id_name']]
    tails_to_download = tails[mask]

    successes, fails = openeo_utils.download_datacube_loop(
        tails = tails_to_download,
        start_date = start_date_summer,
        end_date = end_date_summer,
        bands = ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B11', 'B12', 
                 'B8A', 'SCL', 'WVP', 'CLOUD_MASK'],
        aggregate = 'temporal',
        out_dir = my_env.OPENEODIR / 'summer',
        connection = connection,
        collection = my_env.COLLECTION_ID,
        backend_server = my_env.BACKEND_SERVER,
        client_id = my_env.CLIENT_ID
        )
    
    n_trial = n_trial + 1


#==================
