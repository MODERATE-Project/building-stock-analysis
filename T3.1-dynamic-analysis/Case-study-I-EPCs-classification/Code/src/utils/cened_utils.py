#!/usr/bin/env python
# coding: utf-8


#----    settings    ----

import pandas as pd
import numpy as np
from pathlib import Path
import os
from geopy.geocoders import Nominatim
from geopy.geocoders import Bing
from geopy.geocoders import GoogleV3
from geopy.extra.rate_limiter import RateLimiter
import geopandas as gpd
import datetime
import re
import time
import random

# Custom modules
from src.utils import my_utils

# my_env object containing environmental variables is passed in the analysis scripts

#----    geocode_data    ----

def geocode_data(
    data:pd.DataFrame,
    provider:str,
    output_dir:Path,
    cache_name:str,
    var_address:str = 'INDIRIZZO_FULL',
    ) -> None:
    """
    Given data as a dataframe, which should contain at least COD_APE and 
    the var specified by var_address, multiple requests are created to geocode 
    addresses to coordinates. Conversions are saved on disk in the 
    output_dir/cache_name directory. 
    
    Check which addresses have been converted to the building level (good data) 
    or not (bad data), and export data accordingly in output_dir.

    data: pd.DataFrame
        CENED dataframe containing the addresses to be converted in the 
        column defined by var_address, rows are identified by the COD_APE column
    provider:str
        name of the provider used to convert the addresses (should be one of 
        ['osm','bing','google'])
    output_dir:Path
        path of the directory where data files (good and bad) are exported
    cache_name:str
        name of the cache directory where data files of the API responses are exported
    var_address:str = 'INDIRIZZO_FULL'
        name of the column with the addresses to geolocalize
    
    Returns
    -------
    None
    """

    # API provider geocode
    if provider not in ['osm', 'bing', 'google']:
        raise ValueError('The provider "{}" is not supported'.format(provider))
    geocode = get_provider_geocode(provider = provider)

    # Folder used to store cached geocoded data from bulk API requests
    cache_dir = output_dir / cache_name

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    # API requests
    if provider == 'osm':
        n_req = 3600
    else:
        n_req = 5000 # both for bing and google

    filenames = request_conversion(
        data = data,
        start_index_global = 0,
        end_index_global = len(data), 
        n_req = n_req, 
        geocode = geocode, 
        provider = provider,
        cache_dir = cache_dir,  # api responses are saved in the cache subdir
        var_address = var_address
        )
    
    # Validate data
    check_conversions(
        provider = provider,
        filenames = filenames,
        cache_dir = cache_dir,
        output_dir = output_dir
        )


#----    get_provider_geocode    ----

def get_provider_geocode(provider:str) -> RateLimiter:
    """
    Given the provider, return the geocode with RateLimiter specific settings to 
    use in the request_conversion() function.
        
    Parameters
    ----------
    provider:str
        Indicate one among 'osm', 'bing', or 'google'. See the comments in the 
        code for the specific provider settings. 
        
    Returns
    -------
    RateLimiter
        Object to perform bulk operations while handling error responses and 
        adding delays when needed. API key are passed through environmental 
        variables in my_env object.
    """

    if provider == 'osm':        
        # osm geocoder (geocoding policy: https://operations.osmfoundation.org/policies/nominatim/)
        # - limit per second: 1, limit per day: no, limit per key: no
        # - key required: no
        # - notes: bulk requests should not be done on a regular basis, and only on small amounts of data
        geolocator = Nominatim(user_agent='moderate_conversion')
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    
    elif provider == 'bing':     
        # bing geocoder (https://www.microsoft.com/en-us/maps/licensing)
        # - limit per second: no, limit per day: 50.000, limit per key: 125.000
        # - key required: yes
        geolocator = Bing(api_key = my_env.BINGKEY)
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds = 1/10)

    elif provider == 'google':   
        # google geocoder (https://developers.google.com/maps/faq#usage_apis)
        # - limit per second: 50, limit per day: no, limit per key: 200USD free per month (1k requests = 5USD)
        # - key required: yes
        geolocator = GoogleV3(api_key = my_env.GOOGLEKEY)
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds = 1/25)
    
    else:
        raise ValueError('The provider "{}" is not supported'.format(provider))
    
    return geocode


