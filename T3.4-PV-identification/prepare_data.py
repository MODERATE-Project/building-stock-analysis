import cut_tif_images
import label_images
from pathlib import Path


# if you want to label rooftops manually set this option to True!
LABELING = False


if __name__ == "__main__":
    # if the rooftops should be manually labeled the label should be set to true. 
    # This will open a window using tkinter for labelling the data manually.
    # If the Classifier should just classify the images without manual labeling to 
    # check its accuracy, the label should be set to False:

    # check if the model from solarnet has been trained already:

    cut_tif_images.main(save_png=False)  # only save pngs if you want to look at them, early for testing.
    if LABELING:
        label_images.main()

