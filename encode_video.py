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
try:
    import ffmpeg
    import click
except ImportError:
    print("You need to install ffmpeg-python : pip install ffmpeg-python ffmpeg-normalize click")
    sys.exit(1)

from typing import List

video_pattern = "[mMrR][23pPkKoO][4vVdDtT]*"
destination = './encode-quality-variable/'

"""
pip install ffmpeg-python
"""
suffix = ""
def encode_one_video(video_file, destination, quality, video_output_size, bitrate=2, codec="h264_nvenc", ):
    ffmpeg_cli = ""
    video_output_filename = ""
    if codec == "h264":
        codec="h264_nvenc"
    if codec == "hevc":
        codec="hevc_nvenc"
    if codec == "h264_nvenc":
        #ffmpeg
        # ffmpeg : -y -hwaccel cuvid -c:v h264_cuvid -i /media/data-nvme/tmp/P1130291.MP4 -cq:v 19 -rc vbr_hq
        #     -rc-lookahead 32 -b:v 3000K -profile:v main -maxrate:v 8M -c:v hevc_nvenc -preset slow -c:a copy
        #     -c:s copy -f matroska /tmp/P1130291.mkv
        # With nvenc, CQ "replace" quality
        # -c:v hevc_nvenc -rc vbr -cq 27 -qmin 27 -qmax 27 -b:v 0
        #quality = str(quality)
        ffmpeg_cli = f'/usr/bin/ffmpeg -y -hide_banner -loglevel warning -i "{video_file}"'
        ffmpeg_cli += f' -vf scale=-1:{video_output_size} -c:v {codec} -rc vbr -cq:v {quality}  -qmin:v {quality} -qmax:v {quality} -b:v 0 -maxrate 4M -bufsize 6M -preset slow '
        video_output_filename = f"{destination}-{video_output_size}-{codec}-{quality}{suffix}.mp4"
        ffmpeg_cli += f' -c:a aac -b:a 128k -c:s copy "{video_output_filename}"'
    if codec == "hevc_nvenc":
        ffmpeg_cli = f'/usr/bin/ffmpeg -y -hide_banner -loglevel warning -i "{video_file}" '
        
        # ffmpeg_cli += f'-c:v hevc_nvenc -preset slow -crf {quality}'
        #ffmpeg_cli += ' -profile:v main  -c:v hevc_nvenc -qp ' + str(quality) + '-preset slow '
        ffmpeg_cli += f' -profile:v main  -c:v hevc_nvenc -rc vbr -cq:v {quality}  -qmin:v {quality} -qmax:v {quality} -tag:v hvc1  -b:v 0 -maxrate 8M -bufsize 8M -preset slow ' # -qmin:v {quality} -qmax:v {quality}
        video_output_filename = f"{destination}-{video_output_size}-{codec}-{quality}{suffix}.mkv"
        ffmpeg_cli += f' -c:a aac -b:a 128k -c:s copy -f matroska "{video_output_filename}"'
    if ffmpeg_cli == "":
        raise AttributeError("No codec found !")
    print('\tCommand : ', ffmpeg_cli)
    process = subprocess.Popen(ffmpeg_cli,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True)
    stdout, stderr = process.communicate()
    print(stdout, stderr)
    return video_output_filename