#----    request_conversion    ----

def request_conversion(
    data:pd.DataFrame, 
    start_index_global:int, 
    end_index_global:int,
    n_req:int, 
    geocode:RateLimiter, 
    provider:str,
    cache_dir:Path,
    var_address:str = 'INDIRIZZO_FULL') -> list:
    """
    Given data as a dataframe, which should contain at least COD_APE and 
    the var specified by var_address, its rows from start_index_global to 
    end_index_global are split in multiple requests in order to geocode addresses 
    to coordinates. Conversions are saved on disk each n_req requests, and 
    temporarly spread according to the min_delay_seconds parameter set in geocode.
        
    Parameters
    ----------
    data: pd.DataFrame
        CENED dataframe containing the addresses to be converted in the 
        column defined by var_address, rows are identified by the COD_APE column
    start_index_global: int
        row index at which to start the conversion of the addresses in the dataframe
    end_index_global: int
        row index at which to end the conversion of the addresses in the dataframe
    n_req: int
        number of conversion requests to send at each call of the geocoding service
    provider:str
        name of the provider used to convert the addresses (should be one of 
        ['osm','bing','google'])
    cache_dir:Path
        path of the directory where data files of the API responses are exported
    var_address:str = 'INDIRIZZO_FULL'
        name of the column with the addresses to geolocalize
        
    Returns
    -------
    list
        filenames of obtained data
    
    """
    
    if provider not in ['osm', 'bing', 'google']:
        raise ValueError('The provider "{}" is not supported'.format(provider))
    
    bing_limit = 50000 # Bing requests limit per day: 50'000

    # store filenames bulk data
    filenames = []

    for start_index in np.arange(start_index_global, end_index_global, n_req):
        end_index = min([start_index + n_req, end_index_global]) # min to avoid out of range values
        columns_content = zip(data['COD_APE'].iloc[start_index:end_index], 
                              data[var_address].iloc[start_index:end_index])
        request_addresses = pd.DataFrame(columns_content, columns=['COD_APE', var_address])
        print('Conversion ', start_index, ' - ', end_index - 1, 
              ' started at ', datetime.datetime.now())
        
        # Bing if above day limit, wait 1 day
        if (provider == 'bing') & (end_index >= bing_limit):
            print('Bing  limit request per day day: 50\'000\n', datetime.datetime.now())
            bing_limit = bing_limit + 50000 # increase to detect next limit
            time.sleep(86400)   # wait 1 day for next round of conversions

        # request conversions and process the reply (https://geopy.readthedocs.io/en/stable/#geopy.point.Point)
        reply = request_addresses[var_address].progress_apply(geocode)
        request_addresses['LAT'] = reply.apply(lambda loc: tuple(loc.point)[0] if loc else None)
        request_addresses['LONG'] = reply.apply(lambda loc: tuple(loc.point)[1] if loc else None)
        
        # check the geocoding precision
        if provider == 'osm':        
            # the first element of an OSM conversion is a number only if the geocoding is precise
            request_addresses['CONVERSION_PRECISION'] = reply.apply(
                lambda loc: loc.address.split(',')[0] if loc else None)
        elif provider == 'bing':
            # https://docs.microsoft.com/en-us/bingmaps/rest-services/locations/location-data
            request_addresses['CONVERSION_PRECISION'] = reply.apply(
                lambda loc: loc.raw['geocodePoints'][0]['calculationMethod'] if loc else None)
        elif provider == 'google':   
            # https://developers.google.com/maps/documentation/geocoding/requests-geocoding#results 
            request_addresses['CONVERSION_PRECISION'] = reply.apply(
                lambda loc: loc.raw['geometry']['location_type'] if loc else None)
        
        # save conversions on disk
        filename =  Path('data_converted_' + str(start_index) + '-' + str(end_index - 1) + '.csv')
        request_addresses.to_csv(cache_dir / filename, index=False, encoding='utf-8')
        filenames.append(filename)
    
    return filenames

#----    check_conversions    ----

