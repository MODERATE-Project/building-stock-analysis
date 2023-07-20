#!/usr/bin/env python
# coding: utf-8


#%%
#----    Settings    ----

from pickle import TRUE
import pandas as pd
import numpy as np
from pathlib import Path
import os
import re
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.geocoders import Bing
from geopy.geocoders import GoogleV3
from geopy.extra.rate_limiter import RateLimiter
import geopandas as gpd
from pyparsing import col
from tqdm import tqdm
import time
from shapely import wkt
import matplotlib.pyplot as plt

# Custom modules
from src.utils import my_utils
from src.utils import cened_utils

if my_utils.in_ipython():
    # Automatic reload custom module to allow interactive development
    # https://stackoverflow.com/a/35597119/12481476
    from IPython import get_ipython
    get_ipython().run_line_magic('reload_ext', 'autoreload')
    get_ipython().run_line_magic('aimport', 'src.utils.my_utils')
    get_ipython().run_line_magic('aimport', 'src.utils.cened_utils')
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
cened_utils.my_env = my_env

# set pandas visualization options
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 200)
pd.set_option('display.max_colwidth', 400)
tqdm.pandas()


# %%
#----    Data Loading    ----

print('Data Loading...')

# read filtered cened data
cened_data = pd.read_csv(my_env.CENEDOUTPUT, dtype=str)

# create a full address to be used for geocoding purposes
cened_data['INDIRIZZO_FULL'] = cened_data['INDIRIZZO'] + ' ' + cened_data['COMUNE']


# %%
#----    Geocoding OSM    ----

print('Geocoding OSM...')

# osm geocoder (geocoding policy: https://operations.osmfoundation.org/policies/nominatim/)
# - limit per second: 1, limit per day: no, limit per key: no
# - key required: no
# - notes: bulk requests should not be done on a regular basis, and only on small amounts of data

cened_utils.geocode_data(
    data = cened_data,
    provider = 'osm',
    output_dir = my_env.CONVERTEDDIR,
    cache_name = 'osm',
    var_address = 'INDIRIZZO_FULL',
)
# API responses saved in my_env.CONVERTEDDIR/osm
# outputs: osm_cened_good.csv and osm_cened_bad.csv saved in my_env.CONVERTEDDIR


# %%
#----    Geocoding Bing    ----

print('Geocoding Bing...')

# bing geocoder (https://www.microsoft.com/en-us/maps/licensing)
# - limit per second: no, limit per day: 50.000, limit per key: 125.000
# - key required: yes
bad_data = pd.read_csv(my_env.CONVERTEDDIR / Path('osm_' + my_env.CENEDBAD))

cened_utils.geocode_data(
    data = cened_data,
    provider = 'bing',
    output_dir = my_env.CONVERTEDDIR,
    cache_name = 'bing',
    var_address = 'INDIRIZZO_FULL',
)
# API responses saved in my_env.CONVERTEDDIR/bing
# outputs: bing_cened_good.csv and bing_cened_bad.csv saved in my_env.CONVERTEDDIR


# %%
#----    Geocoding Google    ----

print('Geocoding Google...')

# google geocoder (https://developers.google.com/maps/faq#usage_apis)
# - limit per second: 50, limit per day: no, limit per key: 200USD free per month (1k requests = 5USD)
# - key required: yes
bad_data = pd.read_csv(my_env.CONVERTEDDIR / Path('bing_' + my_env.CENEDBAD))

cened_utils.geocode_data(
    data = cened_data,
    provider = 'google',
    output_dir = my_env.CONVERTEDDIR,
    cache_name = 'google',
    var_address = 'INDIRIZZO_FULL',
)
# API responses saved in my_env.CONVERTEDDIR/google
# outputs: google_cened_good.csv and google_cened_bad.csv saved in my_env.CONVERTEDDIR


# %%
#----    Geocoded data    ----

print('Full geocoded data')

