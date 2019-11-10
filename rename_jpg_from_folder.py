#!/usr/bin/python3

# Description: This script looks for directories for their names.
#              For each dir it looks in it to rename file accordingly.
#
# Tested under Ubuntu 18.04 and Windows 10
#
import os
import glob
import re
import sys
import getopt

FOLDER_TO_IGNORE = ['raw', 'A supprimer', 'to_delete', 'jpg_only', 'Videos']

'''
How to test it :
rm -r test_folder
mkdir -p test_folder/raw test_folder/jpg1 test_folder/jpg2
touch test_folder/raw/picture_to_not_rename.rw2
touch test_folder/jpg1/picture_to_rename_01.jpg
touch test_folder/jpg1/picture_to_rename_01.jpg
touch "test_folder/jpg1/18.08.12 - 60793 - RealSanta - Flying (Canon).jpg"
touch "test_folder/jpg1/18.08.12 - 60794 - RealSanta - Landind.jpg"
touch "test_folder/jpg1/18.08.12 - 60795 - RealSanta - TakeOff.jpg"
touch "test_folder/jpg2/17.12.25 - Real Santa2.JPG"
touch "test_folder/jpg2/17.12.25 - Fake Santa.jpg"
touch "test_folder/jpg2/17.12.25 - Fake Santa2.JPG"
=> Launch the script in current folder.
Attended result :
Files in jpg1 and jpg2 are rename with the folder name at the end.

'''

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
    print('Reminder : Run in RAW folder !!!')
    try:
      opts, args = getopt.getopt(argv,'hr')
    except getopt.GetoptError:
      print('Usage : rename_jpg_from_folder.py -r to rename files')
      sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('Usage : rename_jpg_from_folder.py [-r]')
            print('Use "-r" to run the script with touching files.')
            sys.exit()
        elif opt == '-r':
         dry_run = False
    rawdir = os.curdir
    jpgdir = os.path.join(os.curdir)
    print("Looking into", os.path.realpath(jpgdir), " to rename in subfolders")
    folder_list = [ name for name in os.listdir(jpgdir) if os.path.isdir(os.path.join(jpgdir, name)) ]
    folder_list = [folder for folder in folder_list if folder not in FOLDER_TO_IGNORE]
    print("# Scan the current folder to rename in subfolders")
    rename_file(folder_list)
    if dry_run :
        print("--------------------------------------------------")
        print("- WARNING : Dry run, no files has been touched ! -")
        print("- Use '-r' switch to really rename file            -")
        print("--------------------------------------------------")
    print("Done")

if __name__ == "__main__":
   main(sys.argv[1:])
