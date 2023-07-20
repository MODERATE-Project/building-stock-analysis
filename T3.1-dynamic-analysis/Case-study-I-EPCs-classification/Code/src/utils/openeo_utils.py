#!/usr/bin/env python
# coding: utf-8


#----    settings    ----
from pathlib import Path
import os
from matplotlib.pyplot import axis
import openeo
from pyproj import Geod
import shapely as shp
import pandas as pd
import geopandas as gpd
import math
import numpy as np
import time
import matplotlib.pyplot as plt
import re
import json
import rasterio
from rasterio.plot import show
import rasterstats
import pygrib
import timeit



# Custom modules
from src.utils import my_utils

# my_env object containing environmental variables is passed in the analysis scripts

#----    get_lombardy_geom    ----

def get_lombardy_geom(
    path:Path,
    crs
    ) -> gpd.GeoDataFrame:
    """
    Load the Lombardy region geometry.

    Parameters
    ----------
    path:Path
        Path to the shapefile of Italian regions
    crs:
        The Coordinate Reference System (CRS) represented as a pyproj.CRS object

    Returns
    -------
    gpd.GeoDataFrame
        returns id_name ('Lombardia') and geometry
    """
    # Read lombardy data (source: https://www.istat.it/it/archivio/222527)
    res = gpd.read_file(path, encoding='utf-8')
    res = res.to_crs(crs)

    mask = res['DEN_REG']=='Lombardia'

    res = res[mask][['DEN_REG', 'geometry']]
    res = res.reset_index(drop=True)
    res = res.rename(columns = {'DEN_REG':'id_name'})

    return res

#----    get_S2_tails    ----

def get_S2_tails(
    path_file:Path, 
    crs) -> gpd.GeoDataFrame:
    """
    Get the Sentinel 2 tails covering the Lombardy region.
    
    Parameters
    ----------
    path_file:Path
        Path too the geojson file with all S2 tiles data
    crs:
        The Coordinate Reference System (CRS) represented as a pyproj.CRS object

    Returns
    -------
    gpd.GeoDataFrame
        For each Sentinel 2 tail covering the Lombardy region, returns id_name 
        and geometry
    """
    S2_tails= gpd.read_file(path_file)

    # Tails covering Lombardy
    lombardy_tails = [
        '32TMS', '32TNS', '32TPS',
        '32TMR', '32TNR', '32TPR',
        '32TMQ', '32TNQ', '32TPQ'
        ]
    mask = [tail in lombardy_tails for tail in S2_tails['Name']]
    S2_tails = S2_tails[mask]
    S2_tails = S2_tails.to_crs(crs)
    
    S2_tails = S2_tails.rename(columns = {
        'Name':'id_name'
        })
    
    S2_tails = S2_tails.reset_index(drop=True)
    
    return S2_tails

#----    plot_tails_grid    ----

def plot_tails_grid(
    region:gpd.GeoDataFrame,
    tails:gpd.GeoDataFrame,
    building_data:gpd.GeoDataFrame = None,
    ) -> None:
    """
    Plot the tail grid on the the region map.

    Parameters
    ----------
    region:gpd.GeoDataFrame
        Dataframe with the following columns:
        - id_name: name of the region
        - geometry: shape of the region
    tails:gpd.GeoDataFrame
        Dataframe with the following columns:
        - id_name: name of the tail
        - geometry: shape of the tail
    building_data:gpd.GeoDataFrame
        GeoDataFrame with the buildings point coordinates (geometry POINT)
    
    Returns
    -------
    None
    """
    centroids = tails.centroid

    # Plot
    ax = region.plot(figsize=(10,10))

    # Buildings
    if building_data is not None:
        building_data.plot(ax=ax, color='red', markersize=.5)
    
    # Tails
    tails.plot(ax=ax, color = 'black', edgecolor='red', alpha = .3)
    for x, y, label in zip(centroids.geometry.x, centroids.geometry.y, tails.id_name):
        ax.annotate(label, xy=(x, y), ha = 'center', va = 'bottom')
    plt.show()

#----    get_corners    ----

