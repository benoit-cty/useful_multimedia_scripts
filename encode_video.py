#!/usr/bin/python3

# Description: This script looks for videos to transcode.
#
# Tested under Ubuntu 22.04
# You need FFMPEG pip install ffmpeg-python 
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
suffix = ""
def encode_one_video(video_file, destination, quality, bitrate=2, codec="h264_nvenc"):
    ffmpeg_cli = ""
    if codec == "h264_nvenc":
        #ffmpeg
        # ffmpeg : -y -hwaccel cuvid -c:v h264_cuvid -i /media/data-nvme/tmp/P1130291.MP4 -cq:v 19 -rc vbr_hq
        #     -rc-lookahead 32 -b:v 3000K -profile:v main -maxrate:v 8M -c:v hevc_nvenc -preset slow -c:a copy
        #     -c:s copy -f matroska /tmp/P1130291.mkv
        # With nvenc, CQ "replace" quality
        # -c:v hevc_nvenc -rc vbr -cq 27 -qmin 27 -qmax 27 -b:v 0
        #quality = str(quality)
        ffmpeg_cli = f'/usr/bin/ffmpeg -y -hide_banner -loglevel warning -i "{video_file}"'
        ffmpeg_cli += f' -c:v h264_nvenc -rc vbr -cq:v {quality}  -qmin:v {quality} -qmax:v {quality} -b:v 0 -maxrate 8M -bufsize 8M -preset slow '
        ffmpeg_cli += f' -c:a aac -b:a 128k -c:s copy "{destination}"'
    if codec == "hevc_nvenc":
        ffmpeg_cli = f'/usr/bin/ffmpeg -y -hide_banner -loglevel warning -i "{video_file}" '
        
        # ffmpeg_cli += f'-c:v hevc_nvenc -preset slow -crf {quality}'
        #ffmpeg_cli += ' -profile:v main  -c:v hevc_nvenc -qp ' + str(quality) + '-preset slow '
        ffmpeg_cli += f' -profile:v main  -c:v hevc_nvenc -rc vbr -cq:v {quality}  -qmin:v {quality} -qmax:v {quality} -tag:v hvc1  -b:v 0 -maxrate 8M -bufsize 8M -preset slow ' # -qmin:v {quality} -qmax:v {quality}
        ffmpeg_cli += f' -c:a aac -b:a 128k -c:s copy "{destination}"' # -f matroska
    if ffmpeg_cli == "":
        raise AttributeError("No codec found !")
    print('\t', ffmpeg_cli)
    process = subprocess.Popen(ffmpeg_cli,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True)
    stdout, stderr = process.communicate()
    print(stdout, stderr)

def normalize_audio_of_video(video_file, destination):
    """Normalize sound level using EBI
    Args:
        video_file (_type_): _description_
        destination (_type_): _description_
        quality (_type_): _description_
        bitrate (int, optional): _description_. Defaults to 2.
    """
    ffmpeg_cli = f'ffmpeg-normalize "{video_file}" -o "{destination}" -c:a aac -b:a 128k'
    print(ffmpeg_cli)
    process = subprocess.Popen(ffmpeg_cli,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True)
    stdout, stderr = process.communicate()
    print(stdout, stderr)

def process_videos(videos_files, destination_folder, trash_folder='./Trash', normalize_audio=False):
    """https://github.com/slhck/ffmpeg-normalize
    """

    if videos_files is None:
        print("No videos found !")
        return
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    for video_file in videos_files:
        original_name = os.path.basename(video_file)
        base_name = os.path.splitext(original_name)[0]
        base_ext = os.path.splitext(original_name)[1]
        print('Processing', video_file)
        try:
            probe = ffmpeg.probe(video_file)
        except Exception as e:
            print(f"\tERROR : Unexpected error reading {video_file} :", e, sys.exc_info())
            continue


        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
        # codec_name = video_streams[0]['codec_name'] if 'codec_name' in video_streams[0] else None
        # height = video_streams[0]['height'] if 'height' in video_streams[0] else None
        # creation_time = video_streams[0]['tags']['creation_time'] if 'creation_time' in video_streams[0]['tags'] else None
        codec_name = video_streams[0].get('codec_name') # return None if not found
        height = int(video_streams[0].get('height'))
        print(f"\t{height=} {codec_name=}")
        if 'tags' in video_streams[0]:
            creation_time = video_streams[0]['tags'].get('creation_time') # TODO: use it to rename ?
        else:
            creation_time = None
        
        if codec_name == 'hevc':
            print("\tAlready in HEVC, don't touch it.")
            continue
        """
        Recommended settings for x264 and x265 encoders:
            RF 18-22 for 480p/576p Standard Definition1
            RF 19-23 for 720p High Definition2
            RF 20-24 for 1080p Full High Definition3
            RF 22-28 for 2160p 4K Ultra High Definition4
    -crf 0 high-quality, low compression, large file
    -crf 23 default
    -crf 51 low-quality, high compression, small file
        """
        if height > 2200: quality=25 # For 8K
        elif height > 1200: quality=24 # For 2.7K and 4K
        elif height > 800: quality=26 # For 1080p
        elif height > 600: quality=24 # For 720p
        else: quality = 22 # For low res
        print('\t',base_name, codec_name, height, creation_time, 'Auto quality=', quality)
        destination_file = destination_folder + base_name + f'-hevc_{quality}{suffix}.mp4'
        normalize_sound_file = destination_folder + base_name + f'-hevc_{quality}{suffix}{base_ext}'
        if normalize_audio:
            print("\tNormalize sound level with ffmpeg-normalize")
            normalize_audio_of_video(video_file, normalize_sound_file)
            encode_one_video(normalize_sound_file, destination_file, quality)
        else:
            encode_one_video(video_file, destination_file, quality)
        # check if we reduce size
        new_size = os.stat(destination_file).st_size
        previous_size = os.stat(video_file).st_size
        reduction = new_size / previous_size
        if reduction > 0.9:
            print(f"\tWARNING : The size reduction is not significative {new_size}/{previous_size} = {reduction}:", (1-reduction)*100)
        else:
            print(f'\tWe reduce the file size by {(1-reduction)*100:.1f}% - {new_size}/{previous_size} = {reduction}')
            trash_destination = os.path.join(trash_folder, original_name)
            print(f"\tMove original to {trash_destination}\n")
        #break


def main(argv):
    global dry_run
    dry_run = True
    print('Reminder : Run in video folder !!!')
    video_dir = os.curdir + "/*." + video_pattern
    video_list = sorted(glob.glob(video_dir))
    process_videos(video_list, destination)
    print("Done")

if __name__ == "__main__":
   main(sys.argv[1:])