def check_conversions(
    provider:str,
    filenames:list, 
    cache_dir:Path, 
    output_dir:Path) -> None:
    """
    Read all files contained in cache_dir, find out which addresses have been 
    converted to the building level (good data) or not (bad data), and export 
    data accordingly in output_dir.
        
    Parameters
    ----------
    provider:str
        name of the provider used to convert the addresses (should be one of 
        ['osm','bing','google'])
    filenames:list
        filenames of obtained data from API requests
    cache_dir:Path
        path of the directory containing the conversions received from a provider
    output_dir:Path
        path of the directory where data files (good and bad) are exported
    
    Returns
    -------
    None
    """
    
    if provider not in ['osm', 'bing', 'google']:
        raise ValueError('The provider "{}" is not supported'.format(provider))
    
    good_data = pd.DataFrame()  # addresses converted to the building level
    bad_data = pd.DataFrame()   # not found or converted to street level

    for file in filenames:
                
        converted_data = pd.read_csv(cache_dir / Path(file))
        
        # filter out cases where the address has not been located
        filter_mask = converted_data['CONVERSION_PRECISION'].isna()
        noaddress_data = converted_data[filter_mask].reset_index(drop=True)
        converted_data = converted_data[~filter_mask].reset_index(drop=True)   
        
        # filter out cases where the geocoding is not precise
        if provider == 'osm':
            converted_data['CONVERSION_PRECISION'] = converted_data['CONVERSION_PRECISION']\
                .apply(lambda loc: re.sub('\D', '', loc))
            filter_mask = converted_data['CONVERSION_PRECISION'].str.isdigit()
        elif provider == 'bing':
            filter_mask = converted_data['CONVERSION_PRECISION'].str.lower() == 'rooftop'
        elif provider == 'google':   
            filter_mask = converted_data['CONVERSION_PRECISION'].str.lower() == 'rooftop'

        unprecise_data = converted_data[~filter_mask]
        converted_data = converted_data[filter_mask]
                
        good_data = pd.concat([good_data, converted_data])
        bad_data = pd.concat([bad_data, noaddress_data, unprecise_data])       
        
    # export good and bad data
    # To avoid overwriting, use as file name the name of the cache directory
    id_name = os.path.basename(cache_dir) 
    good_data.to_csv(output_dir / Path(id_name + '_' + my_env.CENEDGOOD), index=False)
    bad_data.to_csv(output_dir / Path(id_name + '_' + my_env.CENEDBAD), index=False)
    print('{} - {} good data rows and {} bad data rows exported on disk ({})'\
        .format(id_name, len(good_data), len(bad_data), len(good_data) + len(bad_data))) 


#----    get_projected_data    ----

def get_projected_data(
    geocoded_data: pd.DataFrame, 
    data_ref: pd.DataFrame,
    crs:str = 'EPSG:4326') -> gpd.GeoDataFrame:
    """
    Given a dataframe with LONG and LAT columns indicating the geographical 
    coordinates, return a gpd.GeoDataFrame with geometry point. crs (default to
    'EPSG:4326') is used as geocoding reference. Moreover, further geographical 
    info (columns: 'REGIONE', 'COMUNE_CATASTALE', and 'COMUNE') are added from 
    data_ref. These can be used in the analysis to check projection fall within 
    the right region and municipality.
    
    Parameters
    ----------
    geocoded_data: pd.DataFrame,
        dataframe with LONG and LAT columns indicating the geographical 
        coordinates and COD_APE column to identify single rows
    data_ref: pd.DataFrame
        dataframe with geographical info (columns: 'REGIONE', 'COMUNE_CATASTALE', 
        and 'COMUNE') to be added according to COD_APE column.
    crs: str
        indicates the geocoding reference. Default to 'EPSG:4326'.
    
    Returns
    -------
    gpd.GeoDataFrame
        geocoded dataframe with further geographical info
    """
    res = gpd.GeoDataFrame(
        geocoded_data, 
        geometry=gpd.points_from_xy(geocoded_data.LONG, geocoded_data.LAT, crs=crs))

    # add region and municipality information used for matching with geom data
    colum_geo_info = ['REGIONE', 'COMUNE_CATASTALE', 'COMUNE']
    data_to_join = data_ref[['COD_APE'] + colum_geo_info]\
        .astype({'COD_APE': int}, errors='raise') 
    res = res.join(
        data_to_join.set_index('COD_APE'),
        on = 'COD_APE', how = 'left'
        )
    
    return res

