#!/usr/bin/python3

# Description: This script looks in a upper directory for files.
#              For each file it looks in current directory if the file exist
#              with the same number (more than 3 digits in filename),
#              Then it rename it in current folder with same name.
#
# Huge modifications of a script from Thomas Dahlmann and Renaud Boitouzet ( https://photo.stackexchange.com/questions/16401/how-to-delete-jpg-files-but-only-if-the-matching-raw-file-exists/49377#49377 )
#
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
touch "test_folder/18.08.12 - 60793 - RealSanta - Flying (Canon).jpg"
touch "test_folder/18.08.12 - 60794 - RealSanta - Landind.jpg"
touch "test_folder/18.08.12 - 60795 - RealSanta - TakeOff.jpg"
touch "test_folder/17.12.25 - Real Santa2.JPG"
touch "test_folder/17.12.25 - Fake Santa.jpg"
touch "test_folder/17.12.25 - Fake Santa2.JPG"
touch "test_folder/raw/18.08.12 - 60793 - RealSanta.crW"
touch "test_folder/raw/18.08.12 - 60794.cr2"
touch "test_folder/raw/P60795.raw"
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

def move_inexisting_file(first_list, second_list, destination_dir):
    global dry_run
    for f in first_list:
        #print("jpg : ", f)
        original_name = os.path.basename(f)
        base_name = os.path.splitext(original_name)[0]
        #print(base_name)
        m = re.search(r'([0-9]{3,10})', base_name)
        if m:
            file_number = m.group(1)
            #print( 'Match found: ', file_number)
        else:
            print('No file number found in', original_name)
            continue
        #print(base_name, "as num",file_number)
        r = re.compile(".*" + file_number + r".*")
        matching_file = list(filter(r.match, second_list))
        #print(matching_file)
        if len(matching_file)<1:
            print("No corresponding file found for", original_name)
        elif len(matching_file)>1:
            print("More than one corresponding file found for", original_name)
        if len(matching_file)==1:
            matching_file = matching_file[0]
            dest_original_name = os.path.basename(matching_file)
            dest_extension = os.path.splitext(dest_original_name)[1]
            destination_file = os.path.join(destination_dir, base_name + dest_extension)
            #print(destination_file)
            print("Moving : ", matching_file, " to ", destination_file)
            if not dry_run :
                if not os.path.exists(destination_file):
                    os.rename(matching_file, destination_file)

def main(argv):
    global dry_run
    dry_run = True
    print('Reminder : Run in RAW folder !!!')
    try:
      opts, args = getopt.getopt(argv,'hr')
    except getopt.GetoptError:
      print('Usage : rename_raw_from_jpg.py -r to rename files')
      sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('Usage : rename_raw_from_jpg.py [-r]')
            print('Use "-m" to run the script with touching files.')
            sys.exit()
        elif opt == '-r':
         dry_run = False
    rawdir = os.curdir
    jpgdir = os.path.join(os.curdir, r"..")
    print("Looking into", os.path.realpath(jpgdir), " to rename in", os.path.realpath(rawdir))
    raw_list = glob.glob(rawdir + "/*.*")
    jpg_list = glob.glob(jpgdir + "/*.*")

    print("# Scan the upper folder to rename the current")
    move_inexisting_file(jpg_list, raw_list, rawdir)
    if dry_run :
        print("--------------------------------------------------")
        print("- WARNING : Dry run, no files has been touched ! -")
        print("- Use '-r' switch to really rename file            -")
        print("--------------------------------------------------")
    print("Done")

if __name__ == "__main__":
   main(sys.argv[1:])
