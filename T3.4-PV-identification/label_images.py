import tkinter as tk
from tkinter import Tk, Label, Entry, Button
from pathlib import Path
from PIL import Image, ImageTk
import os
import pandas as pd
import numpy as np
import shutil
import random


def label_images(image_folder, label_path: Path):
    """
    Open images in a folder using a Tkinter window, allow the user to label them, 
    and append the label to the file name.
    Labeled images are ignored.
    
    Args:
    image_folder (str): The directory where the images are stored.
    """
    def display_image(file_path: Path):
        """Display the image in the Tkinter window and get user input for the label."""
        image_array = np.load(file_path)
        img = np.moveaxis(image_array, 0, -1) 
        img = Image.fromarray(img.astype('uint8'))

        img.thumbnail((800, 800))  # Resize the image to fit in the window
        
        # Update the image in the window
        img_tk = ImageTk.PhotoImage(img)
        
        # Keep the image reference to avoid garbage collection
        img_label.config(image=img_tk)
        img_label.image = img_tk  # Keeping a reference to avoid it being collected
        
        # Update the filename label
        filename_label.config(text=file_path.name)

        # Clear and focus on the input field
        label_entry.delete(0, 'end')  # Clear any previous input
        label_entry.focus()

        # Update the window
        root.update_idletasks()
        img.close()

    def save_label():
        """Save the label and rename the file."""
        label = label_entry.get().strip().lower()

        if label in ["0", "1"]:
            # Generate the new file name with the label
            new_file_name = f"{current_file.name.replace('.npy','')}_{label}.npy"
            new_file_path = image_folder / "labeled" / new_file_name

            # Rename the file (overwrite the original image)
            shutil.copy(current_file, new_file_path)
            print(f"Image {current_file} labeled as '{label}' and renamed to {new_file_name}")

            # Move to the next image
            next_image()
        else:
            error_label.config(text="Invalid input. Please type '1='yes or '0'=no.", fg="red")

    def next_image():
        """Load the next image."""
        nonlocal current_file

        try:
            current_file = next(files_iter)  # Get the next image file
            display_image(current_file)
        except StopIteration:
            print("No more images to label.")
            root.quit()

    # Get the list of PNG files that are not already labeled
    if label_path.exists():
        labels = pd.read_csv(label_path, sep=";")
        identified_ids = list(labels["osmid"].values)
    else:
        identified_ids = []
    files = [f for f in (image_folder).iterdir() if f.name.endswith(".npy") and not ("_0.npy" in f.name or "_1.npy" in f.name)]
    labeled_ids = [f.name.replace(".npy", "").replace("building_", "")[:-2] for f in (image_folder/"labeled").iterdir() if f.name.endswith(".npy")]
    # drop the ids from the csv file in case the images have been moved or deleted and the info is just stored in the csv file:
    files_2 = [f for f in files if f.name.replace(".npy", "").replace("building_", "") not in identified_ids]
    files_3 = [f for f in files_2 if f.name.replace(".npy", "").replace("building_", "") not in labeled_ids]
    random.shuffle(files_3)  
    files_iter = iter(files_3)

    # Set up Tkinter window
    root = Tk()
    root.title("Image Labeling")

    # Set up the layout
    img_label = Label(root)
    img_label.pack()

    filename_label = Label(root, text="")
    filename_label.pack()

    label_entry = Entry(root)
    label_entry.pack()

    submit_button = Button(root, text="Submit", command=save_label)
    submit_button.pack()

    error_label = Label(root, text="")
    error_label.pack()

    # Start labeling the first image
    current_file = None
    next_image()

    # Start the Tkinter event loop
    root.mainloop()


