#!/usr/bin/python3

'''
This script rename your pictures and videos according to a given name and the date you took them, according to EXIF data.

Usage :
python3 rename_and_classify_pictures.py <folder> <name>

Writen by : Benoît Courty
Licence : BSD 3
'''

import os
import glob
import re
import sys
import argparse
from pathlib import Path
from PIL import Image # For EXIF



def rename_file(folder_list):
    global dry_run
    for folder in folder_list:
        #print("jpg : ", f)
        folder_name = os.path.basename(folder)
        print(folder_name)
        #print(matching_file)
        file_list = [ name for name in os.listdir(folder) if not os.path.isdir(os.path.join(folder, name)) ]
        for f in file_list:
            file_name = os.path.splitext(f)[0]
            ext = os.path.splitext(f)[1]
            origin_file = os.path.join(folder_name, f)
            destination_file = os.path.join(folder_name, file_name + ' - ' + folder_name + ext)
            print(origin_file,'->', destination_file)
            if not dry_run :
                if not os.path.exists(destination_file):
                    os.rename(origin_file, destination_file)

def main(argv):
    global dry_run
    dry_run = True
    #print('Reminder : Run in RAW folder !!!')

    parser = argparse.ArgumentParser(description='Process some files.')
    parser.add_argument('folder', type=str, help='Input dir for videos')
    parser.add_argument('name')
    parser.add_argument('--modify', dest='dry_run', action='store_const',
                        const=False, default=True,
                        help='No dry run (default: no modification)')

    args = parser.parse_args()
    print(args.folder)



    oridir = os.path.realpath(os.path.join(args.folder))
    jpg_dir = os.path.join(oridir, 'jpg')
    raw_dir = os.path.join(oridir, 'raw')
    jpg_only_dir = os.path.join(oridir, 'jpg_only')
    Path(jpg_only_dir).mkdir(parents=True, exist_ok=True)

    print("Looking into", oridir, " to rename in subfolders")
    # file_list = [ name for name in os.listdir(jpgdir) if os.path.isdir(os.path.join(jpgdir, name)) ]
    # folder_list = [folder for folder in folder_list if folder not in FOLDER_TO_IGNORE]
    # print("# Scan the current folder to rename in subfolders")
    # rename_file(folder_list)
    # if dry_run :
    #     print("--------------------------------------------------")
    #     print("- WARNING : Dry run, no files has been touched ! -")
    #     print("- Use '-r' switch to really rename file            -")
    #     print("--------------------------------------------------")
    # print("Done")
    file_list = [ name for name in os.listdir(folder) if not os.path.isdir(os.path.join(folder, name)) ]
    for file_ori in file_list:
        # Mettre tout les fichiers en minuscules
        file_dest = file_ori.lower()

        print(file_ori,'->', file_dest)
    
        # Traite les photos
        # retire les prefix inutile (DSC...)
        # Get jpg exif (Thanks to https://github.com/matthewrenze/rename-images/blob/master/Rename.py)

        # Get the file extension
        file_ext = os.path.splitext(file_name)[1]

        # If the file does not have a valid file extension
        # then skip it
        if (file_ext not in valid_extensions):
            continue

        # Create the old file path
        old_file_path = os.path.join(folder_path, file_name)

        # Open the image
        image = Image.open(old_file_path)

        # Get the date taken from EXIF metadata
        date_taken = image._getexif()[36867]

        # Close the image
        image.close()

        # Reformat the date taken to "YYYYMMDD-HHmmss"
        date_time = date_taken \
            .replace(":", "")      \
            .replace(" ", "-")

        # Combine the new file name and file extension
        new_file_name = date_time + file_ext

        # Create the new folder path
        new_file_path = os.path.join(folder_path, new_file_name)

        # Rename the file
        os.rename(old_file_path, new_file_path)

        # rename RAW
        # Move jpg_only
        # Move jpg to "jpg_ori"
        # Move raw

        # Rename MP4 with filesystem date
        # Move MP4 to "videos"

        # exifautotran ?

if __name__ == "__main__":
   main(sys.argv[1:])
