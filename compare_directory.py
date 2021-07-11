#!/usr/bin/python3
# Based on https://gist.github.com/mscalora/e86e2bbfd3c24a7c1784f3d692b1c684

# Description: This script looks in a directory for files.
#              For each file it looks in other directory if the file exist
#
# compare_directory.py dir1 dir2 '/<regexp of pattern to ignore : \.git >/'

import os, sys, re

skip = re.compile(sys.argv[3] if len(sys.argv) > 3 else '$.')

def compare_dirs(d1: "first directory name", d2: "second directory name"):
    def print_local(a, msg):
        print('DIR ' if a[2] else 'FILE', a[1], msg)
    # ensure validity
    for d in [d1,d2]:
        if not os.path.isdir(d):
            raise ValueError("not a directory: " + d)
    # get relative path
    l1 = [(x,os.path.join(d1,x)) for x in os.listdir(d1)]
    l2 = [(x,os.path.join(d2,x)) for x in os.listdir(d2)]
    # determine type: directory or file?
    l1 = sorted([(x,y,os.path.isdir(y)) for x,y in l1])
    l2 = sorted([(x,y,os.path.isdir(y)) for x,y in l2])
    i1 = i2 = 0
    common_dirs = []
    while i1<len(l1) and i2<len(l2):
        if l1[i1][0] == l2[i2][0]:      # same name
            if l1[i1][2] == l2[i2][2]:  # same type
                if l1[i1][2]:           # remember this folder for recursion
                    common_dirs.append((l1[i1][1], l2[i2][1]))
            elif not skip.search(l1[i1][1]):
                print_local(l1[i1],'type changed')
            i1 += 1
            i2 += 1
        elif l1[i1][0]<l2[i2][0]:
            if not skip.search(l1[i1][1]):
                print_local(l1[i1],'removed')
            i1 += 1
        elif l1[i1][0]>l2[i2][0]:
            if not skip.search(l2[i2][1]):
                print_local(l2[i2],'added')
            i2 += 1
    while i1<len(l1):
        if not skip.search(l1[i1][1]):
            print_local(l1[i1],'removed')
        i1 += 1
    while i2<len(l2):
        if not skip.search(l2[i2][1]):
            print_local(l2[i2],'added')
        i2 += 1
    # # compare subfolders recursively
    # for sd1,sd2 in common_dirs:
    #     compare_dirs(sd1, sd2)

if __name__=="__main__":
    compare_dirs(sys.argv[1], sys.argv[2])