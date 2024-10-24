import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import osmnx as ox
import os
import geopandas as gpd
import rasterio
from PIL import Image, ImageTk
import pathlib
from shapely.geometry import box
from rasterio.transform import from_bounds
from rasterio.windows import Window
from pyproj import Transformer


def download_osm_building_shapes(source: str):
    """ downloads all building shapes that are within the bounds of the source"""
    bounds = source.bounds
    polygon = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
    polygon_wgs84 = ox.projection.project_geometry(polygon, crs=source.crs, to_crs='EPSG:4326')[0]
    buildings = ox.geometries_from_polygon(polygon=polygon_wgs84, tags={"building": True})
    
    areas = buildings.to_crs(epsg=3857).area
    columns_2_keep = ["geometry", "nodes", "building", ]
    df = buildings.loc[:, columns_2_keep]
    df["area"] = areas
    df_filtered = df.loc[df["area"] > 45, :].copy()
    df_filtered.to_file(Path(__file__).parent / "solar-panel-classifier" / "new_data" / f'{Path(source.name).name.replace(".tif", "")}.gpkg', driver="GPKG")
    return df_filtered


def cut_tif_into_building_photos(buildings, src, imsize: int):
    # create folders:
    processed_folder = Path(__file__).parent / "solar-panel-classifier" / "new_data" / "processed" 
    processed_folder.mkdir(parents=True, exist_ok=True)
    (processed_folder/ "unlabelled").mkdir(exist_ok=True)

    out_of_bounds = []
    # cut out the buildings from the photos:
    orig_file = src.read()

    for i, building in buildings.iterrows():
            # Mask the image using the building polygon
            image_path = processed_folder / "unlabelled" / f"building_{building.osmid}.png"
            if image_path.exists():
                print(f"{building.osmid} already exists")
                continue

            try:
                out_image, out_transform = mask(src, [building["geometry"]], crop=True)
            except:
                out_of_bounds.append(building.osmid)
                continue
            
            # Calculate bounds for a 224x224 window around the centroid
            centroid = building["geometry"].centroid
            bounds = building['geometry'].bounds
            min_px, min_py = src.index(bounds[0], bounds[1])  # minx, miny
            max_px, max_py = src.index(bounds[2], bounds[3]) 
            # if min and max are change - swap them
            if min_px > max_px:
                min_px, max_px = max_px, min_px

            if min_py > max_py:
                min_py, max_py = max_py, min_py

            # Ensure the pixel coordinates are within image bounds
            px_min = max(0, min_px)
            px_max = min(orig_file.shape[1], max_px)
            py_min = max(0, min_py)
            py_max = min(orig_file.shape[2], max_py)
            
            clipped_orgfile = orig_file[:3, int(px_min):int(px_max), int(py_min):int(py_max)]  # CAREFUL, this is writte for RGBI images, cutting the infrared part

            # Convert to PIL Image, resize, then convert back to NumPy array
            img = np.moveaxis(clipped_orgfile, 0, -1)  # Rearrange (bands, x, y) to (x, y, bands)
            img = Image.fromarray(img.astype('uint8'))  # Convert to unsigned 8-bit integer format
            img_resized = img.resize((imsize, imsize), Image.LANCZOS)
            clipped_orgfile = np.moveaxis(np.array(img_resized), -1, 0) 
            
            np.save(processed_folder / f'building_{building.osmid}.npy', clipped_orgfile)

            # to check the images:
            img_resized.save(processed_folder/ "unlabelled" / f"building_{building.osmid}.png")
        
    print(f"{len(out_of_bounds)} buildings were out of bounds")




def remove_black_images(image_folder: Path):
    """
    This function checks each image in the folder and removes the black images.
    
    Args:
    image_folder (str): Path to the folder containing the images.
    """
    # Get all PNG files in the folder
    files = [f for f in image_folder.iterdir() if f.name.endswith('.png')]
    numpy_folder = image_folder.parent
    for file_path in files:
        try:
            # Open the image
            img = Image.open(file_path)
            
            # Convert the image to a NumPy array
            img_array = np.array(img)
            
            # Check if all the pixels are black
            if np.all(img_array == 0):
                # If the image is black, delete it
                os.remove(file_path)
                os.remove(numpy_folder / file_path.name.replace(".png", ".npy")) # also delete corresponding numpy file
                print(f"Removed black image: {file_path.name}")

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")



if __name__ =="__main__":
    tif_folder = Path(__file__).parent / "solar-panel-classifier" / "new_data" / "input_tifs"
    input_tifs =  [f for f in tif_folder.iterdir() if f.suffix == ".tif"]

    for file in input_tifs:
        src = rasterio.open(file)
        buildings = download_osm_building_shapes(src)
        buildings.reset_index(inplace=True)

        if src.crs != buildings.crs:
            buildings = buildings.to_crs(src.crs)
        cut_tif_into_building_photos(buildings=buildings, src=src, imsize=224)

    # some images are just black, remove them
    remove_black_images(image_folder=Path(__file__).parent / "solar-panel-classifier" / "new_data" /"processed" / "unlabelled" )