def normalize_audio_of_video(video_file, destination):
    """Normalize sound level using EBI (legacy function for compatibility)
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
    if process.returncode != 0:
        print(f"Error : {stderr}")
        if "ffmpeg-normalize: not found" in stderr:
            print("You need to install ffmpeg-normalize : pip install ffmpeg-normalize")
        raise Exception(f"Error : {stderr}")

def boost_and_normalize_audio(video_file, destination, two_pass=False, target_loudness=-16, true_peak=-1.5, lra=11, bitrate="192k"):
    """Boost and normalize audio using dynamic compression and EBU R128 loudness normalization
    
    Args:
        video_file (str): Input video file path
        destination (str): Output video file path
        two_pass (bool): Use two-pass normalization for higher precision
        target_loudness (int): Target integrated loudness (LUFS) - default -16 for streaming
        true_peak (float): Maximum true peak to avoid clipping - default -1.5
        lra (int): Loudness Range (lower = more consistent volume) - default 11
        bitrate (str): Audio bitrate - default 192k
    """
    import json
    import tempfile
    
    # Audio filter chain: compression + loudness normalization
    audio_filter = (
        f"acompressor=threshold=-20dB:ratio=3:attack=50:release=500,"
        f"loudnorm=I={target_loudness}:TP={true_peak}:LRA={lra}:print_format=summary"
    )
    
    if two_pass:
        print("\tUsing two-pass audio normalization for higher precision...")
        
        # First pass: analyze audio
        analyze_filter = f"loudnorm=I={target_loudness}:TP={true_peak}:LRA={lra}:print_format=json"
        analyze_cmd = f'/usr/bin/ffmpeg -hide_banner -i "{video_file}" -af "{analyze_filter}" -f null -'
        
        print(f"\tFirst pass (analyzing): {analyze_cmd}")
        process = subprocess.Popen(analyze_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        shell=True)
        stdout, stderr = process.communicate()
        
        # Extract JSON from stderr (ffmpeg outputs analysis there)
        json_start = stderr.find('{')
        json_end = stderr.rfind('}') + 1
        
        if json_start != -1 and json_end != -1:
            try:
                json_data = json.loads(stderr[json_start:json_end])
                measured_i = json_data.get('input_i', target_loudness)
                measured_tp = json_data.get('input_tp', true_peak)
                measured_lra = json_data.get('input_lra', lra)
                measured_thresh = json_data.get('input_thresh', -30)
                
                print(f"\tMeasured values: I={measured_i}, TP={measured_tp}, LRA={measured_lra}, Thresh={measured_thresh}")
                
                # Second pass: apply normalization with measured values
                audio_filter = (
                    f"acompressor=threshold=-20dB:ratio=3:attack=50:release=500,"
                    f"loudnorm=I={target_loudness}:TP={true_peak}:LRA={lra}:"
                    f"measured_I={measured_i}:measured_TP={measured_tp}:measured_LRA={measured_lra}:"
                    f"measured_thresh={measured_thresh}:linear=true"
                )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"\tWarning: Could not parse analysis data, falling back to single-pass: {e}")
        else:
            print("\tWarning: No analysis data found, falling back to single-pass")
    
    # Build the final command
    ffmpeg_cli = (
        f'/usr/bin/ffmpeg -y -hide_banner -loglevel warning -i "{video_file}" '
        f'-c:v copy -af "{audio_filter}" -c:a aac -b:a {bitrate} "{destination}"'
    )
    
    print(f"\tAudio normalization command: {ffmpeg_cli}")
    process = subprocess.Popen(ffmpeg_cli,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True)
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        print(f"Error normalizing audio: {stderr}")
        raise Exception(f"Audio normalization failed: {stderr}")
    
    print(f"\tAudio normalization completed: {destination}")
    return destination

def process_videos(videos_files: List, destination_folder:str, video_output_size:str, codec:str, trash_folder='./Trash', normalize_audio=False, video_quality=None, boost_audio=False, two_pass_audio=False, target_loudness=-16, audio_bitrate="192k"):
    """https://github.com/slhck/ffmpeg-normalize
    Process videos to transcode them
    Args:
        videos_files (List): List of videos to process
        destination_folder (Path): Destination folder
        trash_folder (str, optional): Where to move original file. Defaults to './Trash'.
        normalize_audio (bool, optional): Normalize audio level using legacy method. Defaults to False.
        boost_audio (bool, optional): Use advanced audio compression and EBU R128 normalization. Defaults to False.
        two_pass_audio (bool, optional): Use two-pass audio normalization for higher precision. Defaults to False.
        target_loudness (int, optional): Target integrated loudness (LUFS). Defaults to -16.
        audio_bitrate (str, optional): Audio bitrate for normalized audio. Defaults to "192k".
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
        if int(video_output_size) > height:
            print(f"\t Video size ({height}) is smaller than {video_output_size}")
            video_output_size = str(height)
        if 'tags' in video_streams[0]:
            creation_time = video_streams[0]['tags'].get('creation_time') # TODO: use it to rename ?
        else:
            creation_time = None
        
        if codec_name == 'hevc':
            print("\tAlready in HEVC, don't touch it.")
            continue
        """
        Recommended settings for x264 and x265 encoders:
            CRF 0 high-quality
            RF 18-22 for 480p/576p Standard Definition1
            RF 19-23 for 720p High Definition2
            RF 20-24 for 1080p Full High Definition3
            RF 22-28 for 2160p 4K Ultra High Definition4
            CRF 51 low-quality, high compression, small file
        """
        height = int(video_output_size)
        if video_quality is None:
            if height > 2200: video_quality=25 # For 8K
            elif height > 1200: video_quality=24 # For 2.7K and 4K
            elif height > 800: video_quality=28 # 26 : OK # For 1080p
            elif height > 600: video_quality=24 # For 720p
            else: video_quality = 22 # For low res
        print('\t',base_name, codec_name, height, creation_time, 'Auto quality=', video_quality)
        destination_file = destination_folder + base_name
        normalize_sound_file = destination_folder + base_name + f'-{video_quality}{suffix}{base_ext}'
        
        # Handle different audio processing options
        if boost_audio:
            print(f"\tBoost and normalize audio with compression and EBU R128 (target: {target_loudness} LUFS)")
            boost_and_normalize_audio(video_file, normalize_sound_file, two_pass=two_pass_audio, 
                                    target_loudness=target_loudness, bitrate=audio_bitrate)
            video_output_filename = encode_one_video(normalize_sound_file, destination_file, video_quality, video_output_size)
        elif normalize_audio:
            print("\tNormalize sound level with ffmpeg-normalize (legacy method)")
            normalize_audio_of_video(video_file, normalize_sound_file)
            video_output_filename = encode_one_video(normalize_sound_file, destination_file, video_quality, video_output_size)
        else:
            video_output_filename = encode_one_video(video_file, destination_file, video_quality, video_output_size)
        # check if we reduce size
        new_size = os.stat(video_output_filename).st_size
        previous_size = os.stat(video_file).st_size
        reduction = new_size / previous_size
        if reduction > 0.9:
            print(f"\tWARNING : The size reduction is not significative {new_size}/{previous_size} = {reduction}:", (1-reduction)*100)
        else:
            print(f'\tWe reduce the file size by {(1-reduction)*100:.1f}% - {new_size}/{previous_size} = {reduction}')
            trash_destination = os.path.join(trash_folder, original_name)
            print(f"\tMove original to {trash_destination}\n")
        #break

