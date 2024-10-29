import cut_tif_images
import label_images

if __name__ == "__main__":
    # if the rooftops should be manually labeled the label should be set to true. 
    # This will open a window using tkinter for labelling the data manually.
    # If the Classifier should just classify the images without manual labeling to 
    # check its accuracy, the label should be set to False:

    labeling = False

    cut_tif_images.main(save_png=labeling)  # only save pngs for labeling
    if labeling:
        label_images.main()