def get_corners(bounds:pd.DataFrame) -> dict: 
    """
    Given the bounds of a geometry, get the corners coordinates.

    Parameters
    ----------
    bounds:pd.DataFrame
        DataFrame with values for minx, miny, maxx, maxy values containing the 
        bounds of the geometry.
    
    Returns
    -------
    dict
        Return a DataFrame with new columns with the coordinates (long, lat) for 
        each corner (bottom_west, bottom_east, top_east, top_west)
    """
    res = pd.DataFrame({
        'bottom_west':[(x, y) for x, y in zip(bounds['minx'], bounds['miny'])],
        'bottom_east':[(x, y) for x, y in zip(bounds['maxx'], bounds['miny'])],
        'top_est':[(x, y) for x, y in zip(bounds['maxx'], bounds['maxy'])],
        'top_west':[(x, y) for x, y in zip(bounds['minx'], bounds['maxy'])]
        })

    return res

#----    get_polygon    ----

def get_polygon(bounds:pd.DataFrame):
    """
    Given the bounds of a geometry, return the respective polygon.

    Parameters
    ----------
    bounds:pd.DataFrame
        DataFrame with columns minx, miny, maxx, maxy values containing the 
        bounds of the geometry.
    
    Returns
    -------
    geometry
    """
    corners = get_corners(bounds)
    
    res = corners.apply(lambda x: shp.geometry.Polygon(
        [list(coord) for coord in [
            x['bottom_west'],
            x['bottom_east'],
            x['top_est'],
            x['top_west'],
            x['bottom_west']]
        ]), axis = 1)
    
    return res

#----    project_point    ----

def project_point(
    point:tuple([float,float]), 
    direction:str, 
    meters:int) -> tuple([float,float]):
    """
    Project a point into a cardinal direction by a certain number of meters.
    
    Parameters
    ----------
    point:tuple(float,float)
        Coordinates of the point to project as (longitude x, latitude y), in 
        degrees - tested in epsg:4326 reference system
    direction:str
        Cardinal direction to project data (should be one of 
        ['east','west','north','south'])
    meters:int
        Number of meters to project data towards a direction
    
    Returns
    -------
    tuple(float,float)
        Coordinates of the projected point as (longitude x, latitude y), in 
        degrees - tested in epsg:4326 reference system
    """ 
    
    # To project, pick the coordinates of a point on Earth, then compute 
    # an approximation of azimuth points towards each cardinal point to find 
    # the direction of projection
    
    if direction == 'east':
        azimuth_point = (point[0] + 0.5, point[1])
    
    elif direction == 'west':
        azimuth_point = (point[0] - 0.5, point[1])
    
    elif direction == 'north':
        azimuth_point = (point[0], point[1] + 0.5)
    
    elif direction == 'south':
        azimuth_point = (point[0], point[1] - 0.5)

    
    
    else:
        raise ValueError('Supported directions are "east", "west", "north", "south"')
    
    geod = Geod(ellps='WGS84')

    az12, _, _ = geod.inv(point[0], point[1], azimuth_point[0], azimuth_point[1])
    new_long, new_lat, _ = geod.fwd(point[0], point[1], az12, meters)
    
    return (new_long, new_lat)

#----    get_tails    ----

