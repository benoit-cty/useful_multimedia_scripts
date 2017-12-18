#!/sbin/python3
# Based on

# Description: This script looks in a sub-directorie for RAW files.
#              For each file it looks in upper directory if the JPG exist
#              if not, it move the RAW to trash.
#
# Original Author:  Thomas Dahlmann and Renaud Boitouzet ( https://photo.stackexchange.com/questions/16401/how-to-delete-jpg-files-but-only-if-the-matching-raw-file-exists/49377#49377 )
#
# WARNING if you use raw only sometime : they will be put in "to_delete"
# one way  to avoid it is to launch the script before deleting jpg,
# then renaming "to_delete" to "raw_only"
#
import os
import glob
import re

'''
How to test it :
mkdir test_folder
touch test_folder/random_file.txt
mkdir test_folder/raw
touch test_folder/picture.jpg
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
We are alerted than "17.12.25 - Fake Santa2.JPG" has no raw image and we find it in "jpg_only"
JPG with raw are moved in
File than are not raw or jpg are moved to "jpg_camera"
'''


# define your file extensions here, case is ignored.
# Please start with a dot.
# multiple raw extensions allowed, single jpg extension only
raw_extensions = (".Dng", ".cR2", ".nef", ".crw")
jpg_extension = ".jPg"

# define waste basket directory here. Include trainling slash or backslash.
# Windows : waste_dir = "C:\path\to\waste\"
waste_dir = "./to_delete/"

# find files
def locate(folder, extensions):
    '''Locate files in directory with given extensions'''
    for filename in os.listdir(folder):
        if filename.endswith(extensions):
            yield os.path.join(folder, filename)

# make waste basket dir
if not os.path.exists(waste_dir):
    os.makedirs(waste_dir)

# Make search case insensitive
raw_ext = tuple(map(str.lower,raw_extensions)) + tuple(map(str.upper,raw_extensions))
jpg_ext = (jpg_extension.lower(), jpg_extension.upper())




basedir = os.curdir + "/*.[dcCD][nrNR][GWg2w]"
raw_list = glob.glob(basedir)
jpg_list = glob.glob(os.curdir + "/../*.[jJ][pP][Gg]")
#print(jpg_list)

#TODO: Scan the jpg to find the one without raw and put it in "jpg_only"

for f in jpg_list:
    print("raw : ", f)
    base_name = os.path.basename(f)
    base_name = os.path.splitext(base_name)[0]
    #print(base_name)
    r = re.compile(".*" + base_name + "\.[jJ][pP][Gg]")
    matching_file = list(filter(r.match, jpg_list))
    #print(matching_file)
    if len(matching_file):
        print("exist, leave it")
    else:
        print("delete raw ", f)

#TODO: Ask before doing all the moves

# Now scan the RAW
raw_list = glob.glob(basedir)
jpg_list = glob.glob(os.curdir + "/../*.[jJ][pP][Gg]")

for f in raw_list:
    print("raw : ", f)
    base_name = os.path.basename(f)
    base_name = os.path.splitext(base_name)[0]
    #print(base_name)
    r = re.compile(".*" + base_name + "\.[jJ][pP][Gg]")
    matching_file = list(filter(r.match, jpg_list))
    #print(matching_file)
    if len(matching_file):
        print("exist, leave it")
    else:
        print("delete raw ", f)


print("fin")
exit(1)


#find subdirectories
for path, dirs, files in os.walk(os.path.abspath(root)):
    #TODO: uniquement fichiers
    print(path)
    raw_hash = {}
    for raw in locate(path, raw_ext):
        base_name = os.path.basename(raw)
        base_name = os.path.splitext(base_name)[0]
        raw_hash[base_name] = True

    # find pairs and move jpgs of pairs to waste basket
    #TODO: remonter d'un repertoire
    for jpg in locate(path, jpg_ext):
        base_name = os.path.basename(jpg)
        base_name = os.path.splitext(base_name)[0]
        if base_name not in raw_hash:
            jpg_base_name_with_ext = base_name + jpg_extension
            new_jpg = waste_dir + jpg_base_name_with_ext
            print(path, base_name, jpg, waste_dir)
            if os.path.exists(new_jpg):
                #os.remove(jpg)
                print("Efface ", new_jpg)
            else:
                #os.rename(jpg, new_jpg)
                print("Rename ", jpg, "=>", new_jpg)
