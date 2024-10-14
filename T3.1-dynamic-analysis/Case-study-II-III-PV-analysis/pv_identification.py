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
  
    columns_2_keep = ["geometry", "nodes", "building", ]
    df = buildings.loc[:, columns_2_keep]
    df.to_file(Path(__file__).parent / "data" / f"{Path(source.name).name.replace(".tif", "")}.gpkg", driver="GPKG")
    return df


def cut_tif_into_building_photos(buildings, src, imsize: int):

    out_of_bounds = []
    # cut out the buildings from the photos:
    orig_file = src.read()

    for i, building in buildings.iterrows():
            # Mask the image using the building polygon
            image_path = Path(__file__).parent / "data" / "processed" / "unlabelled" / f"building_{building.osmid}.png"
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
            building_width_px = max_px - min_px
            building_height_px = max_py - min_py

            if building_width_px <= imsize and building_height_px <= imsize:
                center_px, center_py = src.index(centroid.x, centroid.y)

                px_min = center_px - imsize / 2
                px_max = center_px + imsize / 2
                py_min = center_py - imsize / 2
                py_max = center_py + imsize / 2

            else:
                px_min = min_px
                px_max = max_px
                py_min = min_py
                py_max = max_py


            # Ensure the pixel coordinates are within image bounds
            px_min = max(0, px_min)
            px_max = min(orig_file.shape[1], px_max)
            py_min = max(0, py_min)
            py_max = min(orig_file.shape[2], py_max)
            
            clipped_orgfile = orig_file[:3, int(px_min):int(px_max), int(py_min):int(py_max)]  # CAREFUL, this is writte for RGBI images, cutting the infrared part

            # If the building was too large, resize it back to 224x224
            if clipped_orgfile.shape[1] != imsize or clipped_orgfile.shape[2] != imsize:
                # Convert to PIL Image, resize, then convert back to NumPy array
                img = np.moveaxis(clipped_orgfile, 0, -1)  # Rearrange (bands, x, y) to (x, y, bands)
                img = Image.fromarray(img.astype('uint8'))  # Convert to unsigned 8-bit integer format
                img_resized = img.resize((imsize, imsize), Image.LANCZOS)
                clipped_orgfile = np.moveaxis(np.array(img_resized), -1, 0) 
                print(f"{building.osmid} had to be resized")
            

            output_path = Path(__file__).parent / "data" / "processed" 
            output_path.mkdir(parents=True, exist_ok=True)
            (output_path / "unlabelled").mkdir(exist_ok=True)

            np.save(output_path / f'building_{building.osmid}.npy', clipped_orgfile)

            # to check the images:
            img = np.moveaxis(clipped_orgfile, 0, -1)  # Rearrange (bands, x, y) to (x, y, bands)
            img = Image.fromarray(img.astype('uint8'))
            img.save(Path(__file__).parent / "data" / "processed" / "unlabelled" / f"building_{building.osmid}.png")
        
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
    input_tifs =  [f for f in (Path(__file__).parent / "data" / "input_tifs").iterdir() if f.suffix == ".tif"]

    # for file in input_tifs:
    #     src = rasterio.open(file)
    #     buildings = download_osm_building_shapes(src)
    #     buildings.reset_index(inplace=True)

    #     if src.crs != buildings.crs:
    #         buildings = buildings.to_crs(src.crs)
    #     cut_tif_into_building_photos(buildings=buildings, src=src, imsize=224)

    # some images are just black, remove them
    remove_black_images(image_folder=Path(__file__).parent / "data" / "processed" / "unlabelled" )