def get_tails(
    data_geom:gpd.GeoDataFrame,
    tail_side_km:int,
    overlapping_km:float,
    crs) -> gpd.GeoDataFrame:
    """
    Given a GeoDataframe with different geometries, define a grid of tails for 
    each geoometry. Tails are defined according to the specified tail side 
    (in km). Returns a GeoDataFrame with the following information for each tail: 
    id of the parent geometry, tail id name, geometry. Tail id names are defined 
    according to their position in the grid (row, column), starting from the top 
    east corner. Note that resulting tail matrix are cropped within the 
    respective parent geometry.

    Parameters
    ----------
    data_geom:pd.DataFrame
        DataFrame with columns 
    tail_side_km:int
        Value indicating the tails side in km.
    overlapping_km:int
        Value indicating the tails overlapping in km.
    crs:
        The Coordinate Reference System (CRS) represented as a pyproj.CRS object
    
    Returns
    -------
    gpd.GeoDataFrame:
        Dataframe with the following columns:
        - id_parent: naem of the parent geometry
        - id_name: tuple indicating the tail position in the grid (row, column), 
          starting from the top east corner.
        - geometry: polygon indicating the shape
    """

    # Get the geom corners
    geom_corners = get_corners(data_geom.bounds)

    res = gpd.GeoDataFrame()

    for i in np.arange(0, len(data_geom)):
        corners = geom_corners.iloc[i]
        geom = data_geom.iloc[i]

        # Considering the bottom west corner as reference,
        # compute vertical and horizontal distances (used for defining number of tails). 
        # Azimuths angles moving east and north are later used for finding tails projections
        geod = Geod(ellps='WGS84')
        azimuth_east, _, distance_west_east = geod.inv(
            corners['bottom_west'][0], corners['bottom_west'][1], 
            corners['bottom_east'][0],  corners['bottom_east'][1]
            )

        azimuth_north, _, distance_south_north = geod.inv(
            corners['bottom_west'][0], corners['bottom_west'][1], 
            corners['top_west'][0], corners['top_west'][1]
            )

        distance_west_east_km = distance_west_east / 1000
        distance_south_north_km = distance_south_north / 1000

        # Print info
        print('\n\nRegion: {}\n'.format(geom['id_name']))
        print('Distance east-west: {:.2f} km'.format(distance_west_east_km))
        print('From ({0[0]:.2f},  {0[1]:.2f}) to ({1[0]:.2f},  {1[1]:.2f})\n'\
            .format(corners['bottom_west'], corners['bottom_east'])) 

        print('Distance north-south: {:.2f} km'.format(distance_south_north_km))
        print('From ({0[0]:.2f},  {0[1]:.2f}) to ({1[0]:.2f},  {1[1]:.2f})\n'\
            .format(corners['bottom_west'], corners['top_west'])) 

        # According to tile size define the size of the grid to download (m x n)
        tail_side_m = tail_side_km * 1000
        overlapping_m = int(overlapping_km * 1000)
        vertical_tails = math.ceil(distance_south_north_km / tail_side_km)
        horizontal_tails = math.ceil(distance_west_east_km / tail_side_km)
        print('Tails matrix to download:', vertical_tails, 'x', horizontal_tails)

        # id-tails according to their position in the grid 
        tails = get_tails_bounds(
            bottom_west = corners['bottom_west'],
            tail_grid = (vertical_tails, horizontal_tails),
            tail_side_m = tail_side_m,
            overlapping_m = overlapping_m,
            azimuth_north = azimuth_north,
            azimuth_east = azimuth_east
        )

        # Add geometry and parent id name
        tails = gpd.GeoDataFrame(
            {
                'id_parent':geom['id_name'],
                'id_name':tails['id_name']
            },
            geometry = get_polygon(tails),
            crs = crs)

        # Crop tails to parent geometry
        tails['geometry'] = tails['geometry'].intersection(geom['geometry'])

        res = pd.concat([res, tails])

    res = res.reset_index(drop=True)

    return res

#----    filter_tails    ----

def filter_tails(
    tails:gpd.GeoDataFrame,
    intersection_with:gpd.GeoDataFrame = gpd.GeoDataFrame(),
    include_elements:gpd.GeoDataFrame = gpd.GeoDataFrame()
    ) -> gpd.GeoDataFrame:
    """
    Filter tails that have no empty intersection with 'intersection_with' and 
    include at least one element of 'include_elements'

    Parameters
    ----------
    tails:gpd.GeoDataFrame
        GeoDataFrame with 'geometry' of each tail
    intersection_with:gpd.GeoDataFrame
        GeoDataFrame with 'geometry' of the element to check intersection is not 
        empty. Note that union of geometries is used
    include_elements:gpd.GeoDataFrame
        GeoDataFrame with 'geometry' of the elements that should be included in 
        the tails. Each tail should include at leas one one element
    
    Returns
    -------
    gpd.GeoDataFrame
        with the filtered tails
    """

    # Keep tails that have intersection with 
    if len(intersection_with) > 0:
        geom_union = shp.ops.unary_union(intersection_with['geometry'])
        mask = ~ tails['geometry'].intersection(geom_union).is_empty
        tails = tails[mask]

    # Keep only tails that include at leas one element
    if len(include_elements) > 0:
        mask = tails['geometry'].apply(lambda x:\
            len(include_elements['geometry'].sindex.query(x)) > 0 )
        tails = tails[mask]
        tails = tails.reset_index(drop=True)
    
    tails = tails.reset_index(drop=True)
    
    return tails
    

#----    get_tails_bounds    ----

