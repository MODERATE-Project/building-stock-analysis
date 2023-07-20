#!/usr/bin/env python
# coding: utf-8


# %%
#----    Settings    ----

import pandas as pd
from pathlib import Path
import os
from dotenv import load_dotenv
from dask import dataframe
import numpy as np

# load environment variables
from py_config_env import EnvironmentLoader

env_loader = EnvironmentLoader(
    env_file='my-env',       # File to load
    env_path='environments'  # Path where files are contained
)

# Object containing loaded environmental variables
my_env = env_loader.configuration.get('my_env')

# set pandas visualization options
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 200)
pd.set_option('display.max_colwidth', 400)

# %%
#----    Cened Data    ----

print('Loading data...')
# use dask to avoid problems due to the size of the dataset (~1gb)
cened_data = dataframe.read_csv(my_env.CENEDTABLE, dtype=str)

print('Filtering data...')
# filter 1
mask = cened_data['INTERO_EDIFICIO'] == 'true'
cened_data_buildings = cened_data[mask]

# filter 2
mask = cened_data_buildings['SUPERF_UTILE_RISCALDATA'].astype(np.float64) >= 100
cened_data = pd.DataFrame(
    cened_data_buildings[mask], 
    columns = cened_data_buildings.columns)

# further remove buildings without address, and without number 
# (Senza Numero Civico - snc, sn and variations)
cened_data = cened_data[~cened_data['INDIRIZZO'].isna()]
cened_data['INDIRIZZO'] = cened_data['INDIRIZZO'].str.lower()
cened_data = cened_data[~cened_data['INDIRIZZO'].str.contains('snc', regex=False)]
cened_data = cened_data[~cened_data['INDIRIZZO'].str.contains('s.n.c.', regex=False)]
cened_data = cened_data[~cened_data['INDIRIZZO'].str.contains('s.n', regex=False)]
cened_data = cened_data[~cened_data['INDIRIZZO'].str.contains('sn$', regex=True)]
cened_data = cened_data[~cened_data['INDIRIZZO'].str.contains('cm', regex=False)]
cened_data = cened_data[~cened_data['INDIRIZZO'].str.contains('c.m.', regex=False)]

# remove buildings without year of construction
cened_data = (cened_data[~cened_data['ANNO_COSTRUZIONE'].isna()])

print('Exporting data...')
# export data
cened_data.to_csv(my_env.CENEDOUTPUT, index=False)


# %%