#----    check_borders    ----

def check_borders(
    projected_data:gpd.GeoDataFrame, 
    geom_data:gpd.GeoDataFrame,
    var_match:str) -> tuple([gpd.GeoDataFrame,gpd.GeoDataFrame,gpd.GeoDataFrame]):
    """
    Check if the geocoding coordinates of the addresses in projected_data_in are 
    within the borders of the respective geom_border whose coordinates are found 
    in geom_border.
        
    Parameters
    ----------
    projected_data: gpd.GeoDataFrame
        A GeoDataFrame containing the geocoding coordinates of the addresses 
        in EPSG:4326 format, and the lowercase name of the corresponding geom 
        in a column specified by var_match.
    geom_data: gpd.GeoDataFrame
        A GeoDataFrame containing the geocoding coordinates of the geom to 
        look in, whose lowercase names is within a column specified by var_match.
    var_match: str
        A string indicating the name of the colum available in projected_data_in
        and geom_data dataframes containing the geoms name used for matching.
            
    Returns
    -------
    tuple(gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame)
        A tuple containing three geodataframes:
        - the buildings within the borders of the corresponding city
        - the buildings out of the borders of the corresponding city
        - the buildings within an unverifiable city
    """
    
    # Remove all non alphanumeric characters (including spaces) to improve matching
    projected_data['TO_MATCH'] = projected_data[var_match]\
        .map(my_utils.to_plain_str)
    geom_data['TO_MATCH'] = geom_data[var_match]\
        .map(my_utils.to_plain_str)
    
    if var_match == 'COMUNE':
        # Fix municipality due to changed or new names (new aggregations)
        projected_data.replace({'TO_MATCH':dic_municipalities}, inplace=True)

    geom_names = set(projected_data['TO_MATCH'])
    buildings_in_full = gpd.GeoDataFrame()
    buildings_out_full = gpd.GeoDataFrame()
    buildings_unverified = gpd.GeoDataFrame()    

    # for each unique geom
    for geom_name in geom_names:
        
        # extract buildings of the geom
        mask = projected_data['TO_MATCH'] == geom_name
        buildings = projected_data[mask]
        
        # find the borders of the geom
        mask = geom_data['TO_MATCH'] == geom_name
        borders = geom_data[mask]
        
        # if the geom is in the shapefile, check if the geocoding of buildings is within the geom's borders
        if len(borders) == 1:
            borders = borders.iloc[0,:]
            mask = buildings.within(borders.geometry)
            buildings_in = buildings[mask]
            buildings_in_full = pd.concat([buildings_in_full, buildings_in])
            buildings_out = buildings[~mask]
            if(len(buildings_out) > 0):
                buildings_out_full = pd.concat([buildings_out_full, buildings_out])
                
        # otherwise, the geocoding cannot be verified
        else:
            buildings_unverified = pd.concat([buildings_unverified, buildings])

    print(len(buildings_in_full), 'buildings within borders of the geom')
    print(len(buildings_out_full), 'buildings out of borders of the geom')
    print(len(buildings_unverified), 'buildings within an unverifiable geom')
    
    buildings_in_full = buildings_in_full.drop('TO_MATCH', axis=1, errors = 'ignore') 
    buildings_out_full = buildings_out_full.drop('TO_MATCH', axis=1, errors = 'ignore')
    buildings_unverified = buildings_unverified.drop('TO_MATCH', axis=1, errors = 'ignore')

    return (buildings_in_full, buildings_out_full, buildings_unverified)


#----    categorize_year    ----