def get_tails_bounds(
    bottom_west:tuple([float, float]),
    tail_grid:tuple([int, int]),
    tail_side_m:int,
    overlapping_m:int,
    azimuth_north:float,
    azimuth_east:float) -> pd.DataFrame:
    """
    Given the bottom west corner, tail grid size (rows, columns), and the size 
    of each tail, compute the borders. The bottom west corner is used as 
    starting point and the horizontal and vertical grid are defined according to 
    the azimuth angle (east and north, respectively). Note that different 
    starting and ending points are defined to allow overlapping between tails. 
    Obtained coordinates are then combined to define all the required points.
    
    Returns a DataFrame with the following information for each tail: id tail 
    and borders (max and min latitude and longitude). Tail id is defined 
    according to its position in the grid (row, column), starting from the top 
    east corner.

    Parameters
    ----------
    bottom_west:tuple([float, float])
        Coordinates (long, lat) of the bottom west corner
    tail_grid:tuple([int, int])
        (rows, columns) indicating the dimension of the tail grid
    tail_side_m:int
        Length (in meter) of the tails. Note that this is used to define the 
        space between tails at the bottom. At the top the space obtained by 
        projecting the coordinates at north
    overlapping_m:int
        Value indicating the tails overlapping in m.
    azimuth_north:float
        Forward azimuth angle moving north from the bottom west corner
    azimuth_east:float
        Forward azimuth angle moving east from the bottom west corner
    
    Returns
    -------
    pd.DataFrame:
        Dataframe with the following columns:
        - id_name: tuple indicating the tail position in the grid (row, column), 
          starting from the top east corner.
        - maxy: float indicating the north latitude
        - miny: float indicating the south latitude
        - maxx: float indicating the east longitude
        - minx: float indicating the west longitude
    """
    geod = Geod(ellps='WGS84')
    
    # Get horizontal grid borders
    horizontal_grid_borders_start = []
    horizontal_grid_borders_end = []
    for i in np.arange(tail_grid[1] + 1):  # +1 to get also final border
        # Start
        long_start, lat_start, _ = geod.fwd(
            bottom_west[0], bottom_west[1], 
            azimuth_east, i * tail_side_m - overlapping_m
            )
        horizontal_grid_borders_start.append((long_start, lat_start))

        # End
        long_end, lat_end, _ = geod.fwd(
            bottom_west[0], bottom_west[1], 
            azimuth_east, i * tail_side_m + overlapping_m
            )
        horizontal_grid_borders_end.append((long_end, lat_end))

    # Get vertical grid borders
    vertical_grid_borders_start = []
    vertical_grid_borders_end = []
    for i in np.arange(tail_grid[0] + 1):  # +1 to get also final border
        # Start
        long_start, lat_start, _ = geod.fwd(
            bottom_west[0], bottom_west[1], 
            azimuth_north, i * tail_side_m - overlapping_m
            )
        vertical_grid_borders_start.append((long_start, lat_start))

        # End
        long_end, lat_end, _ = geod.fwd(
            bottom_west[0], bottom_west[1], 
            azimuth_north, i * tail_side_m + overlapping_m
            )
        vertical_grid_borders_end.append((long_end, lat_end)) 
    
    # Reverse element to allow referring tails grid from the top left corner (top east)
    vertical_grid_borders_start.reverse()
    vertical_grid_borders_end.reverse()

    # Tails id name defined according to their position in the grid (row x column) 
    # starting from the top east corner
    id_name = [(x, y) for x in np.arange(tail_grid[0]) for y in np.arange(tail_grid[1])]

    # Define borders of each tail
    tails = pd.DataFrame()

    for row, column in id_name:

        # borders
        maxy = vertical_grid_borders_end[row][1]
        miny = vertical_grid_borders_start[row + 1][1]
        minx = horizontal_grid_borders_start[column][0]
        maxx = horizontal_grid_borders_end[column + 1][0]

        new_row = pd.DataFrame({
            'id_name':['({}, {})'.format(row, column)],
            'maxy':maxy,
            'miny':miny, 
            'minx':minx,
            'maxx':maxx
        })

        tails = pd.concat([tails, new_row])
    
    tails = tails.reset_index(drop=True)

    return tails
   
#----    get_job_title    ----

def get_job_title(
    id_name:str,
    start_date:str,
    end_date:str,
    id_parent:str = '') -> str:
    """
    Create a unique name for the job. 
    Name must be unique compared to pasts names as well.

    Parameters
    ----------
    id_name:str
        Tail id name
    start_date:str
        Temporal start date,
    end_date:str
        Temporal end date
    id_parent:str
        Parent geometry id name
    
    Returns
    -------
    str:
        tail_{name_tail}_openeo_{start_date}_{end_date}_now_{current_date}
    """
    tail_name = re.sub(pattern = ',', repl = 'x', string = id_name)
    tail_name = my_utils.to_plain_str(tail_name)

    if id_parent != '':
        tail_name = '_'.join([id_parent, tail_name])

    title_job = 'tail_{}_openeo_{}_{}_now_{}'.format(
        tail_name,
        start_date, 
        end_date,
        my_utils.now_str())
    
    return(title_job)


