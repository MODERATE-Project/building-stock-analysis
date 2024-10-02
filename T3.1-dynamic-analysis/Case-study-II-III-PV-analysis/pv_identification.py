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


def download_osm_building_shapes(name: str):
    """ make sure that you downloaded the boundary shapefile from geojson.io and save it as 'name.shp' in the data folder"""
    # the polygon shp file was downloaded from geojson.io
    # polygon = gpd.read_file(Path(__file__).parent / "data" / f"{name}.shp").geometry.iloc[0]
    # buildings = ox.geometries_from_polygon(polygon=polygon, tags={"building": True})
    buildings = ox.geometries_from_place("Crevillent, Spain", tags={"building": True})

    columns_2_keep = ["geometry", "nodes", "building", ]
    df = buildings.loc[:, columns_2_keep]
    df.to_file(Path(__file__).parent / "data" / f"{name}.gpkg", driver="GPKG")
    return df

def load_tif_orthopohots(src_file_name:str):
    tif_path = Path(__file__).parent / "data" / src_file_name
    src = rasterio.open(tif_path)
    return src


def cut_tif_into_building_photos(buildings, src, imsize: int):
    out_of_bounds = []
    # cut out the buildings from the photos:
    orig_file = src.read()

    for i, building in buildings.iterrows():
            # Mask the image using the building polygon
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
            
            clipped_orgfile = orig_file[:, int(px_min):int(px_max), int(py_min):int(py_max)]

            # If the building was too large, resize it back to 224x224
            if clipped_orgfile.shape[1] != imsize or clipped_orgfile.shape[2] != imsize:
                # Convert to PIL Image, resize, then convert back to NumPy array
                img = np.moveaxis(clipped_orgfile, 0, -1)  # Rearrange (bands, x, y) to (x, y, bands)
                img = Image.fromarray(img.astype('uint8'))  # Convert to unsigned 8-bit integer format
                img_resized = img.resize((imsize, imsize), Image.LANCZOS)
                clipped_orgfile = np.moveaxis(np.array(img_resized), -1, 0) 
                print(f"{building.osmid} had to be resized")
            

            output_path = Path(__file__).parent / "data" / "processed" 
            if not output_path.exists():
                output_path.mkdir(parents=True)
            if not (output_path / "labelled").exists():
                (output_path / "labelled").mkdir()

            np.save(output_path / f'building_{building.osmid}.npy', clipped_orgfile)

            # to check the images:
            img = np.moveaxis(clipped_orgfile, 0, -1)  # Rearrange (bands, x, y) to (x, y, bands)
            img = Image.fromarray(img.astype('uint8'))
            img.save(Path(__file__).parent / "data" / "processed" / "labelled" / f"building_{building.osmid}.png")
        
    print(f"{len(out_of_bounds)} buildings were out of bounds")





if __name__ =="__main__":
    buildings = download_osm_building_shapes(name="Crevillent")
    buildings.reset_index(inplace=True)

    src_files = [
        Path(__file__).parent / "data" / "020201_2023CVAL0025_25830_8bits_RGBI_0893_2-5.tif",
        Path(__file__).parent / "data" / "020201_2023CVAL0025_25830_8bits_RGBI_0893_2-4.tif",
        Path(__file__).parent / "data" / "020201_2023CVAL0025_25830_8bits_RGBI_0893_1-5.tif",
        Path(__file__).parent / "data" / "020201_2023CVAL0025_25830_8bits_RGBI_0893_1-4.tif",

    ]
    for file in src_files:
        src = load_tif_orthopohots(file)
        if src.crs != buildings.crs:
            buildings = buildings.to_crs(src.crs)
        cut_tif_into_building_photos(buildings=buildings, src=src, imsize=224)