def categorize_year(year):
    """
    Categorize year of construction according to https://gitlab.com/hotmaps/building-stock:
    - before 1945 (historic buildings - highly inhomogeneous)
    - [1945,1969] (generally characterized by nearly missing insulation and inefficient energy systems)
    - [1970,1979] (presence of first insulation applications)
    - [1980,1989] (before the introduction of the first national thermal efficiency ordinances)
    - [1990,1999] (after the introduction of the first national thermal efficiency ordinances)
    - [2000,2010] (impacted by the EU Energy Performance of Buildings Directive)
    - after 2010  (recently constructed buildings)
    If a range in the original data is spread across multiple categories, buildings are probabilistically split according to the 
    timeframe intersection of original categories with aforementioned categories.
    """
    
    # conditions appear in frequency order
    if year == '1961-1976':     # 16y: 1961-1969 (9y 0.57)->[1945,1969], 1970-1976 (7y 0.43)->[1970,1979]
        if random.random() <= 0.57:
            return '1945-1969' 
        else:
            return '1970-1979'
    elif year == '1977-1992':   # 16y: 1977-1979 (3y 0.19)->[1970,1979], 1980-1989 (10y 0.62)->[1980,1989], 1990-1992 (3y 0.19)->[1990,1999]
        if random.random() <= 0.62:
            return '1980-1989'
        elif random.random() <= 0.50:
            return '1970-1979'
        else: 
            return '1990-1999'
    elif year == '1993-2006':   # 14y: 1993-1999 (7y 0.5)->[1990,1999], 2000-2006 (7y 0.5)->[2000,2010]
        if random.random() <= 0.50:
            return '1990-1999' 
        else:
            return '2000-2010'
    elif year == '1946-1960':
        return '1945-1969'
    elif year == 'Prima del 1930':
        return 'before 1945'
    elif year == '1930-1945':   # 16y: 1930-1944 (15y 0.94)->before 1945, 1945 (1y 0.06)->[1945,1969]
        if random.random() <= 0.94:
            return 'before 1945' 
        else:
            return '1945-1969'
    elif year == 'Dopo il 2006':
        return '2000-2010'
    else:
        try:
            year = int(year)
            if year < 1945:
                return 'before 1945'
            elif year >= 1945 and year <= 1969:
                return '1945-1969'
            elif year >= 1970 and year <= 1979:
                return '1970-1979'
            elif year >= 1980 and year <= 1989:
                return '1980-1989'
            elif year >= 1990 and year <= 1999:
                return '1990-1999'
            elif year >= 2000 and year <= 2010:
                return '2000-2010'
            else:
                return 'after 2010'
        except ValueError:
            print('{} is not a valid year'.format(year))
            return year


#----    merge_energyclass    ----

def merge_energyclass(energyclass):
    """
    Merge the A energy subclasses of a building into a single A class.
    """
    
    if energyclass in ['A1', 'A2', 'A3', 'A4']:
        return 'A'
    else:
        return energyclass


#---    dic_municipalities    ----

dic_municipalities = {
    'bigarello':'sangiorgiobigarello',
    'borgofrancosulpo':'borgocarbonara',
    'cadandrea':'torredepicenardi',
    'cadrezzate':'cadrezzateconosmate',
    'cagno':'solbiateconcagno',

    'camairago':'castelgerundo',
    'canevino':'colliverdi',
    'carbonaradipo':'borgocarbonara',
    'casascodintelvi':'centrovalleintelvi',
    'castiglionedintelvi':'centrovalleintelvi',

    'cavacurta':'castelgerundo',
    'cavallasca':'sanfermodellabattaglia',
    'ceranointelvi':'ceranodintelvi',
    'drizzona':'piadenadrizzona',
    'felonica':'sermideefelonica',

    'godiasco':'godiascosaliceterme',
    'introzzo':'valvarrone',
    'lanzodintelvi':'altavalleintelvi',
    'osmate':'cadrezzateconosmate',
    'pelliointelvi':'altavalleintelvi',

    'piadena':'piadenadrizzona',
    'pievedicoriano':'borgomantovano',
    'prestine':'bienno',
    'puegnagosulgarda':'puegnagodelgarda',
    'ramponiovernia':'altavalleintelvi',
    'revere':'borgomantovano',

    'rivanazzano':'rivanazzanoterme',
    'ruino':'colliverdi',
    'sanfedeleintelvi':'centrovalleintelvi',
    'solbiate':'solbiateconcagno',
    'tremenico':'valvarrone',

    'tremosine':'tremosinesulgarda',
    'valverde':'colliverdi',
    'vendrogno':'bellano',
    'vermezzo':'vermezzoconzelo',
    'vestreno':'valvarrone',

    'villapoma':'borgomantovano',
    'zelosurrigone':'vermezzoconzelo'
}


#----