#----    download_datacube_loop    ----

def download_datacube_loop(
    tails:pd.DataFrame,
    start_date:str,
    end_date:str,
    bands:list,
    aggregate:str,
    out_dir:Path,
    connection,
    collection:str,
    backend_server:str,
    client_id:str) -> tuple:
    """
    Download tail image from openeo according to tail and temporal parameters.
    Images are saved in a subdirectory of the specified output directory. 
    
    Parameters
    ----------
    tails:pd.DataFrame,
        pd.DataFrame containing the following columns:
        - id_parent: id name of the parent geometry
        - id_name: id name indicating the tail position in the grid (row, column), 
          starting from the top east corner.
    start_date:str
        Temporal start date,
    end_date:str
        Temporal end date
    bands:list
        List indicating the bands to download
    aggregate:str
        String indicating the type of aggregation. Currently available are
        'spatial' or 'temporal'
    out_dir:Path
        Path indicating the directory were to store the downloaded images
    connection
        The entry point to OpenEO
    collection:str
        String Id of the collection
    backend_server:str
        The server used to download the data
    client_id:str
        Client ID

    Returns
    -------
    tuple:
        tuple with two lists:
        - list of tail id that were successful downloaded
        - list of tail id that failed at download
    
    """

    successes = [] # record tails that succeeded download
    fails = [] # record tails that failed download
    
    # Add bounds info
    tails = pd.concat([tails, tails.bounds], axis = 1)

    for i in np.arange(len(tails)):
        tail = tails.iloc[i]

        print('\n\n{} / {}'.format(i+1, len(tails)))
        print('Preparing download tail {} {}...'.format(
            tail['id_parent'],
            tail['id_name'])
        )
            
        # EURAC server allows only OIDC auth 
        # (https://open-eo.github.io/openeo-python-client/auth.html)
        connection = openeo.connect(backend_server)
        connection.authenticate_oidc(client_id)
        
        # Define subset of the datacube
        datacube = create_datacube(
            bounds = tails.bounds.iloc[[i]],
            start_date = start_date, 
            end_date = end_date,
            bands = bands,
            aggregate = aggregate,
            connection = connection,
            collection = collection
            )  
    
        # Create a unique name for the job 
        # Name must be unique compared to pasts names as well
        title_job = get_job_title(
            id_name = tail['id_name'],
            start_date = start_date, 
            end_date = end_date,
            id_parent =  tail['id_parent']
            )
        print('job local name:', title_job)        
            
        # Execute computations by actually sending the job on the back-end
        job = datacube.create_job(title=title_job)
        job_id = job.job_id
        print('Batch job created with id: ', job_id)
    
        try:
            job.start_and_wait(
                max_poll_interval = 5, 
                connection_retry_interval = 10)
            results = job.get_results()
            print('Downloading tail {} {}...\n'.format(
                tail['id_parent'],
                tail['id_name']))
            results.download_files(out_dir / Path(title_job))
            successes.append(tail['id_name'])
            time.sleep(1)
        
        except:
            print('An unknown problem happened on the server when downloading tail {} {}.\n'\
                  .format(tail['id_parent'], tail['id_name']))
            fails.append(tail['id_name'])
    
    print('Tails downloaded:', successes)
    print('Error download:', fails)

    return (successes, fails)

#----    create_datacube    ----