def create_csv_with_labels(folder: Path, label_file: Path):

    files = [f.name for f in folder.iterdir() if f.name.endswith("_0.npy") or f.name.endswith("_1.npy")]
    id_dict = {}
    for f in files:
        osmid = f.replace("building_", "").replace("_0.npy", "").replace("_1.npy", "")
        pv_bool =  f.split("_")[-1].replace(".npy","")
        if pv_bool == "0":
            has_pv = "no"
        elif  pv_bool == "1":
            has_pv = "yes"
        else:
            assert "wrong pv bool in image name"
        id_dict[osmid] = has_pv
    df = pd.DataFrame.from_dict(id_dict, orient="index").reset_index().rename(columns={"index": "osmid", 0: "has_pv"})

    if label_file.exists():
        label_df = pd.read_csv(label_file, sep=";")  # read the file with labels that were already saved
        df_sum = pd.concat([label_df, df], axis=0)
        # df_sum.drop_duplicates(inplace=True)
    else:
        df_sum = df
    
    df_sum.drop_duplicates(inplace=True)  # drop duplicates in case this function is called multiple times with the same data
    df_sum.to_csv(label_file, sep=";", index=False)
    print(f"saved {label_file}")


def shift_numpy_files_into_empty_and_solar_folders(data_folder: Path):
    """ if test = True than the files will be saved in different "test" folders which are not used for training but only for valudation
    """
    # numpy files are saved in image folder parent and are shifted in the correct folders here:

    empty_train_folder = data_folder / "empty/org"  
    solar_train_folder = data_folder / "solar/org"
    empty_val_folder = data_folder / "empty/val"  
    solar_val_folder = data_folder / "solar/val"

    empty_val_folder.mkdir(exist_ok=True, parents=True)
    solar_val_folder.mkdir(exist_ok=True, parents=True)
    empty_train_folder.mkdir(exist_ok=True, parents=True)
    solar_train_folder.mkdir(exist_ok=True, parents=True)

    # iterate through labeled folder:
    # split the files into training and validation folders 80/20
    labeled_folder = data_folder / "processed" / "labeled"
    files_true = [f for f in labeled_folder.iterdir() if f.is_file() and f.name.endswith("_1.npy")]
    files_false = [f for f in labeled_folder.iterdir() if f.is_file() and f.name.endswith("_0.npy")]

    for i, file in enumerate(files_true):
        # first 80% into the train folders:
        if i < int(0.8*len(files_true)):
            if not (solar_train_folder / file.name).exists(): # dont copy twice in case it was copied before
                file.rename(solar_train_folder / file.name)
        else:  # remaining 20% in validation folder:
            if not (solar_val_folder / file.name).exists(): 
                file.rename(solar_val_folder / file.name)
    
    for i, file in enumerate(files_false):
        # first 80% into the train folders:
        if i < int(0.8*len(files_false)):
            if not (empty_train_folder / file.name).exists(): # dont copy twice in case it was copied before
                file.rename(empty_train_folder / file.name)
        else:  # remaining 20% in validation folder:
            if not (empty_val_folder / file.name).exists(): 
                file.rename(empty_val_folder / file.name)

    print(f"moved labeled files from {labeled_folder} to "
          f"{empty_train_folder} and \n "
          f"{empty_val_folder} and to solar folder \n "
          f"{solar_train_folder} and \n "
          f"{solar_val_folder}" 
          )         


def main():
    preped_image_folder = Path(__file__).parent / "solar-panel-classifier" / "new_data" / "processed" 
    label_file = Path(__file__).parent / "results" / "OSM_IDs_labeled.csv"

    if not preped_image_folder.exists():
        preped_image_folder.mkdir(parents=True)
    if not (preped_image_folder / "labeled").exists():   
        (preped_image_folder / "labeled").mkdir(parents=True)

    # create csv file before and after to make sure the labeles from the previous run, if aborted are updated
    create_csv_with_labels(preped_image_folder / "labeled", label_file)
    label_images(preped_image_folder, label_file)
    create_csv_with_labels(preped_image_folder / "labeled", label_file)

    shift_numpy_files_into_empty_and_solar_folders(data_folder=preped_image_folder.parent)


if __name__ == "__main__":
    main()


    