# concatenate good data (buildings with geocoding checked to rooftop level)
good_osm = pd.read_csv(my_env.CONVERTEDDIR / Path('osm_' + my_env.CENEDGOOD))
good_bing = pd.read_csv(my_env.CONVERTEDDIR / Path('bing_' + my_env.CENEDGOOD))
good_google = pd.read_csv(my_env.CONVERTEDDIR / Path('google_' + my_env.CENEDGOOD))
good_osm['PROVIDER'] = 'osm'
good_bing['PROVIDER'] = 'bing'
good_google['PROVIDER'] = 'google'
good_full = pd.concat([good_osm, good_bing, good_google])


# %%
#----    Projected Data    ----

print('Projecting data...')

# project points on a common CRS to check the geocoding geographically
# WGS84 latitude-longitude projection corresponds to EPSG:4326 
# (https://geopandas.org/en/stable/docs/user_guide/projections.html)

projected_data = cened_utils.get_projected_data(
    geocoded_data = good_full, 
    data_ref = cened_data,
)


# %%
#----    Check Region    ----

print('Checking within region...')

# Get Lombardy region geometry data
geom_reg = gpd.read_file(my_env.GEOREGION, encoding='utf-8')  # source: https://www.istat.it/it/archivio/222527
geom_reg = geom_reg.to_crs(projected_data.crs)
geom_reg = geom_reg.rename(columns={'DEN_REG': 'REGIONE'})

mask = geom_reg['REGIONE']=='Lombardia'
geom_reg = geom_reg[mask]


# %%

# check if points are within lombardy
projected_reg_in, projected_reg_out, projected_reg_unverified = cened_utils.\
    check_borders(
    projected_data = projected_data,
    geom_data = geom_reg,
    var_match = 'REGIONE'
    )


# %%
#----    Check Municipality    ----

print('Checking within municipalities...')

# check if points are within the municipality
geom_mun = gpd.read_file(my_env.GEOMUNICIPALITY, encoding='utf-8')   # source: https://www.istat.it/it/archivio/222527
geom_mun = geom_mun.to_crs(projected_data.crs)

# get Lombardy code checking for Milan
cod_reg = geom_mun[geom_mun['COMUNE'] == 'Milano']['COD_REG'].iloc[0]

# keep only municipalities in Lombardy and useful columns
mask = geom_mun['COD_REG'] == cod_reg
geom_mun = geom_mun[mask].drop(['COD_RIP', 'COD_REG', 'COD_PROV', 'COD_CM', 
                                'COD_UTS', 'PRO_COM', 'PRO_COM_T', 'COMUNE_A',
                                'CC_UTS', 'Shape_Leng', 'Shape_Area'], axis=1)


# %%

# check if points are within their municipalities
projected_mun_in, projected_mun_out, projected_mun_unverified = cened_utils.\
    check_borders(
    projected_data = projected_reg_in,
    geom_data = geom_mun,
    var_match = 'COMUNE'
    )


#%%
#----    Improving Geocoding Verification    ----

# Try improve geocoding of buildings out of region or municipality by specifying
# also the region in the address

#[Note: Ideally the region should be specified by the beginning in the first 
#       definition of 'INDIRIZZO_FULL'. But I (Claudio) was not able to run 
#       the script from the begininng as google does not accept my debit card]
data_to_geocode = pd.concat([projected_reg_out, projected_mun_out])
data_to_geocode['INDIRIZZO_FULL'] = data_to_geocode['INDIRIZZO_FULL'] + ', ' + data_to_geocode['REGIONE']


# %%
#----    Geocoding Bing Verification    ----
# [Note: Bing Verification would not be needed if the script is run from the 
#        beginning. Ideally, you would go directly to Google verification, 
#        geocoding all data in data_to_geocode. I (Claudio) was not able to run 
#        the Google geocodig as I  google does not accept my debit card]

print('Geocoding Bing Verification...')

# bing geocoder (https://www.microsoft.com/en-us/maps/licensing)
# - limit per second: no, limit per day: 50.000, limit per key: 125.000
# - key required: yes

cened_utils.geocode_data(
    data = data_to_geocode,
    provider = 'bing',
    output_dir = my_env.CONVERTEDDIR,
    cache_name = 'bing_verification',
    var_address = 'INDIRIZZO_FULL',
)
# API responses saved in my_env.CONVERTEDDIR/bing_verification
# outputs: bing_verification_cened_good.csv and bing_verification_cened_bad.csv 
#          saved in my_env.CONVERTEDDIR


