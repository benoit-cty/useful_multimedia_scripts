#!/usr/bin/python3
# Based on

# Description: This script looks in a sub-directorie for RAW files.
#              For each file it looks in upper directory if the JPG exist
#              if not, it move the RAW to trash.
#
# Huge modifications of a script from Thomas Dahlmann and Renaud Boitouzet ( https://photo.stackexchange.com/questions/16401/how-to-delete-jpg-files-but-only-if-the-matching-raw-file-exists/49377#49377 )
#
# WARNING if you use raw only sometime : they will be put in "to_delete"
# one way  to avoid it is to launch the script before deleting jpg,
# then renaming "to_delete" to "raw_only"
#
# Tested under Ubuntu and Windows
#
#
import os
import glob
import re
import sys
import getopt

'''
How to test it :
rm -r test_folder
mkdir test_folder
touch test_folder/random_file.txt
mkdir test_folder/raw
touch test_folder/picture.jPg
touch "test_folder/17.12.25 - Real Santa.jpg"
touch "test_folder/17.12.25 - Real Santa2.JPG"
touch "test_folder/17.12.25 - Fake Santa.jpg"
touch "test_folder/17.12.25 - Fake Santa2.JPG"
touch "test_folder/raw/17.12.25 - Real Santa.dng"
touch "test_folder/raw/17.12.25 - Real Santa2.cr2"
touch "test_folder/raw/17.12.25 - Real Santa3.crw"
=> Launch the script in "raw" folder.
Attended result :
"17.12.25 - Real Santa3.crw" is moved to "to_delete"
We are alerted than "17.12.25 - Fake Santa2.JPG", "picture.jPg" and "17.12.25 - Fake Santa.jpg" has no raw image and we find it in "jpg_only"
JPG with raw are moved in
File than are not raw or jpg are moved to "jpg_camera"

jpg without raw :  ./../17.12.25 - Fake Santa.jpg
jpg without raw :  ./../17.12.25 - Fake Santa2.JPG
jpg without raw :  ./../picture.jpg
# Scan the RAW to delete the one without jpg
move raw to trash  ./17.12.25 - Real Santa3.crw


'''

# Define directory to move files
to_delete_folder = "./to_delete"
jpg_only_folder = "../jpg_only"

# Define your file extensions, case is sensitive.
raw_pattern = "[dcCDrR][wWaAnrNR][GWg2w]" # dng, crw, cr2, raw, rw2
jpg_pattern = "[jJ][pP][Gg]" # jpg

def move_inexisting_file(first_list, second_list, pattern, destination_dir):
    global dry_run
    for f in first_list:
        #print("jpg : ", f)
        original_name = os.path.basename(f)
        base_name = os.path.splitext(original_name)[0]
        #print(base_name)
        r = re.compile(".*" + base_name + "\." + pattern)
        matching_file = list(filter(r.match, second_list))
        #print(matching_file)
        if not len(matching_file):
            destination_file = destination_dir + "/" + original_name
            print("Moving : ", f, " to ", destination_file)
            if not dry_run :
                if not os.path.exists(destination_dir):
                    os.makedirs(destination_dir)
                os.rename(f, destination_file)

def main(argv):
    global dry_run
    dry_run = True
    print('Reminder : Run in RAW folder !!!')
    try:
      opts, args = getopt.getopt(argv,'hm')
    except getopt.GetoptError:
      print('Usage : delete_raw_if_jpg_not_exist.py -m to move files')
      sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('Usage : delete_raw_if_jpg_not_exist.py [-m]')
            print('Use "-m" to run the script with touching files.')
            sys.exit()
        elif opt == '-m':
         dry_run = False
    rawdir = os.curdir + "/*." + raw_pattern
    jpgdir = os.curdir + "/../*." + jpg_pattern
    raw_list = glob.glob(rawdir)
    jpg_list = glob.glob(jpgdir)
    print("# Scan the jpg to find the one without raw and put it in 'jpg_only'")
    move_inexisting_file(jpg_list, raw_list, raw_pattern, jpg_only_folder)
    print("# Scan the RAW to delete the one without jpg")
    move_inexisting_file(raw_list, jpg_list, jpg_pattern, to_delete_folder)
    if dry_run :
        print("--------------------------------------------------")
        print("- WARNING : Dry run, no files has been touched ! -")
        print("- Use '-m' switch to really move file            -")
        print("--------------------------------------------------")
    print("Done")

if __name__ == "__main__":
   main(sys.argv[1:])