def create_datacube(
    bounds:pd.DataFrame,
    start_date:str, 
    end_date:str,
    bands:list,
    aggregate:str,
    connection,
    collection:str) -> openeo.DataCube:
    """
    Create a datacube with defined borders for the download through openEO. 
    Spatial and temporal extent are specified through the parameters.
    
    Parameters
    ----------
    bounds:pd.DataFrame
        DataFrame with 'minx', 'maxx', 'miny', and 'maxy' data
    start_date:str
        Temporal start date
    end_date:str
        Temporal end date
    bands:list
        List indicating the bands to download
    aggregate:str
        String indicating the type of aggregation. Currently available are
        'spatial' or 'temporal'
    connection
        The entry point to OpenEO
    collection:str
        String Id of the collection

    Returns
    -------
    openeo.DataCube:
        Openeo datacube containing the description of the datacube to be 
        downloaded from openEO
    
    """            
    # load a collection in a cube and select only useful bands 
    # (https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi/resolutions/radiometric)
    # 10m res bands: RGB - RedGreenBlue(B2 B3 B4), 
    #                NIR - Near Infrared(B8), 
    #                AOT - Aerosol Optical Thickness, 
    #                WVP - Water Vapour
    # 20m res bands: VNIR - Visible Near Infrared(B5 B6 B7 B8A), 
    #                SWIR - Short Wavelength Infrared(B11 B12), 
    #                SCL - Scene Classification
    datacube = connection.load_collection(
        collection,
        spatial_extent={'west': bounds['minx'].iloc[0], 
                        'south': bounds['miny'].iloc[0], 
                        'east': bounds['maxx'].iloc[0], 
                        'north': bounds['maxy'].iloc[0]},
        temporal_extent=[start_date, end_date],
        #bands=['AOT_10m', 'B02_10m', 'B03_10m', 'B04_10m', 'B05_20m', 'B06_20m', 
        #       'B07_20m', 'B08_10m', 'B11_20m', 'B12_20m', 'B8A_20m', 'SCL_20m', 'WVP_10m']
        # ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B11', 'B12', 
        #  'B8A', 'SCL', 'WVP', 'CLOUD_MASK']
        bands = bands
        )
    
    # apply a process to the cube and define how to save data
    if aggregate == 'temporal':
        # aggregate data according to time
        datacube = datacube.max_time()
        datacube = datacube.save_result('GTiff')

    elif aggregate == 'spatial':
        # aggregate data according to space
        polygon = list(get_polygon(bounds).iloc[0].exterior.coords)
        polygon = [[x, y] for x,y in polygon]
        polygon_json = { 
            "type": "FeatureCollection", 
            "features": [ { 
                "type": "Feature", 
                "properties": {}, 
                "geometry": { 
                    "type": "Polygon", 
                    "coordinates": [ polygon ] 
                } }
            ]}
        
        datacube = datacube.aggregate_spatial(
            geometries =  polygon_json,
            reducer = 'mean'
            )
        datacube = datacube.save_result('JSON')
    
    # mask out clouds, cloud shadows, water and snow 
    # (https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm)
    # https://openeo.org/documentation/1.0/cookbook/#mask-out-specific-values
    #scl = datacube.band('SCL')
    #mask = ~ ((scl == 4) | (scl == 5) | (scl == 6))
    #datacube_masked = datacube.mask(mask)
    #datacube = datacube_masked
    
    return datacube

#----    get_data_cloud_mask    ----

def get_data_cloud_mask(path:Path) -> pd.DataFrame:
    """
    Given the path to the directory with all downloaded data about cloud mask, 
    return a dataframe with columns: 'id_parent', 'id_name', 'date_time', and
    'cloud_mask'.

    Parameters
    ----------
    path:Path
        Path to the directory with all downloaded data about cloud mask
    
    Returns
    -------
    pd.DataFrame
        Dataframe with columns: 'id_parent', 'id_name', 'date_time', and 
        'cloud_mask'.
    """

    # List all directories with downloaded json files 
    list_dir = os.listdir(path)
    list_files = [
        path/ dir / 'result.json' for dir in list_dir if re.search('^tail_', dir)
        ]

    # regex to match parent geom name and tail id name (row, col)
    pattern = re.compile(r"tail_(?P<id_parent>.+?)_(?P<row>[0-9]+)x(?P<col>[0-9]+)_openeo")
    
    res = pd.DataFrame()
    for file in list_files:
        with open(file, 'r') as file_json:
            data_iter = json.load(file_json)
    
        data_iter = pd.DataFrame.from_dict(data_iter).T
        data_iter = data_iter.reset_index().rename(columns = {
            'index':'date_time',
            'CLOUD_MASK':'cloud_mask'})
        data_iter['cloud_mask'] = data_iter['cloud_mask'].apply(lambda x: float(x[0]))
        data_iter['date_time'] = pd.to_datetime(data_iter['date_time'])


        re_result = pattern.search(str(file))
        data_iter['id_parent'] = re_result['id_parent']
        data_iter['id_name'] = '({}, {})'.format(re_result['row'], re_result['col'])

        res = pd.concat([res, data_iter])
    
    res = res.reindex(columns = ['id_parent', 'id_name', 'date_time', 'cloud_mask'])
    res = res.sort_values(by=['id_parent', 'id_name', 'date_time', 'cloud_mask'])
    res = res.reset_index(drop = True)
    return res

#----    assign_tail    ----

