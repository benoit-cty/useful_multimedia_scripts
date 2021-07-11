#!/usr/bin/python3

# Description: This script looks for videos to transcode.
#
# Tested under Ubuntu 18.04
# You need FFMPEG
#
import os
import glob
import re
import sys
import subprocess
import ffmpeg

video_pattern = "[mMrR][23pPkKoO][4vVdDtT]*"
destination = './encode-quality-variable/'

"""
pip install ffmpeg-python
"""

def encode_one_video(video_file, destination, quality):
    #ffmpeg
    # ffmpeg : -y -hwaccel cuvid -c:v h264_cuvid -i /media/data-nvme/tmp/P1130291.MP4 -cq:v 19 -rc vbr_hq
    #     -rc-lookahead 32 -b:v 3000K -profile:v main -maxrate:v 8M -c:v hevc_nvenc -preset slow -c:a copy
    #     -c:s copy -f matroska /tmp/P1130291.mkv
    # With nvenc, CQ "replace" quality
    # -c:v hevc_nvenc -rc vbr -cq 27 -qmin 27 -qmax 27 -b:v 0
    #quality = str(quality)
    ffmpeg_cli = '/usr/bin/ffmpeg -y -hide_banner -loglevel warning -i "' + video_file + '" '
    #ffmpeg_cli += ' -profile:v main  -c:v hevc_nvenc -qp ' + str(quality) + '-preset slow '
    ffmpeg_cli += f' -profile:v main  -c:v hevc_nvenc -rc vbr -cq {quality} -qmin {quality-2} -qmax {quality+2} -b:v 0 -preset slow '
    ffmpeg_cli += f' -c:a copy -c:s copy -f matroska "{destination}"'
    print(ffmpeg_cli)
    process = subprocess.Popen(ffmpeg_cli,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True)
    stdout, stderr = process.communicate()
    print(stdout, stderr)
    #print(stderr)

def process_videos(videos_files, destination_folder, trash_folder='./Trash'):
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    for video_file in videos_files:
        original_name = os.path.basename(video_file)
        base_name = os.path.splitext(original_name)[0]
        print('Processing', video_file)
        try:
            probe = ffmpeg.probe(video_file)
        except:
            print(f"ERROR : Unexpected error reading {video_file} :", sys.exc_info()[0])
            continue

        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
        # codec_name = video_streams[0]['codec_name'] if 'codec_name' in video_streams[0] else None
        # height = video_streams[0]['height'] if 'height' in video_streams[0] else None
        # creation_time = video_streams[0]['tags']['creation_time'] if 'creation_time' in video_streams[0]['tags'] else None
        codec_name = video_streams[0].get('codec_name') # return None if not found
        height = int(video_streams[0].get('height'))
        if 'tags' in video_streams[0]:
            creation_time = video_streams[0]['tags'].get('creation_time') # TODO: use it to rename ?
        else:
            creation_time = None
        
        if codec_name == 'hevc':
            print("Already in HEVC, don't touch it.")
            continue
        """
        Recommended settings for x264 and x265 encoders:
            RF 18-22 for 480p/576p Standard Definition1
            RF 19-23 for 720p High Definition2
            RF 20-24 for 1080p Full High Definition3
            RF 22-28 for 2160p 4K Ultra High Definition4
        """
        if height > 2200: quality=25 # For 8K
        elif height > 1200: quality=22 # For 2.7K and 4K
        elif height > 800: quality=21 # For 1080p
        elif height > 600: quality=20 # For 720p
        else: quality = 18 # For low res
        print('\t',base_name, codec_name, height, creation_time, 'Auto quality=', quality)
        destination_file = destination_folder + base_name + f'-hevc_{quality}.mkv'
        encode_one_video(video_file, destination_file, quality)
        # check if we reduce size
        new_size = os.stat(destination_file).st_size
        previous_size = os.stat(video_file).st_size
        reduction = new_size / previous_size
        if reduction < 0.1:
            print(f"WARNING : The size reduction is not significative {new_size}/{previous_size} = {reduction}:", (1-reduction)*100)
        else:
            print(f'We reduce the file size by {(1-reduction)*100:.1f}% - {new_size}/{previous_size} = {reduction}')
        trash_destination = os.path.join(original_name, trash_folder)
        print('\t', "Move original to ", trash_destination)
        #break


def main(argv):
    global dry_run
    dry_run = True
    print('Reminder : Run in video folder !!!')
    video_dir = os.curdir + "/*." + video_pattern
    video_list = glob.glob(video_dir)
    process_videos(video_list, destination)
    print("Done")

if __name__ == "__main__":
   main(sys.argv[1:])