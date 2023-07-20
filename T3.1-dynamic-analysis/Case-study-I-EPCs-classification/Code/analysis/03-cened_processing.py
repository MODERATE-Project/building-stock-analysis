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
import geopandas as gpd
from tqdm import tqdm
import random
import matplotlib.pyplot as plt

# Custom modules
import importlib
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

print('Data loading...')

# Read filtered cened data
cened_data = pd.read_csv(my_env.CENEDOUTPUT, dtype = 'str')
cened_data = cened_data.astype({'COD_APE':'int'})
cened_data = cened_data.drop(['COMUNE', 'REGIONE', 'INDIRIZZO'], axis = 1)

# Read geocoded data
geocoded_data = gpd.read_file(my_env.CENEDGEOCODEDSHAPE)
geocoded_data = geocoded_data.astype({'COD_APE':'int'})


# %%
#----    Data Processing    ----

print('Data processing...')

# Create unique dataframe, 'COD_APE' indicates the unique buildings
cened_data = geocoded_data.join(
    cened_data.set_index('COD_APE'), 
    on = 'COD_APE', 
    how = 'left'
    )


# %%

# select from original data the features which could be useful for modeling and interpretation
list_features = [
    'COD_APE',
    'DATA_INS',
    'INDIRIZZO',
    'COMUNE',
    'LAT',
    'LONG',
    'geometry',
    'RESIDENZIALE', 
    'CLASSIFICAZIONE_DPR',
    'NUOVA_COSTRUZIONE', 
    'RISTRUTTURAZIONE_IMPORTANTE', 
    'RIQUALIFICAZIONE_ENERGETICA',  
    'SUPERF_UTILE_RISCALDATA', 
    'SUPERF_UTILE_RAFFRESCATA', 
    'SUPERFICIE_DISPERDENTE', 
    'VOLUME_LORDO_RISCALDATO', 
    'VOLUME_LORDO_RAFFRESCATO', 
    'EP_GL_NREN', 
    'EP_GL_REN', 
    'CONSUMI_ENERGIA_ELETTRICA',
    'ANNO_COSTRUZIONE',
    'CLASSE_ENERGETICA' 
]

cened_reduced = cened_data[list_features]


# %%

# Remove buildings which could decrease correlation between year and APE
# buildings which were subject to important rebuilding
mask_1 =  cened_reduced['RISTRUTTURAZIONE_IMPORTANTE']=='false'
# buildings which were subject to energy performance requalification
mask_2 =  cened_reduced['RIQUALIFICAZIONE_ENERGETICA']=='false'

cened_reduced = cened_reduced[mask_1 & mask_2]

cened_reduced = cened_reduced.drop(
    ['RISTRUTTURAZIONE_IMPORTANTE', 'RIQUALIFICAZIONE_ENERGETICA'], 
    axis=1)


# %%
#----    Create Categories    ----

print('Creating categories...')

# transform year of construction into categories
random.seed(5)
cened_reduced['ANNO_COSTRUZIONE'] = cened_reduced['ANNO_COSTRUZIONE']\
    .apply(cened_utils.categorize_year)
print(cened_reduced['ANNO_COSTRUZIONE'].value_counts())

# merge energy classes
cened_reduced['CLASSE_ENERGETICA'] = cened_reduced['CLASSE_ENERGETICA']\
    .apply(cened_utils.merge_energyclass)
print(cened_reduced['CLASSE_ENERGETICA'].value_counts())


# %%
#----    Saving Data    ----

print('Saving data...')

# For Shapefile column names max length is 10 characters
cened_reduced = cened_reduced.rename(columns = {
    'RESIDENZIALE':'RESIDENT', 
    'CLASSIFICAZIONE_DPR':'DPR_CLASS', 
    'NUOVA_COSTRUZIONE':'NEW_BUILD',
    'SUPERF_UTILE_RISCALDATA':'HEAT_AREA', 
    'SUPERF_UTILE_RAFFRESCATA':'COOL_AREA',
    'SUPERFICIE_DISPERDENTE':'DISP_AREA',
    'VOLUME_LORDO_RISCALDATO':'HEAT_VOLUM',
    'VOLUME_LORDO_RAFFRESCATO':'COOL_VOLUM',
    'EP_GL_NREN':'EPGL_NREN',
    'EP_GL_REN':'EPGL_REN',
    'CONSUMI_ENERGIA_ELETTRICA':'ELETRIC_CO',
    'ANNO_COSTRUZIONE':'YEAR_BUILD',
    'CLASSE_ENERGETICA':'ENER_CLASS'})

# %%

cened_reduced.to_csv(my_env.CENEDPROCESSED, index=False)
cened_reduced.to_file(my_env.CENEDPROCESSEDSHAPE, index=False)

print('Final processed data: {}'.format(len(cened_reduced)))


# %%
#----    Plot    ----

print('Plotting...')

# Get Lombardy region geometry data
geom_reg = gpd.read_file(my_env.GEOREGION, encoding='utf-8')  # source: https://www.istat.it/it/archivio/222527
geom_reg = geom_reg.to_crs(cened_reduced.crs)

mask = geom_reg['DEN_REG']=='Lombardia'
geom_reg = geom_reg[mask]

# Plot
ax = geom_reg['geometry'].plot(figsize=(10,10))
cened_reduced.plot(ax=ax, color='red', markersize=1)
plt.show()


#=============
# %%