def assign_tail(
    geom,
    data_tail:gpd.GeoDataFrame,
    ) -> str:
    """
    Given a set of tails, check which tail contains a given geom. Returns 
    the tail 'id_name'

    Parameters
    ----------
    geom
        a geometry to check
    data_tail:gpd.GeoDataFrame
        dataframe with tails 'id_name' and 'geometry'

    Return
    ------
    str
        indicating the tail 'id_name'
    """
    mask = data_tail.contains(geom)

    # Check geom is contained in only one tail
    if sum(mask) != 1:
        if sum(mask) == 0:
            message = 'No tail contains the geom'
        else:
            message =  'Geom is contained in multiple tails'
        raise ValueError('Issue finding tail: {}'.format(message))
    
    res = data_tail['id_name'][mask].iloc[0]

    return res

#----    get_closest_geom    ----

def get_closest_geom(
    point,
    geoms:gpd.GeoSeries,
    initial_buffer:int = 10,
    max_buffer:int = 50
    ):
    """
    Get the closest geom to a specific point. Search is conduct by spacial 
    indexing starting form a buffer around the point. If no geom is found, the 
    buffer is increased up too max_buffer value.

    Parameters
    ----------
    point
        point geometry used as reference
    geoms:gpd.GeoSeries
        geometries used to find closest
    initial_buffer:int
        value of the initial search buffer
    max_buffer:int
        value of the maximum search buffer
    
    Return
    ------
    the closest geometry or empty geom if no geometry has been found within the 
    maximum buffer
    """

    buffer = initial_buffer
    query = []

    while len(query) == 0 and buffer <= max_buffer:
        buffered = point.buffer(buffer)
        query = geoms.sindex.query(buffered)
        buffer += initial_buffer
    
    if len(query) == 0:
        message = 'No close building available for'
        print('{} {}.\nResult set to empty polygon'.format(message, point))
        res = shp.geometry.Polygon(None)

        return res
    
    distances = geoms.iloc[query].distance(point)
    min_dist = min(distances)
    mask = distances == min_dist

    # Check there is unique entry with min distance
    if(sum(mask) != 1):
        message = 'Multiple geom with same minimum distance for'
        print('{} {}.\nResult set to empty polygon'.format(message, point))
        res = shp.geometry.Polygon(None)
    else:
        res = geoms.iloc[query].loc[mask].iloc[0]

    return res

#----    normalize    ----

def normalize(array, clip_max = .3):
    # # normalize bands into 0.0 - 1.0 scale (for better visualization)
    # array_min, array_max = array.min(), array.max()
    # array_normalized = (array - array_min) / (array_max - array_min)


    ndata_cutoff = np.clip(array/10000, 0, clip_max)  # divide with 10000 and cut of to range [0.0, 0.3]
    array_normalized = ndata_cutoff/clip_max # stretch to [0.0, 1.0]

    ndata_8bit = (array_normalized*255).astype(np.uint8) 
    return ndata_8bit

#----    plot_satellite    ----

def plot_satellite(
    file,
    bands = [4,3,2],
    osm_raster = None,
    buildings = None,
    points = None,
    figsize = (50, 50)):

    # get bands
    src = rasterio.open(file / "result.tiff")

    band_0 = normalize(src.read(bands[0]))
    band_1 = normalize(src.read(bands[1]))
    band_2 = normalize(src.read(bands[2]))

    band_stack = np.array([band_0, band_1, band_2])
    
    fig, ax = plt.subplots(1, figsize = figsize)
    show(band_stack, transform=src.transform, ax = ax)

    if osm_raster is not None:
        osm_raster.to_crs(src.crs).plot(ax = ax)
    
    if buildings is not None:
        buildings.to_crs(src.crs).plot(ax = ax, color = 'green')
    
    if points is not None:
        points.to_crs(src.crs).plot(ax = ax, color = 'red')

#----    get_bands_stats    ----