# Use click to add a video size parameter
@click.command()
@click.option('-s', '--video_output_size', default='1080', help='Video output size (1080 (default), 720, 480)')
@click.option('-q', '--video_quality', default='24', help='Video quality from 0 (high) to 51 (low) default 24')
@click.option('-c', '--codec', default='h264', help='Codec to use (h264 (default), hevc)')
@click.option('-n', '--normalize_audio', is_flag=True, help='Normalize audio level (legacy method)', default=False)
@click.option('-b', '--boost_audio', is_flag=True, help='Boost and normalize audio with compression and EBU R128', default=False)
@click.option('--two_pass_audio', is_flag=True, help='Use two-pass audio normalization for higher precision', default=False)
@click.option('--target_loudness', default=-16, type=int, help='Target integrated loudness in LUFS (default: -16 for streaming)')
@click.option('--audio_bitrate', default='192k', help='Audio bitrate for normalized audio (default: 192k)')
def encode(video_output_size, video_quality, codec, normalize_audio, boost_audio, two_pass_audio, target_loudness, audio_bitrate):
    """Encode all videos in current folder to HEVC codec
    
    Audio processing options:
    - Use -n for legacy ffmpeg-normalize audio normalization
    - Use -b for advanced audio compression + EBU R128 normalization
    - Use --two_pass_audio with -b for highest quality audio normalization
    - Adjust --target_loudness for different platforms (-16 for streaming, -23 for broadcast)
    """
    global dry_run
    dry_run = True
    
    # Validate audio options
    if normalize_audio and boost_audio:
        click.echo("Warning: Both -n and -b specified. Using advanced boost audio (-b) method.")
        normalize_audio = False
    
    if two_pass_audio and not boost_audio:
        click.echo("Warning: --two_pass_audio requires --boost_audio (-b). Enabling boost audio.")
        boost_audio = True
    
    # click.echo('Reminder : Run in video folder !!!')
    video_dir = os.curdir + "/*." + video_pattern
    # Get all videos files from video_dir
    video_list = sorted(glob.glob(video_dir))
    # Add the result of click
    process_videos(video_list, destination, video_output_size, codec, 
                  video_quality=video_quality, normalize_audio=normalize_audio,
                  boost_audio=boost_audio, two_pass_audio=two_pass_audio,
                  target_loudness=target_loudness, audio_bitrate=audio_bitrate)
    click.echo("Done")

if __name__ == "__main__":
   encode()