# %%
#----    Check Projection Bing Verification    ----

# Load data geocoded correctly
good_bing_verification = pd.read_csv(my_env.CONVERTEDDIR / Path('bing_verification_' + my_env.CENEDGOOD))
good_bing_verification['PROVIDER'] = 'bing'

# project points on a common CRS to check the geocoding geographically
projected_bing_verification = cened_utils.get_projected_data(
    geocoded_data = good_bing_verification, 
    data_ref = projected_data,
)


# %%

# check if points are within lombardy
print('Checking within region...')
bing_verification_reg_in, bing_verification_reg_out, bing_verification_reg_unverified = cened_utils.\
    check_borders(
    projected_data = projected_bing_verification,
    geom_data = geom_reg,
    var_match = 'REGIONE'
    )


# %%

# check if points are within municipalities
print('Checking within municipalities...')
bing_verification_mun_in, bing_verification_mun_out, bing_verification_mun_unverified = cened_utils.\
    check_borders(
    projected_data = bing_verification_reg_in,
    geom_data = geom_mun,
    var_match = 'COMUNE' 
    )


# %%
#----    Geocoding Google Verification    ----
print('Geocoding Google Verification...')

# google geocoder (https://developers.google.com/maps/faq#usage_apis)
# - limit per second: 50, limit per day: no, limit per key: 200USD free per month (1k requests = 5USD)
# - key required: yes
bad_data = pd.concat([bing_verification_reg_out, bing_verification_mun_out])

cened_utils.geocode_data(
    data = bad_data,
    provider = 'google',
    output_dir = my_env.CONVERTEDDIR,
    cache_name = 'google_verification',
    var_address = 'INDIRIZZO_FULL',
)
# API responses saved in my_env.CONVERTEDDIR/google_verification
# outputs: google_verification_cened_good.csv and google_verification_cened_bad.csv 
#          saved in my_env.CONVERTEDDIR


# %%
#----    Check Projection Google Verification    ----

# Load data geocoded correctly 
good_google_verification = pd.read_csv(my_env.CONVERTEDDIR / Path('google_verification_' + my_env.CENEDGOOD))
good_google_verification['PROVIDER'] = 'google'

# project points on a common CRS to check the geocoding geographically
projected_google_verification = cened_utils.get_projected_data(
    geocoded_data = good_google_verification, 
    data_ref = projected_data,
)


# %%

# check if points are within lombardy
print('Checking within region...')
google_verification_reg_in, google_verification_reg_out, google_verification_reg_unverified = cened_utils.\
    check_borders(
    projected_data = projected_google_verification,
    geom_data = geom_reg,
    var_match = 'REGIONE'
    )


# %%

# check if points are within municipalities
print('Checking within municipalities...')
google_verification_mun_in, google_verification_mun_out, google_verification_mun_unverified = cened_utils.\
    check_borders(
    projected_data = google_verification_reg_in,
    geom_data = geom_mun,
    var_match = 'COMUNE'
    )


# %%
#----    Saving Geocoded Data    ----

print('Saving geocoded data...')
# Add include 'REGIONE' in 'INDIRIZZO_FULL' for all data
projected_mun_in['INDIRIZZO_FULL'] = projected_mun_in['INDIRIZZO_FULL'] + ', ' + projected_mun_in['REGIONE']

# %%
geocoded_data = pd.concat([projected_mun_in, bing_verification_mun_in, google_verification_mun_in])
geocoded_data = geocoded_data.drop('COMUNE_CATASTALE', axis = 1)

# For Shapefile column names max length is 10 characters
geocoded_data = geocoded_data.rename(columns = {
    'INDIRIZZO_FULL':'INDIRIZZO',
    'CONVERSION_PRECISION':'PRECISION'})

geocoded_data.to_csv(my_env.CENEDGEOCODED, index = False)
geocoded_data.to_file(my_env.CENEDGEOCODEDSHAPE, index = False)

print('Final geocoded data (excluding unverified buildings): {}'.format(len(geocoded_data)))


# %%
#----    Plot    ----

ax = geom_reg['geometry'].plot(figsize=(10,10))
geocoded_data.plot(ax=ax, color='red', markersize=1)
plt.show()


#===============================