def get_bands_stats(
    file:Path,
    geom_data:gpd.GeoDataFrame
    ) -> pd.DataFrame:
    """
    For each band in the raster, get summary statistics (count, min, mean, and 
    max) of the pixels delimited by the geometry objects. 

    Parameters
    ----------
    file:Path
        Path to the directory with the openeo satellite image
    geom_data:gpd.GeoDataFrame
        Data defining the buildings geometries. Required columns are 'COD_APE'
        indicating the building id

    Return
    ------
    pd.DataFrame
        Summary statistics (count, min, mean, and max) of each band. Returned
        columns are formatted as '{name_band}_{stats}'. Puls, 'COD_APE' is used 
        to identify the buildings.
    """
   
    # Load the image
    src = rasterio.open(file / 'result.tiff')

    # Summarize bands values
    res = pd.DataFrame()
    bands_available = src.descriptions
    affine = src.transform
    for i, name_band in zip(range(1, len(bands_available) + 1), bands_available):
        array = src.read(i)
        res_iter = pd.DataFrame(
            rasterstats.zonal_stats(
                vectors = geom_data, 
                raster = array, 
                affine=affine,
                nodata = -999,
                all_touched = False))
        res_iter = res_iter.add_prefix(name_band + "_")
        res = pd.concat([res, res_iter], axis = 1)

    res = res.set_index(geom_data.index)
    res = res.replace(-999, np.nan)
    res.insert(0, 'COD_APE', geom_data['COD_APE'])

    return res

#----    loop_get_bands_stats    ----

def loop_get_bands_stats(
    files,
    geom_data
    ):
    """
    For each satellite image, get bands summary statistics (count, min, mean, and 
    max) of the pixels delimited by the buildings geom within the image. 

    Parameters
    ----------
    file:Path
        Path to the directory with the openeo satellite image
    geom_data:gpd.GeoDataFrame
        Data defining the buildings geometries. Required columns are 'COD_APE'
        indicating the building id

    Return
    ------
    pd.DataFrame
        Summary statistics (count, min, mean, and max) of each band. Returned
        columns are formatted as '{name_band}_{stats}'. Puls, 'COD_APE' is used 
        to identify the buildings.
    """
    res = pd.DataFrame()

    start = timeit.default_timer()
    for index, file in enumerate(files):
        start_iter = timeit.default_timer()

         # Get the image id_tail 
        pattern = re.compile(r"tail_(?P<id_parent>.+?)_(?P<row>[0-9]+)x(?P<col>[0-9]+)_openeo")
        re_result = pattern.search(str(file))
        id_tail = '({}, {})'.format(re_result['row'], re_result['col'])
        
        print('\n{}/{}'.format(index + 1, len(files)))
        print('Evaluating tail {}'.format(id_tail))
        
        # Select buildings within that tail
        mask = geom_data['id_tail'] == id_tail

        if not any(mask):
            print('No available builidings')
            continue

        # Get summary statistics
        res_iter = get_bands_stats(
            file = file,
            geom_data = geom_data.loc[mask]
            )

        res = pd.concat([res, res_iter], axis = 0)
        stop = timeit.default_timer()
        print('Iter Time: {:.2f}'.format(stop - start_iter))
        print('Total Time: {:.2f}'.format(stop - start))

    res.insert(1, 'count', res['AOT_count'])
    to_drop =list(res.filter(regex=r'.+_count'))
    res = res.drop(to_drop, axis = 1)

    return res

#----    test_shadow    ----

def test_shadow(
    data,
    col_bands,
    val:int = 100):
    """
    """

    test = data[col_bands].copy()
    test = test.applymap(lambda x: x < val)
    res = test.apply(lambda x: all(x), axis = 1)
    
    return res


#----    get_data_era_5    ----

def get_data_era_5(
        path_to_file,
        layer:int = 0,
        crs:str = 'EPSG:4326') -> gpd.GeoDataFrame:
    """
    Given the path to the ERA5 .grib file, get a geodataframe with the 
    information included in the selected layer. Grid of polygons is obtained 
    creating tails with of +/- .05 grade dimension from center coordinates.

    Can specify custom crs for export.
    """

    grbs = pygrib.open(str(path_to_file))

    # select correct layer
    grb = grbs.select()[layer]

    lats, lons = grb.latlons()

    res = gpd.GeoDataFrame(
        data = pd.DataFrame({
            'temp':my_utils.kelvin2celsius(grb.values.flatten())
        }),
        geometry = get_era5_tails(lons.flatten(), lats.flatten()),
        crs = 'EPSG:4326'
    )

    res = res.to_crs(crs)
    
    return res

#----    get_era5_tails    ----

def get_era5_tails(
        lon:pd.Series, 
        lat:pd.Series):
    """
    Given center longitudes and latitudes in grades, return a polygons of +/- .05 
    grade dimension.
    """

    bounds = pd.DataFrame({
        'minx' : lon - .05,
        'miny' : lat - .05,
        'maxx' : lon + .05,
        'maxy' : lat + .05,
    })

    res = get_polygon(bounds = bounds)

    return res

#=================

