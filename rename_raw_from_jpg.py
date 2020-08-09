#!/usr/bin/python3

# Description: This script looks in a upper directory for files.
#              For each file it looks in current directory if the file exist
#              with the same number (between 3 and 50 digits in filename),
#              Then it rename it in current folder with same name.
#
# Make for renaming RAW after JPG but it could do the same for any extensions.
#
#
# Huge modifications of a script from Thomas Dahlmann and Renaud Boitouzet ( https://photo.stackexchange.com/questions/16401/how-to-delete-jpg-files-but-only-if-the-matching-raw-file-exists/49377#49377 )
#
#
# Tested under Ubuntu 18.04 and Windows 10
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
touch "test_folder/18.08.12 - 60793 - RealSanta - Flying (Canon).jpg"
touch "test_folder/18.08.12 - 60794 - RealSanta - Landind.jpg"
touch "test_folder/18.08.12 - 60795 - RealSanta - TakeOff.jpg"
touch "test_folder/18.08.12 - 60796 - RealSanta - TakeOff.jpg"
touch "test_folder/18.08.12 - 60796 - RealSanta - TakeOff-ret.jpg"
touch "test_folder/raw/garbage.jPg" # No file number
touch "test_folder/raw/18.08.12 - 60793 - RealSanta.crW" # To be renamed
touch "test_folder/raw/18.08.12 - 60794.cr2" # To be renamed
touch "test_folder/raw/P60795.raw" # To be renamed
touch "test_folder/raw/P60796.CRW" # Multiple corresponding JPG
touch "test_folder/raw/P60797.CRW" # No corresponding JPG
touch "test_folder/raw/17.12.25 - Real Santa3.crw" # No file number
#=> Launch the script in "raw" folder :
cd test_folder/raw
python3 ../../rename_raw_from_jpg.py
# Expected result :
# No file number found in "garbage.jPg" Leave as it is.
WARNING : More than one named file found for "P60796.CRW"
No named file for "P60797.CRW"
No file number found in "17.12.25 - Real Santa3.crw" Leave as it is.

--- End of processing ---
Number of file modification: 5

'''

debug = False

def move_file(ori_name, dest_dir, dest_name):
    destination_file = os.path.join(dest_dir, dest_name)
    if debug: print(f'Moving "{ori_name}", to "{destination_file}"')
    if not dry_run :
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        os.rename(ori_name, destination_file)
        return 1
    else:
        return 0


def rename_file(named_list, to_rename_list, orphan_dir, many_match_dir):
    file_modification_nb = 0
    for file_to_rename in to_rename_list:
        if debug: print("-----------\nProcessing : ", file_to_rename)
        to_rename_basename = os.path.basename(file_to_rename)
        to_rename_without_ext = os.path.splitext(to_rename_basename)[0]
        #if debug: print('to_rename_without_ext', to_rename_without_ext)
        # Looking for number in filename
        reg_exp_match = re.search(r'([0-9]{3,50})', to_rename_without_ext)
        if reg_exp_match:
            file_number = reg_exp_match.group(1)
        else:
            print(f'No file number found in "{to_rename_basename}" Leave as it is.')
            continue
        # Looking for the same number in named files
        r = re.compile(".*" + file_number + r".*")
        matching_file = list(filter(r.match, named_list))
        if len(matching_file)<1:
            print(f'No named file for "{to_rename_basename}"')
            file_modification_nb += move_file(file_to_rename, orphan_dir, to_rename_basename)
        elif len(matching_file)>1:
            print(f'WARNING : More than one named file found for "{to_rename_basename}"')
            file_modification_nb += move_file(file_to_rename, many_match_dir, to_rename_basename)
        elif len(matching_file)==1:
            matching_file = matching_file[0]
            #if debug: print('matching_file', matching_file)
            named_without_ext = os.path.splitext(os.path.basename(matching_file))[0]
            to_rename_extension = os.path.splitext(to_rename_basename)[1]
            file_modification_nb += move_file(file_to_rename, './', named_without_ext + to_rename_extension)
    print("\n--- End of processing ---\nNumber of file modification:", file_modification_nb)

def main(argv):
    global dry_run
    dry_run = True
    print('Reminder : Run in RAW folder !!!')
    try:
      opts, _ = getopt.getopt(argv,'hr')
    except getopt.GetoptError:
      print('Usage : rename_raw_from_jpg.py -r to rename files')
      sys.exit(2)
    for opt, _ in opts:
        if opt == '-h':
            print('Usage : rename_raw_from_jpg.py [-r]')
            print('Use "-r" to run the script with files modification.')
            sys.exit()
        elif opt == '-r':
         dry_run = False
    to_rename_dir = os.curdir
    named_dir = os.path.join(os.curdir, r"..")
    orphan_dir = os.path.join(os.curdir, r"../no_named_file_found/")
    many_match_dir = os.path.join(os.curdir, r"../multiple_named_found/")
    print("Looking into", os.path.realpath(named_dir), " to rename in", os.path.realpath(to_rename_dir))
    to_rename_list = glob.glob(to_rename_dir + "/*.*")
    named_list = glob.glob(named_dir + "/*.*")

    rename_file(named_list, to_rename_list, orphan_dir, many_match_dir)
    if dry_run :
        print("--------------------------------------------------")
        print("- WARNING : Dry run, no files has been touched ! -")
        print("- Use '-r' switch to really rename file            -")
        print("--------------------------------------------------")
    print("Done")

if __name__ == "__main__":
   main(sys.argv[1:])
